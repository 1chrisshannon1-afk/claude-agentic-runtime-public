# code-quality-architect

`code-quality-architect` answers one question about a codebase: "is this getting easier or harder
to change, and what one rule change would most alter that trajectory?" — structure, coupling,
complexity, debt trend, and the coding standards themselves, judged as architecture, never as
individual diffs (`agents/code-quality-architect.md:10-13`). It is the ninth and newest seat on the
oversight roster (added 2026-08-30). It exists as a standing role, distinct from code-reviewer,
because per-commit correctness review structurally cannot see a slow architectural trend — a
codebase can pass every individual commit review and still be quietly getting harder to change,
one small acceptable-looking diff at a time.

## Model & tools

- **Model:** `opus` (`agents/code-quality-architect.md:4`) — one of the runtime's sanctioned-Opus
  agents (CLAUDE.md §10/§13, same cost shape as test-architect/trust-architect/
  agentic-systems-architect). Interpreting a deterministic scan's deltas into a debt-trend verdict,
  and authoring followable rule diffs against the repo's own standards doc, is genuine judgment —
  not the scan itself, which the agent explicitly never computes or overrides.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/code-quality-architect.md:5`) — effectively
  read-only, with **one narrow sanctioned write**: it never edits repo source, docs, or the
  standards doc, and the single exception is creating the debt sensor's append-only ledger by
  taking its FIRST snapshot when the scanner exists and the ledger holds zero records (see
  Boundaries below). It never commits even that file itself, and it never runs a scan while
  another agent holds its shared artifacts.

## Cadence / trigger

**No scheduled job exists yet — dispatch-only, by design.** No `com.oversight.csa.*` plist for
code-quality was found under `~/.claude/schedules/` (confirmed 2026-08-30), matching CLAUDE.md §13's
explicit statement that a schedule for this agent "is deliberately deferred until ≥2 audits show it
is worth automating" — unlike `agentic-systems-architect`, whose plist is authored and committed
(`2fa882d`) but not yet `launchctl` loaded, code-quality-architect has no plist artifact at all yet.
In ExampleApp it
is invoked via the `/code-quality-audit` slash-command entry point named in this repo's own
CLAUDE.md, which also names its dossier (`.claude/oversight/code-quality-architect.md`) and its
deterministic sensor (`repo_tooling/code_debt/scan.py`).

## What it audits / judges

Its primer (`knowledge/code_quality_architect_primer.md`) grounds it in structured-design doctrine
(Constantine & Yourdon's cohesion/coupling; Ousterhout's "deep modules" — a small interface over
substantial functionality, with complexity manifesting as exactly two symptoms: dependencies and
obscurity); complexity measures and their limits (cyclomatic and cognitive complexity as proxies,
never truths; Tornhill's hotspot doctrine — complexity only costs where change happens, so every
structural finding is weighted by git churn, making a high-churn/high-complexity/still-growing file
its highest-priority class); Fowler's technical-debt quadrants (only inadvertent-reckless debt
compounds fast and invisibly; deliberate-prudent debt is legitimate as long as it stays RECORDED,
never re-filed as a fresh defect); and what makes a standards rule actually followable (a mechanical
check, a named threshold, and a stated exception path — a rule missing any of the three is dead
text). Separately — stated in the agent file itself (`agents/code-quality-architect.md`, Grading
discipline) and not yet reflected in the primer, a known gap — the grading discipline that most
sharply distinguishes it from every other reviewer in the roster: per-module verdicts are **five
values, not three** — `sound`/`sound-with-findings`/`off-track` from a real delta, plus `baseline`
(a module with no matching entry in the previous snapshot) and `removed` (present previously, absent
now) — and they come VERBATIM from the repo's own deterministic scan; this agent interprets them, it
never computes, invents, or overrides them, and it never publishes a composite numeric score
(Goodhart) or a per-commit grade (gameable by pathspec-splitting, and it would stack a reviewer on a
boundary — code-reviewer's — that already has one). Six review axes: boundaries (cross-module internal-API reach, pass-through layers, change-
amplification clusters); complexity-where-it-churns; debt trend (a flagged class RE-ENTERING after a
fix is its own named finding — the loop isn't converging); standards health (is every rule
followable, and actually LOADED by a named reader surface, or dead text); duplication drift (copies
that have started to diverge); and dead weight (`agents/code-quality-architect.md`, Review axes,
axis 6). It ranks
findings by DELTA since the last snapshot first, absolute stock second — a report that fires on
hundreds of pre-existing violations at once is alert fatigue and gets dismissed within two runs. A
single snapshot is baseline only: no verdicts, no trend claims, stated explicitly rather than
inventing a direction.

## Grounding

Runtime discipline: `knowledge/code_quality_architect_primer.md`. Repo-local grounding:
`.claude/oversight/code-quality-architect.md` — the repo's module inventory and intended
boundaries, which standard sections apply to which directories, the debt-scan invocation command and
ledger path, and known-and-accepted debt with its rulings. Missing dossier is declared DEGRADED,
restricted to repo-discoverable state only (`agents/code-quality-architect.md`, Read FIRST item 2).
ExampleApp carries this dossier (confirmed present, 2026-08-30). Read FIRST also names an
own-prior-audit-record step (mirroring test-architect/trust-architect) — reached via Bash against
`~/.claude/schedules/logs/` and `~/.claude/schedules/heartbeats/`, never `Glob` from a dispatched
job's cwd — and is explicit that, until a scheduled job exists for this agent, the session
dispatching a follow-up audit must supply the prior audit's findings inline in the dispatch prompt
for the Escalation trigger's "two consecutive monthly audits" clause to be evaluable at all.

## Sensor degraded modes and grading vocabulary

Read FIRST distinguishes three sensor states — absent scanner, a scanner file present but whose
invocation FAILED (quote the verbatim interpreter error + exit code, declare the sensor
UNAVAILABLE, audit by hand — including a documented bare-`python`-vs-`python3` PATH landmine seen
in a scheduled job elsewhere in the roster), and a successfully-invoked scanner whose ledger is
itself in one of three states (no snapshots yet / exactly one snapshot / two-or-more snapshots,
i.e. `no_snapshots` / `baseline_only` / `ranked` in the scan's own vocabulary) — and it never
collapses these into each other. Per-module verdicts are **five values, not three**: `sound` /
`sound-with-findings` / `off-track` from a real delta, plus `baseline` (a module with no matching
entry in the previous snapshot — newly discovered, which can occur inside an otherwise-ranked
report, not only on the whole-ledger first snapshot) and `removed` (present previously, absent
now). Because the ledger carries no rule-set version field, the file names an interim manual
proxy — diff the per-module metrics dict's key-set between the last two records — for the "never
trend across a rule-set change" instruction to stay followable until that schema gap closes.

## Boundaries — what it will NOT do

Never edits repo source, docs, or the standards doc — rule diffs are emitted in its report and
applied by the orchestrator through the normal plan/code-review boundary. **One narrow, explicit
carve-out, mirroring test-architect's sanctioned first-snapshot write:** when the scanner exists
and the ledger holds zero records, taking that ONE bootstrap snapshot is this agent's sanctioned
write — one new ledger line, nothing else, never a second snapshot in the same pass, never
committed by the agent itself. Never a standing commit gate, never a reviewer at a commit
boundary — its own cadence rule states explicitly that substituting it there would LOSE the
correctness coverage that gate exists for (`agents/code-quality-architect.md`, Cadence rule). Never
pushes/PR/merges/deploys; never production; never runs a scan while another agent holds its shared
artifacts. Every finding is VERIFIED (file:line or grep anchor + short quote, or a scan/ledger row
with its as-of stamp) or UNVERIFIED — never blended.

## How it fits with other oversight agents / the review boundary

Its own seams table is explicit (`agents/code-quality-architect.md`, Boundaries — Seams): correctness at the
commit boundary is code-reviewer's; tests/observability is test-architect's; security/tenancy/money
is trust-architect's (a leaked secret VALUE is theirs — this agent's lane is only the hygiene
pattern, cross-referenced, never filed twice); agent-system design is agentic-systems-architect's;
product-domain architecture belongs to the repo's own domain architect where one is named; UI/UX and
design tokens are design-reviewer's entirely. It carries its own written-but-not-yet-built escalation
trigger, mirroring trust-architect's split-trigger pattern: if the SAME debt class re-enters after
being flagged across two consecutive monthly audits, it proposes — never enacts — a narrow
reviewer-of-record substitution scoped to exactly that class.

## Example invocation

A monthly audit (or an on-demand `/code-quality-audit` run) compares the current debt-scan snapshot
against the prior one and finds that a module already flagged `sound-with-findings` last time for a
cross-module internal-API reach has grown two more such reaches since. code-quality-architect names
this a debt-trend finding (axis 3, re-entering-after-flagged class), traces it to a missing boundary
rule in the repo's standards doc, and proposes an exact rule diff — a grep-checkable "no importing
from another module's `_internal/` package" rule with a named exception path — rather than a vague
"reduce coupling" recommendation.
