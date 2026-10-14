# Posting — Index

Files in this directory cover the hiring lifecycle from "we need to hire someone" through "the post
is live and applicants are coming in": turning a hiring need into requirements, writing the job
post, and choosing where to publish it. They are company-agnostic and are read by the runtime's
`hiring-specialist` agent (or any agent/session doing hiring work for a small US business) alongside
the rest of `~/.claude/knowledge/hiring_kb/`.

**Co-founders and advisors are a different lane.** Recruiting a founding team or an advisor is
covered by `~/.claude/knowledge/venture_kb/recruiting/`, not here — this directory is about hiring
staff (employees and individual contract workers) into an existing business.

## Files

- **`role-requirements-and-job-posts.md`** — how to turn a hiring need into a must-have/nice-to-have
  requirements list (job-related and consistent with business necessity, or a legal credential —
  never a "BFOQ" claim, which is a separate, much narrower statutory defense), how to structure and write the
  job post itself (title, summary, duties, requirements, pay, benefits, schedule, location, how to
  apply), EEOC/discrimination-safe wording (age, sex, disability, national origin, "culture fit,"
  physical requirements), ADA essential-functions wording, the pay-wording doctrine ("lead with the
  guaranteed floor, never present pay as 'X or Y'"), and which US states currently require a pay
  range and benefits description in job postings (Colorado, California, Washington, New York
  detailed; others flagged as varying).
- **`job-boards-and-indeed.md`** — where to post by role type (trades, office, healthcare, tech);
  Indeed's specific mechanics (free vs. sponsored, job-posting quality/discrimination policy,
  Indeed Apply, screener questions, the XML/Job Sync feed, applicant retrieval and candidate
  messaging, the Glassdoor relationship); ZipRecruiter, LinkedIn (manual-only — its own Terms
  prohibit automation), Craigslist (manual-only — same reason), trade schools, unions, referral
  programs, and local job boards; what can safely be automated (drafting, feed updates once
  approved, sorting already-retrieved applicants) versus what must stay in the owner's hands
  (publishing, sending, any credentialed board-account action); and the approval gates that sit in
  front of every one of those actions.

## Reading order

Read `role-requirements-and-job-posts.md` first — it produces the actual post text and pay wording
that `job-boards-and-indeed.md` then assumes is already correct before covering where and how to
publish it.

## Claim-id namespace

Both files in this directory use the `[KB-HPOST-NNN]` claim-id namespace, numbered continuously
across the two files (role-requirements-and-job-posts.md: 001-039; job-boards-and-indeed.md:
040-075). A future file added to this directory should continue the sequence from 076.

## Citation discipline

Every numeric or behavioral claim in both files carries one of the six provenance tags defined in
`~/.claude/knowledge/marketing_kb/shared/citation-style.md` (official / third-party /
internal-measured / internal doctrine / UNVERIFIED — seeded / UNVERIFIED — primary source
unreachable), with a 2026-09-28 retrieval date on every dated tag. Both files draw portable doctrine
from a read-only study of an existing in-house hiring system's design — that doctrine is tagged
`(internal doctrine)` throughout and the source system, its company, and its files are never named,
per this KB's own writing brief.

## Legal-content disclaimer (applies to both files)

Everything in this directory is information, not legal advice. State and federal employment law
changes; several claims below are explicitly flagged UNVERIFIED or as needing a state-specific
lookup before a company relies on them for a real decision. An employment attorney should confirm
current requirements before a company finalizes a job-posting template, expands hiring into a new
state, or relies on any specific dollar figure, threshold, or penalty amount cited here.

## Known gaps as of this writing

- Screening and scoring live in `../selection/screening-scoring-and-interviews.md`; the approval
  gates and job-board automation conditions live in `../approval-gates-and-pipeline.md`.
- Several state pay-transparency figures (exact penalty schedules) and two vertical-board claims
  (a specific healthcare or tech niche board) are marked UNVERIFIED in the files above — treat them
  as prohibited-until-verified per this KB's citation-style rules, not as settled fact.
- Colorado's CDLE guidance is now read directly and cited as official in
  `role-requirements-and-job-posts.md` §6 (INFO #9A for EPEWA posting/notice mechanics, INFO #9D for
  the credit-history rule) — CDLE has split its old combined INFO #9 PDF into separate INFO #9A–#9E
  documents; the file's old INFO #9 URL is stale and no longer cited.
