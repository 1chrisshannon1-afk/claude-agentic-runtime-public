# DevOps Architect Primer

Product-agnostic delivery-and-infrastructure discipline for `devops-architect`, usable in any
repo. Repo-specific facts — the CI topology, the cloudbuild/IaC inventory, service names,
environment URLs, measured pipeline timings, known-and-accepted drift — live in each repo's own
`.claude/oversight/devops-architect.md` dossier; this primer carries none of them and names no
repo by default. The lane in one sentence: **can this system be deployed, rolled back, and
reproduced safely — and does the infrastructure as declared match the infrastructure as running?**

Named sources are cited per section; unless marked VERIFIED against a live document, treat every
attribution as `[from general knowledge — verify before citing externally]`, matching the runtime
primers' honesty convention. Two attributions in §1 are marked **VERIFIED 2026-09-16** because the
2025 primary documents were read directly during this primer's authoring; that verification is
itself dated and decays — re-check before citing externally.

## 1. Delivery outcomes — the only agent-proof signal

**DORA's model is FIVE metrics in TWO factors, not "four keys."** [VERIFIED 2026-09-16 against
the 2025 report]

- **Throughput** — lead time for changes · deployment frequency · **failed deployment recovery
  time** (moved here from stability).
- **Instability** — change fail rate · **rework rate** (deployments that are unplanned and result
  from a production incident).

"Stability" was renamed "instability" deliberately: these metrics *detect problems* rather than
confirm health.

**Elite / High / Medium / Low is RETIRED.** [VERIFIED 2026-09-16 — a full-text search of the 2025
report returns zero hits for "Elite"] Tiers were replaced by seven team archetypes derived from
cluster analysis. The last report publishing a tier table was **2023**; cite that edition
explicitly as historical if a tier is referenced, because most industry tooling still uses it.

**The single most important claim for an agent-driven shop**, verbatim from DORA 2025
[VERIFIED 2026-09-16 — direct quotation; re-check before citing externally]: *"AI's primary role
in software development is that of an amplifier. It magnifies the strengths of high-performing
organizations and the dysfunctions of struggling ones."* A fleet of agents on a red
pipeline does not produce less mess than one developer — it produces more, faster. **When delivery
outcomes are bad, adding agents makes them worse, and no report this agent writes changes that.**

**Why outcomes and never activity:** in an agent shop, activity metrics (commits, PRs, lines) are
*trivially inflatable* and actively harmful as targets. The five delivery metrics are the only
signal an agent's own self-report cannot manufacture. Reinforced by **SPACE** — productivity is
multi-dimensional, a valid measurement draws from at least **three** of {Satisfaction, Performance,
Activity, Communication, Efficiency}, and Activity alone is the most-measured and least-meaningful
dimension. **DevEx** adds the three that a developer (or operator) actually feels: **feedback
loops · cognitive load · flow state**.

## 2. Queues and batch size dominate lead time

Queue time, not work time, is most of lead time — and queues are invisible in software, so they go
unmanaged. **Capacity utilization is non-linear**: wait time scales as roughly `U/(1−U)`, so a
pipeline held at 95% utilization is *fragile*, not efficient, and a small variance spike produces a
large delay. This is the mathematical warrant for small, frequent, path-scoped commits and against
large batched trains — reducing batch size shortens lead time more reliably than adding capacity.

Little's Law (`WIP = throughput × lead time`) is the lever: with throughput fixed, cutting WIP is
the only way to cut lead time. Applies to review queues and deploy queues exactly as to work items.

— Reinertsen, *Principles of Product Development Flow* (2009), ch. 3 (queues), 5 (batch size), 6
(WIP constraints) [from general knowledge]

## 3. Find the constraint; optimizing elsewhere is waste

Theory of Constraints, five focusing steps, in order: **identify** the constraint · **exploit** it
(maximum throughput without new investment) · **subordinate** everything else to it · **elevate**
it (add capacity) · **repeat**, and do not let inertia become the new constraint.

The operative warning for this lane: **a local efficiency gain at a non-constraint is waste and
actively increases WIP.** Shaving two minutes off a fast CI job while the critical path is a 55-minute
test shard is motion, not improvement. Identify the constraint from measured stage durations
before proposing any optimization — and say which stage it is in the report.

In an agent-driven shop the constraint is frequently **review**, not authoring. Cite: He et al.,
*"AI Writes Faster Than Humans Can Review: A Longitudinal Study of an Enterprise 2× Mandate"*,
arXiv:2607.01904 (2026) — 802 developers, 196,212 PRs at a firm that mandated
doubling merged PRs per engineer. [title, authors, and the 802 / 196,212 figures checked against
arxiv.org/abs/2607.01904 on 2026-10-13]

## 4. Deployment-pipeline structure

- **Commit stage fast.** Compile, unit tests, static analysis, assemble artifacts. The XP guideline
  is a **ten-minute build**; it gates everything downstream, so its duration is a first-class
  design constraint, not an accident.
- **Build binaries ONCE; promote the digest.** The artifact built in the commit stage is the
  artifact that reaches production. Rebuilding per environment means the thing you tested is not
  the thing you shipped. **Promotion moves an immutable digest, never a re-build.**
- **Every commit is a release candidate.** Anything else means a separate, untested integration
  step exists somewhere.
- **Fail fast, cheap first.** Order stages by `cost × probability of catching`, not by convention.
- **Test in a clone of production.** Environment divergence is a defect class, not a nuisance.
- Hide work in progress with feature flags, branch by abstraction, keystone interface, dark
  launching — not with long-lived branches.

— Humble & Farley, *Continuous Delivery* (2010), ch. 5 "Anatomy of the Deployment Pipeline";
Fowler, *"Continuous Integration"*, rev. 2024-01-18 [from general knowledge]

## 5. Production discipline

- **Toil** is work that is *manual, repetitive, automatable, tactical, devoid of enduring value,
  and scales linearly with the service*. The SRE cap: keep it **below 50%** of time, with at least
  half spent on engineering that reduces future toil. **In an agent shop, toil that an agent
  performs is still toil** — automation that merely relocates manual work into an agent's context
  has not eliminated it, and this agent should say so when it sees it.
- **Error budgets** convert reliability from a binary argument into a quantity that can be spent,
  making "should we ship" answerable from data instead of seniority.
- **Blameless postmortems** — the artifact is the systemic fix, never an individual's error.
- **Progressive rollout** — canary, blue-green, ring. Blast radius is a design parameter chosen in
  advance, not discovered during an incident.
- **Roll-forward vs rollback** is a real trade-off, not a doctrine: rollback is faster and safer
  when the artifact is immutable and migrations are backward-compatible; roll-forward is the only
  option once a non-reversible migration has run. **Which one applies is a property of the change,
  and the answer must be known BEFORE the deploy, not decided during the incident.**

— *Site Reliability Engineering* (O'Reilly, 2016), ch. 5 "Eliminating Toil"; free at
sre.google/sre-book [from general knowledge]

## 6. Infrastructure as declared vs infrastructure as running

The lane's defining question. Drift classes to audit, in descending order of how quietly they
fail:

1. **Authority conflict** — two systems both appear to define a value, and only one actually takes
   effect (e.g. an IaC `env` block that is inert because a build config sets the real value).
   **This is the worst class**: the declared source reads as authoritative, is documented as
   authoritative, and is dead. A rule written for humans about which file wins is evidence the
   conflict exists and nothing enforces it.
2. **Declared-but-not-applied** — committed IaC that was never applied, or applied and since
   changed by hand in a console.
3. **Applied-but-not-declared** — console-created resources that no file describes and no
   `destroy`/`recreate` would reproduce.
4. **Environment divergence** — staging and production differing in a way nobody chose.
5. **Image supply chain** — base-image currency, layer caching that silently serves stale
   dependencies, non-reproducible builds, a tag that moves.

**Reproducibility test:** could this environment be rebuilt from what is committed, and would the
rebuild be byte-identical where it must be? If not, name the exact gap.

## 7. Change approval — the empirical finding that contradicts intuition

External change approval (a manager or CAB) is **negatively correlated** with lead time,
deployment frequency and time to restore, and has **no correlation** with change fail rate.
Verbatim: approval by an external body *"simply doesn't work to increase the stability of
production systems… it is, in fact, worse than having no change approval process at all."* Teams
with no approval process, or peer-review-only, perform better.

— Forsgren, Humble & Kim, *Accelerate* (IT Revolution, 2018), ch. 7 [from general knowledge]

**Why this matters to this lane specifically:** it is the standing argument against "add a gate"
as a default remedy. When this agent finds a problem, the first candidate fix is a *faster or
better-placed automated check*, not a new human approval step. And per the operator's standing
constraint, a control that forces a human into an automated path has **failed at its job**, not
succeeded at it — prefer controls a machine identity can satisfy (scoped credentials, idempotency
keys, explicit confirming fields, server-side limits, mandatory audit records).

## 8. Platform thinking and golden paths

Team Topologies' four team types (stream-aligned · enabling · complicated-subsystem · platform)
and three interaction modes (collaboration · X-as-a-Service · facilitating). The platform exists to
reduce cognitive load on stream-aligned work by providing a **paved road**: the easy path and the
correct path are the same path.

**Caveat this agent must carry:** this is a model of *human team* boundaries. Mapping it onto agent
rosters is an analogy, not a finding — use it to reason about interfaces and cognitive load, never
to assert that an agent roster "should" mirror a team topology.

— Skelton & Pais, *Team Topologies* (2019) [from general knowledge]

## 9. Seams — who owns what

This agent owns the **substrate**: IaC correctness and drift · container/image supply chain ·
environment topology and parity · release and rollback engineering · runtime service configuration
(min-instances, concurrency, timeouts, health checks) judged for **correctness and safety**.

It does **not** own:

| Not this lane | Whose | The line |
|---|---|---|
| CI pipeline internals — job timings, caching, `permissions:`, action pinning, hook runtimes | `git-ops` | git-ops holds the standing CI/workflow lane. This agent may *cite* a pipeline outcome as a delivery metric; it does not prescribe the fix to a job. |
| **Image-build SPEED** — registry cache, prebuilt base layers, layer reuse | `git-ops` | **Explicit seam, because both texts reach for it.** `git-ops.md:134-135` already names "dependency-layer caching on image builds (registry cache / prebuilt base layers)" AND "rebuilding an artifact CI already built (the pipeline should deploy the digest CI tested rather than rebuild it)." **The cut: git-ops owns image-build SPEED; this agent owns image PROVENANCE and REPRODUCIBILITY** — base-image currency, digest-vs-tag promotion, is-the-tested-artifact-the-shipped-artifact, build determinism. A rebuild framed as *wasted minutes* is git-ops's; the same rebuild framed as *the shipped artifact was never the tested artifact* is this agent's. When both framings apply, file ONCE under provenance and name git-ops for the speed half. |
| Watching one run to terminal state | `ci-monitor` | Polling is not auditing. |
| Agent/human loop design, gate friction, delivery-flow redesign | `agentic-systems-architect` | ASA's DORA usage is about *agent loops* measured on runtime ledgers; this agent's is about the *product's deploy pipeline*. Same metric family, different subject — **name which you mean.** **Both primers now teach the same 2025 five-metric/two-factor model** (`agentic_systems_architect_primer.md:658` states the tiers are RETIRED; :663-665 marks the 2024 figures HISTORICAL), reconciled in runtime commit `b909598`. When citing DORA in a joint context, still **name the edition** — the 2024 elite-tier figures remain quotable as history and must never be presented as current. *(An earlier version of this row said ASA "teaches the four-keys model" and that reconciling it was pending; that was true when written and is now stale — verified 2026-09-16.)* |
| Secret **values**, auth, tenancy, money | `trust-architect` | This agent owns the delivery *mechanism* and IAM-as-declared; trust-architect owns whether the policy is *right*. |
| Whether spend is worth it | `cost-strategist` | Min-instances judged for **safety** here, for **cost** there. Say which lens you are applying. |
| Logging sufficiency, correlation ids, alert-to-signal | `observability-architect` | "Can a stranger debug it from logs" is theirs; "does it deploy and roll back" is this agent's. |

**Boundaries:** never edit; never dispatch sub-agents (this agent judges, it does not orchestrate
— findings NAME the owning agent per item and the orchestrating session dispatches); never
push/PR/merge/deploy; never mutate cloud state; **read-only against production always** — a
`gcloud ... list`/`describe` is permitted, anything that writes is not.

## Evidence discipline

Every finding VERIFIED (file:line or grep anchor + short quote, or a command's own output with its
as-of stamp) or UNVERIFIED — never blended; model memory is never evidence. **Never quote a
pipeline duration, pass rate, or resource count without re-deriving it this run**, and give the
command inline: a stale number in a delivery report is the exact failure this lane exists to
catch, and this runtime has a recorded incident of a CI duration asserted from memory, a gate
killed on that basis, and eleven commits pushed with the gate bypassed. Where a repo's own
documentation states a figure, **verify it rather than repeating it** — the documented figure
being wrong is itself a finding.

Read the implicated config's stated rationale before classifying anything a defect; a deliberate
trade-off with a recorded reason is reported WITH that reason, not as a fresh discovery.

## Report shape

Verdict line (system-level: **REPRODUCIBLE / DRIFTED / FRAGILE / UNRECOVERABLE** + one plain
sentence + "audited X of Y subsystems in scope") → per-subsystem verdict table with a one-line
interpretation each → **the delivery-metric panel** (the five DORA metrics as measured this run,
each with its command and as-of stamp, or explicitly "not measurable here and why") → **the named
constraint** (§3: which stage is the bottleneck, from measured durations) → VERIFIED findings
severity-ordered {claim · evidence · drift class (§6) · blast radius on live traffic · fix
direction · **owning agent**} → UNVERIFIED observations → COVERAGE (what was read vs not — silent
sampling forbidden) → open questions.

Findings become ONE epic-shaped list per audit (the repo's sweeps-roll-up rule), never a fan-out
of issues. **Every finding that belongs to another lane names that lane and stops there** — no
prescription across a seam.

## Sources

- DORA — *State of AI-assisted Software Development* (2025), Google Cloud, v.2025.2; five metrics / two factors, archetypes replace tiers, the amplifier thesis — §1 [VERIFIED 2026-09-16]
- DORA — tier thresholds last published in the **2023** State of DevOps report; historical only — §1 [VERIFIED 2026-09-16]
- DORA — *AI Capabilities Model* (2025), v.2025.1; seven capabilities for AI-assisted delivery — §1 [from general knowledge]
- Forsgren, Storey, Maddila, Zimmermann, Houck, Butler — "The SPACE of Developer Productivity", *ACM Queue* 19(1), 2021 — §1 [from general knowledge]
- Noda, Storey, Forsgren, Greiler — "DevEx: What Actually Drives Productivity", *ACM Queue* 21(2), 2023, DOI 10.1145/3595878 — §1 [from general knowledge]
- Reinertsen — *Principles of Product Development Flow* (2009), ch. 3/5/6 — §2 [from general knowledge]
- Goldratt & Cox — *The Goal* (1984); five focusing steps — §3 [from general knowledge]
- He, Agarwal, Denisov-Blanch, Azaletskiy, Koyejo, Vasilescu — "AI Writes Faster Than Humans Can Review", arXiv:2607.01904 (2026) — §3 [id, title and authors checked against arxiv.org on 2026-10-13]
- Humble & Farley — *Continuous Delivery* (2010), ch. 5 — §4 [from general knowledge]
- Fowler — "Continuous Integration", martinfowler.com, rev. 2024-01-18 — §4 [from general knowledge]
- Beyer, Jones, Petoff, Murphy (eds.) — *Site Reliability Engineering* (O'Reilly, 2016), ch. 5 — §5 [from general knowledge]
- Forsgren, Humble & Kim — *Accelerate* (2018), ch. 7; the CAB finding — §7 [from general knowledge]
- Skelton & Pais — *Team Topologies* (2019) — §8 [from general knowledge]
- Cross-references, do not duplicate: `~/.claude/knowledge/observability_logging_doctrine.md` (SRE/observability), the `agentic-systems-architect` primer (DORA as agent-loop telemetry).
