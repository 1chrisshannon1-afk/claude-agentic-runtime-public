# Screening, scoring, and interviews

**What this file answers:** how to build a written screening rubric per role from its must-haves,
why fit tiering must be kept structurally separate from compliance clearance, the rule that a
failed lookup or missing data never moves a candidate's rank, why consistency and documentation
matter for legal defensibility, the EEOC's four-fifths rule for adverse impact, the risks and
state/local rules around AI and automated screening tools, how to design structured interviews and
scorecards, which interview questions are lawful and which are not, salary-history bans, reference
checks, candidate-communication standards, and which outreach channels are safe to use (and which
need consent first).

This file is information, not legal advice. An employment attorney — not this file, not the hiring
agent — decides how a specific screening process, question, or automated tool should be built or
defended in a specific state. Where state law differs, Colorado, California, Washington, New York
are called out by name; every other state varies and must be checked before a multi-state process
is finalized.

---

## 1. Build a written rubric per role, derived from the must-haves — never from vibes

**Decision rule:** before the first resume is screened, write down (a) the role's true
must-haves (the small set of things that make someone unable to do the job at all — a required
license, a legally required certification, availability for the actual shift, ability to lift X
lbs for a physical role), (b) the things that are merely preferred, and (c) the specific evidence
that will be accepted as proof of each. Score every candidate against that same written rubric.
Never let two candidates for the same role get judged against two different unwritten standards —
that is the single most common way a screening process becomes legally indefensible, because there
is no record of what was actually being measured `[KB-HSEL-001]` (internal doctrine, retrieved
2026-09-28 — generalized from a real in-house hiring system's role-requirements design, which maps
a job title to a canonical role definition specifying required-vs-expected credentials and which
checks apply to that role; the mechanism generalizes to any profession by defining a new role's
credential taxonomy the same way, never by improvising per candidate).

A rubric should be genuinely job-related and consistently applied — the EEOC's guidance on
employment tests and selection procedures states that under Title VII and the ADA, a test or
selection procedure can be lawful even if it has a disparate impact on a protected group, so long
as the employer can show the procedure is **job-related and consistent with business necessity**,
and that no less-discriminatory alternative would serve the employer's needs equally well
`[KB-HSEL-002]` (official, EEOC "Employment Tests and Selection Procedures," retrieved 2026-09-28).
In practice that means: write down why each must-have is actually necessary to perform the job,
not merely convenient or traditional, before using it to screen anyone out.

**Anti-pattern:** a rubric written after screening has already started, "reverse-engineered" to
justify whichever candidates were already favored. If the rubric changes mid-search, document why,
apply the new version going forward, and never re-score earlier candidates selectively to change an
outcome.

## 2. Keep fit tiers and compliance clearance on two separate axes — never one blended score

**The single most important structural rule in this file.** Separate two different questions that
are easy to blend into one number and should never be blended:

- **Fit / rank** — "should a human prioritize looking at this candidate now?" Based on how well the
  candidate's real, verifiable qualifications match the role's rubric (§1) and the posting's
  screening criteria (skills, schedule, pay-band fit, keyword/experience match).
- **Compliance clearance** — "has every required check that gates an actual hire been completed and
  come back clean?" (license/certification verification, right-to-work status, background check
  results, reference checks). This is a pass/fail/pending gate on the eventual hire decision, not a
  ranking input.

Use four fit tiers, evaluated purely on fit evidence:

| Tier | Meaning |
|---|---|
| **Strong match** | Meets every must-have with strong, verifiable evidence; clearly worth fast-tracking to interview. |
| **Worth interviewing** | Meets the must-haves but with some gaps or unclear evidence; worth a conversation to clarify. |
| **Needs review** | Missing information, an inconclusive check, or a borderline case that a human must look at before any tier decision is finalized — this tier also catches every failed/incomplete compliance lookup (§3). |
| **Reject** | A verified, adverse finding directly relevant to the role — not an assumption, not an inconclusive result. |

This rank-vs-clearance split, and the rule in §3 below, is generalized from a real in-house hiring
system that deliberately separates a candidate's fit tier from a distinct compliance "cleared to
hire" verdict, and documents that an infrastructure error or an inconclusive lookup must never be
allowed to move a candidate's fit ranking `[KB-HSEL-003]` (internal doctrine, retrieved 2026-09-28).
This generalizes to any background-check-driven hiring flow — contractor licensing, professional
registration, a driving-record check for a driver role, a standard criminal background check — by
swapping in whichever checks are universal (apply to every role) versus role-gated (apply only when
the specific role legally or practically requires them).

**Decision rule:** `REJECT` fires only on a verified adverse finding that is actually relevant to
the specific role being filled (e.g., an expired or suspended license for a role that legally
requires one, a confirmed sanctions/exclusion-list hit, a background-check result the employer has
individually assessed as job-related under the applicable ban-the-box law — see the companion file
for the FCRA/ban-the-box mechanics). It never fires on a check that could not be completed.

## 3. A failed lookup or missing data never moves a candidate's rank — it becomes "needs review"

**This is a hard rule, not a preference.** If a license-verification API times out, a background
check comes back inconclusive, a reference doesn't answer, or a data field is simply missing, the
candidate's fit tier and hire recommendation must **freeze at "needs review"** — never silently
downgrade to reject, and never quietly advance as if the check had passed. The distinction that
must never be lost: an infrastructure failure or a data gap is not evidence of anything about the
candidate `[KB-HSEL-004]` (internal doctrine, retrieved 2026-09-28 — the same in-house design
explicitly documents this as a load-bearing rule in its scoring engine, barring any inconclusive or
error result from moving rank).

**Why this matters legally, not just operationally:** if a screening tool systematically treats
"check could not be completed" as equivalent to "check failed," and that failure mode correlates
with any protected characteristic (e.g., a records database that returns more false negatives for
certain name patterns, address histories, or countries of prior residence), the tool has built a
disparate-impact risk into its own error-handling path, not just its scoring logic. Treating every
non-passing state as a "needs review, human decides" state — never a silent rejection — is both the
safer and the more legally defensible default.

**Anti-pattern:** a dashboard that displays only "cleared" / "not cleared" with no third state for
"still pending" or "could not verify" — this design choice alone forces every incomplete check to
be miscoded as a failure.

## 4. Consistency and documentation

- Score every candidate for the same requisition against the identical written rubric (§1), and
  keep a record of what evidence was used for each score — not just the final number. If asked
  later why a candidate advanced or didn't, "the file shows the rubric and the evidence" should be
  the entire answer.
- Do not change the rubric or interview questions mid-pipeline for the same requisition without
  documenting the change and the reason, and never apply a changed rubric retroactively to
  selectively re-score candidates who were already screened under the old one.
- Keep records long enough to satisfy any applicable retention requirement (see the companion file,
  `background-checks-offers-and-onboarding.md`, for federal recordkeeping minimums) — a
  screening decision with no surviving record of its basis is close to indefensible if challenged.
- Log every screening/scoring action against a real requisition, not a person's private notes —
  the record needs to be attributable and reviewable by someone other than the person who made the
  call.

## 5. Adverse impact basics — the EEOC's four-fifths rule

**[KB-HSEL-005]** The Uniform Guidelines on Employee Selection Procedures (UGESP; adopted jointly by
the EEOC, DOL, DOJ, and the former Civil Service Commission, codified at 29 CFR Part 1607) set out
the **four-fifths (80%) rule** at **29 CFR § 1607.4(D)** as the standard practical test enforcement
agencies use to flag a possible adverse impact: a selection rate for any race, sex, or ethnic group
that is **less than four-fifths (80%)** of the rate for the group with the **highest** selection rate
will generally be regarded as evidence of adverse impact, while a greater-than-four-fifths rate will
generally not be. **The Guidelines themselves also state the reverse case, which this KB previously
omitted: smaller differences in selection rate can still count as adverse impact where they are
significant in both statistical and practical terms**, or where the employer's own actions
discouraged applicants disproportionately by race, sex, or ethnic group — so a pass rate just above
80% is not an automatic safe harbor either. Conversely, a larger raw difference may not be adverse
impact where it is based on small, statistically insignificant numbers, or where a special
recruiting program causes an atypical applicant pool. The four-fifths rule is explicitly **not a
legal definition of discrimination** — it is a practical screening threshold for enforcement
attention, not a safe harbor or an automatic violation on its own (official, 29 CFR § 1607.4(D),
retrieved 2026-09-28).

**How to actually compute it, in plain steps:**
1. For each group, divide the number selected (e.g., advanced past the screen, or hired) by the
   number who applied. That is the group's selection rate.
2. Find the group with the highest selection rate.
3. Divide every other group's selection rate by the highest group's rate. That ratio is the
   "impact ratio."
4. Any group with an impact ratio below 0.80 (80%) is a flag worth investigating — not proof of
   discrimination on its own, but a signal that the selection step (a test, a keyword filter, a
   resume-screening rule, an interview-scoring pattern) should be examined for whether it is
   actually job-related and necessary, and whether a less-discriminatory alternative exists that
   would work as well `[KB-HSEL-006]` (official, same source as KB-HSEL-005).

**Decision rule:** any time a screening step (a keyword filter, a required-years-of-experience
cutoff, a physical test, an automated tool — see §6) is applied consistently at scale across many
candidates, periodically check its pass rates by group where that data is available and legally
appropriate to collect, using the four-fifths calculation above. A single small requisition with
few applicants will rarely produce statistically meaningful numbers — this check matters most once
volume is real (e.g., a recurring high-volume role, or any use of an automated screening tool at
scale).

**Anti-pattern:** assuming that because a criterion is "neutral on its face" (e.g., "must have a
four-year degree" for a role that doesn't actually require one) it cannot create adverse impact.
Facially neutral criteria are exactly what the four-fifths rule and business-necessity test exist
to examine.

## 6. AI and automated screening — risks and specific state/local rules

Using AI or an automated tool to screen, rank, or score candidates does not remove any of the legal
obligations above — it adds new, tool-specific ones. Treat every automated screening step as
subject to (a) the same adverse-impact scrutiny as any other selection procedure (§5), and (b) any
specific jurisdictional rule below that applies to the tool or the candidate's location.

### 6.1 New York City — Local Law 144 (Automated Employment Decision Tools)

**[KB-HSEL-007]** NYC Local Law 144 requires any employer or employment agency using an "automated
employment decision tool" (AEDT) to screen candidates for employment decisions within New York City
to: (a) have the tool undergo an independent **bias audit** within one year before use, (b) make a
summary of the bias-audit results **publicly available** (e.g., posted on the employer's own
careers page), and (c) provide **notice to candidates or employees** at least **10 business days**
before the tool is used, including how to request an alternative selection process or accommodation
where available. Enforcement began **July 5, 2023**. Complaints can be filed with the NYC
Department of Consumer and Worker Protection (DCWP) (official, NYC DCWP "Automated Employment
Decision Tools," retrieved 2026-09-28). **Decision rule:** if a candidate's application will be
screened by an AI/automated tool and the role is based in or the hiring is otherwise covered by NYC
jurisdiction, do not run that tool against that candidate until the bias audit, public summary, and
10-business-day candidate notice are all confirmed in place — treat this as a hard precondition, not
a nice-to-have.

### 6.2 Illinois — Artificial Intelligence Video Interview Act, and the Human Rights Act's AI rule

**[KB-HSEL-008]** The Illinois Artificial Intelligence Video Interview Act (820 ILCS 42) applies
specifically to **video interviews analyzed by AI**, for positions based in Illinois. Before the
interview, an employer that will use AI to analyze an applicant's video interview must: (a) notify
the applicant that AI may be used to analyze their video and consider their fitness for the
position, (b) provide information explaining how the AI works and what general types of
characteristics it uses to evaluate applicants, and (c) obtain the applicant's **consent** to be
evaluated by that AI. The employer may not share applicant videos except with people whose expertise
or technology is genuinely necessary to evaluate fitness for the role. On request from the
applicant, the employer must **delete the applicant's video interviews within 30 days**, including
instructing any other party who received copies to delete them, including backups. The Act is
effective **January 1, 2020**. **A second, separate obligation applies to employers who rely
*solely* on AI analysis of video interviews to decide who gets an in-person interview** (820 ILCS
42/20, added by P.A. 102-47, effective January 1, 2022): those employers must collect and report the
race and ethnicity of (a) applicants who are and are not given an in-person interview after the AI
analysis, and (b) applicants who are hired, to the Illinois Department of Commerce and Economic
Opportunity (DCEO) annually by **December 31**, covering the 12 months ending the prior November 30;
DCEO in turn reports to the Governor and General Assembly by July 1 each year on whether the data
shows racial bias (official — 820 ILCS 42, read directly at ilga.gov, retrieved 2026-09-28 — this
corrects a prior version of this claim, which had not read ilga.gov directly, tagged the enactment
date as unverified, and omitted the §20 reporting duty entirely).

**[KB-HSEL-008b]** Separately from the AI Video Interview Act, the **Illinois Human Rights Act, 775
ILCS 5/2-102(L)** (added by P.A. 103-804, effective **January 1, 2026**) makes it a civil rights
violation for an employer to use artificial intelligence — in recruitment, hiring, promotion,
discharge, discipline, or the terms/privileges/conditions of employment — that has the effect of
discriminating on the basis of a protected class, **or to use zip codes as a proxy for a protected
class**. It also requires an employer to notify an employee that it is using AI for these purposes;
the Illinois Department of Human Rights is directed to adopt rules on the specifics of when and how
notice must be given (official — 775 ILCS 5/2-102(L), read directly at ilga.gov, retrieved
2026-09-28). **Decision rule:** for an Illinois-connected hiring process using any AI tool (not only
video-interview AI), check both statutes — the AI Video Interview Act's notice/consent/deletion
regime where video interviews are AI-analyzed, and the Human Rights Act's broader
discrimination/zip-code-proxy/notice rule for any AI use in the employment decision generally.

### 6.3 Colorado — the (since-replaced) Colorado AI Act

**[KB-HSEL-009] Verify current status before relying on this — the law changed twice, in 2025 and
2026.** Colorado's SB24-205 ("Colorado AI Act"), enacted in 2024, was originally set to take effect
February 1, 2026, and would have required deployers of "high-risk" AI systems (a category that
includes AI systems making or substantially contributing to consequential decisions about
employment) to implement a risk management policy, complete impact assessments, conduct annual
reviews for algorithmic discrimination, notify consumers when AI is used to make a consequential
decision about them, and provide a process to correct or appeal that decision. In 2025, the
legislature delayed the effective date to June 30, 2026 (SB25B-004, signed August 28, 2025). Before
that delayed date took effect, **SB24-205 was repealed and re-enacted as SB26-189 (signed May 14,
2026), which takes effect January 1, 2027.**

**SB26-189's own enacted substance (official — Colorado General Assembly, SB26-189 enrolled bill
summary, `leg.colorado.gov`, retrieved 2026-09-28):** the act defines "automated decision-making
technology" (ADMT) broadly (any technology processing personal data to generate output — a
prediction, recommendation, classification, ranking, or score — used to make, guide, or assist a
decision about a person) and a "consequential decision" to include one affecting a person's access
to, eligibility for, or compensation related to **employment**, among other listed areas. Starting
**January 1, 2027**: an ADMT's developer must give a deployer technical documentation (intended
uses, training-data categories, known limitations, human-review instructions) and notify the
deployer of material updates; both developer and deployer must retain compliance records for at
least **3 years**; a deployer must give consumers **clear and conspicuous notice at the point of
interaction** with a covered ADMT, and within **30 days** of an adverse consequential decision must
give a plain-language description of the ADMT's role in that decision; consumers have the right to
request their own data, request correction of factually incorrect data the ADMT used, and request
**meaningful human review and reconsideration** of an adverse decision. The Colorado Attorney
General enforces the act as a deceptive trade practice under the Colorado Consumer Protection Act,
and — until January 1, 2030 — must give a **60-day notice and cure opportunity** before suing. The
act does not create a new private right of action, but does address how fault is allocated between
developers and deployers in an existing discrimination lawsuit.

**Decision rule until re-verified:** treat Colorado as covered by SB26-189 starting January 1, 2027
— do not tell an operator Colorado has no such law, and re-check the enrolled SB26-189 text (or the
Attorney General's implementing rules, due by the same date) before advising a client on the exact
current mechanics, since rulemaking may still refine the notice and cure procedures.

### 6.4 California — Civil Rights Council automated-decision-system regulations

**[KB-HSEL-010]** California's Civil Rights Council (part of the Civil Rights Department, enforcing
FEHA) adopted regulations on employers' use of "automated-decision systems" (ADS) in employment,
effective **October 1, 2025**. An ADS is defined broadly as a computational process — which may use
AI, machine learning, algorithms, statistics, or other data-processing techniques — that makes a
decision or facilitates human decision-making about an employment benefit (which includes hiring
screening). The regulations confirm that using an ADS to make employment decisions that
discriminate against applicants or employees, directly or through disparate impact, on the basis of
a protected characteristic violates FEHA exactly as a human-made discriminatory decision would.
Employers and covered entities must **retain employment records, including automated-decision
data, for a minimum of four years**. The regulations apply to employers with **five or more
employees** connected to California (third-party, corroborated across multiple law-firm summaries
— Paul Hastings, Mayer Brown, Jackson Lewis — retrieved 2026-09-28; the Civil Rights Council's own
regulation text was not independently fetched during this pass due to a site connection error —
`UNVERIFIED (primary source unreachable: calcivilrights.ca.gov returned an error at retrieval
time)` as to the exact regulatory text; the substantive summary above is corroborated by multiple
independent law-firm sources describing the same adopted regulations, which this file treats as
reliable secondary corroboration, not a substitute for reading the regulation text itself before
advising a client).

### 6.5 General AI-screening risk, regardless of jurisdiction

**[KB-HSEL-011]** **Do not cite "the EEOC has stated" for AI-hiring liability — its technical
assistance page making that statement is gone, and its enforcement posture has shifted.** The legal
basis for employer liability over AI/algorithmic hiring tools is Title VII, the ADA, and the ADEA
themselves — using a vendor's tool does not change who the statutes hold responsible for a
discriminatory hiring decision. This KB previously grounded that in "the EEOC has stated" language;
the specific EEOC technical-assistance page making that statement now returns a 404 and was not
re-locatable this pass, so that citation is retired here. Separately, **Executive Order 14281 (FR
2025-07378)** directs federal agencies, including the EEOC, to **deprioritize enforcement of
disparate-impact liability** under statutes including 42 U.S.C. § 2000e-2 (Title VII), and orders the
Attorney General and EEOC Chair to review pending disparate-impact matters within 45 days of the
order and take action consistent with that policy (official, Executive Order 14281, Federal Register
citation 2025-07378, retrieved 2026-09-28). **What this means in practice:** federal *agency*
enforcement of disparate-impact theory is currently deprioritized at the EEOC — but this does not
repeal Title VII's disparate-impact provision itself (still 42 U.S.C. § 2000e-2(k), still the law),
does not bind a private plaintiff's own civil suit, does not touch state human-rights-law claims, and
does not affect state/local AI-hiring statutes like NYC Local Law 144 or California's ADS
regulations (§§6.1, 6.4) — those keep applying on their own terms regardless of federal enforcement
posture (official as to EO 14281's text and its deprioritization directive, retrieved
2026-09-28; internal doctrine as to the practical decision rule that follows from it). **Decision
rule:** before adopting any automated screening or scoring tool, ask the vendor directly for their
most recent bias-audit results and methodology, run the four-fifths check (§5) on the tool's own
outcomes once volume allows it, never treat a vendor's compliance claim as a substitute for the
employer's own audit, and do not treat reduced federal enforcement appetite as meaning the underlying
legal exposure (private suits, state law, NYC LL144, California's ADS rules) has gone away.

## 7. Structured interview design and scorecards

**[KB-HSEL-012]** A structured interview — the same set of job-related questions, asked in the same
order, scored against the same predefined rubric, for every candidate for a given role — is one of
the most well-supported predictors of job performance in the personnel-selection research
literature, and is far more legally defensible than an unstructured "just talk to them" interview
precisely because it produces a comparable, documented record (internal doctrine, retrieved
2026-09-28 — this is standard I/O-psychology and EEOC-enforcement-consistent practice; not itself
tied to a single named regulatory source, but consistent with the "job-related and consistent with
business necessity" standard EEOC applies to selection procedures generally, `[KB-HSEL-002]`).

**How to build one:**
1. Start from the role's rubric (§1). For each must-have and each meaningfully differentiating
   preferred quality, write one or more behavioral or situational questions that would surface real
   evidence of it (e.g., "tell me about a time you had to [X]" rather than "are you good at [X]?").
2. Write a scoring anchor for each question — what a strong, adequate, and weak answer actually
   sounds like — before the first candidate is interviewed, not after.
3. Use the same question set and scoring anchors for every candidate interviewed for that
   requisition. Deviating (skipping a question, adding an off-script one) for one candidate and not
   another undermines the comparability that makes the process defensible.
4. Score immediately after each interview, independently, before comparing notes with other
   interviewers — comparing too early anchors everyone to the first opinion voiced.
5. Keep the completed scorecards on file with the requisition record (see §4 and the retention
   guidance in the companion file).

**Anti-pattern:** a "structured" interview in name only, where the interviewer has the question
list but freely improvises follow-ups that differ candidate-to-candidate in ways that change what's
actually being evaluated, or where scores are filled in after the fact to match a gut decision
already made.

## 8. Lawful vs. unlawful interview questions

**[KB-HSEL-013]** The EEOC's general guidance on pre-employment inquiries states that information
gathered from an applicant should be **limited to what is essential for determining whether the
person is qualified** for the job, and that employers should generally avoid asking about race,
sex, national origin, age, or religion; should not ask about organizational memberships in a way
that reveals a protected characteristic; should not request a photograph before a job offer; and
are **explicitly prohibited from making disability-related inquiries before a job offer is made**
(official, EEOC "Prohibited Employment Policies/Practices," eeoc.gov/prohibited-employment-policiespractices,
retrieved 2026-09-28, for the essential-information, organizational-membership and photograph points;
official, EEOC "Job Applicants and the ADA," eeoc.gov/laws/guidance/job-applicants-and-ada,
retrieved 2026-09-28, for the disability-inquiry-before-offer point). The EEOC also
notes that even questions not flatly forbidden "may be used as evidence of an employer's intent to
discriminate unless the questions asked can be justified by some business purpose" — meaning a
facially odd but not-explicitly-banned question still carries risk if it isn't clearly tied to a
real job requirement (official, EEOC "Prohibited Employment Policies/Practices," retrieved 2026-09-28).

**[KB-HSEL-034] Categories to avoid pre-offer, as a working checklist** (internal doctrine,
retrieved 2026-09-28 — this specific checklist enumeration is this KB's own organization of the
protected categories already sourced in claim 013 and elsewhere in this file, not itself a single
EEOC citation; verify against current EEOC guidance and counsel before finalizing a
jurisdiction-specific interview guide):
- Age, date of birth, or graduation dates that reveal age (candidates 40+ are protected under the
  ADEA).
- Race, color, national origin, or ancestry.
- Religion or religious observance/holidays.
- Sex, sexual orientation, gender identity, or pregnancy/family-planning status.
- Disability, medical history, or workers'-compensation history — before an offer is made. (After a
  conditional offer, disability-related medical inquiries may be permitted in limited
  circumstances under the ADA; this is a fact-specific area — get counsel involved before any
  post-offer medical inquiry.)
- Marital or family status, number or age of children, childcare arrangements.
- Arrest record (as distinct from conviction record — see the companion file's ban-the-box section;
  arrests without conviction are generally not a lawful basis for an employment decision).
- Citizenship (as distinct from the lawful, required question of work authorization — see the
  companion file's I-9 section; "are you authorized to work in the US" is fine, "what is your
  citizenship / where were you born" is not).
- Prior salary, in any state or city with a salary-history ban (§9 below).

**Decision rule:** if a question doesn't map directly to a must-have on the written rubric (§1) or
to a legally required disclosure (like work-authorization status), don't ask it. If in doubt about
whether a specific question is safe in a specific state, treat it as unsafe until an employment
attorney confirms otherwise — this is exactly the kind of judgment call this file flags for a human,
never resolves itself.

## 9. Salary-history bans by state and city

**[KB-HSEL-014]** As of mid-2026, a substantial and growing list of states restrict employers from
asking about or relying on an applicant's salary history to set pay: reported sources name
California, Colorado, Connecticut, Delaware, Hawaii, Illinois, Maine, Maryland, Massachusetts,
Nevada, New Jersey, New York, Oregon, Rhode Island, Vermont, Virginia (effective July 1, 2026), and
Washington, plus Washington, D.C., with many additional cities/counties layering on their own local
versions (third-party, corroborated across HR Dive, Paycor, and other compliance-vendor trackers,
retrieved 2026-09-28 — `UNVERIFIED — seeded, needs derivation` as the exact, current-as-of-today
list; no single official federal registry of these state/local laws was reached during this pass,
and this list changes as new states and cities enact their own versions). **Decision rule (the safe
default, independent of the incomplete list above):** never ask a candidate about their current or
past salary, and never require it on an application form, in any state — build every offer around
the role's own budgeted pay band and the candidate's demonstrated qualifications instead. This
default is compliant everywhere this file is aware of and requires no per-state lookup before every
posting or interview. If a candidate volunteers salary-history information unprompted, do not use
it to set or justify a lower offer than the role's own band would otherwise support.

## 10. Reference checks

**[KB-HSEL-035]** (internal doctrine, retrieved 2026-09-28 — reference-check practice discipline
generalized from the same rubric/documentation principles sourced elsewhere in this file, §§1-4;
the state-immunity/disclosure-restriction point specifically is `UNVERIFIED — seeded, needs
derivation`, not independently verified state-by-state this pass):

- Get the candidate's explicit permission before contacting any reference, and confirm which
  specific people the candidate has authorized (do not contact a "backdoor" reference the
  candidate didn't list, without separately disclosing that intent).
- Ask job-related questions only — dates of employment, job duties, performance, eligibility for
  rehire — and avoid any of the protected-characteristic categories in §8, even when talking to a
  former employer rather than the candidate directly.
- Document what was asked and what was said, with the date and who conducted the check — this
  becomes part of the same defensible record discussed in §4.
- Some states restrict what a former employer may disclose, or give employers immunity for good-
  faith factual references — this varies by state; do not assume a reference will speak freely, and
  do not assume the operator's own company is shielded from liability for what it says about a
  former employee without checking applicable state law.

## 11. Candidate communication standards

**[KB-HSEL-015]** "Never ghost a candidate" is not just good practice — a hiring process with long,
unexplained silences or with unequal responsiveness across candidates is both a candidate-experience
failure and a documentation gap that undermines the "consistent process" defense described in §4
(internal doctrine, retrieved 2026-09-28 — generalized from a documented
company-agnostic hiring-process template's own per-stage communication-and-SLA table, which pairs
every pipeline stage with an owner, a target response time, and an explicit "never ghost" principle
— the response-time numbers themselves are the calling company's own internal targets and are not
restated here as a universal standard; set response-time targets appropriate to the operator's own
hiring volume and capacity, and keep them consistent across every candidate for the same
requisition).

**Decision rules:**
- Acknowledge receipt of every application, even automatically, within a short and consistent
  window.
- Send a real rejection notice to every candidate who is screened out, not just the ones who reach
  an interview — silence is not a rejection, and leaves candidates (and the process record) in
  limbo.
- Use the same response-time standard for every candidate in the same requisition; do not let a
  favored candidate get same-day replies while others wait weeks — an uneven pattern like this is
  exactly the kind of thing that turns into a legal claim tied to a protected characteristic even
  when the underlying reason had nothing to do with one.
- Keep every outreach attempt logged as a record tied to the candidate and requisition, regardless
  of channel — this is both a communication-quality practice and, for SMS specifically, load-bearing
  for the consent-and-compliance reasons in §12.

## 12. Candidate outreach channels and consent

**[KB-HSEL-036]** (the TCPA-specific sub-claims below carry their own official 47 CFR § 64.1200
citations inline; this id covers the section's overall channel-selection framework, which is
internal doctrine, retrieved 2026-09-28):

- **Email** is the default, lowest-friction channel for candidate communication and carries no
  special consent regime beyond ordinary business-communication norms — safe to use freely for
  acknowledgments, interview scheduling, and decisions.
- **Texting a candidate requires consent first.** Sending an SMS to a candidate's phone using any
  automated or bulk-sending platform (an autodialer, or a platform that sends without a human
  manually dialing/typing each message) is governed by the TCPA consent regime that governs any
  other business text message. The federal legal floor is **prior express consent** for a
  non-telemarketing autodialed or prerecorded/artificial-voice message — 47 CFR § 64.1200(a)(1) —
  which does not have to be in writing; **prior express *written* consent is required only where the
  message is telemarketing** — 47 CFR § 64.1200(a)(2) (official, 47 CFR § 64.1200, retrieved
  2026-09-28). An ordinary candidate-pipeline text ("your interview is scheduled for...") is
  ordinarily not telemarketing, so the federal floor for it is the lower, non-written prior-express-
  consent standard. **This KB's own decision rule is stricter than that floor, deliberately:**
  never enable auto-texting to candidates (an ATS or scheduling tool that texts on a trigger, e.g.,
  "interview scheduled") until the application or intake form the candidate actually completed
  contains SMS-specific consent language naming the phone number — an "email me about my
  application" checkbox does not cover texting (internal doctrine — stricter than the federal
  minimum on purpose, to avoid a state-by-state or message-content-by-message-content analysis of
  which texts count as telemarketing). See
  [`~/.claude/knowledge/marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md)
  for the full TCPA mechanics (consent, quiet-hours defaults, revocation handling, and the separate
  A2P 10DLC carrier-registration layer).
- **Never use an automated or AI-generated voice for candidate calls.** A phone call placed by an
  autodialer or using a prerecorded/artificial voice to a candidate is subject to the TCPA's
  **prior-express-consent** requirement at minimum (47 CFR § 64.1200(a)(1)) — written consent is a
  telemarketing-specific requirement (§ (a)(2)), not a blanket rule for every autodialed/prerecorded
  call — and beyond the legal exposure, an AI or robotic voice calling a candidate about their own
  job application is a poor candidate experience that actively damages the employer's reputation.
  **Decision rule: candidate phone contact is always a real human, never an automated or AI voice
  system, regardless of what the TCPA would technically permit with consent** (internal doctrine —
  this KB bans automated/AI-voice candidate calls outright, a stricter-than-required policy choice,
  not a restatement of what the TCPA itself mandates).
- LinkedIn InMail or similar platform-native messaging is generally safe for outreach (subject to
  that platform's own terms of use) and is a reasonable channel for initial candidate sourcing
  outreach before an application exists.
- Keep a do-not-contact list and check it before any outreach attempt, and cap unsolicited
  follow-up attempts to a small, defined number before marking a non-responsive candidate/lead as
  closed — mirroring the same discipline the linked TCPA file applies to marketing contacts
  generally.

---

## Decision rules (summary)

1. Write the role's rubric — must-haves, preferred qualities, accepted evidence — before screening
   the first candidate. Score everyone against the same written rubric.
2. Keep fit tier and compliance clearance on two separate axes. Never blend them into one score.
3. A failed or incomplete check always resolves to "needs review" — never to a lower fit tier and
   never to an automatic pass.
4. Run the four-fifths adverse-impact check on any selection step applied at scale, once volume is
   meaningful.
5. Before using any AI/automated screening tool, confirm which jurisdiction-specific rules apply
   (NYC bias-audit-and-notice, Illinois AI-video-interview notice/consent/deletion, Colorado's
   currently-in-flux AI law, California's ADS recordkeeping) and get the vendor's own bias-audit
   evidence — never take a vendor's compliance claim on faith.
6. Use a structured interview with a pre-written scorecard for every candidate in a requisition; do
   not improvise per-candidate.
7. Never ask about a protected characteristic, salary history, or arrest (as opposed to conviction)
   record; never ask a disability-related question before an offer.
8. Text a candidate only with documented, channel-specific consent; never use an automated or AI
   voice to call a candidate.
9. Respond to every candidate, on a consistent timeline, including a real rejection notice — never
   silence.

## Anti-patterns

- Screening candidates against an unwritten or evolving standard, then reconstructing a rubric after
  the fact to justify the outcome.
- Letting a background-check timeout, an unreachable licensing database, or a missing data field
  silently downgrade or reject a candidate instead of flagging "needs review."
- Treating a vendor's AI screening tool as exempt from adverse-impact scrutiny because "the vendor
  says it's compliant."
- Asking about salary history, disability, or family status because "it came up naturally in
  conversation" — an informal setting does not make an unlawful inquiry lawful.
- Auto-texting candidates from a scheduling tool because the tool made it the default, without ever
  confirming the candidate gave SMS-specific consent.
- Using an AI or robotic voice to call a candidate to save staff time.
- Letting one candidate wait weeks for a response while another gets same-day replies, with no
  documented reason tied to the requisition's own process.

## Sources

- EEOC, "Employment Tests and Selection Procedures" — https://www.eeoc.gov/laws/guidance/employment-tests-and-selection-procedures (official, retrieved 2026-09-28)
- EEOC, "Questions and Answers to Clarify and Provide a Common Interpretation of the Uniform Guidelines on Employee Selection Procedures" — https://www.eeoc.gov/laws/guidance/questions-and-answers-clarify-and-provide-common-interpretation-uniform-guidelines (official, retrieved 2026-09-28)
- 29 CFR § 1607.4(D) (Uniform Guidelines, four-fifths rule, read directly) (official, retrieved 2026-09-28)
- EEOC, "Prohibited Employment Policies/Practices" — https://www.eeoc.gov/prohibited-employment-policiespractices (official, retrieved 2026-09-28)
- EEOC, "Job Applicants and the ADA" — https://www.eeoc.gov/laws/guidance/job-applicants-and-ada (official, retrieved 2026-09-28)
- Executive Order 14281, Federal Register 2025-07378 (disparate-impact enforcement deprioritization) (official, retrieved 2026-09-28)
- 42 U.S.C. § 2000e-2(k) (Title VII disparate-impact/business-necessity standard, still current law notwithstanding EO 14281's enforcement-priority shift) (official, retrieved 2026-09-28)
- NYC Department of Consumer and Worker Protection, "Automated Employment Decision Tools" — https://www.nyc.gov/site/dca/about/automated-employment-decision-tools.page (official, retrieved 2026-09-28)
- Illinois Artificial Intelligence Video Interview Act, 820 ILCS 42, read directly at ilga.gov (official, retrieved 2026-09-28)
- Illinois Human Rights Act, 775 ILCS 5/2-102(L), read directly at ilga.gov (official, retrieved 2026-09-28)
- Colorado SB26-189 (enacted, repealing and re-enacting SB24-205), enrolled bill summary at leg.colorado.gov, read directly (official, retrieved 2026-09-28)
- California Civil Rights Council automated-decision-system regulations — third-party law-firm summaries (Paul Hastings, Mayer Brown, Jackson Lewis), retrieved 2026-09-28; `UNVERIFIED (primary source unreachable: calcivilrights.ca.gov returned an error at retrieval time)` as to exact regulatory text
- 47 CFR § 64.1200 (TCPA consent requirements — (a)(1) prior express consent for non-telemarketing autodialed/prerecorded calls and texts, (a)(2) prior express written consent for telemarketing), read directly (official, retrieved 2026-09-28)
- Salary-history ban state list — third-party compliance-vendor tracker (HR Dive), retrieved 2026-09-28; `UNVERIFIED — seeded, needs derivation` as to the complete current list
- [`~/.claude/knowledge/marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md) — TCPA consent, quiet hours, and A2P 10DLC mechanics governing any candidate text message (internal cross-reference)
