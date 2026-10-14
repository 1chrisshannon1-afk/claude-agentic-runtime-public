# Homeowner buyer psychology — the B2C persona counterpart

This file is the B2C mirror of [`contractor-buyer-psychology.md`](contractor-buyer-psychology.md) —
that file describes a trade-business owner as a *buyer of B2B software*; this file describes the
**homeowner** as a *buyer of a remodeling/renovation job* from one of this department's
`local_service` companies. Every seat working a `local_service` company's consumer-facing surface —
a landing page, a Google/Meta ad, a GBP post, a review-response, an estimate-follow-up email — reads
this file, which describes that company's own end customer. `contractor-buyer-psychology.md`
describes a different persona shape entirely (a B2B software buyer) and applies only when the
company being served is itself selling software to trade businesses, a separate question from what
this file covers.

This file is company-agnostic doctrine: no company facts, no company name, generic examples only.
A specific company's actual homeowner persona (their real average job value, their real service
area, their real brand voice) lives in that company's own `persona_file` (`company_schema.json`),
never here.

## Who this buyer is

**[KB-SHARED-101]** More than half of U.S. homeowners undertook a renovation project in the most
recent full year measured, with painting, outdoor living, bathroom remodels, and landscaping the
most common project types (third-party, Great Day Improvements "2026 State of American Home
Renovation & Improvement" report summary, retrieved 2026-09-27:
https://www.greatdayimprovements.com/home-advice/american-home-renovation-report/2026/). This is a
mainstream, majority behavior — not a niche buyer segment — so a `local_service` company's
addressable market is large, but also means the homeowner has almost certainly seen several
competitors' marketing before reaching this one.

**[KB-SHARED-102]** Roughly seven in ten homeowners fund renovations out of pocket (savings), making
self-funding more than three times as common as the next most common method, credit cards
(third-party, Block Renovation "How America Renovates 2026" report summary, retrieved 2026-09-27:
https://www.blockrenovation.com/guides/how-america-renovates-in-2026). **Practical translation:**
most of this buyer's project budget is a real, finite, already-saved sum they are protecting, not a
financed amount they can stretch by taking on debt mid-project — a price surprise mid-job lands
differently on this buyer than on a buyer who financed the whole project up front.

**[KB-SHARED-103]** Aesthetics and comfort/livability are cited as the most common project
motivators (19% and 18% respectively in one 2026 industry survey), significantly outweighing resale
value (8%) (third-party, Great Day Improvements 2026 report summary, retrieved 2026-09-27, same
source as [KB-SHARED-101] — survey methodology and sample size not independently confirmed here;
treat as directional). **Practical translation:** the dominant motivator is "I want to enjoy living
here," not "I need to flip this for a return" — copy that leads with resale-value ROI math is
answering a question most of this buyer segment isn't asking.

## The research-and-trust gauntlet

**[KB-SHARED-104]** Homeowners are reported to be researching contractors earlier and more
thoroughly than before — evaluating online reviews, comparing credentials, assessing project
photos, and seeking transparency in pricing and timelines, and "quietly evaluating" a contractor
before ever making contact (third-party, improveit360 "Major Shifts in How Homeowners Choose
Contractors" summary, retrieved 2026-09-27:
https://www.improveit360.com/blog/homeowner-behavior-shifts-2026/ — a vendor blog in the home-services
software space; treat as directional, not an independently audited survey). **Practical
translation:** by the time this homeowner fills out a contact form, they have typically already
looked at the reviews, the photos, and the price range — the marketing surface's job at that point
is to confirm what they already suspect (this looks legitimate and specific), not to persuade them
from zero.

**[KB-SHARED-105]** In the same reporting, 72% of homeowners said they would pay up to 10% more for
a contractor with a stronger service reputation (third-party, improveit360, same source and caveat
as [KB-SHARED-104], retrieved 2026-09-27). **Practical translation:** reputation (real reviews, real
response time, real before/afters) is not a soft nice-to-have next to price — for a meaningful share
of this buyer segment it is worth real money, which is the justification for the review-acquisition
and reputation-management discipline in `reputation/` and the review-reply doctrine that this
department treats as a T2-review tier action (see `autonomy-tiers.md`), not an afterthought.

## Five behavioral facts, translated for marketing surfaces

**1. The homeowner is not the GC.** They do not read a spec sheet, do not compare API integrations,
and are not evaluating this as a professional tool — they are hiring a person/company to do
physical work inside their home, which is a trust decision closer to hiring a babysitter or a
surgeon than to buying software. Every claim should answer "will this person do good, honest work
in my house" before it answers "is this the cheapest option."

**2. Price is read as a range, not a number, until a real estimate exists.** A homeowner researching
online almost never has a firm budget number yet (see [KB-SHARED-102] — they know roughly what
they've saved, not what the job costs). Marketing copy that promises an exact price before a real
site visit/estimate reads as either naive or bait-and-switch to a homeowner who has shopped before;
a range framed around real, cited scope ("a mid-range bathroom remodel typically runs $X-$Y for a
project this size" sourced to a real published cost book, never invented) is more credible than a
suspiciously precise single number.

**3. Photos and specificity beat adjectives, exactly as with the GC buyer.** "Quality craftsmanship"
and "trusted professionals" are ignorable filler to a homeowner who has read the same phrase on
every competitor's site. A real project photo with a real (consented, see below) before/after, a
real completion timeframe, and a real neighborhood/project-type match to their own situation reads
as evidence; a generic adjective reads as nothing.

**4. Trust is fragile and front-loaded on response time.** A homeowner who fills out a contact form
or calls is often comparing 3+ contractors simultaneously; the first one to respond with a real,
specific answer (not a generic auto-reply) has a structural advantage that erodes with every hour of
delay. This is the reason `sales/speed-to-lead.md` exists as its own doctrine file — the marketing
surface's promise ("we respond within X") is only credible if the operating process behind it
actually delivers, so no seat should promise a response time faster than what the company's actual
process can sustain.

**5. A homeowner in an active renovation is stressed, disruptive-to-daily-life, and reading
everything defensively.** Once a job is underway, the homeowner's inbox/phone is a source of
anxiety (is this going over budget, is this going to take longer than promised), not curiosity. Any
homeowner-facing communication *during* an active job (a status update, a change-order notice, a
billing email) should be calm, specific, and free of marketing tone — this is a different register
than acquisition copy, and a seat drafting mid-project communication should never reuse acquisition
copy's persuasive framing on a customer who has already bought and is now living inside the
disruption.

## Before/after photos and testimonials — the compliance-adjacent trust surface

This is the single highest-leverage, highest-risk content type for a `local_service` company, so it
gets its own subsection here rather than being left to `reputation/` alone.

**[KB-SHARED-106]** The FTC's Endorsement Guides (16 CFR Part 255) require that when an endorsement
features an atypical or exceptional result, the advertiser must clearly and conspicuously disclose
the generally expected results for someone in the depicted circumstances, unless the advertiser has
adequate substantiation that the endorser's experience is what consumers will generally achieve —
the older "results not typical" disclaimer safe harbor was removed in the Guides' 2023 revision
(official, FTC "FTC's Endorsement Guides: What People Are Asking," retrieved 2026-09-27:
https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking).
**Practical translation for a before/after photo:** if the photo shows an unusually dramatic
transformation (e.g. a full gut-and-rebuild finished in an unusually short timeframe), the caption
or surrounding copy must not imply that timeframe or outcome is what every customer should expect
— either caption it honestly ("this project's scope and timeline") or add the generally-expected-
range disclosure. See `department-anti-patterns.md` item 3 for the parallel rule against unverified
accuracy claims.

**[KB-SHARED-107]** The FTC's Rule on the Use of Consumer Reviews and Testimonials (16 CFR Part 465)
took effect October 21, 2024, and bans: writing, selling, or buying fake reviews; an undisclosed
company-insider review; suppressing genuine negative reviews through false legal threats,
intimidation, or physical threats (responding publicly to a negative review remains fine); and
**review gating** — soliciting reviews in a way that conditions an incentive on the review being
positive, or that only solicits reviews from customers expected to be satisfied while suppressing
solicitation from others (official, FTC "Consumer Reviews and Testimonials Rule: Questions and
Answers," retrieved 2026-09-27:
https://www.ftc.gov/business-guidance/resources/consumer-reviews-testimonials-rule-questions-answers).
**Practical translation:** a review-request campaign must ask every recent customer, not just the
ones the company believes are happy, and any review-request incentive (a discount, a gift card) must
never be framed as conditional on a positive review — see `compliance/review-gating.md` for the
full operational rule this KB addition owns.

**[KB-SHARED-108]** A contractor generally needs the homeowner's written permission (a photo
release) before using project photos — including before/after photos identifying the home, its
location, or the homeowner by name — for commercial marketing purposes, because an individual holds
a right of publicity over commercial use of their name, image, and likeness (third-party, general
photo-release-form guidance aggregated from multiple legal-template providers — HFS Financial "How
to Get Permission to Use Images for Your Contractor Business," Format.com "The Ultimate Guide to
Photo Release Forms," retrieved 2026-09-27; this is general commercial-photography practice, not a
home-services-specific regulation, and state law on right-of-publicity varies — treat the *need for
written consent* as the governing practice and the exact legal mechanics as UNVERIFIED per
jurisdiction until a specific state's statute is checked). **Practical translation:** no seat
proposes using a real customer's before/after photo, name, address, or identifying project detail
in marketing without a documented release on file for that specific project; the standard, low-
friction practice is to have the release signed at project closeout, while satisfaction is highest
and the ask is easiest.

## Seasonal and trust framing (see also `home-services-playbooks.md`)

A homeowner's stage in the research-and-trust gauntlet interacts with seasonality: a homeowner
researching in the off-season (see `home-services-playbooks.md` §Seasonality) is often earlier in
the decision process and more price-sensitive to a first-contact response; a homeowner researching
during peak season is often further along and more sensitive to availability/timeline than to price,
because they have already accepted that peak-season contractors are in demand. A seat drafting
seasonal ad copy or landing-page framing should adjust which of the five behavioral facts above it
leans on accordingly — off-season copy can afford to spend more words on trust-building detail;
peak-season copy should front-load availability and speed-to-response.

## Contractor bend

There is no further "bend" section here in the sense the SEO/paid-acquisition domains use it — this
entire file already **is** the bend, translating generic B2C consumer-marketing doctrine for the
home-services homeowner specifically. Where a channel seat's own doctrine (a generic conversion-rate
playbook, a generic email-marketing best-practice) assumes an anonymous e-commerce consumer, this
file is what a `local_service` seat translates through instead: a real name, a real address (subject
to consent, [KB-SHARED-108]), a real budget range grounded in a real cost book, and copy that never
promises a result this specific company hasn't actually delivered and can't honestly generalize.
