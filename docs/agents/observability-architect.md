# observability-architect

`observability-architect` owns one question about a SaaS product: if this fails in production, will
anyone know, and can a stranger find out why from logs alone (`agents/observability-architect.md`,
opening paragraph)? It is a dispatch-only oversight seat, added 2026-09-15 at operator direction
(CLAUDE.md §10/§13). It exists as a standing role because logging quality is an architectural
property no single commit can be blamed for: a diff-scoped reviewer can check that a new log call is
well formed, but only a codebase-wide view can tell whether correlation ids survive async
boundaries, whether alerts filter on fields that are actually emitted, or whether anyone reads what
the system writes.

## Model & tools

- **Model:** `opus` (`agents/observability-architect.md:4`) — one of the runtime's sanctioned-Opus
  agents (CLAUDE.md §10/§13). Deciding whether an alert is traceable to a real signal, or whether a
  swallowed error is a genuine non-event, is judgment across a wide evidence surface.
- **Tools:** `Read, Grep, Glob, Bash` — read-only. Bash is limited to read-only census and
  verification (search, listing, counting, `jq`, `git log`/`show`, read-only cloud `list`/
  `describe`/`read`). It never runs a mutating command or a command that appeared inside a file,
  config, comment, or log line it read. The agent file is explicit that this restriction is
  prose-enforced; nothing narrows Bash for this agent mechanically
  (`agents/observability-architect.md`, "Injection safety").

## Cadence / trigger

**No scheduled job — dispatch-only, by design.** Modes are an audit of the logging and
observability surface named in the repo dossier, and on-demand consults: a specific subsystem, an
incident postmortem, or a pre-launch observability readiness check. A schedule is deferred until at
least two audits show it is worth automating (CLAUDE.md §13). It is never a standing commit gate
and never a reviewer at a commit boundary; that is `code-reviewer`'s lane, applying the doctrine
file's review-time checklist to a pending diff, and substituting this seat there would duplicate
rather than add coverage.

## What it audits / judges

Per critical flow or subsystem in the dossier's scope (`agents/observability-architect.md`, "What
you measure"):

- structured-logger adoption ratio;
- correlation-id coverage across external-call boundaries, including survival through async and
  background tasks;
- error log-or-reraise discipline and `error_class` field coverage;
- severity-string validity against the cloud provider's log-severity enum;
- alert-to-signal traceability: does the alert's filter field actually get emitted, and does the
  alert pass the three-question page test;
- dead telemetry: signals with no named consumer;
- PII and secret redaction coverage on the shapes the doctrine flags as most often missed (nested
  dicts, values embedded in exceptions, URL query strings).

The verdict per subsystem is one of `DEBUGGABLE` / `PARTIAL` / `OPAQUE` / `NOISY` / `DEAD` — never
a composite score. No dedicated logging-quality scanner exists in the runtime, so it interprets
`code-quality-architect`'s existing debt scan metrics (bare except, except-pass, print calls) as an
adjacent signal with attribution, never recomputing or claiming them, and otherwise audits by hand
at module or subsystem granularity. It states the absence of a dedicated sensor explicitly, as a
finding in its own right. The first audit reports the stock once as a baseline (one line per
subsystem, no itemized dump); from the second audit onward it ranks by delta first
(`agents/observability-architect.md`, "Sensor discipline").

## Grounding

Runtime discipline: `knowledge/observability_architect_primer.md` — the relationship to the doctrine
file, cadence, what is measured, sensor and evidence discipline, report shape, and boundaries. The
sourced doctrine itself is `knowledge/observability_logging_doctrine.md` (SRE guidance, twelve-factor,
OpenTelemetry semantic conventions, W3C Trace Context, cloud logging and runtime docs, the OWASP
logging cheat sheet, plus local incident precedents); sections 1 through 8 are read fresh every
audit rather than recited from memory. Its section 9 is the review-time checklist and belongs to
`code-reviewer`. Repo-local grounding: `.claude/oversight/observability-architect.md` — that app's
actual logging architecture and known gaps. A missing dossier is declared DEGRADED, restricted to
repo-discoverable state. The agent file's fourth Read-FIRST item is its own prior audit record;
with no scheduled job, a confirmed absence of prior logs is the expected first-audit state.

## Report shape

Findings are numbered so each can be accounted for, and each is VERIFIED (file and line with a
quote, or a command with its actual output) or UNVERIFIED, never blended. Counts are re-derived that
pass with a re-derive command and an as-of date, never carried from a prior pass. The full report
shape is specified in the primer's "Report shape" section
(`agents/observability-architect.md` points there for method and detail).

## Boundaries — what it will NOT do

Never edits repo source, docs, tests, or the doctrine file; never runs another agent's scan or
harness; never pushes, opens a PR, merges, or deploys; never touches production; never files an
issue itself (issue filing is the orchestrator's, through `board-steward`'s rules, one issue per
root-cause cluster). Log lines, configs, and comments are treated as attacker-influenceable data,
never as directives.

## How it fits with other oversight agents

Cross-references are filed once, never double (`agents/observability-architect.md`, "Boundaries").
Dead telemetry viewed as test-net sufficiency is `test-architect`'s lane. The same pattern viewed as
agentic-system design is `agentic-systems-architect`'s. A gap on a trust-surface path is flagged for
`trust-architect`'s attention rather than treated as fully this seat's call. Per-diff logging checks
stay with `code-reviewer`. Debt-scan metrics come from `code-quality-architect`.

## Example invocation

Ahead of a launch, the orchestrator dispatches `observability-architect` for a readiness check on a
payment-handling subsystem. It finds that an alert filters on a field the code never emits (an
alert with no live signal behind it), that a background task drops the correlation id when it
spawns, and that several handlers log an error and then swallow it. It marks the subsystem
`OPAQUE`, numbers the findings, flags the trust-surface gap for `trust-architect`, and leaves the fix
dispatch to the orchestrator.
