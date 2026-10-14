# browser-ops

`browser-ops` drives a single, orchestrator-assigned browser pool slot to observe and act on live
web surfaces, then reports structural facts back — page titles, URLs, HTTP statuses, element/row
counts. It exists to give sessions real browser-driven verification (does the page actually render,
does the flow actually work) without any one agent holding standing, unscoped access to a live
browser or to credentials — every constraint in its doc traces back to that single design goal.

## Model & tools

- **Model:** `sonnet` (frontmatter, `browser-ops.md:4`)
- **Tools:** `Read, ToolSearch`, plus the full enumerated `mcp__playwright-01__*` through
  `mcp__playwright-12__*` tool sets (`browser-ops.md:5`) — one entry per numbered pool slot, per
  action (`navigate`, `snapshot`, `click`, `type`, `fill_form`, `select_option`, `hover`,
  `press_key`, `wait_for`, `navigate_back`, `tabs`, `take_screenshot`, `resize`, `console_messages`,
  `network_requests`, `handle_dialog`, `file_upload`, `close`). This is the most structurally
  different tool grant in the dev-workflow slice: no `Bash`, `Edit`, `Write`, `Glob`, or `Grep` at
  all — its only way to act on anything is through a leased browser slot or to `Read` a local file.

Two things about this grant matter practically:
- **The grant is enumerated per action and per slot, and deliberately excludes every
  JS-evaluation tool** (`browser_evaluate`, `browser_run_code_unsafe`) and both non-pool servers —
  the unleased `playwright-adhoc` and the separately-leased `playwright-auth` capture slot (its own
  `claim-auth`/`release-auth` lifecycle, never `browser-ops`'s). Its own doc explains why: "Since the 2026-07-24
  operator override there is NO origin-enforcing hook on the numbered slots... the allowlist is
  ADVISORY... your tool grant is ENUMERATED per slot and excludes every JS-evaluation tool... with
  no origin hook, the grant is the only mechanical boundary" (`browser-ops.md:26-59`). In other
  words: normally the runtime's `~/.claude/live-testing/allowlist.json` policy would gate which
  origins/tenants are in play, but for the numbered slots that gate doesn't actually exist as a
  hook — so the tool grant itself (no eval, no adhoc, no auth) is the mechanical half of
  enforcement; the STAGING-default rule and the `denied_action_patterns`/`test_recipients`
  obligation the same section adds are the behavioral half, since the grant alone still leaves
  click/type/fill_form/file_upload usable against any origin the agent is pointed at.
- **The frontmatter grants tools for all 12 slots at once**, but the agent is only ever supposed to
  use the one slot number the orchestrator hands it — see Boundaries below. The mechanical boundary
  is "no eval / no adhoc / no auth / no bare unpooled server," not "only slot NN's tools are
  callable."

## When it's dispatched

On-demand, whenever an orchestrator has already claimed a free pool slot (via
`python ~/.claude/live-testing/browser_pool.py claim`, per `~/.claude/CLAUDE.md` §12) and needs
that specific slot driven for a task — a staging walkthrough, a live functional check, a UI
verification step. The orchestrator owns the entire lease lifecycle (claim → renew → release);
`browser-ops` is invoked only after a slot is already leased and handed to it by number.

## What it does

Before its first browser action, it must call `ToolSearch` naming exactly the deferred
`mcp__playwright-NN__*` tools it will use for its leased slot — e.g.
`select:mcp__playwright-07__browser_navigate,mcp__playwright-07__browser_snapshot,mcp__playwright-07__browser_click`
(`browser-ops.md:19-24`). A `ToolSearch` that returns nothing for its slot is a report-and-stop
condition, not a reason to try a different slot.

STAGING is its default target — it drives production only when the task prompt itself relays an
explicit operator go-ahead for that specific run (`browser-ops.md:27-31`). It navigates only to
origins its task names AND the allowlist permits for that environment, and stops and reports on
anything else — it treats the (advisory-only) allowlist as a policy it follows by instruction, since
there's no hook enforcing it mechanically (`browser-ops.md:32-42`). Before any state-mutating or
message-sending action it reads the allowlist's `denied_action_patterns`/`test_recipients` and
refuses a payment/billing/comms-provider surface, an ads-billing/checkout path, an `*/admin/*` path,
or any recipient outside `test_recipients` (`browser-ops.md:47-52`). On any slot or tool error
— busy, crash, navigation blocked/denied — it stops immediately and reports the slot id plus the
full error; it does not retry on another slot (`browser-ops.md:72-73`).

Every response reports the slot id, the actions taken, the resulting page title + URL, HTTP status
codes where relevant, and structural counts (`browser-ops.md:93-95`) — never raw page content from
an authenticated page.

## Grounding / inputs

Unlike the other seven agents in this slice, `browser-ops`'s use of `<repo>/.claude/oversight/dev-runtime.md`
is deliberately partial: "Read it (your tool grant has no Grep, so this means reading the whole
file) and use ONLY its 'Local dev ports' section (which local port is which app) — ignore the rest.
Every other fact you need (origins, tenants, recipients) is owned by the runtime allowlist below,
never by that file" (`browser-ops.md:11-17`). If that file, or its "Local dev ports" section, is
missing AND the task prompt doesn't name the port either, it says so in the first line of its
report, declares that dimension DEGRADED, and stops — it never guesses a port or assumes a
conventional default. This is a genuine, intentional divergence from the other seven agents'
full-dossier grounding — worth knowing explicitly rather than assuming the pattern is identical
everywhere.

## Boundaries — what it will NOT do

- **Never picks production as where to test** — STAGING is the default target; production is driven
  only on an explicit operator go-ahead relayed through the task prompt for that specific run
  (`browser-ops.md:27-31`).
- **Never self-claims, self-renews, switches slots, or invokes the pool manager** — the orchestrator
  owns the full lease lifecycle; `browser-ops` uses only the one slot it was assigned
  (`browser-ops.md:69-71`).
- **Never drives the bare, unpooled `playwright` server** (the global `~/.claude.json` entry with no
  isolation/origin flags, never a leasable slot) — and is not granted it (`browser-ops.md:62-68`).
- **Never drives a denylisted surface or messages a non-test recipient** — before any state-mutating
  or message-sending action it reads the allowlist's `denied_action_patterns`/`test_recipients` and
  refuses a payment/billing/comms-provider surface, an ads-billing/checkout path, an `*/admin/*`
  path, or any recipient outside `test_recipients`; never creates, modifies, or deletes an
  identity-provider account (`browser-ops.md:47-52`).
- **Never passes a password, OTP, token, or API key as a literal tool argument**, and never logs in
  itself — a slot arrives unauthenticated unless the orchestrator already logged it in on that same
  slot (the live `.mcp.json` gives numbered slots no `--storage-state`, so nothing persists across a
  slot restart); if a task needs an authenticated page and the slot isn't already authenticated, it
  stops and reports rather than logging in (`browser-ops.md:76-83`).
- **Never returns secrets, tokens, cookies, JWTs, or PII/PHI** — only page title/URL, HTTP status
  codes, element/row counts, and other structural facts (`browser-ops.md:84-85`).
- **Never emits full-page snapshots or screenshots of authenticated pages** — "they capture verbatim
  sensitive content. Prefer targeted structural assertions." (`browser-ops.md:86-87`)
- **Never retries on a different slot after an error.**

## How it fits with other agents

`browser-ops` is invoked only after the orchestrator has already done the pool-management work
(`~/.claude/CLAUDE.md` §12) — it never manages its own lease. It is the mechanism behind live
verification steps that `implement`/`test-runner` cannot provide (they operate on code
and local test runs, not a rendered browser). Its findings route back to the orchestrator like every
other agent in this slice; it never dispatches other agents. It is closely related to, but distinct
from, `product-qa` (an oversight-roster agent that also drives numbered Playwright slots for
scripted staging walkthroughs scored against usability heuristics) — `browser-ops` is the generic,
on-demand driver any orchestrator can dispatch for a one-off browser task, while `product-qa` is a
persona-scripted, scheduled/weekly QA agent with its own review discipline.

## Example invocation

After deploying a fix to staging, the orchestrator claims a free pool slot (say, slot 04) and
dispatches `browser-ops` with that slot number and the exact staging URL/flow to check — e.g.
"navigate to the staging billing settings page and confirm the new discount field renders with a
200 status" — expecting back the slot id, the actions taken, and the resulting page title/URL/status,
with no credentials or page content beyond structural facts in the response.
