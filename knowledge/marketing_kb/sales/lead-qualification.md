# Lead Qualification

Qualification is the discipline of deciding, with a repeatable framework rather than gut feel,
whether a lead is worth continued sales effort right now — and if so, how it should be routed and
prioritized. Two framework families dominate: BANT (simple, transactional) and
MEDDIC/MEDDPICC (complex, multi-stakeholder B2B).

## 1. BANT — the simple, transactional framework

**[KB-SALES-010]** BANT stands for **B**udget, **A**uthority, **N**eed, **T**imeline. It is widely
attributed to IBM, developed to help sales reps quickly triage viable deals from tire-kickers; the
exact decade of origin is inconsistently reported across secondary sources (some cite the 1950s,
others the 1960s), and no single primary IBM document stating the framework's own origin date was
located during this research pass. **UNVERIFIED (primary source unreachable: no IBM-authored
original document found; treat "IBM, mid-20th century" as the consistent thread across third-party
sources, retrieved 2026-09-27, and the specific decade as unconfirmed.)**

**[KB-SALES-011] (internal doctrine)** The four criteria, applied as qualifying questions:
- **Budget** — does the prospect have, or can they access, money allocated or allocatable for this
  category of purchase?
- **Authority** — is the person you're talking to the decision-maker, an influencer, or someone
  with no purchasing say at all?
- **Need** — does the prospect have a genuine, articulated problem this offering solves, versus
  idle browsing?
- **Timeline** — is there a real, near-term event or deadline driving urgency, or is this
  someday/maybe?

**[KB-SALES-012]** BANT's well-documented weakness (third-party, widely repeated across modern
sales-methodology commentary, retrieved 2026-09-27): it front-loads "budget" and "authority" as
gating questions asked too early in a conversation, which can kill a genuinely qualified lead who
hasn't yet built internal budget/authority clarity, and it was designed for a single-decision-maker,
transactional sale — it does not model multi-stakeholder buying committees well. Modern usage
generally treats BANT as a lightweight *inbound-lead triage* filter (fast, cheap, good for
high-volume/low-complexity pipelines) rather than the qualification framework for a complex,
multi-stakeholder enterprise deal — that's what MEDDIC/MEDDPICC is for.

## 2. MEDDIC / MEDDPICC — the complex-deal framework

**[KB-SALES-013]** MEDDIC was created inside PTC (a software company) in 1996 by Dick Dunkel
(official/primary, MEDDICC.com — the methodology's own steward site — retrieved 2026-09-27). Under
this methodology, PTC's sales grew from roughly $300 million to $1 billion in about four years
(third-party, reported alongside the methodology's own origin story; treat this specific revenue
claim as the vendor's own historical narrative about its founding success, not independently
audited).

**[KB-SALES-014]** MEDDPICC extends MEDDIC with a "Paper Process" step. Full letter-by-letter
meaning (official, MEDDICC.com, retrieved 2026-09-27):
- **M**etrics — the quantifiable measures of value the solution can provide.
- **E**conomic Buyer — the person with overall authority in the buying decision (not necessarily
  the person you're talking to).
- **D**ecision Criteria — the principles/guidelines/requirements the organization uses to decide.
- **D**ecision Process — the actual steps the buyer will take to reach a decision.
- **P**aper Process — the steps *after* the decision, from verbal yes to signed contract (legal
  review, procurement, security review) — frequently the step that silently kills a deal everyone
  thought was closed.
- **I**mplicate the Pain — has the pain been surfaced and connected concretely to a cost of
  inaction, not just acknowledged in the abstract?
- **C**hampion — a person inside the buying organization with real power, influence, and
  credibility who actively wants you to win (distinct from merely a friendly contact).
- **C**ompetition — every real alternative, including "do nothing" and "build it ourselves," not
  only named competitor products.

**[KB-SALES-015]** MEDDIC/MEDDPICC's own guidance on when it applies: it fits mid-market and
enterprise B2B sales with complex processes, multiple stakeholders, and a defined buying journey
(official, MEDDICC.com, retrieved 2026-09-27); a commonly cited practical sweet spot is deals above
roughly $100K with 3+ month sales cycles and formal procurement (third-party, retrieved 2026-09-27
— treat the specific dollar/month thresholds as illustrative guidance from methodology
practitioners, not a hard rule).

## 3. Choosing between them, and what a qualification score should drive

**[KB-SALES-016] (internal doctrine)** The mechanism, applicable regardless of which acronym a company pack adopts:
- **High-volume, low-average-deal-size, single-decision-maker pipelines** (most inbound
  consumer/SMB lead flow) are well served by a lightweight BANT-style triage — a handful of
  qualifying questions that route a lead to "pursue now," "nurture," or "disqualify" fast, without
  the overhead of tracking eight separate MEDDPICC fields on every lead.
- **Lower-volume, higher-average-deal-size, multi-stakeholder pipelines** (enterprise software,
  large B2B contracts) benefit from MEDDIC/MEDDPICC's fuller model, because the actual failure
  modes at that deal size (no real economic buyer identified, no champion, an undiscovered paper
  process step) are exactly what BANT's four questions don't surface.
- **A qualification score is only useful if it changes what happens next.** A framework tracked in
  a CRM field but never used to change routing, prioritization, or forecast confidence is
  bookkeeping, not qualification — see `crm-hygiene.md` for the discipline that keeps a
  qualification field trustworthy rather than stale.
- **Never gate a lead's very first response on full qualification.** Qualification depth should
  scale with the conversation, not block the initial fast response the [KB-SALES-006] speed-to-lead
  evidence demands — a 2-question triage before the first callback, deeper qualification once a
  human is actually engaged.

**Pass example:** An inbound lead answers three fast triage questions (project type, rough budget
range, timeline) in an automated intake form before a human ever calls; the human then spends the
qualification call on need and decision process, not re-asking what's already known.

**Reject example:** A lead sits unrouted for days while a rep tries to fully MEDDPICC-qualify a
$400 transactional lead before making first contact — the framework's overhead has become the
bottleneck the speed-to-lead evidence warns against.

## Contractor bend

A residential GC's sales cycle is almost always closer to the BANT end of the spectrum than the
MEDDPICC end: one household, one or two decision-makers (often a couple deciding jointly), a
project-specific budget, and a timeline driven by something concrete (a leak, a planned move, a
seasonal window) rather than a multi-department procurement process. Full MEDDPICC tracking is
usually overkill and will slow the business down without adding real signal. What *does* port from
MEDDPICC's structure, even at this deal size: **Implicate the Pain** (has the homeowner actually
connected their problem to a cost of waiting — a leak that's getting worse, a kitchen they're
embarrassed to host in — versus a vague "someday" renovation fantasy) and **Decision Process** (is
this homeowner deciding alone, or do they need to bring a spouse/partner into a second
conversation before signing — missing this is a common, avoidable reason a seemingly-qualified lead
goes quiet). Both are cheap to ask about on the very first call and meaningfully improve
prioritization without adopting the full enterprise framework.
