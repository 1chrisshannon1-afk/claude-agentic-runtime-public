# agentic-systems-architect

`agentic-systems-architect` audits how agentic systems THEMSELVES are designed — this runtime's own
agents, hooks, and knowledge surfaces, and, where a repo dossier grounds it, the agentic systems
built inside a product (`agents/agentic-systems-architect.md:10-13`). It exists as a standing role
because nothing else in the roster looks at the AGENT LAYER as architecture: whether a task loop is
sized right, whether a review/consensus layer earns its cost, whether a knowledge surface has any
actual reader, whether a gate fails open on the exact case it exists to catch. It also carries two
deeper, doctrine-grounded duties beyond after-the-fact critique: feedback-loop and delivery-flow
design (naming the specific mechanism — gain, latency, batch size, stop condition — to change in a
loop, grounded in control theory, Lean/TPS, and DORA), and agentic software-factory design
(delivering a NAMED target pipeline for a new class of repeatable agent work, grounded in real
precedent).

## Model & tools

- **Model:** `opus` (`agents/agentic-systems-architect.md:4`) — one of the runtime's sanctioned-Opus
  agents (CLAUDE.md §10/§13). Judging decomposition, verification economics, and telemetry honesty
  across the whole agent layer, and producing grounded redesign proposals, is genuine architectural
  synthesis, not a mechanical check.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/agentic-systems-architect.md:5`) — read-only. It never
  writes a cycle telemetry record for itself or any system it audits; it consumes
  `~/.claude/telemetry/cycles/` read-only when present.

## Cadence / trigger

**No scheduled job is currently loaded.** A plist, `com.oversight.csa.agentarch.plist` (monthly, day
8 of the month at 06:10), **is committed and tracked** — landed in commit `2fa882d` ("chore(schedules):
land the orphaned agentic-systems-architect scheduled job"); verify with `git ls-files
schedules/com.oversight.csa.agentarch.plist` — but is **NOT LOADED**, confirmed by `launchctl list |
grep oversight` (seven `com.oversight.csa.*` labels — daily, testarch, steward, productqa, loop,
trustarch, launchdir — no `agentarch`, re-derived 2026-08-31). Loading it is a pending explicit
operator action. This matches CLAUDE.md §13's own statement that agentic-systems-architect "has no
scheduled job yet ... and runs by explicit dispatch." Until the plist is loaded, it runs ONLY
on-demand.

**Scope cap.** A monthly audit is not unbounded: when the full in-scope file set (`agents/`,
`hooks/`, `knowledge/`, plus every audited repo's dossier) exceeds roughly 150 files in one run, it
rotates to ONE of three named axis GROUPS that PARTITION all eleven axes — Group A: axes 1+2+9+10
(unit size/convergence, verification/consensus/context economics, feedback-loop & delivery-flow
design, agentic software-factory design); Group B: axes 3+5+8 (grounding quality, telemetry truth,
cycle telemetry & empirical calibration); Group C: axes 4+6+7+11 (gate friction, in-app agent
design, platform-capability drift, pattern fit and selection) — applied across the full file set
that run, instead of shallow-sampling all eleven axes. It states which GROUP rotated in and which
are deferred in its own COVERAGE line, and closes the full three-group rotation — all eleven axes —
within three consecutive monthly runs, one GROUP per capped run. An on-demand consult scoped to a
named system or an axis 9/10 design request is never subject to this cap
(`agents/agentic-systems-architect.md` § "Report shape", item 6, "Scope cap").

## What it audits / judges

Its primer (`knowledge/agentic_systems_architect_primer.md`) grounds it in start-simple doctrine,
grounded-vs-ungrounded feedback, consensus/verification economics (a standing voting/debate layer
found without a stated structural reason is reported with its real cost — 3-40x base — not presumed
a band-aid outright), adaptive decomposition (a plateau is the split signal, never a numeric cap),
fact-store failure modes, and — its two newest axes — feedback-loop/delivery-flow doctrine (control
theory's gain/oscillation and loop latency, OODA, jidoka/andon's real-stop-condition test, Theory of
Constraints, DORA's Four Keys, Goodhart's Law, applied to both machine loops and the operator's own
edit→verify→commit working loop) and agentic software-factory design (Anthropic's three-scenario
start-simple test, filesystem vs. SDK-level context isolation priced, gate placement before the
hard-to-reverse step, grounded in Stripe's published "Minions" pipeline and this runtime's own
nightly finishing-loop), and pattern fit/selection (primer §15's twenty-pattern catalog, each
pattern evidence-graded — for every pattern PRESENT in a design under audit, judge fit against
that grade; Read-FIRST #7 carries the caveats for its underlying sources 36–63,
`knowledge/agentic_patterns_evidence_2026_08_30.md`). Eleven review axes total, each finding
naming its axis (`agents/agentic-systems-architect.md` § "Axes (each finding names its axis)"): unit size/convergence;
verification/consensus/context economics (cost judged in real MONEY via four token fields, never
token headcount); grounding quality (does every knowledge surface have both a source AND a
reader — a surface nobody reads is dead weight); gate friction in BOTH directions (false positives
AND the false-negative half — a gate that lets through exactly what it exists to catch); telemetry
truth; in-app agent design (dossier-scoped); platform-capability drift (what Claude Code now does
natively that was hand-built here); cycle telemetry and empirical calibration; feedback-loop and
delivery-flow design; agentic software-factory design; and pattern fit and selection (axis 11,
§15's five fenced rows are audit-the-mechanism only, never perform-the-activity). It also owns and
re-scores a standing recommendation ledger
(`knowledge/agentarch_recommendations.jsonl`) every run against each entry's own stated
`metric_command` — never re-derived by memory — under a strict, mechanically-guarded command-safety
allowlist before ever running a stored command. **The re-score is script-first, not hand-derived:**
`python3 ~/.claude/hooks/validate_agentarch_ledger.py` is the authoritative mechanical ENFORCER of
that whole guard (the agent file's own guard description remains the SPEC — a divergence between
the two is a defect in the script, never a redefinition of the guard); it runs form/arity
classification, the hardcoded-repo-path scan, path-bounds enforcement, AND a live re-run of every
row whose `checked_at`/`checked_value` are BOTH non-null (any status, not only `open`), reporting
only an ADVERSE divergence as `checked-value-mismatch` — a regression against `target_direction`
vs. the stored `checked_value`, or a fall-back past `baseline_value` (a non-comparable stored value
falls back to plain inequality); an improvement IN the target direction is silently accepted and
never printed, so validator silence is never evidence a row's metric is unchanged — **this is a
divergence CHECK, not the re-score table**: it prints no current value for a clean row, so the
Report shape's ledger re-score table is still built by running each `open` row's own
`metric_command`. It is run and treated as the primary
verdict before the agent's own hand-derivable rules are applied as a fallback/cross-check; if the
script is missing, unreadable, or reports `validator-crashed:`/`ledger-unreadable:`, the mechanical
guard is DEGRADED and the hand-derivable rules apply in full instead
(`agents/agentic-systems-architect.md` § "Read FIRST", item 4, "Run the guard mechanically before
applying it by hand").

## Grounding

Runtime discipline: `knowledge/agentic_systems_architect_primer.md`, plus a dedicated evidence/
citation file, `knowledge/agentic_systems_evidence_2026_08_25.md`, holding full bibliographic detail
and caveats for its cited sources. Repo-local grounding: `.claude/oversight/agentic-systems-
architect.md` — this app's in-app agentic-system inventory (agents, prompts, orchestration points).
Missing dossier declares that repo's IN-APP scope DEGRADED specifically — the runtime-level audit
(this machine's own `agents/`, `hooks/`, `CLAUDE.md`) still runs in full regardless
(`agents/agentic-systems-architect.md:53`). ExampleApp carries this dossier (confirmed
present, 2026-08-30).

## Boundaries — what it will NOT do

Never edits; never dispatches other sub-agents (it judges, it does not orchestrate); never writes a
cycle telemetry record; never pushes/PR/merges/deploys; never production. A feedback-loop redesign
or factory target design is a BLUEPRINT reported to the orchestrator, never implemented or wired by
this agent itself, and acting on one still goes through the normal plan-review boundary. It never
re-litigates the primer's own standing-decisions list, and it never ranks other work against the
app's one goal — that is launch-director's lane, not this agent's
(`agents/agentic-systems-architect.md` § "Boundaries", final sentence).

## How it fits with other oversight agents / the review boundary

Its cost/consensus axis directly informed trust-architect's own agentic-security assignment
(2026-08-27) — the "consolidation review" that found agentic-system security unowned across the
roster. Several axes share a gate with a named sibling but produce a DIFFERENT verdict, always
cross-referenced rather than duplicated: dead telemetry judged as test/log sufficiency is
test-architect's; the same counter judged as "is any reader wired to it at all" is this agent's —
now declared reciprocally in both agents' own Boundaries sections, not only here
(`agents/agentic-systems-architect.md`, final paragraph after § "Boundaries",
`agents/test-architect.md`, Boundaries). An
agent/gate judged as security CONTROL is trust-architect's; the same gate judged as DESIGN (wired,
grounded, converging) is this agent's.
This is the agent that most recently reviewed the roster-relocation project (moving product-domain
specialists into `~/.claude/agents/`) as a permission-scope change.

## Example invocation

An on-demand consult is requested before adding a third automated review pass to an already-
two-stage pipeline. agentic-systems-architect applies Theory of Constraints first (axis 9): is the
existing review step actually the system's current bottleneck, or would a third layer sit at a
non-bottleneck and just pile up WIP? It also checks the proposal against CLAUDE.md §10's own
standing decision that reviews happen at exactly two boundaries — finding that this specific
"add a third pass" argument is precisely the kind of first-principles re-derivation the standing
decision already forbids, and reports the proposal dropped rather than recommended.
