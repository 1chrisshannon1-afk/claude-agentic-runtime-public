# Sentinel Primer

Runtime-level oversight primer. Product-agnostic: contains no app-specific paths, account names,
or counts belonging to any one repository. Distilled from external research on SRE-lite practice
for small/solo teams; every claim below carries its source, except §8 (cross-cycle loop telemetry)
and the heartbeat-audit duty in "How this agent applies it" — both are design requirements for
this agent's own operation, stated as duties, not attributed to a citation.

## 1. SRE-lite for small/solo teams

The core adaptation: apply SLOs, observability, incident response, and automation *without* a
dedicated SRE organization — a single person (or a single scheduled agent) can hold the practice,
starting from a narrow proof-of-concept and iterating rather than adopting the full discipline
wholesale on day one. An explicit warning surfaced in the research: SRE fails if it becomes a
silo — "one team/process does reliability while everyone else ships unchecked change" degrades
it into "a complaint department with dashboards." Even at team size one, reliability discipline
has to touch every change, not live in a separate checklist nobody else honors.
(Sources: "SRE for Small Teams: A Practical Guide" — Makitsol; "SRE Without the Drama:
Practical Reliability That Sticks" — DevOps Oasis; "SRE Best Practices" — InfraCloud)

## 2. Toil and the toil budget

Toil is formally defined (Google SRE) as work that is manual, repetitive, automatable,
tactical/reactive, devoid of enduring value, and that scales linearly with service growth.
Google's SRE Workbook caps SRE time spent on operational work (toil + non-toil ops combined) at
50% — the source explicitly flags that exact number as one that "may not suit every
organization." The transferable principle is not the 50% figure itself; it is *set some upper
bound* and hold to it, so operational sweeps never silently crowd out everything else. Measurement
recipe given: pick an objective unit (minutes, hours, tickets, or manual changes) and track it
continuously before, during, and after a reduction effort, rather than estimating toil
impressionistically. The smallest-team-viable tactics named: "reject toil" — decline unnecessary
manual work outright rather than absorbing it — and partial/incomplete automation, which still
cuts interrupt volume and reveals the next pattern worth eliminating even before it's fully
automated.
(Source: "Eliminating Toil" — Google SRE Workbook, https://sre.google/workbook/eliminating-toil/
— VERIFIED, opened directly)

## 3. Error budget

Error Budget = 100% − SLO. Example given: a 99.999% SLO leaves a 0.001% error budget per quarter;
one incident consuming 0.0002% of queries burns 20% of that quarter's entire budget. While budget
remains, product/dev work ships faster and can take on more risk; as the budget nears zero, the
team self-regulates toward more testing and slower release velocity. The stated purpose is
explicitly political as much as technical: it removes outage negotiation by giving both
reliability-minded and velocity-minded stakeholders one shared, objective number instead of an
argument.
(Source: "Embracing Risk" — Google SRE Book, https://sre.google/sre-book/embracing-risk/ —
VERIFIED, opened directly)

## 4. Synthetic monitoring

Scripted checks that replay real user journeys from external vantage points at set intervals —
this is what catches "the site is up but the actual flow is broken," a failure mode a bare
ping/uptime check cannot see because it never exercises the flow itself. Startup-sizing guidance:
prioritize which flows get synthetic coverage by revenue impact, customer impact, brand exposure,
and prior-incident history — not "monitor everything," which is itself a toil sink. Named
low-cost small-team tools: UptimeRobot (generous free tier) and Hyperping (flat-rate monitoring +
on-call + status page).
(Sources: UptimeRobot, "What Is Synthetic Monitoring?"; dev.to, "Synthetic Monitoring Best
Practices for Optimal Uptime")

## 5. Alert fatigue avoidance

Stated design rule: "if an alert fires and the on-call [operator] can't take a specific action,
the alert shouldn't exist." Concrete practices: every alert carries context — severity plus a
concrete next step, not just a symptom; dedupe/group repeated firings into a single notification
rather than one per occurrence; tune thresholds from historical data rather than arbitrary
defaults picked at setup time; auto-suppress lower-priority alerts when a related higher-priority
one is already firing (inhibition), since the lower-priority signal adds no new information once
the root cause is already flagged; silence alerting during declared maintenance windows so
expected noise doesn't erode trust in the channel.
(Sources: Rootly, "Alert Fatigue"; Better Stack, "Alert Fatigue Best Practices"; Icinga, "Alert
Fatigue in Monitoring")

## 6. Deploy/config-drift detection

Drift is live infrastructure state diverging from the IaC-declared desired state via
manual/out-of-band changes. The best practice found: run automated drift detection both
immediately after every deploy AND on a standing maintenance-window schedule — not only ad hoc or
on-demand. The after-deploy check catches drift introduced by the deploy itself; the standing
schedule catches drift introduced by anything else (a manual console change, an out-of-band
config edit) between deploys.
(Sources: Spacelift, "Drift Detection"; HashiCorp, "Detect Configuration Drift" —
Well-Architected Framework)

## 7. Error-log review rhythm

Cadence should scale with release risk: daily during active testing or as a release nears,
2–3×/week in steady state. Keep the review session itself to 15–30 minutes — a longer session is
a sign the cadence is too sparse, not that the review needs to be deeper each time. Rotate who
owns the review (daily or weekly per-person rotation) rather than making it one person's
permanent toil — directly transferable to a rotation between a human operator and a scheduled
review agent/session, so the review duty itself doesn't become an unbounded toil sink for one
party.
(Source: same cadence guidance corroborated across bug-triage sources — Bugreel, "Bug Triage
Process Guide"; Atlassian, "Bug Triage" — applied here to error-log review specifically per the
source research's own cross-application)

## 8. Self-correcting loop telemetry — cross-cycle cost and honesty (added 2026-08-28)

**INERT UNTIL WIRED — read this line before anything else in this section.** Everything below
documents this leg's design; none of it is a standing duty until an operator wires the `cost`
rotation slot's job prompt/dossier to actually invoke it (see the activation bullet under "How
this agent applies it" below). Do not run this leg unprompted, and do not report it as already
active.

Not external research — this runtime's own hard-won operational evidence, stated as a duty like
the heartbeat-audit below. Any self-correcting agent loop (a finder/consolidator/verifier pipeline
that re-runs itself against a corpus, in any repo, for any domain) emits one **cycle record** per
run at the canonical, repo-agnostic path `~/.claude/telemetry/cycles/<system>/<cycle_id>.json`.
The schema (schema_version 1 or 2 — v2 additive over v1, see `~/.claude/telemetry/schema.json` —
TRACKED (corrected 2026-08-28: `.gitignore`'s `telemetry/*` blanket ignore carries explicit
`!telemetry/schema.json` / `!telemetry/README.md` negation entries, so these two files ship on a
fresh checkout like any other runtime config; only the per-cycle JSONL/JSON runtime DATA under
`telemetry/cycles/` remains gitignored and absent there — DEGRADED if schema.json is unreadable
despite being tracked, per `agents/agentic-systems-architect.md`'s Read FIRST #5 git-state caveat),
full field list, and the seven derived-metric formulas
(`symptom_precision`, `cause_precision`, `duplicate_rate`, `ruling_conflict_rate`,
`plant_catch_by_slot`, `usd_per_confirmed_defect`, `consolidation_ratio`) are the shared runtime
contract documented in `agentic_systems_architect_primer.md`'s cycle-telemetry schema section — that
document is the schema's source of truth; this section states what THIS agent (a lighter, more frequent watcher, not the
deep periodic audit) does with it.

**Division of labor, load-bearing:** a daily sweep cannot afford the deep ledger-correspondence
reconciliation (time window + agent-type set + count + REQUIRED declared dispatch identity —
FOUR signals, not three, against `~/.claude/.agent_budget/spend.jsonl`) that
`agentic-systems-architect` performs on its own
cadence — that work stays there, in full, unduplicated here. This agent's job is cheaper and
repeats more often: read what each cycle record says about itself, trend it across cycles for the
same system, and flag when the record's own self-description is untrustworthy or degrading. It
never re-verifies the ledger from scratch, and it never stops a cycle in progress — a separate
mechanical guard owns stopping a runaway cycle in real time; a once-a-day sweep structurally
cannot see today's burn until tomorrow, so this agent's role is trend/health watch, never an
interrupt.

**Telemetry-honesty findings (ranked by specificity — check these before any cost/value trend,
because a dishonest or unresolved input poisons the trend built on top of it). Each cycle record
is counted ONCE, in its single most-specific matching category among the THREE below, never once
per rule it happens to satisfy — a record can trip more than one predicate, and de-duping this way
is what stops one defective record from manufacturing more than one finding (e.g. a spurious
"pipeline regression" finding from otherwise-flat data):**
1. A cycle record whose `cost.source` is `"unavailable"` — the producer's own HONEST-REFUSAL
   signal (`~/.claude/hooks/cycle_telemetry.py`'s `resolve_cost()`: it could not confidently
   attribute spend to this cycle and declined to guess, carrying a `cost.reason`). This is a
   DIFFERENT failure mode from (2) below, never merged with it — a record that honestly says "I
   don't know" is not the same problem as one that reports a possibly-fabricated number. Report as
   **UNKNOWN (source: unavailable — <cost.reason>)**, never real spend and never folded into an
   UNVERIFIED count.
2. A cycle record whose `cost.source` is `"reported"` (and not `"unavailable"` — (1) always takes
   priority). Per the primer's cycle-telemetry motivating case, a harness-reported cost figure was once found ~26× lower
   than the real, ledger-derived spend. Report a `"reported"`-sourced cycle's numbers as
   **UNVERIFIED**, never as real spend, and never let one enter a cost/value trend average
   silently.
3. A cycle record whose `cost.source` is `"spend_ledger"` but with a missing/null `cost.total_usd`
   despite a non-empty `dispatches[]` — the ledger did not cover it. Report as **UNMEASURED**,
   never a passing zero: a $0 loop and an unmeasured loop look identical in a naive sum, and only
   one of them is actually free.

Outside that per-record dedup scope — these are CROSS-CYCLE trend categories, computed FROM the
per-record counts above, never additional buckets a single record is counted into:
- A RISING COUNT, cycle over cycle for the same system, of (1) or (2) — tracked as two SEPARATE
  counts, never merged, since they are different failure modes with different remedies (fixing an
  honest-refusal attribution gap is not the same fix as stopping a harness field from fabricating
  numbers). A single occurrence of either may be a one-off gap; a climbing fraction of either is a
  telemetry-pipeline regression, reported as exactly that, not as a cost problem.
- Any derived-metric computation (the primer's seven cycle-telemetry formulas, or a discovered oracle script) that fails
  to resolve — missing denominator, script error, field absent from every record in scope. Report
  `UNMEASURED: <reason>` for the systems/cycles it could not be computed for; never substitute a
  zero or average silently over only the cycles where it resolved.

**Cost/value trend findings (computed ONLY from `cost.source == "spend_ledger"` cycles — neither a
`"reported"` nor an `"unavailable"` cycle's numbers ever enter these averages, for the different
reasons named in categories (1)/(2) above):**
- `usd_per_confirmed_defect` rising across consecutive cycles for the same system.
- Total `cost.total_usd` trending up while `count(findings where verifier_verdict in
  {CONFIRMED, PARTIALLY_CONFIRMED})` is flat or falling for the same system (the same
  CONFIRMED-union-PARTIALLY_CONFIRMED set `usd_per_confirmed_defect` itself uses as "a defect" —
  see `hooks/cycle_telemetry.py`'s `usd_per_confirmed_defect()`, never re-derive this denominator
  by hand) — more expensive for less value, the clearest "stop and look" signal a cross-cycle view
  produces that a single cycle's own report cannot.
- A cycle overrunning a ceiling — only when a ceiling is actually discoverable for that system (the
  schema defines no ceiling field as of this writing; discover one the same way the primer's
  cycle-telemetry metrics oracle is discovered — a documented budget/ceiling value inside the cycle record itself, or a
  sibling per-system config file — never assume a field name, never invent a number). No
  discoverable ceiling ⇒ N/A for that system, never "no overrun."

**Repo-agnostic sweep, always:** glob every `<system>` directory under
`~/.claude/telemetry/cycles/` and cover all of them in one sweep; a finding scoped to only one
system when others have records is undercoverage. No product/system name may appear in this primer
or in `agents/sentinel.md` as anything but a documentation example. A `<system>` with zero cycle
records, or the whole `~/.claude/telemetry/cycles/` tree not existing yet, is DEGRADED for this
dimension, stated explicitly — never treated as "nothing to report."

---

## How this agent applies it

- **Sweep composition**: a scheduled sweep runs error-log review, deploy-drift detection, and a
  synthetic-monitoring check on the prioritized flows, at the cadence in §4/§6/§7 — tightening
  during active testing or near a release, relaxing to steady-state frequency otherwise.
- **Toil and alert-fatigue discipline apply to the sweep itself**, not just what it's monitoring:
  if a sweep finding recurs unchanged with no actionable next step available, that is itself a
  finding — per §2, reject or automate the toil rather than repeating it forever; per §5, a
  recurring finding with no specific action attached should not keep generating fresh noise.
- **Heartbeat-audit duty — runs FIRST, before any other sweep work.** Before doing anything else,
  verify every other scheduled job's heartbeat file is within its expected cadence plus a grace
  window. One missed heartbeat is a warn (logged, not escalated). Two consecutive missed
  heartbeats is filed and notified — a scheduled job that has gone silent twice in a row is itself
  a production-health finding, since a sweep that silently stopped running is worse than one that
  ran and found nothing. **Dedup with the dispatching session:** the daily job's own session runs
  this same heartbeat audit itself as its fixed pre-step A before it ever dispatches this agent —
  run this duty yourself ONLY when dispatched ad hoc, without a brief stating the session already
  did it, so the audit never runs twice for the same day's pass.
- **Findings never get filed directly by this agent.** Every finding — including a heartbeat
  failure — routes through the board steward's filing rules (see `board_steward_primer.md`): its
  disposition, labeling, and duplicate-check happen there, not here. This agent detects and
  reports; it does not maintain the tracker.
- **Once wired (see the "Activation is the operator's" bullet below) — INERT UNTIL THEN — the
  loop-telemetry sweep (§8) rides the existing cost dimension**, not a new schedule slot: once
  activated, it runs whenever `cost` is the assigned rotation dimension, alongside the existing
  spend/churn legs, with the same VERIFIED/UNVERIFIED discipline as every other finding this agent
  produces.
- **Lane discipline for §8 is absolute:** this agent reports the trend and the telemetry-health
  finding and stops there. It never throttles, pauses, reconfigures, or otherwise touches a
  running loop, and never writes under `~/.claude/telemetry/`. Stopping a cycle already overrunning
  its ceiling in real time is a separate mechanical guard's job, not this agent's — a sweep that
  runs at most daily cannot see today's burn until tomorrow.
- **Activation is the operator's, not this agent's.** This primer documents the sweep's design; it
  does not run until an operator wires the `cost` rotation slot's job prompt/dossier to actually
  invoke it. This agent does not modify `schedules/`, does not start any job, and treats §8 as
  inert prose until told otherwise.
