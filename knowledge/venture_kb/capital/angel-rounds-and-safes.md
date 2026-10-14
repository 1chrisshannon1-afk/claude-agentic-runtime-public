# Angel rounds and SAFEs

**What this file answers:** whether a small angel round helps or hurts a given company right now,
how the YC-style post-money SAFE actually works (valuation cap, discount, MFN, pro rata side
letter), the arithmetic of how a SAFE converts and what it does to a founder's ownership, what a
typical pre-seed/angel round looks like in size and cap today, why a company usually cannot issue
a clean SAFE as an LLC, what a cap table is and why it matters from the first dollar raised, what
pitch materials a first-time founder actually needs, and how a live raise interacts with a
same-year sale process. This is written for a solo, first-time founder who codes with AI agents and
has not raised money before. It is information, not legal or tax advice — see the "When to bring in
a professional" section in each relevant part.

---

## 1. When a small angel round helps

**Decision rules:**

- IF the company has zero revenue, zero users, and no demonstrated distribution channel, THEN an
  angel round mostly buys runway to find product-market fit, not to scale a working motion — that
  is a legitimate use of angel money but a different pitch than "give us fuel for growth."
- IF the founder can reach the same milestone (first paying customers, a working demo, a second
  team member) on personal savings, revenue, or a small friends-and-family note within 3-6 months,
  THEN raising is optional — money raised earlier than needed converts more of the company for the
  same dollars than money raised at a higher valuation later (see Section 3 dilution math).
- IF the raise is being used to solve a *distribution* problem (the product works, but the founder
  cannot reach buyers alone) and the check comes from someone who personally supplies that
  distribution — an operator-angel with the exact customer relationships, a domain expert who
  opens doors — THEN the round helps disproportionately to its dollar size. The right angel is a
  channel, not just capital.
- IF the raise is being used to solve a *product* problem the founder could solve faster with focus
  and free/cheap tools (which is increasingly true for a single technical founder using AI coding
  agents) THEN a round mainly adds overhead (board/update expectations, a cap table to maintain,
  future dilution) without buying the missing thing.
- IF the company is a side project or lifestyle business with no intent to seek a priced
  venture round or exit within ~5-7 years, THEN a SAFE-based angel round is usually the wrong
  instrument — SAFEs are underwritten on the assumption of a future priced equity round; raising
  SAFE money with no realistic path to a qualifying event leaves investors converted into an
  illiquid instrument that may never convert, which is a foreseeable source of investor anger and
  reputational cost to the founder even without a lawsuit.

**When it hurts:**

- **Too early, too small, wrong signal.** A tiny round (a few thousand to ~$25k) from a
  non-strategic friend or family member at a real priced valuation, done informally with a
  handshake or a vague note, can create a legal cap-table entry that complicates every later round
  — every professional investor's counsel will ask about it in diligence. `[KB-VCAP-001]` Small,
  informal early checks are exactly the kind of cap-table noise that shows up as a diligence
  question later; formalize even a small round with a real instrument (a SAFE, not a handshake)
  (internal doctrine, retrieved 2026-09-28).
- **Capped too low.** Setting a valuation cap without understanding the dilution math (Section 3)
  can give away a large, non-obvious percentage of the company for a small check — the founder who
  does this discovers it only when a priced round is being negotiated and the option pool and SAFE
  conversions eat far more of the pre-money than expected.
- **Wrong investor.** An angel who expects hands-on control, frequent reporting, or a say in
  hiring/product decisions in exchange for a small check is a governance cost that outweighs the
  capital. A SAFE is non-voting and carries no board seat by default, but an investor's *informal*
  expectations (set verbally, never in the document) can still become a real distraction if not
  managed from the first conversation.
- **Signals weakness to a later, larger investor.** A round raised at an unusually low cap, or
  raised from an unusually large number of very small checks (a "spray and pray" round), can read
  to an institutional seed investor as evidence the company could not attract a stronger lead — this
  is a soft signal, not a rule, but it is real in practice.
- **Selling while trying to sell the company.** Raising new investor money at the same time the
  founder is exploring a sale of the company creates a direct conflict: new investors buy in
  expecting the company to grow toward a future priced round or larger exit, and a near-term sale
  at a modest price can leave them worse off than if they had never invested, exposing the founder
  to a claim of bad faith or misrepresentation even under a SAFE's minimal contractual promises. See
  Section 8.

**Anti-patterns:**

- Raising because raising feels like "startup progress" rather than because a specific, named
  milestone requires outside capital to reach.
- Taking the first check offered without shopping the cap — a solo first-time founder has no
  reference point for what cap is normal this quarter (Section 4 gives sourced current data) and
  can anchor far too low.
- Treating a SAFE as "not real money" or "not real equity" because no cash equity changes hands at
  signing — a SAFE is a binding contract that converts into real, often meaningfully dilutive,
  equity later. Under-explaining this to an unsophisticated angel (a friend, a family member) is
  both an ethical problem and, if the angel is not actually accredited, a securities-law problem
  (see `securities-rules-for-founders.md`).
- Signing a SAFE with terms copied from a friend's deal without reading the actual document — the
  YC SAFE has several non-interchangeable variants (Section 2) and picking the wrong one changes
  the economics substantially.

---

## 2. The YC post-money SAFE

The SAFE ("Simple Agreement for Future Equity") was created by Y Combinator in 2013 as a
faster, cheaper alternative to a convertible note for early-stage fundraising. `[KB-VCAP-002]` A
SAFE is "a short contract an investor signs to fund your startup now in exchange for the right to
shares of stock in your startup later" (official, Y Combinator, "SAFE Financing Documents,"
retrieved 2026-09-28). It is not debt: it carries no interest rate and no maturity date, and the
company owes nothing back if the triggering event never happens (subject to the dissolution/
liquidity provisions in the document itself).

In 2018, YC moved from a "pre-money" SAFE to a "post-money" SAFE, which is now the standard
template referenced by "the YC SAFE" in ordinary conversation. The post-money SAFE makes the
investor's percentage ownership on conversion mathematically determinable at signing **when the SAFE
converts at its cap** (see Section 3) — this is the single most important practical difference for a
founder to understand, because it means a SAFE converting at its cap **immediately and precisely**
sets aside a slice of the company's fully-diluted ownership, even though no stock is issued yet. A
SAFE with a discount, or one that ends up converting off a later priced round's price rather than
its own cap, is not fixed at signing in the same precise sense — the actual percentage still depends
on the terms of whatever triggers conversion; see Section 3 for the worked math.

### The three variants (plus an optional side letter)

YC publishes the SAFE in a small number of standard forms. `[KB-VCAP-003]` YC's own SAFE library
offers three primary variants for US companies — valuation cap only (no discount), discount only
(no valuation cap), and MFN only (no cap or discount) — each of which can optionally add a Pro Rata
Side Letter (official, Y Combinator, "SAFE Financing Documents," retrieved 2026-09-28). A fourth
combination, cap-and-discount, has also circulated in the venture ecosystem and in some non-YC
templates; a founder using a non-YC counsel-drafted SAFE should confirm in writing exactly which
terms are present, since "SAFE" is now used loosely to describe any short-form convertible
instrument, not only the literal YC document.

**Valuation cap.** `[KB-VCAP-004]` "The highest valuation at which a SAFE converts... On post-money
SAFEs, ownership sold equals the investment amount divided by the valuation cap" (official, Y
Combinator, "SAFE Financing Documents," retrieved 2026-09-28). In plain terms: the cap is a ceiling
on the price the SAFE investor effectively pays per share, protecting them from being diluted down
to a trivial stake if the company's next priced round values it far higher than when the SAFE was
signed.

**Discount.** `[KB-VCAP-005]` "A discount rewards early investors with a lower price than your
startup's next priced round" — for example, a 20% discount means the SAFE converts at 80% of the
per-share price paid by new investors in the priced round (official, Y Combinator, "SAFE Financing
Documents," retrieved 2026-09-28). A SAFE can carry a discount with no cap at all, a cap with no
discount, or (in some non-YC templates) both — when both are present, the SAFE converts at
whichever of the two gives the investor more shares (the better deal for the investor).

**MFN (Most Favored Nation).** `[KB-VCAP-006]` "An MFN SAFE has no valuation cap or discount;
instead it automatically takes the valuation cap or discount of any SAFE you issue later" (official,
Y Combinator, "SAFE Financing Documents," retrieved 2026-09-28). This is useful very early, before
a founder has enough information to set a defensible cap — it defers the pricing question to
whatever terms get set once the company has more data, but it means the founder cannot promise an
MFN investor any specific number today, and it means every later, more-favorable SAFE issued
automatically re-prices the MFN investor's deal too. A founder who plans to raise several SAFEs
over time should decide upfront whether later investors get better terms and disclose that
intention rather than let an MFN clause be a surprise.

**Pro rata side letter.** An optional side document (not part of the SAFE itself) giving the
investor the right, but not the obligation, to invest further in the company's next priced
equity round to maintain their percentage ownership. It matters most for larger checks or
investors the founder wants a continuing relationship with; it is administrative overhead for very
small checks and is often skipped for smaller angel checks by practice `[KB-VCAP-042]` UNVERIFIED
— seeded, needs derivation (a specific dollar threshold such as "under roughly $25k" is sometimes
cited informally but was not confirmed against any named source this pass — treat any specific
dollar cutoff as an unsourced rule of thumb, not a market standard), though YC's own documents do
not set a dollar threshold — this is founder/investor negotiation, not a rule.

**What a SAFE is not:** it is not a loan (no interest, no repayment obligation, no maturity date in
the current YC form), not common stock, and not a guarantee that the investor will ever receive
anything — if the company never raises a priced round and never has an exit or dissolution event
that triggers conversion, the SAFE may simply never convert. This is precisely why raising SAFE
money from a company with no intention of ever raising a priced round or seeking a sale is a
mismatched instrument (Section 1).

### When to bring in a professional

Have a startup-experienced attorney review the actual SAFE document before the first signature,
even when using YC's unmodified template — confirm which variant is being used, confirm the cap
and discount numbers match what was verbally agreed, and confirm the entity issuing the SAFE is a
Delaware C-corporation (Section 5). A CPA should be looped in before the round closes if the
founder does not already understand how the raise will be treated for the company's own tax
reporting and how much (if any) of the proceeds should be treated as taxable to the company.

---

## 3. How the cap converts, and the dilution math

A post-money SAFE's defining feature is that the investor's percentage ownership is fixed at
signing (before any other SAFEs or later dilution are layered on) by a simple formula:

```
Investor's SAFE ownership % (at conversion, before later dilution) = Investment Amount ÷ Valuation Cap
```

**Worked example 1 — single SAFE.**
An angel invests $50,000 on a SAFE with a $2,000,000 post-money valuation cap.

```
$50,000 ÷ $2,000,000 = 2.5%
```

That investor is entitled to shares equal to 2.5% of the company's fully-diluted capitalization
*as of the post-money cap* — that is what "post-money" means: the $2,000,000 cap already includes
this investor's own money, so the founder's retained ownership right after this one SAFE is
signed is already effectively ~97.5% of a company now understood to be valued (for SAFE-conversion
purposes only, not a real appraised value) at $2,000,000.

**Worked example 2 — stacking multiple SAFEs.**
This is where founders most often get the math wrong. Suppose the founder raises three SAFEs over
several months, each at a different cap:

| SAFE | Amount | Cap | % of company (Amount ÷ Cap) |
|---|---|---|---|
| A | $25,000 | $1,000,000 | 2.5% |
| B | $50,000 | $2,000,000 | 2.5% |
| C | $100,000 | $4,000,000 | 2.5% |
| **Total** | **$175,000** | — | **7.5%** |

Because each SAFE is calculated against its *own* cap at the time it was signed, the percentages
add up directly for post-money SAFEs (this is one of the reasons YC moved to the post-money
structure — it makes stacking multiple SAFEs' dilution arithmetic simple and additive rather than
requiring a circular pre-money calculation). After these three rounds the founder has raised
$175,000 and given up 7.5% of the company's future fully-diluted cap, leaving 92.5% for the
founder and any option pool created later.

**Worked example 3 — the option pool interaction (why founders are often surprised).** When a
company later raises a priced seed or Series A round, the lead investor typically requires an
option pool (commonly cited as 10-20% of the post-money cap `[KB-VCAP-041]` UNVERIFIED — seeded,
needs derivation; this range is repeated widely in startup-finance commentary but was not
independently re-confirmed against a named, dated primary or third-party source this pass — confirm
current market range before quoting a specific percentage to a founder) to be created *before* the
new money comes in, and that pool is carved out of the existing shareholders' ownership — including
the SAFE holders who are converting at that same moment and the founder. `[KB-VCAP-007]` This "option pool
shuffle" is a well-documented mechanic in priced-round negotiations where the pool's dilutive
effect lands disproportionately on the pre-round shareholders rather than the new investor
(internal doctrine, retrieved 2026-09-28 — this is standard venture-financing structure, not a
company-specific fact, and a first-time founder should have counsel model the actual post-money
cap table before signing a priced-round term sheet, not rely on this file's simplified example).

**Decision rules:**

- IF stacking multiple SAFEs, THEN track every cap, amount, and issue date in one cap table from
  the very first SAFE — never rely on memory or a single spreadsheet cell added ad hoc after each
  raise (Section 6).
- IF a SAFE's cap is being negotiated, THEN calculate the resulting percentage (Amount ÷ Cap)
  *before* agreeing to a number, not after — a founder who agrees to "a $1.5M cap" without doing
  this division in front of the investor has no way to sanity-check whether that is a reasonable
  ask relative to comparable current rounds (Section 4).
- IF total SAFE ownership sold across all rounds before the first priced round exceeds roughly
  15-25% of the company, THEN treat that as a flag to slow down and get counsel/an experienced
  advisor to model the eventual priced-round cap table before selling any more — beyond that
  range, the founder's own eventual stake can be diluted faster than expected once the option pool
  and new investor's round are layered on top.

---

## 4. Typical pre-seed/angel round sizes and caps (sourced, dated)

`[KB-VCAP-008]` In Q2 2026, the average pre-seed instrument size was $276,000, a 27% year-over-year
increase from Q2 2025 and a record high over the trailing four-plus years; few pre-seed deals
exceed $2.5 million, and those that do typically stack ten or more separate instruments together
(third-party, Carta "State of Pre-Seed: Q2 2026," retrieved 2026-09-28 — Carta's own dataset,
drawn from companies using Carta's cap-table platform; not a random sample of all US startups and
skews toward venture-track, Delaware C-corp companies).

`[KB-VCAP-009]` The pre-seed market has become "barbell-shaped": the share of pre-seed rounds
smaller than $250,000 reached a new high of 35% in Q4 2025, while the share of rounds larger than
$5 million stayed roughly flat at 8% — meaning the *small* end of the market is growing as a share
of the total while the large end holds steady, with the middle shrinking in between (third-party,
Carta "A disappearing middle: Why the pre-seed market is growing increasingly barbell-shaped,"
retrieved 2026-09-28 — do not describe the large-round share as "growing"; Carta's own figure is
flat, not increasing).

`[KB-VCAP-010]` At the 90th percentile, valuation caps on pre-seed SAFEs larger than $2.5 million
can reach roughly $100 million, a trend Carta attributes substantially to investor enthusiasm for
AI-related companies, which captured about half of all pre-seed dollars in the period measured
(third-party, Carta "State of Pre-Seed: Q2 2026," retrieved 2026-09-28 — this is a top-decile
figure for large, AI-branded rounds, not representative of a typical solo-founder angel round; do
not use it to anchor a normal round's cap).

`[KB-VCAP-011]` Total pre-seed capital deployed was $3.19 billion across more than 11,500
instruments in Q2 2026, compared with $3.22 billion across 14,825 instruments in Q2 2025 — meaning
roughly similar total dollars were spread across notably fewer, larger instruments year-over-year
(third-party, Carta "State of Pre-Seed: Q2 2026," retrieved 2026-09-28).

**What this means for a typical solo, first-time founder's angel round (not an AI mega-round):**
a round in the low hundreds of thousands of dollars, at a cap well below the 90th-percentile
figures above, is squarely typical per this dataset — a founder should not anchor a pitch on the
$100M-cap headline figure, which describes an atypical, top-decile outcome. A founder should
re-pull Carta's most recent quarterly release before setting a cap for an actual raise, since these
figures move materially quarter to quarter and this file's numbers will age.

**Decision rules:**

- IF an investor or a peer founder cites a specific cap or round-size figure as "standard right
  now," THEN ask for the source and the date — round sizes and caps have moved substantially
  year-over-year per the data above, and a number from even a year earlier is stale.
- IF the company's actual product category is AI-branded and investor interest reflects that,
  THEN the founder may see cap offers well above the median for non-AI companies — this is a real,
  dated market condition (Section 4 above), not necessarily an error on the investor's part, but it
  is also not permanent and should not be assumed to persist.

---

## 5. What a company must be: entity type

`[KB-VCAP-012]` Standard SAFE and convertible-note templates are written to convert into preferred
stock of a Delaware C-corporation; most institutional and professional investors "cannot or will
not invest in LLCs because pass-through income creates tax headaches for their own limited
partners," and if a company is still an LLC when a priced round is ready to close, "there is a
structural problem that needs to be resolved before closing" (third-party, Rho "How to Convert an
LLC to a C Corp," retrieved 2026-09-28 — a vendor blog written for founders, directionally reliable
on market practice but not a substitute for counsel on the actual conversion mechanics or tax
treatment).

`[KB-VCAP-013]` A company should complete an LLC-to-C-corp conversion *before* signing a term sheet
for a priced round, not simultaneously with closing — running the conversion in parallel with a
priced round creates tax-code timing problems (a Section 351 control-test issue) and can jeopardize
eligibility for Qualified Small Business Stock (QSBS) treatment later; practitioners commonly
recommend starting the conversion two to three months before a fundraise to complete it cleanly
(third-party, Rho "How to Convert an LLC to a C Corp," retrieved 2026-09-28 — UNVERIFIED as to the
specific "two to three months" figure and the Section 351/QSBS mechanics, which are genuinely
technical tax-code questions; a CPA and startup counsel must confirm both the timeline and the tax
treatment for the company's actual facts before relying on this).

`[KB-VCAP-014]` A company can technically issue a SAFE-like instrument from an LLC, but it is
non-standard and creates real legal ambiguity, because the standard SAFE "specifically
contemplates a type of investment that LLCs cannot do — namely, a priced, preferred stock round
with a venture-capital firm" (third-party, McCarthy Law Group, "Can an LLC Use a SAFE?," retrieved
2026-09-28).

**Decision rules:**

- IF the company is currently an LLC and a priced equity round (not just SAFEs) is realistically on
  the horizon within the next year, THEN start the LLC-to-C-corp conversion process with counsel
  now rather than at the point of signing a term sheet — this is squarely an "engage a professional
  now" item, not a DIY step; get a real attorney and CPA, confirm the actual mechanics and current
  tax treatment for the specific facts, and do not rely on this file's summary for the conversion
  itself.
- IF the company is an LLC and only ever intends to raise from friends/family/small angels with no
  institutional round expected, THEN a SAFE is still a mismatched instrument (per Section 2's "what
  a SAFE is not") — use a convertible note or a simple revenue-share/profit-share agreement drafted
  for an LLC instead, with counsel confirming the instrument actually fits an LLC's membership-
  interest structure.
- IF unsure whether the company should be an LLC or a C-corp from day one, THEN raise this with
  counsel before incorporating at all — the earlier this is settled, the cheaper the eventual
  conversion (or the avoided need for one).

---

## 6. Cap tables

A cap table (capitalization table) is the single record of who owns what percentage of a company,
and under what instrument (common stock, preferred stock, unconverted SAFEs, an option pool),
as of a given date. It matters from the first dollar raised, not only once a priced round happens,
because:

- Every SAFE signed is a real, binding future ownership claim (Section 3) even though it issues no
  stock today — a cap table that only tracks issued stock and ignores outstanding SAFEs is
  materially incomplete and will produce a false picture of the founder's actual retained
  ownership.
- Diligence for any future round, sale, or hire-with-equity will require producing an accurate,
  fully-diluted cap table on demand; reconstructing one from memory or scattered documents after
  the fact is slow, error-prone, and a credibility problem with a sophisticated counterparty.
- Founders regularly underestimate how much of the company they have already promised away once
  multiple SAFEs, an option pool, and any advisor grants are all summed — the option-pool-shuffle
  example in Section 3 is one of several mechanics that can surprise a founder who has not kept a
  running, fully-diluted table.

**Decision rules:**

- IF any SAFE, note, or equity grant (including advisor or employee equity) is signed, THEN update
  the cap table the same day — never batch this for "later."
  `[KB-VCAP-015]` Purpose-built cap-table software (e.g., Carta, Pulley, or a properly-built
  fully-diluted spreadsheet model reviewed by counsel) is standard market practice once more than
  one instrument type exists (internal doctrine, retrieved 2026-09-28 — this file does not endorse
  a specific vendor; the requirement is a maintained, fully-diluted, dated record, not a specific
  tool).
- IF a single founder has not yet raised anything, THEN a simple table is still worth starting
  immediately, showing 100% founder ownership as the baseline every future instrument dilutes from
  — this makes every later addition a single new row rather than a reconstruction project.
- IF an advisor or early team member is promised equity informally ("you'll get some equity"),
  THEN treat that promise as a cap-table liability the moment it is made, even before paperwork is
  signed — record the informal promise on the cap table as a liability internally, and have counsel
  paper it (a FAST-style or attorney-drafted agreement) before any specific number or vesting
  schedule is put in writing and sent to the recipient (this is consistent with
  `equity-and-agreements.md`'s rule that a specific percentage is never put in writing before an
  attorney-reviewed agreement exists — tracking the liability internally and sending the recipient a
  written number are two different steps, and only the first should happen "promptly").

---

## 7. Pitch materials for a first-time founder

A first-time solo founder raising a small angel round typically needs, at minimum:

1. **A short narrative deck** (10-15 slides is a commonly cited range `[KB-VCAP-043]` UNVERIFIED —
   seeded, needs derivation; not confirmed against a named source this pass — treat as a general
   rule of thumb, not a market standard, and never a rule):
   problem, solution, why now, product (screenshots/demo), market size, traction to date (even
   pre-revenue traction — users, waitlist, LOIs, pilot conversations — counts), business model, the
   ask (amount, instrument, use of funds), and the team (even a team of one, framed around relevant
   experience and why this founder is credible for this problem).
2. **A one-paragraph or one-page summary** for warm-intro emails — most early conversations start
   from a forwarded paragraph, not the deck itself.
3. **A simple, honest financial model** — even a rough 12-24 month projection of costs and expected
   revenue/usage milestones. It does not need to be sophisticated; it needs to show the founder has
   thought about how the money will be spent and what it buys.
4. **The actual SAFE document** (the correct YC variant, or counsel-drafted equivalent), ready to
   send once terms are agreed — having this ready signals seriousness and speeds up closing a
   willing investor before they lose momentum.
5. **A data room or folder** (even a simple shared drive folder) containing: cap table, any
   existing IP assignment/founder agreements, incorporation documents, and key metrics — this does
   not need to be elaborate for an angel check, but professional investors will expect it to exist
   and be organized before a larger round.

**Anti-patterns:**

- A deck with no clear, specific ask (amount + instrument + use of funds) — "we're raising a seed
  round" with no number attached signals the founder has not decided what they actually need.
- Overstating traction or projecting unrealistic growth curves with no basis — sophisticated
  angels have seen this pattern many times and it damages credibility faster than admitting early
  traction is thin.
- Sending the SAFE document before the cap and discount have been explicitly agreed in writing
  (even a one-line email) — sending a blank-cap document and asking the investor to "fill in what
  feels fair" creates room for a misunderstanding that is expensive to unwind later.

---

## 8. How a raise interacts with selling the company within 2 years

This is a genuine conflict-of-interest and disclosure problem, not just a strategic awkwardness,
and it deserves its own section because a first-time founder is unlikely to see it coming.

**The core tension:** a SAFE investor puts money in on the implicit premise that the company is
being built toward a future priced round or a larger exit that will make their converted equity
worth meaningfully more than their check. If the founder is *simultaneously* exploring or
negotiating a near-term sale of the company — especially a modest-sized sale, an acquihire, or an
asset sale — the new investor's money may never convert to anything of real value, or may convert
into equity in a transaction structured in a way that leaves them diluted or cashed out at a low
number.

**Decision rules:**

- IF the founder is actively in, or seriously contemplating, a sale process for the company, THEN
  disclose that fact to any prospective angel investor before accepting their money — silence here
  is not a technicality; an investor who later learns the founder was already negotiating a sale
  while raising fresh capital has a real and reasonable grievance, and depending on what was said
  or omitted, potentially a securities-fraud claim (see `securities-rules-for-founders.md` on
  material misrepresentation/omission) even under an instrument as simple as a SAFE.
- IF a sale is likely within roughly the SAFE's realistic conversion horizon (there is no fixed
  rule here — use judgment informed by how advanced the sale conversation already is), THEN
  consider whether raising at all is the right move, versus funding the remaining runway to close
  the sale through founder capital, revenue, or a bridge specifically disclosed as sale-bridge
  financing.
- IF new SAFE money is raised and a sale then closes shortly after, THEN the SAFE's own terms
  govern what the investor receives on that liquidity/change-of-control event — read the actual
  document's acquisition/dissolution provisions before assuming "the SAFE just goes away" or "the
  SAFE investor just gets their money back." `[KB-VCAP-016]` The YC post-money SAFE's standard form
  addresses this directly: on a Liquidity Event (an acquisition or IPO) before conversion, a
  valuation-cap SAFE pays the investor the **greater of** 1x their money back (the "Cash-Out Amount")
  **or** what they would have received had the SAFE converted to common stock immediately before the
  event (the "Conversion Amount") (official, Y Combinator SAFE FAQ / SAFE User Guide and the
  post-money SAFE's own §1(b), retrieved 2026-09-28: "the investor gets the greater of 1x
  their money back, or what they'd receive if the SAFE had converted to common stock"). The exact
  mechanics still depend on the specific document signed (a discount-only or MFN SAFE's liquidity
  provisions can differ) and must be read directly, not assumed from this summary — confirm against
  the actual signed document and counsel before relying on it for a live transaction.
- IF a sale process and a raise are both live at once, THEN this is a "bring in counsel now" moment
  — the disclosure obligations, the sequencing, and the SAFE's own change-of-control mechanics all
  need a real legal read of the actual documents and actual timeline, not general guidance.

---

## Sources

- Y Combinator, "SAFE Financing Documents" (official, retrieved 2026-09-28) — https://www.ycombinator.com/documents
- Carta, "State of Pre-Seed: Q2 2026" (third-party, retrieved 2026-09-28) — https://carta.com/data/state-of-pre-seed-q2-2026/
- Carta, "A disappearing middle: Why the pre-seed market is growing increasingly barbell-shaped" (third-party, retrieved 2026-09-28) — https://carta.com/data/disappearing-middle-pre-seed-market/
- Rho, "How to Convert an LLC to a C Corp in 2026" (third-party, retrieved 2026-09-28) — https://www.rho.co/blog/convert-llc-to-c-corp
- McCarthy Law Group, "Can an LLC Use a SAFE?" (third-party, retrieved 2026-09-28) — https://mccarthylg.com/can-an-llc-use-a-safe/

**UNVERIFIED claims in this file:**
- `[KB-VCAP-041]` — the 10-20% option-pool-size range: not confirmed against a named, dated source this pass.
- `[KB-VCAP-042]` — the "~$25k" pro-rata-side-letter skip threshold: not confirmed against any named source this pass; treat as an unsourced rule of thumb.
- `[KB-VCAP-043]` — the "10-15 slides" deck-length range: not confirmed against a named source this pass.
