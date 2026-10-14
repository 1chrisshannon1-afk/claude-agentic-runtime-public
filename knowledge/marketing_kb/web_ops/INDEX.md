# Web Ops — Index

Corpus for any GTM seat that touches a company's marketing-site infrastructure directly — the
platform/hosting/CMS layer itself, not the copy, SEO strategy, or conversion design that lives on
top of it (those are `content/`, `seo/`, and `conversion/`'s lanes respectively). This domain
answers "how do I make a change to this website without breaking it or losing the ability to undo
it," for whichever platform the company's site actually runs on. Grep-reachable on demand — read
the file that matches the company's actual platform, not the whole corpus.

**Governing shared doctrine:** [`shared/web-dev-safety.md`](../shared/web-dev-safety.md) is the
cross-domain staging-first/backup-verified/audit-logged rule that covers this same surface at the
department level; per `shared/INDEX.md`'s conflict rule, it wins whenever this domain's own
platform-specific doctrine would say otherwise. This domain's files specialize that rule for a
given platform shape (WordPress-equivalent vs. static-build) — read the shared file first, then the
platform-specific file below for the mechanics.

| File | Answers |
|---|---|
| [`wordpress-safe-change-protocol.md`](wordpress-safe-change-protocol.md) | For a WordPress (or equivalent page-builder + host-cache) site: how to classify a change's reversibility before touching it (staging-gated per `shared/web-dev-safety.md`), where a page builder's real content actually lives vs. where it looks like it lives, how to map and clear a multi-layer cache stack in the right order, and the mandatory six-step pre-flight (staging first) + stop-and-roll-back conditions for every change. |
| [`wordpress-security-backups-plugins.md`](wordpress-security-backups-plugins.md) | How to provision an automation/agent identity on WordPress at the correct least-privilege role (Editor, never Administrator), what Application Passwords do and don't buy you, what a real backup posture requires and the three traps that make a "we have backups" claim false, hardening constants worth knowing, why plugins (not core) are where update risk concentrates, and why a native audit log doesn't exist and what closes that gap. |
| [`static-site-ops.md`](static-site-ops.md) | For a static-site-generator/pre-rendered site instead of a database-backed CMS: why the risk shape is structurally different (the build step is the single point of truth), how content-hashed filenames make aggressive asset caching safe while HTML must stay no-cache, why a deploy-preview URL is not the same as verifying production, and why redirects/headers living in versioned config is a real advantage with its own new failure mode. |
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What a web-ops-touching seat must NEVER do regardless of platform — editing production directly with no staging/rollback path, provisioning a standing Administrator credential for routine automation, trusting a source you have not personally confirmed is restorable, treating "it looked right on reload" as verification, and more, each with the mechanism that makes it a hard no. |

## Which file applies

A company's marketing site runs on exactly one of these shapes at a time (occasionally more than
one surface — e.g. a static marketing site plus a separately-hosted WordPress blog):

- **Database-backed CMS with a page builder and host-level caching** (WordPress + Elementor/
  Breakdance/Divi/etc., or an equivalent CMS+builder+cache stack) → read
  `wordpress-safe-change-protocol.md` first (the change-safety mechanics), then
  `wordpress-security-backups-plugins.md` (the provisioning/backup/plugin posture) before any
  agent identity is set up or any Class H change is proposed.
- **Static or pre-rendered output** (a static-site generator's build step, or any pipeline that
  emits plain HTML/CSS/JS to a `dist/`-style directory served from a CDN/static host, with no live
  database render step) → read `static-site-ops.md`. Do not apply the WordPress files' Class O/
  Class H reversibility framework here without adjustment — `static-site-ops.md` §1 explains why
  it collapses into a simpler rule for this shape.
- **Unknown / not yet confirmed** — do not guess from the visual design of the site. Confirm the
  actual platform first (response headers, page-source comments, a build-artifact check, or asking
  whoever set the site up) before choosing which file's doctrine applies; treat an unconfirmed
  platform as the higher-risk WordPress-equivalent posture until proven otherwise, since the WordPress
  files' backup/rollback gates are the more conservative default.

## House style, restated for anyone editing this corpus

- Every numeric or behavioral claim carries a citation tag — `(official)`, `(third-party)`,
  `(internal-measured)`, `(internal doctrine)`, or `UNVERIFIED — seeded, needs derivation` — with a
  retrieval date, per `shared/citation-style.md`. There is no house-style exemption from this: a
  structural/mechanism claim that this corpus itself asserts as a general, portable rule (e.g. "a
  page builder's data field, not the classic content field, renders the page," or the Class O/Class
  H reversibility framework itself) is tagged `(internal doctrine, retrieved <date>)` per
  `citation-style.md`'s definition of that tag, exactly like a claim that asserts a specific
  vendor's documented behavior is tagged `(official)`/`(third-party)`.
- Every claim in this corpus that carries a citation also carries a stable claim id in the form
  `[KB-WEBOPS-NNN]`, assigned sequentially across every file in this directory (not per-file), so a
  claim can be referenced from another domain's file without restating it. The current highest id
  in use is `[KB-WEBOPS-012]` (`static-site-ops.md`) — the next new claim in this directory is
  `[KB-WEBOPS-013]`. `[KB-WEBOPS-001]` is retired (it duplicated `[KB-WEBOPS-003]`'s same claim
  from the same source under a second id) — do not reassign it; both citing files now reference
  `[KB-WEBOPS-003]` only.
- **No company name, domain, account fact, or platform-specific configuration detail from any real
  audit appears in this corpus.** `wordpress-safe-change-protocol.md` and
  `static-site-ops.md` are generalized from real incident/audit evidence; the evidence proves the
  failure mode is real, not hypothetical, but every example, threshold, and worked scenario in the
  doctrine itself is generic and must stay that way through any future edit.
- Where a primary source could not be reached directly (a platform's own help center or a
  government/regulatory source blocking automated retrieval), the doctrine cites the best reachable
  mirror and marks the claim `UNVERIFIED (primary source unreachable: <url>)` rather than presenting
  it as settled — see `shared/citation-style.md` and `compliance/` for worked examples of this
  pattern in practice.
- Every file ends with a "Contractor bend" section translating the doctrine for a small
  owner-operated home-services/trade business archetype (or, where a file is used across verticals,
  the equivalent local-service or B2B buyer this corpus otherwise targets) — phone-first, no
  in-house technical staff, and generally burned by a vendor or agency before.

## Cross-domain pointers (things adjacent to web ops that belong to a different domain)

- **What content to put on the site, and the words used** — copy, page structure, calls to action —
  belongs to `content/` and `conversion/`, not here. This domain governs *how a change is made
  safely*, never *what the change should say*.
- **Technical SEO mechanics** (crawlability, canonicalization, sitemap correctness, Core Web
  Vitals thresholds, structured data) belong to `seo/` — this domain touches SEO only at the
  operational seam where an SEO-driven change (a redirect batch, a robots-directive edit, a
  per-page noindex flip) must go through the same safe-change discipline as any other site change.
  A redirect's *correctness* (should this URL 301 to that URL) is `seo/`'s call; *how to ship the
  redirect without breaking anything else* is this domain's.
- **Tracking/analytics implementation** (GTM container governance, GA4 event design, consent mode,
  conversion uploads) belongs to `measurement/`. This corpus notes only the narrow overlap where a
  tag-manager snippet is itself part of the site's head code and therefore subject to the same
  change-safety discipline as any other site-wide code injection (`wordpress-safe-change-protocol.md`
  §3's head-code caching note; `static-site-ops.md` §5's tag-container note) — the tag's own
  *contents and firing logic* are `measurement/`'s doctrine, not this domain's.
- **Local-listing platforms** (GBP, Yelp, Angi, Thumbtack, Houzz, Nextdoor, BBB/Apple/Bing) are a
  separate operational surface from the company's own website and belong to `local/` — those
  platforms have their own change-safety and suspension-risk considerations, distinct from a
  self-hosted or self-built site.
- **Compliance-driven site requirements** (HIPAA-regulated marketing content, cookie-consent legal
  requirements, accessibility law) belong to `compliance/`; this domain implements a compliance
  requirement's *mechanics* once decided (how to ship a consent-gated pixel safely) but does not
  decide what compliance requires.
