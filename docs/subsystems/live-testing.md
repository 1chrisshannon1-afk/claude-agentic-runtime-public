# Live Testing

**Maturity: optional.** Not part of the core gate chain. The hook described below is enforcing; the
slot pool is convenience tooling; and there is no network-level enforcement for MCP slots yet (see
"Where the policy is and is not enforced").

*Orienting doc for `live-testing/`. The field reference for the policy file, the rules the hook
applies, and the notes on how the test suite treats the policy are in
[`live-testing/README.md`](../../live-testing/README.md). Read it in full before driving a slot that
can reach a production host. This page orients and points there.*

## The rule

An agent drives a real browser only through a leased slot and inside a written policy, and a hook
enforces the policy. `hooks/block_prod_mutations.py` is a `PreToolUse` hook registered on the
`mcp__playwright.*` tools. It reads `live-testing/allowlist.json` on every call and denies:

- a write to a host outside the policy's origins;
- a write to a billing, messaging or admin endpoint named in the policy;
- a comms write whose recipient is not a listed test recipient;
- a request carrying an off-list tenant id, on a tenant-scoped host;
- an interaction-class tool (click, type, fill, evaluate, ...) on a production host listed in the
  policy, or on a slot that has navigated nowhere (no exception applies to that case), except where a
  host has a scoped
  `interactive_production_hosts` entry and for one fixed session-banner snippet (both described in
  `live-testing/README.md`).

A missing or unreadable policy denies every write and every interaction tool; the hook never falls
back to a default. Like every gate in this runtime it blocks only when enforcement is on; otherwise
it records what it would have denied and lets the call through. It does not limit plain navigation
(GET) to a host, with one exception: a GET carrying an off-list tenant id on a tenant-scoped host is
still denied.

## What this is

Playwright and all live-testing infrastructure are part of the **runtime**, not product code: it is
how agents test, not something any one app ships. The `browser-ops` agent (and `product-qa`) drive
it; both are least-privilege by tool grant (see "Where the policy is and is not enforced").

```
live-testing/
  README.md                 field reference for the policy file and the hook's rules
  allowlist.example.json    generic seed for allowlist.json (localhost and example.com only)
  allowlist.json            your policy: per machine, never published; copy it from the example
  browser_pool.py           pool/lease manager CLI
  tests/                    tests for the pool
```

A maintainer's own checkout also carries private helpers (production login and capture tooling, a
decision layer for direct Playwright use, a data-governance note). They are not published, and
nothing on this page depends on them.

## The pool: 12 numbered slots + auth + adhoc

There are **twelve independent numbered browser slots** (`playwright-01` ... `playwright-12`), plus
`playwright-auth` and `playwright-adhoc`. Never assume one shared browser and never hardcode
`playwright-01`; always claim a slot:

```
python ~/.claude/live-testing/browser_pool.py claim --label "..." --ttl 900
```

which returns a free slot name, and release it the same way when done. The pool self-heals a corrupt
registry (rebuilds from scratch, fail-open, only when no slot has a live owner per `ps`) and stores
everything under `~/.claude/.browser_pool/` (registry, per-slot/auth leases, merged storage-state
jar, per-service captures), all mode `0600`.

Slot tools (`mcp__playwright-NN__*`) are **deferred**: an agent must call `ToolSearch` first with
`select:mcp__playwright-NN__browser_navigate,...` naming the exact tools it needs, and any agent
granted a numbered/`-auth`/`-adhoc` slot must also be granted `ToolSearch`. The bare, unpooled
`mcp__playwright__` server (in `~/.claude.json`, no isolation/origin flags, not a leasable slot) is
never granted to any agent: it is prohibited outright, alongside a wildcard/JS-eval/`adhoc` grant,
on a pooled agent (`browser-grant-not-least-privilege`).

## Where the policy is and is not enforced

`allowlist.json` is the single source of truth: origins, tenants, test recipients, URL patterns that
a write may never reach, and the production hosts on which interaction is denied. Its keys and the
order in which the hook applies its rules (R0 to R5) are in `live-testing/README.md`. It is consumed
by `hooks/block_prod_mutations.py` on every call and by `browser_pool.py`.

The nuance to hold onto: **slot launch flags are not an origin control.** `browser_pool.py`'s
`_server_entry_numbered()` computes the `--allowed-origins` and `--blocked-origins` values from the
policy and then discards them (an operator override recorded in the code, 2026-07-24: headed real
Chrome, no origin allowlist at launch). The entries it generates start each numbered slot with only
`--isolated --browser chrome --output-dir <cache dir>`, plus `--storage-state <jar>` when a staging
jar exists. For MCP-driven runs the enforcement is therefore the hook above plus the agent's own
**enumerated tool grant**: no `browser_evaluate` or `browser_run_code_unsafe` on an agent driving
authenticated pages, and no `-adhoc` grant. A network-level layer that applies the same policy to
MCP traffic would close the remaining gap; it does not exist yet.

## Credentials

Never typed from memory, never guessed, never echoed into logs or summaries, never inlined in a
script. They are fetched **live from a secret manager at the moment of use**. A staging login comes
from the secret store on demand; a production login does not use a saved storage-state jar, and the
skill's recipe is to log in fresh each session with the fetched password.

## Two lanes

- **Lane A: sandbox** (the default for autonomous flows): a zero-value staging company, no real
  PII, safe by construction.
- **Lane B: a production tenant with real customer data.** Autonomous access needs a data-governance
  determination signed by the operator before the first run; the determination itself lives in a
  maintainer's private checkout. The technical mitigations stay active regardless: `redact_browser_phi`
  (a `PostToolUse` hook that, under enforcement, emits a scrubbed copy of browser tool output), the hook's deny rules
  including the interaction denial on production hosts, a capture reaper, and a skill rule against
  full-page snapshots of authed production pages. `redact_browser_phi`'s named-cookie/JSON-key
  redaction set is manifest-driven: generic defaults (`session`, `refresh_token`, `auth_token`)
  unioned with the calling repo's own `security.auth_cookie_names` from
  `<repo>/.claude/oversight/manifest.json`. **A repo onboarding onto Lane B with a differently-named
  real auth cookie must set this key in its manifest, or that cookie is never redacted**: the generic
  defaults alone do not cover a product-specific cookie name. Same mechanism, same doc-citation
  pattern as `review_risk_tier.py`'s `security.extra_risk_keywords`
  (`docs/subsystems/review-ladder.md`); `scripts/repo_manifest.py validate` checks the key's shape
  but not its coverage.

This runtime doc does not override a product repo's own rule about where to test (staging by
default; production only on explicit human instruction). That rule governs which lane an agent
*picks*; this page and the README govern how the infrastructure behaves once picked.

---

For the complete field-by-field reference, see [`live-testing/README.md`](../../live-testing/README.md).
