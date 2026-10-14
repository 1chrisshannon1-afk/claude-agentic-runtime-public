# sentinel

`sentinel` is the runtime's standing watch: it finds the problems nobody asked about — before a
customer does — and it notices when the oversight wheel itself stops turning
(`agents/sentinel.md:10-12`). It exists as a STANDING role because SRE-lite discovery (health
checks, log-error trends, cost/drift signals) is exactly the kind of thing that only has value when
run continuously and compared against a baseline; a one-off health check tells you almost nothing,
a daily one shows you a trend. It also carries a unique second duty distinct from its detection
work: it is the agent that audits every OTHER scheduled job's own heartbeat, so a silently-broken
oversight job doesn't just sit undetected.

## Model & tools

- **Model:** `sonnet` (`agents/sentinel.md:4`) — not one of the sanctioned-Opus agents. Its rotation
  dimensions (health/logs/cost) and the heartbeat audit are pattern-matching against known
  shapes/thresholds rather than open-ended synthesis, consistent with the runtime's cheap-model
  posture for mechanical detection work.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/sentinel.md:5`) — read-only, except for one narrow,
  explicitly sanctioned write: appending a detected staging deploy-drift revision, as the literal
  line `{"revision":"<name>","detected_at":"<iso>"}`, to
  `~/.claude/schedules/queue/product_qa.jsonl`, the one write this role makes outside its own
  report (`agents/sentinel.md:53-58`).

## Cadence / trigger

Scheduled daily via `com.oversight.csa.daily.plist` — `StartCalendarInterval` fires every day at
05:10 (confirmed loaded via `launchctl list`, 2026-08-30). This is the `daily` label in CLAUDE.md
§13's job table; sentinel and consistency-auditor both ride this single daily job slot rather than
each having a dedicated schedule. Each invocation runs ONE assigned rotation dimension
(health / logs / cost) plus the fixed pre-steps (heartbeat audit, deploy-drift poll) — the daily
job prompt decides which dimension. Manual fallback when schedules are down is `/sweep`.

## What it audits / judges

Its primer (`knowledge/sentinel_primer.md`) grounds it in SRE-lite practice sized for a solo team:
toil-budget discipline (Google SRE's toil definition — manual, repetitive, automatable work — with
an explicit upper bound so sweeps never silently crowd out everything else); error-budget mechanics
(100% − SLO, the shared number that removes outage-negotiation friction); synthetic monitoring
prioritized by revenue/customer/brand impact, not "monitor everything"; alert-fatigue avoidance (an
alert with no specific next action shouldn't exist; dedupe/group repeated firings; tune thresholds
from real data); deploy/config-drift detection (both immediately after every deploy and on a
standing schedule); and an error-log review rhythm that tightens near a release and relaxes in
steady state. Three rotation dimensions: **health** (endpoints/smoke commands vs. expected shapes,
plus a second leg — see below), **logs** (new error classes, rate vs. baseline, recurring warnings
that fire constantly and gate nothing — named a finding, not noise), and **cost** (spend by
account/trend/churn signals, plus a model-pin-parity check).

**health**'s second leg is the runtime mirror publish pipeline itself
(`python3 ~/.claude/hooks/runtime_mirror_sync.py --status`, subsystem doc
`docs/subsystems/mirror-sync.md`) — strictly read-only; sentinel never runs `--sync` itself. Four
exit-coded states, each a genuinely different problem: **OK** (0, mirror current), **BLOCKED** (3,
the publish gate withheld a push — relay `BLOCKED.md`'s `Source HEAD:` and matched-pattern lines
verbatim; a block needs adjudication, not an assumed leak), **DRIFTED** (4, mirror behind — expected
and self-clearing shortly after a local commit, escalate only on distance/age), and **INERT** (5, a
missing/unreadable/rejected mirror config disables the whole subsystem silently — a **P1 finding**,
and this check is the only thing that can see it). This leg is RUNTIME-scoped, not app-scoped — it
reads no dossier and needs no `gcloud` auth — so it survives both a DEGRADED (missing-dossier) pass
and a BLOCKED-AUTH pass; it is the one health leg neither condition disables
(`agents/sentinel.md:63-93`).

A second leg under the cost dimension — cross-cycle self-correcting-loop
telemetry health (primer §8) — is fully designed but explicitly INERT UNTIL AN OPERATOR WIRES IT;
sentinel is instructed not to run it or report it as active until then
(`agents/sentinel.md:101-134`). The heartbeat-audit duty runs first, before any other sweep work: one
missed heartbeat (+ grace window) is a WARN, two consecutive misses is a filed P1 finding — a
scheduled job gone silent twice in a row is itself a production-health finding. When sentinel owns
the fixed pre-steps itself (an ad hoc dispatch, with no "session already ran them" note in the
brief), it also runs `python3 ~/.claude/hooks/heartbeat_audit.py < /dev/null` — the mechanical
expected-job-set diff against `oversight_install.md`'s §2 table and `launchctl list`, which is what
actually catches a job that has never fired at all (a monthly-cadence job like testarch or
trustarch has no heartbeat file yet to glob, so a raw directory listing alone is blind to it). It
always exits 0 — sentinel reads its STDOUT `violation(s)` line rather than its exit status
(`agents/sentinel.md:36-52`).

## Grounding

Runtime discipline: `knowledge/sentinel_primer.md`. Repo-local grounding:
`.claude/oversight/sentinel.md` — GCP project IDs, Cloud Run services per environment, the exact
per-dimension commands and their expected output shapes, health endpoints, and the error-rate
baseline with its capture command/date. Missing dossier is a declared DEGRADED state that restricts
it to the RUNTIME-SCOPED legs — the heartbeat audit and the health dimension's runtime-mirror-sync
leg — every app-scoped leg suppressed (`agents/sentinel.md:22-27`). An auth precondition
also gates cloud-touching work: `gcloud auth list` must show the dossier's expected account, or
every cloud-touching leg is reported BLOCKED-AUTH rather than guessed at.

## Boundaries — what it will NOT do

Never edits repo files (the queue append and its own digest are the only writes); never fixes
anything; never dispatches other agents; never pushes/PR/merges/deploys; never touches production
beyond the dossier's read-only commands. It never files, closes, or transitions issues itself —
findings route through board-steward's rules. Staging browser work belongs to product-qa, not
sentinel. Its digest opens with a one-line verdict naming the dimension actually run, one of four
tokens in precedence order `DEGRADED > BLOCKED-AUTH > findings > all clear` (the first that applies
wins — never `all clear` on a pass where any leg was suppressed or unrun) — and closes with a
`COVERAGE:` line stating what it ran vs. what it skipped and why (e.g. which app-scoped legs a
DEGRADED pass suppressed), so the digest asserts its own completeness. Every finding in between is
VERIFIED (command + output excerpt + as-of time) or UNVERIFIED — never blended
(`agents/sentinel.md:141-156`).

## How it fits with other oversight agents / the review boundary

sentinel's heartbeat audit is what launch-director's weekly report depends on to confirm the wheel
is actually turning — CLAUDE.md's framing is a watcher chain, not a line: sentinel watches every
other job daily, launch-director watches sentinel's own job weekly. sentinel never dispatches
consistency-auditor itself; the daily job's own prompt dispatches consistency-auditor on its own
slot directly. A recurring-warning finding sentinel surfaces under its `logs` dimension is the same
finding class test-architect judges as a standing test/observability-net gap — the two are meant to
cross-reference, never be filed twice, per test-architect's own definition.

## Example invocation

The daily job assigns sentinel the `logs` rotation dimension. It reads the dossier's
`gcloud logging read` recipe, finds a warning class firing several thousand times over the last 24
hours that gates nothing downstream, and reports it as a finding (not noise, per its alert-fatigue
discipline) — while separately confirming, via the heartbeat pre-step, that `com.oversight.csa.
testarch`'s heartbeat is current and no scheduled job has gone silent.
