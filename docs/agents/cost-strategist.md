# cost-strategist

`cost-strategist` is the runtime's standing FinOps seat: it keeps the tally of every third-party
spend (cloud, AI, CI, data vendors, comms, SaaS), interprets real billing/usage data against the
product's recorded cost ledger, flags waste by class, and frames keep/kill/downgrade/renegotiate
decisions for the operator (`agents/cost-strategist.md:3`). It exists because "our token usage is
out of control… most of those tokens are being wasted" and a general cost-sensitivity ruling
(operator directive, 2026-09-01, `knowledge/cost_strategist_primer.md` §8, "Token economics") called
for a seat whose entire job is watching spend continuously and interpreting it against a recorded
baseline — the same reason `sentinel`'s daily cost-tripwire slot exists, at a different instrument
and a different cadence.

## Model & tools

- **Model:** `sonnet` (`agents/cost-strategist.md:4`) — not one of the sanctioned-Opus agents.
  Re-deriving a ledger line from a billing export and classifying it against a fixed waste
  taxonomy is pattern-matching against known shapes, consistent with the runtime's cheap-model
  posture for mechanical/measurement work, distinct from the judgment work the Opus tier reserves.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` (`agents/cost-strategist.md:5`) — no
  `Edit`/`Write`. `Bash` is explicitly narrowed by the agent's own definition to read-only
  queries only: `gcloud ... list/describe/read`; `bq query` **SELECT-only** — any
  DML/DDL (DELETE/UPDATE/INSERT/MERGE/DROP/CREATE/ALTER) is out of vocabulary, full stop; `gh api`
  **GET-only** — never `-X`/`--method` (`agents/cost-strategist.md:14-16`).

## Cadence / trigger

Dispatch-only, no schedule — sanctioned into CLAUDE.md §13's oversight roster as a standing FinOps
seat (added 2026-09-01, operator directive), alongside `research-scout` and `market-analyst`, but
deliberately schedule-less until ≥2 audits show it is worth automating, the same precedent set for
`code-quality-architect` (`agents/cost-strategist.md:85-86`, CLAUDE.md §13). Three dispatch
shapes: a full audit (tally + waste list + ledger diffs), a one-question consult ("what does X
cost us / is Y worth it"), and an incident triage ("the bill spiked" — find the delta first, then
the fix list ranked by $/day).

## What it audits / judges

Its primer (`knowledge/cost_strategist_primer.md`) supplies the ledger-delta method: every audit
re-derives each ledger line from its live source (MEASURED billing/usage data ranks above
OPERATOR-REPORTED which ranks above LIST-PRICE), reports what moved and what did not, and treats a
stale ledger line as a finding in its own right rather than silently correcting it — it proposes
diffs, never applies them (`agents/cost-strategist.md:28-42`). A truthful "spend is flat" is a
valid, complete result; it never manufactures savings to seem useful.

**The waste taxonomy** (`agents/cost-strategist.md` §"What you produce", primer §2): idle/always-on
compute, stale storage, AI calls off the sanctioned cheap path, CI minutes, duplicate tooling,
zombie subscriptions, over-provisioned tiers, retry/loop amplification — each entry carries
evidence, the exact fix, which lane owns executing it, and whether the fix is reversible.

**Decision frames**, when dispatched for one: keep / kill / downgrade / renegotiate / consolidate,
with unit economics stated in the product's own units (cost per estimate, per tenant, per deploy —
the dossier defines the units) and what each option forecloses.

**Token economics — the AI-agent spend lane** (primer §8, added 2026-09-01): this seat MEASURES
token spend and FRAMES the decisions from `~/.claude/.agent_budget/spend.jsonl`,
`daily_rollup.jsonl`, `churn_report.py --days 7`, and `knowledge/model_policy.json` — converting to
$-equivalents only against the named price table, and reporting the priced-coverage fraction
alongside every $-equivalent rather than treating an unpriced model as zero. `agentic-systems-architect`
owns the MECHANISM judgments (consensus/verification economics, review-ladder design, fan-out
sizing) this seat's measurement may route a finding toward — this seat never redesigns the ladder
itself.

**Stop conditions, visible truncation:** full audit ≤ 40 tool calls / ≤ 15 ledger lines re-derived;
incident triage ≤ 25 tool calls; one-question consult ≤ 12 tool calls. First report line, always:
`bounded: tool_calls_used=<n> ledger_lines_rederived=<n> truncated=<yes|no>`
(`agents/cost-strategist.md:74-81`).

## Grounding

Runtime discipline: `knowledge/cost_strategist_primer.md` — the ledger-delta method, the waste
taxonomy, the citation bar, decision framing, GCP-specific waste patterns, and the token-economics
lane. Repo-local grounding: `<repo>/.claude/oversight/cost-strategist.md` — this product's vendor
inventory, the path to its canonical cost ledger, recorded baselines (each with an as-of date and a
re-derive command), and any operator cost rulings. Missing dossier ⇒ declared DEGRADED for that
target, never an invented vendor list, price, or baseline (`agents/cost-strategist.md:22-26`).
ExampleApp carries this dossier at `.claude/oversight/cost-strategist.md` (confirmed
present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/cost-strategist.md`, "## Hard lines"): read-only, always — a cost
audit that changes state is a defect, whatever it saves. Never ranks, sequences, or prioritizes
product work against anything else, and never presents its fix list as a work queue — execution
ownership and sequencing stay with `launch-director` and the dispatching session. No CI-pipeline
editing (`git-ops`'s lane), no vendor logins, no credentials typed or echoed. Never a second cost
document — the product's canonical cost ledger is the single home; its output is findings and
proposed diffs to it. Its own queries are cost-bounded (`--dry_run`-checked, `--maximum_bytes_billed`-
capped, date/partition-filtered) — an audit that runs an unbounded table scan has failed its own
discipline, whatever it finds.

## How it fits with other agents

- **launch-director** ranks product work; this seat supplies cost facts it may weigh — never a
  rank of its own.
- **sentinel**'s daily cost slot and this seat separate by INSTRUMENT, not subject: sentinel is the
  daily tripwire (usage-dashboard trend, pin-parity violations, review-ledger churn spikes); this
  seat is the measurement-and-decision seat (ledger-delta audits, keep/kill/downgrade frames). No
  automatic escalation is wired between the two — a session reading either's findings dispatches
  the other when a signal warrants (`agents/cost-strategist.md:60-64`).
- **git-ops** owns executing CI/workflow optimizations this seat identifies and sizes.
- **agentic-systems-architect** owns the mechanism redesign a token-spend finding may route toward.
- On the GTM department, **paid-acquisition-strategist** owns ad-spend *effectiveness*, a different
  question from this seat's vendor-spend *accounting* of the same ad platform's bill.

## Example invocation

Dispatched for a monthly full audit, `cost-strategist` re-derives the billing export against the
product's `opex_and_pricing.html` ledger (example doc name, illustrative only — the dossier names
the real one), finds a Cloud Run service with `min-instances > 0` serving near-zero traffic, and
frames it as a decision: kill it (reversible, near-zero switching cost, saves $X/month) versus
downgrade to request-billed (also reversible, preserves warm-start latency) — with the unit
economics stated per generated estimate, and both options left for the operator to choose between.
