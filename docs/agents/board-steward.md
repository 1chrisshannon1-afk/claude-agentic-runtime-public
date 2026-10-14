# board-steward

`board-steward` is the runtime's issue-tracker truth-keeper: its only job is making the GitHub
issue tracker and project board tell the truth (`agents/board-steward.md:10-12`). It exists as a
standing role because a tracker's drift is invisible day-to-day and only compounds — duplicates
pile up, stale items sit un-dispositioned, priority fields go stale — and every other oversight
agent (and the operator) depends on the board being trustworthy to know what's actually open. Its
own framing: "a board nobody trusts is worse than no board."

## Model & tools

- **Model:** `sonnet` (`agents/board-steward.md:4`) — NOT one of the roster's sanctioned-Opus
  agents. Its work is largely mechanical (dedup detection, label/field hygiene, disposition
  proposals against fixed rules) rather than open-ended judgment, so it runs at the cheaper tier
  per the runtime's cost posture (CLAUDE.md §10/§13; cheap models for mechanical work, Opus
  reserved for genuine judgment boundaries).
- **Tools:** `Read, Grep, Glob, Bash` (`agents/board-steward.md:5`) — read-only at the tool-grant
  level; it never touches file contents. Nearly all of its actual issue writes go through one
  sanctioned script, `~/.claude/scripts/gh_issue.sh` (`create`/`comment`/`transition`/`resolve`/
  `dispose`), never a bare `gh issue close` or a raw `gh api` state mutation, plus one further
  sanctioned write outside that script — `gh issue edit --add-label/--remove-label` (since
  `gh_issue.sh` has no label subcommand for an existing issue) — and one sanctioned batch WRAPPER
  around it, `~/.claude/scripts/priority_backfill.py`, for its two narrow batch fixes (backfilling
  an empty Priority field from a priority label; resetting `Ready #1`/`Ready #2` back to
  `Backlog`). The wrapper routes every field SET back through `gh_issue.sh transition`, is dry-run
  by default, requires an explicit `--repo OWNER/NAME`, caps at 40 mutations per `--apply` pass, and
  has exactly one non-helper write of its own: `reverse --log <file>`'s `--clear` path, which
  restores the **Priority** field to empty when undoing a backfill, and is run only against a log
  the script itself produced. **`--apply` is attended-only and limited to the two batches the
  operator approved (card [97], 2026-09-20)**: board-steward applies only when its dispatching brief
  quotes that approval; an unattended/scheduled dispatch (THE ISSUE WHEEL's standing close
  authorization names this script nowhere) runs dry-run only; one `--apply` pass per dispatch, the
  remainder reported as parked; every pass is reported like a `gh_issue.sh` call and counts against
  the sweep cap; a third batch use needs its own operator ruling
  (`agents/board-steward.md` § "Write mechanics (the ONLY sanctioned paths)").

## Cadence / trigger

`com.oversight.csa.steward.plist` (its own twice-weekly sweep) is REMOVED (2026-09-08) — board-
steward is now dispatched nightly by THE ISSUE WHEEL's own P3 CLOSE phase
(`schedules/prompts/issue_wheel.txt`), under a standing close authorization, and remains available
for direct/manual dispatch same as before. Manual fallback when schedules are down is `/sweep`.

## What it audits / judges

Its primer (`knowledge/board_steward_primer.md`) grounds it in issue-tracker hygiene practice:
Pivotal Tracker's "icebox is where stories go to die" failure mode and auto-expiry patterns with a
manual opt-out escape hatch; Linear's zero-bug mechanics (no passive backlog state for a defect —
either actively owned toward a fix or explicitly, visibly won't-fixed); honest won't-fix discipline
(always a stated reason, capacity math shown transparently, and a close that a reporter can trust
is not a silent brush-off); duplicate-detection practice (semantic matching is good enough to
*propose* a merge, not to auto-close on its own); WIP limits; fields-over-labels hygiene; and — most
load-bearing for how it files findings — the one-issue-per-root-cause-cluster rule: a single audit
pass that surfaces many related findings becomes ONE issue with a checklist, never a fan-out of
top-level tickets, unless a finding is independently launch-blocking on its own severity
(`knowledge/board_steward_primer.md:117-131`; the rule itself exists specifically because an
earlier audit process created 71 issues in one day from what was really one review surfacing many
symptoms of the same root cause — that measured incident is recorded in `CLAUDE.md`'s own §8
correction, not the primer, `CLAUDE.md` §8, "Correction (2026-08-03) — a batch of RELATED findings
from one audit/review pass is ONE issue"). Its sweep procedure runs a budgeted
continuity-tracked pass: duplicate
detection, an honesty pass on stale items, a hygiene pass (missing labels, empty priority fields,
orphaned epic children), then an emit with a verdict, executed non-destructive mutations, a
proposed disposition batch, what the budget left unswept, and honesty metrics (open count,
empty-priority share, completed vs. not-planned close ratio) — a cleanup that inverts that ratio is
named as laundering, not celebrated as progress; a FAILED/PARTIAL slot in the same emit lists every
mutation that exited non-zero rather than letting it disappear into the executed count
(`agents/board-steward.md` § "Sweep procedure").

## Grounding

Runtime discipline: `knowledge/board_steward_primer.md`. Repo-local grounding:
`.claude/oversight/board-steward.md` — the repo's label taxonomy, project board number and owner,
field names, and epic conventions. Missing dossier is a declared DEGRADED state, restricted to
read-only analysis only (`agents/board-steward.md:20`). ExampleApp carries this dossier
(confirmed present, 2026-08-30).

## Boundaries — what it will NOT do

The two-tier mutation rule is the core of its boundary discipline
(`agents/board-steward.md` § "The two-tier mutation rule (non-negotiable)"): **autonomous** (no approval needed) covers only non-destructive
mutations — labels, project fields, status transitions, comments, cross-references, and creating a
genuinely new, dedup-checked issue. **Proposed** covers anything destructive or outward-final —
every not-planned close, every duplicate-close, every merge; it emits a structured `Disposition:`
line per item and waits for operator approval, EXCEPT where the dispatching job names a standing
close authorization AND every close passes both `gh_issue.sh`'s guards and gate 5 (THE ISSUE
WHEEL's own P3 CLOSE phase is exactly this exception — see `issue_wheel.txt`'s P3 section). It
never edits repo files,
never pushes/PR/merges/deploys, and never scans git history for triage — backlog grooming reasons
about issue state (labels, fields, comments, linked items), not commit history, which is slow and
unbounded (`knowledge/board_steward_primer.md:151-153`). Every claim is VERIFIED (citation with a
heading or grep-able anchor) or explicitly UNVERIFIED — never blended.

## How it fits with other oversight agents / the review boundary

board-steward owns the filing RULES every other agent's findings ultimately flow through — it is
never a backend those agents call directly. sentinel, consistency-auditor, test-architect,
trust-architect, product-qa, agentic-systems-architect, and code-quality-architect all detect and
report findings but explicitly never file issues themselves — "findings route through the board
steward's filing rules via the orchestrator" appears verbatim (or equivalently) in each of their own
boundary sections. The ORCHESTRATOR is the one that actually files, typically leaving the finding
for board-steward's own next regular sweep to absorb rather than dispatching it mid-run;
board-steward is the one place the one-issue-per-root-cause-cluster rule is actually enforced, which
is what keeps a monthly Opus audit from turning into dozens of noisy top-level tickets — not an
agent every neighbor calls directly.

## Example invocation

sentinel's daily sweep flags three separate stale-heartbeat warnings and consistency-auditor's slot
finds two pricing-doc contradictions in the same run; both route their findings through the
orchestrator per their own boundary rules, never filing directly. When board-steward next runs its
own sweep, it checks for an existing "oversight findings" epic, folds all five into its checklist
via `--related`, and separately proposes closing an 11-month-old icebox item as won't-fix (with the
capacity math stated) for operator approval — never executing that close itself.
