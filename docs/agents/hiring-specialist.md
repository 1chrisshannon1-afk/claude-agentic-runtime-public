# hiring-specialist

`hiring-specialist` helps a small employer hire staff for one company at a time
(`agents/hiring-specialist.md` frontmatter's `description:` key). It drafts and scores; the owner
posts, contacts, decides and signs.

## Model & tools

- **Model:** `sonnet` — bounded drafting and rubric scoring from a cited KB; decisions stay with the
  owner and an employment attorney.
- **Tools:** `Read, Grep, Glob, WebFetch, WebSearch` — no Bash, no browser, no Write.

## What it does

Role requirements, lawful job posts with required pay disclosure, board choice (Indeed first),
screening rubrics with fit tiers separate from clearance, interview guides and scorecards, reference
guides, offer, decline and onboarding drafts.

## Grounding

`knowledge/hiring_specialist_primer.md`; `knowledge/hiring_kb/` (cited); the company's
`<home>/.claude/oversight/hiring-specialist.md` dossier (missing ⇒ DEGRADED).

## Boundaries — what it will NOT do

Never posts, messages candidates, decides a hire, quotes off-band pay, reads a board's applicant
list, or applies a criterion that could screen on a protected class; never edits files or spends.

## Example invocation

"hiring-specialist: a small remodeling company in Colorado needs a carpenter; draft the
Indeed post and a screening rubric." It returns a post with the Colorado pay-range and benefits
disclosure, a board plan, and a rubric with must-haves tied to the job — plus the facts it still
needs (pay band, benefits) if the dossier lacks them.
