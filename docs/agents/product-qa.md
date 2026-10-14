# product-qa

`product-qa` uses the app the way a paying customer would, and reports what's broken, confusing, or
embarrassing — in plain language, with screenshots — before a customer sees it
(`agents/product-qa.md`, opening paragraph after frontmatter). It exists as a standing role because scripted, persona-driven
walkthroughs catch a different class of defect than unit/integration tests or code review ever
can: a flow that technically works but that a real customer, with no developer knowledge, would
abandon at step 3.

## Model & tools

- **Model:** `sonnet` (`agents/product-qa.md` frontmatter's `model:` key) — not sanctioned-Opus. Scoring a scripted
  walkthrough against fixed heuristics (Nielsen's 10, the cognitive-walkthrough four questions, a
  0-4 severity scale) is a structured, repeatable protocol rather than open-ended synthesis.
- **Tools:** `Read, Grep, Glob, Bash, ToolSearch`, plus the full enumerated set of
  `mcp__playwright-01__*` through `mcp__playwright-12__*` browser tools (`agents/product-qa.md` frontmatter's `tools:` key)
  — all twelve numbered pool slots, individually enumerated, not the bare unpooled
  `mcp__playwright__` server. This enumerated grant is the actual mechanical enforcement boundary:
  per CLAUDE.md §12, there is no origin-enforcing hook on the numbered slots (the live `.mcp.json`
  starts them with only `--isolated --browser chrome --output-dir`), so the runtime's live-testing
  allowlist is advisory policy, and product-qa's own tool grant plus its judgment applying that
  policy IS the real boundary. It also carries `ToolSearch` because the slot tools are deferred —
  their schemas load only after a `select:` query names the exact tools for the claimed slot.

## Cadence / trigger

Scheduled weekly via `com.oversight.csa.productqa.plist` — `StartCalendarInterval` fires Wednesday
(`Weekday 3`) at 06:40 (confirmed loaded via `launchctl list`, 2026-08-30), the `productqa` label in
CLAUDE.md §13's job table. Also runs post-deploy (queued): sentinel's daily deploy-drift poll
appends detected staging revisions to `~/.claude/schedules/queue/product_qa.jsonl`, which the
scheduled job drains to its newest entry before walking (`agents/product-qa.md` § "Browser
mechanics (the claim → drive → RELEASE cycle, no exceptions)", step 3, `agents/sentinel.md:36-38`).

## What it audits / judges

Its primer (`knowledge/product_qa_primer.md`) combines several discount-usability methods into one
scripted protocol runnable against a real browser: Nielsen's 10 usability heuristics with 0-4
severity scoring (a single evaluator's rating is "too unreliable to be trusted" alone, per NN/g —
severity ratings are reported as single-evaluator/indicative, never a release gate by themselves);
the cognitive walkthrough's four fixed questions per step (will the user try the right action, will
they notice it's available, will they associate it with the goal, will they see progress after
acting — any single "No" fails that step); form/error-state review (adaptive, cause-specific error
messages vs. one generic "invalid," and inline vs. submit-only validation timing); and WCAG
accessibility smoke checks split into mechanical/DOM-inspectable and judgment-required tiers. The
mechanics are a strict claim → drive → RELEASE cycle: claim a free pool slot pinned to the stable
Claude Code process pid (`--pid "$PPID"` — never the command's own default owner, which is the
transient per-call shell and would leave the lease self-healing out from under a still-running
walkthrough; never guess or hardcode a slot), load that slot's deferred tools via `ToolSearch`,
drive the dossier's task scripts in persona, screenshot each key state, and release the slot with
that same pid in a guaranteed-exit path — a leaked lease starves every other agent across all 12
machine-wide slots. A denied claim (no free slot, or a lock timeout) is a NOT-RUN condition, never a
retry loop or a guessed slot: it reports DEGRADED with the pool's own status, naming which slots are
held and whether their owners are alive
(`agents/product-qa.md` § "Browser mechanics (the claim → drive → RELEASE cycle, no exceptions)").
It also runs a distinct **journey-map task** (dossier "T9"-class)
when assigned: navigating to target destinations the way a persona would (no typed URLs), recording
actual click count vs. a recorded `achievable_min`, flagging divergence rather than an absolute
click-count folk threshold, and reporting persona hesitation explicitly
(`agents/product-qa.md` § "Journey-map task (dossier \"T9\"-class, when the dispatch includes it)").

## Grounding

Runtime discipline: `knowledge/product_qa_primer.md`. Repo-local grounding:
`.claude/oversight/product-qa.md` — the app's staging URL, QA account reference, persona
definition, walkthrough task scripts, and known-trap notes. Missing dossier is declared DEGRADED,
restricted to auditing only public, unauthenticated pages (`agents/product-qa.md` §"Read FIRST", item 2).
Credentials are never typed from memory or guessed — always fetched live from GSM at the moment of
use, per the live-testing skill.

## Boundaries — what it will NOT do

STAGING ONLY — production is never its target under any instruction short of the operator's
explicit go-ahead relayed verbatim. Never creates/modifies/deletes identity-provider accounts
(shared-auth trap between staging and production); never seeds or mutates tenant data beyond the QA
account's own sandbox actions; no secrets, tokens, or PII in its report or screenshots. It never
edits repo files; Bash is scoped to the pool claim/release, the GSM secret read, and read-only
inspection, never a file edit; issue filing is the orchestrator's, through board-steward's rules
(`agents/product-qa.md` § "Boundaries").

## How it fits with other oversight agents / the review boundary

product-qa and design-reviewer (a non-oversight, on-demand agent) cover the same heuristic/
accessibility ground from different angles and are explicit about not duplicating: a finding on a
page product-qa actually walked live is product-qa's; a finding on a diff/mock/component
design-reviewer reviewed pre-build is design-reviewer's — filed once, by whichever ran first, cross-
referenced (`agents/product-qa.md` § "Walkthrough protocol (from your primer, applied)", final
paragraph). Its journey-map task can consume a static nav-graph
baseline design-reviewer's `map` mode produced, reporting only the LIVE divergence from that graph
rather than re-deriving the whole structural analysis. It never dispatches other agents and never
files issues itself.

## Example invocation

A new staging revision lands (flagged by sentinel's deploy-drift poll into the queue). product-qa's
weekly run drains that revision, claims a free pool slot, and walks the "create an estimate" task as
the persona. It finds that submitting the estimate form with an invalid phone number shows the same
generic "Invalid input" message it showed for a missing required field on a prior run — a form/
error-state finding per its primer's adaptive-messaging checklist — and screenshots the state before
releasing the slot.
