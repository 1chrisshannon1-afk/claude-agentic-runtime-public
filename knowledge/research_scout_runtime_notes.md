# research-scout — runtime notes

This is `research-scout`'s dossier-equivalent for the runtime itself (`~/.claude`) — the target row
with no product repo behind it. Read this before a sweep dispatched against the runtime rather than
against a product repo. Facts below are dated findings from the runtime's own groundwork probe run
(2026-08-31, `~/.claude/plans/research_groundwork_2026_08_31/probe_oss-agent-infra.json`) plus the
query-craft lessons that probe surfaced specifically while searching the agent-infrastructure/OSS
ecosystem. Re-verify anything here (stars, license, `pushed_at`) before treating it as current — a
finding's evidence ages the moment it's recorded.

## 1. What "the runtime" means as a research target

The runtime is `~/.claude` itself: its agent roster, hooks, schedules, telemetry contract, and
oversight-wheel design. A sweep against this target is asking "does open-source agent
infrastructure already solve a problem we're solving ourselves with ad hoc scripts?" — distinct
from a sweep against a product repo, which asks the same question about that product's own
domain/feature surface.

## 2. Findings from the 2026-08-31 groundwork probe (openclaw ecosystem)

Five repos evaluated, all found via the agent-infrastructure/OSS-hobbyist-tooling niche. Re-verify
stars/license/`pushed_at` before citing any of these as current in a future report — they age fast
in a space this active.

- **A large, actively-shipping (MIT) multi-agent gateway project** exposes a security
  **self-audit CLI** built from roughly 25 independent, composable finding-collectors (gateway
  exposure, exec/sandbox config drift, plugin trust boundaries, dangerous config flags, filesystem
  permissions), all rolled into one report with severities and remediation text, plus a
  suppressions mechanism. **Verdict: LEARN-FROM.** The code itself is deeply coupled to that
  project's own config/gateway/plugin types and isn't liftable verbatim, but the **architecture** —
  a registry of named, independent audit collectors composed into one report — is directly
  applicable to this runtime's own scattered safety-parity/drift scripts, which currently exist as
  several separate ad hoc checks rather than one composed collector registry. Worth citing the next
  time those scripts are revisited for restructuring.
- **The same project's job scheduler** persists every scheduled job's run history in a local
  database that survives restarts, only marks a one-shot job's cleanup as done once delivery is
  *confirmed* (never merely attempted), runs an independent scheduler watchdog on its own cadence
  separate from any single job/agent-turn timeout, and on startup **reschedules** overdue jobs
  rather than **replaying** them, specifically to avoid blocking its own startup window. **Verdict:
  LEARN-FROM.** This runtime's own scheduled-job wheel has heartbeat/liveness auditing but no
  persisted run-history ledger, no delivery-confirmation-gated cleanup, and no documented
  startup-catch-up policy for jobs missed during a machine sleep/reboot — a real, named gap. Not
  directly portable code (it's wired into that project's own process model), but the specific set
  of edge-case policies (persisted history + confirmed-delivery cleanup + reschedule-not-replay) is
  worth adopting as design requirements for any future evolution of this runtime's own scheduled-job
  mechanism.
- **A cross-session memory tool** hooks a fixed lifecycle of session/tool-use events to drive a
  background worker that compresses tool-use observations via a live sub-call to an LLM, then
  stores them for semantic retrieval on a later session. **Verdict: LEARN-FROM.** This runtime's own
  cross-session memory is a single flat, manually-curated file with no automatic capture and no
  semantic search — a genuinely different tradeoff, made deliberately (this runtime's memory is
  auditable plaintext with no background services and no vector database, by design). Direct COPY
  is unattractive precisely because it requires standing up infrastructure weight (a background
  worker daemon plus a vector store) this runtime deliberately avoids. The narrower, cheaper idea —
  hooking a tool-use event to auto-capture a structured observation log as a plain append-only file,
  independent of and never replacing the curated memory file — is a concrete, scoped feature this
  runtime currently lacks and could add far more cheaply than the full pipeline.
- **A container-per-agent variant of the same ecosystem** runs each agent inside its own OS-level
  container for filesystem isolation, contrasted explicitly (in its own documentation) against the
  single-process, application-level isolation model the larger project uses. **Verdict: LEARN-FROM.**
  Not liftable without adopting a whole container-per-agent model, but directly relevant prior art
  the next time this runtime's own agent-isolation approach (worktree + hook based, not
  container-based) is revisited — it's a real, documented example of the same underlying tradeoff
  (trusting concurrent/untrusted agent code with shared state vs. paying for stronger isolation)
  resolved the other way by another project.
- **An enterprise reference-stack wrapper** around a third-party sandbox product, and **a
  6-star pure-Bash concurrent-session file-locking tool**, were both evaluated and found not
  worth further attention: the former is an onboarding/deployment wrapper with the actual
  isolation mechanism living in a separate, unexamined repo (nothing to learn from without
  inspecting that other repo, which was out of scope); the latter, while MIT-licensed and solving
  literally the same file-contest problem this runtime's own commit-claim ledger solves, showed no
  evidence of production battle-testing and offered no design maturity beyond what this runtime
  already has (which additionally has commit-time gate integration, dead-process self-heal, and a
  documented incident history). **Verdict: AVOID** on both — recorded so a future sweep doesn't
  re-spend rounds re-evaluating either from scratch, not because either is a trap in the licensing
  sense.

## 3. Query craft specific to the agent-infrastructure niche

- **Prefer the raw search API form over a convenience CLI wrapper's search subcommand.** The
  wrapper form threw spurious rate-limit-shaped errors at low actual usage while the raw endpoint,
  called seconds later with the account's core quota showing nearly full, worked immediately.
  Default to the raw form for this niche.
- **Always quote a URL containing a `?`** when constructing a request in a shell — an unquoted `?`
  in a query string is interpreted as a shell glob character and fails with a confusing "no
  matches" error that has nothing to do with the actual request. Cost one full wasted round in this
  probe before being caught.
- **Fetch and read the actual license file text, not just the summary API field, especially for a
  large/fast-moving repo.** One of the largest repos evaluated in this probe reported `NOASSERTION`
  via its summary metadata while its actual LICENSE file was a clean, standard permissive license —
  metadata license detection can be stale on large or fast-changing repositories. Trusting only the
  summary field would have wrongly capped a legitimately liftable finding at a lower verdict.
- **Broad, generic keyword queries in this niche return a scatter of low-differentiation hobbyist
  projects, not real findings.** Two broad queries in this probe surfaced dozens of near-identical,
  low-star personal projects with no meaningful differentiation from each other and no adoption
  evidence — useful only as a sanity check that nothing larger was hiding in that specific query
  shape, never as a source of real findings on their own. In this niche specifically, a star count
  above roughly the low tens is a reasonably reliable junk filter for the broad-query result set;
  below that threshold, treat a hit as needing independent evidence of real use before it's worth
  inspecting further.
- **Treat curated list/index repositories (an "awesome-list" style aggregator) as pointers, not
  findings.** A list repo that curates from a larger ecosystem's own registry is useful context for
  understanding a category's taxonomy, but is not itself a reusable mechanism — don't report a list
  repo as a finding; use it to identify what to search for next instead.
- **A fixed three-call minimum per real candidate is the efficient default in this niche:** repo
  metadata, README, and a recursive file-tree listing (quoted, per the URL-quoting note above).
  Only fetch individual file contents for the two or three paths the tree listing itself suggests
  are load-bearing — a README or a docs index page usually contains an architecture summary that's
  cheaper to read than reverse-engineering source directly.

## 4. Degraded / unverified facts

None carried forward from the groundwork probe as an open unverified-fact warning — the probe's own
findings above are each individually evidence-graded (repo, stars, license, `pushed_at`, inspected
mechanism) per the primer's evidence bar. Treat every star count and `pushed_at` value above as
**as of 2026-08-31** — re-derive rather than trust a frozen number on any repo this file names, the
same discipline this runtime applies to every other frozen count anywhere else.

**Reference corpus (added 2026-08-31):** `~/.claude/knowledge/karpathy/corpus.md` — the AutoResearch section is convergent prior art for bounded keep/revert loops (and a live example of the README-claims-MIT-but-/license-404s trap, ledger row RS-0024); the minimal-implementation section grounds the small-single-purpose-file principle for agent-edited code.
