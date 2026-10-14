# Selection — index

Knowledge base for the hiring agent's applicant-selection work: screening, scoring, interviews,
background checks, offers, and onboarding paperwork. Company-agnostic — used for any small US
business hiring staff (employees or individual contract workers) (a remodeling company hiring crew, a small SaaS hiring
engineers, a dental office hiring hygienists). The agent drafts and prepares every artifact
described here; the operator posts, contacts, decides, and signs.

- **[screening-scoring-and-interviews.md](screening-scoring-and-interviews.md)** — how to build a
  written rubric per role from its must-haves; the hard separation between fit tiers (strong match /
  worth interviewing / needs review / reject) and compliance clearance, and the rule that a failed
  lookup or missing data always resolves to "needs review," never a rank change; consistency and
  documentation; the four-fifths adverse-impact rule (29 CFR § 1607.4(D)); AI/automated-screening
  risk and the specific NYC Local Law 144, Illinois AI Video Interview Act plus the Illinois Human
  Rights Act's own AI provision, Colorado's SB26-189 (enacted, effective 2027-01-01), and California
  ADS-regulation rules; structured interview design and scorecards;
  lawful vs. unlawful interview questions; salary-history bans; reference checks; candidate
  communication standards; and outreach-channel rules (email is fine, texting needs documented
  consent, never an automated/AI voice call).
- **[background-checks-offers-and-onboarding.md](background-checks-offers-and-onboarding.md)** —
  FCRA-compliant background checks (standalone disclosure, written authorization, pre-adverse and
  adverse action notices with the CFPB Summary of Rights); ban-the-box/fair-chance laws (federal
  contractors, California Fair Chance Act, Colorado Chance to Compete Act, others vary) — including
  that no criminal-history question is safe before a conditional offer, not just on the application
  form itself; driving records for driver roles (FMCSA coverage turns on vehicle weight, not CDL
  status — a non-CDL truck-and-trailer combination can still be a covered commercial motor vehicle);
  drug-testing basics and the state-law variation flag; license
  verification for licensed trades and healthcare roles; offer letters (at-will language, what not
  to promise); Form I-9 timing (Section 1 by day one, Section 2 within 3 business days); E-Verify
  (voluntary vs. required); W-4 and state withholding; new-hire reporting to the state; worker
  classification (links to `venture_kb/recruiting/equity-and-agreements.md` §9 rather than
  duplicating it); workers' comp and required posters; and a first-week onboarding checklist.

Both files are information, not legal, tax, or accounting advice — they name where an employment
attorney, a CPA, or the relevant state agency must actually decide, and never instruct posting,
contacting, deciding, or signing anything on the operator's behalf. State-law differences are
flagged throughout; Colorado, California, Washington, and New York are covered by name where a
sourced rule was found, and every other state is noted as varying and requiring its own check.

## What's out of scope here (see elsewhere)

- **Co-founders, advisors, and equity** — a different lane entirely; see
  [`~/.claude/knowledge/venture_kb/recruiting/`](../../venture_kb/recruiting/INDEX.md), never
  repeated in this KB.
- **Job posting itself** (writing the posting, distributing to Indeed and other boards, the
  approval-gated posting/retrieval mechanics) — a sibling area of this KB
  (`~/.claude/knowledge/hiring_kb/posting/`), not covered by these two files.
- **TCPA/SMS-consent mechanics for texting a candidate** — covered in full in
  [`~/.claude/knowledge/marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md)
  and linked from `screening-scoring-and-interviews.md` §12 rather than duplicated.

## Claim-id range

Both files in this directory use claim ids `[KB-HSEL-NNN]`, numbered sequentially starting at 001:
`screening-scoring-and-interviews.md` uses 001–015 plus 034–036 (added later to tag previously
untagged §8/§10/§12 content so the `hiring-specialist` agent can cite it);
`background-checks-offers-and-onboarding.md` uses 016–033 plus 037–040 (same reason, for §5/§9/§12/
§13). A future file added to this directory should continue the sequence from 041. No collision with
any other KB's claim-id range (each KB area uses its own prefix — see `KB-COMPLIANCE-*` in
`marketing_kb/compliance/`, `KB-VREC-*` in `venture_kb/recruiting/`).

## Known UNVERIFIED claims in this directory (as of 2026-09-28)

Carried here for visibility — each is also flagged in place in its source file. Several items
formerly listed here were resolved by reading the primary source directly during a later review
pass and are removed from this list: Illinois AI Video Interview Act's enactment date and its §20
demographic-reporting duty (both now read directly at ilga.gov); the Illinois Human Rights Act's own
AI provision, § 2-102(L) (also read directly, newly added to this KB); Colorado SB26-189's enacted
substantive text (read directly at leg.colorado.gov); Colorado Chance to Compete Act's official CDLE
INFO #9C text (read directly, and corrected a 10x-wrong penalty figure); FMCSA's 30-day MVR inquiry
window under 49 CFR § 391.23 (confirmed directly, and the KB's prior claim that FMCSA rules require a
CDL was itself found and corrected — CMV status turns on vehicle weight under 49 CFR § 390.5, not
license class); and the I-9 Section 2 three-business-day rule (confirmed directly against both USCIS
guidance and 8 CFR § 274a.2, no longer third-party-only).

- California Civil Rights Council ADS-regulation exact text (substance corroborated by three
  independent law-firm summaries; the regulation's own site returned a connection error).
- Complete current state list for salary-history bans (a safe universal default — never ask, any
  state — is given instead of relying on the incomplete list).
- FCRA pre-adverse-action waiting-period specific day count (no fixed federal number exists; a
  commonly used practice figure is flagged as unverified against the statute itself).
- CFPB Summary of Rights (Appendix K) exact current text (existence and title confirmed; full text
  not retrieved).
- Federal Fair Chance Act (contractors) exact scope/date; California Fair Chance Act's exact current
  notice/response timelines; Washington's and New York's specific ban-the-box mechanics (not
  independently verified this pass).
- U.S. DOT 49 CFR Part 40's exact drug-panel and alcohol-testing scope (not independently read this
  pass; a secondary source reports pre-employment alcohol testing is NOT required for FMCSA-covered
  drivers, only pre-employment drug testing — verify directly before relying on the panel details).
- State-specific drug-testing restrictions (Colorado, California, Washington, New York) — flagged as
  requiring a state-specific legal check before policy is built, not asserted here.
- I-9 penalty dollar figures and any specific 2026 enforcement-policy characterization circulating in
  secondary sources — excluded from the file rather than quoted as fact.
- E-Verify's current state-by-state mandate list.
- Workers' comp coverage threshold and the complete required-poster list, per state.
- Montana's Wrongful Discharge from Employment Act mechanics (the fact that Montana is an at-will
  exception is flagged; its statute text was not read this pass).
- State-by-state reference-check disclosure-immunity statutes (a general pattern is flagged as
  existing; not independently verified per state).

Re-verify any of the above against its named primary source before it anchors a specific compliance
claim made to an operator or a client, per this corpus's citation-style re-verification discipline.
