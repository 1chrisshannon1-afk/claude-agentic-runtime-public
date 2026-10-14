# Escalation Triggers

When a review response requires the operator's hand instead of an agent draft, and what review
content stops an agent cold before it writes a single word.

## 0. Mandatory pre-filter for a HIPAA-covered practice — read this before anything else in this file

**For any dental, medical, or other HIPAA-covered practice account, every review response first
passes `compliance/hipaa-marketing-for-practices.md` §6.1's non-confirming reply template — full
stop, before this file's own triggers are applied.** That compliance-file gate governs *whether and
how* a reply may confirm patient status or restate any clinical/financial/insurance detail; nothing
in §§1-6 below overrides it. §6.1 also names its own hard-stop set (a clinical detail, a malpractice
allegation, or a legal threat in the review) that escalates regardless of what this file's §2 table
says. Add "clinical claim / treatment detail / malpractice allegation / HIPAA-relevant disclosure"
as a hard-stop for a HIPAA-covered practice specifically — §2's table below now includes this row.

## 1. The base rule (mechanism ported from prior dental-vertical reputation doctrine)

**Citation (internal doctrine, dental vertical, retrieved 2026-09-05):** Stop conditions include *"A
negative review requires a response and contains a clinical claim, a HIPAA-relevant disclosure, or
a threat of legal action."* And: *"For 1-3 star reviews: flag for same-day operator attention
before drafting."*

**Mechanism, not the numbers:** the dental source's specific triggers ("clinical claim,"
"HIPAA-relevant disclosure") are vertical-specific — for a home-services/contractor company they
don't port literally, since there is no patient or clinical relationship to protect. What ports is
the STRUCTURE: certain review content is categorically outside what an agent should draft against,
full stop, regardless of star rating, because responding to it requires legal, safety, or ownership
judgment an agent should not make unilaterally. For a HIPAA-covered practice, the dental triggers DO
apply directly and are restated as a hard-stop row in §2 below (see §0).

## 2. Hard stop conditions — never draft, escalate immediately (mechanism port + home-services derivation)

| Trigger | Why this stops an agent, not just slows it down | Vertical origin |
|---|---|---|
| **Threat of legal action** (reviewer states or implies they are pursuing legal action, filing a complaint with a licensing board, or "talking to a lawyer") | A public reply can become evidence; the business's legal counsel — not a marketing agent — decides what, if anything, gets said publicly. | Direct mechanism port from the dental-vertical doctrine — applies unchanged. |
| **Safety or code-violation claim** (reviewer alleges unsafe electrical/gas/structural work, a code violation, or an injury on the job site) | This is the construction-vertical equivalent of the dental source's "clinical claim" — a claim about the actual physical work performed, not a service/experience complaint. A wrong public response can be read as an admission or a denial of a safety issue with real liability exposure. | Home-services derivation from the dental doctrine's "clinical claim" trigger — re-derived, not ported as a number (there is no number here; this is the mechanism transplanted to the correct vertical-specific claim type). |
| **Licensing/insurance dispute** (reviewer claims the business was unlicensed, uninsured, or misrepresented licensing/insurance status for the job) | Directly touches the business's legal standing to operate — same category of "needs counsel/ownership judgment, not a marketing draft" as the legal-threat trigger above. | Home-services derivation — construction's licensing/insurance exposure is the rough equivalent of dental's HIPAA/clinical-disclosure exposure: a regulatory/legal-standing claim, not a service complaint. |
| **Payment or contract dispute with specific dollar figures** (reviewer states an exact amount they were overcharged, a contract term the business allegedly violated, or accuses the business of a billing scam) | A public reply that confirms or disputes a specific dollar figure can be read as an admission in a later dispute; this belongs in a private, ideally written (not just phone) conversation the operator controls. | Home-services derivation — the financial-liability equivalent of the dental source's stop conditions. |
| **Any review disclosing another person's private information** (a customer's address, a subcontractor's personal details, a dispute involving a named third party who did not consent to being named publicly) | Privacy exposure — same shape as the dental source's "HIPAA-relevant disclosure" trigger, generalized: any review that would require the BUSINESS's reply to further publish someone's private information is a stop. | Direct structural port of the dental doctrine's "HIPAA-relevant disclosure" trigger, generalized past healthcare's specific privacy law to the general privacy-exposure shape. |
| **Clinical claim / treatment detail / malpractice allegation / HIPAA-relevant disclosure** (for dental/medical companies: the review names a clinical detail, a treatment/diagnosis, a malpractice allegation, or any content that would require confirming patient status to answer) | Confirming patient status or restating a clinical/financial/insurance detail in a public reply is itself a PHI disclosure, independent of what the reviewer volunteered first — see `compliance/hipaa-marketing-for-practices.md` §6.1 for the full non-confirming-reply rule and the two enforcement cases behind it. | §1's dental-vertical original trigger (see also `compliance/hipaa-marketing-for-practices.md` §6.1). |

## 3. Soft escalation — operator sees it before a draft is written, but it is not a hard stop

**Citation (internal doctrine, dental vertical, same source as §1, retrieved 2026-09-05):** *"For 1-3 star reviews: flag for same-day operator attention
before drafting."*

Every 1-star and 2-star review is soft-escalated: the operator (or whoever holds that role for this
seat) sees the raw review same-day, before an agent drafts anything, even when none of §2's hard
triggers apply. This is not because a low-star review is presumed to be a legal problem — most
aren't — it's because a negative review is exactly the place a hard-trigger fact hides in the
details (a customer might mention "and there's no way they're actually licensed for this" almost in
passing), and the base rate of missing that on a fast read is nonzero. **3-star reviews get the same
same-day-visibility treatment** even though `response-templates-by-severity.md` gives them a
different response structure than 1-2 star — visibility and drafting-structure are separate axes:
this file (escalation-triggers.md) governs whether a draft may be written at all (the
review-content question); `response-templates-by-severity.md` governs how a cleared review is
structured once drafting starts (the response-structure question).

## 4. What "escalate" means in practice

Escalating is NOT the same as refusing to help — it means:
1. The raw review content and platform link go to the operator (or the standing operator-input
   surface the company's own pack/dossier names for this seat) with a one-line summary
   of why it triggered.
2. The agent does not draft a response, publish anything, or contact the reviewer.
3. The agent may still do everything else normal for that review (log it, add it to a reputation
   tracking sheet, flag related pattern if this is the third similar complaint this month — that
   pattern-flagging is itself valuable operator input).

**Every company running this doctrine has its own operator-input surface and its own discipline
for reaching it** — a review carrying a legal threat or a licensing dispute is exactly the kind of
item that surface exists for, whatever form it takes for a given company (a decision queue, a
tracker's operator-actions section, a direct message). See that company's own pack/dossier for
where escalations actually get filed; this file names no specific surface because none is
universal across every company this corpus serves.

## 5. Pass/reject examples

- **REJECT (should have escalated, didn't):** A 1-star review says "these guys weren't even
  licensed to pull the permit, I checked" — an agent drafts a friendly "sorry to hear that, please
  call us" response without flagging the licensing claim. This is exactly the §2 licensing-dispute
  trigger; the draft should never have been written before operator eyes on it.
- **REJECT (over-escalated, wastes the operator's time):** A 3-star review that says "the crew was
  great but showed up 40 minutes late both days" gets treated as a hard stop requiring legal
  review. There is no §2 trigger here — this is a straightforward same-day-visibility soft
  escalation per §3, draftable per `response-templates-by-severity.md` §3 once seen.
- **PASS:** A 2-star review mentioning a scheduling complaint with no legal/safety/licensing content
  goes through same-day operator visibility (§3), then gets drafted per
  `response-templates-by-severity.md` once cleared.
- **PASS:** A 1-star review alleging an electrical outlet installed during a bathroom remodel is
  "sparking and dangerous" is flagged as a hard stop (§2, safety/code-violation trigger) — no draft
  is written; it goes straight to the operator with the safety claim called out explicitly in the
  escalation note.

## 6. Contractor bend

The dental source's triggers (clinical claim, HIPAA) map to a licensed-professional, heavily
regulated vertical where a wrong public statement risks a licensing board complaint on top of
ordinary reputational harm (see §0 above for how those triggers apply directly, unmodified, to a
HIPAA-covered practice using this file). For home-services/contractor companies, construction
carries an analogous but differently-shaped risk profile:
the safety/code-violation and licensing/insurance triggers above are this vertical's equivalent
regulatory exposure, but the owner-operator residential-remodeling GC archetype (whose relevant
end-customer persona is `shared/homeowner-buyer-psychology.md`;
`shared/contractor-buyer-psychology.md` is a different, B2B software-buyer persona) ALSO faces a risk the dental mechanism
doesn't: **subcontractor blame-shifting inside a public review.** A homeowner's negative review
about "the plumber's shoddy work" may actually be about a sub the GC hired, not the GC's own crew —
this is not one of the hard-stop legal triggers above, but it is a genuine judgment call (does the
response own it anyway, since the GC hired and is responsible for the sub? does it name the sub?)
that a marketing agent should not resolve unilaterally either — treat "review blames a named
subcontractor" as an additional soft-escalation trigger alongside every 1-3 star review, flagged
explicitly as "sub-attribution question" in the escalation note so the operator knows exactly what
judgment call is being asked of them.
