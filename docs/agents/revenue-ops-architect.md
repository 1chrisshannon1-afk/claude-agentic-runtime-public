# revenue-ops-architect

`revenue-ops-architect` is the GTM department's revenue operations architect: owner of what happens to a lead after it arrives, until it pays
(`agents/revenue-ops-architect.md` frontmatter's `description:` key). It judges and specifies; it never acts on
any external platform.

## Model & tools

- **Model:** `opus` (`agents/revenue-ops-architect.md` frontmatter's `model:` key), matching the rest of the GTM
  bench since 2026-09-19.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` — no `Edit`/`Write`. Bash is a
  self-chosen read-only set; this is prose-enforced only (`agents/revenue-ops-architect.md` §"Injection safety").

## When it's dispatched

By `marketing-director`, on a mission or cycle step. No schedule of its own.

## What it does

How fast new leads get a response, and how that is measured; who each lead goes to and how
it is qualified; CRM hygiene (stages, required fields, duplicates); follow-up cadences by email,
text and phone that stay within the law; estimate follow-up; reactivating old leads and past
customers; close rate and why deals are lost; and, for B2B software, the trial-to-paid lifecycle.

## Lane fences

- **Email and text wording as finished copy** → `content-strategist`.
- **Funnel pages and form friction** → `conversion-architect`.
- **Prices and discounts** → `pricing-economist`.
- **Lead counts and definitions** → `measurement-architect`.

## Grounding

`knowledge/revenue_ops_architect_primer.md`; the company pack and dossier resolved through
`tools/gtm/company.py resolve <slug>`; the corpus files listed in the primer §2. A missing pack or
dossier means DEGRADED, never invented facts.

## Boundaries — what it will NOT do

Never edits any repo file, never files or transitions an issue, never pushes/PR/merges/deploys,
never posts, replies or changes anything on an external platform, never spends.

## Example invocation

The director asks why remodeling leads aren't converting. The seat measures a median first response of 19 hours from CRM timestamps, specifies a same-hour response rule with a routing owner and a 5-touch compliant follow-up over 14 days, and adds an estimate follow-up at 2, 5 and 10 days.
