# Deal structure and diligence

**What this file answers.** Once a buyer is actually negotiating (see
`selling-a-small-software-company.md` for how a buyer gets to this point), this file covers how the
deal itself gets structured — asset sale vs. stock sale and why that choice matters a great deal for
taxes and liability, earnouts, escrows and holdbacks, reps and warranties, non-competes, transition
services, and seller notes — plus what a Letter of Intent actually commits either party to, what
exclusivity means, what a small SaaS company's data room should contain, the diligence red flags
that most often stall or kill a deal (and how to fix each one before a buyer ever sees it), and when
paying for an M&A advisor or banker makes economic sense versus when the deal is too small to
justify one. Everything here is information for a founder to understand before a real deal, never a
substitute for an attorney, CPA, or securities counsel reviewing the actual documents.

---

## 1. Asset sale vs. stock sale

This is the single most consequential structural decision in a small company sale, and buyer and
seller usually want opposite things.

### 1.1 The core mechanics

- **Asset sale.** The buyer purchases specific assets and (usually) assumes specific liabilities of
  the business — the code, the customer contracts, the domain, the trademarks, sometimes specific
  equipment — while the legal entity itself (the LLC or corporation) stays with the seller, along
  with anything not explicitly transferred, including unknown or undisclosed liabilities.
- **Stock sale.** The buyer purchases the ownership interests (stock or membership units) of the
  legal entity itself. The entity, with everything inside it — including any liability the seller
  doesn't know about yet — passes to the buyer.

### 1.2 Why buyers prefer asset sales and sellers often prefer stock sales

**Liability.** In an asset sale, the buyer can cherry-pick which liabilities it assumes and leave
behind anything unknown, contingent, or undisclosed (a pending lawsuit, an unpaid tax liability, a
warranty claim). In a stock sale, the buyer inherits the entity as-is, unknown liabilities included
— which is exactly why buyers, especially unsophisticated first-time buyers, default to preferring
an asset structure, and why a seller who wants a stock sale should expect to negotiate harder for
it and to offer stronger reps and warranties (§3) as compensation for the buyer's added risk.
**(internal doctrine, retrieved 2026-09-28)** [KB-VEXIT-015]

**Tax treatment — the IRS residual method.** For federal tax purposes, when a group of assets that
constitutes a trade or business is sold, the IRS requires the purchase price to be allocated across
seven statutorily defined asset classes using the **residual method**, and both buyer and seller
must file **Form 8594 (Asset Acquisition Statement)**; the allocation binds both only if they agree
to it in writing (IRC §1060(a)). The classes, in the
order consideration is allocated:

| Class | Contents |
|---|---|
| Class I | Cash and general deposit accounts |
| Class II | Actively traded personal property, certificates of deposit, foreign currency |
| Class III | Debt instruments and mark-to-market assets (excluding related-party/contingent/convertible debt) |
| Class IV | Inventory / stock in trade |
| Class V | All assets other than those in Classes I-IV, VI, and VII (tangible assets not in another class, e.g. equipment, furniture, vehicles, and land/buildings) |
| Class VI | Section 197 intangibles other than goodwill (customer lists, workforce, trademarks, non-compete covenants) |
| Class VII | Goodwill and going-concern value |

Consideration is applied to each class in order, up to the fair market value of the assets in that
class, before any amount is allocated to the next class — meaning goodwill (Class VII) absorbs
whatever purchase price is left over after every more specific asset class is accounted for.
**(official, IRS Instructions for Form 8594, retrieved 2026-09-28)** [KB-VEXIT-016]

**Why the allocation matters to both sides, and why they usually disagree:** the buyer generally
wants more of the price allocated to depreciable/amortizable assets (Classes V and VI, and even
goodwill under Section 197, which is amortizable over 15 years) to maximize future tax
deductions, while the seller generally wants more allocated to capital assets that qualify for
capital-gains treatment rather than ordinary income. **The allocation is binding on both the buyer
and the seller only if they agree to it in writing** — under IRC §1060(a), an asset acquisition's
allocation, as agreed to in a written agreement between the parties, is binding on both unless the
IRS determines it is not appropriate. Form 8594 itself asks (Part II, line 5) whether the buyer and
seller's allocation of the sales price is determined by such a written agreement. Neither the Form
8594 instructions nor the IRS's own "Sale of a Business" page states that a mismatch between the two
parties' filed forms is a known audit trigger — that framing is dropped here as unsupported; the
practical takeaway that survives is that the buyer and seller are expected to negotiate and agree on
the allocation, in writing, as part of the purchase agreement, because doing so is what makes the
allocation binding in the first place. **(official, IRC §1060(a) and Form 8594's own written-agreement
question, retrieved 2026-09-28)** [KB-VEXIT-017]

Separately, the IRS treats a sale of business assets as a sale of each underlying asset, not the
business as a single unit — capital assets generate capital gain or loss, depreciable/real property
held over a year falls under Section 1231 treatment, and inventory generates ordinary income or
loss. This is why the Class-by-Class allocation directly determines how much of the total sale
price is taxed at capital-gains rates versus ordinary-income rates. **(official, IRS, "Sale of a
Business," retrieved 2026-09-28)** [KB-VEXIT-018]

**A stock sale is simpler on this axis** — the seller generally recognizes a single capital gain or
loss on the sale of the stock itself, with no asset-by-asset allocation exercise — which is a second
reason sellers often prefer it, on top of the liability question above. **Which structure is
actually better for a specific seller depends on the entity type (C-corp, S-corp, single-member LLC
taxed as a disregarded entity, multi-member LLC/partnership), the seller's basis in the assets, and
the buyer's own tax posture — this is a CPA and tax-attorney decision, made with the actual purchase
price and asset mix in hand, not a generic rule this file can give.** [KB-VEXIT-019]

### 1.3 Decision rule for structure

- **If** the seller's entity is a C-corporation with appreciated assets, **then** flag the classic
  "double taxation" risk of an asset sale (tax at the corporate level on the sale, then again when
  proceeds are distributed to the shareholder) for the CPA to model against a stock-sale
  alternative before any number is agreed with a buyer.
- **If** the buyer is asking for an asset sale and the seller has minimal disclosed/undisclosed
  liability risk, **then** an asset sale is usually the lower-friction path to close, since it is
  what most buyers expect and will fight least to get.
- **If** the seller wants a stock sale, **then** expect the buyer to require stronger reps and
  warranties (§3) and possibly a larger escrow/holdback (§2) as the price of taking on unknown
  liabilities.

---

## 2. Earnouts, escrows, holdbacks, and seller notes — bridging a valuation gap

These are the mechanisms that let a buyer and seller close a deal even when they don't fully agree
on value or risk, by shifting part of the payment to later and making it conditional.

### 2.1 Earnouts

Part of the purchase price is paid later, contingent on the business hitting agreed performance
targets (commonly revenue or gross-profit thresholds) over a defined period after close (commonly
1-3 years). Earnouts are most common when the buyer is skeptical of the seller's growth story, or
when the seller believes the company is worth more than the buyer's underwriting supports and is
willing to bet on their own forecast.

**If the buyer is financing the purchase with an SBA 7(a) loan, seller earnouts are prohibited
outright.** SBA's SOP 50 10 8 and 8.1 both state that "seller earnouts are prohibited; however,
buyer rebates based on business performance are allowed because this is a benefit to the Borrower" —
and if the borrower receives a rebate payment from the seller, SBA requires the proceeds to be
applied to pay down the principal balance of the 7(a) loan. This is a hard SBA program rule, not a
negotiating position: an earnout structure of the kind described below simply cannot be paired with
SBA financing, which rules it out for the large majority of individual buyers of a small business
(see the companion file's §3 on SBA financing generally). **(official, SBA SOP 50 10 8.1, effective
2026-10-01, read directly from the .docx published at legacy.sba.gov, retrieved 2026-09-28)**
[KB-VEXIT-020b]

**What to get in writing before agreeing to any earnout:** the exact metric and how it's measured
(and by whom — never leave post-close accounting entirely in the buyer's hands with no seller
audit right), the payment schedule, what happens if the buyer changes how the acquired business is
run in a way that suppresses the metric (a common and well-known source of earnout disputes — a
buyer who reassigns the sales team, changes pricing, or merges the product into another one can
tank an earnout's numbers without technically breaching anything), and a dispute-resolution
mechanism. **An earnout is only as good as the seller's ability to actually verify and enforce it
after they've lost operational control — an attorney should negotiate the operating covenants that
protect the metric, not just the number.** **(internal doctrine, retrieved 2026-09-28)**
[KB-VEXIT-020]

### 2.2 Escrows and holdbacks

A portion of the purchase price (commonly in the range of roughly 5-15% of deal value, though this
varies by deal and risk profile) is withheld — either placed with a neutral third-party escrow agent
or simply held back by the buyer — for a fixed period after close (commonly 12-24 months) to cover
any claims that arise under the reps and warranties (§3) or indemnification provisions. This is
distinct from an earnout: an escrow/holdback is the seller's own money being protected against a
future claim, not new money conditional on performance. **UNVERIFIED — seeded, needs derivation
(the percentage and duration ranges above are general M&A market practice reported across multiple
advisory sources, not confirmed against one authoritative, dated primary source specific to small
software deals; treat any real escrow term as a negotiated fact specific to that deal)**
[KB-VEXIT-021]

### 2.3 Reps and warranties

Statements the seller makes about the state of the business as of closing — that the company owns
its IP free and clear, that the financial statements are accurate, that there's no undisclosed
litigation, that taxes are current, that material contracts are disclosed and in good standing, and
so on. A breach discovered after close is what the escrow/holdback and indemnification provisions
exist to remedy. **The single best protection against a rep-and-warranty claim is for every
statement to already be true and documented before the deal is signed** — which is exactly what the
diligence-readiness work in §4-§5 below accomplishes.

### 2.4 Non-competes

A covenant restricting the seller from starting or joining a competing business for a defined period
and geography after the sale. **Important current-law context, and the actual sequence of what
happened:** the FTC's 2024 rule that would have banned most non-compete agreements nationwide was
never vacated by the agency itself. A federal district court (Ryan, LLC v. FTC, N.D. Tex., 2024) held
that the FTC exceeded its statutory authority and that the rule was arbitrary and capricious, and
"set aside" the rule under APA §706(2). The FTC did not accept that outcome immediately — it kept the
rule's appeal alive until September 5, 2025, when the Commission voted 3-1 to dismiss its own appeals
in Ryan and in a parallel case (Properties of the Villages v. FTC) and "accede to the vacatur." Only
then, in a February 12, 2026 Federal Register final rule, did the FTC formally remove the Non-Compete
Rule (16 CFR Part 910) from the Code of Federal Regulations, effective that same day. So: court
vacatur (2024) → FTC accession by dismissing its own appeals (September 5, 2025) → formal CFR removal
(February 12, 2026) — not an FTC self-vacatur in September 2024. As of this KB's retrieval date there
is **no federal ban** on non-competes, and enforceability is governed entirely by **state law**,
which varies widely (several states, including California, ban employee non-competes outright by
statute, though the treatment of a non-compete signed as part of a business sale — rather than an
employment relationship — is often treated more permissively even in restrictive states). The FTC has
said it will pursue non-competes it views as anticompetitive through case-by-case enforcement rather
than a blanket rule going forward. **(official, Federal Register 2026-02866, 91 FR 6507, Feb. 12,
2026, retrieved 2026-09-28 via direct fetch of the document's full text — the specific state-by-state
enforceability landscape is a state-law question a business attorney must confirm for the seller's
actual state and the buyer's chosen governing-law state)** [KB-VEXIT-022]

**Decision rule:** never assume a non-compete term is enforceable or unenforceable based on general
knowledge — the seller's actual state of residence/incorporation and the buyer's proposed governing
law both matter, and this is squarely a question for the deal attorney, not this file.

### 2.5 Transition services agreements (TSAs)

A defined period (commonly 30-180 days for a small deal, sometimes longer) during which the seller
continues to support the business post-close — training the buyer's team, answering technical
questions, sometimes continuing limited customer support — usually for a stated fee or as a
condition of the purchase price, and always with an explicit end date. A TSA is where "founder
dependency" (see the companion file §2.3) gets converted from a valuation discount into a bounded,
paid, time-limited commitment; a buyer who is worried the business can't run without the founder
will always ask for one, and a seller who wants to be done can negotiate the length down rather than
refuse it outright, since refusing outright often reads as evasive and can itself become a
diligence red flag (§4).

### 2.6 Seller notes

Part of the purchase price is structured as a loan from the seller to the buyer, repaid over time
(commonly 1-5 years) with interest, instead of cash at close. This is common when a buyer (a search
fund especially, see the companion file §1.3) cannot or does not want to finance the entire purchase
price upfront, and it signals the seller's own confidence in the business's ability to keep
generating cash under the new owner — a seller unwilling to accept any note at all on a deal that
otherwise wants one is sometimes read by the buyer as the seller not truly believing their own
growth story. **A seller note is real credit risk to the seller** — if the buyer runs the company
into the ground, the note may not get repaid — so it should be sized so that a total loss of the
note amount would not be catastrophic to the seller, and ideally secured against specific company
assets, which is a term for the attorney to negotiate.

---

## 3. Letters of intent — what's binding and what isn't

An LOI is typically **mostly non-binding** on the core deal terms (price, structure, most
conditions) — it is a statement of intent to proceed toward a definitive agreement, not the
agreement itself. **Two provisions inside an LOI are typically binding even though the rest isn't:**

1. **Exclusivity / "no-shop."** A clause committing the seller not to solicit, negotiate with, or
   accept an offer from any other buyer for a defined period (commonly 30-90 days for a small deal).
   This is the clause that ends the competitive tension described in the companion file's §5 — once
   signed, the seller has effectively bet the whole process on this one buyer closing.
2. **Confidentiality.** Typically a standalone binding obligation (or incorporated from an earlier
   NDA) covering what either party learned during the LOI negotiation itself.

**Decision rules:**
- **If** an LOI's exclusivity period seems long relative to the deal's complexity (a simple,
  small asset sale needing 90+ days of exclusivity is a warning sign), **then** negotiate it down or
  ask the buyer why more time is needed — a buyer with a real, well-resourced diligence team should
  not need months of exclusive lock-up for a small company.
- **If** a buyer asks the seller to treat any other LOI term as binding beyond exclusivity and
  confidentiality, **then** that request itself needs an attorney's review before signing — it is
  not standard.
- **Never treat "we signed an LOI" as "we have a deal."** The deal is the definitive purchase
  agreement; the LOI is the on-ramp to negotiating it, and either party can generally walk away
  from the non-binding terms (though not the exclusivity/confidentiality provisions) if diligence
  changes the picture.

---

## 4. Data room index for a small SaaS company

A data room is the organized set of documents a buyer's diligence team reviews. Building it before
going to market — not scrambling to assemble it once a buyer asks — is one of the highest-leverage
things a founder can do, because it surfaces the red flags in §5 while there's still time to fix
them quietly.

**Corporate**
- Certificate of incorporation / formation, bylaws or operating agreement, cap table, all
  stockholder/member agreements.
- Board and shareholder consent history (even a single-founder company should have basic corporate
  formalities documented).

**IP assignment chain — the single most-checked section**
- Founder invention-assignment/IP-assignment agreements (every founder, signed at or before
  incorporation).
- Every contractor and agency agreement that ever touched the codebase, each with a signed IP
  assignment clause — an unsigned or missing assignment from even one long-departed contractor is a
  real, documented gap a buyer's counsel will find.
- Every employee's proprietary-information and invention-assignment agreement (signed at hire).
- Trademark and domain registration records.

**Open-source licenses**
- A current software-composition inventory of every open-source dependency and its license type,
  flagging anything under a "copyleft" license (GPL-family) that could create an obligation to
  release proprietary source code if triggered — this is a genuine, well-known SaaS diligence
  concern and should be resolved (or at minimum documented and explained) before a buyer's technical
  diligence team runs their own scan and finds it first.

**Customer contracts**
- Every active customer agreement or the current standard terms of service, any non-standard
  negotiated terms, and a summary of customer concentration (% of revenue from the largest 1, 5,
  and 10 customers).
- Any customer contract containing a change-of-control clause requiring consent before the deal can
  close — these must be identified early, since obtaining consent can take real time.

**Security posture**
- A summary of the security architecture (authentication, encryption at rest/in transit, access
  controls), any past security incidents and how they were handled and disclosed, and any
  certifications held (SOC 2, ISO 27001) or explicitly not held.

**Privacy — and specifically health-data (HIPAA) exposure**
- If the product processes any protected health information (PHI) on behalf of a healthcare
  provider or health plan, the company is very likely a **HIPAA "business associate"** — a person or
  entity that creates, receives, maintains, or transmits protected health information on behalf of a
  covered entity, other than as that entity's own workforce member — which requires a signed
  **Business Associate Agreement (BAA)** with each covered-entity customer and creates its own set
  of security and breach-notification obligations under the HIPAA Security and Breach Notification
  Rules. **UNVERIFIED (primary source unreachable: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-160/subpart-A/section-160.103) —
  the definition above is this KB's own restatement of the commonly cited "business associate"
  definition, not a claim confirmed by a direct read of the eCFR text, and it must not be treated as
  `(official)` until that source is actually fetched and read**
  [KB-VEXIT-023]. A buyer acquiring a company with undisclosed BAA obligations, or with PHI exposure
  and no BAAs in place, is discovering a real compliance liability — disclose this upfront (see §5).
- The general privacy posture otherwise: what personal data is collected, what privacy policy is
  published and whether the company's actual practice matches it, and any state privacy law
  exposure (e.g., CCPA-style obligations) relevant to the customer base.

**Financials and tax**
- Financial statements (ideally reviewed or at least internally consistent and reconciled to bank
  records) for the trailing 2-3 years, current cap table, and a clean statement of any related-party
  transactions.
- Tax returns for the same period, and confirmation that all payroll, sales, and income tax
  obligations are current — an unpaid tax liability discovered during diligence is a common
  deal-delayer.

---

## 5. Common diligence red flags — and how to fix each before going to market

| Red flag | Why it kills or stalls deals | Fix before going to market |
|---|---|---|
| **IP not assigned** — a contractor, early collaborator, or pre-incorporation founder never signed an assignment | Buyer's counsel cannot confirm the company actually owns what it's selling; can void the deal outright or force a costly retroactive-assignment negotiation with someone who now has leverage | Get every past contributor's signed retroactive IP assignment now, while relationships are still good and before a sale creates leverage for them to hold out |
| **Co-mingled entities** — personal expenses run through the company, or the company's revenue/costs are mixed with the founder's other ventures | Makes the real financial picture of the business being sold unreadable; a buyer cannot underwrite what they can't isolate | Separate the books fully — dedicated bank accounts, no personal expenses through the company — for at least one full trailing period before going to market; document the un-mingling clearly if any commingling happened historically |
| **Related-party revenue** — a meaningful share of revenue comes from an entity the founder also owns or controls | Buyer cannot trust that revenue would continue at arm's length after the sale, or at all; reads as inflated/non-durable revenue | Disclose it plainly and be prepared for the buyer to discount or exclude it from the valued revenue base — attempting to hide it is worse than disclosing it, since discovery during diligence reads as concealment |
| **Undisclosed security incident** | Discovery during diligence (rather than upfront disclosure) reads as concealment and creates liability under the reps and warranties (§3) even after close | Disclose any past incident upfront, with how it was handled and remediated — an honestly disclosed and well-handled past incident is far less damaging than one a buyer's own technical diligence uncovers independently |
| **Key-person risk** — the business visibly cannot run without the founder personally coding, selling, or supporting customers | Depresses valuation (see companion file §2.3) and increases the buyer's required transition-services length (§2.5) or their eventual walk-away risk | Document processes, cross-train any existing team member, and be honest about the transition-services period a buyer should expect to need — don't claim the business is founder-independent if it isn't |
| **Customer concentration** discovered late in diligence rather than disclosed upfront | Buyer re-prices or adds structural protection (a concentration-specific indemnity, an earnout tied to retaining the concentrated customer) once trust is already strained | Disclose concentration in the teaser/CIM stage (see companion file §3), not as a diligence surprise |
| **Open-source license exposure** (an unvetted copyleft dependency) | Can create an obligation to release proprietary source, which is often a walk-away issue for a strategic or PE buyer's counsel | Run a software-composition scan and resolve or document every copyleft dependency before the data room opens |
| **Missing or informal customer contracts** | Buyer cannot confirm what revenue is actually contractually committed versus month-to-month and revocable | Formalize standard terms of service / master service agreements even for a small customer base, before going to market |

---

## 6. Exclusivity and the no-shop clause — practical mechanics

Covered structurally in §3 above; the practical negotiating point worth restating here: exclusivity
is the seller's single biggest concession in the whole process, because it is one of the two LOI
provisions that are actually binding (§3) and the one that directly ends the competitive tension the
companion file's §5 describes building. **Decision rule:** never grant exclusivity to the first buyer who asks for it
without first confirming (a) the exclusivity period is proportionate to deal complexity, (b) there
is a hard end date with no automatic extension, and (c) the seller has done enough of their own
pre-market diligence readiness (§4-§5) that the buyer is unlikely to find something during the
exclusivity window that resets the negotiation from a position of no remaining leverage.

---

## 7. M&A advisor and banker fees — and when a deal is too small for one

### 7.1 Fee structures

The most common success-fee model for a sell-side advisor on a smaller deal is a version of the
**Lehman formula**, originally: 5% of the first $1M of transaction value, 4% of the second $1M, 3%
of the third, 2% of the fourth, and 1% of everything above $4M. Because the original formula
generates too little fee income to justify the months of work a smaller deal requires, most
advisors working on deals under roughly $5M use a **"Double Lehman"** (also called the "Modified
Lehman Scale") instead: 10% on the first $1M, 8% on the second, 6% on the third, and continuing to
step down on additional tiers. **(third-party, Rejigg "How Much Do Business Brokers Charge? The Real
Cost at Every Deal Size," retrieved 2026-09-28 — the Lehman/Double Lehman formulas are widely cited
industry conventions rather than a single regulator-defined standard; treat the specific percentages
as typical, not universal)** [KB-VEXIT-024]

On top of the success fee, most advisors also charge:
- **A retainer** paid while the advisor prepares the company and runs the process — reported ranges
  span from a few thousand dollars up to $50,000+ depending on the advisor and deal size.
- **A minimum fee floor** — commonly reported in the roughly $50,000-$150,000 range — that applies
  regardless of the Lehman-formula calculation, meaning a very small deal can still generate a large
  effective percentage fee once the floor applies.

**(third-party, Rejigg "How Much Do Business Brokers Charge? The Real Cost at Every Deal Size,"
retrieved 2026-09-28 — a reported market range, not a single authoritative source; the effect of the
minimum-fee floor is the single most important number for a first-time founder to get a real quote on
before assuming an advisor is affordable)** [KB-VEXIT-025]

The marketplace/broker fee structures in the companion file's §1.4-§1.5 (Acquire.com's 6-8% closing
fee, Empire Flippers' 15%/8%/2.5% tiered blend, with a $10,000 minimum commission on deals under
roughly $66,667) are a different, generally lower-friction fee model
than a traditional M&A banker's Lehman-style retainer-plus-success-fee structure, and are typically
the better fit for a deal small enough that a traditional banker's minimum-fee floor would consume
an outsized share of proceeds.

### 7.2 When a small deal can't justify a banker

**Decision rule:** run the math before engaging any advisor. If the advisor's minimum fee (commonly
$50,000+, per §7.1) would represent a large fraction (a common rule of thumb is above roughly
10-15%) of the expected total proceeds, a traditional M&A banker's economics don't work for this
deal — the founder is better served by:

- A **marketplace** (Acquire.com) or **specialized broker** (FE International, Empire Flippers) with
  a percentage-of-close fee structure and no large minimum floor, or
- **Running the process founder-led** entirely — direct corp dev outreach (see companion file §4)
  plus a marketplace listing — using an attorney only for document review at the LOI and purchase-
  agreement stages rather than for running the whole process.

A useful gut-check: **if the expected deal size is under roughly $500K-$1M, a traditional banker
is very unlikely to be economical; in the roughly $1M-$5M range, get real quotes from more than one
advisor and compare the effective total percentage (success fee + retainer, blended) against a
broker/marketplace alternative before committing; above that range, a banker's process and buyer
network typically starts to pay for itself.** **(internal doctrine, retrieved 2026-09-28 — this
threshold framing is derived from the sourced fee ranges above, not itself a cited statistic)**
[KB-VEXIT-026]

---

## Decision rules

- **If** the seller's entity is a C-corp with appreciated assets, **then** get the CPA to model
  asset-sale double-taxation exposure before agreeing to structure (§1.2, §1.3).
- **If** a buyer proposes an asset sale, **then** confirm the Form 8594 allocation is negotiated and
  agreed with the buyer **in writing** before filing — under IRC §1060(a), only a written agreement
  makes the allocation binding on both parties (§1.2).
- **If** an earnout is proposed, **then** confirm it does not violate SBA's ban on seller
  earnouts in an SBA-financed deal (see `selling-a-local-service-business.md` §3.3a), and
  separately insist on written protection for the metric (no unilateral post-close changes that
  suppress it) before agreeing to any earnout-heavy structure (§2.1).
- **If** the product touches protected health information, **then** treat the company as a likely
  HIPAA business associate, confirm BAAs exist with every relevant customer, and disclose this
  status to any buyer upfront rather than letting diligence find it (§4).
- **If** any red flag in §5's table is present, **then** fix it before going to market — every fix
  in that table is cheaper and faster pre-market than under deal pressure.
- **If** an LOI's exclusivity period seems disproportionate to deal size/complexity, **then**
  negotiate it down before signing (§3, §6).
- **If** the expected deal size is under roughly $500K-$1M, **then** do not engage a traditional
  Lehman-fee banker — use a marketplace, a specialized broker, or a founder-led process instead
  (§7.2).
- **If** a non-compete term is being discussed, **then** confirm current state-law enforceability
  with an attorney rather than assuming either a ban or a blanket allowance — there is no federal
  rule either way as of this KB's retrieval date (§2.4).

## Anti-patterns

- **Agreeing to deal structure (asset vs. stock) before the CPA has modeled the actual tax
  consequence for this seller's specific entity type.** §1 shows why this is not a generic
  one-size answer.
- **Treating an LOI as a done deal.** Only exclusivity and confidentiality are typically binding;
  everything else is a statement of intent (§3).
- **Building the data room after a buyer asks for it instead of before going to market.** Every red
  flag in §5 is cheaper to fix with no buyer watching the clock.
- **Hiding customer concentration, related-party revenue, or a past security incident and hoping
  diligence doesn't find it.** Discovery during diligence is treated as concealment even when the
  underlying fact would have been an acceptable, priced-in disclosure (§5).
- **Signing a long exclusivity period with a buyer who hasn't demonstrated real financing or
  seriousness.** This surrenders the seller's only remaining leverage for the length of that window
  (§3, §6).
- **Engaging a traditional M&A banker on a deal too small for the economics to work.** Run the
  minimum-fee math first (§7.2).
- **Assuming a non-compete is either always enforceable or never enforceable.** It's a state-law
  question, and the federal landscape changed materially in 2024-2026 (§2.4).
- **Letting an earnout's metric be defined loosely enough that the buyer can suppress it post-close
  without breaching anything.** Get the operating covenants that protect the metric written into
  the agreement, not just the payment schedule (§2.1).

## Sources

- IRS, Instructions for Form 8594 (Asset Acquisition Statement), https://www.irs.gov/instructions/i8594 — retrieved 2026-09-28 (official)
- IRS, "Sale of a Business," https://www.irs.gov/businesses/small-businesses-self-employed/sale-of-a-business — retrieved 2026-09-28 (official)
- Federal Register, "Revision of the Negative Option Rule, Withdrawal of the CARS Rule, Removal of the Non-Compete Rule To Conform These Rules to Federal Court Decisions," 91 FR 6507, Feb. 12, 2026, https://www.federalregister.gov/documents/2026/02/12/2026-02866/revision-of-the-negative-option-rule-withdrawal-of-the-cars-rule-removal-of-the-non-compete-rule-to — retrieved 2026-09-28 (official; direct fetch succeeded via the document's full-text URL)
- eCFR, 45 CFR 160.103 (HIPAA "business associate" definition) — https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-160/subpart-A/section-160.103 — primary source identified but not fetched/read during this pass. UNVERIFIED (primary source unreachable: https://www.ecfr.gov/current/title-45/subtitle-A/subchapter-C/part-160/subpart-A/section-160.103)
- Aggregated M&A-advisory fee reporting (Lehman/Double Lehman formula, retainer and minimum-fee ranges) — third-party, retrieved 2026-09-28, no single authoritative primary source
- Acquire.com and Empire Flippers fee structures — see `selling-a-small-software-company.md` Sources for citations, cross-referenced here
- Escrow/holdback percentage and duration ranges, and M&A process timelines — UNVERIFIED, seeded from general industry heuristics, needs derivation against a small-software-specific primary source
