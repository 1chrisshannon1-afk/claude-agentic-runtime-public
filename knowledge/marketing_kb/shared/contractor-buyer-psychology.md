# Contractor buyer psychology — a B2B software-buyer persona shape

This is one of several shared persona-file shapes every GTM seat reads before writing anything for a
company whose customer is a **B2B software buyer** — an ad, a landing page, a pricing table, an
email, a piece of content. It exists because most marketing doctrine is written for a tech-literate
SaaS buyer who reads a comparison page, checks a review site, starts a free trial, and self-serves
onboarding. **A trade-business software buyer is often not that buyer**, and doctrine applied without
translation will misfire.

This file describes a **reusable archetype**, not any one company's actual customer — a worked
example (a general contractor buying estimating/project software) that demonstrates the shape a real
persona file should take. **A specific company's own actual buyer — their real revenue band, their
real stated pricing objections, their real never-a-desktop-user habits — lives in that company's own
`persona_file`** (`company_schema.json`), sourced to that company's own product-positioning doc or
its own market research, never assumed to be identical to the archetype below. Author that file
before or alongside a company's pack, per `company-pack-authoring.md` §2.

## Who this kind of buyer typically is

**The worked archetype: an owner-operator running a real multi-crew trade business** (a residential
remodeling general contractor is the example used throughout this file) — a real, somewhat
sophisticated small business, not a hobbyist and not a one-truck handyman, but one that still runs
day-to-day from a truck, a phone, and a spreadsheet rather than a SaaS stack (internal doctrine —
illustrative archetype, not a measured market figure, retrieved 2026-09-27). **A real company's own version of this
archetype — including its actual revenue band — should be sourced to that company's own
product-positioning doc and its operator's own reported buying behavior** — a founder's own
experience of what they themselves would and wouldn't pay for their own trade is often the single
best available market data point for a pre-launch or early-stage B2B product in this space, worth
stating explicitly and dating in that company's own persona file rather than assumed generically.

The bend below is about *how this kind of buyer buys*, not about talking down to them — an
owner-operator running real volume in a real trade is not a hobbyist, even if their day-to-day tools
look informal.

## Five behavioral facts about this kind of buyer

**1. Phone-first, mobile-first, always.** More than half of contractors with a smartphone (53%)
use it in the purchase decision-making process — researching brands, comparing prices, checking
reviews — and 56% use it to photograph a job site to reference while shopping for materials
(third-party, PRNewswire/Contractor magazine survey summary, retrieved 2026-09-05). This buyer is
not sitting at a desktop reading a comparison matrix. Every page, every proposal, every checkout
flow this department ships must work — and read well — on a phone screen, one-handed, possibly
between job-site tasks.

**2. In a truck, not at a desk — attention is short and interruptible.** This buyer's day is
customer service, estimating, scheduling, and supervision, often all five roles at once (the same
research-fatigue dynamic documented for small-business owners generally: a 2026 survey found the
average small business owner fills five roles daily — customer service 54%, marketer 44%,
bookkeeper 43%, and more, third-party, Klipy small-business-owner-burnout survey, retrieved
2026-09-05 — general small-business-owner population, not contractor-specific; treat as
directional). Copy must front-load the point. A hero that takes three scrolls to state what the
product does has already lost this buyer.

**3. Burned by software before — real, quantified skepticism.** This is not a rhetorical flourish;
it is a documented pattern. 92% of software buyers report research fatigue and 29% report being
completely burned out by the software-evaluation process, with 72% having delayed a purchase
because research felt too complex (third-party, SoftwareFinder "The Burnout Behind the Purchase,"
retrieved 2026-09-05 — general SMB software-buyer population, not contractor-specific; treat as
directional). Construction-specific adoption resistance compounds this: a 2024 AGC survey found 47%
of contractors cite getting their own people to actually use new technology as their single biggest
adoption challenge — ahead of cost or integration (third-party, cited via iBeam "Why Construction
Software Adoption Fails," retrieved 2026-09-05). **Practical translation: this kind of buyer has
often already tried at least one tool that overpromised, under-delivered, or that their crew refused
to use. Every claim this department makes on their behalf is being read against that memory, not a
blank slate.**

**4. Price-sensitive on subscription, not price-insensitive overall.** A monthly software line-item
often reads as *overhead* to this kind of buyer, and overhead gets cut — this is not the same as
"cheap": it is the standing observation that the identical dollar amount, framed as a monthly
subscription cost, reads very differently than the same amount framed as a tool that pays for itself
on the job (internal doctrine, retrieved 2026-09-27). A company's own real pricing objections and
real willingness-to-pay (if known — from the operator's own experience buying similar tools, or from
real prospect conversations) are that company's own fact for its own persona file; the *mechanism*
generalizes: every seat's pricing/value copy for this kind of buyer leads with the job-level payoff,
never the monthly fee.

**5. Trust is earned by specificity, not polish.** A generically slick SaaS landing page can read
as *more* suspicious to a buyer who has been burned before — polish without substance is exactly
what a demo-ware competitor looks like (internal doctrine, retrieved 2026-09-27). This buyer trusts
a named citation (a real, checkable source
for a claim), a real concrete number ("typically N minutes"), and a concrete artifact (a real
output example) more than an adjective ("powerful," "seamless," "revolutionary"). Every seat should
prefer showing the real thing over describing it.

## What this is NOT

This kind of buyer is not unsophisticated, not anti-technology on principle (they use a smartphone
constantly, per fact 1), and not a bad-faith or irrational actor. Treating them as slow or
technophobic is itself a failure mode — see `department-anti-patterns.md`. The correct read is:
time-poor, skepticism-earned, mobile-native, and allergic to subscription-shaped overhead that
doesn't visibly pay for a specific job.

## Contractor bend

This entire file *is* the contractor bend — it exists so every other file in this corpus doesn't
have to re-derive it. When a channel seat's own doctrine (a generic ads-discipline reference, general
SEO best practice, generic conversion-rate-optimization advice) assumes a desktop-browsing,
comparison-shopping, tech-fluent SaaS buyer, the seat's job is to translate through this file (or
that company's own more specific persona file) before shipping: shorten the page, move the price
frame to job-level payoff, lead with a concrete number over an adjective, and design for a thumb on a
truck dashboard, not a mouse at a desk.
