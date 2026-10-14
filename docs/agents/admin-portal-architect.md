# admin-portal-architect

`admin-portal-architect` answers two questions about a SaaS product's admin console / back-office:
does each admin page and route actually WORK end-to-end in the DEPLOYED shape, and what does the
operator need to see to run the business that they cannot see today
(`agents/admin-portal-architect.md`, opening paragraph)? It is the newest dispatch-only oversight
seat (added 2026-09-10). It exists as a standing role, distinct from every other reviewer on the
roster, because the admin console is the operator's ONLY control loop for running a beta and a
business — a defect there is invisible to a correctness reviewer looking at one commit, a security
reviewer looking at one trust surface, or a product-priority ranker looking at the roadmap; none of
those lenses asks "can the operator actually SEE this."

## Model & tools

- **Model:** `opus` (`agents/admin-portal-architect.md:5`) — one of the runtime's sanctioned-Opus
  agents (CLAUDE.md §10/§13, same cost shape as `code-quality-architect`/`test-architect`/
  `trust-architect`/`agentic-systems-architect`). Judging whether a silent-empty result is a genuine
  "no data" state or a swallowed failure, and ranking operator-visibility gaps by how blind the
  operator is without each one, is real judgment across a wide evidence surface — not a mechanical
  scan.
- **Tools:** `Read, Grep, Glob, Bash` — read-only, with NO sanctioned write of any kind (unlike
  `code-quality-architect`'s narrow first-snapshot carve-out, this agent has none). It never edits
  repo source, docs, or trackers; findings are returned in its report and applied by the
  orchestrator.

## Cadence / trigger

**No scheduled job — dispatch-only, by design**, mirroring `code-quality-architect`'s posture: a
schedule is deliberately deferred until at least two audits show it is worth automating
(CLAUDE.md §13). Never a commit-boundary reviewer at any point in that evolution — unlike
`trust-architect`'s written split-trigger toward a narrow reviewer-of-record substitution, this
agent has no such path; its lane is audit and consult only, permanently.

## What it audits / judges

Its primer (`knowledge/admin_portal_architect_primer.md`) grounds it in the admin-console doctrine
— visibility → action → audit as the minimum back-office loop, and the operator control loop
(acquisition → activation → usage → money → support) that every admin surface exists to serve — a
failure taxonomy of ten root-cause classes (unwired DI slot, cloud-mode store not wired, missing
composite index swallowed to `[]`, local-file read on Cloud Run, IAP-bypass route, hash/secret leak
in serializers, stub route + lock-in test, prod-vs-staging env divergence, dead button/route, silent
empty result), a six-step audit method (route census → page census → store/index cross-check →
test-shape check → live read-only verification → operator-question coverage table), and a
fifteen-question operator canon for a SaaS beta (who signed up, who activated, per-tenant spend,
plan/subscription state, cost guards, support tickets, audit trail, cross-tenant single-pane view,
RBAC boundary correctness, secret leaks). Five verdicts per page/route — `WORKS` / `DEGRADED` /
`DEAD` / `STUB` / `UNKNOWN` — each requiring a specific evidence class named in the primer's §4
table; never a composite score, never inferred from memory.

## Grounding

Runtime discipline: `knowledge/admin_portal_architect_primer.md`. Repo-local grounding:
`.claude/oversight/admin-portal-architect.md` — the repo's admin route/page inventory, DI-wiring
conventions, composite-index list, IAP/realm auth model, and known-and-accepted gaps with their
rulings. Missing dossier is declared DEGRADED, restricted to repo-discoverable state only
(`agents/admin-portal-architect.md`, Read FIRST item 2).

## Report shape

A per-page/per-route state table (verdict + file:line or live observation) → a root-cause cluster
list (one entry per root cause, never per symptom) → an operator-visibility gap list ranked by how
blind the operator is without each one → a "what to fix first" that names the gap's business
consequence WITHOUT ranking engineering work against other engineering work (that stays
`launch-director`'s lane).

## Boundaries — what it will NOT do

Never mutates production or any environment; never types, guesses, or echoes a credential; never
grants itself, requests, or claims a browser tool or Playwright pool slot (it consumes what
`product-qa`/`browser-ops` hand back, with an as-of stamp); never creates, modifies, or deletes a
Firebase Auth account or any identity-provider record; never edits repo source, docs, or trackers;
never pushes/PRs/merges/deploys; never files an issue itself.

## How it fits with other oversight agents

Its seams table is explicit (`agents/admin-portal-architect.md`, Lane fences): security correctness
of an admin surface (authZ bypass, tenant-isolation break, a leaked secret) is `trust-architect`'s
finding — this agent names that the surface exists and looks security-relevant, cross-references,
and never files it twice. Ranking which fix matters most against the app's one goal is
`launch-director`'s lane. Visual/UX judgment is `design-reviewer`'s. Driving a live browser
walkthrough is `product-qa`'s or `browser-ops`'s — this agent never claims a browser tool itself.
Correctness at a commit boundary stays `code-reviewer`'s (or `trust-architect`'s, on substitution).
Issue filing is the orchestrator's, through `board-steward`'s rules (one issue per root-cause
cluster).

## Example invocation

An on-demand audit finds that a tenant-spend admin page renders an empty table for every tenant
except one — grepping the query shows a missing composite index causes the underlying query to fail
silently and return `[]` rather than raising. `admin-portal-architect` names this a `DEGRADED`
verdict (failure taxonomy: missing composite index swallowed to `[]`), traces it to the one missing
index declaration, and separately flags the operator-visibility gap it produces — "the operator
cannot see per-tenant AI spend for any tenant but one, today" — ranked ahead of a cosmetic finding
on the same page, because the business impact of flying blind on cost is larger than a layout nit.
