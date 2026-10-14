# LinkedIn B2B doctrine — for a B2B/SaaS company's own marketing (not a contractor's own presence)

**Scope note, read first:** LinkedIn is a B2B/software-buyer platform. It is the right channel for
a B2B SaaS company selling into the home-services/contractor vertical to run its own SaaS marketing
(reaching remodeling-company owners and operators in their capacity as *software buyers*, GC
associations, industry partners, potential integration partners), and it is generally **not**
where an individual contractor customer's own home-services marketing lives (see
`shared/contractor-buyer-psychology.md` — this buyer is phone-first and does
not run a LinkedIn content strategy for their own trade business). Keep this distinction explicit
in any doctrine or plan that cites this file: "LinkedIn doctrine" in this corpus means a B2B SaaS
company's own GTM presence, not a template to hand a contractor customer. The dwell-time, Creator
Mode, and Newsletter mechanics below apply to any B2B company's LinkedIn presence, regardless of
vertical; the home-services/contractor-buyer framing throughout this file is the vertical-specific
part, written for a B2B SaaS company that sells into the home-services/contractor vertical
specifically.

## Dwell time — LinkedIn's own named ranking signal

LinkedIn's own engineering team has published, in detail, how it measures and uses "dwell time" in
feed ranking:

> Dwell time is measured two ways: "dwell time 'on the feed,'" which "starts measuring when at
> least half of a feed update is visible" as a member scrolls, and "dwell time 'after the click,'"
> the time spent on content after clicking into an update. [KB-SOCIAL-030] (official, LinkedIn
> Engineering Blog, "Understanding dwell time to improve LinkedIn feed ranking," published
> 2020-05-12, retrieved 2026-09-27:
> https://www.linkedin.com/blog/engineering/feed/understanding-feed-dwell-time)

LinkedIn uses dwell-time signal in a "P(skip)" model that predicts the probability a member will
skip a given update, and reduces that update's ranking score in proportion to the predicted skip
likelihood [KB-SOCIAL-031] (official, same source, retrieved 2026-09-27).

**Operational read:** a post whose first line does not earn a pause (a strong hook, a real number,
a genuine before/after claim) gets skipped, and a skip actively suppresses that post's future
reach via the P(skip) model — this is a named mechanism, not a guess. Never open a LinkedIn post
with a generic throat-clearing line ("Excited to share..."); the opening line is doing real
ranking work.

**What is NOT independently confirmed here:** the specific numeric claim that "personal profiles
get 5-8x the reach of company pages" circulating in third-party 2026 LinkedIn-strategy content
[KB-SOCIAL-032] (third-party, multiple 2026 LinkedIn-algorithm explainer aggregations, retrieved
2026-09-27) is **UNVERIFIED (primary source unreachable: no official LinkedIn document was located
during this pass that states this specific multiplier)**. The directionally-consistent, sourced
fact is narrower and comes from LinkedIn's own commentary reported across these same sources: LinkedIn's
feed ranking treats person-to-person content and company-page content differently by design, and a
company page's own distribution is largely limited to its existing follower base while a personal
profile's content can reach second/third-degree connections through engagement-driven expansion.
Treat the exact multiplier as unverified; treat "a founder/employee's personal post generally
outreaches the same content posted from the company page" as the safe, mechanism-level claim to
act on.

## Creator Mode is retired — a live example of doctrine that must be re-verified before use

**This is the single most important fact in this file for avoiding stale recommendations.**
LinkedIn's own Help Center states, in its own words:

> "We are removing the creator mode on/off toggle in the Resources section of your profile."
> [KB-SOCIAL-033] (official, LinkedIn Help Center, "Updates to Creator Mode," retrieved 2026-09-27:
> https://www.linkedin.com/help/linkedin/answer/a5999182)

Timeline: profile hashtags/topics were removed in February 2024, and the Creator Mode toggle
itself (along with the Connect/Follow default and About-section repositioning it used to control)
was removed in March 2024 [KB-SOCIAL-034] (official, same source, retrieved 2026-09-27). Members
who previously had Creator Mode on keep the tools it used to unlock — LinkedIn Live, Audio Events,
Newsletter, creator analytics — but there is no toggle to turn on for a new account; **these
features are simply available to everyone now, always on** [KB-SOCIAL-035] (official, same source,
retrieved 2026-09-27).

**Why this matters as an anti-pattern to avoid:** any inherited GTM doctrine, template, or
cross-corpus-ported material that instructs "turn on Creator Mode" is instructing an agent to look for a
UI control that no longer exists as of March 2024. This is exactly the kind of platform-mechanics
fact that goes stale fast (`shared/citation-style.md`'s re-verification-window rule) and exactly
why this corpus never lets an agent act on an un-dated claim. See `ANTI-PATTERNS.md` in this
directory for the standing rule this generates.

## Newsletter and long-form content

LinkedIn Newsletter (subscription-based recurring long-form posts, formerly gated behind Creator
Mode, now generally available per the retirement above) is a legitimate format for a B2B SaaS
company's own GTM content — e.g. a recurring vertical-trends update or founder-voice update —
because it earns a direct subscriber notification on each publish, which is a stronger distribution
guarantee than a single feed post competing against the dwell-time/skip model above. This is a
mechanism-level, not numerically benchmarked, recommendation; no specific subscriber-growth or
open-rate figure is cited here — do not invent one.

## What belongs to a different domain

- **LinkedIn Ads** (Sponsored Content, Lead Gen Forms, Message Ads, targeting mechanics, CPC/CPL
  benchmarks) belongs to `paid_acquisition/` — this file does not build out paid-LinkedIn doctrine.
- **B2B sales sequencing on LinkedIn** (connection-request cadence, InMail follow-up, sales
  navigator workflows) belongs to the `sales/` domain — this file covers organic content/profile
  doctrine only, not outbound sales motion.

## Contractor bend

None in the usual sense — this file's audience is a B2B SaaS company's own marketing function, not
a contractor customer's own presence, per the scope note above. The bend that does apply: when the
company's own LinkedIn content talks *about* contractors (case studies, product positioning, market commentary),
it must still obey `shared/contractor-buyer-psychology.md` in how it describes the buyer — never
condescend to the home-services-owner-operator archetype in front of a LinkedIn audience of software buyers and
industry peers who may include contractors themselves.
