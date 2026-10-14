# Autonomy tiers — plain-language summary

This file translates the GTM Autonomous Department plan's tier table (§6.3, as superseded by §20.6)
and autonomy rules (§20.6/§20.7) into plain language for any seat that needs to reason about "can I
do this myself, or does it need to go to the operator" without parsing the full plan. **This file is
a summary, not the authority** — where anything here appears to conflict with the plan itself (the
runtime's `plans/gtm_autonomous_department_plan.md` §20.6/§20.7 — **note: this plan file is
local-only, excluded from version control by this runtime's own `.gitignore`, so a reader of the
GitHub mirror cannot open it directly; `tools/gtm/README.md` and `tools/gtm/company_schema.json` are
tracked and cover the pack-authoring mechanics this file also touches, though neither restates the
tier table itself**) or, once it exists, with the machine-readable tier table
(`tools/gtm/tier_table.json` is planned and not yet built, so there is no file to link; its draft
schema and row list are §3.4 of `tools/gtm/contracts/03_schemas.md`), the plan and the JSON win;
update this summary to match them, never the reverse. Until the JSON exists, the plan and that draft
schema are the only authority. This file carries no citation tags of its own because it makes no external factual claims —
it restates internal governance already sourced in the plan.

## The one-sentence version

Every action a GTM agent might take is classified into a **tier** (how much oversight it needs) by
what it touches, and the **autonomy level** the company is currently running at (whether that tiered
oversight is actually executing, or only logging what it would have done) is a separate dial. A read
is (almost) always free. Anything that spends money always goes to a human, no matter what.

## The tiers, from least to most oversight

| Tier | What it means | Plain-language examples |
|---|---|---|
| **T0** | Read-only. No approval needed, ever. | Pulling a report, exporting current ad performance, taking a snapshot of a page. |
| **T1** | Reversible and not yet public — a draft, a paused item. | Drafting a scheduled social post that hasn't gone live; creating a paused ad campaign; a GTM (tag manager) workspace edit nobody has published yet. |
| **T2** | Public, but within an already-approved lane and reviewed before it ships. | Publishing a reviewed blog post; replying to a public review; editing an existing website page under the safe-change protocol; publishing a scheduled post. |
| **T2-review** | Same as T2, specifically for review-platform replies. | Replying to a 2-star Google/Yelp review. |
| **Identity / irreversible** | Changes identity, or something not trivially reversible — even if it costs nothing. | Changing a business's primary category, name, or address; a deletion that can't be trivially undone; linking accounts/roles within the same company; messaging a specific named person; creating that company's own new app/API access. |
| **`$` (money)** | Any row flagged `money: true`, any row with no `money: false` flag, any action with a nonzero monthly spend delta, and any action with no tier-table match at all. | Setting or changing a budget/cap/ceiling; enabling, pausing, or removing a paid campaign or ad set; any purchase, subscription, fee, paid trial, or paid usage; pay-per-lead area/category changes (the plan names Thumbtack/Angi; Google Local Services Ads service areas and job types follow the same rule); the department's own AI-spend caps. |
| **Shared systems** | A system two of the operator's companies both touch, declared in a company pack's `shared_identifiers` (plan §20.2). | Any action on such a system is an operator card, never autonomous. |
| **NEVER** | Not automatable at any autonomy level, full stop. | Linking two different companies' accounts/assets together; creating or joining a Meta Business Portfolio; anything that would put a secret in a tool call or transcript; the handful of other absolute per-company denials the current plan names. |

**Within-ceiling optimizations are not a separate tier.** Plan §20.6 lists them inside its
autonomous class, alongside T0, T1, T2 and T2-review: keywords (including competitor-brand
keywords), negatives, ad copy/assets, audiences and other targeting, bid strategy and bid
targets/caps, and pausing a single ad, ad group, or keyword — all inside an operator-approved budget
that the change leaves unchanged (plan §20.13). They run **autonomously after the required reviews**,
exactly like T0–T2-review. The tier-table schema draft (`tools/gtm/contracts/03_schemas.md`) labels
these rows `T3` with class `auto`; that label names this same autonomous class, never a separate or
more restricted one. Creating a campaign, ad group, or ad PAUSED, even with a budget field set, is
T1 (plan §20.13: a paused campaign's budget is committed only at enable).

**No match in the tier table defaults to `$` (operator sign-off)** — an action nobody has explicitly
classified gets the conservative treatment, never the permissive one.

## The autonomy levels — the separate dial

The current plan runs a **two-level** ladder (this replaces an earlier four-level draft —
advisory/shadow/semi/autonomous — that this file used to describe; that draft was superseded before
it shipped, and any older note or memory referencing "semi" or "advisory" as a running mode is stale):

- **shadow** — the department behaves as if it *would* execute every tier, and logs what it would
  have done, but doesn't actually do it — this is the verification period (14 days per company) a
  company runs before being promoted, and what a demoted system falls back to after a breaker trip.
- **autonomous** — T0 through T2, T2-review, and within-ceiling optimizations run without a human
  touching each individual instance, once the reviews required for that tier (see below) are
  satisfied structurally; the identity/
  irreversible class runs as **notify-then-execute** (below), never silently; shared-system actions
  are always cards; and `$` always still goes to the operator, at every autonomy level, forever,
  with no exception.

Demotion (a system falling back to `shadow`, i.e. would-execute-only) happens automatically on a
breaker trip, and automatic re-promotion happens after 7 clean days — this ladder never applies to
`$`, which is never automatic at any level.

## The money rule (memorize this one — it never bends)

Stated once in the plan and repeated here because it is the single most important line in this whole
file: **committing money — setting or changing a budget/cap/ceiling, enabling or pausing a paid
campaign, any purchase or subscription — always goes to the operator, at every autonomy level,
forever.** *Spend delivered inside an operator-approved ceiling* (which keyword to bid on, which ad
copy to run, which audience to target, where to set the bid within an approved range) is what can
become autonomous. The plan's own wording: **"Stopping spend (pausing, lowering) is `$` too."** A
seat does not get to unilaterally decide to *reduce* spend either — even a cost-saving pause is a
money decision and goes to the operator, not just a cost-increasing one. If an agent detects runaway
spend, the correct action is an **urgent** `$` card with a push notification — never a silent pause;
nothing is paused without sign-off.

## The identity/irreversible middle class — notify-then-execute

Between "fully autonomous" and "always a card" sits the **identity/irreversible** class: things that
aren't spend but also aren't cleanly reversible — a deletion that isn't trivially undoable, renaming
the business, changing its primary category or address, linking roles/accounts within the same
company, sending a message to a specific named person (only with consent already on record), or
creating that company's own new app/API access. These **execute automatically once autonomous**, but
the operator is notified with a hold window and a real, working cancel option before (or as) they go
live — never silently. A hold that expires during a pause stays held until the pause lifts, then
re-notifies with a fresh window; the operator (or, for a needed fix, an agent) can cancel from any of
several channels, and every cancel is logged with who cancelled it.

## What "autonomous" actually requires structurally — it is never a vibe

An action being tiered below `$` does not by itself make it eligible to run with no human touch at
all. Every tier that runs autonomously still passes through the maker-checker review lanes
(`approval-gate-triad.md`) and the content checks (claims, other-business-content, AI-asset
provenance, rate caps, spend caps) required for that tier — and for the identity/irreversible class,
a real notify-then-execute hold with a genuine, working cancel mechanism. "Autonomous" describes the
*absence of a required human approval step for each individual instance*, not the absence of every
other safeguard. A seat that treats "this tier is low-risk, I can just do it" as license to skip the
review lane has misunderstood the tier table — the tier and the review requirement are two separate
gates, and this file only summarizes the first one.

## Kill switches always override the ladder

A pause file (scoped to one system, or the whole company, or the whole department) beats any autonomy
level, without exception. If a pause is in effect for a system, that system's tiered actions stop
being autonomous regardless of what the tier table or the autonomy level would otherwise say — see
the plan's pause-scope rules for the exact pause types and what each still allows through (reads and
lead-capture keep working even under most pauses; nothing does under the runtime's global
schedules-disabled switch except the narrowest safety-relevant reads).

## Contractor bend

Not applicable in the direct sense (this is internal department governance, not customer-facing
content) — but the reason this ladder exists at all connects directly to
`contractor-buyer-psychology.md`: a buyer who has been burned by software or agencies overpromising
and under-delivering (fact 3) is exactly the buyer who would be most damaged by an autonomous system
that quietly spent money it wasn't authorized to spend, or changed something about their business
identity without them knowing. The tier table's conservatism is not bureaucratic caution for its own
sake — it is the mechanical version of the trust this buyer has to be re-earned, one correctly-scoped
action at a time.
