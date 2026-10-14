# Co-founder equity, vesting, and agreements

**What this file answers:** how co-founder equity is typically split when someone joins after a
product already exists, how vesting and cliffs work, what single- vs. double-trigger acceleration
means and which is standard, what an 83(b) election is and why its 30-day deadline is absolute,
what advisor equity typically looks like (the FAST agreement), stipends vs. salary, how a share of
sale proceeds differs from real equity when the company sits inside a holding structure with
another business, why IP assignment (a CIIAA) must exist before anyone touches the codebase, how
contractor-vs-employee classification actually works and where the legal risk sits for a cash-poor
startup, and — as a checklist — what must be in writing and when versus what must never be promised
before counsel is involved. **This file is information, not legal, tax, or securities advice.**
Every section below names the professional (attorney, CPA, or securities counsel) who must make the
actual decision and what to bring them; nothing here authorizes signing or promising anything.
Raise/SAFE/priced-round mechanics belong to `capital-and-exit-strategist`'s lane, not this file —
this file covers co-founder and advisor compensation only.

---

## 1. Co-founder equity splits — and how it changes for a late joiner

### What the data actually shows for two-founder teams

Carta's Founder Ownership research, drawn from thousands of companies and tens of thousands of
founders on its platform, finds that **only a minority of two-founder teams split equity exactly
equally**: for two-founder teams, the median split is 51%/49%; three-founder teams commonly split
around 45%/38%/20%; four-founder teams around 40%/25%/19%/12% `[KB-VREC-101]` (third-party, Carta
"How do co-founders actually split equity?", retrieved 2026-09-28). The trend, however, is moving
toward equal splits over time: the rate of exactly-equal splits in two-founder teams rose from
roughly 31.5% in 2015 to roughly 45.9% in a recent year measured `[KB-VREC-102]` (third-party,
Carta, retrieved 2026-09-28). Solo-founder companies have also grown substantially as a share of
all new companies on Carta's platform `[KB-VREC-103]` (third-party, Carta, retrieved 2026-09-28).

### YC's own guidance: default to equal, question the reasons for unequal

YC's published guidance on splitting founder equity argues for equal or close-to-equal splits as
the default, on the logic that when a startup is still pre-scale, the overwhelming majority of the
work and risk is still ahead of the team, not behind it — so early differences (who had the idea,
who started a few months earlier, who is more experienced) matter far less than they feel like they
do at the moment of splitting `[KB-VREC-104]` (official, YC Startup Library "How to Split Equity
Among Co-Founders," retrieved 2026-09-28). YC's companion piece on equity mistakes goes further than
simply listing these as factors to weigh: it names hiring a co-founder **after raising some money**
and hiring a co-founder **post-launch** as two specific *bad* reasons for an unequal split, on the
logic that neither event retires much real risk — even well-funded startups overwhelmingly still
fail, and a co-founder joining at either point is still going to be a key, make-or-break contributor
to everything still ahead, so the founder should be generous and close to equal rather than reach
for a smaller slice `[KB-VREC-105]` (official, YC Startup Library "Co-Founder Equity Mistakes to
Avoid," retrieved 2026-09-28).

**This is genuinely in tension with the case this KB exists for** — a founder whose product is
already mostly built, possibly with real revenue, bringing on a co-founder after that point. **YC's
own framing does not treat this as a neutral factor to weigh — it explicitly names "joined after
fundraising" and "joined post-launch" as bad reasons to reach for a smaller-than-equal split.** Any
reasoning toward a narrower late-joiner split is reasoning against YC's stated position, not an
application of it; that tension should be named to the operator explicitly, with the actual number
left to a real conversation informed by counsel — never resolved by citing YC as support for a
smaller share.

### How to reason about the late-joiner split, without inventing a number

No cited source in this KB gives a single formula that outputs "the correct percentage" for a
late-joining co-founder — treat any specific percentage claimed as a fixed rule as unsourced. What
the cited frameworks agree on as inputs to the conversation:

- **How much of the hardest uncertainty is actually resolved** — a working product with paying
  customers has retired more risk than a working product with zero users, which has retired more
  risk than an idea alone. The more risk already retired, the more the "remaining work is what
  matters" logic in `[KB-VREC-104]` shifts toward a smaller share for the new joiner (there is less
  remaining uncertainty left to earn a larger share of).
- **How much runway of hard work genuinely remains** — if the honest picture is "the product works
  but nothing about revenue, retention, or scaling is proven," a very large share of the real
  founding work is still ahead, and the split should reflect that closer to a day-one split than a
  token grant.
- **What the new co-founder is actually taking on** — full ownership of a function the existing
  founder cannot do at all (e.g. the only technical judgment in the company, or the only person who
  can sell) argues for a larger share than a role that supplements what the existing founder can
  already do adequately.
- **A named, well-known alternative framework: Slicing Pie.** This is a dynamic-equity model that
  allocates equity based on ongoing, tracked contributions (time, cash, relationships, ideas — each
  assigned a multiplier) rather than a fixed grant decided once up front, with the allocation
  recalculated as contributions accrue until the company raises outside capital or becomes
  cash-flow positive `[KB-VREC-106]` UNVERIFIED — seeded, needs derivation (the framework's own
  site, slicingpie.com, was not independently re-fetched this pass to confirm current mechanics;
  verify directly before an agent states Slicing Pie's specific formula or multipliers as current
  fact). **Note YC's own view of dynamic-equity models generally: YC's "Co-Founder Equity Mistakes
  to Avoid" piece calls this style of approach "too fancy" and advises against it in favor of a
  simple, one-time negotiated split** `[KB-VREC-105]` (official, YC Startup Library "Co-Founder
  Equity Mistakes to Avoid," retrieved 2026-09-28) — mention Slicing Pie as a named alternative that
  exists, but do not present it as YC-endorsed or as this KB's recommended mechanism. Slicing Pie is
  best understood as a *mechanism* for handling exactly the late-joiner /
  uneven-contribution problem this section is about, worth knowing exists as an alternative to a
  single fixed-percentage negotiation — not as a recommendation to use it over a simpler, one-time
  negotiated split with standard vesting.

**Decision rule for this specific question is in the Decision rules section below.**

---

## 2. Vesting: the 4-year, 1-year-cliff standard

**Mechanics.** The near-universal standard for both founder and employee equity at venture-style
startups is vesting over 4 years with a 1-year cliff: no shares vest during the first 12 months;
on the 12-month anniversary, 25% of the total grant vests all at once (the "cliff"); the remaining
75% then vests in equal monthly installments (1/48th of the total grant per month) over the
following 36 months `[KB-VREC-107]` (UNVERIFIED — seeded, needs derivation: standard 4-year / 1-year-cliff
monthly-vesting arithmetic, not read from one named source — the
4-year/1-year-cliff structure itself is treated as settled market practice, not a claim needing a
single named primary source; it is also the structure YC's own standard post-incorporation
documents and most institutional-investor term sheets assume as a condition of investment
`[KB-VREC-108]` UNVERIFIED — seeded, needs derivation, YC's own specific template language was not
independently re-fetched this pass to quote verbatim; verify against YC's current Startup Library
equity documentation before quoting exact template text).

**What happens on departure, by scenario:**
- **Leaving voluntarily before the 1-year cliff:** the departing person receives none of the
  unvested grant — this is the entire point of the cliff, protecting the company and the remaining
  founders from a co-founder who leaves within the first year having already earned a meaningful
  equity stake.
- **Leaving voluntarily after the cliff:** the person keeps whatever has vested to date (the cliff
  amount plus any monthly vesting since); unvested shares are typically forfeited back to the
  company's option pool or cap table per the grant's own terms — the specific mechanics (repurchase
  right, forfeiture) are set by the actual stock purchase agreement or equity incentive plan
  document, which only the company's attorney drafts.
- **Termination for cause:** most standard agreements treat this the same as voluntary departure
  for vesting purposes (keep what's vested, forfeit the rest), though some agreements impose
  additional forfeiture or repurchase-at-cost terms specifically for cause — this is exactly the
  kind of provision that must be reviewed and chosen by the company's attorney when the agreement is
  drafted, not decided informally.
- **Termination without cause:** standard treatment is the same vesting mechanics (keep what's
  vested), though this is also where acceleration provisions (§3) can modify the outcome, and is a
  common point of negotiation when the agreement is originally drafted.

---

## 3. Acceleration: single-trigger vs. double-trigger

**Single-trigger acceleration** vests some or all of a person's unvested equity immediately upon a
single defined event — typically a change of control (the company being acquired) — regardless of
whether that person's employment continues or ends `[KB-VREC-109]` (internal doctrine: the definition of
double-trigger acceleration; counsel drafts the actual clause).

**Double-trigger acceleration** requires *two* events before acceleration happens: (1) a change of
control, **and** (2) that specific person being terminated without cause (or resigning for "good
reason" / constructive termination — e.g. a forced title downgrade, pay cut, or relocation) within
a defined window after the deal closes, commonly 12 months `[KB-VREC-110]` (UNVERIFIED — seeded, needs
derivation: the 12-month window is common practice, not read from a named source).

**Double-trigger is the market standard for venture-backed companies and is what NVCA-style model
financing documents are generally understood to assume** `[KB-VREC-111]` UNVERIFIED — seeded, needs
derivation (nvca.org's own current model legal documents were not independently re-fetched and
quoted verbatim this pass to confirm the exact current template language; verify against
nvca.org/model-legal-documents directly before an agent states NVCA's specific current clause
language as fact). The reasoning commonly given: single-trigger acceleration front-loads a cost onto
an acquirer and can hand a windfall to someone who is about to leave anyway with no retention
benefit to the buyer, which makes acquirers price that risk into the deal or resist it outright;
double-trigger protects the founder/employee from being pushed out right after a deal (a real risk,
since an acquirer sometimes wants to replace the founding team) while not penalizing a smooth,
retained transition.

**When single-trigger might still apply:** it is more commonly seen, when it appears at all, in
very founder-favorable early negotiations or in specific board-approved carve-outs — it is the
exception, not the default, and any specific request for single-trigger terms should be evaluated
by the company's attorney against how it will read to a future acquirer or investor, since it can
complicate a future deal.

---

## 4. The 83(b) election — a strict, unforgiving IRS deadline

**What it does.** When a person receives restricted stock that is subject to vesting (the normal
case for founder and early co-founder equity), the default federal tax rule is that they owe
ordinary income tax on the value of each tranche of stock *as it vests* — which can mean paying tax
repeatedly over 4 years, at whatever the stock's fair market value happens to be on each vesting
date (a serious problem if the company's value has grown a lot by then). Filing a **Section 83(b)
election** lets the recipient instead choose to be taxed once, up front, on the value at the time of
grant — which for a very early-stage company is usually low or near-zero — with all future
appreciation taxed later, at sale, as capital gains rather than ordinary income
`[KB-VREC-112]` (official, Treas. Reg. §1.83-2 / IRC §83(b), retrieved 2026-09-28: "When
substantially nonvested property is transferred in connection with the
performance of services, the person who performs the services may elect under IRC § 83(b) to
currently include in gross income the excess of the property's fair market value at the time of
transfer over the amount paid for the property, rather than when the property later becomes
substantially vested.").

**The deadline is strict, with one narrow, mechanical exception.** The election must be filed with
the IRS **no later than 30 calendar days after the date the property is transferred**
`[KB-VREC-113]` (official, IRS Treasury Regulation §1.83-2(b), retrieved 2026-09-28 — the
regulation text states the election "must be filed not later than 30 days after the date the
property was transferred"). This is 30 calendar days, not 30 business days, and there is no
extension for a good-faith mistake and no cure once the deadline (as computed below) passes. The
one exception is mechanical, not discretionary: **if the 30th day itself falls on a Saturday,
Sunday, or legal holiday, IRC §7503 rolls the deadline to the next business day** — Form 15620's
own instructions point to this rule `[KB-VREC-114]` (official, IRS Form 15620 instructions and IRC
§7503, retrieved 2026-09-28). **This is a narrow rollover of the deadline itself, not a general
grace period** — do not read it as license to file late for any other reason, and do not plan on
the rollover; file within the calendar-day window as if no rollover existed, and treat the rollover
only as a backstop if day 30 happens to land on a weekend or holiday. **Missing the (correctly
computed) deadline is irreversible**: the recipient loses the ability to make the election for that
grant entirely and is taxed under the default rule (ordinary income at each vesting date's
then-current fair market value) instead.

**Filing mechanics.** The election is made by filing a written statement — or the IRS's own Form
15620, "Section 83(b) Election" — with the IRS `[KB-VREC-115]` (official, IRS Form 15620 and
associated Publication 525 update guidance, retrieved 2026-09-28: "You can make the choice by
filing a written statement, or Form 15620, Section 83(b) Election, with the Internal Revenue
Service Center where you file your return."). The election statement must include: the name,
address, and taxpayer ID of the person making the election; a description of the property; the
date(s) of transfer and the taxable year for which the election is made; the nature of the
restrictions on the property; the property's fair market value at the time of transfer; the amount
(if any) paid for the property; **the election-maker's signature and a statement that the election
is being made under §83(b)**; and **a statement that copies of the election have been furnished to
the person for whom the services were performed** (i.e., the company) `[KB-VREC-116]` (official,
Treas. Reg. §1.83-2(e), retrieved 2026-09-28). Filing with the IRS is not the only required step:
**the person making the election must also actually furnish a copy of the statement to the company**
(and to any transferee of the property, if different) — this is a separate, independent duty, not
satisfied merely by filing with the IRS `[KB-VREC-117]` (official, Treas. Reg. §1.83-2(d), retrieved
2026-09-28: "the person who performed the services shall also submit a copy of the statement... to
the person for whom the services are performed"). Form 15620 itself repeats both requirements.

**Why this belongs at the top of any co-founder onboarding checklist.** Because the deadline is a
hard calendar cutoff with zero flexibility, and because the tax consequence of missing it can be
severe and permanent, **this is exactly the kind of decision that must go to a CPA or tax attorney
immediately upon any restricted-stock grant to a new co-founder — the same week the grant paperwork
is signed, not "sometime this month."** Do not treat this document, or any general startup-advice
source, as sufficient basis for actually filing; the specific fair-market-value figure, the exact
statement language, and confirmation of current IRS filing procedure (mailing address, any
e-filing option that may exist by the time this is read) must come from a professional who can also
confirm nothing about the company's specific facts changes the standard analysis.

---

## 5. Advisor equity — the FAST agreement

The **Founder/Advisor Standard Template (FAST)**, published by Founder Institute, is a widely-used
standard agreement for granting equity to startup advisors without a full bespoke negotiation each
time `[KB-VREC-118]` (official, Founder Institute FAST agreement page, retrieved 2026-09-28). It
scales advisor equity along two axes: **company stage** (pre-seed, seed, Series A) and **advisor
engagement level** (a "Standard" tier for regular, e.g. monthly, advice, and an "Expert" tier for
deeper involvement such as introductions, recruiting help, or direct customer/deal work)
`[KB-VREC-119]` (official, Founder Institute FAST agreement page, retrieved 2026-09-28).

**Typical ranges reported (Founder Institute's own published matrix):** Standard-tier advisors
around 0.50% at pre-seed, scaling down to roughly 0.25% at seed and roughly 0.10% at Series A;
Expert-tier advisors around 1.00% at pre-seed, scaling down to roughly 0.75% at seed and roughly
0.50% at Series A `[KB-VREC-120]` (official, Founder Institute FAST agreement page, retrieved
2026-09-28 — note that Founder Institute has revised this matrix across versions, e.g. a 2026 "FAST
v3" release reported as simplifying the tier structure and adjusting the lowest tier upward; always
confirm the *current* version's numbers directly from fi.co/fast before quoting a specific
percentage to the operator, rather than relying on a cached figure).

**Vesting for advisor grants under FAST** is a 3-month cliff followed by vesting over 2 years total
— intentionally shorter than the standard 4-year founder schedule because an advisor relationship is
lighter-weight and easier to end cleanly `[KB-VREC-121]` (official, fi.co/fast, retrieved
2026-09-28, verbatim: "The FAST Agreement does include a three-month 'cliff' on equity vesting,
allowing for an unproductive advisory relationship to be terminated without having the burden of
allocating any equity within the first three months" — confirmed directly against the agreement
page itself, current as of this retrieval; re-verify before quoting if significant time has passed).

**Practical rule:** never grant advisor equity informally or "by understanding" — use a written
FAST-style agreement (or the company's own attorney-drafted equivalent) for every advisor, before
any advisory work begins, specifying tier, percentage, vesting, and what the advisor is actually
expected to do. See the Anti-patterns section for the risk of a "handshake" advisor.

---

## 6. Stipends vs. salary

- **A stipend** is a modest, typically fixed periodic payment (not tied to hours worked or output)
  intended to offset real costs (health insurance, basic living expenses) rather than function as
  market-rate compensation. It is common for very early-stage founders and sometimes early
  co-founders in a pre-revenue or barely-revenue company. Tax treatment: a stipend paid to someone
  performing services for the company is still generally treated as compensation for tax purposes
  (subject to withholding if the recipient is an employee, or self-employment tax considerations if
  paid to a contractor) — this is not a way to avoid payroll-tax or classification questions, and
  should be confirmed with a CPA rather than assumed.
- **A deferred or below-market salary** is a formal salary (with normal payroll tax withholding if
  the person is an employee) set below what the role would command at a funded company, with the
  gap made up in equity. This is more common once a company has at least some revenue and can
  commit to a regular payroll obligation, and it more cleanly establishes an employer-employee
  relationship where one is intended (see §9).
- **No cash at all, equity-only** is the highest-risk arrangement from a worker-classification and
  wage-law perspective (see §9) and should always be reviewed with an employment attorney before
  being offered to anyone, co-founder included. **There is no blanket "genuine co-founder" exemption
  from wage law.** A founder who works for the company can still be an employee under wage law; the
  one federal carve-out is the owner exemption at 29 CFR 541.101, which requires at least a
  bona-fide 20% equity interest *and* being actively engaged in management `[KB-VREC-131]` (official,
  29 CFR 541.101, retrieved 2026-09-28: "any employee who owns at least a bona fide 20-percent
  equity interest in the enterprise in which the employee is employed... and who is actively engaged
  in its management"), and several states (California among them) have no equivalent exemption at
  all — meaning a California founder can be owed minimum wage and overtime even while holding real
  equity and a "co-founder" title. Whether any specific founder or co-founder can lawfully go unpaid
  is an employment-attorney decision, not something this file or a founder can assume from title
  alone — giving "equity only" compensation to someone who functions like a regular employee is one
  of the most common ways early companies create legal exposure.

**Decision framing:** the choice between stipend, deferred salary, and equity-only should track how
much the person is expected to behave like a true co-founder (shared governance, no set hours, real
downside risk) versus how much they function like an early employee (set expectations, defined
scope, managed by the founder) — the more employee-shaped the actual working relationship, the more
a real wage (stipend or salary) is legally appropriate, regardless of what title is used.

---

## 7. Share of sale proceeds vs. real equity inside a multi-business holding structure

A distinct and more complex situation: a company operates as one of several businesses sitting
under a common holding structure (for example, a holding LLC that owns more than one operating
business). A new co-founder joining that one company cannot simply be handed "equity in the
company" without first answering a structural question that only an attorney (and typically a tax
advisor) can properly resolve: **equity in what, exactly?**

**The menu of structures an attorney might consider (conceptual only — this is not a
recommendation of any one option):**
- **A genuine equity carve-out or subsidiary spin-out** — the operating business is formed or
  reorganized as its own separate legal entity (e.g. its own LLC or corporation), and the new
  co-founder receives real membership interests or shares in *that* entity specifically, not in the
  parent holding structure or its other businesses.
- **A profits-interest grant within an existing LLC** — a real, tax-recognized form of equity
  compensation specific to LLCs taxed as partnerships, which grants a share of future profits
  and/or appreciation in value from the date of grant, without necessarily requiring the recipient
  to buy in at current value. This has specific IRS safe-harbor requirements and valuation timing
  rules that a tax attorney must apply correctly, or the intended tax treatment can fail.
- **A contractual, non-equity arrangement — often called "phantom equity" or a synthetic equity/
  synthetic-participation agreement** — a contract promising a defined share of sale proceeds (or a
  cash payment tied to a formula resembling equity appreciation) without granting actual ownership,
  voting rights, or membership interest. This avoids some of the complexity of real equity in a
  multi-business structure but gives the recipient no real governance role and depends entirely on
  the strength and clarity of the contract itself.
- **A membership-interest grant in a newly formed subsidiary** created specifically to hold the one
  business, cleanly separating it from the holding structure's other businesses before any equity
  is granted.

**Why this must go to an attorney, not be decided informally:** the right structure depends on
facts only the holding entity's own operating agreement, tax elections, and the specifics of the
*other* business(es) inside the same structure can answer — for example, whether the operating
agreement already restricts how membership interests can be granted, whether a carve-out triggers a
taxable event, and whether the other business(es) inside the structure have their own investors or
obligations that constrain what can be offered. **Do not describe a specific percentage or
structure to a candidate co-founder as settled until the company's attorney has confirmed which
structure is actually being used** — describing "you'll get equity in the company" without knowing
which of the above (if any) is actually available is a promise that may not be deliverable as
described.

---

## 8. IP assignment — the CIIAA

A **Confidential Information and Invention Assignment Agreement (CIIAA)** is a standard agreement
under which anyone contributing work — code, designs, written content, ideas developed in the
course of the work — assigns ownership of that work product to the company, and agrees to keep the
company's confidential information confidential `[KB-VREC-122]` (internal doctrine, retrieved
2026-09-28 — CIIAA/PIIA/IP-assignment agreements of this general shape are standard, widely-used
instruments across US startups; YC's own standard post-incorporation document set is understood to
include an equivalent invention-assignment agreement for founders `[KB-VREC-123]` UNVERIFIED —
seeded, needs derivation, YC's specific current template name and text were not independently
re-fetched and quoted this pass; verify against YC's own current Startup Library / post-incorporation
document guidance before citing specific template language).

**Why this must exist before anyone touches the codebase or any other work product — no
exceptions:** without a signed assignment, a contributor (a trial-project candidate, a new
co-founder, a contractor, even a well-meaning friend who "just helped out for a weekend") can retain
a legal claim to what they created, which can cloud the company's ownership of its own product at
exactly the moment (a sale, a fundraise) when clean ownership matters most. This is not a
theoretical risk reserved for later-stage companies — it applies from the very first line of code
or the very first trial project.

**Practical rule:** every co-founder, every advisor, every contractor, and every employee signs a
CIIAA (or the company's attorney-drafted equivalent) **before** contributing any code, design, or
other IP — including during an unpaid or paid trial period (§3 of `cofounder-search.md`). This is
one of the few items in this file that should never be delayed "until things are more serious" —
delaying it is exactly what creates the exposure.

---

## 9. Worker classification — contractor vs. employee

This is one of the highest-risk areas for a cash-poor early company, because the informal
arrangements that feel natural (equity-only compensation, "just help out and we'll figure out
comp later," calling someone a 1099 contractor to avoid payroll complexity) are frequently the
arrangements most likely to be misclassified under the actual legal tests.

### The IRS common-law test (federal tax classification)

The IRS evaluates worker classification using three categories of evidence, with no single factor
being determinative — the full relationship must be examined `[KB-VREC-124]` (official, IRS
guidance "Independent contractor (self-employed) or employee?", retrieved 2026-09-28):

1. **Behavioral control** — does the company control, or have the right to control, what the
   worker does and how the worker does the job (set hours, dictate methods, provide tools)?
2. **Financial control** — are the business aspects of the worker's job controlled by the company
   (how they're paid, whether expenses are reimbursed, who provides tools/supplies, whether the
   worker can realize a profit or loss)?
3. **Type of relationship** — is there a written contract, are there employee-type benefits
   (pension, insurance, vacation pay), will the relationship continue indefinitely, and is the work
   a key aspect of the company's regular business?

`[KB-VREC-125]` (official, IRS "Independent contractor (self-employed) or employee?", retrieved
2026-09-28, verbatim: "no one factor stands alone in making this determination.")

### The federal DOL test — currently unsettled, check before relying on it

Federal Department of Labor classification under the Fair Labor Standards Act has been genuinely in
flux and should be checked for its current status before an agent states it as settled:

- A final rule published by DOL on January 10, 2024, effective March 11, 2024, adopted a **six-factor
  "economic reality" test**: (1) opportunity for profit or loss depending on managerial skill; (2)
  investments by the worker and the employer; (3) degree of permanence of the working relationship;
  (4) nature and degree of control; (5) extent to which the work performed is integral to the
  employer's business; and (6) skill and initiative — evaluated under a "totality of the
  circumstances" approach with no factor given predetermined weight `[KB-VREC-126]` (official, DOL
  guidance on the 2024 independent contractor rule, retrieved 2026-09-28).
- **As of a February 27, 2026 proposed rule, DOL proposed to rescind the 2024 rule's analysis (29 CFR
  part 795) and replace it with the analysis from its own prior January 2021 final rule, with a few
  modifications** — under the revived 2021-style approach, two factors (control over the work, and
  the worker's opportunity for profit or loss) are given greater weight and are generally
  determinative in most cases, a departure from the 2024 rule's no-factor-predetermined-weight
  approach `[KB-VREC-127]` (official, Federal Register document 2026-03962, "Employee or Independent
  Contractor Status Under the Fair Labor Standards Act, Family and Medical Leave Act, and Migrant and
  Seasonal Agricultural Worker Protection Act," published 2026-02-27, retrieved 2026-09-28). The
  public comment period on this proposal ran until April 28, 2026. **Because this is a live
  rulemaking that had not been finalized as of this pass, do not state the current federal DOL test
  as settled without re-checking dol.gov or federalregister.gov directly at the time of use** —
  confirm whether the 2024 rule, this 2026 proposal (now possibly finalized), or a further-updated
  rule is in effect at that moment.

### State law can be stricter: the ABC test (e.g. California AB5)

Several states, including California under AB5, apply a stricter **"ABC" test** that presumes a
worker is an employee unless the hiring business proves **all three** of the following
`[KB-VREC-128]` (third-party legal-industry synthesis of California's ABC test as codified via AB5,
retrieved 2026-09-28 — confirm current statutory text via the California Labor Code / DIR before
relying on this for a specific worker in California):

- **(A)** The worker is free from the company's control and direction in performing the work, both
  under the contract and in actual practice;
- **(B)** The work performed is outside the usual course of the hiring company's business; and
- **(C)** The worker is customarily engaged in an independently established trade, occupation, or
  business of the same nature as the work performed.

**All three prongs must be satisfied — this is not a balancing test like the IRS common-law
factors. If any single prong fails, the worker is an employee by default, and the burden is on the
hiring business to prove all three.** This matters directly for a software company: a contractor
doing product or engineering work for a software company is doing work that is very plausibly
"within the usual course of the company's business" (prong B), which is exactly the prong many
software-company contractor arrangements fail in ABC-test states.

### The practical risk for this KB's users specifically

The single most common and most legally exposed pattern for a cash-poor early-stage company is:
calling an early co-founder or key early contributor a "1099 contractor" or "equity-only,
no-wages" participant specifically *to avoid* payroll taxes, minimum-wage/overtime obligations, or
benefits — while the actual working relationship (set expectations, ongoing integral work, real
control over how and when the work is done) looks like an employment relationship under either the
IRS or a state ABC test. The consequences of misclassification can include back taxes, back wages,
penalties, and — for someone effectively working unpaid in a role a court or agency later
characterizes as employee-shaped — wage-and-hour liability. **This determination should never be
made by the founder alone based on convenience; it requires the company's employment attorney (and,
for tax withholding consequences, its CPA) evaluating the actual facts of the specific working
relationship, in the specific state(s) involved, against the current federal and state tests.**

---

## 10. What must be in writing, when — and what never goes in writing before counsel

### Must be in writing, and before the milestone named:

| Document | Must exist before |
|---|---|
| CIIAA (IP assignment) | Any code, design, or IP contribution — including trial-period work (this is the one document that must exist BEFORE any trial project starts — see `cofounder-search.md` §3) |
| Cofounder / founders' agreement (the full agreement, with equity/vesting terms) | Before any formal commitment as a co-founder — normally AFTER the trial project, once the decision to proceed is actually made, not before it (§3's "no equity in writing before a trial" rule and this row are not in tension: the CIIAA is signed pre-trial, the founders' agreement itself is signed once the trial has concluded and both sides are committing) |
| Vesting schedule, in the actual stock purchase agreement / cap table documents | The equity grant itself — never a verbal-only vesting understanding |
| Advisor agreement (FAST-style or attorney-drafted equivalent) | Any advisory work begins, before any advisor equity is granted |
| Written 83(b) election | Within 30 calendar days of any restricted-stock grant — see §4 |
| Employment or contractor agreement matching the ACTUAL working relationship | Before regular ongoing work begins, per the classification analysis in §9 |

### Must never be put in writing, or promised, before the right professional is involved:

- **A specific equity percentage stated as a firm promise before a written, attorney-reviewed
  agreement exists.** Verbal percentage promises create real disputes when the final paperwork
  differs even slightly from what was said on a call.
- **Any 83(b) election content or filing decided without a CPA or tax attorney confirming the
  fair-market-value figure and current filing procedure** — the deadline is unforgiving (§4) and
  the cost of getting the mechanics wrong is high and permanent.
- **A specific holding-structure equity/profit-share arrangement described as settled before the
  company's attorney has confirmed which structure (§7) is actually being used** — this is a
  promise that may not be deliverable as described.
- **Anything that starts to look like an offer of securities to multiple outside investors without
  securities counsel review** — this file covers co-founder and advisor compensation only; any
  broader fundraising mechanics (SAFEs, priced rounds, multiple outside investors) belong to
  `capital-and-exit-strategist`'s lane and need their own securities-counsel review before any
  written terms are shared with a prospective investor.
- **A classification decision (contractor vs. employee) made purely to save money on payroll,
  without the attorney's classification analysis under §9's actual tests.**

---

## Decision rules

- **IF** a candidate is joining before there is any real revenue or user validation (i.e., the
  hardest uncertainty is still largely unresolved), **THEN** the split should lean closer to a
  day-one, near-equal split per YC's own default reasoning (§1) — the "remaining work" argument for
  equal splits is at its strongest here.
- **IF** a candidate is joining after real revenue and real customer validation already exist,
  **THEN** note that this is exactly the scenario YC names as a *bad* reason for an unequal split
  (§1) — a smaller-than-day-one share is not automatically the correct default just because revenue
  exists. Any narrower number must be reasoned from how much genuine, hard remaining work and risk
  the new person is taking on (§1), flagged to the operator as running counter to YC's own stated
  position, and never derived from a fixed rule of thumb or finalized without the vesting/cliff
  structure (§2) attached and counsel's input.
- **IF** a co-founder receives restricted stock subject to vesting, **THEN** the 83(b) election
  must be filed within 30 calendar days of the date of transfer (rolling to the next business day
  only if day 30 itself lands on a weekend or holiday, per §4) or the tax treatment is permanently
  lost — flag this to the operator and their CPA immediately upon the grant, not at some later
  convenient time (§4).
- **IF** the company sits inside a multi-business holding structure, **THEN** never describe a
  specific equity or profit-share arrangement to a candidate as settled until the company's
  attorney has confirmed which structure (§7) is actually available and will be used.
- **IF** an advisor is being brought on, **THEN** use a written FAST-style (or attorney-drafted
  equivalent) agreement before any advisory work begins — never a handshake understanding (§5, §10).
- **IF** a new co-founder or contractor is about to touch the codebase or any other work product,
  **THEN** a signed CIIAA must exist first, with no exceptions for trial periods or "just helping
  out" (§8, §10).
- **IF** there is any doubt about whether a working relationship is really contractor-shaped or
  employee-shaped, **THEN** treat it as employee-shaped until the company's employment attorney
  says otherwise, especially for anyone in a state with an ABC test (§9) — the cost of
  over-classifying as employee is materially lower than the cost of misclassification penalties.
- **IF** the federal DOL classification test's current status matters to a specific decision,
  **THEN** re-check dol.gov directly at the time of the decision rather than relying on a cached
  answer — this area was in active rulemaking flux as of this file's last research pass (§9).

---

## Anti-patterns

- **Verbally promising a specific equity percentage before any written, attorney-reviewed agreement
  exists.** This is the single most common source of later co-founder disputes — what was said and
  what was signed rarely match perfectly in memory, and the mismatch becomes a real conflict.
- **Missing the 83(b) election's 30-day deadline** through delay, uncertainty about the paperwork,
  or simply not knowing it exists — this is irreversible and should be flagged and actioned the
  same week any restricted-stock grant is made (§4).
- **Calling an early co-founder a "1099 contractor" specifically to avoid payroll taxes or
  benefits**, when the actual working relationship (set expectations, ongoing integral work, real
  control) looks like employment under the applicable test (§9) — this is a common, high-risk
  shortcut, not a legitimate cost-saving structure.
- **Granting advisor equity on a handshake, with no signed FAST-style agreement**, and later facing
  a dispute when the advisor claims a larger stake or a different vesting schedule than either side
  clearly remembers agreeing to (§5, §10).
- **Letting a trial-project candidate, a new co-founder, or any contractor touch the actual codebase
  before a CIIAA is signed** — even "just for the weekend," even from someone trusted personally
  (§8).
- **Describing a share of a multi-business holding structure as "equity in the company" without the
  attorney having confirmed which actual structure (§7) will be used** — this can promise something
  that isn't deliverable as described once the real structuring work happens.
- **Treating a stated stock-purchase or vesting term as final before the company's actual attorney
  has drafted and reviewed it**, based only on a template or a generic online description (including
  this file) — every document in the checklist (§10) needs real counsel review before signature.
- **Assuming the federal DOL classification test is fixed and settled** when it has, in fact, been
  the subject of repeated rulemaking changes in recent years (§9) — always re-verify current status
  rather than relying on a remembered rule.

---

## Sources

- [How do co-founders actually split equity?](https://carta.com/data/how-co-founders-split-equity/) — Carta — (third-party, retrieved 2026-09-28)
- [How to Split Equity Among Co-Founders](https://www.ycombinator.com/library/5x-how-to-split-equity-among-co-founders) — YC Startup Library — (official, retrieved 2026-09-28)
- [Co-Founder Equity Mistakes to Avoid](https://www.ycombinator.com/library/LP-co-founder-equity-mistakes-to-avoid) — YC Startup Library — (official, retrieved 2026-09-28)
- [Independent contractor (self-employed) or employee?](https://www.irs.gov/businesses/small-businesses-self-employed/independent-contractor-self-employed-or-employee) — IRS — (official, retrieved 2026-09-28)
- IRS guidance on Section 83(b) elections, Form 15620, and required election content (irs.gov content including the Form 15620 instructions and the Publication 525 update page) — IRS — (official, retrieved 2026-09-28)
- [Update to the 2024 Publication 525 for Section 83(b) election](https://www.irs.gov/forms-pubs/update-to-the-2024-publication-525-for-section-83b-election) — IRS — (official, retrieved 2026-09-28)
- [Employee or Independent Contractor Status Under the Fair Labor Standards Act... (Federal Register 2026-03962)](https://www.federalregister.gov/documents/2026/02/27/2026-03962/employee-or-independent-contractor-status-under-the-fair-labor-standards-act-family-and-medical) — DOL, published 2026-02-27 — (official, retrieved 2026-09-28)
- DOL 2024 independent contractor final rule (six-factor economic reality test) — third-party legal/HR summaries of the DOL rule, retrieved 2026-09-28 — (third-party, retrieved 2026-09-28)
- California AB5 / ABC test three-prong summary — third-party legal-industry synthesis, retrieved 2026-09-28 — (third-party, retrieved 2026-09-28) — confirm current statutory text via the California Labor Code / DIR before relying on it for a specific case
- [FAST Agreement](https://fi.co/fast) — Founder Institute — (official, retrieved 2026-09-28)
- NVCA Model Legal Documents (single/double-trigger acceleration market-standard framing) — nvca.org/model-legal-documents, plus third-party legal-industry synthesis — (third-party, retrieved 2026-09-28) — NVCA's own current template text not independently re-fetched and quoted verbatim this pass
- [29 CFR 541.101](https://www.law.cornell.edu/cfr/text/29/541.101) — Cornell LII mirror of eCFR, business-owner exemption from FLSA executive-capacity rules — (official, retrieved 2026-09-28)
- [Treas. Reg. §1.83-2](https://www.law.cornell.edu/cfr/text/26/1.83-2) — Cornell LII mirror of eCFR — (official, retrieved 2026-09-28)
- IRS Form 15620 instructions, "When To File" (30-day deadline and IRC §7503 weekend/holiday rollover) — IRS — (official, retrieved 2026-09-28)

**UNVERIFIED claims in this file:**
- `[KB-VREC-106]` — Slicing Pie's specific current formula/multipliers; slicingpie.com not independently re-fetched this pass.
- `[KB-VREC-108]` — YC's specific current post-incorporation vesting template language; not independently re-fetched and quoted verbatim this pass.
- `[KB-VREC-111]` — NVCA's specific current model-document clause language on double-trigger acceleration; nvca.org/model-legal-documents not independently re-fetched and quoted verbatim this pass.
- `[KB-VREC-123]` — YC's specific current invention-assignment template name/text; not independently re-fetched and quoted this pass.
- `[KB-VREC-127]` is no longer UNVERIFIED — confirmed directly against Federal Register document 2026-03962 (published 2026-02-27). This was a proposed rule as of that publication (comment period through 2026-04-28); re-verify against dol.gov/federalregister.gov before treating the current federal test as settled, since a proposed rule may have since been finalized, modified, or withdrawn.
