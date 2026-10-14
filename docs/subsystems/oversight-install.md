# Oversight system — liveness contract, kill-switch, and self-install

This is the portable half of the oversight system's operational reference: how the liveness
contract works, how to stop or unstick it, and how to install the whole system into a fresh repo.
The per-machine half — which jobs are actually installed, their labels/paths/prompt files, and any
install-specific status narrative — lives in `~/.claude/knowledge/oversight_install.md`, seeded from
`templates/knowledge/oversight_install.md` on first install (`init_repo.sh` copies it in only if
that path is absent). Read that file for "what jobs exist here"; read this one for "how any of it
actually works." See `docs/subsystems/oversight-wheel.md` for THE ISSUE WHEEL's own heartbeat shape,
its concurrency lock, and its queue mechanism in full mechanical detail — this document does not
repeat that content, only the parts of the liveness/kill-switch/install contract that apply to the
whole oversight roster, not just the wheel.

## Liveness contract

- Heartbeats: `~/.claude/schedules/heartbeats/<job>.json` — written TWICE per run, via Bash heredoc
  (the proven headless write path in repos with a bare `Bash` allow; see the spike history below).
  The two wheel jobs differ (GH #4767): their wrapper writes START and the session writes END through
  `hooks/wheel_sink.py`. A START write immediately
  after the budget-status pre-flight step: `{"job":"...","started_at":"...","finished_at":null,
  "exit":1,"cadence":"...","summary":"STARTED ..."}`. An END write OVERWRITES the same file with the
  completed shape: `{"job":"...","started_at":"...","finished_at":"...","exit":0,"cadence":"...",
  "summary":"..."}`. All timestamps are UTC ISO-8601 with a literal `Z` suffix. `manual-*`
  heartbeats (the manual on-demand fallback) carry `"cadence":"manual"` and are exempt from cadence
  auditing entirely.
- A daily (or otherwise most-frequent) job's first step should audit every other job's heartbeat,
  and a weekly report job should audit that daily job's heartbeat in return — a loop, not a chain,
  so no single job's silence goes unnoticed for longer than one full cycle of the *other* job that
  checks it.
- `~/.claude/hooks/heartbeat_audit.py` is the mechanical, non-LLM complement to that mutual-check
  step: it diffs the expected job set (parsed from the per-install seed's §2 job table) against
  actual heartbeats and `launchctl list` output, validates typed-key/UTC formatting, checks for a
  log-mtime divergence (a >5 minute gap between a heartbeat's claimed times and its own log file's
  mtimes flags a possible fabricated timestamp), and detects a job that's loaded but has never
  actually fired. It is designed to run as an embedded pre-step inside a session that is already
  firing (a daily job's first step, or a manual sweep's fixed pre-steps) — report-only, exit 0
  always. Its `stale-start` check (a STARTED heartbeat older than its own cadence + grace) can
  detect a job that crashed mid-run. What it alone CANNOT detect: the whole system going fully
  dark — every scheduled job silently failing to fire, so no session ever runs the audit in the
  first place. Closing that residual gap requires a separate, pure Python/shell watchdog process —
  no LLM session in its own loop, deliberately outside every other job's failure domain — that runs
  on its own independent schedule and calls `heartbeat_audit.py` itself, escalating on the finding
  classes that mean "a job is not alive" (a silently-dark job, a job that never fired despite being
  loaded, or a job whose table row says it should be loaded but `launchctl list` shows it absent).
  Escalation via a local desktop notification is the only LLM-free notify path available to a pure
  supervisor process — an agent-tool notification call requires a live session, which is exactly
  what a watchdog must not depend on.
- Non-zero `exit` in any heartbeat means the auditor should read that job's log tail and report why.
- **Residual gaps, named honestly rather than claimed away:** a local desktop notification only
  fires while the operator's machine is awake and logged in nearby — a run that dies while nobody is
  present produces a notification nobody sees until they next return. And on-demand/manual runs have
  no watchdog coverage at all — by definition, an on-demand run is watched by the human who invoked
  it, so this is accepted as out of scope rather than treated as a bug.

## Kill-switch & operations

- **Stop the whole system:** `touch ~/.claude/schedules/DISABLED` — every job checks this first: the
  two wheel jobs' wrapper checks it before launch and writes a `skipped-disabled` heartbeat plus a
  `WRAPPER:` log line; every other job's session checks it and exits silently (F7, ExampleApp
  #5913, moves those into the wrapper too). Remove the file to resume.
- Unload one job: `launchctl unload ~/Library/LaunchAgents/<label>.plist`.
- List running jobs: `launchctl list | grep oversight`. Logs: `~/.claude/schedules/logs/`.
- **Manual fallback when schedules are down or unavailable:** invoke the equivalent manual command
  (the runtime bundle's own on-demand command for this) rather than waiting for the next scheduled
  fire.
- A wheel-style job (one that builds, commits, and closes issues against a repo) needs its own
  concurrency guard so a nightly fire and an on-demand invocation can never race against the same
  repo — see `docs/subsystems/oversight-wheel.md`'s "Concurrency guard" section for the full lock
  design, its stale-reclaim sequence, and its own `lock-refused` heartbeat finding class. That
  mechanism is scoped to wheel-style jobs specifically (keyed by `WHEEL_SLUG`, a no-op for every
  other oversight job sharing the same launchd wrapper) — it is not a general-purpose lock for the
  rest of the roster.

## Installing into a new repo (the self-install procedure)

1. Author one FACTS dossier per oversight agent at `<repo>/.claude/oversight/<agent>.md` —
   trackers, incident history, staging-account references, flow lists, per-dimension commands —
   never a tracker itself. Rule: every count carries its own re-derive command plus an as-of date.
   1b. If the repo will dispatch the runtime's generic dev agents (`implement`, `test-writer`,
   `test-runner`, `git-ops`, `ci-monitor`, `explore`), also author a `<repo>/.claude/oversight/
   dev-runtime.md` dossier — a structurally different file: this repo's commands, layout, test
   placement, lint flags, branch model, and label taxonomy, each with `file:line` provenance. Those
   agents read it at task start when present and report it missing otherwise. Never create a
   same-named `<repo>/.claude/agents/<name>.md` twin instead — a project-level agent definition
   REPLACES the runtime one outright (see the runtime operating contract's preamble carve-out on
   name-keyed registries).
   1c. Set `worktree.baseRef: "head"` in `<repo>/.claude/settings.json`. Without it, harness-created
   worktrees branch from the remote default branch instead of the working branch's own HEAD, every
   worktree-isolated sub-agent reads a tree missing the session's own commits, and any job that
   relies on worktree isolation fails that precondition and exits every time it fires. Verify with
   `python3 -c "import json;print(json.load(open('<repo>/.claude/settings.json')).get('worktree',
   {}).get('baseRef'))"` — it must print `head` (the key is nested JSON; a grep for the dotted name
   can never match it).
   1d. Any job whose preconditions depend on locally-recorded verdict files (e.g. a review-gate or
   worktree-isolation probe) reads them from a machine-local, gitignored location — a fresh
   checkout or a new machine carries no verdicts. Such a job should fail SAFE on their absence
   (precondition FAIL means heartbeat-and-exit, never proceed unverified). Before relying on a job
   with this shape on a new machine, re-run its own precondition probes on THAT machine and confirm
   they record a passing verdict at the expected path before trusting the job to run unattended.
2. Add a one-paragraph routing note to the repo's own CLAUDE.md: a pointer to the runtime operating
   contract's oversight-roster section, plus the repo's own app-specific triggers for when to
   consult it.
3. Copy the per-install seed's §2 job table with this repo's own labels/paths/prompt files; install
   the corresponding plists — the launchd shape (`run_oversight_job.sh <job-label> <prompt-file>
   <cadence-text> [alarm-seconds]`, `WorkingDirectory`, `StartCalendarInterval`, never `RunAtLoad`)
   is documented in `docs/subsystems/oversight-wheel.md` § *The launchd jobs*, and
   `schedules/example.oversight.plist` / `schedules/example.wheel.plist` are the annotated
   templates to copy and fill per machine.
4. Sequence first engagements deliberately, each with a withheld calibration seed (a known-answer
   check kept out-of-band, so a first real audit can be graded against something concrete) — never
   trust a first audit's own self-report of quality with nothing to check it against.

## Standing decisions (do not re-litigate per install)

Enforcement stays globally ON; review cost is proportional to risk tier, not uniform; priority
lives in tracker FIELDS, not labels (labels retire once fields exist); unattended close/disposal
batches are always proposed for approval unless a job's own prompt names a standing close
authorization that passes every mechanical guard on each individual close; scheduled sessions are
always the cheaper model tier, never the expensive one — dispatched agents' own model pins govern
their individual runs regardless of the session's own tier.

## Installing a mission-scoped department (e.g. GTM) — dispatch-only, no scheduled job, by design

A mission-scoped department (the runtime operating contract's department-orchestrator class) is
NOT part of the oversight wheel — it is dispatched only on demand, never scheduled, and its absence
from the schedule must not be flagged as a fault by any heartbeat audit. Installing one into a new
product repo mirrors the self-install procedure above:

1. **One repo-local dossier per department seat** at `<repo>/.claude/oversight/<seat>.md` — a
   missing dossier means that seat self-declares DEGRADED, the same rule as the oversight roster
   above.
2. **A durable inbound label** (e.g. `dept:<name>`) in that repo — the department's durable inbound
   queue. Any agent, loop, or session that surfaces a finding belonging to the department files an
   issue with that label, and every mission's clarify phase reads the open queue before drafting
   questions for the operator. This label convention is the cross-department bus; a live
   session-to-session message is an accelerator only, never the durable channel.
3. **A mission-artifact surface** — a repo-local directory holding mission JSON output plus a
   dissent ledger and its own mechanical exit-contract evaluator, so mission convergence is decided
   mechanically rather than by an agent's own claim of consensus.
4. **The on-demand dispatch command/skill** that launches the department orchestrator with the
   operator's goal verbatim.

Runtime-side prerequisites (once per machine, already done as part of the runtime bundle itself):
the department's agent files and primers under `~/.claude/agents/` and `~/.claude/knowledge/`, and
any model-tier sanction the orchestrator needs recorded in the runtime's own model-policy files.

## Background: why this shape (spike history)

The launchd-plus-headless-session mechanism this whole system is built on was proven, not assumed,
through a phased spike before any job was written:

- A headless session correctly resolves its plist's working directory and its git context.
- The `Agent` tool (sub-agent dispatch) works headless.
- Headless auth for external CLIs (a git host CLI, a cloud CLI) is inherited from the environment.
- Headless, any path under a directory named `.claude` is a sensitive file: the Write tool,
  redirects, `cp`, `mkdir` and `rm` are refused there even when granted. Two exceptions: the CLI's
  own auto-memory dir (`~/.claude/projects/<cwd-slug>/memory/`) takes Write-tool and redirect
  writes with no grant at all, and only a `//` Edit/Write deny stopped that; and a Bash heredoc the
  analyzer bails on succeeds in repos with a bare `Bash` allow (CSA), even past `//` Edit/Write
  denies, and never in Agency. The wheel writes through `hooks/wheel_sink.py`, and its whole-tree
  `~/.claude/**` deny is what closes the auto-memory dir for it. The other jobs still rely on the
  heredoc gap until F7 (#5913); see `knowledge/oversight_install.md` §1.
- A `PreToolUse` hook dispatcher (the runtime's git-safety guard) runs correctly headless and denies
  branch operations exactly as it would interactively — proving the safety gates are not silently
  bypassed just because no human is present to approve anything.
- A local desktop notification tool is callable headless, but actual delivery is not guaranteed (it
  can self-suppress when the user is already active) — every job's own escalation path needs a
  fallback (e.g. commenting on a tracking issue) for when a direct notification doesn't land.
- A worktree-isolated sub-agent, given the correct `worktree.baseRef: "head"` setting, honors that
  base ref and runs headless with no unexpected permission denials — proving isolated builds are a
  safe headless pattern once that one setting is correct.
- A pure in-session reminder mechanism (session-scoped, in-memory, expires with the session) is
  disqualified as a standing scheduling mechanism for exactly that reason — it is fine for one-off
  reminders inside a session, never for anything meant to survive past it. All standing triggers are
  therefore OS-level scheduling (e.g. launchd on macOS), never an in-session timer.

History: this spike also recorded a "permission precondition": that headless writes outside the
session's working directory work once the working repo's local settings grant Bash and Write
broadly. Re-measurement retired it (GH #4767, 2026-09-24): no settings grant makes the Write
tool, a plain redirect, `cp`, `mkdir` or `rm` work on a path under a `.claude` directory. The
exceptions are a heredoc the analyzer bails on under a bare `Bash` allow (CSA), which also gets
past `//` Edit/Write denies, and the CLI's own auto-memory dir, which needs no grant at all. The
current model, including at least the two commands the sensitive-file rule is MEASURED not to
cover (`python3` and `tee` — never asserted complete; other candidate forms are stated as
UNVERIFIED, not closed, N6) and the write channel an installed job uses instead, is
**PERMISSION MODEL OF A HEADLESS JOB** in `knowledge/oversight_install.md` §1.
