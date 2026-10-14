# Speed to Lead

Speed to lead is the elapsed time between a prospect submitting an inbound inquiry (form fill,
call, chat, SMS) and a human or system first responding to it. It is the single highest-leverage,
best-evidenced lever in this entire domain, and the one most commonly violated in practice.

## 1. The academic anchor: what the original research actually measured

**[KB-SALES-001]** The foundational study is Dr. James B. Oldroyd (then at MIT Sloan, later
Kellogg School of Management) in partnership with InsideSales.com, first published as the "Lead
Response Management Study" (~2007) and later formalized in *Harvard Business Review* as "The Short
Life of Online Sales Leads" (Oldroyd, McElheran, Elkington, HBR, 2011). The original study tracked
data from six companies, more than 15,000 leads, and over 100,000 call attempts; the later HBR
analysis expanded to roughly 1.25 million leads across 2,241 U.S. companies (third-party,
InsideSales/HBR summary, retrieved 2026-09-27 — the original MarketingSherpa-hosted PDF of the
underlying report is reachable at
`content.marketingsherpa.com/heap/DG07SFSlides/LeadResponseManagementReport.pdf`; the HBR article
itself sits behind HBR's paywall and was not independently re-read line-by-line for this claim —
treat the HBR headline finding below as third-party-reported until the original article text is
directly verified).

**[KB-SALES-002]** Reported findings, restated precisely because they are frequently garbled in
secondary sources:
- Contacting a lead within **5 minutes** made a firm roughly **100x more likely to make contact**,
  and **21x more likely to qualify** the lead, than waiting 30 minutes (third-party, InsideSales
  summary of the Oldroyd study, retrieved 2026-09-27).
- The later HBR-published analysis (1.25M leads, 2,241 firms) found that responding within one hour
  made a firm roughly **7x more likely to qualify** a lead than responding within the next hour
  after that (third-party, HBR summary, retrieved 2026-09-27).
- **Important methodological caveat, stated plainly:** this is vendor-adjacent data drawn from
  InsideSales' own customer base and call-tracking infrastructure, not a randomized controlled
  trial with a business population selected independently of the vendor. Treat the *direction and
  order of magnitude* (minutes matter enormously; the decay is front-loaded, not linear) as robust,
  and treat the *precise multipliers* (100x, 21x, 7x) as illustrative of that study's specific
  sample rather than a universal constant that reproduces exactly in every industry.

## 2. A separate, frequently-conflated claim: cold-call timing

**[KB-SALES-003]** A distinct, widely-repeated statistic — "calling a lead within one minute
increases conversion by 391% versus calling after two minutes" — traces to a different research
lineage (commonly attributed to a Velocify/Chili Piper-adjacent study) and could not be
independently traced to a primary, citable methodology during this research pass.
**UNVERIFIED (primary source unreachable: no citable original study/methodology page located;
every reachable source is a secondary blog restating the figure without attribution to a primary
report).** Do not cite the "391%" figure as if it were as well-evidenced as the Oldroyd/HBR
findings above; if it must be used, mark it exactly this way.

## 3. The current-state gap: how slow response actually is in practice today

**[KB-SALES-004]** A widely-cited 2024 study reported that of 1,000 companies analyzed, **63.5%
never responded** to a test inbound lead at all, and the subset that did respond took an average of
over **29 hours** (third-party, commonly attributed to a Drift/RevenueHero-lineage speed-to-lead
audit; retrieved 2026-09-27 via secondary aggregation — the original audit's own methodology page
was not independently reached during this pass. **UNVERIFIED (primary source unreachable) for the
exact 63.5%/29-hour figures** — cite as directionally consistent with the broader literature that
most companies respond far slower than the evidence says they should, not as a precisely-sourced
number.)

**[KB-SALES-005]** For home-services/contractor-adjacent lead flow specifically, third-party
industry analyses commonly report an average contractor response time in the **4–8 hour** range,
against the multi-hour-to-multi-day range documented broadly in the speed-to-lead literature.
**UNVERIFIED — seeded from aggregated third-party blog sources, needs a home-services-specific
primary study** before being cited as a precise number to any operator; use only as directional
evidence that the gap between "what evidence says to do" and "what actually happens" is large and
well-documented across verticals, home services included.

## 4. What a sales-ops agent actually designs from this evidence

**[KB-SALES-006] (internal doctrine)** The mechanism, not the multiplier, is what should drive the SLA design for any
company pack:
1. **Set a first-response SLA measured in minutes, not hours**, for every inbound channel (form,
   call, chat, SMS). The evidence above supports treating anything past the first hour as a steep,
   front-loaded decay — the exact target minute count is a business decision (staffing, after-hours
   coverage) informed by this evidence, not dictated by it.
2. **Escalate on miss, automatically.** A missed-SLA lead should trigger a defined escalation path
   (next available rep, a manager alert, an automated acknowledgment message) rather than silently
   aging in a queue — this is the mechanical answer to the finding that most non-response is not a
   deliberate choice but an absence of a forcing function.
3. **An automated acknowledgment is not a substitute for a human response**, but closes the
   window where a lead assumes they were ignored. "We got your request and someone will call you
   within [SLA]" sent instantly, followed by an actual human contact inside the SLA window, is the
   correct two-step pattern — never let the automated message be the only response.
4. **Measure time-to-first-touch as its own dashboard metric**, separate from time-to-close. A
   company can have a healthy overall conversion rate while still bleeding a specific, fixable
   percentage of leads to slow response — the two numbers answer different questions and both
   should be visible.

**Pass example:** A lead submits a contact form at 2:14 PM. An automated SMS acknowledgment sends
at 2:14 PM. A human calls at 2:22 PM. Both the acknowledgment and the human contact are logged with
timestamps against the original inquiry time.

**Reject example:** A lead submits a contact form. It sits in a shared inbox with no SLA, no
escalation rule, and no visibility into how old it is. Three days later someone notices it and
calls — this is the exact failure pattern [KB-SALES-004]/[KB-SALES-005] describe as typical, not
exceptional.

## Contractor bend

A small owner-operated residential remodeling business's "sales team" is very often one person — the owner — who is also
running a crew, standing on a roof, or driving between job sites when the lead comes in. The
mechanism above does not change for this buyer, but the *implementation* has to account for a
sales function that cannot staff a always-on call desk: an instant automated acknowledgment plus a
push/SMS alert the owner can act on from a truck cab is the realistic version of "respond in
minutes," not a call center. Where the owner genuinely cannot self-staff fast response even with
good tooling, the correct recommendation — ported as a mechanism, not a specific vendor — is a
answering service or virtual receptionist that can at minimum acknowledge and triage within the
SLA window while the owner calls back personally once free. Never recommend a cadence that assumes
a dedicated inside-sales rep exists when the company pack's own facts say it doesn't.
