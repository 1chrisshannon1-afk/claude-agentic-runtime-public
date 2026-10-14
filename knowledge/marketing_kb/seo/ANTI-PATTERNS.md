# SEO Anti-Patterns — Things a Seat Must NEVER Recommend

Every item below is something the `seo-architect` seat (or any GTM agent touching SEO) must refuse
to propose, even when a founder/operator asks for it directly, even when a competitor is visibly
doing it, and even when it would plausibly work short-term. Cite this file when refusing.

---

## 1. Doorway pages / one-city-clone pages

**What it is:** Generating near-identical pages that differ only by city/neighborhood name
("Bathroom Remodeling in Base City", "Bathroom Remodeling in Adjacent Town A", "Bathroom
Remodeling in Adjacent Town B") with no genuinely distinct content, funneling every one of them to
the same underlying page or form.

**Why it's banned:** This is Google's own named violation. "Doorway abuse is when sites or pages
are created to rank for specific, similar search queries. They lead users to intermediate pages
that aren't as useful as the final destination." (official, Google Search Central spam policies,
retrieved 2026-09-05: https://developers.google.com/search/docs/essentials/spam-policies). A site
found doing this is subject to a manual action — full or partial deindexing — which is the single
worst outcome an SEO recommendation can cause (see `technical-seo-checklist.md`'s Manual Actions
section). There is no "light" version of this that's safe.

**What's actually allowed:** A genuinely distinct local page per real service area *is* legitimate
local SEO — see `local-seo-for-contractors.md` — but it must carry unique, substantive content
(real project photos from that area, that area's permit/code notes, that area-specific service
radius, distinct testimonials), not a templated city-name swap over otherwise identical copy.
**Reject example:** 40 pages differing only in `{city}` string substitution in an H1 and meta
title, same 200 words of body copy. **Pass example:** a page for a service area that names actual
completed projects in that town, that town's specific permit office/inspection quirks, and a
service-radius map — even if the template/layout is shared.

## 2. Keyword stuffing

**What it is:** Unnatural repetition of a target phrase in body copy, alt text, or hidden
elements to try to signal relevance.

**Why it's banned:** Named Google spam policy: "Keyword stuffing refers to the practice of
filling a web page with keywords or numbers in an attempt to manipulate rankings in Google Search
results." (official, retrieved 2026-09-05, same source as above). Modern ranking systems use
semantic/embedding-based relevance, not term-frequency counting — stuffing reads as spam to both
the algorithm and the human reader, and actively hurts conversion (a pattern also documented in a
different vertical's own generic-AI-copy anti-pattern doctrine, internal doctrine, retrieved
2026-09-05 — the mechanism is vertical-agnostic: readers and ranking systems both penalize
obviously mechanical repetition regardless of industry).

**Reject example:** "Our Metro City bathroom remodel Metro City bathroom remodeling company remodels
bathrooms in Metro City for Metro City homeowners who need a Metro City bathroom remodel." **Pass example:**
one natural mention of the target phrase in the H1, one in the first 100 words, and otherwise
write for the reader.

## 3. Schema spam / fabricated structured data

**What it is:** Marking up content with `AggregateRating`, `Review`, `FAQPage`, or similar schema
types where the underlying reviews/FAQs are fake, undisclosed-incentivized, or don't actually
appear as visible content on the page — i.e., using structured data to claim something to Google
that isn't true or isn't shown to the user.

**Why it's banned:** Google's July 2026 update to Review Snippets guidelines specifically added
language addressing "fake and undisclosed incentivized reviews" (official, Google Search Central
changelog, retrieved 2026-09-05). Google's general structured data guidelines also require that
marked-up content be visible to users on the page — schema is not a place to assert facts that
don't otherwise exist on the page. A manual action for structured data spam removes the rich
result eligibility for the *entire site*, not just the offending page.

**Reject example:** Adding `AggregateRating` schema with a 4.9-star/312-review claim when the
actual GBP or on-page review count is 12. Adding `FAQPage` schema whose questions/answers are not
rendered as visible text anywhere on the page (schema-only content). **Pass example:** `Review`/
`AggregateRating` schema that mirrors exactly what's rendered on the page and matches the real
review platform data — see `schema-strategy.md` for the current (post-May-2026) status of FAQPage
rich results specifically, which changes what's even worth marking up.

## 4. Cloaking / different content to bots vs. users

**What it is:** Serving search engine crawlers a different version of a page than what a human
visitor sees (a pre-rendered "SEO version" with more keywords/links, a JS-gated version that
shows more to Googlebot, user-agent sniffing that swaps content).

**Why it's banned:** Named Google spam policy: "Cloaking refers to the practice of presenting
different content to users and search engines with the intent to manipulate search rankings and
mislead users." (official, retrieved 2026-09-05, same source). This is one of the most severely
penalized violations because it's read as deliberate deception, not a quality miss.

**A common real risk surface, not just a hypothetical:** a statically pre-rendered marketing site
served identically to bots and humans has no runtime rendering divergence today, but a *future*
change that adds client-side-only content (e.g. a JS widget that injects text Googlebot's renderer
might not wait for) can silently introduce cloaking risk without anyone intending it, if nobody
checks that the injected content also appears in the static HTML. Any recommendation to add
dynamically-injected page content must specify how it verifies parity with what a crawler sees
(e.g. `curl` the deployed HTML, don't just view it in a browser). Whether a given company's site is
statically pre-rendered or has runtime divergence is a company-specific fact — see that company's
own pack/dossier for its actual build pipeline.

## 5. Scaled/AI-generated content abuse

**What it is:** Mass-producing pages (via AI generation, scraping, or thin recombination of
existing content) whose primary purpose is to rank for many query variations rather than to help
a specific reader.

**Why it's banned:** Named Google spam policy (added as its own category, superseding the older
"auto-generated content" policy): "Scaled content abuse is when many pages are generated for the
primary purpose of manipulating search rankings and not helping users." (official, retrieved
2026-09-05, same source). Google is explicit that this applies "regardless of creation method" —
using AI to write it is not what's punished; producing it at low-value scale is.

**Reject example:** Auto-generating 200 blog posts ("25 Kitchen Remodel Ideas for [Zodiac Sign]",
"[City] Kitchen Trends for [Year]") from a template with no genuine research or local specificity,
published in a burst. **Pass example:** AI-assisted drafting of a smaller number of genuinely
useful, fact-checked, locally-specific pieces, each reviewed by a human before publish — see the
Helpful Content self-assessment in `keyword-research-doctrine.md`.

## 6. Buying links / link schemes

**What it is:** Paying for backlinks, participating in link exchange networks, or using
automated/programmatic link-building services that place links on unrelated sites purely for SEO
value.

**Why it's banned:** Covered under Google's link spam policy (part of the same spam-policies
doctrine, official, retrieved 2026-09-05) — one of the three canonical named violation categories
alongside doorway pages and cloaking in Google's own P0 Manual Actions framing (see
`technical-seo-checklist.md`). For a contractor GC, the legitimate equivalent is real local
citations (supplier partners, trade associations, local chamber of commerce, past-client
testimonial pages that link back) — see `local-seo-for-contractors.md`.

## 7. Recommending a rich-result schema type that Google no longer renders

**What it is:** Prescribing `FAQPage` schema (or any other deprecated rich-result type) as an SEO
lever because "it used to boost CTR," without checking current eligibility.

**Why it's banned here specifically:** Google removed the FAQ rich result from Search results
entirely starting May 7, 2026, and removed its own documentation for the feature in June 2026
(official, Google Search Central changelog, retrieved 2026-09-05). Marking up FAQ content in
`FAQPage` schema today does not produce an FAQ accordion in search results — it does nothing
functionally harmful, but recommending it *as an SEO win* is a stale/wrong recommendation. See
`schema-strategy.md` for what to use instead (well-structured on-page FAQ content still helps
E-E-A-T and can surface in AI Overviews/snippets, just not via that specific schema mechanism).

## 8. Pausing organic-dominant paid spend without checking first (SEO/paid cross-contamination)

**What it is:** Recommending a paid-spend cut on a term "because organic already ranks well" without
having actually pulled live Search Console data for that exact term, or recommending new paid
spend on a term without checking whether organic already owns it efficiently.

**Why it's banned:** This is a mandatory gate carried over from the source doctrine, restated here
because SEO recommendations feed directly into paid decisions: "Cannibalization and
organic-dominance checks are mandatory before recommending paid spend on a term. Never recommend
bidding on a query without first checking whether organic already ranks 1-3 with strong CTR for
it." (internal doctrine, retrieved 2026-09-05).
Never state a term's classification (organic-dominant / present-not-dominant / absent) without
citing the live query data that produced it (see `keyword-research-doctrine.md`).

## 9. Claiming a Manual Action or Security Issue check that was never actually run

**What it is:** Reporting "no manual actions found" or "site is clean" as if a tool confirmed it,
when no bound tool can actually read the Search Console Manual Actions or Security Issues reports.

**Why it's banned:** Verified as a real, structural API gap: the Search Console API's own reference
index lists only Search Analytics (`query`), Sitemaps (`delete`/`get`/`list`/`submit`), Sites
(`add`/`delete`/`get`/`list`), and URL Inspection (`index.inspect`) — there is no
`manualActions.list` / `securityIssues.list` call available to a third-party integration (official,
Search Console API reference index, retrieved 2026-09-27:
https://developers.google.com/webmaster-tools/v1/api_reference_index). A false-clean report here is
actively dangerous: a real manual action drops organic traffic to zero and forces 100% paid
dependency, and nobody would know to check because the tooling "already said it's fine."
**Correct behavior:** always state plainly that this specific check requires a human to look at
the Search Console UI directly; never infer it from any other clean signal.

## 10. Fabricating one vertical's benchmark numbers as if they apply to another

**What it is:** Quoting a different vertical's CPC/CPA/CPL benchmarks (e.g. a patient-acquisition
CPL figure from a healthcare-practice corpus) as if they apply to a home-services/contracting GC,
without deriving a home-services-specific number.

**Why it's banned:** These numbers are vertical-specific by construction (a different vertical's
acquisition economics, not GC lead economics) and porting them as fact would misprice every
downstream recommendation this corpus feeds — see the house-style rule in `INDEX.md`; any ported
number that hasn't been independently re-derived for home services carries the standard
`UNVERIFIED — seeded, needs derivation` tag (see `shared/citation-style.md`). Only the
*mechanism* (the gate, the classification logic, the threshold structure) ports; the number never
does without independent home-services derivation and citation.

---

## Contractor bend

None of the above changes for the home-services/contracting GC buyer (see
`shared/contractor-buyer-psychology.md` for the full persona) — if anything the stakes are
higher, because this buyer typically has no in-house marketing staff to catch a bad recommendation
before it costs them a manual action or wasted spend, and they are far more likely to have been
burned before by an agency or software vendor that over-promised ("we'll get you page 1 in 30 days"
is itself close to a doorway-page-era sales pitch). When explaining *why* something is off-limits
to this buyer, skip the algorithm-abuse framing and lead with the business consequence in plain
terms: "if we do this and Google catches it, your entire website disappears from search for weeks
to months — that's not a risk worth the shortcut." Never assume this buyer will push back on a
shortcut being offered; the obligation not to offer it is entirely on the agent.
