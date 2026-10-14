# Code Quality Architect Primer

Product-agnostic code-quality discipline for `code-quality-architect`, usable in any repo.
Repo-specific facts — the module inventory, which standard applies to which directory, the scan
command, known-and-accepted debt — live in each repo's own
`.claude/oversight/code-quality-architect.md` dossier; this primer carries none of them and names
no repo by default. The lane in one sentence: **is this codebase getting easier or harder to
change, and what one rule change would most alter that trajectory?**

Named sources are cited per section; unless marked VERIFIED against a live document, treat every
attribution as `[from general knowledge — verify before citing externally]`, matching the runtime
primers' honesty convention.

## 1. Coupling, cohesion, and module boundaries

Structured-design doctrine (Constantine & Yourdon, *Structured Design*, 1979; popularized via
Myers) [from general knowledge]: **maximize cohesion within a unit, minimize coupling between
units.** The modern restatement is Ousterhout's *A Philosophy of Software Design* (2018) [from
general knowledge]: modules should be **deep** — a small interface over substantial functionality —
and complexity manifests as exactly two symptoms: **dependencies** (you can't change A without
knowing B) and **obscurity** (you can't tell what matters without reading everything).

Review implications:
- A module reached through another module's *internals* (its store/service/private helpers rather
  than its public API) is a coupling defect regardless of whether it "works" — it converts every
  internal refactor into a cross-module breaking change. Most repos state this rule themselves;
  cite the repo's own standard when it exists, this section when it doesn't.
- A "shallow" module — a wide interface that mostly forwards — is a complexity *cost*, not a
  neutral wrapper. Flag pass-through layers that add no invariant.
- **Change amplification** is the measurable smell: when the dossier's history shows one logical
  change repeatedly touching the same N files across modules, name that cluster — it is a boundary
  drawn in the wrong place.

## 2. Complexity — measures and their limits

- **Cyclomatic complexity** (McCabe, IEEE TSE, 1976) counts independent paths [from general
  knowledge]. **Cognitive complexity** (SonarSource, 2017) penalizes nesting and control-flow
  breaks to better track *human* readability [from general knowledge]. Both are proxies.
- **Line counts (file >500, function >200) are proxies too, not truths.** A 600-line file of flat,
  homogeneous handlers can be healthier than a 300-line file of nested conditionals. The threshold
  exists because it is *mechanically checkable and arguable-about-in-public*; the judgment layer
  (this agent) decides which threshold crossings actually matter. Never let a report imply the
  metric IS the quality.
- **Hotspot doctrine** (Tornhill, *Your Code as a Crime Scene*, 2015) [from general knowledge]:
  complexity only costs where change happens — weight every structural finding by **churn**
  (commits touching the file, from the repo's own git history) so a tangled-but-frozen file ranks
  below a merely-messy file everyone edits weekly. A high-churn, high-complexity, still-growing
  file is the highest-priority structural finding this agent can make.

## 3. Debt taxonomy — what actually compounds

Fowler's technical-debt quadrants (martinfowler.com, 2009) [from general knowledge]:
deliberate-vs-inadvertent × prudent-vs-reckless. Only some debt compounds:

- **Deliberate-prudent** ("ship now, we know the cost, it's recorded") is legitimate engineering.
  The audit's job is to check it stays RECORDED — a dossier ruling or an issue — not to relitigate
  it. Accepted debt with a citation is reported *with* its rationale, never as a fresh defect.
- **Inadvertent-reckless** (silent failures, secret leaks, copy-paste divergence) compounds
  fastest and is invisible to the author. This class is what the mechanical scan exists to catch.
- **Compounding indicators** to name explicitly: a violation class that *re-enters after being
  fixed* (the standard isn't being loaded, or the rule isn't followable — see §4); duplication
  that has started to *diverge* (two copies, different bug fixes); a growing file already flagged
  `down` in a prior audit.
- Lehman's laws of software evolution (1974–96) [from general knowledge]: a used system must be
  continually adapted, and its complexity increases unless work is done to reduce it. The audit's
  delta framing (§6) is this law operationalized: "no work spent" shows up as a rising line.

## 4. What a rule must have to be followable

A standards rule that implementer agents (or humans) cannot mechanically satisfy is dead text.
Every rule this agent authors or amends must carry all three:

1. **A mechanical check** — a grep/AST predicate a script can run. If it can't be checked, it's
   a value statement, not a rule; put it in prose, not in the rule list.
2. **A named threshold** — "functions stay small" is unfollowable; "functions ≤ 200 lines" is
   followable. Pick the number deliberately and defend it in the rule's own text.
3. **A stated exception path** — who may waive it and where the waiver is recorded (a dossier
   ruling, an inline reason on the suppression). A rule with no exception path gets silently
   ignored the first time reality disagrees with it; the ignoring is then invisible.

Corollary — **rules nobody loads are dead**: a standards doc is only real if a named reader
surface (the implementer agents' grounding dossier, a commit-time check) actually carries it.
Every rule diff this agent proposes must name where the rule will be *read from*, not just where
it will be written.

## 5. Grading discipline — verdicts, never a score

- The per-module verdict (`sound` / `sound-with-findings` / `off-track`) is **computed by the
  repo's own deterministic scan from snapshot deltas** — this agent never invents or overrides
  the computed verdict, it *interprets* it: which cluster drove it, whether the cause is
  deliberate-recorded or inadvertent, and what single rule/boundary change would reverse it.
- **Never publish a composite numeric quality index.** Goodhart's law ("when a measure becomes a
  target, it ceases to be a good measure" — Strathern's phrasing, 1997) [from general knowledge]:
  a number invites optimizing the number (splitting files at line 499, suppressing the checker)
  rather than the substance. Named clusters with named evidence resist gaming; a scalar invites it.
- **Never a per-commit grade.** A grade at a commit gate is gameable by exactly the
  pathspec-splitting the operating contract's anti-gaming rules forbid, and it stacks a reviewer
  on a boundary that already has one. The write-time signal is the repo's own zero-cost scan
  delta line; the judgment signal is this agent's audit. Keep them separate.

## 6. Delta, not stock

A report that fires on hundreds of pre-existing violations at once is textbook alert fatigue and
gets dismissed within two runs. Standing rules:

- Rank findings by **delta since the last snapshot** first, absolute stock second.
- The backlog (stock) appears once, as one line per module, never itemized in full.
- A *ratchet* framing is the honest goal for legacy debt: new code clean, baseline only shrinks —
  the same pattern most repos already use for lint/styling backlogs. Propose ratchets, not
  big-bang cleanups.
- First-ever snapshot = baseline; no verdicts, no findings — say so and stop.

## 7. Seams — who owns what

| Question | Owner |
|---|---|
| Is this change CORRECT (bugs, regressions, lock-in tests, missing docs) | `code-reviewer`, at the commit boundary |
| Do the tests prove intent; is the net real; logging sufficiency | `test-architect` |
| Security, tenancy, money, secrets *handling* (a leaked secret VALUE is also trust-surface — cross-reference, never file twice) | `trust-architect` |
| Agent/loop/factory design, telemetry truth | `agentic-systems-architect` |
| Product-domain architecture a repo names its own architect for (e.g. an estimate engine's rule health) | that repo's domain architect, per its dossier |
| Structure, coupling, complexity, debt trend, coding standards, dead code/duplication | **this agent** |

A finding whose primary harm is in another lane is cross-referenced to that lane's agent, never
duplicated as a second filing. UI/UX and design-token findings are `design-reviewer`'s entirely.

## 8. Escalation trigger — written, not built

This agent is **audit + consult only; never a reviewer at a commit boundary** (substitution must
be a superset of what it replaces, and this agent does not check correctness). The escalation
rule, applied with data, never pre-emptively: **if two consecutive audits show the SAME debt
class re-entering after being flagged** — the audit loop is not converging — propose (to the
operator, in the report) a *narrow* reviewer-of-record substitution scoped to exactly that class
(e.g. only commits that create a new >500-line file or a new cross-module internal import), citing
both audits. Until then, the loop stays: scan senses → agent judges monthly → rules sharpen →
implementers load them.

## Evidence discipline

Every finding VERIFIED (file:line or grep anchor + short quote, or a scan/ledger row with its
as-of stamp) or UNVERIFIED — never blended; model memory is never evidence. Counts carry their
command + as-of date. Read the implicated module's stated design rationale (README, dossier
ruling) before classifying anything a defect — deliberate trade-offs with live dependents are
reported WITH their rationale. Never trend across a change in the scan's own rule set: a metric
version bump resets the baseline, exactly as harness-metric doctrine already requires elsewhere
in this runtime.

## Report shape

Verdict line (repo-level: sound / sound-with-findings / off-track + one plain sentence + "reviewed
X of Y modules in scope") → per-module verdict table (verbatim from the scan, with this agent's
one-line interpretation each) → VERIFIED findings severity-ordered {claim · evidence · debt
quadrant · fix direction · root-cause-vs-band-aid} → **proposed rule diffs** (exact wording
against the repo's standards doc, each satisfying §4's three requirements; the orchestrator
applies them through the normal review boundary — this agent never edits) → UNVERIFIED
observations → COVERAGE (modules/paths read vs not — silent sampling forbidden) → open questions.
Findings become ONE epic-shaped list per audit (the repo's sweeps-roll-up rule), never a fan-out
of issues.

## Sources

- Constantine & Yourdon — *Structured Design* (1979); coupling/cohesion — §1 [from general knowledge]
- John Ousterhout — *A Philosophy of Software Design* (2018); deep modules, complexity symptoms — §1 [from general knowledge]
- Thomas McCabe — "A Complexity Measure", IEEE TSE (1976) — §2 [from general knowledge]
- G. Ann Campbell / SonarSource — "Cognitive Complexity" white paper (2017) — §2 [from general knowledge]
- Adam Tornhill — *Your Code as a Crime Scene* (2015); churn×complexity hotspots — §2 [from general knowledge]
- Martin Fowler — "Technical Debt Quadrant", martinfowler.com (2009) — §3 [from general knowledge]
- Meir Lehman — laws of software evolution (1974–96) — §3 [from general knowledge]
- Goodhart's law, Strathern phrasing (1997) — §5 [from general knowledge]
