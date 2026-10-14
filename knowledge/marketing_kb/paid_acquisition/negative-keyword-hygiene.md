# Negative-Keyword Hygiene

Ported mechanism from a prior internal ads discipline's negatives gate and search-term mining
discipline (ported incident-derived mechanism, 2026-07 — history only, never a live source). This
is the single most consequential
recurring lever in paid search — a strong negative list is what keeps broad match and Smart
Bidding from spraying budget on irrelevant queries — and it is also where a real production
incident happened, so the guardrails below are non-negotiable, not stylistic. This top-of-file
attribution covers the GATE STRUCTURE and the incident narrative; it does not itself stand in for a
citation on any individual number below — each numeric threshold (e.g. the 15-click significance
bar) carries its own provenance tag where it first appears, per house style.

---

## The core gate: a term only qualifies as a negative if it passes ALL four checks

Never recommend "add all N zero-conversion search terms as negatives." A raw zero-conversion count
is not a negative-keyword list — it is an unfiltered dump that will predictably block real,
converting demand somewhere in it. A term is safe to add ONLY when it passes every one of:

1. **Significance bar** — at least 15 clicks with zero conversions. Below 15 clicks, zero
   conversions is statistical noise, not a signal. (Ported incident-derived mechanism, 2026-07 —
   the 15-click bar is `UNVERIFIED — seeded, needs derivation`: a heuristic from the ported gate,
   not a Google-stated or independently benchmarked figure.)
2. **No overlap with any converting term.** If the exact query, or a close variant of it, has ever
   converted, it is not a negative candidate — even if it also drives some non-converting traffic.
3. **Not a deliberate conquest target.** If the business runs (or has ever run, even paused) a
   conquest campaign against a named competitor, that competitor's name is not a negative — a
   PAUSED conquest campaign is not evidence the term is safe to block; the test is the campaign's
   *strategy*, not whether it happens to be live right now.
4. **Not an owned/accepted-segment term.** See the accepted-segment trap below — this is where the
   real incident happened.

State the count AFTER filtering, and name which raw candidates were held back and why. Recommending
"add all N" where N is the unfiltered zero-conversion count is a defect, full stop.

## The accepted-segment trap (the incident this rule exists because of)

**Incident (ported incident-derived mechanism, 2026-07, live production failure):** a review
recommended negativizing an insurance carrier's name as wasted spend for a dental practice that
actually accepted that carrier. Queries like "dentist that accepts [carrier]," "[carrier] dentist
near me," and "[carrier] provider" are HIGH-INTENT in-network prospects, not waste — the
recommendation was applied to the live account and suppressed valuable, converting demand. The
specific account, carrier, and date belong in the measuring company's own dossier, never here.

**Before recommending ANY brand or partner name as a negative, first distinguish:**
- A **competitor's** brand or business name → negativizable, subject to the 4-check gate above.
- An **owned or accepted relationship's** name → never blanket-negativizable as a bare term.

**Contractor-vertical equivalents of the accepted-payer trap** (the mechanism is identical; the
specific brands differ by vertical):

- A **financing partner's brand name** the contractor is an approved dealer/originator for (e.g. a
  homeowner searching "[financing company] contractor near me" is a high-intent, pre-qualified
  lead, not waste).
- A **manufacturer or supplier co-op brand** the contractor is an authorized installer/dealer for
  (e.g. "[window brand] certified installer," "[roofing brand] preferred contractor" — these are
  exactly the searches an authorized dealer relationship exists to capture).
- A **franchise or co-op brand** the business operates under, if distinct from its own trade name.

If some queries containing that partner's name genuinely aren't relevant (e.g. "[financing
company] customer service," "[financing company] login," "[financing company] complaint"),
negative ONLY those specific disambiguating phrases — never the bare partner name. When unsure
whether a term is a competitor or an owned relationship, say so explicitly and ask, rather than
guessing and negativizing.

## Brand negatives: EXACT match only, plus explicit variants

**Never apply a brand or partner negative at PHRASE or BROAD match.** A PHRASE or BROAD negative on
a brand term blocks every LONGER query containing it too — not just the bare brand — including
exactly the valuable prospects the negative was never meant to touch:

- A PHRASE negative on a financing partner's name blocks "[remodeler] financing through [partner]"
  — a real, in-progress qualification search.
- A PHRASE negative on a competitor's name blocks "alternatives to [competitor]" and "[competitor]
  vs [us]" switcher queries — exactly the prospects actively shopping AWAY from that competitor and
  toward the business running the campaign.

EXACT match blocks only the bare query itself and lets every longer, higher-intent variation
through.

**Negative keywords do not match close variants the way positive keywords do.** An EXACT negative
on the canonical spelling alone will NOT block plurals, run-together spellings, word-order
variants, or common misspellings of that same brand. To actually block the bare brand across all
its real-world forms, add EXACT negatives for the base term AND its known variants — e.g. a roofing
brand name spelled with and without a space, its common misspelling, and "[brand] [trade]" /
"[trade] [brand]" word-order swaps. (Ported incident-derived mechanism, 2026-07.)

## Standard contractor-vertical negative categories (re-derived for the contractor vertical)

The categories below are re-derived for the home-services contractor vertical. The ported source's
negative-keyword categories came from a different vertical (the same ported guardrail set as
[`budget-as-formula.md`](budget-as-formula.md)'s multiplier structure) and did not transfer
directly; overlapping category names (job seekers, DIY) are re-derived here, not carried over:

| Category | Example terms | Why |
|---|---|---|
| Job seekers | "jobs," "hiring," "careers," "salary," "apply" | A contractor's Ads budget is for customers, not applicants — route hiring intent to the careers page organically, never pay for it |
| DIY / self-install seekers | "diy," "how to install," "how to build," "tutorial," "step by step" | These searchers are explicitly not hiring a contractor for this job |
| Wrong-scale segment | "commercial," "industrial," "warehouse," if the business is residential-only (or the inverse) | A residential remodeler's ad showing for commercial-construction searches wastes spend on an unserviceable segment |
| Price-shopping / free-estimate-tool seekers | "free estimate calculator," "cost estimator app," "diy cost calculator" | These searchers want a self-serve tool, not a contractor visit |
| Employment-adjacent | "apprentice," "trade school," "license requirements," "certification" | Trade-education searchers, not buyers |
| Wrong-trade / wrong-service | Any trade-specific term outside the business's actual service scope (e.g. a kitchen-remodel-only business should negative "roof repair," "hvac install," etc.) | Prevents the account from paying for demand it cannot fulfill — see the company-profile-alignment rule in [`grade-a-gates.md`](grade-a-gates.md) |
| Reviews/reputation research (non-buying intent) | "[business name] reviews," "[business name] complaints," "is [business name] legit" | Legitimate research traffic, but typically low-intent for a paid click compared to organic/GBP presence; judge per account rather than blanket-excluding |

Never treat "free" as a blanket broad-match negative for a contractor offering free estimates —
this blocks the exact high-intent phrase "free estimate," which is standard buying language in
this vertical (the same "free" over-blocking pattern applies to a free-trial SaaS offer).

## Mining cadence

| Phase | Cadence | Action |
|---|---|---|
| Week 1–2 of a new campaign | Daily | Build the initial negative list — this window is the highest-leverage moment to catch waste before it compounds |
| Month 1 | Every 2–3 days | Expand negatives; also mine for new positive-keyword opportunities in the same report |
| Month 2–3 | Weekly | Ongoing refinement |
| Steady state | Bi-weekly | Maintain the list; spot-check for query drift as seasonality or service mix changes |
| Quarterly | Full audit | Review the ENTIRE negative list for anything that may now be blocking valid traffic — a negative added for a good reason 8 months ago can become a liability as the business's service mix changes |

(Structure: ported incident-derived mechanism, 2026-07, re-derived for this vertical — the
cadences are `UNVERIFIED — seeded, needs derivation`.)

## Shared (account-level) vs per-campaign negative lists

Prefer a shared, account-level negative-keyword list for any negative that should apply across
every campaign (universal exclusions like job-seeker or DIY terms). Reserve per-campaign or
per-ad-group negatives for exclusions specific to that campaign's scope (e.g. negativizing a
service the business doesn't offer, scoped only to the campaign where it would otherwise
accidentally trigger). A shared list centralizes maintenance and avoids the same term being added
inconsistently across campaigns.

## Verification discipline — never claim a negative "was added" without reading it back

A queued or approved negative-keyword change is not the same as it actually landing on the account.
Read the live negative list back and confirm the exact keyword text and match type appear before
reporting the change as done (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #10 — this is the same
"applied vs verified" discipline that governs every mutation in this corpus).

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **The accepted-segment trap is a live risk for almost every contractor account, not an edge
  case.** Any GC running manufacturer-authorized-dealer status, a financing partnership, or a
  franchise/co-op affiliation has at least one brand name that looks negativizable but isn't. Ask
  the question explicitly during onboarding: "are there any brand names you're an authorized
  dealer/partner for?" — don't wait to discover it the hard way after a bad negative goes live.
- **A GC will often ask to blanket-negative a competitor's name "so we don't pay for their
  traffic."** Explain plainly: negativizing a competitor's name doesn't stop THEM from
  advertising — it only stops the GC's own ad from showing when someone searches for the
  competitor, which is a strategic decision (see [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #9 —
  there is no default competitor negative; if one is used it is EXACT match only and a stated,
  deliberate choice), not a cost-saving default.
- **The wrong-trade / wrong-scale category matters more here than in almost any other vertical.**
  A residential-only remodeling GC accidentally capturing commercial-construction search traffic
  wastes real budget on leads the business cannot even bid competitively for — this is a
  higher-value negative category for a contractor than the generic job-seeker/DIY categories that
  dominate most best-practice guides.
- **Present the filtered negative count in plain terms**: "we found 40 wasted search terms; 31 pass
  the safety checks and are safe to block; 9 we're holding because they overlap with real leads or
  look like a brand you might be partnered with — confirm before we touch those." This is more
  trust-building for a GC than a raw list dump, and it makes the filtering process visible rather
  than invisible.
