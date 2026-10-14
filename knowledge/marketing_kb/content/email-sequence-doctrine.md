# Email Sequence Doctrine

Structural rules governing subject lines, CTAs, sequence architecture, and claim-checking for
lifecycle email — company-agnostic. For any specific company's actual live sequences (files,
triggers, exit conditions, inventoried defects), see that company's own marketing pack/dossier —
this file is doctrine only, never a live inventory of any one company's shipped copy.

> **Funnel-shape caveat.** Whether a company runs a free-trial-based conversion funnel, a
> card-at-signup-plus-money-back-guarantee funnel, or something else entirely is a per-company,
> per-offer decision that can change on its own ruling timeline. Before building or judging any
> sequence against this file's taxonomy (a "trial signup" trigger, a "trial expiry" exit, a
> win-back-from-trial-expiry state), confirm the current company's actual, currently-live offer
> shape from its own pricing/positioning source of truth — do not assume a trial funnel exists just
> because this file's examples reference one, and do not assume a company's offer shape is stable
> across time without checking its current ruling status.

## 1. Sequence inventory — read from the company's own pack, not this file

A company's actual live email sequences (which files exist, their length, trigger, and exit
condition, and any inventoried live-copy defects) live in that company's own marketing pack or
dossier — never in this shared runtime file. When auditing a company's sequences, build (or update)
that company's own inventory there, following the shape below as a template:

| File | Length | Trigger | Exit condition |
|---|---|---|---|
| (example) welcome/onboarding sequence | N emails over N days | Signup / trial start | Trial expiry, or conversion, or a fixed day count |
| (example) nurture sequence | N emails over N days | Lead opts in, no purchase/trial yet | User converts or starts a trial → nurture suppressed |
| (example) win-back sequence | N emails over N days | Trial/offer ends without conversion | User converts → remaining win-back emails suppressed |

**Recurring defect classes to check for in any company's live sequences** (see `ANTI-PATTERNS.md`
for the mechanisms): unmeasured speed claims that shipped before or survived past a positioning
ruling; unsourced customer-proof dollar/percentage figures used as testimonials. When found, file
as a tracked issue per that company's own process discipline — this knowledge-base file does not
itself patch any company's email files.

## 2. Sequence structure principles (internal doctrine — mechanism)

**Welcome/Day-0 email fires immediately, never delayed.** Welcome emails carry the highest open
rate of any email type in most lifecycle-email programs — commonly cited around **50-60% open
rate, UNVERIFIED, re-derive and cite at time of use** — not having one, or delaying it, wastes the
moment of highest intent. (Internal doctrine — mechanism, a structural claim about behavior
patterns, not a dollar/CPA number, so it ports across companies as-is; the specific percentage is a
commonly-cited figure requiring its own citation before use, same posture as the $36-42/$1 figure
in §3 below.)

**Automation lifecycle-flow priorities (P0/P1/P2 ladder), portable mechanism:**

| Flow | Priority | Notes |
|---|---|---|
| Welcome series | P0 | Fires immediately on signup/trial start, never suppressed |
| Lead nurture (multi-touch for not-yet-ready leads) | P1 | For leads who opted in but haven't converted |
| Re-engagement / win-back | P1 | For users whose trial/offer window ended without conversion |
| Post-purchase/post-service follow-up | P1 | Often a gap — check whether the current company has built this |
| Abandoned action recovery | P0 for transactional flows | E.g. started-then-went-idle mid-flow re-engagement, beyond scheduled day-N emails |

**Citation:** internal doctrine — a standard lifecycle-flow priority ladder, mechanism-only, no
dollar figures attached; re-derive per company which flows actually exist and which are gaps.

## 3. Benchmarks — general, re-derive per vertical

**A commonly-cited figure not to port as fact without checking its source:** claims like "email is
the highest-ROI digital marketing channel ($36-42 return per $1 spent)" circulate widely as general
marketing doctrine, not tied to any one vertical — treat any such figure as a third-party number
requiring its own citation before use; do not assert it without checking its original source at
time of use.

**General cross-industry benchmarks (third-party, retrieved 2026-09-05):**

| Metric | Healthy | Warning | Critical | Source |
|---|---|---|---|---|
| Open rate (general, cross-industry average ~19-21%) | >20-25% | 15-20% | <15% | WebFX / Klaviyo / Brevo 2026 benchmark roundups, retrieved 2026-09-05 |
| Click-through rate (of sends, cross-industry average ~2.3-2.5%) | >2.5-3.5% | 1-2.5% | <1% | Same sources, retrieved 2026-09-05 |
| Hard bounce rate | <0.5% | 0.5-2% | >2% | (internal doctrine) — generic ESP hygiene threshold, not vertical-specific; a technical/deliverability fact, not a marketing-performance claim |
| Spam complaint rate | <0.05% (internal doctrine — stricter-than-enforcement target) | 0.05-0.10% | ≥0.10% (Google's enforcement ceiling) | Google's bulk-sender guidelines: keep spam rate below 0.10% and never reach 0.30% (support.google.com/a/answer/81126, retrieved 2026-09-27); Yahoo's Sender Hub best practices state the same complaint-rate discipline for bulk senders (senders.yahooinc.com/best-practices/, retrieved 2026-09-27) |

**Note on the spam-complaint row:** Google's own bulk-sender guideline states an enforcement
floor — stay below 0.10%, never reach 0.30% — it is not itself a "healthy" target. This table sets
a stricter internal-doctrine "healthy" band (<0.05%) so that reaching Google's own ceiling reads as
already-critical, not merely healthy.

**UNVERIFIED — seeded, needs vertical-specific derivation:** no home-services/contractor-vertical
or other specific-vertical open/click-rate benchmark was found in this session's web research. The
cross-industry averages above are the best available substitute; do not present them as
vertical-specific in a report or in doctrine used for grading a real campaign's performance. If a
future session finds a Mailchimp/Constant Contact/HubSpot industry-segmented vertical row relevant
to the company being audited, replace this table and cite it.

## 4. Authentication basics (external, official-adjacent, mechanism + facts both port cleanly)

Email authentication is infrastructure, not marketing copy — it ports as fact regardless of
vertical, since SPF/DKIM/DMARC mechanics don't vary by industry or by company:

- **SPF, DKIM, DMARC** should all be configured; DMARC policy should progress toward
  `p=quarantine` or `p=reject`, never left at `p=none` long-term.
- Google and Yahoo enforce DMARC as a bulk-sender requirement, effective February 2024, ongoing.
- **Citation:** Google's email sender guidelines (support.google.com/a/answer/81126, retrieved
  2026-09-27) and Yahoo's Sender Hub best practices (senders.yahooinc.com/best-practices/, retrieved
  2026-09-27) — both require SPF, DKIM, and DMARC for bulk senders as of the Feb-2024 requirement
  date. This is
  deliverability-infrastructure knowledge, not a vertical-specific marketing number, so it ports
  directly across companies.

This is operational/technical doctrine, not something a content-strategist seat typically edits —
but a content seat should know it exists and flag it to whoever owns that company's operator-input
surface if a sequence's deliverability looks compromised (very low open rates across the board, in
a way that suggests an infrastructure problem rather than a copy problem).

## 5. Subject line and CTA rules

- **One primary CTA per email, prominent, button not bare text link** — deliverability/design
  mechanism, vertical-agnostic and company-agnostic.
- **Subject lines under ~50 characters, no spam-trigger words** (ALL CAPS, "FREE," "ACT NOW") —
  this is an inbox-provider filtering mechanic, not a marketing-persuasion claim, so it ports as
  fact regardless of company.
- **Every claim in a subject line or body passes the `ANTI-PATTERNS.md` check before shipping** —
  subject lines are a recurring place an unmeasured speed claim or similar defect ships; they are
  copy like any other copy and get the same gate.
- **A/B subject-line testing** is sound practice — mechanism from general email doctrine, not
  vertical- or company-specific.

## Per-vertical bend (example: contractor/home-services buyer)

A dental patient reads email between appointments on a desk computer or a phone in a waiting room.
A contractor/home-services buyer reads email on a phone, between jobs, often one-handed, often in a
truck cab. Two concrete adjustments for that kind of buyer:

- **Front-load the value in the subject line and preview text** — this reader will not open on
  curiosity alone as reliably as a nurtured SaaS lead; they need to see the concrete payoff
  (a real number, a real trade term) before they'll tap.
- **Every email should survive being read in 10 seconds.** If the HTML template requires
  scrolling through three sections before the CTA, that's a structural mismatch with how this
  buyer actually reads mail. Prefer one clear message, one clear action, per send — hold any
  company's sequences to this same discipline rather than adding more sections "since we're
  already in there."
