# Capital — index

Files in this directory cover raising a small amount of outside capital (angel/pre-seed) as a
first-time, solo founder: when it helps or hurts, the standard instrument used (the YC-style SAFE)
and its dilution math, current market sizing data, entity-type prerequisites, cap tables, pitch
materials, and the interaction between raising and a near-term sale — plus the federal and state
securities-law rules that govern how any of that money can legally be raised.

Read `securities-rules-for-founders.md` before ever contacting a prospective investor — it governs
*how* an angel round may be marketed and who may fund it. Read `angel-rounds-and-safes.md` for the
economics and mechanics once the legal frame from that file is understood.

## Files

- **`angel-rounds-and-safes.md`** — When a small angel round helps vs. hurts a given company; the
  YC post-money SAFE's terms (valuation cap, discount, MFN, pro rata side letter); worked dilution
  arithmetic for a single SAFE and for stacking multiple SAFEs, including the option-pool-shuffle
  effect at a priced round; current (2026) sourced data on typical pre-seed round sizes and
  valuation caps; why a company usually must be a Delaware C-corp (not an LLC) to issue a SAFE
  cleanly, and how/when to convert; what a cap table is and why it must be maintained from the
  first signed instrument; the pitch materials a first-time founder needs; and the disclosure
  problem created by raising while also exploring a sale of the company.
  19 claim ids (`[KB-VCAP-001]`–`[KB-VCAP-016]`, plus `[KB-VCAP-041]`–`[KB-VCAP-043]`), 5 sources,
  3 UNVERIFIED (the option-pool-size range, the pro-rata-side-letter dollar threshold, and the
  deck-length range — each listed inline and in that file's own "UNVERIFIED claims in this file"
  closing section; the SAFE's liquidity-event clause, `[KB-VCAP-016]`, is now confirmed directly
  against YC's own SAFE FAQ/User Guide and is no longer flagged UNVERIFIED).

- **`securities-rules-for-founders.md`** — Regulation D Rule 506(b) vs. 506(c) (private/
  no-solicitation vs. public/accredited-only-and-verified); what counts as general solicitation and
  what doesn't, including the "pre-existing substantive relationship" doctrine and the cold-outreach
  gray zone; the accredited-investor definition and the documented methods for verifying it under
  506(c); the Form D filing requirement and its 15-calendar-day deadline; state blue-sky notice
  filings; why paying a "finder" a success fee risks unregistered-broker-dealer liability;
  Regulation Crowdfunding as an alternative public-raise path; what a founder may safely post
  publicly/on LinkedIn while raising without it becoming solicitation; and the specific triggers
  that make securities counsel mandatory rather than optional.
  27 claim ids (`[KB-VCAP-017]`–`[KB-VCAP-040]`, plus `[KB-VCAP-023b]`, `[KB-VCAP-024b]`,
  `[KB-VCAP-034b]`, `[KB-VCAP-038b]`, `[KB-VCAP-044]`), 9 sources, 5 UNVERIFIED claims (listed both
  inline and in that file's own "UNVERIFIED claims in this file" closing section: the specific
  SEC-designated professional certifications for accredited-investor status; the current
  status/conditions of 2025-dated SEC staff guidance easing 506(c) verification; New York's specific
  Form D notice-filing fee tiers; NASAA EFD's stated $150 system fee; and the current status of 2026
  SEC staff guidance on Reg CF's rolling-12-month cap calculation — `[KB-VCAP-028]`'s five
  verification methods are now confirmed directly against the regulatory text and no longer
  UNVERIFIED).

## Decision rules — which file to open

- IF the question is "should we raise, and how much/what terms," THEN start with
  `angel-rounds-and-safes.md`.
- IF the question is "can we legally talk to this person / post this / pay this person for an
  intro," THEN start with `securities-rules-for-founders.md`.
- IF the company is currently an LLC and any raise (even a small SAFE) is being considered, THEN
  read `angel-rounds-and-safes.md` §5 before any other step — the entity-type prerequisite gates
  everything else in both files.
- IF a sale process and a raise could overlap in time, THEN read `angel-rounds-and-safes.md` §8 and
  bring counsel in per `securities-rules-for-founders.md` §10 before proceeding with either.

## Anti-patterns (cross-file)

- Treating either file as a substitute for actual securities/tax counsel at the trigger points each
  file names — both files are informational grounding for the venture department's agents, not a
  legal opinion for any specific raise.
- Quoting a market-data figure (round size, cap, valuation) from `angel-rounds-and-safes.md` without
  checking its retrieval date — Carta's own data moves materially quarter to quarter and both files
  say so explicitly.
- Assuming a "small" or "informal" raise is exempt from the Form D/blue-sky/solicitation rules in
  `securities-rules-for-founders.md` — none of those rules have a de minimis dollar carve-out for a
  friends-and-family-sized round.
