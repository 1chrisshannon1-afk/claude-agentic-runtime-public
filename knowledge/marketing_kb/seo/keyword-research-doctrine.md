# Keyword Research Doctrine

Pre-launch keyword research (Keyword Planner-first, since there's no live GSC data yet for a new
domain or new page), intent segmentation, the organic/paid alignment gate, and the people-first
content standard that governs what to actually write once keywords are chosen.

---

## 1. Pre-launch: Keyword Planner-first (no GSC history to lean on yet)

For a brand-new page, a brand-new domain, or a company's own marketing site before it has
meaningful Search Console history, there is no live organic query data to analyze — the entire
`organic-search-alignment` mechanism (§4 below) has nothing to read yet. **Google Keyword Planner
is the correct starting instrument for this phase**, not Search Console.

**Access mechanics (third-party, retrieved 2026-09-05):**
- A Google Ads account is required to reach Keyword Planner, but **an active campaign or spend is
  not required** — Google changed this in 2023 to allow account creation without launching a
  campaign or entering payment information.
- **Without active ad spend, search volumes are shown as wide ranges** (e.g., "1K–10K") rather than
  exact numbers. This is a real, structural data-quality limitation, not a UI quirk — treat
  Keyword-Planner-only volume estimates pre-launch as **directional, not precise**, and never
  present a range-derived number to an operator as if it were an exact monthly search volume.
- Full numeric precision unlocks with active campaign spend — meaning the moment a company (or its
  own contractor customer) runs even a small live Google Ads campaign, the same tool starts
  returning much more trustworthy numbers. This is worth stating explicitly when advising an
  operator on sequencing: a small, deliberate paid spend can be justified purely as a
  keyword-research data-quality unlock, independent of its direct lead-gen value.

**What Keyword Planner is good for pre-launch:** rough volume-tier sorting (is this a "1K-10K/mo"
term or a "10-100/mo" term), close variant discovery ("bathroom remodel cost" vs "bathroom
renovation cost" vs "how much does a bathroom remodel cost"), and competitive/CPC-bid signal as a
rough commercial-intent proxy (a term with a high suggested bid is one advertisers believe converts,
which is itself useful signal even before any organic work begins).

**What it is not good for:** precise volume numbers without spend (see above), and it says nothing
about current *ranking difficulty* — that requires either a paid rank-tracking/difficulty tool
(out of scope for this corpus pass — mark any specific vendor recommendation as **UNVERIFIED,
needs derivation**) or, once the domain exists, actual GSC position data per §4.

## 2. Intent segmentation — the regex framework, ported and re-anchored for home services

**Mechanism ported directly from the source doctrine** (internal doctrine, retrieved 2026-09-05 —
two files in the source corpus state the identical framework, which is expected corroboration
since one summarizes the other, not independent confirmation). The regex patterns themselves are
query-language patterns, not vertical-specific vocabulary, so they port as-is:

| Intent stage | Pattern (RE2, case-insensitive) | What it means for a GC's content |
|---|---|---|
| Informational | `^(how\|what\|why\|when\|where\|who\|which\|can\|does\|is\|are\|will\|should\|do)\s` | "How much does a kitchen remodel cost", "what is a permit for" — educational content, guides, cost-range pages |
| Commercial | `\b(best\|vs\|comparison\|top\|review\|features\|alternatives)\b` | "best bathroom remodeler near me", "kitchen remodel vs refacing" — comparison pages, differentiator content |
| Transactional | `\b(buy\|purchase\|discount\|offer\|deal\|subscribe\|sign up\|download\|book\|schedule\|quote\|estimate\|cost\|price\|near me)\b` | "get a kitchen remodel quote", "bathroom remodel cost [city]" — this is the highest-value bucket for a GC: it maps directly to "get an estimate," the core lead-conversion motion for this vertical |
| Long-tail | `^\w+(\s\w+){6,}$` (7+ words) | "how much does it cost to remodel a small bathroom in an older home" — low-competition, often the highest-converting single-page targets available to a small/new site |

**Contractor-specific re-anchoring:** the transactional-intent vocabulary list above (`quote`,
`estimate`, `cost`, `price`, `near me`) is a GC's highest-value search-lead vocabulary regardless of
what any vendor sells. The general point worth naming to any company in this space: map the
vertical's own transactional-intent vocabulary to that company's own actual conversion action (a
quote request, a signup, a booked call) rather than assuming a generic list applies unchanged — for
some companies (e.g. a vendor whose own product category is directly named by that vocabulary,
such as an estimating tool) the alignment between search-intent vocabulary and product vocabulary
can be unusually tight, which is worth calling out explicitly when it's true, but this is
company/product-specific and must be checked against that company's own product category before
being asserted, not assumed as a default.

## 3. "Almost there" keywords — positions 4-15

**Ported directly** (internal doctrine, retrieved 2026-09-05): pages already ranking positions
4-15 have "sufficient authority, need on-page signal refinement" — weave the target keyword into
H1/H2 tags, body copy, and internal anchor text; expand sections buyers expect (pricing, timeline,
FAQ). These pages are also the correct exact-match paid-ad destinations while organic rank is still
being built, since the existing organic signal proves relevance/authority even before the ranking
itself lands on page 1.

**Illustrative pattern for a remodeling content page** (a worked pattern, not any one company's
measured numbers — UNVERIFIED as a benchmark, illustrative only): a kitchen-remodel page ranking
8-14 for its target local term, with a title that doesn't lead with the target phrase and under
1,500 words of body content, is a textbook "almost there" candidate (it sits inside the 4-15 gate
defined above). The fix is exactly the "almost there" playbook above plus expanding to 1,500+ words
with the sections buyers expect (cost ranges, timeline, material options, before/after gallery,
FAQ) — this is a good template for what "on-page signal refinement" concretely means for a
remodeling content page.

**A page ranking well outside the 4-15 gate — e.g. position 40-60 — is NOT an "almost there"
candidate and is not yet a correct paid-ad destination proxy either** (see §4's classification
table: a page ranking outside page 1-2 is closer to "organic-absent" than "organic-present, not
dominant"). The same on-page refinement plus content-expansion playbook still applies (keyword
placement, 1,500+ words, the buyer-expected sections), but expect a materially longer ramp before
it earns page-1 authority, and do not cite it to an operator as evidence the page is close to
converting via organic rank. When doing this for a real company, pull that company's own live
Search Console data for the actual position/impression numbers rather than assuming these
illustrative figures.

## 4. Organic/paid alignment — the mandatory gate before recommending or cutting paid spend

**This is the single most rigorously-specified mechanism in the source doctrine, and it ports
completely unmodified** (internal doctrine, retrieved 2026-09-05): "Before recommending or
spending on any paid keyword, check what organic search is already doing for that same term." The
classification logic:

| Classification | Definition | Action |
|---|---|---|
| **Organic-dominant** | Position 1-3 AND CTR above ~5% | Do not recommend new/increased paid spend on this term. If paid is already running on it, flag as a pause/redirect candidate (subject to standard paid-side safety gates). |
| **Organic-present, not dominant** | Page 1-2, position 4-15, modest CTR | Call out the specific on-page fix (title/meta rewrite, added content, internal linking) *and* the paid option; let the operator choose the lever, or both. |
| **Organic-absent** | No ranking data, or ranks well outside page 2 | Paid is the correct and only available lever. No organic-alignment objection applies. |
| **Cannibalized** | 2+ owned URLs ranking for the same query | Name every competing URL and its position/CTR; recommend consolidation (301, canonical, or intent re-optimization) before further investment of either kind in that query. |

**Hard rule, restated because it's easy to skip under time pressure:** never report a term's
classification without citing the live query-data pull that produced it, and never recommend paid
spend on an organic-dominant term without saying so explicitly (internal doctrine, retrieved
2026-09-05, same source). This is READ-ONLY doctrine — it informs a decision, it never itself
executes a campaign change.

**Incrementality testing, for when the alignment classification alone isn't conclusive:** geo-based
or time-based holdout tests, minimum 4 weeks (2 ramp-down + 2 steady-state), before permanently
reallocating budget off an organic-dominant term (internal doctrine, retrieved 2026-09-05). The
benchmark cited in the source doctrine — "~89% of non-branded ad clicks are genuinely incremental"
(third-party meta-analysis, as characterized there) — is a general paid-search industry figure, not
home-services-specific; treat it as a reasonable prior, not a home-services-verified number.
**UNVERIFIED for home-services specifically — needs independent derivation** if a precise vertical
number is ever required for a real budget decision.

## 5. Cannibalization diagnosis mechanism

**Ported directly, vertical-agnostic** (internal doctrine, retrieved 2026-09-05): filter the
Performance report by the specific query, switch to the Pages tab — if 2+ owned URLs generate
impressions for the same query, cannibalization is active.
A declining CTR trend on the competing URLs over time is a corroborating signal. Resolution paths,
in order of typical fit: content consolidation with a 301 redirect (one page is clearly strongest),
intent re-optimization (both pages have a genuine reason to exist, so retarget the weaker one to a
distinct long-tail variant), or a canonical tag (the secondary page exists for a real UX reason but
shouldn't compete for ranking signal).

## 6. Helpful Content / people-first self-assessment — what actually earns the ranking, after the keyword is chosen

Choosing the right keyword is necessary but not sufficient — Google's ranking systems evaluate
whether the resulting content is genuinely useful, not just correctly targeted. **Self-assessment
questions** (official, Google Search Central "Creating Helpful, Reliable, People-First Content,"
retrieved 2026-09-05: https://developers.google.com/search/docs/fundamentals/creating-helpful-content):
"Does your content provide original information, reporting, research, or analysis?" / "Does it
provide a substantial, complete, or comprehensive description of the topic?" / "Is this the sort of
page you'd want to bookmark, share with a friend, or recommend?"

**E-E-A-T framing** (official, same source): assess content on **Who** (is it self-evident who
created it — a byline, author background), **How** (was it produced with genuine care, or
mass-generated), and **Why** (was it created primarily to help a reader, or primarily to rank for a
query). This directly informs the anti-pattern boundary in `ANTI-PATTERNS.md` §5 (scaled/AI-generated
content abuse) — the "Why" question is the exact test that separates AI-*assisted* content (fine)
from AI-*generated-at-scale-to-rank* content (a named spam violation).

**For a GC's content specifically:** the "original information/experience" bar is easy to clear
honestly and easy to fake badly. A genuine advantage a real contractor has over a content farm: real
project photos, real local permit/code knowledge, real pricing ranges from their own completed jobs.
Content that leans on those genuine assets passes E-E-A-T's "Who/How/Why" test naturally; generic,
templated copy that could describe any contractor in any city does not, regardless of how well the
keyword itself was chosen.

---

## Contractor bend

Keyword research is the most abstract, least tangible part of SEO doctrine to this buyer (see
`shared/contractor-buyer-psychology.md` for the full persona) — "search volume," "CPC," and
"intent segmentation" are all agency jargon to someone who thinks in bids, punch lists, and change
orders. Two translations that consistently land:

- Frame keyword tiers the way a GC already thinks about lead quality: informational-intent keywords
  are "tire kickers doing research," transactional-intent keywords ("cost," "estimate," "quote,"
  "near me") are "people ready to hire," and the doctrine's own priority order (chase transactional
  first, use informational content to build trust and E-E-A-T secondarily) matches exactly how this
  buyer already triages phone leads.
- Never present a Keyword-Planner volume range as a promise of lead volume. This buyer has been
  burned before by a vendor selling "10,000 searches a month for your keyword!" that translated into
  zero real jobs. State plainly, every time: search volume is *demand that exists*, not *leads
  you'll get* — conversion depends on rank, on-page quality, and the buyer's own responsiveness
  (tying directly back to `local-seo-for-contractors.md` §4's response-time doctrine).
