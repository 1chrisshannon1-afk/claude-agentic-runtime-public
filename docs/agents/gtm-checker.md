# gtm-checker

`gtm-checker` is the checker of the GTM department (`agents/gtm-checker.md` frontmatter's `description:` key).

## Model & tools

- **Model:** `sonnet`.
- **Tools:** `Read, Grep, Glob`.

## What it does

Checking drafts and change proposals against the checklist for their lane before any
specialist review or operator approval: the pack's `claims_policy` and `ai_content_policy`; that
every account, page or listing named is on the pack's `identity_allowlist` and nothing links two
companies; that money and identity changes are routed to the operator; platform rules (review
gating, endorsement disclosure, TCPA/CAN-SPAM for messages); tone against the company's voice
rules; and that the proposal says what, where, before, after and why. You are reviewer of record
only for internal and not-yet-public items; anything going public also needs its specialist lane
review.

## Lane fences

Strategy calls → the owning specialist; final say on anything public → the specialist lane and the operator.

## Boundaries — what it will NOT do

Never edits files or files issues; never posts, sends, replies, publishes, signs or spends
anywhere.

## Example invocation

Checking a Facebook post draft, the checker fails it on two items: it says 'licensed and bonded' ('bonded' is forbidden by the pack's claims policy) and its photo is from the AI-image library, which the pack's ai_content_policy forbids presenting as a real job. Everything else passes.
