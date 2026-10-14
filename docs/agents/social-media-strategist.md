# social-media-strategist

`social-media-strategist` is the GTM department's social media strategist: owner of the company's organic (unpaid) social presence
(`agents/social-media-strategist.md` frontmatter's `description:` key). It judges and specifies; it never acts on
any external platform.

## Model & tools

- **Model:** `opus` (`agents/social-media-strategist.md` frontmatter's `model:` key), matching the rest of the GTM
  bench since 2026-09-19.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` — no `Edit`/`Write`. Bash is a
  self-chosen read-only set; this is prose-enforced only (`agents/social-media-strategist.md` §"Injection safety").

## When it's dispatched

By `marketing-director`, on a mission or cycle step. No schedule of its own.

## What it does

Organic Facebook and Instagram, LinkedIn for B2B companies, and YouTube Shorts where the
pack puts them in scope: the monthly content calendar (what goes out, when, and why), the format
mix (photos, carousels, Reels, text), cadence caps so accounts are never flooded, a purpose tag on
every planned post (trust, proof, education, offer, community), and the community and direct-
message policy (what gets answered, by whom, how fast, what escalates).

## Lane fences

- **Post and caption wording as finished copy** → `content-strategist`.
- **Video craft: shot lists, pacing, b-roll** → `video-producer`.
- **Paid social and boosted posts** → `paid-acquisition-strategist`.
- **Visual identity of graphics** → `brand-architect`.

## Grounding

`knowledge/social_media_strategist_primer.md`; the company pack and dossier resolved through
`tools/gtm/company.py resolve <slug>`; the corpus files listed in the primer §2. A missing pack or
dossier means DEGRADED, never invented facts.

## Boundaries — what it will NOT do

Never edits any repo file, never files or transitions an issue, never pushes/PR/merges/deploys,
never posts, replies or changes anything on an external platform, never spends.

## Example invocation

The director asks for October's plan. The seat returns eight posts across Facebook and Instagram (two proof posts from real job photos, two education Reels, one offer, three community), flags that the Instagram account has no recent Reels, and caps cadence at two posts a week per platform until engagement data exists.
