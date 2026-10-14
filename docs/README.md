# Documentation index

One line per document. Start with the top-level [`ARCHITECTURE.md`](../ARCHITECTURE.md) for how the
pieces fit, and [`GLOSSARY.md`](../GLOSSARY.md) for the vocabulary. In this public repo,
`CLAUDE.md §N` means `OPERATING_CONTRACT.md §N`.

## Maturity tags

- `core` — the git gate chain, the review stack and the everyday dev agents. The rest of the repo
  assumes these. Read them first.
- `optional` — complete and tested, but the core runs without it. Adopt one at a time.
- `experimental` — newer, narrower, tied to the author's own setup, or described but not fully
  shipped here. Expect to adapt it, and expect less operating history.

The tags come from what each document says about itself and about the code it covers. The project
files in the next table are all `core` except the component READMEs and the templates file, which carry their own tag.

## Top-level and component files

| Document | Tag | What it covers |
|---|---|---|
| [`../README.md`](../README.md) | `core` | What the repo is, how to install it, and the table of gates and what each prevents. |
| [`../CLAUDE.md`](../CLAUDE.md) | `core` | The short file Claude Code reads every session: the four rules most often broken. |
| [`../OPERATING_CONTRACT.md`](../OPERATING_CONTRACT.md) | `optional` | The full rule set, and what every `CLAUDE.md §N` citation in this repo points at. Its own header calls it an optional appendix to adopt one rule at a time. |
| [`../POSTMORTEM.md`](../POSTMORTEM.md) | `core` | The incidents behind the gates, with a table of which lessons a hook enforces and which are working discipline. |
| [`../ARCHITECTURE.md`](../ARCHITECTURE.md) | `core` | The three layers, the gate chain with its fail-open and fail-closed cases, state directories, one change end to end. |
| [`../GLOSSARY.md`](../GLOSSARY.md) | `core` | The project's own words: gate numbering, lane, dossier, primer, tier, reviewer of record, and more. |
| [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | `core` | How to build and test a change, the two rules every change follows, how to report a gate false positive. |
| [`../SECURITY.md`](../SECURITY.md) | `core` | What counts as a security issue here (a gate bypass) and how to report one privately. |
| [`../SUPPORT.md`](../SUPPORT.md) | `core` | What to expect from free support and how to report a bug; paid help is on [`consulting.md`](consulting.md). |
| [`../CHANGELOG.md`](../CHANGELOG.md) | `core` | Release notes by version, with a list of known gaps. |
| [`../CODE_OF_CONDUCT.md`](../CODE_OF_CONDUCT.md) | `core` | Contributor Covenant 2.1. |
| [`../live-testing/README.md`](../live-testing/README.md) | `optional` | The browser-testing policy file, the pool tooling, and the hook that enforces the policy. |
| [`../telemetry/README.md`](../telemetry/README.md) | `optional` | Record schema and pricing data for measuring self-correcting agent loops; the code is `hooks/cycle_telemetry.py`. |
| [`../templates/oversight/PLACEHOLDERS.md`](../templates/oversight/PLACEHOLDERS.md) | `optional` | The `__TOKEN__` placeholders used across the dossier templates, with an example value for each. |
| [`../tools/gtm/README.md`](../tools/gtm/README.md) | `experimental` | Company-pack and logging tools for the GTM department; its design contracts are only partly implemented. |

## Getting started and offers

| Document | Tag | What it covers |
|---|---|---|
| [`getting-started.md`](getting-started.md) | `core` | The install path: put the runtime in place, either as a fresh clone or merged into an existing `~/.claude`; wire the hooks; turn enforcement on; run the gate-chain suites. Then, optionally, stand up the oversight roster and GTM department on your own repo with `init_repo.sh`, `manifest.json` and dossiers. |
| [`consulting.md`](consulting.md) | `optional` | The paid audit and setup-sprint offer with starting prices. Not part of the software. |

## Subsystems

| Document | Tag | What it covers |
|---|---|---|
| [`subsystems/gate-chain.md`](subsystems/gate-chain.md) | `core` | Every gate on the Bash tool: what it denies, escape hatches, log-only versus enforcing. |
| [`subsystems/review-ladder.md`](subsystems/review-ladder.md) | `core` | Review before commit: the content-keyed ledger, plan and code review, risk tiers, warm and cold rounds. |
| [`subsystems/concurrency-and-claims.md`](subsystems/concurrency-and-claims.md) | `core` | The file-claim ledger and per-repo commit mutex that keep concurrent commits from colliding. |
| [`subsystems/telemetry-and-spend.md`](subsystems/telemetry-and-spend.md) | `optional` | Spend and churn data: the per-dispatch ledger, cost resolution, review-attribution audits. |
| [`subsystems/knowledge-and-primers.md`](subsystems/knowledge-and-primers.md) | `optional` | What lives in `knowledge/`: primers, model policy, the repo registry behind `${REPO:<slug>}`. |
| [`subsystems/skills-and-commands.md`](subsystems/skills-and-commands.md) | `optional` | Skills versus slash commands, and the lane skills that drive `scripts/lane.sh`. |
| [`subsystems/workflows-and-orchestration.md`](subsystems/workflows-and-orchestration.md) | `optional` | The `Workflow` tool, warm continuation with `SendMessage`, and when to use each. |
| [`subsystems/oversight-wheel.md`](subsystems/oversight-wheel.md) | `optional` | The fifteen-agent oversight roster, the scheduled jobs that launch it, and THE ISSUE WHEEL. |
| [`subsystems/oversight-install.md`](subsystems/oversight-install.md) | `optional` | Heartbeats, kill switch, and installing the oversight system into a new repo. |
| [`subsystems/live-testing.md`](subsystems/live-testing.md) | `optional` | The pool of numbered browser slots, the allowlist policy, and how credentials are handled. |
| [`subsystems/mirror-sync.md`](subsystems/mirror-sync.md) | `optional` | How this runtime is exported, redacted and published. Only useful if you publish your own. |
| [`subsystems/gtm-department.md`](subsystems/gtm-department.md) | `experimental` | The go-to-market department: mission lifecycle, sixteen seats, what a repo must provide. |
| [`subsystems/codex-review.md`](subsystems/codex-review.md) | `experimental` | A scaffold for sending a diff to a second model for review, with its consent and safety gates. |
| [`subsystems/board-state.md`](subsystems/board-state.md) | `experimental` | A script that bulk-sets priority and status on one project board without exhausting API budget. |
| [`subsystems/account-rotation.md`](subsystems/account-rotation.md) | `experimental` | Switching between your own paid accounts near a usage limit. The tool is not in this repo. |

## Patterns

| Document | Tag | What it covers |
|---|---|---|
| [`patterns/estimate-feedback-loop.md`](patterns/estimate-feedback-loop.md) | `experimental` | Theory only: domain agents that check an engine's confident output and feed fixes back. No code here. |

## Agents

[`agents/README.md`](agents/README.md) is the generated roster (model, tools, who dispatches whom)
and is `core`. Each agent below has an explainer next to it.

**Everyday dev agents**

| Document | Tag | What it covers |
|---|---|---|
| [`agents/code-reviewer.md`](agents/code-reviewer.md) | `core` | Reviews a pending commit before it lands; returns findings and a blocker count; never edits. |
| [`agents/plan-reviewer.md`](agents/plan-reviewer.md) | `core` | Reviews a plan before any code is written, for completeness and root-cause fixes. |
| [`agents/implement.md`](agents/implement.md) | `core` | Writes code by targeted patch inside an assigned set of files; never touches git. |
| [`agents/test-writer.md`](agents/test-writer.md) | `core` | Writes tests of intended behavior and shows they fail without the fix. |
| [`agents/explore.md`](agents/explore.md) | `core` | Read-only codebase mapping that returns paths and signatures. |
| [`agents/git-ops.md`](agents/git-ops.md) | `core` | Path-scoped commits, issue lifecycle, PR text and CI audits; no push without a go-ahead. |
| [`agents/test-runner.md`](agents/test-runner.md) | `core` | Runs a named suite and reports counts, coverage and failures; can detect flakes. |
| [`agents/ci-monitor.md`](agents/ci-monitor.md) | `optional` | Polls one CI run to a result and reports failures as they appear. |
| [`agents/design-reviewer.md`](agents/design-reviewer.md) | `optional` | Advisory UI, UX and accessibility review against a repo's own design system. |
| [`agents/browser-ops.md`](agents/browser-ops.md) | `optional` | Drives one assigned browser-pool slot and reports structural facts only. |
| [`agents/session-coordinator.md`](agents/session-coordinator.md) | `optional` | Integration lane for multi-worktree efforts: lands reviewed diffs one at a time. |

**Oversight roster** (all `optional`; none edits code)

| Document | Tag | What it covers |
|---|---|---|
| [`agents/launch-director.md`](agents/launch-director.md) | `optional` | Ranks all work against the app's one goal and kills gold-plating. |
| [`agents/board-steward.md`](agents/board-steward.md) | `optional` | Keeps the issue tracker honest: dedupe, re-triage, truthful closes. |
| [`agents/sentinel.md`](agents/sentinel.md) | `optional` | Health, log and cost sweeps, and the audit of every scheduled job's heartbeat. |
| [`agents/consistency-auditor.md`](agents/consistency-auditor.md) | `optional` | Finds contradictions between docs, help copy, app text and backend behavior. |
| [`agents/test-architect.md`](agents/test-architect.md) | `optional` | Judges whether the test suite proves intent and whether logs are debuggable. |
| [`agents/trust-architect.md`](agents/trust-architect.md) | `optional` | Security, tenancy and money review; reviewer of record on trust-surface commits. |
| [`agents/product-qa.md`](agents/product-qa.md) | `optional` | Staging walkthroughs as a customer persona, with screenshots and severity scores. |
| [`agents/agentic-systems-architect.md`](agents/agentic-systems-architect.md) | `optional` | Audits the design of agents, loops and gates, including their cost. |
| [`agents/code-quality-architect.md`](agents/code-quality-architect.md) | `optional` | Code structure, coupling and debt trend, from a deterministic scan. |
| [`agents/admin-portal-architect.md`](agents/admin-portal-architect.md) | `optional` | Which admin-console pages work, and what the operator cannot see. |
| [`agents/observability-architect.md`](agents/observability-architect.md) | `optional` | Logging quality: correlation ids, error handling, alerts tied to real signals. |
| [`agents/devops-architect.md`](agents/devops-architect.md) | `optional` | Delivery and infrastructure: IaC drift, release and rollback safety. |
| [`agents/research-scout.md`](agents/research-scout.md) | `optional` | Prior-art checks on open-source code, with a license-checked verdict per finding. |
| [`agents/market-analyst.md`](agents/market-analyst.md) | `optional` | Competitor and market facts as dated deltas against a baseline. |
| [`agents/cost-strategist.md`](agents/cost-strategist.md) | `optional` | Vendor and cloud spend tally with keep, kill or downgrade framing. |

**GTM department** (all `experimental`; run by `marketing-director`; they advise and draft, none posts, publishes or spends)

| Document | Tag | What it covers |
|---|---|---|
| [`agents/marketing-director.md`](agents/marketing-director.md) | `experimental` | Runs a go-to-market mission through its phases and dispatches the bench. |
| [`agents/conversion-architect.md`](agents/conversion-architect.md) | `experimental` | Finds conversion friction on public funnel pages. |
| [`agents/brand-architect.md`](agents/brand-architect.md) | `experimental` | Visual identity of marketing surfaces: type, color, spacing, asset quality. |
| [`agents/content-strategist.md`](agents/content-strategist.md) | `experimental` | Headlines, page copy, email sequences, voice guide, video scripts. |
| [`agents/seo-architect.md`](agents/seo-architect.md) | `experimental` | Crawlability, schema markup, page speed, sitemaps, content gaps. |
| [`agents/paid-acquisition-strategist.md`](agents/paid-acquisition-strategist.md) | `experimental` | Ad account structure, budgets, bidding and CAC math; advisory only. |
| [`agents/pricing-economist.md`](agents/pricing-economist.md) | `experimental` | Questions the cost basis and price position; never reprices. |
| [`agents/video-producer.md`](agents/video-producer.md) | `experimental` | Shot lists, b-roll briefs and review of rendered cuts. |
| [`agents/local-presence-architect.md`](agents/local-presence-architect.md) | `experimental` | Local listings, name-address-phone consistency, review-response policy. |
| [`agents/social-media-strategist.md`](agents/social-media-strategist.md) | `experimental` | Organic social calendar, format mix and community policy; never posts. |
| [`agents/measurement-architect.md`](agents/measurement-architect.md) | `experimental` | Analytics events, tag-container governance, consent, metric definitions. |
| [`agents/revenue-ops-architect.md`](agents/revenue-ops-architect.md) | `experimental` | Speed to lead, routing, CRM hygiene and follow-up; never contacts a lead. |
| [`agents/gtm-analyst.md`](agents/gtm-analyst.md) | `experimental` | Read-only analyst that turns handed-over exports into scoreboard values. |
| [`agents/gtm-drafter.md`](agents/gtm-drafter.md) | `experimental` | Drafts short replies, captions and listing text; proposals only. |
| [`agents/gtm-checker.md`](agents/gtm-checker.md) | `experimental` | Checks drafts against claims, AI-content and compliance lists; pass or fail. |

**Venture department** (all `experimental`; drafts and plans, never sends, signs or spends)

| Document | Tag | What it covers |
|---|---|---|
| [`agents/venture-director.md`](agents/venture-director.md) | `experimental` | Runs one company's money missions and dispatches the venture bench. |
| [`agents/capital-and-exit-strategist.md`](agents/capital-and-exit-strategist.md) | `experimental` | Exit paths, buyer and investor maps, valuation ranges, deal structure. |
| [`agents/bizdev-outbound-strategist.md`](agents/bizdev-outbound-strategist.md) | `experimental` | Outbound campaign plans and target lists; never sends. |
| [`agents/partner-recruiter.md`](agents/partner-recruiter.md) | `experimental` | Shortlists and drafts for recruiting co-founders and advisors. |
| [`agents/hiring-specialist.md`](agents/hiring-specialist.md) | `experimental` | Role requirements, job posts, screening rubrics and interview guides; never posts. |

**Not portable**

| Document | Tag | What it covers |
|---|---|---|
| [`agents/trading-strategist.md`](agents/trading-strategist.md) | `experimental` | A second-opinion agent for one trading repo. Its explainer says it is outside the runtime bundle. |
