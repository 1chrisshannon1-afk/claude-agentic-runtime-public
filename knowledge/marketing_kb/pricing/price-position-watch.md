# Price-position watch — competitor price-move monitoring method

**Answers:** How does this domain's pricing discipline monitor competitor price moves on a standing
basis, what cadence and method, and how does that watch hand off to `market-analyst` (the runtime's
competitor/market-facts seat) rather than duplicate it?

## Why this exists: it feeds reopen class (c), nothing more

Per `reopen-discipline.md`, "a competitor materially repricing" is one of exactly four conditions
that can reopen a company's ruled pricing ladder. This file's entire purpose is producing that
evidence reliably, so whoever applies this discipline is never caught re-deriving a competitive
landscape from scratch when a reopen question comes up — and never missing a real reopen trigger
because nobody was watching. **It does not exist to generate ongoing competitive strategy
recommendations** — that is `market-analyst`'s job (per-industry competitor/market-facts intel, a
separate runtime seat, dispatch-only, per `~/.claude/CLAUDE.md` §13).

## The fence: what this discipline watches vs. what market-analyst does

- **This discipline (pricing-economist's — see `INDEX.md`: a live runtime agent) watches:**
  published list prices, tier structures, trial/guarantee policy,
  and seat/add-on pricing mechanics for the specific competitor set a company's own ladder was
  benchmarked against (see the company's own pricing source-of-truth doc for the named competitor
  set from its own audit). The watch is narrow and mechanical: did a **price number** change.
- **`market-analyst` owns:** broader competitor/market-facts intel — positioning shifts, feature
  launches, funding events, market-sizing, and any qualitative "what does this mean for our
  strategy" analysis. If a price-position watch surfaces a repricing, this job stops at
  **reporting the fact with a citation** — handing off to `market-analyst` (or the operator directly,
  per `reopen-discipline.md`'s worked example) for any interpretation beyond "does this touch a
  ruled assumption."
- **When in doubt, under-reach.** Writing "and here's what the company should do about
  it" has left the pricing-economist lane and wandered into `market-analyst`'s or the operator's.

## Monitoring cadence and method (external doctrine, applied)

(third-party, retrieved 2026-09-05 — aggregated from Visualping.io and PageCrawl.io competitive
pricing-tracking sources): published SaaS tier prices rarely change more than 2-4 times per year, so
a monthly check is generally sufficient to catch changes without excess noise — but a
broader sample (third-party, retrieved 2026-09-05, same source set) found that across a mixed set of
B2B SaaS competitor pricing pages, **roughly 7 in 10 changed their pricing page at least once over a
6-month window**, and in any given week about 1 in 3 had *some* pricing-page change (though many of
those are copy/feature changes, not list-price changes). Guidance from the same sources: match
cadence to market volatility — daily-to-weekly is appropriate for a fast-moving category; monthly is
generally sufficient for a stable category (e.g. a stable B2B SaaS category) — judge which describes
a given company's own category before picking a cadence.

**Vertical note (internal doctrine):** for B2B software sold to trade/home-services businesses, the
category typically reprices infrequently and deliberately rather than on a fast-moving/dynamic-pricing
cadence — treat such a category as "stable" for the purpose of the guidance above unless a specific
competitor is observed repricing often.

**Applied method, monthly cadence as a starting default, four steps:**

1. **Snapshot** the pricing page (or documented plan/price page) for each of a company's own named
   benchmark competitors once a month. A lightweight manual check (visit + note price, trial terms,
   guarantee terms) is sufficient at this cadence and competitor-set size — no tool is prescribed
   here; if the department later adopts one, this file should be updated to name it.
2. **Diff** against the last snapshot and against the figures already cited in the company's own
   pricing source-of-truth doc.
3. **Classify the diff:** a changed *list price* on a plan the company's ladder was benchmarked
   against is a candidate class (c) trigger. A changed feature set, a limited-time promo, or a copy/
   positioning change is not — log it as a market-facts note for `market-analyst`, not a reopen
   candidate.
4. **Card genuine candidates** per `reopen-discipline.md`'s worked example format: old price, new
   price, source URL, retrieval date, and which ruled assumption in the company's own pricing doc it
   touches. No proposed new company price accompanies the card.

## Numeric gate: what counts as "materially repricing" — UNVERIFIED, seeded, needs derivation

**Every threshold in this gate is `UNVERIFIED — seeded, needs derivation` (see
`../shared/citation-style.md`) — it is bootstrapped by analogy from
`cogs-currency-method.md`'s own equally-unverified COGS-materiality heuristic, not derived
independently for competitive pricing. "Consistency across the domain" is not evidence for either
number; treat both as working defaults a reader should not mistake for ruled thresholds.**

- **Pass `UNVERIFIED` (log only, no card):** a competitor's price moves by less than ~15%, or the
  change is to a tier/plan the company's ladder does not directly reference (e.g. an enterprise-only
  SKU with no comparable tier of the company's own).
- **Reject `UNVERIFIED` (card as class (c) candidate):** a competitor's price moves by more than
  ~15-20% on a plan the company explicitly benchmarked (i.e. a figure the company's own pricing doc
  actually cites as evidence for a positioning claim), or a competitor eliminates/adds a trial or
  money-back guarantee that changes how the company's own risk-reversal positioning compares.
- **This 15-20% threshold is `UNVERIFIED — seeded, needs derivation`.** It is not operator-set; it
  mirrors the same "material" heuristic used for COGS divergence in `cogs-currency-method.md`,
  applied here by analogy for consistency across this domain rather than derived independently for
  competitive pricing. Treat it as a working default, not a ruled number.

## Worked example (illustrative — already used in reopen-discipline.md, full method shown here)

A named competitor drops its month-to-month price by roughly 40% (well past the 15-20% gate). This
is a class (c) candidate if that competitor's prior price is the specific figure a company's own
pricing doc cites as evidence for a positioning claim (e.g. "no [category] tool exists under
$[N]"). Card: "Class (c) candidate — [Competitor] month-to-month price $X → $Y (retrieved [date], source:
[URL]). Touches [doc]'s '[claim]' basis for [tier]'s entry price. Recommend `market-analyst` confirm
this is a durable list-price change (not a time-limited promo) before treating as a reopen trigger.
No price change proposed." Note the explicit hand-off to `market-analyst` for the durability check —
that is exactly the fence this file exists to keep.

## Vertical bends — trade/home-services (B2B) and local-service (B2C)

Many B2B trade buyers do almost no comparison shopping the way a SaaS-fluent buyer does — they are
not reading G2 comparison grids or three vendors' pricing pages side by side before they call a
salesperson. What they *do* carry is anchor memory from whatever software burned them on price
before — often per-seat creep or a surprise renewal hike (see the persona file the company pack
selects (`persona_file`) — e.g. `shared/contractor-buyer-psychology.md` for a B2B-software buyer,
or `shared/homeowner-buyer-psychology.md` for a B2C service buyer — for the specifics of that
buyer). This changes what "competitor
reprice" should mean for marketing copy aimed at such a buyer even when it doesn't change the
internal monitoring method: a competitor's price move only matters to this buyer's decision if it is
a number they will actually encounter (a quoted price on a call, a referral's complaint, a
review-site mention) — not an abstract shift on a pricing page a busy trade buyer never visits. When
this watch's findings do reach buyer-facing copy (e.g. a sanctioned per-seat-economics attack line),
keep the comparison concrete and unit-specific (named seat counts, named dollar figures) rather than
abstract percentage moves — that is the form this kind of buyer can actually use on a phone call.
