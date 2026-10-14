# observability-architect — repo-local grounding dossier (__PRODUCT_NAME__)

Facts file for the runtime `observability-architect` agent (opus, findings-only, dispatch-only).
Discipline lives in `~/.claude/knowledge/observability_architect_primer.md` and the sourced
doctrine in `~/.claude/knowledge/observability_logging_doctrine.md`; this file carries this app's
own logging and observability facts only. Every count carries its re-derive command + an as-of
date. VERIFIED = read, grepped, or run live this pass; anything else is carried forward, not
re-measured. A missing or stale section here means the agent declares itself DEGRADED and audits
only repo-discoverable state, saying explicitly what it could not ground.

## (a) Subsystem scope

*What goes here: the critical flows and subsystems the audit judges, one row each. The dossier's
inventory sets the audit's scope, and the verdict report says "reviewed X of Y subsystems in
dossier scope", so an incomplete list silently narrows the audit.*
Re-derive: the subsystem list is hand-curated; re-check it against `` `ls -d __MODULES_ROOT__/*/` ``.

- __OBSERVABILITY_SUBSYSTEM_ROW__ — *repeat per subsystem: name | entry paths | external call
  boundaries (payments, datastore, AI provider, third-party APIs) | logger in use | alerts that
  cover it.*

## (b) Logger inventory and adoption

*What goes here: which loggers and wrappers exist, how widely the structured wrapper is used
against plain stdlib logging, what the formatter actually emits, and what redaction runs. A
module that bypasses the structured wrapper cannot be DEBUGGABLE however much it logs, because
none of it is redacted, correlated, or consistently shaped.*
Re-derive: `` `grep -rn "__STRUCTURED_LOGGER_MODULE__" __BACKEND_ENTRY_PATH__ | wc -l` `` against the
plain-logger count in the block at the end of this file.

- Structured wrapper: `__STRUCTURED_LOGGER_MODULE__`. Modules that bypass it and call stdlib
  logging directly: __PLAIN_LOGGER_COEXISTENCE__.
- Severity emission: __LOG_SEVERITY_FORMATTER_NOTE__ — *what the formatter emits for warning and
  critical levels, checked against the cloud logging severity enum. A silent mismatch quietly
  mutes a whole class of alerts, so state the checked result and the file it was read from.*
- Redaction: __REDACTION_MECHANISM__ — *what runs, where, and whether it covers nested dicts,
  exception-embedded values and URL query strings (the most-missed shapes).*

## (c) Where logs land, correlation, and how to read them

*What goes here: the log sink and retention, the trace or request id mechanism and where it is
injected, and the working command to read recent logs. Correlation has to survive async and
background-task boundaries; "the mechanism exists somewhere in the repo" is not coverage.*
Re-derive: `` `__LOG_READ_COMMAND__` `` and `` `__LOG_READBACK_RECIPE__` ``.

- Sink and retention: __LOG_SINK_AND_RETENTION__.
- Correlation: __CORRELATION_MECHANISM__ — *id name, where it is created, where it is injected,
  and which boundaries are known to drop it.*

## (d) Alerting and notifier layer

*What goes here: every alert, notifier and paging rule, the field each one filters on, and its
documented coverage gaps. The agent checks that the filtered field is actually emitted by current
code (a dead check), that each alert passes the three-question page test, and that it is
symptom-based rather than cause-based.*

- __ALERT_INVENTORY__ — *per alert: name | filter field | the code that emits that field |
  severity | who is paged.*
- Error-rate baseline owner: __ERROR_RATE_BASELINE_OWNER__. External uptime monitor:
  __UPTIME_MONITOR_SERVICE__.

## (e) Telemetry consumers (for the dead-telemetry check)

*What goes here: the named consumers of each signal (dashboard, alert, documented runbook query).
A signal with no named consumer after a real search is a removal candidate, named as such, never
silently dropped from the report.*

- __TELEMETRY_CONSUMERS__

## (f) Sensors the agent interprets (never recomputes)

*What goes here: any deterministic scanner whose output is an adjacent signal for logging
discipline. The `bare_except`, `except_pass` and `print_calls` metrics of the code-debt scan are
a partial proxy and belong to `code-quality-architect`: cite them with attribution, never
recompute them. If no dedicated logging-quality scanner exists, say so here; that absence is a
finding in its own right (an unmeasured surface), never treated as clean.*
Re-derive: `` `python3 __CODE_DEBT_SCANNER_PATH__ report` ``.

- Code-debt scanner: `__CODE_DEBT_SCANNER_PATH__`, ledger `__CODE_DEBT_LEDGER_PATH__`.
- Surfaces no scanner covers: __SCANNER_COVERAGE_GAPS__.

## (g) Known-and-accepted gaps (report WITH rationale, never as fresh findings)

*What goes here: logging and observability gaps already recorded with an operator ruling or an
open tracked issue. A first audit reports the stock once as a baseline; from a second audit
onward findings are ranked by delta since the last audit.*

- __OBSERVABILITY_ACCEPTED_GAPS__

## (h) Out of scope for this agent in this repo

*Hand-off map to sibling agents for adjacent lanes this agent never claims.*

`__OUT_OF_SCOPE_HANDOFF_MAP__` (for example: a single diff's logging checklist items →
`code-reviewer`; dead telemetry judged as test-net sufficiency → `test-architect`; the same
pattern judged as agentic-system design → `agentic-systems-architect`; a gap on an auth, billing,
webhook or secrets path → flagged for `trust-architect`; debt-scan metrics → `code-quality-architect`;
issue filing → the orchestrator via `board-steward`'s rules).

## First assignment

__FIRST_ASSIGNMENT__

## How to re-derive

```bash
__RE_DERIVE_COMMAND_BLOCK__
```
