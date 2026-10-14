# Technical SEO Checklist

The mechanical, verifiable half of SEO: crawlability, indexability, canonicalization, sitemap/robots
correctness, and the P0 risk surfaces. This file is the operational cadence + audit checklist; see
`schema-strategy.md` for structured data specifically and `web-vitals-thresholds.md` for performance.

---

## 1. Crawl and index fundamentals (official doctrine)

- **Canonicalization is a hint, not a rule.** "You can indicate your preference to Google using
  these techniques, but Google may choose a different page as canonical than you do, for various
  reasons." (official, Google Search Central, "What is URL Canonicalization", retrieved 2026-09-05:
  https://developers.google.com/search/docs/crawling-indexing/canonicalization). Never tell an
  operator a `rel=canonical` tag *guarantees* a specific URL gets indexed — it's a strong signal,
  not a directive.
- **Self-referencing canonicals on every indexable page.** Use a self-referencing
  `<link rel="canonical">` tag on all indexable pages, and use the *same* URL in internal links,
  the sitemap, and the canonical tag (official, same source, retrieved 2026-09-05). URL
  inconsistency across these three surfaces is one of the most common real-world canonicalization
  bugs.
- **Content similarity test.** Google's own heuristic for whether a canonical claim is honest: "if
  you placed the duplicate side-by-side with the canonical, does a very large percentage of the
  words of the duplicate page appear on the canonical page?" (official, same source). If not,
  it isn't a duplicate — don't canonicalize it away; it needs its own indexable identity.
- **Never use robots.txt for canonicalization.** Blocking a URL in robots.txt does not consolidate
  its ranking signals into another URL — it just stops Google from seeing the page at all
  (official, Google Search Central "5 common mistakes with rel=canonical", retrieved 2026-09-05).

### Indexing resolution playbook: "Crawled — currently not indexed"

(internal doctrine, retrieved 2026-09-05)

1. Confirm live via URL Inspection — never trust a cached report.
2. Optimize crawl budget: block genuinely low-value URLs (faceted nav, internal search results,
   pagination params) in robots.txt.
3. Strengthen internal linking from high-authority pages to the unindexed URL.
4. Review content quality — thin or duplicate content is the most common real cause of exclusion.
5. Verify canonical tags point to self or the correct primary URL.
6. Request indexing via URL Inspection — strategically, never as a mass/bulk action (Google rate-
   limits and may treat mass requests as a spam signal).

---

## 2. robots.txt correctness

**Official rules** (Google Search Central, "How to write and submit a robots.txt file", retrieved
2026-09-05: https://developers.google.com/search/docs/crawling-indexing/robots/create-robots-txt):

- Must live at the site root: `https://example.com/robots.txt`. It applies only to that exact
  protocol/host/port — a robots.txt at `app.example.com` never governs `example.com` or vice versa.
  **This is exactly the reject example below** — two separate domains need two separate,
  independently correct robots.txt files; one cannot cover for the other.
- `User-agent: *` matches all crawlers except AdsBot, which must be named explicitly if you need to
  control it.
- `Disallow` paths must start with `/`; directory-style blocks should end with `/`.
- Case-sensitive: `/File.asp` and `/file.asp` are different paths to the rule matcher.
- Exactly one robots.txt per site, plain UTF-8 text — word-processor exports that inject smart
  quotes or non-breaking spaces silently break the file.
- `Sitemap:` directive uses a fully-qualified absolute URL, not a relative path.

### Pass / reject examples

- **Pass:** `Disallow: /api/` on a marketing domain whose only non-page traffic is a backend
  rewrite prefix with zero SEO value.
- **Reject:** A robots.txt with a `Sitemap:` line pointing at a *different domain's* sitemap
  (`Sitemap: https://example.com/sitemap.xml` served from `app.example.com`). A crawler reading
  the app domain's robots.txt is told to go fetch a sitemap that describes a *different* site's
  URL set — a real, recurring failure mode for any company that splits a marketing domain from an
  app subdomain; check the company's own pack/dossier for whether it has this split and whether
  both robots.txt files are independently correct.

---

## 3. sitemap.xml correctness

**Official limits and rules** (Google Search Central, "Build and submit a sitemap", retrieved
2026-09-05: https://developers.google.com/search/docs/crawling-indexing/sitemaps/build-sitemap):

- **Hard limit: 50,000 URLs or 50MB uncompressed per sitemap file.** Beyond that, split into
  multiple sitemap files plus an optional sitemap index. (A pre-launch or early-stage marketing
  site will typically be nowhere near this limit — the same number is independently corroborated
  in the source doctrine below, which is good corroboration, not coincidence.)
- **Include only canonical, indexable URLs you actually want ranked.** Absolute URLs only
  (`https://...`, never relative paths). Never list duplicate URLs for the same content — pick the
  canonical one.
- **Google ignores `<priority>` and `<changefreq>`.** These tags exist in the sitemap protocol but
  "Google disregards the `<priority>` and `<changefreq>` tags in XML sitemaps, so these values
  won't affect indexing decisions" (official, same source, retrieved 2026-09-05). If a company's
  own sitemap generator hand-tunes per-path `priority`/`changefreq` values, that is not wrong to
  keep (harmless, and some third-party crawlers may still read it), but it must never be described
  to an operator as something that influences Google ranking or crawl frequency — see the
  company's own pack/dossier for whether its build pipeline does this.

### Sitemap hygiene checklist (internal doctrine, retrieved 2026-09-05)

- [ ] Only canonical URLs — no `noindex`-tagged or robots.txt-blocked pages
- [ ] Only HTTPS URLs
- [ ] Under 50MB uncompressed, under 50,000 URLs per file
- [ ] Every URL matches the domain the sitemap itself is served from (same-domain check)
- [ ] No URL appears that the build doesn't actually produce, and no produced page is missing from
      the sitemap — bidirectional drift check (a build-time test that mechanically enforces this
      bidirectional drift check is the strongest available guard; check the company's own
      pack/dossier for whether one exists and where)

---

## 4. Structured data validation cadence

(internal doctrine, retrieved 2026-09-05)

- Validate via Search Console's structured data reports.
- Fix **errors** immediately.
- Fix **warnings** within 7 days.
- Deploy schema on all key page types appropriate to the business — see `schema-strategy.md` for
  which types are actually still worth deploying post-May-2026 FAQPage deprecation.

---

## 5. Core Web Vitals — see `web-vitals-thresholds.md` for full detail

Quick reference only:

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP | ≤ 2.5s | 2.5s–4.0s | > 4.0s |
| INP | ≤ 200ms | 200ms–500ms | > 500ms |
| CLS | ≤ 0.1 | 0.1–0.25 | > 0.25 |

(official, web.dev, retrieved 2026-09-05 — see `web-vitals-thresholds.md` for full citations and
the CrUX-data-discontinuation note)

Poor CWV on any page that's also a paid landing page lowers Google Ads Quality Score, which raises
CPC — this is the single clearest place technical SEO and paid spend interact (internal doctrine,
retrieved 2026-09-05).

---

## 6. Weekly / Monthly / Quarterly operational cadence

(internal doctrine, retrieved 2026-09-05; mechanism ported as-is — cadence
logic is vertical-agnostic)

### Weekly
1. Check the Pages report for new `Crawled — currently not indexed`, `Not found (404)`, `Server
   error (5xx)`, and `Soft 404` spikes. Prioritize revenue pages first (pricing, signup, contact).
2. Check Security Issues and Manual Actions reports **manually in the GSC UI** — no tool can read
   these programmatically (see §7 below). Any finding is P0.
3. Review the Core Web Vitals report. Fix "Poor" URLs before "Needs improvement" ones; sort by
   impressions so the highest-traffic pages get fixed first.
4. Check the GSC message center for new notifications (indexing warnings, structured data errors).
5. Cross-reference any 404s against active paid landing pages — a 404 on a paid landing page is
   simultaneous budget waste and a Quality Score penalty.

### Monthly
1. Pull a 3-month Performance report window. Identify high-impression/low-CTR pages (meta
   title/description problem) and pages ranking positions 8-20 ("almost there" — see
   `keyword-research-doctrine.md`).
2. Run cannibalization check on top revenue keywords: filter Performance by query, switch to the
   Pages tab, flag any query served by 2+ owned URLs.
3. Verify sitemap health per §3 above.
4. Cross-reference top organic queries against active paid keywords (see
   `local-seo-for-contractors.md` and the organic-alignment doctrine referenced in
   `keyword-research-doctrine.md`).

### Quarterly
1. Full technical audit: crawl budget, redirect chains, canonical consistency, mobile usability,
   HTTPS coverage.
2. Content cluster review: are pages meeting traffic/conversion targets? Refresh stale sections,
   strengthen internal linking.
3. Structured data revalidation across all key page types.

---

## 7. P0 risk surfaces — Manual Actions and Security Issues

**Structural tooling gap (official, Search Console API reference index, retrieved 2026-09-27:
https://developers.google.com/webmaster-tools/v1/api_reference_index — the API exposes only Search
Analytics, Sitemaps, Sites, and URL Inspection):** The public Search Console API does not expose
either report. There is no `manualActions.list` or `securityIssues.list` call. No automated tool —
a Search Console query or URL-inspection integration, a site-audit tool, PSI, or CrUX — can confirm
"no manual action" or "no security issue." **Never report either as checked/clean unless a human
has actually looked at the GSC UI directly this session.** The correct phrasing when asked "are
there any manual actions" is "no tool can check that programmatically — the GSC UI needs to be
checked directly," never a fabricated "none found."

### Manual Actions (P0)
- **Trigger:** A human Google reviewer found a spam-policy violation (link schemes, cloaking,
  keyword stuffing, doorway pages, scaled content abuse, structured-data spam — see
  `ANTI-PATTERNS.md`).
- **Impact:** Pages, a subdomain, or the entire site can be demoted or fully deindexed. Traffic to
  the affected scope drops to zero, forcing 100% paid-search dependency for that scope.
- **Resolution timeline:** Weeks to months — requires a forensic audit of what triggered it plus a
  reconsideration request; there is no fast path.
- **Prevention:** Never do anything in `ANTI-PATTERNS.md`.

### Security Issues (P0)
- **Categories:** Hacked content, malware/unwanted software, social engineering/phishing.
- **Impact:** Chrome SafeBrowsing warnings block users in-browser before they even reach the site;
  Google Ads campaigns on the domain are immediately disapproved or suspended — this is a
  paid-channel kill switch, not just an organic one.
- **Prevention:** Weekly security scans, automatic backups, CMS/dependency updates, strong access
  controls.

**Phase gate (internal doctrine, retrieved 2026-09-05):** Do not propose or execute *any* content or
technical SEO change until both reports read clean via direct human check. Optimizing on top of an
active manual action or security issue is pointless — fix the P0 first.

---

## Contractor bend

The home-services/contracting GC buyer (see `shared/contractor-buyer-psychology.md`) will never
open Search Console themselves, will not know what "crawl budget" means, and does not care about
the mechanism — they care about "is my phone ringing." Translate every item on this checklist into
a business consequence before presenting it:

- "Crawled — currently not indexed" → "Google found this page but decided it's not worth showing
  people yet — usually means the page needs more real content, not more code."
- Canonicalization bugs → "Google might be confused about which of your pages is the *real* one,
  so it's giving credit to the wrong page instead of building up the one you actually want people
  to find."
- A Manual Action → "Google would remove your entire website from search results for weeks to
  months — this is the single worst thing that can happen to your online presence, worse than a
  bad review."
- Sitemap/robots correctness → "This is the map we hand Google so it knows every page on your site
  exists. If the map points to the wrong address, some of your pages are invisible to search even
  though they're live."

This buyer has likely been sold vague "technical SEO audit" retainers before with no visible
outcome. Every item reported to them should tie to a specific page and a specific, checkable
before/after (position, indexed status, CWV score) — never an unfalsifiable "we improved your
technical health." Weekly/monthly/quarterly cadence items are the *agent's* job, silently, in the
background; this buyer should only ever see a monthly rollup that says what changed and what it's
expected to do, in the same plain-English terms as their own trade (a punch list, not a lab report).
