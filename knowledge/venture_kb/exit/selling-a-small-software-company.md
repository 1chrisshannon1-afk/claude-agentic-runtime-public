# Selling a small software company

**What this file answers.** Who actually buys a small (pre-revenue to roughly $10M ARR) software
company, what each buyer type is really paying for, how to put a defensible number on a company
that has little or no revenue versus one with a revenue history, what the sale process looks like
step by step and how long it takes, how to reach buyers without a banker, how to create competitive
tension between more than one interested party, and the specific things that kill a deal after it
looked live. It is written for a first-time, solo, US-based technical founder selling their own
small SaaS or software company — not a venture-backed company doing a $50M+ strategic sale, though
many of the mechanics scale down from that world. Pair this file with
`deal-structure-and-diligence.md` for what happens once a buyer is actually negotiating, and treat
everything here as information, not legal or tax advice — see the callouts throughout for where an
attorney, CPA, or securities counsel must take over.

---

## 1. Buyer types and what each one is actually paying for

There is no single "market" for a small software company. Five distinct buyer types show up, and
each is underwriting a different thing. Misreading which type you're talking to is the single
biggest source of wasted time in a small-deal process — a strategic acquirer's team will ask
questions a search-fund buyer never would, and vice versa, and pitching the wrong story to the
wrong buyer reads as a founder who doesn't understand their own business.

### 1.1 Strategic acquirers (another operating company)

A strategic buyer is an existing company — often a competitor, a company selling to the same
customer base, or a company that wants your technology inside its own product — buying you to
advance its own operating business, not primarily to run you as a standalone investment.

**What they pay for:** the thing your company gets them that is faster or cheaper to buy than to
build — a customer base already inside your vertical, an engineering team with specific domain
knowledge, a piece of technology (an integration, an algorithm, a data set) that would take their
own team a quarter or two to build, or simply removing a competitor from the market. Revenue
matters far less to a strategic than to a financial buyer; a strategic will sometimes pay a premium
for a company with modest revenue but a hard-to-replicate technical or customer asset, and will
sometimes pay very little for a company with real revenue that doesn't fit their roadmap.
**(internal doctrine, retrieved 2026-09-28)** [KB-VEXIT-001]

**How to find them:** the corporate development ("corp dev") function at companies your size
threatens or complements. Corp dev teams at even mid-size software companies actively track smaller
players in adjacent categories; a cold, well-targeted email to a named corp dev contact (never a
generic `info@` inbox) describing the specific strategic fit is a normal and expected channel — see
§6.

### 1.2 Private equity and holding companies (financial buyers, "buy and hold")

This category spans two related models that a first-time founder should tell apart:

- **Traditional PE** buys a company (usually with meaningful existing revenue and profit, often
  $2M+ EBITDA) with a plan to grow it operationally and sell again in 3-7 years, typically using
  some debt in the purchase.
- **Permanent-capital holding companies** (the model popularized by firms structured after Berkshire
  Hathaway and, in the small-software space specifically, the public roll-up model pioneered by
  Constellation Software and imitated by a wave of smaller "software holdco" buyers since the
  early 2020s) buy small, profitable, often niche/vertical software businesses with **no intent to
  ever sell them again** — they are underwriting a long-hold cash-flow stream, not a resale. This
  model is specifically friendly to a small, profitable, boring, low-growth vertical SaaS product
  that a traditional venture-backed acquirer would never look at, because permanent-capital buyers
  do not need hypergrowth — they need durable, profitable, low-churn recurring revenue.
  **(internal doctrine, retrieved 2026-09-28 — Constellation Software's own public buy-and-hold
  strategy and the holdco model it inspired are widely reported facts in the software-M&A
  press; treat the general mechanism as doctrine and re-verify any specific firm's current
  criteria before approaching them, since underwriting bars move)** [KB-VEXIT-002]

**What they pay for:** predictable, recurring cash flow, low customer concentration, low key-person
dependency (the business must survive the founder leaving), and a clean, well-documented company
(see `deal-structure-and-diligence.md` §4-§5 for the data-room checklist and diligence red flags this buyer type runs hardest).
They pay on a multiple of revenue or, once a company has real profit, a multiple of EBITDA — see
§2.

### 1.3 Search funds (an individual buyer raising capital to buy one company)

A search fund is typically one or two people (often recent MBA graduates or experienced operators)
who raise capital from a small group of investors specifically to find, buy, and then personally
run one company for several years. They behave like a financial buyer in underwriting (profitable,
durable cash flow, low key-person risk) but like a strategic in engagement — the buyer intends to
become your full-time replacement as CEO/operator, so they care intensely about transition support,
whether the business can run without you personally, and whether the team will stay.
**(internal doctrine, retrieved 2026-09-28)** [KB-VEXIT-003]

### 1.4 Individual buyers via marketplaces (Acquire.com, Flippa, MicroAcquire's successor)

Acquire.com (the platform formerly known as MicroAcquire) is a self-serve marketplace connecting
sellers of small, mostly bootstrapped SaaS and internet businesses directly with individual and
small-group buyers, without requiring a broker. As of this KB's retrieval date, Acquire.com's own
homepage states **$500M+ closed deal volume and 2,000+ startups sold** on the platform, and it
targets operator-buyers and small search-fund-style buyers with typical deal sizes under $2M
**(official, Acquire.com homepage, retrieved 2026-09-28 via direct fetch — self-reported figures,
methodology not independently audited)** [KB-VEXIT-004]. Acquire.com's own seller pricing states a **6-8% closing
fee due only at close** (no fee if the deal doesn't close) plus a **$25-100/month listing fee**
while the listing is live; the closing-fee percentage is tiered by deal size, with smaller deals
landing at the higher end of the range **(official, Acquire.com seller pricing page, retrieved
2026-09-28)** [KB-VEXIT-005].

**What this buyer type pays for:** speed and self-service more than anything — many of these
buyers are themselves first-time acquirers, and the marketplace format favors a company with a
clean, simple story that can be understood from a listing page and a short set of calls, without
months of relationship-building. This channel works best for pre-revenue to a few million ARR;
larger deals move to a broker or banker relationship instead.

### 1.5 Brokers as buyer-facilitators (FE International, Empire Flippers, and similar)

Brokers don't buy the company themselves — they represent the seller and run the sale process
(listing, vetting inbound buyers, negotiating, closing) in exchange for a commission, similar to a
real-estate agent. Two of the most established firms in the online-business/SaaS space:

- **FE International** — an advisory firm reporting more than 1,500 completed transactions since
  2010 and a 94.1% reported close rate on engaged mandates **(official, FE International, retrieved
  2026-09-28 — firm-reported figures)** [KB-VEXIT-006].
- **Empire Flippers** — a highly selective marketplace/brokerage. Its own commission calculator uses
  a **blended, tiered rate: 15% on the first $700,000 of sale price, 8% on the portion from $700,001
  to $5,000,000, and 2.5% on any amount above $5,000,000** — so on a typical sub-$700K deal (which
  covers most first-time-founder exits) the effective rate is the full 15% — **plus a $10,000 minimum
  commission on any deal under roughly $66,667** (below which the 15% tier alone would produce less
  than $10,000). `UNVERIFIED — seeded, needs derivation`: a prior version of this file cited "sellers
  report achieving 88% of asking price on average" as `(official)`; that figure does not appear on
  Empire Flippers' sell-your-business or how-it-works pages and has been removed rather than carried
  forward unsourced. **(official, Empire Flippers commission calculator, for the tiered rate and
  minimum commission only, retrieved 2026-09-28)** [KB-VEXIT-007].

**When a broker is worth it vs. not:** see `deal-structure-and-diligence.md` §7 for the full
cost/benefit breakdown, including when a deal is too small to justify any advisor at all.

---

## 2. Valuing pre-revenue, tiny-revenue, and revenue-generating software

### 2.1 Pre-revenue or near-zero revenue: value the assets and the team, not the multiple

A revenue multiple is meaningless on $0-$5K/month of revenue — there is no meaningful trend line to
multiply. Three honest valuation frames apply instead, and a founder should know which one a given
buyer conversation is actually using:

1. **Asset / technology sale.** The buyer is paying for the codebase, the IP, any proprietary data,
   and possibly a customer list — priced roughly at what it would cost the buyer to build the same
   thing from scratch, discounted for the risk and time saved. This is usually a small, one-time
   cash number (commonly low five figures to low six figures for a genuinely small, single-founder
   product), structured as an asset sale (see `deal-structure-and-diligence.md` §1) with no ongoing
   obligation to the seller.
2. **Acqui-hire.** The buyer is paying primarily for the founder(s) and any team joining as
   employees; the "purchase price" is often mostly deferred as salary, a signing bonus, or
   time-vested equity in the acquirer, with a token amount (sometimes near-zero) allocated to the
   company itself. This is common when a strategic buyer wants the engineering talent more than the
   product, and it should be evaluated as a job offer with a small signing transaction attached, not
   as a company sale — the economics live almost entirely in the employment terms, which a
   securities/employment attorney should review before signing anything.
3. **Replacement-cost logic from the buyer's side.** Even when a deal is framed as a "company sale,"
   a sophisticated buyer at this size is mentally running the replacement-cost math: engineering
   months saved, time-to-market saved, and the discounted value of not having to recruit a team.
   Founders can use this same frame to build their own asking-price floor — price at a discount to
   what a competent contractor or in-house team would charge to rebuild the same functionality,
   plus a premium for the time saved.

**(internal doctrine, retrieved 2026-09-28)** [KB-VEXIT-008]

### 2.2 Revenue-generating software: multiples by ARR band

Once a company has a real, recurring revenue history (even a small one), buyers price it as a
multiple of Annual Recurring Revenue (ARR) — or, once it is profitable, sometimes a multiple of
Seller's Discretionary Earnings (SDE) or EBITDA instead. The ranges below are **private-transaction
ranges**, meaningfully lower than the multiples reported for public SaaS companies, and they move
with the broader market — re-verify before using any of these numbers to anchor a real
conversation, per the citation-style guidance on re-pulling numbers older than ~90 days.

| ARR band | Typical private multiple range | Basis |
|---|---|---|
| Under $1M ARR | 2x-3x ARR (often priced on SDE at 2.5x-4x SDE instead) | (third-party, FE International, retrieved 2026-09-28) |
| $1M-$3M ARR | 2.5x-3.5x ARR | (third-party, FE International, retrieved 2026-09-28) |
| $3M-$5M ARR | 3x-4.5x ARR | (third-party, FE International, retrieved 2026-09-28) |
| $5M-$10M ARR | 3.5x-5.5x ARR | (third-party, FE International, retrieved 2026-09-28) |
| $10M-$20M ARR | 4x-6x ARR (top quartile 7.5x) | (third-party, FE International, retrieved 2026-09-28) |
| $20M+ ARR | 5x-7x ARR (8x+ for "Rule of 40"-qualifying businesses with NRR above ~120%) | (third-party, FE International, retrieved 2026-09-28) |

**(third-party, FE International "SaaS Valuation Multiples in 2026: Private Deal Benchmarks by ARR,
Growth, and Retention," retrieved 2026-09-28 via direct fetch — the firm states these ranges reflect
its own advisory transaction data (1,500+ completed transactions, 94.1% success rate) cross-checked
against public SaaS comparables; the full band table is published as an image on the page rather than
as machine-readable text, so the row figures above are read from that image; treat as directional
private-market benchmarks, not a guarantee for any single company, and note the firm has a commercial
interest in appearing authoritative on this topic)** [KB-VEXIT-009]

A second, independent data point: the SaaS Capital Index tracks a basket of **public** B2B SaaS
companies — it is not a survey of private companies in the $3M-$20M
ARR range specifically. The one figure confirmed by this KB's research is that the Index's median
growth rate fell to the low teens as SaaS valuations broadly hit decade-plus lows in Q1 2026, with
public markets pricing in AI-driven disruption risk to existing SaaS categories. `UNVERIFIED —
seeded, needs derivation`: the 3.5x-5.5x private-transaction range, the 5.3x equity-backed median,
and the 4.8x bootstrapped-overall median that a prior version of this file attributed to SaaS Capital
do not appear on SaaS Capital's own cited blog post and have been removed — do not cite them as
`(third-party)` until they are independently confirmed against a primary SaaS Capital publication.
**(third-party, SaaS Capital, retrieved 2026-09-28, for the low-teens median-growth and decade-plus-low
valuation claims only)** [KB-VEXIT-010]

**"Rule of 40" premium.** FE International's own FAQ states only that companies "clearing the Rule of
40 with net revenue retention above 120%" reach **8x and above** ARR — the top of the $20M+ band in
the table above, not a separate, higher band. `UNVERIFIED — seeded, needs derivation`: a prior version
of this file cited a distinct "7x-9x ARR" range for Rule-of-40 qualifiers, which is not FE
International's own wording and is not independently confirmed elsewhere; that figure has been
removed. Cite the source's actual wording ("8x and above ARR is reachable for companies clearing the
Rule of 40 with net revenue retention above 120%") rather than a specific range beyond that floor.
**(third-party, FE International, retrieved 2026-09-28 via direct fetch)** [KB-VEXIT-011]

### 2.3 What actually moves a company up or down within its band

Inside any given ARR band, the actual multiple a specific company gets depends on:

- **Growth rate and its trend direction** — accelerating beats flat beats decelerating, even at the
  same absolute ARR.
- **Net revenue retention (NRR)** — a business where existing customers expand their spend over
  time (NRR > 100%) is worth meaningfully more than one that merely replaces churned revenue with
  new logos.
- **Customer concentration** — one customer at >20% of revenue is a red flag buyers will discount
  for or require a structural fix on (see `deal-structure-and-diligence.md` §5).
- **Gross margin** — software with high, clean gross margin (minimal cost of hosting/support per
  customer) prices better than software with heavy services/implementation cost baked in.
- **Founder dependency** — a business that visibly cannot run without the founder personally selling,
  supporting, or coding is priced down, or the buyer will insist on a longer, harder transition
  period (see `deal-structure-and-diligence.md` §2.5 on transition services agreements).
- **Vertical foothold** — a defensible position in a specific, named vertical (a compliance
  requirement, a data integration, a certification) that a generic competitor can't easily copy
  raises the multiple, especially to a strategic buyer or a permanent-capital holdco looking for
  a durable niche.

**Decision rule:** never anchor a founder's own expectation, or a buyer conversation, on a single
multiple number pulled from memory or from one blog post. Always (a) identify the correct ARR band,
(b) check at least two independently sourced ranges for that band, (c) adjust up or down for the
five factors above, and (d) treat the result as a range, not a point estimate, until a real buyer's
own offer sets a market data point.

---

## 3. The process, start to finish

A small software company sale generally follows the same skeleton as a larger M&A deal, compressed:

1. **Preparation.** Clean financials, a data room started (see `deal-structure-and-diligence.md`
   §4), a one-paragraph description of the business, and a decision on which buyer types to target
   first (§1 above). This is also when any diligence red flags (§5 of the companion file) should be
   found and fixed — fixing an IP-assignment gap before a buyer finds it is dramatically cheaper
   than fixing it under deal pressure.
2. **Teaser.** A one-to-two page anonymized summary — revenue band, growth, vertical, why it's for
   sale, no company name — sent to prospective buyers or corp dev contacts to gauge interest without
   revealing identity prematurely.
3. **NDA.** A mutual non-disclosure agreement signed before the company's identity and real
   financials are shared. A generic NDA template reviewed once by an attorney can be reused across
   many buyer conversations; never skip this step to save a day, since it is the only thing standing
   between "buyer sees your real numbers" and "the deal falls apart with your numbers already out."
4. **CIM (Confidential Information Memorandum).** A fuller document — company history, product,
   team, financials, customer base, growth story, and the specific ask — shared only after the NDA
   is signed. For a small deal this is often 10-20 pages, not the 50+-page CIM of a large sale.
5. **Management calls / Q&A.** Live calls where the buyer's team asks about the business, the
   product, the market, and the team. Expect multiple rounds as buyer interest firms up.
6. **LOI (Letter of Intent).** A short document setting out the buyer's proposed price, structure,
   and key terms, and — critically — an exclusivity period during which the seller agrees not to
   shop the deal to other buyers (see `deal-structure-and-diligence.md` §3 for what in an LOI is
   actually binding versus not, and §6 for how to negotiate the exclusivity window).
7. **Exclusivity + full diligence.** The buyer now digs into the data room in earnest: legal,
   financial, technical, and (if relevant) security/privacy diligence. This is where most deals that
   die, die (§6 below).
8. **Purchase agreement negotiation.** The attorneys on both sides turn the LOI's terms into a
   binding asset purchase agreement or stock purchase agreement, with full reps and warranties,
   indemnification terms, and closing conditions (see `deal-structure-and-diligence.md` §1-§3).
9. **Close.** Signing and funding — cash (and any escrow, earnout, or seller-note terms) moves,
   ownership transfers, and any transition-services period begins.

**Timelines.** There is no single authoritative published timeline specific to sub-$5M software
deals; general M&A industry guidance places the process from initial buyer outreach to close
commonly in the 4-9 month range for a well-prepared small-to-mid-size company, with pre-revenue or
asset-style deals sometimes closing much faster (weeks, not months) because there is no meaningful
financial diligence to run. **UNVERIFIED — seeded, needs derivation (this range is a general M&A
industry heuristic reported across multiple advisory-firm sources, not confirmed against a single
authoritative, dated primary source specific to small software transactions; treat any specific
timeline commitment to a real buyer as a negotiated fact, not this benchmark)** [KB-VEXIT-012]

---

## 4. Reaching buyers directly: corporate development outreach

A founder does not need a banker to reach a strategic acquirer. Corp dev teams at software
companies actively want inbound from smaller companies that fit their roadmap — cold, well-targeted
outreach to a named corp dev contact is a normal, expected channel, not an imposition.

**What makes corp dev outreach land:**
- Address a real named person on the corp dev or business-development team, never a generic
  `partnerships@` or `info@` inbox.
- Lead with the specific strategic fit in one sentence (the customer base, the integration, the
  vertical foothold) — not a generic "we're for sale" pitch.
- Keep the first message short enough to read in 30 seconds; the teaser document (§3 above) is the
  follow-up, not the opener.
- Any compliant B2B cold-email outreach must follow the CAN-SPAM requirements covered in the
  bizdev/outbound KB (working opt-out, accurate header/from information, physical postal address) —
  see that corpus for the compliance mechanics; this file only covers who to contact and why.

**Decision rule:** run corp dev outreach and marketplace/broker listing in parallel, not
sequentially — a strategic conversation can take months to develop interest, and running it
alongside a marketplace listing or broker process creates the competitive tension described in §5
without cannibalizing either channel.

---

## 5. Creating competitive tension with more than one interested party

A single interested buyer has no reason to improve their offer. The mechanics that create real
competitive tension in a small deal:

- **Run more than one channel at once** (corp dev outreach + a marketplace listing + a broker, or
  any two of the three) rather than waiting to see if one channel produces a buyer before trying
  another.
- **Disclose, honestly, that other conversations are happening** once a real second conversation
  exists — never bluff a nonexistent second buyer; a sophisticated buyer's diligence will often
  surface a bluff (shared investor networks, common advisors, or simply asking directly), and a
  caught bluff destroys trust in every future round of the same negotiation.
- **Set a soft deadline for LOIs** once genuine multi-party interest exists, so buyers know a
  decision point is coming rather than assuming they can negotiate indefinitely.
- **Never let exclusivity start before it has to.** Once an LOI grants a buyer exclusivity (§3
  above, §6 of the companion file), competitive tension ends — so time the exclusivity grant to the
  point where the seller is confident that buyer is the right one, not simply the first one to make
  an offer.

**(internal doctrine, retrieved 2026-09-28 — standard small-M&A practice; no single regulator or
vendor source governs deal-process tactics)** [KB-VEXIT-013]

---

## 6. What kills deals

The most common, well-documented deal-killers for a small software sale, gathered from the
diligence-red-flag literature and cross-referenced with `deal-structure-and-diligence.md` §5:

- **IP not actually assigned to the company** — code written by a contractor, a co-founder before
  incorporation, or an employee without a signed invention-assignment agreement. This is the single
  most common and most fixable-in-advance killer; fix it before going to market (see the companion
  file's §4).
- **Customer or revenue concentration discovered late** — a buyer who learns during diligence that
  one customer is 40% of revenue, after underwriting a diversified base, will re-price or walk.
- **Founder over-promising in early calls, then diligence contradicting it** — inflated growth
  claims, an unstated churn problem, or a "the product does X" claim that diligence shows is
  actually manual/human-powered behind the scenes.
- **A co-mingled personal/business entity** — personal expenses run through the company, or company
  revenue mixed with a founder's other ventures, that makes the real financial picture unreadable
  (see the companion file's §5 for how to unwind this before a data room is built).
- **Security or privacy incidents surfacing during diligence** that were not disclosed upfront —
  disclosure early, on the founder's own terms, is always better than a buyer finding it.
- **Seller fatigue / slow responsiveness during diligence** — a multi-month diligence process is a
  second job; a seller who goes quiet or slow-walks document requests reads as either hiding
  something or not serious about closing, and buyers walk from both.
- **Renegotiation after exclusivity ("re-trading")** — a buyer who materially lowers their offer
  once exclusivity has locked the seller out of other conversations, based on a diligence finding
  that doesn't actually justify the size of the cut. This is a well-known bad-faith buyer tactic;
  a seller's best protection is thorough pre-market diligence (so there is nothing left to "find")
  and a short exclusivity window with a hard expiration.
- **No urgency on the buyer's side once exclusivity is granted** — the seller has given up
  competitive tension (§5) and now has no lever left except the exclusivity clock itself; this is
  why the exclusivity window's length is a real negotiating point, not boilerplate (see the
  companion file's §6).

**(internal doctrine, retrieved 2026-09-28 — synthesized from widely reported small-business and
SaaS M&A practitioner sources; no single primary regulator source catalogs "deal killers")**
[KB-VEXIT-014]

---

## Decision rules

- **If** the company has under ~$50K ARR or is pre-revenue, **then** value it on asset/replacement
  cost or acqui-hire terms (§2.1), never on a revenue multiple.
- **If** the company has a real ARR history, **then** find its ARR band (§2.2), check at least two
  independently sourced multiple ranges, and adjust for growth/NRR/concentration/margin/founder-
  dependency/vertical foothold (§2.3) before quoting any number to a buyer or to the operator.
- **If** only one buyer conversation exists, **then** open at least one additional channel (§4, §5)
  before granting exclusivity to that one buyer — a single-threaded negotiation has structurally
  worse terms than a competitive one.
- **If** a buyer is a permanent-capital holding company, **then** lead with durability, profitability,
  and low churn — not growth rate — since that buyer type is explicitly not underwriting
  hypergrowth (§1.2).
- **If** a buyer is a strategic acquirer, **then** lead with the specific asset they can't quickly
  build themselves (technology, customer base, team, vertical foothold) — not a generic financial
  summary (§1.1).
- **If** any diligence red flag from §6 is present, **then** fix it before going to market, not
  after a buyer finds it — see `deal-structure-and-diligence.md` §5 for the fix playbook per flag.
- **If** a deal size is small enough that a broker's minimum fee would consume most of the proceeds,
  **then** see `deal-structure-and-diligence.md` §7 for the self-run-process alternative.
- **If** any deal term (price, exclusivity, structure) needs to be committed to a buyer in writing,
  **then** an attorney drafts or reviews it before it is sent — this file and its companion inform
  the founder's own negotiating judgment; they do not replace counsel.

## Anti-patterns

- **Quoting a single multiple number as if it were a fact about this company.** Every multiple in
  §2 is a range from a cited, dated third-party source; treat it as a starting point for a
  negotiation, never as a promise of what a real buyer will pay.
- **Pitching a strategic buyer with a financial-buyer story (or vice versa).** A strategic doesn't
  care about your EBITDA if your team is the asset they want; a permanent-capital holdco doesn't
  care about your growth rate if your churn is high (§1).
- **Treating a marketplace listing (Acquire.com, Flippa) as free.** The closing fee (§1.4) is real
  money due at close; budget for it before setting an asking price.
- **Bluffing a competing offer that doesn't exist.** See §5 — a caught bluff is worse than no
  leverage at all.
- **Letting exclusivity start before real diligence-readiness.** Once exclusivity is granted, the
  seller has no more competitive leverage for the rest of the process (§5, §6).
- **Skipping the teaser/NDA sequence and sending a full CIM with real financials to an unvetted,
  un-NDA'd contact.** This is how a company's real numbers end up circulating outside the deal.
- **Assuming a broker or banker is required at every deal size.** See
  `deal-structure-and-diligence.md` §7 — below a certain size, no advisor's economics work, and a
  founder-run process via a marketplace or direct corp dev outreach is the realistic path.
- **Treating "we got an LOI" as "we have a deal."** An LOI is mostly non-binding (see
  `deal-structure-and-diligence.md` §6); the deal isn't real until the purchase agreement is signed
  and funded.

## Sources

- FE International, "SaaS Valuation Multiples 2026," https://www.feinternational.com/blog/saas-valuation-multiples — publication date 2026-08-25, retrieved 2026-09-28 (third-party)
- Acquire.com, seller pricing page, https://help.acquire.com/how-much-does-it-cost-to-sell — retrieved 2026-09-28 (official)
- Empire Flippers, commission calculator / how-it-works, https://empireflippers.com/how-it-works/ and public commission-structure reporting — retrieved 2026-09-28 (official/third-party)
- SaaS Capital, "Four early 2026 SaaS trends," https://www.saas-capital.com/blog-posts/four-early-2026-saas-trends/ — retrieved 2026-09-28 (third-party; some cited figures came from secondary reporting on this source, flagged inline where so)
- General M&A process/timeline literature — UNVERIFIED, seeded from general industry heuristics, needs derivation against a small-software-specific primary source
