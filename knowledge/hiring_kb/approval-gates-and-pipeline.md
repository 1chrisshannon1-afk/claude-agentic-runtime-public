# Hiring — approval gates, pipeline stages and safe job-board automation

**What this file answers:** which hiring actions always need the business owner's explicit
go-ahead, the stages every candidate moves through, and the conditions under which any automation
may touch the company's own job-board account. Everything here is portable doctrine for any small
US employer; company facts (roles, pay bands, boards used) live in the company's own hiring dossier.

This file is information, not legal advice; an employment attorney decides how a specific approval
process, pipeline stage, or job-board automation should be built or defended for a specific
company.

## 1. The six approval gates (never automated past) [KB-HGATE-001] (internal doctrine)

1. **Posting.** No job post goes live on any board, careers page or community without the owner's
   explicit go-ahead on the exact final text and pay wording.
2. **Candidate messages.** No outbound message of any kind (invite, follow-up, offer, decline) is
   sent without approval of that message or of a named template for that stage.
3. **Hire / no-hire / termination.** The agent surfaces evidence and a recommendation; only the
   owner decides, and the decision is recorded by the owner's hand.
4. **Pay deviations.** Any pay figure quoted outside the approved band or framing needs approval
   before it reaches a candidate.
5. **Job-board account reads (applicant retrieval).** Scoped to one job, time-limited, and
   re-verified at the moment it runs; never a standing "sync everything" grant.
6. **Discriminatory criteria.** Any screening criterion that could screen on a protected class
   (age, sex, race, national origin, disability, religion, pregnancy, and state-added classes) is
   a hard stop: the agent refuses to apply it and flags it to the owner.

## 2. Pipeline stages [KB-HGATE-002] (internal doctrine)

NEW → SCREENED (fit tier assigned; clearance pending) → CONTACTED → INTERVIEW SCHEDULED →
INTERVIEWED (scorecard complete) → REFERENCES → OFFER (owner-approved) → HIRED, with REJECTED and
WITHDRAWN as exits from any stage. Each move records who moved it, when and why. Service levels to
aim for: first response to a qualified applicant within 2 business days; a decision or status update
at least weekly while a candidate is active [KB-HGATE-003] (internal doctrine — a practice target,
not a legal rule).

## 3. Fit tier and clearance are separate [KB-HGATE-004] (internal doctrine)

A candidate's fit tier (strong match / worth interviewing / needs review / reject) comes only from
job-related criteria in the written rubric. Clearance (license, right to work, background check
where lawful) is a separate verdict. A lookup that fails, times out or returns nothing never moves
the fit tier; it leaves clearance as "needs review". See
`selection/screening-scoring-and-interviews.md`.

## 4. Pay wording [KB-HGATE-005] (internal doctrine)

Lead with the guaranteed floor. Never write "X or Y" pay (e.g. "$25/hr or 30% commission"), which
reads as the higher number and invites disputes; write "$25/hr guaranteed, plus …". Where a state
requires a pay range in postings, the range is the honest range the employer would pay. See
`posting/role-requirements-and-job-posts.md`.

## 5. Automation on the company's own job-board account [KB-HGATE-006] (internal doctrine)

Browser automation on a job board is the last resort, allowed only when all of these hold:
1. It is the company's own account, confirmed by the owner, never a personal or another company's
   account.
2. No documented API, feed or export covers the need (prefer the board's XML job feed and its own
   applicant export).
3. The owner approved this specific action for this specific job, with an expiry.
4. The account identity shown on screen is checked against the company's recorded identity before
   every run; a mismatch stops the run.
5. A CAPTCHA, anti-bot challenge or verification prompt is a hard stop; never retried or bypassed.
6. Rate limits are conservative and the board's terms of service are followed.
7. Applicant personal data is stored only where the company keeps hiring records, never pasted into
   chat, logs or reports; reports use counts and anonymised summaries.
8. Posting to boards with no partner API or feed (e.g. community classifieds) is done by the owner
   in the browser, never headless.

## 6. Outreach channels [KB-HGATE-007] (internal doctrine)

Email or the board's own messaging for first contact; phone calls only by a person; text messages
only to candidates who gave consent to be texted (see
`../marketing_kb/compliance/tcpa-a2p-10dlc.md`); never automated or AI-voice calls; a candidate who
asks not to be contacted is suppressed everywhere at once. Follow-ups: at most two unanswered
follow-ups per stage.

## Decision rules

- IF an action would publish, message a candidate, decide a hire, quote off-band pay or read an
  applicant list from a board → stop and prepare it for the owner's approval.
- IF a criterion could correlate with a protected class → do not apply it; flag it.
- IF a lookup fails → clearance "needs review"; fit tier unchanged.
- IF a board has a feed or export → use it before any browser step.

## Anti-patterns

Auto-posting; auto-rejecting on a failed background lookup; "or" pay wording; standing scraping
grants; texting candidates without consent; storing applicant data in chat or logs; letting the
agent pick the hire.

## Sources

Internal doctrine distilled from a production small-business hiring system's code and rules
(studied read-only 2026-09-28); legal specifics are in the posting/ and selection/ files, each
with its own cited sources.
