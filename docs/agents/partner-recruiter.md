# partner-recruiter

`partner-recruiter` helps an operator recruit a founding team for one company: co-founders and
advisors (`agents/partner-recruiter.md` frontmatter's `description:` key). It researches and
drafts; the operator sends, calls, decides and signs.

## Model & tools

- **Model:** `sonnet` — bounded research and drafting from a fixed recruiting package; judgment on
  terms stays with the operator and an attorney.
- **Tools:** `Read, Grep, Glob, WebFetch, WebSearch` — no `Edit`/`Write`; the session writes
  any pipeline rows it proposes.

## When it's dispatched

By name, with the path of the company's recruiting package. No schedule.

## What it does

Public-source shortlists per role, personalised draft messages, first-call briefs, scoring against
the package's scorecard, and pipeline tracking with a weekly funnel check.

## Grounding

`knowledge/partner_recruiter_primer.md` plus the recruiting package named in the dispatch
(`README.md`, `role_profiles.md`, `offer_sheets.md`, `screening.md`). No package ⇒ DEGRADED.

## Boundaries — what it will NOT do

Never sends, posts, calls or signs in as the operator; never writes equity or pay into a
candidate-facing draft; never scrapes or automates LinkedIn; never edits files or files issues.

## Example invocation

"partner-recruiter: using ~/Desktop/OtherApp_Venture_Plan/recruiting/, build a shortlist of 10 CTO
co-founder candidates and draft a first message for each." It returns ten public-source
candidates with fit evidence and unknowns, ten short personalised drafts with no terms in them, and
proposed `pipeline.md` rows.
