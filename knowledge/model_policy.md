# Model Policy — human-readable companion

**Single source of truth is [`model_policy.json`](model_policy.json).** This file explains the
reasoning behind it; if the two ever disagree, the JSON wins and this file is stale and should be
corrected to match it, not the other way around.

## Why "token-optimal," not "cheapest"

The goal is never the lowest-cost model per call — it's the lowest *expected total cost* to reach a
correct, complete, verified result. A cheap model that produces a wrong answer, gets caught in
review, and has to be redone on a capable model cost more tokens overall than starting on the
capable model once. Conversely, running Opus on a poll-and-report loop or a mechanical sweep is
waste in the other direction — no reasoning depth is being bought with that spend. `task_defaults`
encodes this per *kind of work*, not per agent: `poll_report` and mechanical/sweep/drafting work sit
on the cheap-to-mid tier (haiku/sonnet); anything that is a genuine judgment boundary — a review
gate, a ranked/prioritized call, hard debugging where the failure mode isn't yet understood — sits
on `opus`. `agent_pins` then fixes each named agent in `~/.claude/agents/` to the tier its typical
work actually needs, so a dispatch never silently inherits whatever model the parent session happens
to be running (see the runtime contract's catch-all-agent warning — unpinned dispatches are exactly
how a stray Opus default cascades).

## The escalate-on-churn logic

Model tier is not a one-time decision per agent — it adapts to observed outcomes:

- **`on_churn`** — the same task failing *twice* on the cheap tier escalates to the capable tier on
  the third attempt. It never gets a third cheap retry: two failures is the signal that the task
  needs more reasoning depth, not more luck.
- **`on_demoted_reasoning`** — if a finding gets demoted during verification specifically because of
  a reasoning-quality gap (not a factual miss a cheap model could equally have made), the re-run goes
  one tier up, not a same-tier retry.
- **`de_escalate`** — the inverse path exists too: once a capable-tier model has stabilized a piece
  of work into a repeatable, mechanical recipe, it moves down one tier — but only after one explicit
  calibration comparison confirms the cheaper tier reproduces the same result, never by default drift.

## The `effort_defaults` dimension (AA-0062, 2026-09-01 agentic-systems-architect audit)

Model tier (`task_defaults`) is one axis of cost; per-dispatch *effort* is a second, independent one,
and until 2026-09-01 the policy had no effort dimension at all — `effortLevel` was globally `"high"`
for every dispatch shape, even though the platform's own measured curves put `"medium"` at 70-85% of
default cost for research/knowledge work and roughly half cost for long-horizon coding. `effort_defaults`
mirrors `task_defaults`'s own shape keys (`poll_report`, `mechanical`, `sweeps`, `drafting`,
`research_reading`, `browser_driving`, `review_boundary`, `ranked_judgment`, `hard_debugging`) so the
two dimensions read together as one per-shape policy: which *model* a shape of work runs on, and how
much *effort* it spends reasoning once dispatched.

**This lever is Workflow-only, not a general dispatch setting.** Verified against the live client
2026-09-01: the plain `Agent` dispatch tool exposes no per-dispatch `effort` parameter at all — a
sub-agent dispatched that way always inherits the parent session's own `effortLevel`, the same
inheritance the runtime contract's catch-all-agent warning already describes for `model`. The
`Workflow` tool's `agent()` helper, by contrast, DOES expose `opts.effort` per agent it dispatches —
so `effort_defaults` only has a real application path inside Workflow-orchestrated fan-out, never a
plain `Agent` call. A session using `Agent` dispatch cannot apply this policy per-call today; it can
only set its own session-level `effortLevel` (governed by `session_rules`/`settings.json`, unchanged
by this addition).

Two guardrails recorded in the block's own `notes` field, not just here: (1) a shape only adopts its
`effort_defaults` tier after a frozen-task sweep confirms the cheaper tier reproduces the same result
on real, already-solved work — per the platform's own cost-optimization doc — never assumed from the
shape's `task_defaults` model tier alone (a `"medium"`-model shape is not automatically a
`"medium"`-effort shape); (2) effort is never changed *mid-conversation* — switching it invalidates
that conversation's prompt cache, a cost larger than what tiering effort is meant to save in the first
place. This mirrors the model-tier discipline already documented above (fixed per dispatch, never
drifted ad hoc) applied to the second axis.

## Who consumes `model_policy.json`

- **The pin-parity checker** (`~/.claude/hooks/model_pin_parity.py`, report-only) — validates that every agent file under `~/.claude/agents/` actually
  declares the model this policy pins it to, catching drift the same class of incident as the
  runtime contract's four historical model-default regressions (a config value silently reverting or
  getting folded into an unrelated commit). It also checks the sanctioned-Opus extension set against BOTH
  `CLAUDE.md`'s own §13 roster table AND §10's sanctioned-Opus bullet enumeration
  (`contract-roster-drift`, two halves — the §10 half added 2026-09-05 after `marketing-director`
  landed in `OPUS_AGENTS` and §13's table while absent from the §10 bullet whose own rule says the
  tuple and the bullet move together, and the table-only check passed throughout), so the
  machine-readable policy and the human-readable contract can't silently diverge. Extended 2026-09-01 (AA-0063) to cross-reference
  the REAL spend ledger against the roster + this policy: `unpinned-live-agent-type` flags any
  `agent_type` seen dispatching in `~/.claude/.agent_budget/spend.jsonl` (last 30 days) with neither an
  `agents/<name>.md` file nor an `agent_pins` entry, and `unsanctioned-fable-dispatch` flags a dispatch
  that ran on `claude-fable-5` ($10/$50, 2x Opus 5) whose `agent_type` is not pinned `"fable"` —
  which, now that standing fable pins are RETIRED (operator directive, 2026-09-24: "change all
  models pinned to fable to be pinned to opus (5.5)") and `sync_agent_rules.FABLE_AGENTS` is empty,
  effectively flags EVERY fable dispatch as a finding. Both checks are opt-in per the same hermeticity pattern `contract-roster-drift`
  already uses (only run when the caller supplies a real spend-ledger path); `main()` always does.
  Extended 2026-09-19 (operator directive: `plan-reviewer`/`marketing-director` permanently
  pinned fable) with `fable-sanction-drift`: the identical two-machine-readable-copies discipline as
  the existing opus `sanction-drift` check, narrowed to the fable subset — holds this policy's fable
  `agent_pins` entries and `sync_agent_rules.FABLE_AGENTS` in parity, flagging a fable pin on any
  seat the tuple does not sanction. **Both former standing fable pins are now retired.**
  `marketing-director` (pinned fable 2026-09-19) and `plan-reviewer` (pinned fable by OPERATOR
  RULING 2026-09-20, ExampleApp OPERATOR_DECISIONS.md card [87], ACCEPTED, which had
  reversed a same-day trust-architect narrowing to opus, BLOCKER B1) are both now pinned `"opus"`.
  Card [87] (which restored plan-reviewer's standing pin against THE ISSUE WHEEL's unattended
  nightly schedule, `com.oversight.wheel.csa`/`.agency`, dispatched BARE) stays on record, but is
  no longer load-bearing at the opus tier: opus-on-the-wheel was itself B1's own 2026-09-19 remedy,
  and `launch-director` already runs its weekly report on opus, unattended, with no override at
  all. `session_rules.no_unattended_opus_loops` never barred a sanctioned Opus agent from running
  unattended — the override card [87] granted was needed only for the fable tier plan-reviewer
  briefly carried, which sits above what that rule already permits. With
  `agent_pins` and `FABLE_AGENTS` both carrying no fable entries, `fable-sanction-drift` reports no
  drift by construction; the tuple and the check remain in place for any future standing fable pin,
  which would need its own operator ruling on a named seat.
  Extended again 2026-09-01 (model-pin-enforcement build) with `pin-tier-mismatch`: cross-references
  `spend.jsonl` against the RESOLVED pin (frontmatter first, falling back to this policy — the exact
  resolution `model_pin_gate.py` uses) in both directions (below-pin and above-pin), suppressing any
  row whose `(agent_type, model)` pair has a historical exception grant on record
  (`~/.claude/.model_exceptions/grants.jsonl`). Report-only, same as every other check here — the
  real enforcement is the gate below.
- **`model_pin_gate.py` (`~/.claude/hooks/pretooluse_task.py`'s gate T1) — the FIRST real
  enforcement of `agent_pins` at dispatch time**, added 2026-09-01, hardened the same day (2026-09-01
  fix round, six trust-architect blockers B1–B6) after an adversarial review found the first cut
  agent-self-serve in practice. **WIRED LIVE 2026-09-03** — `settings.json`'s `PreToolUse:Task`
  matcher runs `pretooluse_task.py`, landed after the fix round's own clean Opus review; see
  `hooks/agent_pacer.md`'s own wiring note for current status. Until this build, the pin-parity
  checker above was the ONLY reader of
  `agent_pins` anywhere — nothing gated an actual `Task` dispatch, so an explicit `tool_input.model`
  override always won client-side regardless of the policy. Pin resolution now UNIONS the runtime
  roster (`~/.claude/agents/`) with the CURRENT REPO's own `.claude/agents/*.md` roster (repo root via
  `git rev-parse --show-toplevel`, repo-local wins a name collision, mirroring the real client's own
  project-over-user precedence) — a still-repo-local product-domain agent is genuinely governed by its
  own frontmatter pin, not silently ungoverned. This gate denies an off-pin dispatch UNLESS one of two
  things covers it: (1) a single-use, 15-minute-TTL, **dispatch-bound** exception token (minted by
  `~/.claude/hooks/record_model_exception.py`, verified independently against `review_risk_tier.py`'s
  real classifier for a genuine downgrade, or a sonnet-pin-only upward escalation for hard-debugging —
  never `fable`, never the caller's own say-so, and bound to the SHA-256 of the exact dispatch prompt
  it was minted for, so a token minted for one dispatch can never authorize a semantically different
  one sharing the same `(agent_type, model)` pair); or (2) a single-use, short-TTL **operator-grant**
  file written by `~/.claude/scripts/grant_model_exception.sh` — run by the OPERATOR directly in their
  own terminal, never agent-invokable — the ONLY path that can ever authorize a below-pin `fable`
  target. See
  `model_pin_gate.py`'s own module docstring for the full decision tree and the residual limitation
  the dispatch-binding does NOT close (it binds exact prompt bytes, not the `--paths` argument's own
  truthfulness about what that prompt will do). **Standing fable pins RETIRED (2026-09-24, operator
  directive, verbatim: "change all models pinned to fable to be pinned to opus (5.5)").**
  `marketing-director` (standing-pinned fable 2026-09-19, PERMANENT) and `plan-reviewer`
  (standing-pinned fable by OPERATOR RULING 2026-09-20, card [87], ACCEPTED, after a same-day
  trust-architect narrowing, BLOCKER B1) are both now pinned `"opus"` in `agent_pins`. An on-pin
  dispatch of either still needs no grant at all (decisions 2/3 of the gate's own decision tree,
  both already agent-type-agnostic) — that mechanic is unchanged, only the pinned tier moved. For
  `plan-reviewer`, dispatched BARE by THE ISSUE WHEEL's own prompt on a launchctl-loaded, unattended
  nightly schedule, card [87]'s exception stays on record but is no longer load-bearing at the opus
  tier: opus-on-the-wheel was itself B1's own 2026-09-19 remedy, and `launch-director` already runs
  its weekly report on opus, unattended, with no override at all — `session_rules.no_unattended_opus_loops`
  never barred a sanctioned Opus agent from running unattended, only the fable tier plan-reviewer
  briefly carried needed the override. `launch-director` stays `opus`; it was excluded from the
  FORMER standing fable pin, not from any "unattended opus" restriction, which does not exist for a
  sanctioned agent. Every agent type is now never-fable, `marketing-director` and
  `plan-reviewer` included: a fable dispatch of any seat is reachable only via the operator-grant
  path above.
- **Scheduled/unattended sessions** — `session_rules.scheduled_session_model` and
  `no_unattended_opus_loops` bound what an unattended run is allowed to default to, so a scheduled
  job can't quietly run an expensive model in a loop with nobody watching the spend.
- **Review-boundary sessions** — `session_rules.review_ladder` encodes the cost-gated review
  discipline: a trivial-risk change gets a cheaper confirmatory pass rather than full Opus review;
  a fix-and-recheck round gets targeted verification BY DEFAULT, escalating to a full re-review on
  a broad fix, the two-consecutive-targeted-rounds cap, or a high-tier diff; only one reviewer
  covers a given boundary (no stacking substitute reviews as a way to avoid a real one); full plan
  review is reserved for plans substantial enough to warrant it; and a CODE-REVIEW full re-review
  round runs WARM — continue the round-1 reviewer at full scope (cold dispatch is the fallback;
  max two consecutive warm rounds per boundary; a risk-tier OR reviewer-of-record change breaks
  the warm chain) — per `CLAUDE.md` §10's 2026-08-30 addition, #4686.

Treat this JSON as append-only in spirit — when a new agent or task kind needs a tier decision, add
it here rather than letting a session improvise one inline.
