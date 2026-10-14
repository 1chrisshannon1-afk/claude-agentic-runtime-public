# board-steward.md — grounding dossier (__PRODUCT_NAME__)

FACTS ONLY. Every count carries its re-derive command + as-of date. VERIFIED = opened/ran directly
this session. **Missing this file ⇒ `board-steward` declares DEGRADED, read-only analysis only.**

## 1. Repo and board identity

*Board number + real `Status`/`Priority` field options, never assumed — `transition`'s
`--project`/`--owner` args come straight from here; a wrong number writes to the wrong board.*
Re-derive: `gh project field-list __PROJECT_NUMBER__ --owner __GH_OWNER__ --format json`

See `.claude/oversight/manifest.json` → `github.repo`/`github.project_owner`/`github.project_number`.
Board = project `__PROJECT_NUMBER__` (`__PROJECT_NAME__`), `__ITEM_COUNT__` items as-of
`__AS_OF_DATE__`. `Status` options: `__STATUS_OPTIONS__`. `Priority` options:
`__PRIORITY_OPTIONS__`. A second same-owner project for a different product: name + mark it
never-touched-from-here.

## 2. Label taxonomy

*The real, live label list by convention, plus any legacy/colliding labels needing an operator
ruling — guessing a taxonomy invents drift instead of removing it.*
Re-derive: `gh label list --limit 200 --json name,description`

- Type/area/difficulty labels: `__TYPE_LABELS__` / `__AREA_LABELS__` / `__DIFFICULTY_LABELS__`.
- Priority truth (field or label): `__PRIORITY_TAXONOMY__`. Legacy labels being retired:
  `__LEGACY_LABELS__`. Unclassified — do not touch until ruled on: `__UNCLASSIFIED_LABELS__`.
- Named collisions (label vs. field/label) — never silently merged: `__LABEL_COLLISIONS__`.

## 3. The sweep cap and aging thresholds

*Mutation cap per sweep + aging thresholds for disposition/icebox — bounds a sweep's blast radius.*

Sweep cap: `__SWEEP_MUTATION_CAP__` mutations/pass. Disposition candidate:
`__DISPOSITION_AGE_THRESHOLD__`. Icebox candidate: `__ICEBOX_AGE_THRESHOLD__`.

## 4. Any existing grooming pipeline — absorb, don't contradict

*A scripted backlog-grooming pipeline's path + disposition vocabulary, so the steward absorbs
rather than duplicates it; say plainly if none exists.*

Path: `__GROOMING_PIPELINE_PATH__` (or "none — this dossier is the first grooming policy").
Disposition vocabulary: `__DISPOSITION_VOCABULARY__`. **Never re-run a bulk-close pipeline live
without explicit operator go-ahead** — a deploy-class action even when it's "just a script."

## 5. Measured dedup baseline

*A re-derivable command, never a frozen number — a coarse signal for the next consolidation pass.*

```bash
gh issue list --state open --limit 1000 --json title -q '.[].title' > __SCRATCH_TITLES_FILE__
# then cluster by keyword substring, per this repo's own recurring finding classes
```

## 6. Epic reality

*Whether epics use native GitHub sub-issues or a different convention — writes must match reality.*

Sub-issue usage: `__SUBISSUE_USAGE_FACT__`. Cross-reference convention: `__CROSSREF_CONVENTION__`.
