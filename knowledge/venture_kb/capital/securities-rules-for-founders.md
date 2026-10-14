# Securities rules for founders

**What this file answers:** the two Regulation D exemptions a small angel/pre-seed round almost
always relies on (Rule 506(b) vs 506(c)), what counts as illegal "general solicitation" and what
does not (including cold one-to-one outreach and public social posts), the "pre-existing
substantive relationship" concept that lets a founder talk to strangers without it being
solicitation, who counts as an "accredited investor," how accredited status must be verified under
506(c), the Form D filing obligation and its deadline, state "blue sky" notice filings, the real
legal risk of paying a "finder" a success fee, Regulation Crowdfunding as an alternative raising
path, what a founder may safely say in public and on LinkedIn while raising, and exactly when
securities counsel stops being optional. **This file is information, not legal advice.** Every
section below says explicitly where a real securities attorney must be engaged before money
changes hands — follow those pointers; do not treat this file as a substitute for that
conversation.

---

## 1. Why this matters at all

Selling equity (or a SAFE, which is a contract for future equity) is selling a security. Selling
securities without either registering the offering with the SEC or qualifying for an exemption is
illegal, full stop, regardless of how small the round is, how well the founder knows the investor,
or how informal the paperwork feels. Every angel round and every pre-seed SAFE a first-time founder
raises needs to fit inside one specific, named exemption — almost always Regulation D, Rule 506(b)
or 506(c) — and the founder needs to know which one they are using and follow its rules exactly,
because the exemptions are not interchangeable and mixing their requirements can blow the
exemption entirely.

**Decision rule:** IF money is being raised in exchange for equity, a SAFE, a convertible note, or
any other instrument that could convert into equity or a share of profits, THEN a securities
exemption analysis is required before the first dollar is accepted — this is true even for a $5,000
check from a friend.

---

## 2. Rule 506(b) vs Rule 506(c): the two paths

Both are part of Regulation D (17 CFR Part 230, Rules 500-508), the primary federal exemption used
by early-stage companies. `[KB-VCAP-017]` 17 CFR 230.506 is titled "Exemption for limited offers and
sales without regard to dollar amount of offering" (official, Cornell Legal Information Institute
mirror of the eCFR, 17 CFR 230.506, retrieved 2026-09-28 — LII mirrors the official eCFR text;
direct ecfr.gov and govinfo.gov access returned a blocking redirect at time of retrieval, so this
citation is sourced to the LII mirror rather than the primary government host directly).

### Rule 506(b) — no general solicitation, up to 35 non-accredited (sophisticated) investors

`[KB-VCAP-018]` Under 506(b), the offering is subject to the manner-of-offering (anti-solicitation)
limitations, meaning the company cannot use general solicitation or general advertising to find
investors; the company may sell to an unlimited number of accredited investors plus "no more than,
or the issuer reasonably believes that there are no more than, 35 purchasers" of securities who are
not accredited, within any 90-calendar-day period (official, Cornell LII mirror of 17 CFR
230.506(b), retrieved 2026-09-28).

`[KB-VCAP-019]` Each non-accredited purchaser under 506(b) must have, or the issuer must reasonably
believe they have, "such knowledge and experience in financial and business matters that he is
capable of evaluating the merits and risks of the prospective investment" — the sophistication
requirement (official, Cornell LII mirror of 17 CFR 230.506(b), retrieved 2026-09-28). In practice,
most professionally-run pre-seed rounds simply avoid non-accredited investors altogether rather
than build the file needed to document sophistication for each one — that is a market-practice
choice, not a legal requirement, and a founder who wants to include a genuinely sophisticated but
non-accredited person (an experienced operator with limited personal net worth, for example) can do
so under 506(b) with proper documentation and counsel's help.

**No general solicitation means:** the company cannot advertise the raise to the public — no
public posts inviting investment, no pitch at an open, unrestricted event, no cold outreach to
strangers with no prior relationship (see Section 3 for the pre-existing-relationship exception).
506(b) works by limiting who the offer ever reaches to people the founder already has some
connection to, or who came through a genuinely private, non-public channel.

**A mandatory disclosure gate if ANY buyer is not accredited.** `[KB-VCAP-044]` Rule 502(b)(1)
requires that if any purchaser in the offering is not accredited, the issuer must furnish that
purchaser specified disclosure — the information described in Rule 502(b)(2), which generally
includes financial statements — a reasonable time before the sale (official, Cornell LII mirror of
17 CFR 230.502(b)(1), retrieved 2026-09-28: the issuer must furnish "the information specified in
paragraph (b)(2)" to non-accredited purchasers "a reasonable time prior to sale"). This is a real,
separate compliance step, not a formality — it is exactly why most professionally-run pre-seed
rounds avoid non-accredited investors altogether (above) rather than build this disclosure file, and
it should be treated as a securities-counsel gate that must be cleared BEFORE accepting any
non-accredited investor's money, not something to assemble after the fact.

**No independent verification requirement** — under 506(b), the company can rely on each investor's
own self-certification of accredited (or sophisticated) status; there is no independent
verification requirement the way there is under 506(c) (Section 4). (Note this is separate from the
502(b)(1) disclosure gate above, which applies regardless of verification method whenever a
non-accredited purchaser is involved.)

### Rule 506(c) — general solicitation allowed, but 100% accredited and verified

`[KB-VCAP-020]` Under 506(c), the company may use general solicitation and general advertising, but
"all purchasers of securities sold in any offering under paragraph (c)... are accredited investors,"
and the issuer must "take reasonable steps to verify" that every purchaser is in fact accredited
(official, Cornell LII mirror of 17 CFR 230.506(c), retrieved 2026-09-28).

This is the trade: 506(c) buys the freedom to publicly announce a raise (a tweet, a LinkedIn post, a
pitch at an open Demo Day-style event) at the cost of (a) accepting money only from accredited
investors, with zero non-accredited exceptions, and (b) doing real, documented verification of each
investor's accredited status rather than just taking their word for it.

**Decision rules:**

- IF the founder wants to raise quietly, from people they already have a pre-existing relationship
  with, and is comfortable including a small number of sophisticated-but-not-technically-accredited
  people, THEN 506(b) is the simpler, more common path for a small first raise. **A warm introduction
  is not automatically a pre-existing relationship for solicitation purposes** — see Section 3's
  "hard middle case" — and this KB's venture department treats outreach as limited to genuinely
  pre-existing relationships unless securities counsel approves a different route for a specific
  contact.
- IF the founder wants to publicly post about the raise (a LinkedIn post, a public pitch event, a
  crowdfunding-adjacent public campaign that is not actually run through Reg CF), THEN 506(c) is
  required, and every single investor must be accredited and independently verified — there is no
  hybrid option that allows public solicitation with only some investors verified.
- IF unsure which path fits, THEN default to 506(b) and keep the raise private — it is the lower-
  friction, lower-verification-burden path for a small, relationship-driven round, which is the
  common case this file is written for.

---

## 3. General solicitation: what counts, what doesn't

`[KB-VCAP-021]` The SEC describes general solicitation as communications that "condition the
market" or generate public interest in securities, and lists examples including newspaper and
magazine advertisements, unrestricted public websites, television and radio broadcasts, and open
seminars — with a specific carve-out for qualifying demo days (official, SEC "General Solicitation,"
retrieved 2026-09-28). `[KB-VCAP-022]` The SEC states the determination is fact-specific, and that
communications reaching many unsophisticated individuals through impersonal channels are more
likely to be treated as general solicitation (official, SEC "General Solicitation," retrieved
2026-09-28).

**What counts as general solicitation (treat these as solicitation, requiring 506(c) if used):**

- A public social media post inviting investment or describing specific terms of an open raise, to
  an audience that is not limited to people the founder already has a substantive relationship with.
- A pitch at an open, publicly-advertised event where attendance is not limited and the pitch
  discloses specific securities being offered (as distinct from a qualifying demo day, below).
- Cold outreach — a message to a stranger with no pre-existing relationship — that references the
  specific raise or invites investment, sent broadly (e.g., a mass cold email campaign to a
  purchased investor list).
- Any advertisement, press release, or public website copy that invites the public to invest.

**What does NOT count (and so remains compatible with 506(b)'s no-solicitation requirement):**

- **A pre-existing, substantive relationship.** `[KB-VCAP-023]` A relationship is "pre-existing"
  when it was formed before the start of the offering (there is no minimum waiting period required —
  the relationship simply has to predate the start of THIS specific offering; a relationship formed
  during a live offering does not count as pre-existing for that same offering — see the "hard middle
  case" below), and "substantive" when the issuer "has sufficient information to evaluate, and does,
  in fact, evaluate, a prospective offeree's financial circumstances and sophistication, in
  determining his or her status as an accredited or sophisticated investor" (official, SEC
  "General Solicitation" page and Securities Act Rules C&DI 256.29 / 256.31, retrieved 2026-09-28).
  An offer made only to people within such a relationship is not general solicitation, even if the
  founder reaches out first.
- **A genuinely private, one-to-one message to someone the founder already knows** (a former
  colleague, a personal friend, an existing advisor) is not solicitation to "the public" — the
  concern is reach and impersonality, not the mere fact that the founder initiated contact.
- **A qualifying demo day.** `[KB-VCAP-024]` Rule 148's demo-day exemption from general solicitation
  requires ALL of the following, not just a sponsor and a content limit (official, 17 CFR 230.148,
  Cornell LII mirror of eCFR, retrieved 2026-09-28):
  - The event is a seminar or meeting in which **more than one issuer participates** — a single
    company's own solo pitch event does not qualify.
  - It is sponsored by a college/university, a state or local government (or their instrumentality),
    a nonprofit, or an angel investor group, incubator, or accelerator.
  - The advertising for the event does not reference any specific securities offering by name.
  - **The sponsor does not** make investment recommendations, provide investment advice, engage in
    investment negotiations between issuers and investors, or charge more than reasonable
    administrative fees for the event — and does not receive compensation for making introductions or
    for negotiations that would otherwise require broker-dealer registration (Rule 148(a)(2)).
  - **If the event is offered online, attendance is limited** to: individuals who are members of or
    otherwise associated with the sponsor organization; individuals the sponsor reasonably believes
    are accredited investors; or individuals invited by the sponsor based on industry or
    investment-related experience the sponsor reasonably selected in good faith (Rule 148(a)(4)).
  - The information conveyed about any company's offering is limited to specified basics: that the
    issuer is offering or planning to offer securities, the type and amount of securities being
    offered, the intended use of proceeds, **and the unsubscribed amount in the offering** — this
    last item is part of the permitted disclosure list, not an omission.
  Confirm a specific planned event against all of these conditions with counsel before relying on
  Rule 148 — missing any one of them (most commonly the "more than one issuer" or online-attendance
  conditions) can mean the event does not qualify at all.

**The hard middle case — cold one-to-one outreach.** A single, personalized cold email to one
specific person, with no prior relationship, that describes the raise, sits in genuinely
contested territory. It is not the mass-blast case the rule clearly prohibits, but it is also not
protected by a pre-existing relationship, since none exists yet. **Critically, this does not resolve
by "building the relationship first" within the same raise: once an offering has started, a
relationship formed during it does not count as pre-existing for THAT offering** `[KB-VCAP-023b]`
(official, SEC C&DI 256.31 and the SEC "General Solicitation" page, retrieved 2026-09-28 — a
"pre-existing" relationship must be "formed before the start of the offering," and relationship
quality/substantiveness only matters once that timing threshold is already met). Practically: a cold
outreach made *after* an offering has begun cannot be cured by having a few relationship-building
conversations before the actual investment ask — the relationship-building itself already happened
inside the live offering and does not qualify. Relationship-building with a stranger can still be
valuable, but only for a *future*, later offering, not the one already underway; whether any contact
with a stranger during a live raise is permitted at all (e.g., as a purely social, non-offering
conversation with a wall kept between it and any securities discussion) is a securities-counsel
judgment call, not a self-service workaround. **One narrow, named exception:** C&DI 256.32 allows an
issuer to reach an experienced, sophisticated member of an established angel-investor network
through a referral from another member of that same network, relying on the network's own
sophistication screening — this is materially different from a founder's own cold outreach to a
stranger and should not be generalized from `[KB-VCAP-024b]` (official, SEC C&DI 256.32, retrieved
2026-09-28).

**Anti-patterns:**

- Posting "we're raising a round, DM me" publicly and then treating every DM reply as if it came
  from a pre-existing relationship — the public post itself is the solicitation; a private reply to
  it does not retroactively cure that.
- Treating a large, purchased or scraped contact list as a set of "pre-existing relationships"
  because the founder has their names and emails — a name in a spreadsheet is not a relationship;
  the SEC's own test requires the issuer to actually possess and have evaluated the person's
  financial circumstances and sophistication.
- Running a "stealth" LinkedIn post that never says the word "invest" but clearly signals an open
  round and invites interested people to reach out — the SEC's test is about substance
  (conditioning the market / generating public investment interest), not about whether a specific
  magic word was used.

---

## 4. Accredited investor: definition and verification

### Definition (17 CFR 230.501(a))

`[KB-VCAP-025]` An individual qualifies as an accredited investor if their individual net worth, or
joint net worth with a spouse or spousal equivalent, exceeds $1,000,000 — excluding the value of
their primary residence from assets, and with related debt calculated under specific limiting rules
in the regulation (official, Cornell LII mirror of 17 CFR 230.501(a), retrieved 2026-09-28).

`[KB-VCAP-026]` Alternatively, an individual qualifies based on income: more than $200,000 in each
of the two most recent years (or joint income with a spouse or spousal equivalent exceeding
$300,000 in each of those years), with a reasonable expectation of reaching that same income level
in the current year (official, Cornell LII mirror of 17 CFR 230.501(a), retrieved 2026-09-28).

`[KB-VCAP-027]` The definition also includes people holding certain professional certifications,
designations, or credentials the SEC has designated as demonstrating sufficient investment
knowledge; certain "knowledgeable employees" (as defined under Investment Company Act Rule
3c-5(a)(4)) **of a private fund that relies on the Investment Company Act §3(c)(1) or §3(c)(7)
exclusion** — this "knowledgeable employee" path is a private-fund concept (it applies where the
issuer would otherwise be an "investment company" but for one of those exclusions), and does **not**
mean an ordinary operating startup's own employees are automatically accredited by virtue of working
there; and, on the entity side, banks, registered broker-dealers, registered investment advisers,
insurance companies, registered investment companies, organizations with assets exceeding $5
million **that were not formed for the specific purpose of acquiring the securities offered**,
family offices with assets over $5 million, entities where all equity owners are themselves
accredited, and — notably for a founder's own cap table — directors, executive officers, and general
partners of the issuer itself (official, Cornell LII mirror of 17 CFR 230.501(a), retrieved
2026-09-28). **UNVERIFIED — seeded, needs derivation:** the specific professional certifications the
SEC has designated (commonly cited in secondary sources as Series 7, Series 65, and Series 82
license holders) were not confirmed against a primary SEC release during this pass; confirm the
current designated list with counsel before relying on a specific license as qualifying.

### Verification under 506(c)

Self-certification (a signed questionnaire in which the investor simply states they are
accredited) is **not sufficient** under 506(c) — the issuer must take "reasonable steps to verify."
`[KB-VCAP-028]` Rule 506(c)(2)(ii) provides exactly **five** non-exclusive, non-mandatory methods
deemed to satisfy the reasonable-steps requirement for a natural person (official, Cornell LII
mirror of 17 CFR 230.506(c)(2)(ii), retrieved 2026-09-28 — confirmed directly against the regulatory
text, the same LII page this file already cites for 230.506 generally):
1. **(A) Income-based:** reviewing any IRS form reporting the person's income for the two most
   recent years, plus a written representation of the expectation of qualifying income in the
   current year.
2. **(B) Net-worth-based:** reviewing asset documentation (bank/brokerage/CD statements, tax
   assessments, appraisals) and liability documentation (a consumer report) dated within the prior
   three months, **together with a written representation from the purchaser that all liabilities
   necessary to make the net-worth determination have been disclosed** — this written liabilities
   representation is a required part of method (B), not an optional extra, and is the piece most
   often left out when this method is summarized.
3. **(C) Third-party confirmation:** written confirmation from a registered broker-dealer, an
   SEC-registered investment adviser, a licensed attorney in good standing, or a licensed CPA in good
   standing, that they have themselves taken reasonable steps within the prior three months to verify
   the person's accredited status.
4. **(D) Prior 506(b) investors:** for someone who purchased as an accredited investor before
   September 23, 2013 in the same issuer's Rule 506(b) offering, obtaining certification of their
   continued accredited status.
5. **(E) Previously-verified persons:** obtaining a new written representation from a person
   previously verified as accredited that they still qualify, valid for five years from the date of
   the original verification.

`[KB-VCAP-029]` Separately, recent SEC staff guidance addressed minimum-investment-amount as one
path to satisfying verification: a natural person investing at least $200,000, or a legal entity
investing at least $1 million, combined with a written representation of accredited status and
confirmation the investment is not financed by a third party specifically to make that investment,
can support a reasonable-verification conclusion (third-party legal-commentary summary of SEC staff
guidance, retrieved 2026-09-28 — this describes recent (2025-dated in the sourced commentary) SEC
staff guidance easing verification burdens; confirm current status and exact conditions with
counsel, since staff guidance can be narrower or more conditional than a summary conveys, and this
was not independently confirmed against the SEC's own primary release).

**Decision rules:**

- IF raising under 506(b), THEN a signed self-certification questionnaire from each investor,
  retained in the deal file, is standard market practice — verify identity is real and the answers
  are not facially implausible, but no independent documentary verification is legally required.
- IF raising under 506(c) (because any general solicitation was used), THEN self-certification
  alone is not enough for any investor — use one of the documented verification methods above (most
  commonly for a small round: a letter from the investor's own CPA, attorney, broker-dealer, or
  registered investment adviser confirming accredited status) and keep that documentation on file.
- IF an investor is reluctant to provide income/net-worth documentation or a professional letter for
  506(c) verification, THEN that reluctance is itself useful information — a genuinely accredited,
  experienced angel investor is typically unsurprised by this requirement and can readily produce
  the letter; a founder who cannot get any investor to complete verification may be inadvertently
  running a 506(b)-shaped (privately-sourced) raise while treating it as 506(c), which is a mismatch
  to fix immediately with counsel.

---

## 5. Form D: filing requirement and deadline

`[KB-VCAP-030]` Form D is "a notice of an exempt offering of securities" required to be filed with
the SEC for offerings conducted under Regulation D, filed electronically through the SEC's EDGAR
system at no cost (official, SEC "What is Form D?," retrieved 2026-09-28).

`[KB-VCAP-031]` Form D must be filed within 15 days after the first sale of securities in the
offering; if the offering continues longer than a year or key details change, an amendment is
required (official, SEC "What is Form D?," retrieved 2026-09-28). `[KB-VCAP-032]` The 15-day clock
is calendar days, not business days (weekends and holidays count toward the 15 days), and starts
running from the date of "first sale" — defined as the point an investor becomes irrevocably
committed to invest, i.e., the moment the investor can no longer legally back out of the deal; if
the 15th day itself falls on a weekend or holiday, the deadline extends to the next business day
(third-party legal-practice summary of SEC Form D deadline rules, retrieved 2026-09-28 — directional
and consistent with the official SEC page's own 15-day statement above; confirm the precise
"first sale"/irrevocable-commitment trigger for a specific SAFE closing with counsel, since when a
SAFE closing legally becomes irrevocable can be a documents-specific question).

**Decision rules:**

- IF any investor becomes irrevocably committed to invest (normally at signing — the point the
  investor can no longer legally back out, which is often days before funds actually clear), THEN
  calendar the Form D filing deadline as 15 calendar days from *that* date immediately, rolling to
  the next business day only if the 15th day itself lands on a weekend or holiday (17 CFR
  230.503(a)(1)) — do not wait for the check to clear and do not wait until the whole round is fully
  closed if the round closes in stages, since the clock starts at the *first* sale, not the last.
  Counsel confirms exactly when a specific SAFE becomes irrevocable for this purpose.
  `[KB-VCAP-033]` Failing to timely file Form D has led to SEC enforcement actions against issuers
  in reported cases (third-party, Stubbs Alderton & Markiles, "SEC Charges Companies for Failing to
  Timely File Form D," retrieved 2026-09-28 — a law-firm client alert; confirm current enforcement
  posture and any applicable safe harbor for late filing with counsel).
- IF this is the founder's first Form D filing, THEN get an EDGAR account, a CIK number, and
  Login.gov credentials set up well before the deadline — this setup step itself can take time and
  should not be started for the first time under deadline pressure.
- IF counsel is engaged for the raise at all (strongly recommended, see Section 9), THEN have
  counsel handle or directly review the Form D filing — it is a short form but a missed or
  materially incorrect filing is a real, avoidable compliance failure.

---

## 6. State "blue sky" notice filings

Regulation D is a federal exemption; it does not by itself exempt an offering from state securities
law. Most states require a notice filing (not a substantive review, for a Rule 506 offering — this
is a federal preemption of state *merit* review, but not of state *notice* requirements) alongside
or shortly after the federal Form D.

`[KB-VCAP-034]` Most states accept a copy of the federal Form D as the primary state notice-filing
document, and many use the NASAA (North American Securities Administrators Association) Uniform
Form D; state filing fees for a Rule 506 notice filing vary by state and by offering size — for
example, New York charges $300 for offerings up to and including $500,000 and $1,200 for offerings above
that amount, under its Martin Act blue-sky overlay `[KB-VCAP-034b]` (UNVERIFIED — seeded, needs derivation: from
blue-sky-compliance legal-alert summaries of New York's EFD fee schedule, not the NY AG's own page — do
NOT state that New York or any specific state charges $0 for this filing; fee figures vary by state
and by offering size and should be confirmed for each state where an investor actually resides
before relying on any cited number).

`[KB-VCAP-035]` NASAA operates an Electronic Filing Depository (EFD) allowing an issuer to submit
Form D and pay fees to multiple participating state regulators through one coordinated system, with
a one-time $150 system-access fee in addition to each state's own filing fee (third-party,
aggregated blue-sky-compliance summaries, retrieved 2026-09-28 — UNVERIFIED against NASAA's own
primary site during this pass; confirm current EFD fee and participating-state list directly with
NASAA or counsel before relying on the $150 figure).

**Decision rule:** IF investors in the round reside in more than one or two states, THEN budget for
and complete a state blue-sky notice filing in every state where an investor resides — this is
commonly handled by the same counsel preparing the federal Form D, and skipping it is a real, if
often under-enforced, compliance gap that a later diligence process (a priced round, an
acquisition) can surface.

---

## 7. Finders and unregistered broker-dealer risk

A "finder" — someone who introduces the founder to investors in exchange for a fee — is one of the
more common ways a first-time founder accidentally creates serious legal exposure, because the SEC
treats the *structure of the fee*, not the person's job title, as the test.

`[KB-VCAP-036]` The SEC and courts treat transaction-based compensation (a fee tied to the size or
success of the specific financing, whether paid in cash or in equity with vesting tied to the
raise's success) as "the hallmark of broker activity," and once compensation is structured this
way, the person is generally treated as acting as an unregistered broker-dealer if not properly
registered — subject to enforcement regardless of what the parties call the arrangement (UNVERIFIED — seeded,
needs derivation: summarised from legal-industry commentary on SEC no-action letters without one
named source; securities counsel confirms before any compensation is structured for a person helping
raise the round).

`[KB-VCAP-037]` If an unregistered person acted as a broker in a securities transaction, the
Exchange Act's rescission remedy can allow investors a "put" right to unwind the transaction (get
their money back), and while this liability falls primarily on the unregistered broker, the company
that paid the finder can be exposed to a claim of aiding and abetting or causing the violation
(UNVERIFIED — seeded, needs derivation: summarised from legal-industry commentary without one named
source; counsel confirms the company's own exposure on the specific facts).

**Decision rules:**

- IF someone offers to introduce the founder to investors in exchange for a percentage of whatever
  is raised, or equity that vests based on the raise closing successfully, THEN treat this as a
  serious red flag requiring securities counsel review before agreeing — do not structure or accept
  a success-fee/commission arrangement with anyone who is not a properly licensed, registered
  broker-dealer.
- IF the founder wants to compensate someone for genuine help with the raise (intros, deck
  feedback, warm connections) without creating broker-dealer exposure, THEN structure the
  compensation as a flat fee for services rendered, not contingent on whether or how much money is
  raised, and confirm the specific structure with counsel — "flat and non-contingent" is the
  general direction market practice takes to avoid the transaction-based-compensation test, but the
  exact line is fact-specific and counsel should confirm any real arrangement.
- IF an advisor or friend has already been promised (verbally or otherwise) a percentage of any
  raise they help bring in, THEN stop and get counsel involved before any money changes hands under
  that arrangement — unwinding a bad structure before money moves is far cheaper than after.

---

## 8. Regulation Crowdfunding (Reg CF) as an alternative

`[KB-VCAP-038]` Regulation Crowdfunding allows a company to raise up to $5 million in aggregate from
investors — including non-accredited, everyday investors — in a 12-month period, through an
SEC-registered intermediary (either a registered broker-dealer or a registered funding portal)
(official, SEC "Regulation Crowdfunding," retrieved 2026-09-28). `[KB-VCAP-038b]` The $5 million cap
is measured on a rolling 12-month basis from the date of each closing, per 2026 SEC staff guidance
clarifying the calculation (third-party, legal-industry summary of 2026 SEC C&DI guidance, retrieved
2026-09-28 — confirm current status of this staff guidance with counsel before relying on the
rolling-calculation detail for a specific offering timeline).

`[KB-VCAP-039]` Reg CF requires disclosure filings with the SEC and to investors and the
intermediary (principally Form C), limits how much any individual non-accredited investor can put
into all Reg CF offerings combined within a 12-month period (specific dollar thresholds not
independently confirmed during this pass — UNVERIFIED, seeded, needs derivation against the SEC's
current investor-limit table before citing a specific number to a founder), imposes a one-year
resale restriction on securities purchased, and applies "bad actor" disqualification rules
(official, SEC "Regulation Crowdfunding," retrieved 2026-09-28).

**Decision rules:**

- IF the founder wants to raise publicly, from a broad base of small, non-accredited backers
  (a genuine "crowd"), and is comfortable with public disclosure obligations and using a registered
  funding portal, THEN Reg CF is a real, lawful alternative to a 506(c) accredited-only public raise
  — but it comes with real disclosure and portal-fee overhead that a small angel round under 506(b)
  does not.
  `[KB-VCAP-040]` Reg CF offerings are executed entirely through a registered funding portal or
  broker-dealer, not directly by the company (official, SEC "Regulation Crowdfunding," retrieved
  2026-09-28) — meaning the founder cannot simply collect money from a public crowdfunding post
  independently; a compliant platform relationship is required.
- IF the company's actual goal is a small, quiet round from a handful of known or warmly-introduced
  people, THEN Reg CF is almost certainly the wrong tool — it is built for public-facing, broad-base
  raising, not a private angel round, and its disclosure and portal requirements are unnecessary
  overhead for that case.

---

## 9. What a founder may say publicly and on LinkedIn while raising

This is the single most common practical question a first-time founder has, because normal startup
behavior (talking about traction, posting product updates, being visibly excited about the company)
sits right next to the general-solicitation line.

**Decision rules — generally safe (does not itself constitute solicitation of securities):**

- Posting about the product, traction, customers, hiring, or company milestones with no reference
  to raising money, an offering, or specific investment terms.
- Saying, generally, that the company exists and is growing, without inviting investment or
  referencing a specific security being offered.
- Responding to an unsolicited inbound question ("are you raising?") with a private, one-to-one
  reply — this is closer to the pre-existing-relationship logic in Section 3, though a truly cold
  inbound stranger is not automatically a pre-existing relationship either; keep the reply
  general and move any real investment discussion to a private conversation rather than continuing
  in a public comment thread.

**Decision rules — treat as solicitation, requiring either silence or a 506(c)-compliant approach:**

- A LinkedIn post that says or clearly implies "we are raising, reach out if interested" to a
  general, public audience — this is general solicitation under Section 3's test, and if the
  founder wants to do this, the raise must be run as a 506(c) offering with 100%-accredited,
  independently-verified investors, not 506(b).
- Publicly stating specific terms (valuation, cap, discount, minimum check size) to an
  undifferentiated public audience.
- Encouraging public sharing/resharing of a fundraising announcement — this expands reach in exactly
  the impersonal, broad way the SEC's test flags.

**The practical rule of thumb this file recommends:** if the raise is meant to stay under 506(b)
(private, no public solicitation), do not post about the raise itself publicly at all — talk about
the company, not the fundraising — and keep every investment conversation in private, one-to-one
channels with people the founder already has a genuine, pre-existing relationship with. **A warm
introduction to a stranger is not by itself a pre-existing relationship** (Section 3) — this KB's
venture department policy is to contact only people with a pre-existing relationship unless
securities counsel approves a different route for that specific contact. If public posting about
the raise itself is important to the founder's
strategy, that is a deliberate choice to run under 506(c), with the accredited-only and
verification consequences in Section 4 — make that choice consciously with counsel, not by
accident through an enthusiastic LinkedIn post.

---

## 10. When securities counsel is mandatory (not optional)

This file is written so a first-time founder can understand the landscape and ask informed
questions — it is not a substitute for the following, each of which should trigger engaging a real
securities attorney before proceeding:

- **Before the first SAFE or note is signed**, to confirm the correct entity type (Section 5 of
  `angel-rounds-and-safes.md`), the correct exemption (506(b) vs 506(c)) for how the round is
  actually being marketed, and that the actual document matches what was agreed.
- **Before any general solicitation is used** (a public post, an open event, any 506(c) approach),
  to confirm the verification process is real and documented, not just a self-certification
  checkbox mistakenly used under a 506(c) offering.
- **Before compensating anyone for helping raise money** on any basis that could be read as
  transaction-based (Section 7).
- **Before or immediately upon the first sale closing**, to handle the Form D filing and any state
  blue-sky notice filings correctly and on time (Sections 5-6).
- **If a sale of the company is being discussed at the same time as a raise** — see
  `angel-rounds-and-safes.md` Section 8; this dual-track scenario carries real disclosure
  obligations that need a real legal read of the actual facts and timeline.
- **If any investor is not clearly, comfortably accredited** and the round is not being run
  carefully under 506(b)'s sophistication standard with real documentation.
- **If a CPA has not separately confirmed** how the raise will be treated for the company's own tax
  reporting, and, if applicable, how founder/investor QSBS eligibility is affected by entity
  structure and timing.

**What to bring to that first attorney meeting:** the actual SAFE/note template being considered
(or a description of terms if not yet drafted), a list of who has already been asked or has already
committed money (with rough amounts and how each person was contacted — cold, warm, public post),
current entity type and state of incorporation, and any parallel conversations (a sale process, an
acqui-hire conversation, a second simultaneous raise) that could interact with this one.

---

## Sources

- 17 CFR 230.506 (Cornell LII mirror of eCFR; primary ecfr.gov/govinfo.gov access blocked by redirect at retrieval time), retrieved 2026-09-28 — https://www.law.cornell.edu/cfr/text/17/230.506
- 17 CFR 230.501(a) (Cornell LII mirror of eCFR; same access note), retrieved 2026-09-28 — https://www.law.cornell.edu/cfr/text/17/230.501
- SEC, "General Solicitation" (official), retrieved 2026-09-28 — https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/general-solicitation
- SEC, "What is Form D?" (official), retrieved 2026-09-28 — https://www.sec.gov/resources-small-businesses/capital-raising-building-blocks/what-form-d
- SEC, "Regulation Crowdfunding" (official), retrieved 2026-09-28 — https://www.sec.gov/resources-small-businesses/exempt-offerings/regulation-crowdfunding
- SEC, Securities Act Rules Compliance and Disclosure Interpretations, Question 256.29, 256.31, 256.32 (official), retrieved 2026-09-28 — pre-existing substantive relationship timing/substantiveness and the angel-network-referral carve-out
- 17 CFR 230.503(a)(1) (Cornell LII mirror of eCFR) (official), retrieved 2026-09-28 — https://www.law.cornell.edu/cfr/text/17/230.503 — 15-day Form D deadline and weekend/holiday rollover
- 17 CFR 230.148 (Cornell LII mirror of eCFR) (official), retrieved 2026-09-28 — https://www.law.cornell.edu/cfr/text/17/230.148 — demo day conditions
- Stubbs Alderton & Markiles, "SEC Charges Companies for Failing to Timely File Form D" (third-party), retrieved 2026-09-28 — https://stubbsalderton.com/client-alert-sec-charges-companies-for-failing-to-timely-file-form-d/
- Aggregated blue-sky-compliance vendor/law-firm summaries on state notice filings and NASAA EFD (third-party, not independently confirmed against NASAA's own primary site), retrieved 2026-09-28
- Aggregated legal-industry summaries on transaction-based compensation and unregistered broker-dealer risk (third-party), retrieved 2026-09-28
- 29 CFR 541.101 (Cornell LII mirror of eCFR) (official), retrieved 2026-09-28 — https://www.law.cornell.edu/cfr/text/29/541.101 — business-owner FLSA exemption, cited for cross-reference in the accreditation section's employee-exemption discussion

### UNVERIFIED claims in this file (flagged inline, listed here for visibility)

- `[KB-VCAP-027]` — the specific professional certifications (Series 7/65/82) the SEC has designated as qualifying for accredited-investor status: seeded, needs derivation against a primary SEC release.
- `[KB-VCAP-028]` is no longer UNVERIFIED — confirmed directly against the Cornell LII mirror of 17 CFR 230.506(c)(2)(ii)'s regulatory text (all five methods, including the net-worth method's required liabilities-disclosure representation).
- `[KB-VCAP-029]` — current status and exact conditions of 2025-dated SEC staff guidance on minimum-investment-amount verification: sourced to third-party legal commentary, not the SEC's own primary release.
- `[KB-VCAP-034b]` — New York's specific $300/$1,200 Form D notice-filing fee tiers: sourced to third-party legal-alert summaries of the state's own EFD fee schedule, not independently re-fetched from the New York AG's own primary page this pass.
- `[KB-VCAP-035]` — NASAA EFD's $150 one-time system fee: not independently confirmed against NASAA's own primary site.
- `[KB-VCAP-038b]` — current status of the 2026 SEC staff guidance on Reg CF's rolling 12-month $5M cap calculation: sourced to third-party legal commentary, not the SEC's own primary release.
- `[KB-VCAP-039]` — Reg CF's specific individual non-accredited investor dollar investment limits: not independently confirmed; needs derivation against the SEC's current investor-limit table.
