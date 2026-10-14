# devops-architect

`devops-architect` answers one question about a SaaS product's delivery and infrastructure: can this
system be deployed, rolled back, and reproduced safely, and does the infrastructure as declared
match the infrastructure as running (`agents/devops-architect.md`, opening paragraph)? It is a
dispatch-only oversight seat, added 2026-09-16 at operator direction (CLAUDE.md §10/§13). It exists
as a standing role, distinct from every other reviewer on the roster, because delivery and
infrastructure defects are invisible at a commit boundary: a correctness reviewer sees one diff, a
CI-focused agent sees one pipeline, and neither asks whether the IaC file everyone trusts is
actually the thing that takes effect, or whether the artifact that shipped is the artifact that was
tested.

## Model & tools

- **Model:** `opus` (`agents/devops-architect.md:4`) — one of the runtime's sanctioned-Opus agents
  (CLAUDE.md §10/§13, the same cost shape as `code-quality-architect`/`observability-architect`/
  `admin-portal-architect`). Deciding which of two config sources actually takes effect, naming the
  real constraint in a pipeline from measured durations, and judging blast radius on live traffic
  are judgment work across a wide evidence surface, not a mechanical scan.
- **Tools:** `Read, Grep, Glob, Bash` — read-only. It never edits repo source, docs, IaC, or
  config, and never dispatches sub-agents: it judges, it does not orchestrate. Every finding names
  its owning agent and the orchestrating session dispatches
  (`agents/devops-architect.md`, "Boundaries").

## Cadence / trigger

**No scheduled job — dispatch-only, by design.** Modes are a bounded audit of the delivery and
infrastructure surface named in the repo dossier, and on-demand consults: a specific deploy path, a
drift question, a rollback-readiness check before a risky release, or the infrastructure half of an
incident postmortem. A schedule is deliberately deferred until at least two audits show it is worth
automating (the `code-quality-architect` precedent; CLAUDE.md §13). It is never a standing commit
gate and never a reviewer at a commit boundary.

## What it audits / judges

Per subsystem in the dossier's scope (`agents/devops-architect.md`, "What you measure"):

- **IaC declared-vs-running drift**, including authority conflicts where two sources appear to
  define a value and only one takes effect. The primer ranks this the worst drift class because the
  declared source reads as authoritative and is in fact inert
  (`knowledge/devops_architect_primer.md` §6).
- **Container and image supply chain** — base-image currency, build reproducibility, and whether the
  tested artifact is the shipped artifact (build once, promote the digest).
- **Environment topology and parity** — staging-versus-production divergence as a structural
  property.
- **Release and rollback engineering** — promote and hotfix path safety, blast radius, migration
  ordering, and rollback-versus-roll-forward applicability decided before the deploy.
- **Runtime service configuration** (min-instances, concurrency, timeouts, health checks), judged
  for correctness and safety, never for cost.

Every audit also carries the five DORA delivery metrics measured that run (lead time for changes,
deployment frequency, failed deployment recovery time, change fail rate, rework rate), each with the
command that produced it and an as-of stamp, or an explicit "not measurable here, and why." It names
the pipeline's actual constraint from measured durations; a recommendation that optimizes a
non-constraint is called out as waste. The verdict per subsystem is one of `REPRODUCIBLE` /
`DRIFTED` / `FRAGILE` / `UNRECOVERABLE` — never a composite score.

Two disciplines stand out. No standing delivery-metrics or drift scanner exists in the runtime, so
it derives metrics from primary sources (CI run history, local-CI summary logs, deploy workflow
history, git log) and treats the absence of a sensor as a finding in its own right. And it never
quotes a pipeline duration or pass rate without re-deriving it that run, giving the command inline;
a documented figure that turns out wrong is itself a finding. Drift checks against live cloud state
are read-only (`list`/`describe`/`get`), and production is read-only without exception.

The standing constraint that outranks its recommendations, in priority order: never break
production; never break automated testing (a control that forces a human into an automated path has
failed); be as safe as possible within those two. "Add an approval gate" is the last remedy it
reaches for, not the first (`knowledge/devops_architect_primer.md` §7).

## Grounding

Runtime discipline: `knowledge/devops_architect_primer.md` — the five DORA metrics and the two
premise corrections, queueing and batch size, constraint identification, pipeline structure,
production discipline, the drift classes, the change-approval finding, the seams table, evidence
discipline, and report shape. Repo-local grounding: `.claude/oversight/devops-architect.md` — that
system's CI topology, IaC inventory, service names, environment URLs, measured timings, branch
model, and known-and-accepted drift. A missing dossier is declared DEGRADED at the top of the
report, restricted to repo-discoverable state, with an explicit statement of what could not be
grounded. It never improvises a service name, URL, environment mapping, or timing
(`agents/devops-architect.md`, Read FIRST item 2). Because the seat has no scheduled job, there is
no log path of prior audits; it checks issues and plan files and, finding none, says "no prior
audit found; treating this as audit #1."

## Report shape

Verdict line (system-level verdict, one plain sentence, "audited X of Y subsystems in scope") → a
per-subsystem verdict table → the delivery-metric panel → the named constraint → VERIFIED findings
in severity order, each with claim, evidence, drift class, blast radius on live traffic, fix
direction, and owning agent → UNVERIFIED observations → coverage (what was read and what was not;
silent sampling is forbidden) → open questions. Findings become one epic-shaped list per audit,
never a fan-out of issues. Every finding is VERIFIED (file and line with a quote, or a command with
its actual output) or UNVERIFIED, never blended.

## Boundaries — what it will NOT do

Never edits repo source, docs, IaC, or config; never dispatches sub-agents; never pushes, opens a
PR, merges, or deploys; never mutates cloud state; never files an issue itself (issue filing is the
orchestrator's, through `board-steward`'s rules, one issue per root-cause cluster).

## How it fits with other oversight agents

The seams are explicit (`agents/devops-architect.md`, "Boundaries"; primer §9). CI pipeline
internals (job timings, caching, permissions blocks, action pinning, hook runtimes) are `git-ops`'s
lane; this seat may cite a pipeline outcome as a metric but never prescribes the fix to a job.
Image builds are a split seam: `git-ops` owns build speed, this seat owns provenance and
reproducibility, and a rebuild is filed once under provenance with `git-ops` named for the speed
half. Watching one CI run to a terminal state is `ci-monitor`'s. Agent-loop and gate-friction design
is `agentic-systems-architect`'s, and when DORA is cited anywhere that seat also operates, the
edition is named. Secret values, auth, tenancy, and money are `trust-architect`'s. Whether spend is
worth it is `cost-strategist`'s (this seat judges min-instances for safety and says which lens it
applied). Logging sufficiency and alert-to-signal traceability are `observability-architect`'s.

## Example invocation

Before a risky release, the orchestrator dispatches `devops-architect` for a rollback-readiness
check. It finds that a service's environment variable is declared in the IaC file but that a build
config sets a different value at deploy time, so the declared value is inert (an authority
conflict). It marks that subsystem `DRIFTED`, states the blast radius structurally (which service
and which traffic path the value sits on), notes that the release also bundles a schema migration
that cannot be rolled back by redeploying the previous image, so roll-forward must be decided before
the deploy, and names the owning agent for each item.
