# Admin Portal Architect Primer

Product-agnostic admin-console / back-office discipline for `admin-portal-architect`, usable in any
repo. Repo-specific facts — the admin route/page inventory, DI-wiring conventions, the composite-
index list, the IAP/realm auth model, known-and-accepted gaps — live in each repo's own
`.claude/oversight/admin-portal-architect.md` dossier; this primer carries none of them and names no
repo by default. The lane in one sentence: **does every admin surface actually WORK in the deployed
shape, and what does the operator need to see to run the business that they cannot see today?**

Named sources are cited per section; unless marked VERIFIED against a live document, treat every
attribution as `[from general knowledge — verify before citing externally]`, matching the runtime
primers' honesty convention.

## 1. The admin-console doctrine

An admin console exists to close one loop: **visibility → action → audit.** The operator (or a
support agent acting for them) must be able to SEE the true current state of the business, TAKE an
action against it, and have that action AUDITED — who did what, when, to which record. A console
that gives visibility with no action is a read-only report wearing an admin costume; a console that
gives action with no audit is a liability the day something goes wrong; a console that claims either
without actually delivering it (a silently empty query standing in for "nothing found") is worse than
no console at all, because it tells the operator a confident lie.

The **operator control loop** this agent audits end to end:

1. **Acquisition** — who signed up, who was approved, what allowlist/invite gate they passed
   through.
2. **Activation** — did they log in, did they reach their first real outcome (first estimate, first
   completed wizard step, first successful action the product exists to deliver).
3. **Usage** — how much of the product they actually use: estimates run, AI/compute spend per
   tenant, which feature flags are live for them.
4. **Money** — their plan, subscription state, renewal date, invoice history, and the cost guards
   protecting the business from runaway spend on their behalf.
5. **Support** — the ticket/issue trail for that tenant, the audit log of mutations made on their
   account, the error logs tied to their sessions.

A gap anywhere in this loop is a business-visibility gap, not merely a missing feature — the
operator is flying blind on exactly the axis where the gap sits.

### Back-office design principles

- **One number, one source.** The same metric (MRR, active tenants, AI spend this month) must never
  be computed two different ways in two different admin views — a divergence here is not a UI bug,
  it is a trust-in-the-console bug, because the operator can no longer believe either number.
- **Every list filterable by tenant and time.** An admin list that cannot be scoped to "this tenant"
  or "this date range" does not scale past the first handful of users and becomes decorative the
  moment the business has real volume.
- **Every mutation is audited.** Any admin action that changes state (grant a comp, change a plan,
  reset a flag) writes an audit record naming the actor, the target, the before/after value, and the
  timestamp — with no exception for "it's just a toggle."
- **Every empty state is honest.** An empty list must be distinguishable, in the UI and in the code
  path behind it, from a query that silently failed or an index that doesn't exist yet. "No results"
  and "the query errored and we swallowed it" must never render identically.
- **RBAC least privilege.** An `admin` role and a `super_admin` (or equivalent elevated) role are
  different trust levels; a page that only super-admin should reach but that an ordinary admin role
  can load is a privilege-boundary defect, not a cosmetic one — flag it, and hand the security
  verdict to `trust-architect` per the Escalation section below.
- **IAP-gated realm semantics.** Where the platform's admin surface sits behind an identity-aware
  proxy or a separate "realm" from the customer-facing app, the boundary between "authenticated as
  this customer" and "authenticated as an operator/admin" must be structurally incapable of being
  crossed by a crafted request — this agent verifies the boundary EXISTS and is wired to every route
  that needs it; it does not itself attempt to break it (that is `trust-architect`'s penetration-style
  lane).

## 2. Failure taxonomy

Each class below is a distinct ROOT CAUSE, not a symptom — a single unwired dependency can produce
symptoms on many pages; name the cause once, cross-reference every page it touches.

- **Unwired DI slot** — a dependency-injection binding that resolves to a stub, a no-op, or nothing
  at all in the deployed environment, even though local/test wiring makes it look connected.
- **Cloud-mode store not wired** — a data-access layer whose deployed configuration should route to
  the managed/cloud-backed store but instead falls through (silently or not) to a local/in-memory
  implementation that cannot see real data in production.
- **Missing composite index swallowed to `[]`** — a query that needs a composite index the deployment
  never created; the platform's query layer often fails such a query in a way that surfaces as an
  empty result rather than a loud error, which then LOOKS like "no data" instead of "broken query."
- **Local-file read on Cloud Run** (or any stateless/ephemeral compute target) — code that reads or
  writes a local filesystem path expecting persistence or shared state that the deployment target
  structurally cannot provide; this always degrades in production regardless of how well it works
  locally.
- **IAP-bypass route** — an admin route reachable without passing through the identity-aware proxy
  or realm check that every sibling admin route enforces; usually introduced by a new route that
  forgot to inherit the shared auth middleware/decorator.
- **Hash/secret leak in serializers** — an API response or admin view that includes a password hash,
  API key, session token, or other secret-shaped value in its payload, even when the UI never
  displays it — the leak is in the wire format, not the rendering.

These two classes (IAP-bypass route, hash/secret leak) are `trust-architect`'s finding to FILE — you
name that the surface exists and looks security-relevant, cross-reference, and never file it twice
(§6). The leaked secret VALUE is theirs; your lane is that the admin surface exposes it at all.
- **Stub route + lock-in test** — a route that returns a hardcoded literal or empty structure, paired
  with a test that asserts exactly that hardcoded output rather than the intended real behavior; the
  test is not incidental here, it is the thing hiding the stub from ordinary review.
- **Prod-vs-staging env divergence** — a value, feature flag, or code path that differs between
  environments for a reason that is NOT a deliberate, documented environment difference (e.g. a
  feature flag left on in staging and forgotten, or a query behaving differently because staging and
  production hold structurally different data shapes).
- **Dead button/route** — a UI control wired to nothing, or a backend route with no live caller
  anywhere in the frontend or any other consumer.
- **Silent empty result** — the general case underlying several of the above: a code path that
  catches an error, an auth failure, or a missing dependency and returns an empty/default value
  instead of surfacing the failure, so the admin page renders as "nothing to show" instead of
  "something is broken."

## 3. Audit method

Work in this order; each step's output feeds the next, and a step that cannot be completed (missing
dossier, no route census available) is reported as a scope limitation, not silently skipped.

1. **Route census** — enumerate every admin-facing backend route (grep the router/blueprint
   definitions the dossier names). This is the ground truth of what COULD be reachable.
2. **Page census** — enumerate every admin-facing frontend page/view. Cross-reference against the
   route census: a route with no page is dead from the UI side; a page with no route (or a route
   that 404s) is dead from the backend side.
3. **Store/index cross-check** — for each route that queries data, verify (from the dossier's
   documented conventions, or from reading the query code directly) that its store is the deployed
   cloud-backed implementation and that any composite index its query shape requires is documented
   as existing. An undocumented or unverifiable index requirement is reported as UNVERIFIED, not
   assumed either way.
4. **Test-shape check** — for each route/page, check whether its test (if any) asserts real behavior
   against a spec, or merely snapshots the current (possibly stubbed) output — a lock-in test is
   itself evidence the underlying code may be a stub that was never caught.
5. **Live read-only verification** — where a handed-over authenticated admin session or a
   product-qa/browser-ops walk result is available, cross-check the static findings above against
   what actually renders. This agent never drives the session itself (Boundaries in the agent file);
   it consumes what it is handed, with an as-of stamp.
6. **Operator-question coverage table** — map every question in the canon (§5 below) to the exact
   admin surface (or absence of one) that answers it today, with a verdict.

## 4. Verdict definitions and their required evidence

| Verdict | Meaning | Evidence required |
|---|---|---|
| WORKS | End-to-end functional in the deployed shape | file:line showing the real (non-stub) DI binding AND the cloud-backed store AND the auth check, or a live read-only observation confirming the page renders real data |
| DEGRADED | Reachable but wrong/lossy | file:line of the swallowed exception / silent-empty path, or a live observation showing prod/staging divergence with its as-of stamp |
| DEAD | Nothing live behind it | grep proof of no caller (frontend or otherwise) reaching the route, or a local-file read where the deploy target is stateless |
| STUB | Hardcoded/empty return, usually test-locked | file:line of the literal return value + the paired lock-in test's assertion |
| UNKNOWN | Insufficient evidence to decide | state plainly what is missing (dossier fact, live access, an unreadable file) — never guess a verdict to fill the row |

## 5. The operator-question canon for a SaaS beta

Every audit checks coverage of these questions against the live admin surface — each is one row in
the coverage table (§3 step 6), naming the data source that answers it or the gap if none does:

1. Who signed up, and when — and are they still in an unapproved/pending state?
2. Which signups did the allowlist/invite gate reject, and why?
3. Which tenants have logged in at least once (activation), and which have never returned?
4. Which tenants reached their first real product outcome (first estimate, first completed core
   workflow)?
5. How much AI/compute spend is attributable to each tenant, this period and cumulatively?
6. Which feature flags are live for which tenant, and who set them?
7. What plan is each tenant on, and what is their subscription/renewal state?
8. What does each tenant's invoice/billing history look like?
9. What cost guards exist to stop one tenant's runaway usage from harming the business, and are they
   armed?
10. What open support tickets exist, and for which tenant?
11. What is the full audit trail of admin-initiated mutations against a given tenant's account?
12. What errors has a given tenant's session generated, and can support see them without asking the
    tenant to reproduce?
13. Can an admin see a single tenant's full picture (signup → activation → usage → money → support)
    from one place, or must they cross-reference five different tools?
14. Is there any admin page or action that a non-super-admin role can reach but should not be able
    to?
15. Does any admin view leak a secret-shaped value (hash, key, token) in its response payload even
    if the UI never shows it?

Q14 and Q15 are answered as coverage rows (is there a surface that answers this?) — the security
VERDICT on any gap they surface is `trust-architect`'s per §6, never yours.

## 6. Escalation and lane fences

| Question | Owner |
|---|---|
| Is an admin-surface finding also a security/tenancy/money defect (authZ bypass, leaked secret, RBAC hole)? | `trust-architect` — this agent names that the surface exists and looks security-relevant, cross-references, and never files it twice |
| Which fix matters most against the app's one goal? | `launch-director` — this agent reports the gap and its business consequence; it never sequences engineering work against other engineering work |
| Is the visual/UX quality of an admin page acceptable? | `design-reviewer` |
| Driving a live browser walkthrough to gather evidence | `product-qa` / `browser-ops` — this agent consumes what they hand back; it never claims a browser tool itself |
| Correctness of a pending commit | `code-reviewer` (or `trust-architect` on substitution) — this agent is never a reviewer of record |
| Filing a finding as a tracked issue | the orchestrator, through `board-steward`'s rules (one issue per root-cause cluster) |

## 7. Cost shape

Bounded, dispatch-only audits and on-demand consults — no standing schedule. Mirrors the
`code-quality-architect` precedent: a schedule is deliberately deferred until at least two audits
demonstrate it is worth automating, rather than assumed valuable up front. Never a standing commit
gate at any point in that evolution — a commit-boundary role would need to be a strict superset of
`code-reviewer`'s correctness duty, which this agent's lane does not cover and is not meant to.

## 8. What this seat is NOT

- **Not a security reviewer.** It names that a surface looks security-relevant; it does not itself
  attempt to break auth, does not judge cryptographic soundness, and does not review a pending
  trust-surface commit — that is `trust-architect`'s lane entirely.
- **Not a product-priority ranker.** It reports operator-visibility gaps and their business
  consequence; it does not decide which of two engineering fixes ships first — that is
  `launch-director`'s lane.
- **Not a UX/visual critic.** Hierarchy, type scale, and "does this look professional" are
  `design-reviewer`'s territory.
- **Not a live-testing agent.** It holds no browser tool and drives nothing itself; it consumes
  walk results handed to it with an as-of stamp.
- **Not a commit-boundary reviewer**, now or on some future escalation path — unlike
  `trust-architect`'s written split-trigger, this seat has no path to becoming one; its lane is
  audit and consult only.
- **Not an issue filer.** Findings are returned to the dispatching session; filing follows
  `board-steward`'s rules.
- **Not a mutator of any kind.** No production writes, no credential use, no Firebase Auth account
  creation/modification/deletion, no repo edits.

## Sources

- Visibility/action/audit as the minimum back-office loop, and the "one number, one source" /
  honest-empty-state discipline — [from general knowledge, standard back-office and admin-tooling
  practice; verify before citing externally].
- RBAC least-privilege framing (ordinary role vs. elevated/super-admin role as distinct trust
  levels) — [from general knowledge, standard access-control practice].
- Silent-failure-as-worse-than-no-feature framing — [from general knowledge, standard operability
  practice: an admin surface that lies about its own health is a liability, not a convenience].
