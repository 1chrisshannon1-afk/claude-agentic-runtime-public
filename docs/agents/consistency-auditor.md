# consistency-auditor

`consistency-auditor` is the runtime's cross-surface truth agent: it catches "the help doc says X,
the backend does Y" before a customer does (`agents/consistency-auditor.md`, opening paragraph after frontmatter). Its unit of
work is the CONTRADICTION — two surfaces (repo docs, help docs, in-app copy, backend behavior,
marketing) asserting different things about the same product fact. It exists as a standing role
because content drift is silent and cumulative: a price changes in code, a marketing page doesn't
get updated, and nobody notices until a customer does the comparison themselves.

## Model & tools

- **Model:** `sonnet` (`agents/consistency-auditor.md` frontmatter's `model:` key) — not sanctioned-Opus. Cross-referencing
  claims across named surfaces against a dossier-stated authority map is closer to structured
  pattern-matching than open-ended judgment, so it runs at the cheaper tier.
- **Tools:** `Read, Grep, Glob, Bash` (`agents/consistency-auditor.md` frontmatter's `tools:` key) — read-only; it never
  edits any surface it audits.

## Cadence / trigger

Rides the daily job, `com.oversight.csa.daily.plist` (`StartCalendarInterval` fires every day at
05:10; confirmed loaded via `launchctl list`, 2026-08-30) — the `daily` label in CLAUDE.md §13's job
table. The job itself fires daily, but its dispatch of consistency-auditor does not: on Tue and Sat
only, the scheduled session dispatches consistency-auditor directly on its own "consistency" slot
instead of a rotation dimension (`schedules/prompts/daily_sweep.txt:21-24`); other days run
sentinel's health/logs/cost rotation instead (`agents/sentinel.md:136` explicitly notes the
consistency dimension is NOT sentinel's — the daily job prompt owns it directly). Each invocation
runs one audit "slice" (e.g. "pricing & tiers") named by the job prompt, and reports both the slice
it ran and the slice it recommends next, in the report's verdict line — the single place that first
line, including its DEGRADED form, is defined (`agents/consistency-auditor.md` § "Report shape",
item 1) — so slices
rotate rather than repeat.

## What it audits / judges

Its primer (`knowledge/consistency_auditor_primer.md`) grounds it in content-audit and docs-as-code
practice: the three-step **inventory → audit → reconcile** method (never skip straight to judgment
— build the complete surface list first, from Nielsen Norman Group's content-audit methodology);
single-source-of-truth architecture (each fact — a price, a tier name, a limit — mastered in
exactly one system, everything else a reference or render of it, which is what makes drift
structurally impossible rather than something a linter has to keep re-catching); terminology
management via a controlled vocabulary (Vale-style accept/reject term lists enforced in CI, not
just a style guide nobody checks against); docs-as-code QA (GitLab's production pipeline as the
concrete example — a redirect/deprecation-removal check that fails a build outright when docs
weren't regenerated alongside a source change that should have updated them); and drift-detection
techniques between UI copy, docs, and marketing (PR-triggered flagging when a settings/pricing
surface changes, and support-ticket "this didn't help" signal as a live drift indicator). Every
reported contradiction carries a mandatory shape: the exact claim from Surface A with its citation,
the exact claim from Surface B with its citation, an explicit authoritative-side call (or
"UNMAPPED," itself a finding — meaning the SSOT map has a gap), the specific dossier rule that
makes that side authoritative, a severity call (customer-visible money/legal facts highest), and a
fix direction (`agents/consistency-auditor.md` § "Finding shape (mandatory, no exceptions)"). A contradiction cited on only one side does
not count as a finding — it goes under UNVERIFIED observations instead.

## Grounding

Runtime discipline: `knowledge/consistency_auditor_primer.md`. Repo-local grounding:
`.claude/oversight/consistency-auditor.md` — this app's truth surfaces (docs site, in-app copy/FAQ
files, marketing source-of-truth and its build direction, pricing/tier definitions in code, known
terminology traps) and which surface is authoritative for each fact class. Missing dossier is a
declared DEGRADED state, named in the verdict line: the run may still inventory surfaces and record
apparent mismatches, but only under UNVERIFIED observations, with `Authoritative side: UNDETERMINED
— no dossier` and no Basis field — never an authoritative-side call, never a Fix direction, never a
Findings section. A DEGRADED run's deliverable is COVERAGE plus UNVERIFIED observations, nothing
more (`agents/consistency-auditor.md` § "Read FIRST", item 2), whose exact DEGRADED verdict-line
form is Report shape item 1 (`agents/consistency-auditor.md` § "Report shape", item 1).

## Boundaries — what it will NOT do

Never edits any surface it audits; never files issues directly (findings route through
board-steward's rules via the orchestrator); never pushes/PR/merges/deploys; never touches
production or drives a browser — a live-page check that only a browser can confirm is cited as
UNVERIFIED and left for product-qa. Its Bash grant is read-only — grep/read/count only, never a
file write, a `gh` state mutation, or a git write op. Silent sampling is forbidden — its report
states coverage as "surfaces read vs. not," explicitly (`agents/consistency-auditor.md` §
"Report shape", item 4, and § "Boundaries").

## How it fits with other oversight agents / the review boundary

consistency-auditor's lane is deliberately narrower than a general docs review: content/fact
consistency only, never usability or heuristic evaluation (that split is stated explicitly in its
primer's scope note). Where a finding requires confirming what a live page actually renders, it
hands that off to product-qa rather than guessing. Its findings, like every other agent's, funnel
through board-steward's one-issue-per-root-cause-cluster filing rule rather than becoming a fan-out
of individual tickets.

## Example invocation

Assigned the "pricing & tiers" slice, consistency-auditor finds that the marketing site lists a
$249/mo tier limit of 500 estimates while the in-app billing copy and the actual code constant both
say 750. It reports a Fact/Surface A/Surface B/Authoritative-side/Basis finding naming the code
constant as authoritative per the dossier's SSOT map, flags the marketing page as the side that
needs to change, and recommends "terminology" as the next slice to sweep.
