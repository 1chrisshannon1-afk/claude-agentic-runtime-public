#!/usr/bin/env python3
"""pretooluse_bash — the single PreToolUse:Bash dispatcher.

Consolidates the three formerly-separate Bash guards into ONE python spawn per
Bash tool call (the old wiring spawned block_branch_ops.py, block_unscoped_commit.py
AND check_staged_scope.py — three interpreter starts, ~135ms). This module reads
the hook event ONCE via _lib, then runs each gate's PURE decision function in a
fixed order; the FIRST gate that says BLOCK wins.

GATE ORDER (first block wins):
  1. block_branch_ops   — git state-mutations (checkout/switch/stash/reset/rebase/
                          restore/clean, branch -d/-D, bulk add, commit -a) + the
                          inline CSA_ALLOW_GIT_STATE_OPS tripwire. `worktree list/
                          prune/repair` and index-only `restore --staged` are
                          narrower carve-outs, not blanket-blocked (2026-08-28).
  1b. block_head_overwrite — `git show <ref>:<path> > <path>` / `git cat-file -p
                          <ref>:<path> > <path>` (or `>>`): a plain shell
                          redirect that overwrites a path with a historical git
                          blob READ FROM THAT SAME PATH. Added 2026-09-05 after
                          GH #4387, a real Sev-1 data-loss incident: an agent
                          ran exactly this shape to "restore formatting
                          sanity" and permanently destroyed uncommitted,
                          never-staged feature work with no git-recoverable
                          trace. NOT a `git` subcommand block (show/cat-file
                          are ordinary reads) — the destructive act is the
                          shell redirect using git only as the content
                          source, so gate 1's STATE_VERBS set correctly never
                          covers it. Narrow by design: a redirect to a
                          DIFFERENT path is allowed (legitimate diffing/
                          scratch-extraction). See block_head_overwrite.py's
                          module docstring for the full rationale and the
                          same escape-hatch/tripwire convention as gate 1.
  1c. block_gcloud_identity — TWO hazard classes sharing one module because
                          they share the same gcloud-tokenizing
                          infrastructure and this gate slot, not because
                          they're the same kind of bug (see
                          block_gcloud_identity.py's own module docstring):
                          (a) IDENTITY MUTATION — a Bash command that mutates
                          the MACHINE-WIDE ambient gcloud identity: `gcloud
                          config set account|core/account`, `gcloud config
                          configurations activate`, `gcloud auth
                          activate-service-account` (no scoping flag exists
                          for this verb), `gcloud auth application-default
                          login`, or `gcloud auth login` without
                          `--no-activate` — plus a shell redirect/cp/mv/tee
                          that writes
                          ~/.config/gcloud/application_default_credentials.json
                          directly. Added 2026-09-13 (#5310): exactly like
                          the shared git working tree gates 1/1b protect,
                          gcloud's active account and the on-disk ADC file are
                          ONE machine-wide resource shared by every
                          concurrently-running agent session — mutating
                          either silently re-identifies every OTHER live
                          session's next gcloud/ADC-consuming call, with no
                          per-session isolation. ALLOWS the sanctioned
                          per-invocation scoping forms instead:
                          `gcloud --account=... <cmd>`,
                          `--impersonate-service-account=...`,
                          `CLOUDSDK_CORE_ACCOUNT=... gcloud <cmd>`, and
                          read-only verbs (`auth list`, `config get-value
                          account`). (b) UNMASKED SECRET-BEARING OUTPUT
                          (#5890, round 2 hardened
                          2026-09-24, fix round hardened further the same
                          day, round 4 fix round hardened again — see below)
                          — a `scheduler jobs`/`run services`/`run jobs`/
                          `run revisions`/`run jobs executions` (`tasks`)/
                          `run worker-pools`[`/revisions`]/`run
                          configurations`/`functions` `describe`, `list`, or
                          (for `functions` only) `deploy` whose `--format` is
                          not a field-PROJECTION naming ONLY leaf fields on
                          that resource family's allowlist (a fail-closed
                          ALLOWLIST of known-safe leaves, not a "doesn't look
                          unsafe" blocklist — a parent key like
                          `httpTarget`/`spec` is denied even though its own
                          name looks benign, since gcloud prints its whole
                          subtree); also denies `--flags-file` and 2+
                          `--format` tokens on those verbs. Denies
                          `--log-http` (resolved per gcloud's own
                          LAST-FLAG-WINS semantics — `--log-http=false`/
                          `=no`/`=0`/`--no-log-http` do NOT deny) or
                          `CLOUDSDK_CORE_LOG_HTTP` resolving ACTIVE (an
                          `unset`/`env -u` mitigation form does NOT deny —
                          P3-2, round 4 fix round) on a command that
                          ACTUALLY INVOKES gcloud somewhere (top-level OR
                          nested inside a `bash -c`/`eval` argument, a
                          heredoc body fed to a shell interpreter, or a
                          `$(...)`/backtick command substitution — B2, round
                          4 fix round; a bare text mention with no real
                          invocation anywhere is never denied) on EVERY
                          gcloud verb (leaks the full HTTP response to
                          stderr regardless of `--format`), plus `gcloud
                          config set log_http|core/log_http` (the
                          PERSISTENT, machine-wide route to the identical
                          leak) and, defensively (P3-1, unverified as
                          exploitable on the currently-installed SDK),
                          `gcloud config set format|core/format` /
                          `CLOUDSDK_CORE_FORMAT` (same resolution/mitigation
                          rules as the log-http pair). A GROUP-LEVEL flag
                          before the verb on any `run` command (`--region`,
                          `--platform`, `--cluster`, `--cluster-location`,
                          `--context`, `--kubeconfig`) can no longer hide the
                          verb path from this gate (B1, round 4 fix round).
                          Deny reason strings: `describe-unmasked-format`,
                          `list-unmasked-format`, `describe-multiple-format`,
                          `list-multiple-format`, `describe-flags-file`,
                          `list-flags-file`, `log-http-leaks-response`,
                          `config-set-log-http`, `config-set-format`,
                          `format-env-override`, `run-path-too-ambiguous`
                          (round 6/7 -- a `run` describe/list whose path
                          reading is too ambiguous, from too many
                          space-separated unrecognized flags, to safely
                          enumerate; never fires for a non-describe/list
                          `run` verb like `deploy`/`update`/`execute`
                          regardless of flag count, round 7). Same
                          escape-hatch/inline-tripwire convention and
                          fail-closed-on-parse-ambiguity posture as gate 1
                          for both classes. See block_gcloud_identity.py's
                          module docstring for the full rationale.
  2. block_unscoped_commit — bulk/unscoped `git add`/`git commit -a` (a subset of
                          gate 1, kept for its distinct operator message).
  3. check_staged_scope — MANDATORY path-scoped commits: every writing `git
                          commit` segment must carry an explicit, non-bulk
                          `-- <pathspec>` (exemptions: mid-merge/cherry-pick/
                          revert/rebase, --allow-empty, CSA_NO_REQUIRE_PATHSPEC=1)
                          — then inspects that pathspec (or, when exempted,
                          the ACTUAL git index) and blocks a commit that would
                          sweep files outside scope. See check_staged_scope.py's
                          module docstring for the full per-segment spec.
  3b. precommit_review_gate — REVIEW BEFORE THE COMMIT (added 2026-08-19 on
                          operator direction: "it shouldn't run after the
                          commit, it should run before the commit"). Denies a
                          `git commit` whose exact pending content — the digest
                          of `git diff HEAD -- <pathspec>` plus any untracked
                          paths named — has no code review on record, or whose
                          recorded review reported unresolved blockers. Cleared
                          with `record_review.py --pre-commit`. Ordered BEFORE
                          gate 4 deliberately: a review-denied commit must not
                          park the per-repo commit mutex and stall every other
                          agent. Fails OPEN on any error; per-gate rollback
                          lever CSA_NO_PRECOMMIT_REVIEW=1. Replaces the retired
                          post-commit Stop gate (task_completion_gate).
  3c. dirty_precommit_config — NEW (#4670 item 3, 2026-08-30): denies a
                          PATHSPEC commit fast when this repo's own
                          `.pre-commit-config.yaml` has uncommitted changes
                          (working tree differs from HEAD, staged or not).
                          `git commit -- <pathspec>` builds a TEMPORARY index
                          from HEAD plus only the named paths; pre-commit then
                          diffs the working tree against THAT temp index, so a
                          dirty config is guaranteed to fail pre-commit's own
                          config-staleness check regardless of whether it was
                          ever `git add`-ed. Ordered BEFORE gate 4 specifically
                          so this entirely predictable, always-doomed failure
                          never takes a file_claims claim (or the per-repo
                          commit mutex) it would then have to leak — #4670
                          measured 8 burned commit attempts one night from
                          exactly this ordering. Scoped to pathspec commits
                          only (see _declared_pathspec) — a pathspec-less
                          commit stages/commits the real index via pre-commit's
                          own stash cycle instead, which is a DIFFERENT,
                          unrelated hazard (see #4091, not fixed by this
                          gate). EXEMPT (BLOCKER 1 fix, Opus review 2026-08-30)
                          when the commit's OWN pathspec already names the
                          config (normalized via prg.normalize_paths, same as
                          gate 3b — a bare string compare misses `./`-prefixed
                          and absolute spellings): that commit's temp index
                          carries the config's fresh content, so pre-commit
                          would actually succeed. WHEN NOT EXEMPT, recovery is
                          a THREE-step chain (round-3 correction — a bare
                          config-only commit is ITSELF denied by gate 3b, since
                          a dirty config's own diff by definition has no
                          recorded review yet): (1) review the config diff and
                          record it — `record_review.py <repo> --pre-commit
                          --clean --paths .pre-commit-config.yaml`; (2) `git
                          commit -m "chore: sync pre-commit config" --
                          .pre-commit-config.yaml`; (3) retry the original
                          commit. Without this chain there is NO sanctioned
                          recovery at all: restore/checkout is gate-1-blocked,
                          add+pathspec-less-commit still needs gate 3's
                          pathspec, gate 3b denies a bare config-only commit
                          for want of a review, and this gate has no escape
                          hatch (git_state=False). Logs under its own
                          `dirty_precommit_config` hook label, not this
                          dispatcher's — matching every sibling gate's
                          convention. Fails OPEN on any error (unresolved
                          repo, `git diff` failure/timeout, no HEAD yet); a
                          non-default pre-commit config path (`pre-commit -c
                          other.yaml`) gets no protection from this gate either
                          — also a fail-open, not a gap this gate claims to
                          cover; see _precommit_config_dirty's own docstring
                          for three further documented-not-fixed fail-open
                          gaps (glob pathspec, symlink spelling, compound-
                          segment granularity). Per-gate rollback lever:
                          CSA_NO_DIRTY_CONFIG_GATE=1.
  4. file_claims        — checks the commit's target paths against every OTHER
                          live agent's claim (~/.claude/.file_claims/); overlap
                          means another agent's in-flight work is contested.
                          ALSO claims a synthetic per-repo commit-mutex token
                          (file_claims.mutex_token) alongside the real paths
                          whenever a real repo toplevel resolved and the mutex
                          is enabled (CSA_NO_COMMIT_MUTEX unset) — this is what
                          makes "only one commit in flight per repo at a time"
                          mechanical, on top of the pre-existing path-overlap
                          contest. LOG-ONLY mode does one non-blocking
                          check-and-claim (never delays a commit); enforcing()
                          mode polls (bounded, jittered) before blocking. See
                          file_claims.py's module docstring for why this design
                          cannot deadlock (only bounded livelock, which the
                          bound terminates) and for the commit-mutex's own
                          documented bounds (TTL self-heal, long-command race).
  5. gh_issue_close_gate — ORTHOGONAL to gates 1-4/3b/6 (those are all `git commit`-
                          shaped triggers; this one fires ONLY for a `gh issue
                          close ...` command, so it can never collide with them
                          on the same segment). Refuses a fabricated-resolution
                          close (no real commit cited, or a cited commit that
                          doesn't exist) and, when the close's own text makes a
                          deploy-status claim ("deployed to prod" / "on
                          staging"), additionally refuses one whose cited
                          commit hasn't actually reached that claim's target
                          ref. Reuses gh_issue_close_gate.decide() verbatim —
                          see that module's own docstring for the full spec.
  5b. protected_board_guard — NEW 2026-09-14 (operator directive, GH #5490).
                          ORTHOGONAL to every other gate (fires on a `gh
                          project item-add|item-create`, a `gh api graphql`
                          add-item/draft-issue mutation, a `gh issue|pr
                          create/edit --project|--add-project`, or a
                          `gh_issue.sh --project` invocation — never a `git
                          commit` or a `gh issue close`). Denies an attempt
                          to ADD an item to a board listed in
                          `knowledge/protected_boards.json` — the customer
                          support-ticket board is the first entry, since only
                          the SaaS support-ticket mirror may write there, no
                          agent ever. Reads/edits of an EXISTING item on a
                          protected board (`item-edit`, field updates) are
                          NOT blocked — only item CREATION. Fails OPEN when
                          the registry is missing/unparseable/empty. See
                          protected_board_guard.py's own docstring for the
                          full per-shape spec.
  6. churn_tracker      — PURE OBSERVER, reached only when gates 1-5/5b did NOT
                          block: records this commit's target paths + current
                          HEAD (~/.claude/.churn/) and, when a path crosses the
                          configured commits-without-a-clean-review threshold
                          within the configured window, LOGS a "churn-flagged"
                          decision. NEVER returns a _Block and has NO
                          enforcing()-gated hard-block path at all (v1) — it
                          cannot affect this or any other gate's outcome.

  issue_create_observer — PURE OBSERVER (#5827, master plan
                          WS1 Phase D — observer-first), called UNCONDITIONALLY
                          and FIRST in resolve_block(), independent of every
                          numbered gate above: has no block-shaped return value
                          at all, so ordering relative to "first block wins"
                          is immaterial to its own outcome. For a `gh issue
                          create ...` that bypassed this runtime's own
                          `gh_issue.sh` helper, logs "bare-issue-create"; for a
                          `gh_issue.sh create ...` missing `--priority` or a
                          type/area:/difficulty: label class, logs
                          "create-missing-triage-would-deny". Imported
                          DEFENSIVELY (`try/except` -> `ico = None` on any
                          import failure) so a missing/broken observer module
                          can never fail this WHOLE dispatcher open — see
                          _issue_create_observe's own docstring.

POLICY (identical to the three modules it replaces — all delegated to their code):
  * CSA_DISABLE_HOOKS=1  master OFF — no-op allow before anything else.
  * LOG-ONLY by default: a would-block is logged (and allowed) unless _lib.enforcing()
    resolves ON, at which point the canonical PreToolUse deny is EMITTED.
  * A deny is ALWAYS via the JSON object, NEVER via a nonzero exit code (exit 0 always).
  * Escape hatch: CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env lets a
    git-state block (gate 1 / gate 1b / gate 1c / gate 2) through — but the INLINE
    tripwire (a command STRING that itself contains the var) is never escapable.
    This escape/tripwire behavior is delegated to each gate's own module (each
    decision() flags the tripwire independently; block_branch_ops.ESCAPE_VAR /
    block_head_overwrite's own reuse / block_gcloud_identity.ESCAPE_VAR all name
    the identical literal, so an operator never needs to remember more than one
    var). The check_staged_scope gate has no escape hatch, exactly as before.
  * Parse-ambiguity fails CLOSED via block_branch_ops (an untokenizable git segment)
    and block_gcloud_identity (an untokenizable gcloud segment), or a malformed
    JSON payload that mentions a git or gcloud token.

Per-gate rollback levers (each disables ONLY its own gate, never the others — the
module's standing pattern, one per gate that can independently wedge a commit):
  * gate 3  — CSA_NO_REQUIRE_PATHSPEC=1  (check_staged_scope.py)
  * gate 3b — CSA_NO_PRECOMMIT_REVIEW=1  (precommit_review_gate.py)
  * gate 3c — CSA_NO_DIRTY_CONFIG_GATE=1 (this module — see
    _dirty_precommit_config_block)
  * gate 4  — CSA_NO_COMMIT_MUTEX=1      (file_claims.py; real path-scoped
    claims are unaffected, only the per-repo commit-mutex is disabled)

Never raises out to the caller: a crashing dispatcher must never break the agent, so
every unexpected error degrades to ALLOW (exit 0, no deny).
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirroring the other hooks)
import block_branch_ops as bbo  # noqa: E402
import block_gcloud_identity as bgi  # noqa: E402
import block_head_overwrite as bho  # noqa: E402
import block_unscoped_commit as buc  # noqa: E402
import check_staged_scope as css  # noqa: E402
import churn_tracker as ct  # noqa: E402
import file_claims as fc  # noqa: E402
import gh_issue_close_gate as gicg  # noqa: E402
import precommit_review_gate as prg  # noqa: E402
import protected_board_guard as pbg  # noqa: E402

# issue_create_observer is imported DEFENSIVELY (fix-round 1, finding 4):
# every OTHER import above is UNGUARDED, which is a pre-existing class this
# module already accepts (a missing/broken sibling module crashes this
# dispatcher's own top-level `import` before main() ever runs, and Python
# itself then reports an ImportError that the harness treats as a hook
# CRASH — under the harness's own fail-open convention for a crashing hook,
# that means EVERY gate in this whole dispatcher silently fails open, not
# just the one broken import). That pre-existing exposure is not widened
# here — this is a NEW import this fix-round adds, so it gets its own
# guard rather than trusting the pattern is safe merely because five other
# modules already use it unguarded. `ico` is None when the module is
# missing or itself raises on import; `_issue_create_observe` checks for
# that and no-ops rather than ever touching a None `ico`.
try:
    import issue_create_observer as ico  # noqa: E402
except Exception:
    ico = None

HOOK_NAME = "pretooluse_bash"

# The escape var an agent must never smuggle inline — reused from block_branch_ops
# so the tripwire literal is defined in exactly one place.
_ESCAPE_VAR = bbo.ESCAPE_VAR


class _Block:
    """A resolved block from one gate: which hook, the audit reason, the operator
    message to emit under enforcement, and whether the escape hatch may rescue it.

    `git_state` is True for gate 1/gate 2 (git state-mutations, escapable via the
    OWN-env CSA_ALLOW_GIT_STATE_OPS) and False for gate 3 (index-scope, never
    escapable — matching check_staged_scope's original behavior).
    """

    __slots__ = ("hook", "reason", "message", "git_state")

    def __init__(self, hook: str, reason: str, message: str, *, git_state: bool):
        self.hook = hook
        self.reason = reason
        self.message = message
        self.git_state = git_state


def _branch_ops_block(command: str) -> _Block | None:
    """Gate 1: run block_branch_ops' PURE decision(); return a _Block or None."""
    block, reason = bbo.decision(command)
    if not block:
        return None
    message = (
        "block_branch_ops: blocked git state-mutation ("
        + reason
        + "). This op is reserved for the operator. "
        "See ~/.claude/.enforcement/log.jsonl."
    )
    if reason == "untokenizable-segment-with-git":
        # AA-0051 remediation (#4670 item 3, 2026-08-30): this reason
        # means a git-mentioning segment could not be tokenized unambiguously
        # at all -- unlike every other reason here, it is NOT a forbidden
        # state-verb, so the generic "reserved for the operator" text above
        # is actively misleading for this one case. Give the agent an actual
        # next step instead of leaving it to re-issue the identical broken
        # text and get denied again. Scoped to ONLY this reason -- every
        # other blocked reason (state-verb-forbidden, inline-escape-var-
        # forbidden, ...) must NOT gain this line, or it becomes noise on
        # the ~3,700 other denials/30d that have nothing to do with parsing.
        message += (
            " REMEDIATION: this is a shell-tokenization failure, not a "
            "forbidden git command -- the segment could not be split into "
            "arguments cleanly (commonly an unmatched quote or a trailing "
            "backslash line-continuation). Rewrite the git command as a "
            "single line with balanced quotes and retry; resubmitting the "
            "exact same unparseable text will deny again every time."
        )
    return _Block(
        bbo.HOOK_NAME,
        reason,
        message,
        git_state=True,
    )


def _head_overwrite_block(ev: dict) -> _Block | None:
    """Gate 1b: run block_head_overwrite's PURE decide(); return a _Block or
    None. Escapable via the SAME CSA_ALLOW_GIT_STATE_OPS var as gate 1 (this
    is the same class of operator-only git-safety override), so git_state
    is True here too — see block_head_overwrite.py's module docstring."""
    decision = bho.decide(ev)
    if not decision.block:
        return None
    message = (
        "block_head_overwrite: blocked a git show/cat-file read of a path "
        "redirected back onto that SAME path (" + decision.reason + "). This "
        "overwrites the working tree with historical content and "
        "PERMANENTLY DESTROYS any uncommitted/unstaged changes at that path "
        "with no git-recoverable trace (see GH #4387). If you need to "
        "inspect an old version, redirect to a DIFFERENT path (e.g. "
        "`git show HEAD:path/to/file > /tmp/file.bak`) or use `git diff -- "
        "<path>` to compare without overwriting anything. "
        "See ~/.claude/.enforcement/log.jsonl."
    )
    return _Block(
        bho.HOOK_NAME,
        decision.reason,
        message,
        git_state=True,
    )


def _gcloud_identity_block(command: str) -> _Block | None:
    """Gate 1c: run block_gcloud_identity's PURE decision(); return a _Block or
    None. Escapable via the SAME CSA_ALLOW_GIT_STATE_OPS var as gates 1/1b/2
    (block_gcloud_identity.ESCAPE_VAR is that identical name, reused rather
    than a new one — see its module docstring: this is the same class of
    operator-only machine-state-mutation override), so git_state is True here
    too. Reuses block_gcloud_identity._message_for verbatim for the deny text
    so the message an agent actually sees can never drift from what that
    module's own tests assert against.

    `command` MUST be passed through to `_message_for` as its second
    positional argument (#5890 round 3, round-3-review
    BLOCKER): `_message_for`'s `describe-unmasked-format` /
    `list-unmasked-format` / `describe-multiple-format` /
    `list-multiple-format` / `describe-flags-file` / `list-flags-file`
    branches re-derive the matched resource FAMILY via
    `_family_for_command(command)` to build a per-family safe --format hint
    (round 2, B6) -- called with no `command` (the bare `_message_for(reason)`
    shape this line used to have), `_family_for_command` always returns
    `None` and every one of those six branches silently falls back to the
    `scheduler-job` example (`table(name,schedule,state)`), which is wrong
    advice for the other 6 of 7 covered families and gets an agent that
    follows it denied AGAIN on retry. This is the ONLY caller in the
    codebase reached by every live enforcing gate-1c dispatch (`decision()`
    called from this module's own `resolve_block` function); a test that
    only calls `guard._message_for(reason, deny_command)` directly, as this
    module's own docstring construction does, never exercises this real
    call site and would not have caught the bug."""
    block, reason = bgi.decision(command)
    if not block:
        return None
    return _Block(
        bgi.HOOK_NAME,
        reason,
        bgi._message_for(reason, command),
        git_state=True,
    )


def _unscoped_commit_block(ev: dict) -> _Block | None:
    """Gate 2: run block_unscoped_commit's PURE decide(); return a _Block or None."""
    decision = buc.decide(ev)
    if not decision.block:
        return None
    return _Block(
        buc.HOOK_NAME,
        decision.reason,
        f"{buc.HOOK_NAME}: blocked bulk/unscoped git staging "
        f"({decision.reason}). Stage explicit paths (git add path/to/file) and "
        'commit with: git commit -m "..." -- <path> [<path>...]; -A/--all/-u/. '
        "and commit -a are reserved for the operator. "
        "See ~/.claude/.enforcement/log.jsonl.",
        git_state=True,
    )


def _staged_scope_block(
    ev: dict, where: str, staged: list | None = None, repo_root: str | None = None
) -> tuple[_Block | None, dict]:
    """Gate 3: check_staged_scope. Reads the real index (impure) ONLY when the
    event is a writing `git commit`, then runs its PURE decision_for_event().

    `staged` lets a caller (resolve_block) pass an ALREADY-read index so this
    gate doesn't re-run `git diff --cached` when gate 4/6 need the same data
    for the same event (NIT 25) — None (every direct/unit-test call site)
    falls back to reading it here itself, unchanged from before. `repo_root`
    is threaded the same way so decision_for_event's own lazy repo-root
    resolution (needed only for an absolute-path bulk-pathspec check) never
    re-derives it when resolve_block already has it.

    Uses check_staged_scope.deny_message() for the operator-facing text so
    this gate's messages (missing-pathspec / bulk-pathspec / scope-sweep) stay
    reason-aware and identical to what check_staged_scope.py's own main()
    would emit for the same Decision, regardless of which entry point fires.

    Returns (_Block | None, detail) — the detail dict is folded into the log record
    exactly as check_staged_scope.main() does.
    """
    if not css.should_guard(ev):
        return None, {}
    if staged is None:
        staged = css.read_staged_paths(where)
    decision = css.decision_for_event(ev, staged, repo_root)
    if decision.action != "BLOCK":
        return None, {}
    block = _Block(css.HOOK_NAME, decision.reason, css.deny_message(decision), git_state=False)
    return block, dict(decision.detail)


def _claim_agent_id(ev: dict) -> str:
    """Claim key for this commit attempt: its tool_use_id, or a minted unique id.

    Mirrors agent_budget._gate_agent_id exactly, for the same reason: tool_use_id
    correlates the PreToolUse claim with the PostToolUse release for THIS exact
    commit call, and two concurrent commits with no tool_use_id must never
    collapse onto one claim. A minted id has no correlated release — it only
    TTL-reaps — matching agent_budget's documented tradeoff.
    """
    tid = _lib.tool_use_id(ev)
    if tid:
        return tid
    import uuid

    return "auto-" + uuid.uuid4().hex


# Shortest unambiguous prefix of `--include` among git-commit's own long
# options: the only other `--in*` options are `--interactive` and
# `--inter-hunk-context`, both of which diverge at the 5th character ('t' vs
# 'c'), so "--inc" is already unambiguous and git accepts it (and every
# longer prefix up to the full spelling) as `--include`.
_INCLUDE_ABBREV_FLOOR = "--inc"


def _matches_include_flag(tok: str) -> bool:
    """True iff `tok` is `--include` or a git-accepted abbreviated spelling.

    git accepts any unambiguous prefix of a long option — `--incl`/`--inclu`/
    `--includ` are real, git-honored spellings that widen a commit to the
    whole staged index exactly like the full `--include`. Matching only the
    exact string missed these: `git commit --incl -m x -- reviewed.py` landed
    the rest of the staged index unreviewed by gate 3b and unclaimed by gate
    4. Matching down to the shortest floor that stays unambiguous (rather
    than requiring the full spelling) is deliberate: under-matching here is
    the LEAK direction, so this errs toward recognizing MORE spellings, never
    fewer. `"--include".startswith(tok)` additionally rules out a token
    LONGER than `--include` (a typo/unrelated flag) from ever matching.
    """
    return tok.startswith(_INCLUDE_ABBREV_FLOOR) and "--include".startswith(tok)


def _segment_includes_index(seg: dict) -> bool:
    """True iff this commit segment also commits the whole staged index.

    Matches the long `--include` (and its unambiguous abbreviations — see
    _matches_include_flag) AND the short `-i` in any BUNDLED form, because
    git accepts them: `-im "msg"` is `-i -m "msg"`. Testing `"-i" in argv`
    alone missed `-im`, which let
    `git add secret.py && git commit -im "x" -- reviewed.py`
    land secret.py unreviewed by gate 3b and unclaimed by gate 4. Reuses
    block_unscoped_commit's existing bundled-short-flag splitter rather than
    growing a second, subtly different one.
    """
    for tok in seg.get("argv") or []:
        if _matches_include_flag(tok):
            return True
        letters = buc._short_flags(tok)
        if letters and "i" in letters:
            return True
    return False


def _review_target_paths(
    ev: dict, command: str, where: str, staged: list | None, repo_root: str | None
) -> list:
    """Gate 3b's target paths, ALL in one coordinate system: repo-root-relative.

    `_commit_target_paths` deliberately returns a MIXTURE — pathspec tokens
    exactly as typed (cwd-relative) unioned with staged-index paths (already
    repo-root-relative). Gate 4 normalizes that itself. Handing the mixture to
    `precommit_review_gate.normalize_paths`, which assumes every token is
    cwd-relative, re-based the staged half onto the subdirectory: from
    `repo/pkg` a staged `pkg/secret.py` became `pkg/pkg/secret.py`, matched
    nothing, produced an empty diff and SILENTLY ALLOWED. Each half is
    resolved in its own frame here instead of letting one guess.
    """
    if not repo_root:
        return _commit_target_paths(ev, command, where, staged)

    segments = css.writing_commit_segments(command)
    pathspec_tokens: list[str] = []
    want_index = False
    for seg in segments:
        tokens = [p for p in seg.get("pathspec") or [] if p and not p.startswith(("<", ">"))]
        if not tokens or _segment_includes_index(seg):
            want_index = True
        pathspec_tokens.extend(tokens)
    if not segments:
        want_index = True

    out = set(prg.normalize_paths(repo_root, where, pathspec_tokens)) if pathspec_tokens else set()
    if want_index:
        # Already repo-root-relative: git reports the index that way.
        index = staged if staged is not None else css.read_staged_paths(where)
        out |= {p for p in (index or []) if p}
    return sorted(out)


def _commit_target_paths(ev: dict, command: str, where: str, staged: list | None = None) -> list:
    """The paths this commit would touch: explicit pathspec, else the full
    staged index — the SAME duality check_staged_scope's gate 3 already uses,
    so "the commit's scope" means one consistent thing across both gates.

    `staged` lets a caller pass an ALREADY-read index (from gate 3's own read)
    so the fallback branch doesn't re-run `git diff --cached` for the same
    event (NIT 25) — None (every direct/unit-test call site) falls back to
    reading it here itself, unchanged from before.

    Filters out shell-redirect leakage (`<file`, `>file`, `<<EOF`, `<<'EOF'`):
    _lib.git_segments' tokenizer has no concept of shell redirection, so a
    heredoc-body commit (`git commit -F - -- <paths> <<'EOF' ... EOF`) shlex-
    splits its own `<<'EOF'` into the pathspec as a literal token. Harmless for
    gate 3 (any non-empty pathspec already ALLOWs there, regardless of
    content) but would poison gate 4's claimed path set — self-observed: a
    heredoc commit claimed a bogus "<<EOF" path that then spuriously
    contested a same-session retry. This filter is intentionally local to
    gate 4's own path-resolution rather than a fix to the shared tokenizer
    (check_staged_scope.py's tests already cover the tokenizer's existing
    contract; narrowing this cheaply here avoids touching that).

    Consistent with check_staged_scope's per-segment view (writing_commit_
    segments): a compound command can carry MULTIPLE writing commit segments,
    each with its own (possibly absent) pathspec. This returns the UNION of
    every segment's pathspec; if ANY writing segment has no pathspec at all,
    that segment's real target set is the whole staged index (gate 3 will
    itself judge/block that segment on the missing-pathspec ground — this
    function just needs to claim a target set that is at least as wide as
    what could actually be touched, so a claim never under-covers).
    """
    segments = css.writing_commit_segments(command)
    if segments:
        union: list[str] = []
        seen: set[str] = set()
        any_missing = False
        for seg in segments:
            pathspec = [p for p in seg.get("pathspec") or [] if p and not p.startswith(("<", ">"))]
            # `-i` / `--include` commits the ENTIRE staged index IN ADDITION to
            # the named pathspec. Reading only the pathspec would let
            # `git add secret.py && git commit -i -m "..." -- reviewed.py`
            # land secret.py unreviewed and unclaimed. Same "never under-claim"
            # rule already applied to a missing pathspec: widen to the index.
            if _segment_includes_index(seg):
                any_missing = True
            if not pathspec:
                any_missing = True
                continue
            for p in pathspec:
                if p not in seen:
                    seen.add(p)
                    union.append(p)
        if not any_missing and union:
            return union
        # At least one segment has no pathspec -> fall back to the staged
        # index (widest possible target set) rather than under-claim.
        if staged is not None:
            return sorted(set(staged) | seen)
        return sorted(set(css.read_staged_paths(where)) | seen)
    if staged is not None:
        return staged
    return css.read_staged_paths(where)


def _declared_pathspec(command: str) -> tuple[list, bool]:
    """The union of every writing commit segment's EXPLICIT pathspec in
    `command`, and whether a real (non-widened) pathspec was actually
    declared — i.e. the same non-fallback branch `_commit_target_paths`
    computes, WITHOUT that function's own "no segments / missing pathspec ->
    fall back to the staged index" default.

    Used only by `_churn_observe`'s defensive net (B1, 08-25 round 3): "never
    record a path that is not in the commit's own pathspec when a pathspec
    exists" needs to know the commit's OWN declared pathspec independently of
    whatever `_commit_target_paths` happened to resolve, so a caller can
    enforce that invariant rather than merely hope `_commit_target_paths`
    got it right. `has_pathspec` is False for a genuinely pathspec-less
    commit, a `--include`/`-i` segment (widens to the whole index by
    design — that is judged/BLOCKed by gate 3, not silently narrowed here),
    or a command with no writing commit segment at all.
    """
    segments = css.writing_commit_segments(command)
    union: list = []
    seen: set = set()
    any_missing = False
    for seg in segments:
        pathspec = [p for p in seg.get("pathspec") or [] if p and not p.startswith(("<", ">"))]
        if _segment_includes_index(seg):
            any_missing = True
        if not pathspec:
            any_missing = True
            continue
        for p in pathspec:
            if p not in seen:
                seen.add(p)
                union.append(p)
    has_pathspec = bool(segments) and not any_missing and bool(union)
    return union, has_pathspec


def _file_claim_block(
    ev: dict,
    command: str,
    where: str,
    targets: list | None = None,
    repo_root: str | None = None,
) -> tuple[_Block | None, dict]:
    """Gate 4: file_claims. Checks/claims this commit's target paths against
    every OTHER agent's live claim. See file_claims.py's module docstring for
    the full deadlock analysis; summary: claiming is atomic and all-or-nothing
    (never partial), which is what rules out real deadlock.

    `targets` lets a caller pass ALREADY-resolved target paths (NIT 25) —
    None (every direct/unit-test call site) falls back to resolving them here
    itself via `_commit_target_paths`, unchanged from before.

    `repo_root` (also None-default, for the same reason): when the caller
    already resolved a REAL repo toplevel (not the churn-only `or where`
    fallback — see resolve_block) and file_claims.mutex_enabled() is True,
    the commit ALSO claims that repo's synthetic commit-mutex token (see
    file_claims.mutex_token) alongside its real target paths, so every commit
    in the same repo contests every OTHER concurrent commit regardless of
    real path overlap — "only one commit in flight per repo at a time". A
    None/unresolved repo_root, or mutex_enabled() False (CSA_NO_COMMIT_MUTEX=1),
    claims real paths only, unchanged from before this feature existed.

    LOG-ONLY (not enforcing()): ONE non-blocking check-and-claim — never delays
    a commit, but still writes the claim so concurrent commits (including an
    enforcing() one elsewhere) see accurate contest state. A contest here is
    logged, not blocked.

    enforcing(): a bounded, jittered poll (file_claims.poll_claim_paths) before
    blocking. No escape hatch (git_state=False) — bypassing this specific
    protection would defeat the point of it, same choice check_staged_scope
    already made for its own gate.

    HONESTY FIX (#4670 item 2, 2026-08-30): when a deny actually fires,
    the message checks fc.pid_alive() on the blocking claim's recorded pid.
    A dead owner gets an honest "this is a LEAKED claim, not another agent's
    active work" message naming the exact standalone release command —
    never the misleading "another agent has uncommitted work" text, which
    is reserved for a genuinely live holder. See file_claims.py's
    "DEAD-PID SELF-HEAL" section for what pid actually gets checked here.

    REACHABILITY of the dead-pid message (Opus review round 2, 2026-08-30):
    under the REAL default ratio (CSA_DEAD_PID_TTL_SEC=15 <
    CSA_COMMIT_CLAIM_MAX_WAIT_SEC=45), file_claims.read_live_claims() itself
    already excludes a dead-owner record once its age crosses 15s — well
    inside this function's own 45s poll budget — so a retrying commit whose
    ONLY contest is that dead record simply CLAIMS THROUGH with no deny at
    all; this function's dead-pid message branch is never reached in that,
    the everyday, case (see file_claims.py's own test_file_claims.py::
    TestDeadPidSelfHeal::test_default_ratio_dead_owner_claim_self_heals_
    mid_poll_and_claims_through, which proves exactly this with the real
    default values). The message branch is defense-in-depth: it is only
    ever REACHED when dead_pid_ttl >= max_wait for the poll actually run —
    an operator override (CSA_DEAD_PID_TTL_SEC raised, or
    CSA_COMMIT_CLAIM_MAX_WAIT_SEC lowered), never the shipped defaults.
    file_claims.py's own self-heal (see its "DEAD-PID SELF-HEAL" section) is
    what actually resolves the common case; this message exists so a
    misconfigured ratio still fails HONEST instead of silently reverting to
    the old, misleading text.
    """
    if not css.should_guard(ev):
        return None, {}
    if targets is None:
        targets = _commit_target_paths(ev, command, where)
    claim_targets = list(targets) if targets else []

    mutex_claimed = False
    if repo_root and fc.mutex_enabled():
        try:
            real_root = os.path.realpath(repo_root)
        except Exception:
            real_root = None
        if real_root and os.path.isdir(real_root):
            claim_targets.append(fc.mutex_token(real_root))
            mutex_claimed = True

    if not claim_targets:
        return None, {}

    agent_id = _claim_agent_id(ev)
    ttl = fc.ttl_from_env()
    lock_timeout = fc.lock_timeout_from_env()

    enforce = _lib.enforcing(where)
    if not enforce:
        claimed, contest = fc.try_claim_paths(_lib.FILE_CLAIMS_DIR, ttl, agent_id, claim_targets, lock_timeout)
        if not claimed:
            real_paths, mutex_repos = fc.split_mutex_paths(
                sorted({fc.normalize_path(p) for p in claim_targets})
            )
            _lib.log(
                fc.HOOK_NAME,
                "would-wait",
                contested_by=contest.get("agent_id") if contest else None,
                paths=real_paths,
                commit_mutex=mutex_repos,
                enforce=enforce,
            )
        return None, {}

    result = fc.poll_claim_paths(
        _lib.FILE_CLAIMS_DIR,
        ttl,
        agent_id,
        claim_targets,
        lock_timeout,
        fc.max_wait_from_env(),
        fc.poll_from_env(),
    )
    if result["claimed"]:
        return None, {}

    contest = result.get("contest") or {}
    holder = contest.get("agent_id", "unknown")
    holder_pid = contest.get("pid")
    # HONESTY FIX (#4670 item 2, 2026-08-30): a claim whose owning
    # process is confirmed dead is a LEAK, not another agent's live work —
    # see file_claims.pid_alive/_owner_pid for what "owning process" means
    # here (CLAUDE_PID, the session's own long-lived pid, not the one-shot
    # hook subprocess that wrote the claim). Say so plainly and name the
    # exact standalone release command (a compounded
    # `file_claims.py release <id> && git commit ...` never works — the
    # PreToolUse gate inspects the whole compound command up front and
    # denies before the release half ever runs — so the recovery MUST be a
    # separate call).
    holder_alive = fc.pid_alive(holder_pid)
    # shlex.quote (Opus review round 3, FINDING 9): `holder` is an
    # agent_id — normally a tool_use_id or a minted "auto-<uuid>", but
    # never validated to be shell-safe — interpolated straight into a
    # command an operator is expected to copy-paste and run. Quoting it
    # means a pathological/malformed agent_id can never break out of its
    # argument position (or worse) when pasted into a shell.
    release_cmd = f"python3 ~/.claude/hooks/file_claims.py release {shlex.quote(str(holder))}"
    contest_norm = set(contest.get("paths", []))
    target_norm = {fc.normalize_path(p) for p in claim_targets}
    overlap_all = sorted(contest_norm & target_norm)
    real_overlap = sorted(p for p in overlap_all if not fc.is_mutex_token(p))

    if mutex_claimed and not real_overlap:
        # The ONLY reason this commit is blocked is the per-repo commit
        # mutex, not a real path collision — say so plainly rather than
        # dumping the raw "//commit-mutex::..." token at the operator.
        if holder_alive:
            message = (
                "file_claims: blocked commit (commit-in-flight). Another agent's "
                f"commit is currently in flight in this repo (holder {holder}). "
                "Only one commit may be in flight per repo at a time. Wait and "
                "retry the exact same commit, or run "
                "'python3 ~/.claude/hooks/file_claims.py status' to see the "
                "holder. See ~/.claude/.enforcement/log.jsonl."
            )
        else:
            message = (
                "file_claims: blocked commit (commit-in-flight). This is a LEAKED "
                f"claim, not another agent's active work: its owner (holder {holder}"
                f", pid {holder_pid}) is no longer running. Run "
                f"'{release_cmd}' to clear it, then retry the exact same commit. "
                "See ~/.claude/.enforcement/log.jsonl."
            )
        block = _Block(fc.HOOK_NAME, "commit-in-flight", message, git_state=False)
        return block, {
            "contested_by": holder,
            "holder_pid": holder_pid,
            "holder_alive": holder_alive,
            "waited_sec": round(result["waited"], 1),
        }

    if holder_alive:
        message = (
            "file_claims: blocked commit (contested-paths). "
            f"Still overlapping agent {holder}'s in-flight claim on {real_overlap} after "
            f"{round(result['waited'], 1)}s of waiting. Another agent has uncommitted "
            "work on these exact paths right now. Do not force through — wait and "
            "retry, or run 'python3 ~/.claude/hooks/file_claims.py status' to see "
            "who holds it. See ~/.claude/.enforcement/log.jsonl."
        )
    else:
        message = (
            "file_claims: blocked commit (contested-paths). Still overlapping "
            f"agent {holder}'s claim on {real_overlap} after {round(result['waited'], 1)}s "
            f"of waiting — but this is a LEAKED claim, not another agent's active "
            f"work: its owner (holder {holder}, pid {holder_pid}) is no longer "
            f"running. Run '{release_cmd}' to clear it, then retry the exact same "
            "commit. See ~/.claude/.enforcement/log.jsonl."
        )
    block = _Block(fc.HOOK_NAME, "contested-paths", message, git_state=False)
    return block, {
        "contested_by": holder,
        "holder_pid": holder_pid,
        "holder_alive": holder_alive,
        "overlap_paths": real_overlap,
        "waited_sec": round(result["waited"], 1),
    }


def _gh_issue_close_block(ev: dict, command: str) -> tuple[_Block | None, dict]:
    """Gate 5: gh_issue_close_gate. Runs gh_issue_close_gate's own PURE
    decide() verbatim (no re-derived regex/git logic here — this is a wiring
    fix, not a reimplementation) and translates a block into a _Block.

    Orthogonal to every other gate: a `git commit` (gates 1-4/6's territory)
    can never trip this gate, and a `gh issue close` can never trip the
    git-commit-shaped gates. Pre-checks `gicg.is_issue_close(command)` (the
    SAME cheap classification every other gate uses to skip real work for an
    event it doesn't own — mirrors `css.should_guard(ev)` in gates 3/4/6) so
    decide() (which shells to git once a close is confirmed) is never even
    invoked for the vast majority of Bash commands that aren't a close at
    all.
    """
    if not gicg.is_issue_close(command):
        return None, {}
    block, reason, detail = gicg.decide(ev)
    if not block:
        return None, {}
    # gicg.decide()'s own detail carries a "command" key; _finish() already
    # logs its OWN truncated `command=` kwarg for every gate uniformly, so
    # drop the duplicate here rather than collide (TypeError: multiple values
    # for keyword argument 'command').
    detail = {k: v for k, v in detail.items() if k != "command"}
    return (
        _Block(
            gicg.HOOK_NAME,
            reason,
            f"{gicg.HOOK_NAME}: {reason} See ~/.claude/.enforcement/log.jsonl.",
            git_state=False,
        ),
        detail,
    )


def _issue_create_observe(command: str, where: str) -> None:
    """Issue-creation quality observer (#5827, master plan
    WS1 Phase D — observer-first). A PURE OBSERVER, exactly like gate 6's
    `_churn_observe`: it can NEVER return a block (issue_create_observer.py
    has no block-shaped return value at all) and never raises out of this
    call — any internal failure is swallowed inside `issue_create_observer.
    observe()`/`main()` itself, matching every other observer's contract.

    Orthogonal to every OTHER gate here, the same way gates 5/5b are: a
    `gh issue create` or `gh_issue.sh create` command can never also be a
    `git commit` or a `gh issue close`/`gh project item-add`, so this never
    collides with any blocking gate on the same segment — it is therefore
    called unconditionally (not gated behind `css.should_guard`, which only
    ever recognizes a writing `git commit`), independent of whether any
    other gate already decided to block this same command.

    `ico` is None (fix-round 1, finding 4) when the top-level `try/except`
    import guard caught the module being missing or itself raising on
    import — a no-op in that case, so a broken/absent observer module can
    never crash this call and, transitively, can never fail this whole
    dispatcher open the way an UNGUARDED top-level import crash would (see
    the import site's own comment).
    """
    if ico is None:
        return
    try:
        enforce = _lib.enforcing(where)
        for decision, detail in ico.observe(command):
            _lib.log(ico.HOOK_NAME, decision, enforce=enforce, **detail)
    except Exception:
        return


def _protected_board_block(command: str) -> _Block | None:
    """Gate 5b: protected_board_guard. Runs its own PURE decide() (no
    re-derived registry/regex logic here) and translates a block into a
    _Block.

    Orthogonal to every other gate here, same reasoning as gate 5: none of
    `gh project item-add`, `gh api graphql`, `gh issue|pr create/edit
    --project`, or a `gh_issue.sh --project` invocation is a `git commit` or
    a `gh issue close`, so this can never collide with gates 1-5/6 on the
    same segment. Takes no cwd/repo — the registry is a single machine-wide
    file, not per-repo state, so the decision and the deny message's registry
    lookup both need nothing beyond `command`. The registry is loaded ONCE
    here and threaded into both `decide()` and `message_for()` so a would-
    block never re-reads the registry file a second time on every deny.
    """
    boards = pbg.load_registry()
    block, reason = pbg.decide(command, boards)
    if not block:
        return None
    return _Block(
        pbg.HOOK_NAME,
        reason,
        pbg.message_for(reason, boards),
        git_state=False,
    )


def _precommit_review_block(
    ev: dict,
    command: str,
    where: str,
    staged: list | None,
    repo_root: str | None,
) -> tuple[_Block | None, dict]:
    """Gate 3b: precommit_review_gate. Review BEFORE the commit, not after.

    Deliberately ordered AFTER gate 3 (staged scope) and BEFORE gate 4 (file
    claims): a commit denied for want of a review must not first take the
    per-repo commit mutex, or an unreviewed commit would park the mutex and
    stall every other agent's commit until the claim's TTL expired.

    Runs its own PURE decide() and translates a block into a _Block; all the
    fail-open behavior lives in that module, not here.
    """
    if not css.should_guard(ev):
        return None, {}
    # Its OWN target resolution, all repo-root-relative (see _review_target_paths),
    # then cwd == repo_root so normalization is idempotent rather than a guess.
    review_targets = _review_target_paths(ev, command, where, staged, repo_root)
    block, reason, detail = prg.decide(
        repo_root, repo_root or where, review_targets, command=command
    )
    if not block:
        return None, {}
    targets = review_targets
    return (
        _Block(
            prg.HOOK_NAME,
            reason,
            prg.message_for(reason, detail, list(targets or []), repo_root),
            git_state=False,
        ),
        detail,
    )


# The one file this gate cares about — see _precommit_config_dirty.
_PRECOMMIT_CONFIG_NAME = ".pre-commit-config.yaml"

# Distinct hook label for this gate's own _Block/log records (Opus review
# round 3, FINDING 3, 2026-08-30). Every OTHER gate in this dispatcher logs
# under its OWN module's HOOK_NAME (fc.HOOK_NAME == "file_claims",
# css.HOOK_NAME == "check_staged_scope", prg.HOOK_NAME ==
# "precommit_review_gate", ...) even though they're all invoked from this
# one dispatcher process — this gate lives INSIDE pretooluse_bash.py itself
# (no separate module), so an earlier version passed the dispatcher's OWN
# HOOK_NAME ("pretooluse_bash") by default, which made this gate's
# would-block/deny records indistinguishable in the ledger from a raw
# dispatcher-level error and broke the sibling convention every downstream
# consumer (churn_report.py's `_GATE_HOOKS` allowlist, an operator grepping
# `~/.claude/.enforcement/log.jsonl`) already relies on: one hook name per
# gate.
DIRTY_CONFIG_HOOK_NAME = "dirty_precommit_config"


def _precommit_config_dirty(repo_root: str) -> bool:
    """True iff `.pre-commit-config.yaml`'s WORKING-TREE content differs from
    HEAD's committed content in `repo_root` — staged or not (#4670 item 3).

    A pathspec commit (`git commit -- <paths>`) builds a TEMPORARY index from
    HEAD plus only the named paths; pre-commit then diffs the working tree
    against THAT temp index, not the real one. Since the temp index always
    carries HEAD's copy of the config (unless the config itself is IN the
    commit's own pathspec), a merely-STAGED-but-uncommitted config edit still
    reads as "unstaged" there and fails pre-commit's own config-staleness
    check — so "dirty" here means differs from HEAD, regardless of index
    state. Verified empirically 2026-08-30: `git add
    .pre-commit-config.yaml` followed by a pathspec commit of an unrelated
    file still trips pre-commit's "Your pre-commit configuration is
    unstaged" error.

    `git diff --quiet HEAD -- <path>` is exit 0 when identical, 1 when it
    differs, and >1 on a real error (e.g. `bad revision 'HEAD'` — no commits
    yet) — anything but exactly 1 is treated as "not dirty" (fail open,
    matching every other gate here). Bounded (15s) and hermetic (no system
    config, no terminal prompt), mirroring every other `git` subprocess call
    in this dispatcher (see posttooluse_bash.py._git).

    DOCUMENTED, NOT FIXED — four narrower gaps (Opus review round 3, FINDING
    10, 2026-08-30), every one of which fails in the SAME safe direction: a
    false "not exempt"/still-denied outcome (annoying, forces the 3-step
    recovery chain below unnecessarily) or a missed deny this gate never
    claimed to guarantee catching — never a false ALLOW that would let a
    genuinely doomed commit through and leak a claim, which is the one
    direction this gate actually exists to prevent:
      1. GLOB PATHSPEC: `_pathspec_includes_precommit_config` compares
         LITERAL, normalized path strings — a glob token (e.g. `-- '.pre-
         commit-config.y*'`) that git itself would expand to match the
         config is never recognized as "the config is named here", so the
         exemption doesn't fire even though a real `git commit` with that
         glob would succeed. Fails toward an unnecessary deny, not a wedge
         (CSA_NO_DIRTY_CONFIG_GATE remains the escape).
      2. SYMLINK SPELLING: normalize_paths() deliberately realpaths only the
         DIRECTORY component of a token, never the leaf (so a symlinked FILE
         normalizes to the link's own name, not its target — see that
         function's own docstring). If `.pre-commit-config.yaml` itself were
         a symlink and a commit named it via its TARGET's own filename
         instead, the literal-string comparison would not recognize it as
         the config either. Same fail direction as #1.
      3. COMPOUND-SEGMENT GRANULARITY: `_declared_pathspec` unions every
         writing commit segment in a compound command into ONE has_pathspec/
         pathspec-set pair; if ANY segment in that compound command is
         pathspec-less or carries `--include`/`-i`, the WHOLE command's
         has_pathspec flips false (see `_declared_pathspec`'s own
         any_missing logic), so `_dirty_precommit_config_block`'s own
         `if not _declared_pathspec(command)[1]: return None` short-circuits
         this gate off for the ENTIRE command — including a later segment
         that DOES name the config — regardless of segment order. This gate
         simply does not engage per-segment; disaggregating it to segment
         granularity is a gate-logic change, out of this round's scope.
      4. NO PRE-COMMIT-INSTALLED CHECK: this gate assumes the repo actually
         runs `pre-commit` as part of `git commit` at all — it never checks
         for `.git/hooks/pre-commit` or that the `pre-commit` binary is on
         PATH. A repo with no pre-commit wired up at all would still be
         denied here for a "dirty" config that could never actually break
         anything. Verifying pre-commit is actually installed/active is
         explicitly out of scope — every repo this gate protects (per this
         runtime's own convention) has it wired, and checking would add a
         second subprocess call for a low-value edge case.
    """
    try:
        env = dict(os.environ)
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["GIT_TERMINAL_PROMPT"] = "0"
        proc = subprocess.run(
            ["git", "-C", repo_root, "diff", "--quiet", "HEAD", "--", _PRECOMMIT_CONFIG_NAME],
            capture_output=True,
            timeout=15,
            env=env,
        )
    except Exception:
        return False
    return proc.returncode == 1


def _pathspec_includes_precommit_config(command: str, where: str, repo_root: str) -> bool:
    """True iff the commit's OWN declared pathspec resolves — after the SAME
    normalization gate 3b's own review-target resolution already applies
    (prg.normalize_paths) — to `.pre-commit-config.yaml` itself.

    BLOCKER 1 fix (Opus review, 2026-08-30): when the config IS in the
    commit's own pathspec, the temp index a pathspec commit builds carries
    the config's CURRENT WORKING-TREE content for that path — same as any
    other named path (see _precommit_config_dirty's own docstring for the
    proof) — so pre-commit's own unstaged-config check reads NO difference
    there and the commit would actually SUCCEED. Denying it anyway is a
    false positive that measurably wedges the repo (35 config-touching
    commits in 60 days) with no sanctioned recovery: `git restore`/
    `checkout --` is gate-1-blocked, `git add` + a pathspec-less commit
    still needs an explicit pathspec under gate 3 (CSA_NO_REQUIRE_PATHSPEC
    is an operator rollback lever, not a normal recovery path), and gate 3c
    itself carries no escape hatch (git_state=False) — leaving only the
    global CSA_DISABLE_HOOKS kill-switch. A bare string compare against the
    literal pathspec token would miss `./.pre-commit-config.yaml` and an
    absolute-path spelling; normalize_paths (the exact function gate 3b
    already uses for this same reason) collapses every spelling to one
    repo-root-relative form before comparing. Covers the mixed case too
    (`-- .pre-commit-config.yaml a.py`) — the whole normalized set is
    checked, not just a single-token pathspec.

    See _precommit_config_dirty's own docstring for four narrower,
    DOCUMENTED-not-fixed gaps in this exemption (glob pathspec, symlink
    spelling, compound-segment granularity, no pre-commit-installed check) —
    every one fails toward "not exempt" (an unnecessary deny), never toward
    a false exemption.
    """
    pathspec, has_pathspec = _declared_pathspec(command)
    if not has_pathspec:
        return False
    normalized = prg.normalize_paths(repo_root, where, pathspec)
    return _PRECOMMIT_CONFIG_NAME in normalized


def _dirty_precommit_config_block(command: str, where: str, repo_root: str | None) -> _Block | None:
    """Gate 3c: dirty_precommit_config (#4670 item 3). See GATE ORDER's
    "3c." entry at the top of this module for the full rationale.

    Scoped to PATHSPEC commits only (`_declared_pathspec(command)[1]`) — a
    pathspec-less commit is judged/blocked by gate 3 already in the common
    case, and even under CSA_NO_REQUIRE_PATHSPEC=1 it commits the real
    staged index through pre-commit's own stash cycle rather than a temp
    index, which is the DIFFERENT hazard #4091 tracks, not this one.

    EXEMPT when the commit's own pathspec already names the config (see
    _pathspec_includes_precommit_config — BLOCKER 1 fix, 2026-08-30): that
    commit would actually succeed against a real pre-commit run, so denying
    it here would wedge the repo with no sanctioned recovery.

    WHEN NOT EXEMPT, the deny message's own recovery is a genuine THREE-STEP
    chain, not one commit (round-3 correction, BLOCKER 1 of the follow-up
    review: the original message told the operator to land the config in
    its own commit, but that commit is ITSELF denied by gate 3b —
    precommit_review_gate — since a dirty config's own diff has, by
    definition of why this gate just fired, no recorded review yet):
      1. review the config diff and record it —
         `python3 ~/.claude/hooks/record_review.py <repo> --pre-commit
         --clean --paths .pre-commit-config.yaml`
      2. `git commit -m "chore: sync pre-commit config" --
         .pre-commit-config.yaml`
      3. retry the original commit.
    Without this chain there is NO sanctioned recovery at all: `git
    restore`/`checkout --` is gate-1-blocked, `git add` + a pathspec-less
    commit still needs gate 3's explicit pathspec, gate 3b denies a bare
    config-only commit for want of a review, and this gate itself has no
    escape hatch (git_state=False) — see the GATE ORDER "3c." entry at the
    top of this module for the same enumeration.

    No repo_root (non-repo cwd, unresolved) -> nothing to check -> no block.
    Fails OPEN on any error (see _precommit_config_dirty). Per-gate rollback
    lever: CSA_NO_DIRTY_CONFIG_GATE=1 (this gate only; mirrors gate 3's
    CSA_NO_REQUIRE_PATHSPEC, 3b's CSA_NO_PRECOMMIT_REVIEW, 4's
    CSA_NO_COMMIT_MUTEX — every gate here that can independently wedge a
    commit has its own rollback lever, not just the global kill-switch).

    Logs/denies under DIRTY_CONFIG_HOOK_NAME ("dirty_precommit_config"), NOT
    this dispatcher's own HOOK_NAME (FINDING 3, round 3) — every sibling
    gate logs under its own module's hook name; this one has no separate
    module, so it needs its own distinct label instead of defaulting to the
    dispatcher's.
    """
    if not repo_root:
        return None
    if os.environ.get("CSA_NO_DIRTY_CONFIG_GATE", "") == "1":
        return None
    if not _declared_pathspec(command)[1]:
        return None
    if _pathspec_includes_precommit_config(command, where, repo_root):
        return None
    if not _precommit_config_dirty(repo_root):
        return None
    return _Block(
        DIRTY_CONFIG_HOOK_NAME,
        "dirty-precommit-config",
        "dirty_precommit_config: blocked commit (dirty-precommit-config). "
        "the pre-commit config has uncommitted changes; a pathspec commit "
        "builds a temp index and WILL fail pre-commit's config check. "
        "Working recovery (3 steps — a bare config-only commit is ITSELF "
        "denied by gate 3b for want of a review): "
        "(1) review the config diff, then record it — "
        "python3 ~/.claude/hooks/record_review.py <repo> --pre-commit "
        "--clean --paths .pre-commit-config.yaml; "
        '(2) git commit -m "chore: sync pre-commit config" -- '
        ".pre-commit-config.yaml; "
        "(3) retry the original commit. "
        "See ~/.claude/.enforcement/log.jsonl.",
        git_state=False,
    )


# Shell-redirect expressions (`>`, `>>`, `<`, `<<`, `<<<`, `2>`, `2>>`, `&>`,
# `2>&1`, `>&-`, `>|`, ...), stripped from the RAW command STRING — not from a
# resolved token/path list. 08-25 fix round (B3): the previous approach
# (_filter_redirect_tokens, retired) filtered the RESOLVED pathspec list
# AFTER _commit_target_paths had already assembled it, which is wrong two
# separate ways that no amount of list-filtering can fix:
#   1. An ATTACHED operator (`2>/dev/null`, no space) is never a separate
#      token at all — shlex fuses it into ONE token, so there is nothing
#      later to recognize as "the operator" to filter.
#   2. A self-contained dup form (`2>&1`) inside a COMPOUND command is
#      amputated by _lib.git_segments' own tokenizer: `_split_segments`
#      treats a bare `&` as a control-operator boundary (it has to, for real
#      `&`/`&&` job-control/AND-OR parsing), so `2>&1 && git commit ... --
#      b.py` gets torn into fragments BEFORE segmentation ever sees a real
#      `&&` between the two commits — by the time a resolved path list
#      exists, the SECOND commit's own pathspec (`b.py`) has already been
#      flattened into the same list as the first commit's dangling `2>`
#      fragment, and the old filter's own skip-next adjacency logic then
#      swallowed `b.py` as if it were `2>`'s redirect target.
# Stripping the raw string ONCE, before ANY tokenization, fixes both: an
# attached operator+target is one contiguous substring to match regardless of
# adjacent whitespace, and removing `2>&1` (self-contained — see below)
# before segmentation means the stray `&` that used to tear the command in
# two is simply never there to trip _split_segments' boundary logic.
#
# Matches an optional leading fd digit(s) or `&` (`2>`, `&>`), the operator
# itself — `>|` (clobber-override; tried BEFORE plain `>>?` so the `|` is
# consumed as PART of the operator, never left for the target class to
# mis-eat, see below), `>`, `>>`, `<<<` (here-string; tried BEFORE plain
# `<<?` so all three `<` are consumed as one operator, never just two), `<`,
# `<<` — then EITHER a self-contained dup/close suffix (`&1`, `&-` —
# consumes NO separate target, e.g. `2>&1`, `>&-`) OR an attached-or-detached
# target (`\s*[^\s|]+` — zero or more spaces then a run of non-whitespace,
# non-`|` characters, so both `2>/dev/null` and `2> /dev/null` match whole,
# and a `|` immediately after — a real pipe boundary, not part of any
# redirect target — is never swallowed into it: `>| out.log`'s `|` belongs
# to the OPERATOR alternative above, and a bare `>` followed by `|less` at a
# pipe boundary now correctly leaves `|less` for whatever parses pipes,
# instead of the pre-fix bug where an unmatched `>|` left `out.log` behind
# as a bare, unclaimed token because the lone `|` got eaten as if it were
# the (1-char) target).
#
# QUOTE-AWARE (08-25 round-3 fix, BLOCKER 1): a redirect-shaped substring
# inside a QUOTED commit message — `-m "A -> B"`, the mandated
# `Co-Authored-By: Claude <noreply@anthropic.com>` trailer, `-m "bump
# n>=3"`, `-m "retry: 2>1"` — used to also get torn apart here, which made
# the CLEANED string untokenizable downstream (`_lib.git_segments` ->
# untokenizable sentinel -> `writing_commit_segments == []`) and, before the
# defensive net below existed, silently widened `_churn_observe`'s recorded
# target set to the WHOLE staged index — i.e. other agents' in-flight files.
# Measured: 23 of the last 55 runtime commit messages and 28 of 60 CSA
# messages went from correct to wrong this way; the mandated Co-Authored-By
# trailer alone triggered it on every commit. Fixed by scanning the RAW
# string with `re.finditer` (so a match's TARGET half may still extend INTO
# an adjacent quoted argument — see `<<< "msg"` below) but rejecting any
# candidate match whose OWN START position falls inside a quoted span (per
# `_quoted_positions`, built with the exact same single/double-quote
# state-walk `_lib._split_segments` uses — no backslash-escape handling,
# deliberately matching that function's own simplification): a `>`/`<`
# that is itself quoted text is never mistaken for a real operator, while a
# real, UNQUOTED operator is still allowed to consume a directly-adjacent
# quoted target the way a shell actually would (`<<< "msg"` -> the whole
# thing is one here-string expression and is removed entirely, never
# leaving a stray bare `msg` token behind after the surrounding quotes are
# later stripped by shlex). Local to this observer only — NOT a fix to the
# shared tokenizer (parked; see churn_phase0_measure.md's "Not in scope").
_REDIRECT_INLINE_RE = re.compile(r"(?:\d+|&)?(?:>\||>>?|<<<|<<?)(?:&(?:\d+|-)|\s*[^\s|]+)?")


def _quoted_positions(command: str) -> list:
    """Boolean mask, one entry per character of `command`: True where that
    character lies inside a single- or double-quoted span (the delimiter
    chars themselves included), False otherwise.

    Mirrors `_lib._split_segments`'s own quote-state walk exactly (same
    simplification: no backslash-escape handling) so this mask can never
    diverge from the shared tokenizer's idea of what's quoted — but returns
    a per-character mask rather than a list of segments, since
    `_strip_redirects` needs to ask "is THIS match's start position quoted?"
    at an exact string offset, not "what are the segment boundaries?" (which
    would also split on `&`/`|`/`;`/`(`/`)`, exactly the characters a
    redirect/here-string expression must be allowed to span across — see the
    `2>&1 &&` chaining case in `_REDIRECT_INLINE_RE`'s own comment).
    """
    mask = [False] * len(command)
    q = None
    for i, c in enumerate(command):
        if q:
            mask[i] = True
            if c == q:
                q = None
            continue
        if c in ("'", '"'):
            mask[i] = True
            q = c
    return mask


def _strip_redirects(command: str) -> str:
    """Remove every UNQUOTED shell-redirect expression from a raw command
    STRING, leaving quoted text (single- or double-quoted) untouched.

    Applied ONCE, before any tokenization/path resolution — see
    _REDIRECT_INLINE_RE's comment for why filtering the already-resolved
    path list (the retired _filter_redirect_tokens) could never be made
    correct, and for the quote-awareness fix (B1, 08-25 round 3). Scans the
    RAW string with `_REDIRECT_INLINE_RE.finditer`; a candidate match is
    replaced with a single space (never empty-string concatenation, so
    removing an operator can never fuse two adjacent real tokens into one)
    UNLESS its own start position is inside a quoted span per
    `_quoted_positions` — that candidate is left exactly as written instead
    (it's quoted TEXT, not a real shell redirect). Never raises: the mask
    build and the regex scan can't fail on a string input.
    """
    if not command:
        return command
    mask = _quoted_positions(command)
    out = []
    last = 0
    for m in _REDIRECT_INLINE_RE.finditer(command):
        start = m.start()
        if mask[start]:
            continue  # the operator itself is quoted text -- leave it alone.
        out.append(command[last:start])
        out.append(" ")
        last = m.end()
    out.append(command[last:])
    return "".join(out)


def _churn_observe(
    ev: dict,
    command: str,
    where: str,
    repo_root: str | None = None,
    staged: list | None = None,
) -> None:
    """Gate 6: churn_tracker. A PURE OBSERVER — NEVER returns a _Block, so it
    cannot itself deny/delay a commit (see churn_tracker.py's module docstring
    and pretooluse_bash's own GATE ORDER note above). Records this commit's
    target paths and logs one "churn-flagged" entry per path that just
    crossed the configured threshold. Only impure for a real, writing `git
    commit` (mirrors every other gate's discipline). Never raises: any
    failure is swallowed, since an observer must never affect the commit
    it's watching.

    Deliberately does NOT accept (or reuse) the caller's already-resolved
    `targets` the way gates 3b/4 do (NIT 25) — that list is derived from the
    RAW, redirect-dirty command (gates 3b/4 tolerate that leakage; this
    observer cannot, see _REDIRECT_INLINE_RE's comment) and reusing it here
    would just reintroduce the exact bug this fix removes. Instead this
    ALWAYS re-derives its own target list from `_strip_redirects(command)`.
    `staged` (the pre-read git index, when the caller already has one) is
    still reused so re-deriving never re-runs `git diff --cached` for the
    same event (NIT 25 actual expensive part — the git-segment parse
    itself is pure and cheap to redo); `repo_root` is reused the same way it
    always was.

    DEFENSIVE NET (B1, 08-25 round 3): `should_guard(ev)` above already
    proved the RAW `command` carries a real writing commit segment (it is
    literally `bool(writing_commit_segments(command))`). If stripping this
    command redirects destroys that parseability — either the cleaned string
    hits the untokenizable sentinel, OR (round-4 blocker) it still parses to
    a writing commit segment but the strip destroyed the `--` pathspec that
    the raw command carried — that is `_strip_redirects` own bug, never a
    genuine "nothing to observe" case. `_commit_target_paths` own fallback
    ("no segments, use the WHOLE staged index") must never fire for a parse
    failure this function caused: that would silently record every OTHER
    agent in-flight staged file against this commit. So: try the cleaned
    command first; if it has no writing commit segments at all, fall back to
    the untouched RAW command instead (should_guard guarantees it parses),
    accepting the narrower, already-documented heredoc-pollution risk
    `_strip_redirects` exists to avoid, rather than the far worse
    staged-index leak. Second half of the same net: even via the RAW
    fallback, never record a path outside the commit own declared pathspec
    when one actually exists (`_declared_pathspec`) — only a genuinely
    pathspec-less or `--include` commit (judged/BLOCKed by gate 3, not
    silently widened here) may legitimately produce a target set wider than
    its pathspec.
    """
    if not css.should_guard(ev):
        return
    try:
        cleaned = _strip_redirects(command)
        raw_has = _declared_pathspec(command)[1]
        cleaned_has = _declared_pathspec(cleaned)[1]
        # Third net condition (round-4 blocker): stripping can leave a string
        # that STILL parses to a writing commit segment but with an emptied
        # pathspec (an embedded literal '"' desyncs the quote walk, so a
        # later <word> is stripped through the `--` boundary). Raw wins then
        # too — never let a strip-destroyed pathspec fall through to
        # _commit_target_paths' whole-staged-index default.
        use_raw = (not css.writing_commit_segments(cleaned)) or (
            raw_has and not cleaned_has
        )
        source = command if use_raw else cleaned
        targets = _commit_target_paths(ev, source, where, staged)
        pathspec, has_pathspec = _declared_pathspec(source)
        if has_pathspec:
            pathspec_set = set(pathspec)
            targets = [t for t in targets if t in pathspec_set]
        if not targets:
            return
        if repo_root is None:
            repo_root = ct.repo_root_of(where) or where
        window = ct.window_from_env()
        threshold = ct.threshold_from_env()
        result = ct.observe_commit_for_event(
            _lib.CHURN_DIR, _lib.LAST_REVIEWED, repo_root, targets, window, threshold
        )
        for path, count in sorted(result.get("newly_flagged", {}).items()):
            _lib.log(ct.HOOK_NAME, "churn-flagged", path=path, count=count, repo=repo_root)
    except Exception:
        return


def resolve_block(
    ev: dict, command: str, where: str, out: dict | None = None
) -> tuple[_Block | None, dict]:
    """Run all eight gates in order; return the FIRST block (with its log detail).

    `out` (optional, default None — every pre-existing caller and test keeps
    its 3-arg call unchanged): when a dict is supplied, the repo root this
    function ALREADY resolves for gates 3/4 is written into it under
    "repo_root" so `_finish` can put it on the enforcement row (telemetry plan
    §4.2a) without paying for a second `git rev-parse` subprocess. It is
    strictly an out-channel: nothing in this function ever reads it, so a
    caller passing None loses only the reuse, never a decision. Only ever set
    for a GUARDED (writing `git commit`) event — the non-commit path
    deliberately resolves no repo root at all, and this change does not make
    it start.

    Gate 3b (precommit_review_gate, added 2026-08-19 on operator direction —
    "it shouldn't run after the commit, it should run before the commit")
    sits between gates 3 and 4: it denies a `git commit` whose exact pending
    content has no code review on record. It is placed before gate 4 so a
    review-denied commit never claims the per-repo commit mutex.

    Gate 3c (dirty_precommit_config, #4670 item 3, 2026-08-30) sits
    between 3b and 4 for the same reason: it denies a pathspec commit that
    is GUARANTEED to fail pre-commit's own config-staleness check (a dirty
    `.pre-commit-config.yaml`) before gate 4 ever takes a claim for it —
    see _dirty_precommit_config_block's own docstring and the GATE ORDER
    note at the top of this module.


    Pure w.r.t. env policy (log-only vs enforce, master-off, escape hatch) — those
    decisions live in main(), EXCEPT gate 4, which must know enforcing() itself to
    decide whether to poll (see _file_claim_block). Gates 3 and 4 are the only
    BLOCKING impure gates among 1-4 (gate 3 reads the git index; gate 4 reads/
    writes the claim ledger), both only for a writing `git commit`. Gate 5
    (gh_issue_close_gate) is also impure (it shells to git to verify commit
    existence/ancestry) but only for a `gh issue close` command — orthogonal to
    gates 1-4's `git commit` trigger, see _gh_issue_close_block. Gate 5b
    (protected_board_guard) is PURE (no I/O beyond loading the static, on-disk
    protected-boards registry) and, like gate 5, orthogonal to every `git
    commit`-shaped gate — see _protected_board_block. Gate 6
    (churn_tracker) is reached ONLY when nothing earlier blocked (matching the
    established first-block-wins short-circuit every gate here already follows
    — recording a commit that a real deny actually prevented would be wrong)
    and can never itself contribute a block.

    NIT 25: gates 3, 4, and 6 each need the SAME two facts about a guarded
    `git commit` event — the staged index / resolved target paths, and the
    repo's toplevel — and each USED to independently re-derive them via its
    own `git` subprocess call. Computed ONCE here (only when `css.should_guard`
    says there's a real writing commit to look at at all — the common non-
    commit case pays for none of this) and threaded down as the `staged` /
    `targets` / `repo_root` params those gates now accept, cutting the git
    subprocess count for a guarded commit from up to 4 calls (read_staged_paths
    x3, repo_root_of x1) to 2 (one each).

    Never raises: any error degrades to no-block.
    """
    try:
        # Issue-creation quality observer (#5827, WS1 Phase D): a PURE
        # OBSERVER that can never block, called unconditionally and first —
        # ordering relative to every blocking gate below is immaterial to
        # THIS call's own outcome (it never returns one), but firing it
        # before any early return guarantees a `gh issue create`/`gh_issue.sh
        # create` command is always observed regardless of what (if
        # anything) later gates decide about the SAME command. See
        # _issue_create_observe's own docstring.
        _issue_create_observe(command, where)

        b = _branch_ops_block(command)
        if b is not None:
            return b, {}
        b = _head_overwrite_block(ev)
        if b is not None:
            return b, {}
        b = _gcloud_identity_block(command)
        if b is not None:
            return b, {}
        b = _unscoped_commit_block(ev)
        if b is not None:
            return b, {}

        guarded = css.should_guard(ev)
        # effective_where: the directory THIS command's git invocation actually
        # targets, honoring `git -C <path>` (the pattern this harness's own
        # system prompt tells agents to prefer over `cd <dir> && git ...`) —
        # NOT just the Bash tool's own cwd. Without this, a commit run via
        # `git -C /other/repo commit ...` read the WRONG repo's staged index
        # and claimed a commit-mutex token / recorded authorship against the
        # session's own cwd instead of the repo actually being committed to
        # (silent wrong-repo mutex + a review-gap-causing UNKNOWN_AUTHOR for
        # the real target repo). Since the #5061 fix, a leading literal
        # `cd <dir> && git ...` prefix IS parsed too (_lib._leading_cd_dir:
        # `&&`-joined literal dirs only — `;`/`||`/`&`/subshell/`cd -`/`$VAR`
        # and any unconsumed later `cd` all fall back to `where`, exactly the
        # pre-fix behavior).
        effective_where = _lib.effective_git_cwd(command, where) if guarded else where
        staged = css.read_staged_paths(effective_where) if guarded else None
        targets = _commit_target_paths(ev, command, effective_where, staged) if guarded else None
        # real_repo_root: the ACTUAL resolved toplevel, or None when it can't
        # be resolved (non-repo cwd, no git, timeout) — used for gates 3/4,
        # which must never claim a commit-mutex token or run an absolute-path
        # bulk-pathspec check against a made-up fallback path. churn_repo_root
        # keeps the pre-existing `or where` fallback (any string is a fine
        # bucketing key for the churn observer, which is not correctness-
        # sensitive the way the mutex/bulk-pathspec checks are).
        real_repo_root = ct.repo_root_of(effective_where) if guarded else None
        churn_repo_root = (real_repo_root or effective_where) if guarded else None
        # Telemetry plan §4.2a: hand the ALREADY-resolved repo root back to
        # _finish for the enforcement row. Best-effort and non-load-bearing —
        # a failure here must never affect which gate blocks, so it is
        # swallowed and _finish simply resolves it itself.
        if out is not None:
            try:
                out["repo_root"] = real_repo_root
            except Exception:
                pass

        b, detail = _staged_scope_block(ev, effective_where, staged, real_repo_root)
        if b is not None:
            return b, detail
        b, detail = _precommit_review_block(
            ev, command, effective_where, staged, real_repo_root
        )
        if b is not None:
            return b, detail
        b = _dirty_precommit_config_block(command, effective_where, real_repo_root)
        if b is not None:
            return b, {}
        b, detail = _file_claim_block(ev, command, effective_where, targets, real_repo_root)
        if b is not None:
            return b, detail
        b, detail = _gh_issue_close_block(ev, command)
        if b is not None:
            return b, detail
        b = _protected_board_block(command)
        if b is not None:
            return b, {}
        _churn_observe(ev, command, effective_where, churn_repo_root, staged)
        return None, {}
    except Exception:  # pragma: no cover - gates already fail-safe internally
        return None, {}


def _escape_hatch_active() -> bool:
    """CSA_ALLOW_GIT_STATE_OPS=1 in the hook's OWN process env."""
    return os.environ.get(_ESCAPE_VAR, "") == "1"


def _log_fields(
    ev: dict | None, where: str, repo_root: str | None, detail: dict | None = None
) -> dict:
    """The identity fields MERGED UNDER `detail`, as ONE dict to splat into
    `_lib.log(**...)`.

    Merging rather than splatting two dicts side by side is load-bearing, not
    style. `**a, **b` in a call raises `TypeError: got multiple values for
    keyword argument` the instant the two share a key — which CRASHES the hook
    and, under enforcement, turns a would-be deny into an unguarded allow. That
    is not hypothetical: `gh_issue_close_gate` (gate 5) already puts a `repo`
    key in its detail dict (gh_issue_close_gate.py:686) holding a GitHub
    `owner/name` SLUG — a different thing entirely from this module's
    filesystem repo ROOT. Five existing tests in test_pretooluse_bash.py's
    TestGateGhIssueClose / TestBashGateShEndToEnd caught exactly that crash.

    `detail` WINS every collision, deliberately: a gate's own field is the
    authoritative one for its row, and this telemetry change must not alter
    what any pre-existing row contained. So a gh-issue-close row keeps its
    `repo` slug and simply gets no filesystem repo root — the honest outcome,
    since that row's `repo` means something else and silently overwriting it
    would corrupt both readings.

    Never raises: identity resolution is fully guarded below, and a bad
    `detail` degrades to identity-only rather than losing the row.
    """
    fields = _identity_safe(ev, where, repo_root)
    try:
        if detail:
            fields.update(detail)
    except Exception:
        return dict(detail) if isinstance(detail, dict) else {}
    return fields


def _identity_safe(ev: dict | None, where: str, repo_root: str | None) -> dict:
    """`_identity` behind an OUTER guard, so the fail-open contract does not
    depend on `_identity`'s own internal try/except staying correct.

    This wrapper is not redundant belt-and-braces: at a call site the identity
    dict is SPLATTED into `_lib.log(**...)`, and the splat is evaluated BEFORE
    log() is entered — so an exception escaping `_identity` propagates out of
    `_finish` entirely, past log()'s own guards, and crashes the hook. A
    crashed PreToolUse hook is precisely the "telemetry failure changes the
    command's outcome" the plan forbids. Proven by test:
    TestBashEntryPointFailOpen::test_denied_command_stays_denied_when_identity_explodes
    fails without this wrapper.

    Every identity call site MUST use this, never `_identity` directly.
    """
    try:
        return _identity(ev, where, repo_root)
    except Exception:
        return {}


def _identity(ev: dict | None, where: str, repo_root: str | None) -> dict:
    """Identity kwargs for THIS entry point's enforcement rows (telemetry plan
    §4.2 4a / §4.2a). Returns a dict to splat into ``_lib.log``.

    NO ``agent_type`` — DELIBERATELY, and this is the one thing about this
    function not to "fix". A ``PreToolUse:Bash`` payload describes a shell
    command, not a dispatch: ``tool_input.subagent_type`` (the field
    ``_lib.subagent_type`` reads, and the only source either gate has for an
    agent type — agent_budget.py:970, model_pin_gate.py:623) exists ONLY on a
    ``Task`` payload. Synthesizing one here would be fabrication. The
    consequence is recorded in the plan and accepted: commit-blocking denials
    get SESSION-level attribution, not per-agent-type attribution; the latter
    is a read-side join on ``session`` + ts against ``spend.jsonl``, never a
    field.

      session   — ``_lib.session_id``; the "nosession" sentinel is dropped by
                  ``_lib._identity_fields``, never written.
      repo      — the repo root gates 3/4 already resolved for this event when
                  it is a guarded `git commit` (threaded in via
                  ``resolve_block``'s `out` channel, so no second subprocess).
                  When that is absent — every NON-commit block, i.e. gates
                  1/1b/2, which deliberately resolve no repo root — it is
                  resolved here, ONLY on the block path (`_finish` calls this
                  only after a gate has already blocked), so an allowed
                  command still pays nothing.

    §4.2a is why `repo` matters at all: all 2,234 historical `gate:
    file_claims` denial rows carry no repo and no cwd, which is what made the
    friction ratio's numerator un-joinable to a per-repo denominator.

    FAIL-OPEN: every failure degrades to {} — identity is telemetry, and a
    telemetry failure must cost the fields, never the row, and never the
    command's allow/deny outcome. The kill-switch short-circuits before the
    repo-root subprocess can be spawned.
    """
    try:
        if not _lib.log_identity_enabled():
            return {}
        out: dict = {}
        try:
            out["session"] = _lib.identity_or_none(_lib.session_id(ev or {}))
        except Exception:
            out["session"] = None
        resolved = repo_root
        if not resolved and where:
            try:
                resolved = ct.repo_root_of(where)
            except Exception:
                resolved = None
        out["repo"] = _lib.identity_or_none(resolved or "")
        return out
    except Exception:
        return {}


def _finish(
    block: _Block | None,
    detail: dict,
    command: str,
    where: str,
    ev: dict | None = None,
    repo_root: str | None = None,
) -> int:
    """Terminal action for the resolved gate result. Returns exit code (ALWAYS 0).

      No block            -> allow (nothing emitted, nothing logged).
      git-state block + OWN-env escape hatch + NOT the inline tripwire
                          -> escape-allowed (log the escape, allow silently).
      block               -> LOG the would-block always; emit the canonical deny
                             ONLY when enforcing(); else stay silent (log-only).

    `ev` / `repo_root` (both optional, default None — every pre-existing
    caller and test keeps its 4-arg call unchanged) carry the identity
    telemetry plan §4.2 4a puts on these rows; see `_identity`. Both are
    read ONLY on a block path, so an allowed command is untouched. Neither
    can influence the decision: they are consumed exclusively as `_lib.log`
    kwargs, below the point where `block` has already been resolved.
    """
    if block is None:
        return 0

    # Escape hatch: only for git-state blocks (gate 1/1b/2), only from the hook's
    # OWN env, and NEVER for the inline tripwire (a command string that smuggled
    # the var name). The index-scope gate (git_state=False) has no hatch.
    if (
        block.git_state
        and block.reason != "inline-escape-var-forbidden"
        and _escape_hatch_active()
    ):
        _lib.log(
            HOOK_NAME,
            "escape-allowed",
            gate=block.hook,
            reason=block.reason,
            command=command,
            **_log_fields(ev, where, repo_root),
        )
        return 0

    # R6 (08-25 fix round): compute the REAL decision once, against the
    # event's OWN cwd (`where`), and pass it explicitly into log() as an
    # `enforce=` override. _lib.log's own internal "enforce" field defaults
    # to a bare, no-arg enforcing() call — which falls back to os.getcwd(),
    # i.e. the PROCESS's cwd, not the event's. Those two can genuinely
    # differ (e.g. a background hook invocation, or any caller whose event
    # payload names a different cwd than the process it's running in), so
    # without this override the logged `enforce` field could read False on a
    # would-block that was ACTUALLY denied (this function's own `enforcing
    # (where)` call two lines below is the real decision). The fields-
    # override loop in _lib.log (see its own docstring) applies caller kwargs
    # AFTER its structural default, so this simply wins.
    enforce = _lib.enforcing(where)
    _lib.log(
        HOOK_NAME,
        "would-block",
        gate=block.hook,
        reason=block.reason,
        command=command[:2000],
        enforce=enforce,
        **_log_fields(ev, where, repo_root, detail),
    )

    if enforce:
        _lib.emit_pretooluse_deny(block.message)
    # Log-only default: allow silently.
    return 0


def main() -> int:
    """Entry point. Reads stdin ONCE, runs the gates, emits/logs, returns 0."""
    # Master OFF switch — no-op allow before touching anything else.
    if _lib.disabled():
        return 0

    try:
        raw = sys.stdin.read()
    except Exception:
        raw = ""

    ev = _lib._parse_event(raw)

    if not ev:
        # Parse error: fail CLOSED only when the raw string mentions a git OR
        # gcloud token (delegated to each gate's own whole-word detector,
        # matching their respective main()s). Checked in gate order — git
        # first, matching every other gate-order tie in this dispatcher.
        if bbo._raw_mentions_git(raw):
            block = _Block(
                bbo.HOOK_NAME,
                "parse-error-with-git-token",
                "block_branch_ops: blocked git state-mutation "
                "(parse-error-with-git-token). This op is reserved for the operator. "
                "See ~/.claude/.enforcement/log.jsonl.",
                git_state=True,
            )
            return _finish(block, {}, raw[:2000], where="")
        if bgi._raw_mentions_gcloud(raw):
            block = _Block(
                bgi.HOOK_NAME,
                "parse-error-with-gcloud-token",
                bgi._message_for("parse-error-with-gcloud-token"),
                git_state=True,
            )
            return _finish(block, {}, raw[:2000], where="")
        return 0  # no git/gcloud mention -> nothing to guard.

    # Only gate the Bash tool.
    if _lib.tool_name(ev) != "Bash":
        return 0

    command = _lib.bash_command(ev)
    where = _lib.cwd(ev)

    # `resolved` is resolve_block's out-channel for the repo root it already
    # computes for gates 3/4 (telemetry plan §4.2a) — reuse, not recompute.
    # An unguarded (non-commit) event leaves it empty and _identity resolves
    # the root itself, but only if a gate actually blocked.
    resolved: dict = {}
    block, detail = resolve_block(ev, command, where, resolved)
    return _finish(
        block, detail, command, where, ev=ev, repo_root=resolved.get("repo_root")
    )


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
