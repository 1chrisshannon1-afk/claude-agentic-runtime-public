# gtm-drafter

`gtm-drafter` is the drafting seat of the GTM department (`agents/gtm-drafter.md` frontmatter's `description:` key).

## Model & tools

- **Model:** `sonnet`.
- **Tools:** `Read, Grep, Glob`.

## What it does

Short-form drafts for one company: review replies (to `local-presence-architect`'s severity
verdict and never-say list), social posts and captions (to `social-media-strategist`'s calendar),
listing descriptions and Q&A answers, GBP posts, and short customer-facing updates. Every draft is a
proposal: what it is for, where it would go, the text, and which claim rules it follows. Long-form
copy (pages, emails, scripts) stays with `content-strategist`.

## Lane fences

Reply strategy and severity → `local-presence-architect`; calendar and DM policy → `social-media-strategist`; long-form copy and the voice guide → `content-strategist`.

## Boundaries — what it will NOT do

Never edits files or files issues; never posts, sends, replies, publishes, signs or spends
anywhere.

## Example invocation

Given a 2-star review, the local-presence verdict (severity 2, no escalation, never mention the refund) and the pack, the drafter returns a 60-word reply proposal that thanks the reviewer, owns the delay without admitting fault, and offers a call to the office number.
