# Web-dev safety — staging first, backup verified, audit logged

Ported near-wholesale (internal doctrine, retrieved 2026-09-27 — this is the mechanism a prior web-dev engagement's own
safety rule established). The rule below is stated generically; each company's own dossier supplies
the surface-specific detail (its actual paths and surfaces this rule covers, and any way its actual
infrastructure differs from a WordPress-hosted client-site shape, which was the shape this rule's
mechanism was originally ported from). Applies to any GTM seat that touches a company's
marketing site, in-app marketing surfaces, or user-facing docs — **see that company's own dossier/
pack for the exact paths and surfaces this rule covers for that company**; this file states the
discipline, not any one company's file layout.

## Core principle (verbatim, ported)

> "Staging first. Always. No exceptions. No agent edits a production website directly. Every change
> lands on staging, is verified, and only then is pushed to production. A production edit with no
> staging step did not follow this process and does not count as completed work."
>
> "Never edit a live website without a verified recovery path, before/after visual proof, and a
> complete audit trail. A web edit that cannot be rolled back is a web edit that cannot be made. A
> web edit without evidence of completion did not happen."

**The incident that created this rule (internal doctrine, incident: web-dev production header edit,
2026-04-18):** an agent marked website tasks done with empty result notes, no
pre-edit backup, no screenshots, no audit log, and edited a global site header directly on production
with no staging step. The site broke. Nobody could tell what changed or when. Recovery required the
host's own backup system. This rule exists so that never happens again.

**A company this department serves may already have its own equivalent rule** (a hard "test on
staging, never production without explicit go-ahead" rule in its own operating contract). Any GTM
seat editing that company's marketing site, in-app marketing components, or docs inherits that rule
directly where one exists — this file is not a new rule in that case, it is the same rule, restated
for the marketing-owned subset of that company's surfaces; where no such company rule exists yet,
this file's discipline is the default.

## Rule 1 — backup/recovery must exist before any edit

For any surface this department edits, before the edit: confirm a real recovery path exists. For a
git-tracked file, the recovery path is git itself — but "it's in git" is only a real backup if the
agent actually confirms the pre-edit state is committed and clean before editing, per the company's
own repo git discipline (path-scoped commits, never editing over uncommitted, uncertain state — see
the runtime operating contract's own git rules for the general shape of this discipline). If the
target file has *uncommitted* changes from another agent's in-flight work, that is a contested-file
situation per the runtime's own file-contest rule — yield and poll, don't edit through it.

If no verifiable recovery path exists (a generated artifact not checked into git, a live CMS/
platform surface outside any tracked repo entirely), the edit does not proceed until one does — same
hard stop as the ported recovery-path rule.

## Rule 2 — pre-flight checklist (every edit)

1. Confirm the recovery path (Rule 1).
2. Identify what actually renders the target — a static HTML template, a component reading from a
   structured content source (a JSON content file, a CMS record), or a docs-site page. This
   determines where the real content lives and how to edit it safely.
3. Take a before-snapshot of every URL/page/component the edit affects — for a live staging or
   production check, a screenshot (via the runtime's live-testing infrastructure); for a local-only
   content change, the pre-edit file content itself (which git already preserves).
4. Record current state: what file(s), what content-source(s), what git SHA you're editing from.
5. Write a pre-edit note (see Rule 5's audit-log shape below) before making the change.

## Rule 3 — edit-mode rules (during the edit)

1. **Staging first, always, every edit** — per the company's own staging-first rule where one
   exists (the runtime operating contract's own ask-before-push/PR/merge/deploy rule applies
   regardless: deploy to staging, verify there, and only push to production on an explicit,
   per-push operator go-ahead).
2. **One logical change per commit.** Never batch multiple structural edits (a copy change *and* a
   layout change *and* a pricing-number change) into one commit — mirrors the ported "one logical
   change per save" discipline, and mirrors the runtime's own path-scoped-commit discipline.
3. **Never hand-edit a generated file.** If a surface is generated from a content source (JSON,
   a template + data file), edit the source, not the rendered output — editing the wrong layer
   silently desyncs the real content from what's displayed.
4. **Respect a learning-period-style gate for conversion-driving elements.** A pricing table, a
   hero CTA, or a lead-capture form that's been live under 14 days should be measured before it's
   changed again (internal doctrine, retrieved 2026-09-27: "if it's been live <14 days, measure
   first, change second." This threshold is an operational heuristic carried forward from prior
   work, not sourced to any published research or platform documentation — it is ported here as-is,
   at the same confidence level its origin assigned it, not upgraded to look more authoritative than
   its source). This is a
   distinct, less rigorous discipline than `paid_acquisition/learning-period-gates.md`'s ad-platform
   thresholds, which are themselves partly grounded in official platform documentation (see that
   file) — the two are *analogous* gates on the same underlying idea (don't judge a change before it
   has enough data), not the same cited number.

## Rule 4 — post-flight verification (after every change)

1. Re-fetch the affected page(s) with cache busted (a fresh load, not a cached one).
2. Take after-screenshots on staging; compare against the before-screenshots for unintended
   regressions — not just the edited section, but nearby, unaffected sections (an edit to a shared
   partial/component can silently break a page nobody was thinking about).
3. Verify: no broken links, no console errors, no unintended layout shift, and — specific to this
   department's governed surfaces — no contradiction of the company's own never-claim list
   (`department-anti-patterns.md` item 2) introduced by the change.
4. Only after staging verification passes does the change go to production, via the runtime's normal
   ask-gated deploy process — never a direct production edit.

## Rule 5 — task/change is not "done" without evidence

Mirrors a ported result-notes-required rule (a `result_notes` field must be populated or the task
isn't done). For this department, a change is not complete without:

1. What was edited (file/component/page) and why.
2. The pre-edit state reference (git SHA, or a before-screenshot for a live-rendered check).
3. Before/after screenshots when the change is visual.
4. A one-sentence plain-English description of what changed.
5. Verification verdict — pass, with what was checked.

A change closed out with fewer than these five is rejected and reopened — same discipline as the
ported result-notes-required rule, and consistent with the runtime operating contract's own rule that
a change leaving evidence/docs/tests stale is a defective change.

## Rule 6 — hard-stop conditions

Stop and escalate immediately (never push through) when:

- No staging environment/verification path exists for the surface being edited.
- The edit is being attempted directly on production, for any reason, bypassing staging.
- The pre-edit recovery path (Rule 1) can't be verified.
- Screenshot/verification tooling is unavailable and there's no other way to confirm the change.
- Credentials or access needed for the edit aren't in the company's own expected credential store
  (e.g. a secrets manager, an `.env` file per the company's own env-var canonical-location rule) —
  never typed from memory or invented.

A stop here is the rule working, not a failure — report it and wait, per the runtime's own 3-strike
and ask-gate discipline.

## What this file does not cover

Backend/API code changes to the marketing product surfaces (not copy/content) follow that company's
normal engineering standards and git/CI discipline — this file is specifically about *marketing copy
and content* edits to the marketing-owned surfaces, not about application logic.

## Contractor bend

The end buyer never sees a staging environment, a pre-edit screenshot, or an audit log — but they
are exactly the buyer for whom a visibly broken marketing site (a garbled pricing page mid-edit, a
headline that contradicts what the product actually does) is most damaging. This kind of buyer often
already suspects software vendors of moving fast and breaking things (see
`contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`'s "burned by software/vendors
before" facts) — a live site that looks unfinished or inconsistent confirms that suspicion in
seconds and is very hard to walk back. The bend is: treat every marketing-surface edit with the same
staging-first discipline as a shipped product feature, because to this kind of buyer, the marketing
site *is* the product's first impression of whether the company is trustworthy enough to hand real
data to.
