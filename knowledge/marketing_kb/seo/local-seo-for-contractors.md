# Local SEO for Contractors

Contractors (and home-services/contracting companies generally) are service-area businesses
(SABs) — the single most important structural fact that changes local SEO doctrine relative to a
storefront/practice business. This file ports a GBP/local-SEO mechanism originally built for a
different, storefront/appointment-based vertical (internal doctrine) and re-derives it for a
residential remodeling GC. It applies directly to two kinds of company this doctrine serves: (1) a
home-services/contracting company running local SEO for its own business, and (2) a vendor (e.g. a
SaaS company) advising its contractor customers on local SEO, or building a customer-facing "local
SEO for your business" feature or content play for them. Read the doctrine below as written for
case (1) first — a company that is itself a local service business — and translate outward to case
(2) as customer-facing guidance where relevant.

---

## 1. Service-area business (SAB) setup — the foundational decision

A contractor is a service-area business: they travel to the customer rather than the customer
visiting a storefront. This is a Google Business Profile *type*, not a formality, and setting it up
wrong actively hurts the listing.

**Official rules** (verified via third-party sources summarizing Google's own support
documentation, third-party, retrieved 2026-09-05 — Google's own `support.google.com/business`
canonical page for this topic returned a 404 on direct fetch during this research pass and should
be re-verified against the live Google Business Profile Help Center rather than trusted at
third-party remove for anything precision-critical):

- Choose "service area business" if the business visits or delivers to customers and does not serve
  walk-in customers at its own address — a home-based contractor is the textbook example.
- A true SAB **does not display a physical street address** publicly on the profile; it shows a
  defined service region instead.
- Google allows up to **20 service areas**, but listing every city within a wide radius dilutes
  relevance rather than expanding reach — stick to areas where jobs are actually taken.
- Guidance caps a service area at roughly **two hours' driving time** from the business's base
  location (third-party, retrieved 2026-09-05 — mark as directionally reliable, not a hard
  documented number Google states explicitly; treat two-hours as a sanity ceiling, not a target).

**Reject example:** A GC based in a base city sets a 20-city service area radius stretching across
the entire surrounding region — including a metro two-plus hours away and another distant metro —
because "more area = more leads." This dilutes relevance for the searches that actually convert
(nearby, high-intent) and Google's own ranking algorithm penalizes the mismatch between claimed
area and actual location signals.

**Pass example:** The same GC sets a service area of the base city plus 6 genuinely-served adjacent
towns within roughly 45 minutes' drive, matching their actual dispatch radius.

## 2. Category selection — the single highest-leverage GBP decision

**Every listing has exactly one primary category and up to nine secondary categories, ten total**
(third-party, retrieved 2026-09-05). The primary category is the strongest category-level ranking
signal on the profile.

**Mechanism ported from the source doctrine, re-derived for contractors:** the source doctrine's own
multi-location-audit skill (originally written for a different, appointment-based vertical) treats
"primary/secondary category match" as one of the dominant prominence-gap factors in its
multi-location audit procedure (internal doctrine, retrieved 2026-09-05). The mechanism — category
specificity beats category breadth — ports directly to contractors. The source doctrine does not
give a specific weighting number for category signal strength; a third-party estimate
claiming "~32% of relevance ranking weight" surfaced during this research pass is **UNVERIFIED —
seeded from a third-party study, needs independent verification** before being cited as a real
percentage to any operator or customer; use it only as directional evidence that category choice
matters a great deal, never as a precise number.

**Reject example:** A roofing specialist selects "General Contractor" as primary category because
it feels more inclusive. This actively *hurts* visibility for "roofer near me" / "roofing
contractor [city]" searches, because Google is matching the specific query intent to the specific
category, not falling back generously to a broader parent category.

**Pass example:** The same business sets "Roofing Contractor" as primary and adds "General
Contractor," "Gutter Cleaning Service," and other genuinely-offered secondary categories underneath
it.

## 3. Reviews — the dominant local-ranking lever, and the one metric worth obsessing over

**Ported directly from the source doctrine's local-ads mechanism** (internal doctrine, retrieved
2026-09-05): "Reviews are the #1 lever... On every local platform, review count, rating, and
recency determine ad effectiveness." This mechanism is vertical-agnostic by construction — it's
about how Google's and every local-lead-platform's ranking algorithms weight trust signals, not
about what's being reviewed.

**Review-count and rating thresholds ported from the source doctrine's Yelp Ads mechanism:**
"4.0+ stars, 20+ reviews minimum before advertising. Advertising a 3-star profile is
counterproductive." **This specific 20-review / 4.0-star figure is `UNVERIFIED — seeded, needs
derivation`** — it was checked against Yelp's own current advertiser-facing pages
(business.yelp.com's Yelp Ads product page) during this pass, and that page was reached
successfully but states no minimum star rating or review count as an advertiser-eligibility
requirement (official, Yelp for Business, "Yelp Ads," retrieved 2026-09-27:
https://business.yelp.com/products/yelp-ads/) — the page describes Yelp Ads features and pricing
with no eligibility floor of any kind. Treat the 20/4.0 figure as internal doctrine only (possibly
a past or account-specific Yelp policy, or Yelp Ads-rep guidance not published on Yelp's own pages)
until it is confirmed directly against Yelp's current advertiser terms at time of use — do not
present it to an operator or customer as "Yelp's own stated minimum." (Next place to check if this
needs firming up: Yelp's advertiser Terms of Service / self-serve ad-purchase flow, which may state
an eligibility floor the marketing product page doesn't.) Google itself does not
publish a hard numeric review-count threshold for map-pack eligibility (no official citation found
for a specific number); treat "more reviews, more recent, higher rating" as the correct qualitative
doctrine regardless of whether the specific 20/4.0 anchor is ever confirmed.

**Recency matters as much as count.** The source doctrine explicitly separates "review count" from
"review recency" as distinct ranking factors (internal doctrine, retrieved 2026-09-05) — a
contractor with 80 reviews from three years ago and none since ranks worse on this signal than one
with 25 reviews, 10 of them from the last 90 days. **Operationally for a GC:** review-request
should be a standing step in every completed-job workflow, not a batch campaign run occasionally.

### Review-response discipline (ported from the source doctrine's reputation-management mechanism)

(internal doctrine, retrieved 2026-09-05)

- **4-5 star reviews:** respond within 24 hours, reference a specific detail from the review, no
  generic templated thank-you.
- **1-3 star reviews:** flag for same-day human attention before any response is drafted; never
  post a defensive or templated response; a human must approve before it goes live.
- **No auto-posting, ever** — every response requires explicit approval before publishing, because
  a published review reply on Google cannot be un-posted.

## 4. Response time — the second-biggest lever, and where phone-first GCs already have an edge (or a gap)

**Ported directly from the source doctrine's local-ads mechanism, with the exact 5-minute/24-hour
figures carried as internal doctrine** (internal doctrine, retrieved 2026-09-05): "Response time is
the #2 lever... Under 5 minutes = strong boost. Over 24 hours = severe penalty." Google's own
documentation supports a weaker version of the mechanism, not these two precise thresholds and not
a stated ranking effect: "For message leads, your average response time may be displayed in your
ad, and quick response times can drive greater consumer engagement on your ad. How likely your ad
is to result in a lead is one factor in the Local Services Ads auction" (official, Google Local
Services Help, "Improve your Local Services Ads performance," retrieved 2026-09-27:
https://support.google.com/localservices/answer/12492201) — this is Google's own documented
mechanism for Local Services Ads specifically (a paid/pay-per-lead product, distinct from organic
map-pack ranking), and it supports "response time affects engagement, and lead likelihood is one
factor in the auction," not a direct, stated ranking boost/penalty. Port the qualitative direction
(faster is better, slow/unresponsive hurts lead performance) with confidence; treat the specific "5
minutes"/"24 hours" cutoffs, and any framing of a direct ranking effect, as internal doctrine, not
an officially documented mechanism, since Google's own page does not state either. It is directly
and confidently applicable to any Local Services Ads program a GC runs, and directionally true
everywhere else (Yelp, Thumbtack, Nextdoor all track and reward response speed per the same source
doctrine).

**Contractor-specific translation:** this buyer is phone-first and often literally driving between
job sites — the gap is rarely "doesn't want to respond fast," it's "missed the call because they
were on a roof." The actionable recommendation isn't "respond faster," it's infrastructure:
instant push/SMS notification on every lead channel, and — if genuinely needed — a virtual
receptionist or answering service for a business that can't self-staff fast response (mechanism
ported as-is from the source doctrine: "If the business cannot answer fast, hire a virtual
receptionist or use an answering service").

## 5. NAP consistency (Name, Address, Phone)

**Ported from the source doctrine's "Universal local ads rules"** (internal doctrine, retrieved
2026-09-05): "Every local ad platform creates a citation. Ensure NAP on every platform matches the
canonical NAP from the local listings audit." Google's own Business Profile guidance confirms the
underlying mechanism for multi-location consistency specifically — "All locations must have the
same name unless the business's real world representation consistently varies from location to
location," and a business should "Represent your business as it's consistently represented and
recognized in the real world across signage, stationery, and other branding" and "Make sure your
address and/or service area is accurate and precise" (official, Google Business Profile Help,
"Guidelines for representing your business on Google," retrieved 2026-09-27:
https://support.google.com/business/answer/3038177) — that page's own emphasis is on
consistency within Google Business Profile and against real-world signage, not an explicit,
named cross-platform NAP-matching rule; the broader claim that inconsistency *across third-party
platforms* (Yelp vs. the website vs. an old directory listing) drags local ranking is internal
doctrine, not something Google's own page states in those terms. Separately, Google's own local-
ranking help page confirms the general accuracy mechanism: "Businesses with complete and accurate
info are more likely to show up in local search results. If your business info isn't accurate,
your Business Profile might not show up for relevant searches in your area" (official, Google
Business Profile Help, "Tips to improve your local ranking on Google," retrieved 2026-09-27:
https://support.google.com/business/answer/7091). This mechanism is fully vertical-agnostic —
Google's local ranking algorithm (and every directory's) treats NAP consistency as a trust signal,
and inconsistency (a different phone number on Yelp than on the website, an old address still
listed on a directory after a move) is a well-established drag on local ranking regardless of
industry.

**Contractor-specific wrinkle:** many lead-gen platforms (Yelp, CallRail-style call tracking)
replace the displayed phone number with a tracking number — legitimate for attribution, but it
creates exactly the NAP-inconsistency risk this rule warns about. Weigh the tracking benefit
against the citation-consistency cost per platform (mechanism ported as-is from the source
doctrine's Yelp-specific considerations).

## 6. The multi-location audit procedure — ports directly, one substitution

The source doctrine's own patient/customer-acquisition skill (written for a different,
appointment-based vertical) has a fully-specified, hard-gated multi-location local SEO audit
procedure (internal doctrine, retrieved 2026-09-05). The entire procedure ports to a multi-crew or
multi-branch GC with one substitution: "practice locations" → "service branches/yards," and
"patient" → "customer/homeowner" throughout. The core discipline is identical
and worth restating in full because it is the single most rigorous honesty rule in the whole source
corpus:

> **HARD PRECONDITION:** a live GBP-listing read must actually run, this turn, before any statement
> about a location's Google Business Profile — never open with an inference about GBP existence,
> verification status, reviews, category, or photos before that call has actually run and returned.
> If it wasn't called, returned nothing, or errored, the only permitted phrasing is: "I could not
> verify [location]'s Google Business Profile this session — connect GBP or check the console."
> **Never** a probabilistic guess like "almost certainly doesn't have one." A missing live read
> means UNKNOWN, never ABSENT.

This ports to the `seo-architect` seat verbatim as a governing principle for any company: never
claim a GBP fact (verification status, review count, category, photo count) without a live check
this session, and when a live check isn't possible, say so plainly rather than inferring.

**The named "prominence gap" factors, in the source doctrine's own priority order** (internal
doctrine, retrieved 2026-09-05): review count + recency (biggest lever), location age (**"Google
takes 3-6 months to build local prominence for a new location" — state this honestly, never oversell
a fast timeline**), primary-category match, GBP completeness (photos/posts/hours), whether the
GBP's website link points to that location's own page vs. the homepage, and per-location website
signals (indexed page, geo+service keywords in title, correct schema, no accidental noindex). This
priority order is vertical-agnostic and ports as-is to a multi-branch GC.

## 7. Photo volume benchmarks

**Ported from the source doctrine's local-ads mechanism, platform-specific and vertical-agnostic**
(internal doctrine, retrieved 2026-09-05): Yelp profile completeness recommends 20+ photos;
Thumbtack optimization recommends "15+ photos minimum," specifically "before/after project
photos." **For a remodeling GC this is not a generic best practice, it's the single best-fit
content type available** — a kitchen/bath remodel is inherently visual, and before/after pairs are
exactly the trust signal Yelp/Thumbtack/GBP photo guidance rewards. This is one case where the
mechanism and the vertical fit are unusually well aligned; lean into it harder for a GC than the
source doctrine's original, differently-scoped vertical framing would suggest.

## 8. Local service ad platforms — what applies to a GC

Google Local Services Ads (LSA) explicitly lists "home services" as an eligible category (official
mechanism, ported from the source doctrine — Google's own eligible-category list is a live,
Google-controlled list and should be re-verified at time of use rather than assumed static). The
verification/badge system (Google Guaranteed, background checks, license/insurance verification)
applies identically to a contractor as to any other eligible category — this is Google's own LSA
program mechanism, not vertical-specific at all.

**Cost benchmark note:** the source doctrine gives a home-services CPL benchmark of **$15-50**
directly (not a figure borrowed from a different vertical — this is the doctrine's own
home-services row, already correctly scoped) — this is safe to cite as-is (internal doctrine,
retrieved 2026-09-05), though it should still be treated as a wide directional range, not a
guarantee, and re-verified periodically since LSA costs are market- and demand-driven and drift
over time.

---

## Contractor bend

This entire file *is* the contractor bend for local SEO — there is no further translation layer
needed beyond what's already written above, because the doctrine was authored directly against
this buyer (see `shared/contractor-buyer-psychology.md` for the full persona). Two things
specific to that archetype worth stating explicitly:

- **This buyer will conflate "local SEO" with "Google Ads" with "my website" with "my GBP listing"**
  — they experience all of it as one undifferentiated "internet marketing" black box that some past
  vendor charged them for with vague results. Any local-SEO recommendation should be explicit about
  which lever it's pulling (organic map pack vs. paid LSA vs. GBP hygiene vs. review generation) and
  why, because this buyer has been burned by vendors who blur these together to avoid accountability
  for which one actually worked.
- **This buyer trusts word-of-mouth and in-person reputation far more than search-engine
  mechanics**, and rightly so — in their actual experience, a referral from a past customer closes
  jobs, not a Google ranking. The review-generation and NAP-consistency doctrine above should be
  framed to this buyer as "making your existing word-of-mouth reputation visible and legible to
  Google," not as an abstract SEO tactic — that framing matches what they already believe works and
  earns buy-in instead of skepticism.
