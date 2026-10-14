---
name: gtm
description: Launch a go-to-market marketing/sales mission — dispatches the marketing-director orchestrator with the goal verbatim, running clarify → plan → produce → converge → present.
argument-hint: "\"<goal>\""
---

# /gtm — GTM department mission entry point

Thin entry point only. The real mission-lifecycle procedure (clarify/plan/produce/converge/present,
the fan-out bounds, the dissent-ledger and evaluator mechanics) lives in the runtime primer
`~/.claude/knowledge/marketing_director_primer.md` — read that for the actual mechanism. This file
just describes what the command does and where things land, resolved per-repo via the manifest.

## Arguments

Invoked as `/gtm "<goal>"` — `$ARGUMENTS` is the goal string, passed through **verbatim**, no
paraphrasing, to the dispatched director.

## What `/gtm "<goal>"` does

Dispatches the `marketing-director` agent (opus, sanctioned department-orchestrator — see
`<repo>/.claude/oversight/marketing-director.md` for that repo's grounding facts) with the goal
string passed **verbatim**.

> **⛔ Dispatch path (platform constraint, confirmed live 2026-09-05):** dispatch
> `marketing-director` as a **direct top-level `Agent` tool call — never inside a `Workflow`
> tool call.** A workflow-spawned agent structurally cannot hold the `Agent` tool ("Agent is
> disabled for this session, in subagents as well as here" — a tool-absence at the platform
> layer, not a permission or pacer denial), which silently reduces the director to read-only
> analysis: no PRODUCE phase, no bench fan-out, no mission artifact ever written. A first mission
> attempt hit exactly this; the top-level re-dispatch worked.

The director:

1. Assigns a mission id `gtm_<YYYY_MM_DD>_<slug>` and creates
   `<gtm.missions_dir>/<mission_id>.json` (schema: `~/.claude/tools/gtm/MISSION_SCHEMA.md`), where
   `gtm.missions_dir` is resolved via `python3 ~/.claude/scripts/repo_manifest.py get
   gtm.missions_dir`. If the id already exists, the director REFUSES and asks for a new slug — no
   silent suffixing.
2. Runs the mission through CLARIFY → PLAN → PRODUCE → CONVERGE → PRESENT, fanning out to the
   department's specialist bench (`conversion-architect`, `brand-architect`, `content-strategist`,
   `seo-architect`, `paid-acquisition-strategist`, `pricing-economist`, `video-producer`, plus
   `market-analyst` for market/competitor facts).
3. Batches any operator-input residue from CLARIFY onto this repo's operator-input surface:
   resolve it via `python3 ~/.claude/scripts/repo_manifest.py get operator_input`. When that key
   is non-null, follow its `kind`/`path`/`regen_command`/`open_path` fields (e.g. a
   decisions-JSON-plus-regenerated-HTML surface). **When `operator_input` is `null`**, use the
   runtime fallback: write numbered cards to `<gtm.missions_dir>/OPERATOR_QUEUE.md` (a "Resolved"
   section holds the operator's verbatim answer once a card is answered) and `open` that file so
   the operator actually sees it — never ask piecemeal in chat instead of batching.
4. Decides convergence mechanically via `python3 ~/.claude/tools/gtm/exit_contract.py --ledger
   <gtm.missions_dir>/gtm_reviewed.jsonl --mission-id <mission_id>` (assertion ids
   `GTM-CONV-01/02/03`) over the dissent ledger — never by an agent's own claim of consensus. It
   prints `GTM convergence: N of 3 …` or `UNEVALUABLE: <reason>` (exit 2 on UNEVALUABLE; exit 3 on
   manifest/resolver failure).
5. Presents the finished artifacts plus the evaluator's verbatim verdict on STOP.

## Where things land

- Mission JSON + dissent ledger: `<gtm.missions_dir>` (`repo_manifest.py get gtm.missions_dir`).
- Evaluator: `~/.claude/tools/gtm/exit_contract.py`. Schema: `~/.claude/tools/gtm/MISSION_SCHEMA.md`.
- Department inbox (cross-department findings addressed to this department): the GitHub label
  named by `repo_manifest.py get gtm.inbox_label`.
- Actual code/copy/asset changes: dispatched to `implement`/`test-writer`/`design-reviewer` per the
  execution-boundary rules in `~/.claude/knowledge/marketing_director_primer.md` §4 — the director
  itself holds no `Write`/`Edit` tool and only ever writes inside `<gtm.missions_dir>/**` and its
  own scratchpad (via a separately-dispatched landing agent).

## Boundaries

The director never ranks product work (that's `launch-director`'s lane), never touches an ad
platform, never spends, never reprices, and never pushes/PR/deploys. Every specialist it dispatches
is findings-only. See `<repo>/.claude/oversight/marketing-director.md` for the full write-allowlist
and trust-boundary notes for that repo.
