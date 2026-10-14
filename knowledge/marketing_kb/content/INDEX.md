# Content Domain — Index

Grep-reachable index for the content-strategist seat (headlines, page copy, email sequences,
video scripts, reputation lane). This corpus is not meant to be read wholesale — find the file
that answers your question, read that file only.

**Seat status:** `content-strategist` is a registered agent (`~/.claude/agents/content-strategist.md`)
— every "content-strategist seat" reference in this corpus's files describes that seat's discipline.

**Read `ANTI-PATTERNS.md` before writing anything customer-facing** — it is short and catches the
mistakes that recur most. **Read `voice-and-vocabulary.md` too, when the company pack selects the
contractor/trades voice persona** — a company pack that selects a different persona (see
`../shared/` for the available buyer-psychology persona files) reads that persona file instead.

**Relocation note (2026-09-27):** `escalation-triggers.md`, `never-do.md`, and
`response-templates-by-severity.md` used to live in a `reputation/` subdirectory here
(`content/reputation/`). They have moved to the sibling `../reputation/` directory
(`marketing_kb/reputation/`), which now holds the full reputation-domain corpus, and were
de-specialized (company names/paths removed) in the same move. The rows below
point to their new location — see `../reputation/INDEX.md` for the rest of that corpus.

| File | Answers |
|---|---|
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a content seat NEVER recommend or write, across headlines, email, video, and reputation? What rule or mechanism created each ban? |
| [`voice-and-vocabulary.md`](voice-and-vocabulary.md) | What words does a working residential-trades buyer actually use vs. SaaS-marketing words to avoid (contractor-vertical voice module)? What is the one sanctioned speed claim, and what claim is banned? |
| [`headline-doctrine.md`](headline-doctrine.md) | What headline formulas work for a phone-first, software-skeptical buyer? How do we adapt AIDA/plain-language direct-response doctrine without sounding like an ad agency? |
| [`ad-copy-doctrine.md`](ad-copy-doctrine.md) | What governs paid ad COPY — Google RSA headlines/descriptions, Meta primary text/headline/description? Field limits and asset-count doctrine, Ad Strength vs. pinning, Google text customization / Meta Advantage+ enhancements silently rewriting our copy, competitor-name restrictions, offer/ROSCA compliance for card-required / money-back-guarantee (negative-option) offer shapes, improbable-outcome claims, Meta's Personal Attributes fence, and ad/landing-page message match. Added 2026-09-19 to close an orphaned lane (neither this corpus nor paid_acquisition's owned ad-unit text before this). |
| [`email-sequence-doctrine.md`](email-sequence-doctrine.md) | What structural rules govern lifecycle-email sequences (welcome, nurture, win-back)? What benchmarks (open/click/bounce) should a sequence be judged against? What structural rules govern subject lines, CTAs, and claim-checking? **⚠ funnel-shape caveat:** a company's actual offer shape (trial-based vs. card-at-signup-plus-guarantee, etc.) can change on its own ruling timeline — confirm the current company's live offer shape from its own pricing source of truth before building doctrine that assumes a trial funnel. |
| [`../sales/outreach-levers-and-drafting.md`](../sales/outreach-levers-and-drafting.md) | (lives in the sales domain) What should an outreach or promotional message lead with, how do you segment by one variable, and how do you draft with an assistant and edit as a human? Read it before writing any business-to-business email campaign or referral-partner note; it is not a template for patient messages. |
| [`video/script-first-timing.md`](video/script-first-timing.md) | Why is narration written and measured BEFORE capture? What does "script-first timing" mean operationally, and what breaks if you skip it? |
| [`video/never-claim-script-gate.md`](video/never-claim-script-gate.md) | What is the per-line gate every video script line must pass before recording? What are the three classes of lines that typically get cut, and why? (a company's own real examples live in its pack/dossier) |
| [`video/licensing-table.md`](video/licensing-table.md) | Which voice, music, and photo sources are commercially safe to use in a demo video, and which are legally risky? What's the verified fact and its citation? |
| [`video/ai_talking_avatar_playbook.md`](video/ai_talking_avatar_playbook.md) | HeyGen vs Synthesia for an AI-generated (not-a-real-person) host — which one can even be used, and why? How do you get the best HeyGen results (identity-anchor consistency, motion prompts, expressiveness, common failure modes) without burning render credits? What's the credit-safe test protocol (free-tier → cheap API test → full render) and the do-not list (never-claim/FTC fence, watermark, fake on-screen UI)? |
| [`video/heygen_api_spec.md`](video/heygen_api_spec.md) | Pinned HeyGen `/v3` API implementer spec — exact endpoints/fields for photo-avatar creation, own-audio lip-sync video generation, polling/download, limits, and pricing. Read this when actually calling the API; the playbook above is the strategy/craft/cost layer that cites it. |
| [`video/heygen_skills_ref/`](video/heygen_skills_ref/) | Vendored copy (MIT, v3.2.0 @ 1bd5e4d, 2026-09-09) of HeyGen's official agent skills (`heygen-avatar` / `heygen-video` / `heygen-translate` SKILL.md + references). REFERENCE ONLY — evaluated in the playbook's §8 and deliberately NOT installed as skills (they route through the CLI/MCP and the Video Agent, not a pinned REST integration — see the company's own pack/dossier). |
| [`../reputation/response-templates-by-severity.md`](../reputation/response-templates-by-severity.md) | How does a review response change by star rating (5/4/3/2/1)? What's the required structure for a negative-review response? |
| [`../reputation/escalation-triggers.md`](../reputation/escalation-triggers.md) | When does a review response require the operator's hand instead of an agent draft? What review content stops an agent cold? |
| [`../reputation/never-do.md`](../reputation/never-do.md) | What review/reputation tactics are illegal (FTC) or bannable (Google policy) — gating, incentivized sentiment, fake reviews, threats? |

## How this corpus was built

Portions of this corpus were ported from prior internal marketing doctrine per the house rule:
MECHANISM ports, NUMBERS get re-derived or marked UNVERIFIED per company/vertical before use. See
each file's own citations. This corpus serves any company the GTM
department runs — never assume a fact, ruling, or number in these files describes any one specific
company unless the file says so explicitly and cites that company's own source of truth.
