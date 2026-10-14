# WordPress Safe-Change Protocol

Generalized from a real devops-architecture audit of a page-builder-based WordPress site
(internal doctrine, incident: page-builder WordPress safe-change audit, 2026-09-26). That audit is
concrete evidence that this class of failure is real, not hypothetical — the mechanism below is the
company-agnostic doctrine it implies. No company name, domain, or account fact from that audit
appears below; every example is generic.

**Governing shared doctrine:** this file specializes `shared/web-dev-safety.md` for the
WordPress-equivalent platform shape. Where the two conflict, `shared/web-dev-safety.md` wins per
`shared/INDEX.md`'s conflict rule — in particular its Rule 6 hard-stop ("no staging environment/
verification path exists" is a stop, never a license to pilot on production) governs §5 below.

## Why this file exists

A managed WordPress site (page builder + host-level caching + a hosting-management layer, whether
that's an agency, a freelancer, or a managed-hosting provider's own remote-admin tooling) fails in
a specific, recurring shape: **a change saved in wp-admin is not the same thing as a change the
public can see**, and **a change nobody can point to a recovery path for is not a change that
should be made**. Both failures are structural, not operator error — they follow from how
WordPress page builders store content and how multi-layer caching works, and they recur across
unrelated sites built the same way. [KB-WEBOPS-003] A single-site WordPress installation's
Administrator role has every capability needed to install/delete plugins and themes, edit theme
and plugin files, and manage all users — nothing below Administrator can do any of this (official,
WordPress.org Documentation, "Roles and Capabilities," retrieved 2026-09-27, cited in full in
`wordpress-security-backups-plugins.md` §1). A site with two Administrators — the site's own team
and an external agency/freelancer/host account — has two parties who can independently make an
irreversible change, and neither can single-handedly guarantee the other's changes are recoverable.

## 1. Classify every change before touching anything

Not every change carries the same risk. Classify first; the class determines the gate. (The
Class O/Class H framework below is `(internal doctrine, retrieved 2026-09-27)` — a general,
portable classification this corpus asserts, not a specific vendor's documented behavior.)

- **Class O (reversible from what you hold today).** The change is confined to content you can
  export, re-import, or re-publish yourself, **and its effect is not independently cached or acted
  on by anything outside the site itself**: a single page's body content (for a page-builder-
  rendered page, only once §2's "before-state must capture the builder's own data" test is met —
  otherwise treat it as Class H), a draft/publish toggle. You hold a working undo path without
  needing anyone else, and reverting the underlying record actually undoes the visible effect for
  everyone who might have seen it.
- **Class H (needs a host-level or third-party-controlled backup, OR is externally propagated).**
  The change touches something that only a full site/database backup can undo — a global template,
  header, footer, or reusable block used across many pages; a site-wide find-and-replace across the
  database; anything that edits `robots.txt` or another file that lives on the server filesystem,
  not in the database; deleting media; a plugin or core update — **or the change's effect is cached
  or acted on outside the site's own database**, even though the underlying setting itself is
  trivially revertible: a redirect rule, a per-page SEO/`noindex` setting, a canonical or robots
  change. A 301 response is heuristically cacheable by browsers and intermediaries when no explicit
  `Cache-Control` is set (RFC 9110 §15.4.2, "301 Moved Permanently," official, retrieved 2026-09-27:
  https://www.rfc-editor.org/rfc/rfc9110#section-15.4.2 — the RFC defers the actual
  heuristic-freshness lifetime to RFC 9111 §4.2.2 and states no unbounded or indefinite lifetime
  itself; "browsers commonly cache 301s for a long time in practice" is a separate, weaker claim,
  `(internal doctrine, retrieved 2026-09-28)`, not itself stated by the RFC), and
  search engines act on a 301 or a `noindex` flip by re-crawling and re-indexing on their own
  schedule — reverting the database row does not undo either effect for a visitor or a crawler that
  already saw it. See §4 for the redirect-specific mitigation (pilot with a 302/307 first).

**The test for which class a change is in:** if you can articulate the *exact* steps to undo it
right now, using only tools/exports you already possess, **and that undo actually reaches everyone
who has already seen the change** (not just resets the database), it's Class O. If your answer is
"we'd restore from a backup," or the change's effect is cached or acted on by something outside the
site (a browser, a CDN, a search engine) that a database revert cannot reach, it's Class H — and
Class H work does not start until §6's gate clears.

## 2. Map where content actually lives before editing it

A page builder (Elementor, Breakdance, Divi, Beaver Builder, etc.) typically stores a page's real
rendered content as structured data in post metadata — not in the classic WordPress "content"
editor field, which may hold a stale copy from before the site adopted the builder. **Editing the
wrong layer is a silent no-op**: you save something, it looks right in the editor, and the public
page never changes, because the builder's data field — not the classic content field — is what
actually renders.

Before any content edit, identify:
1. **What actually renders this element** — a page-specific builder field, a shared global
   template/header/footer/reusable block, or a plugin's own settings table (an SEO plugin's
   business-listing fields, for example, live in the SEO plugin's own options, not in any page).
2. **How many places carry a copy of the same fact.** The same string (a phone number, an
   address, a claim) frequently exists in more than one place at once: the live page-builder data,
   an old classic-editor copy, a previous builder's leftover data (if the site migrated builders),
   and a global template or block reused across pages. A search-and-replace that only checks the
   classic content field can report "0 matches" while the string is still live everywhere, because
   it never looked at the field that actually renders.
3. **Whether editing that layer is even possible for the account doing the work.** It is common
   for a site's own administrative user to be technically an Administrator but *blocked* from
   editing global templates, headers, footers, and reusable blocks by the page builder's own
   internal permission system — a restriction the page builder enforces, separate from and
   invisible to WordPress's own role system. Confirm this before promising a timeline for a
   template-level change.
4. **For a builder-rendered page, whether your before-state export actually captures the builder's
   own data.** A plain content export commonly omits the exact metadata field a page builder
   actually renders from (`wordpress-security-backups-plugins.md` §3 trap 2), so it looks like a
   legitimate export while being useless as a restore source. Before treating a builder-rendered
   page as Class O (§1), confirm the before-state is the builder's own export/template export, or
   that revisions are confirmed on per `WP_POST_REVISIONS` (`wordpress-security-backups-plugins.md`
   §4). If neither is confirmed, treat the change as Class H regardless of how simple the edit looks.

## 3. Map the caching stack before verifying anything

A managed WordPress host commonly stacks **two to three independent caching layers** between
wp-admin and a visitor's browser: an application-level page-cache plugin, a server-level page
cache the host runs, and a CDN/edge cache in front of that. [KB-WEBOPS-002] A managed WordPress
host's documented caching architecture separates a server-level full-page cache from an
edge/CDN cache layer, and explicitly notes that a theme or plugin's *own* built-in cache is managed
independently of the host's caching and must be cleared separately (official, Kinsta Docs,
"WordPress Hosting — Caching," retrieved 2026-09-27:
https://kinsta.com/docs/wordpress-hosting/caching/). **This is the mechanism, not a
vendor-specific quirk — any host or CDN combination that layers caching has the same property**:
each layer can independently continue serving a stale copy after you have changed the setting, the
content, or the file, until *that specific layer* is cleared.

**The operational consequence:** "I saved it in wp-admin and it looked right when I reloaded the
page" is not verification. The reload that "looked right" was very likely served from wp-admin's
own no-cache session context, or from a cache-busted preview — not the same response an anonymous
visitor gets. A change is not verified until you have fetched the *public* URL, cache intact, and
seen the new value.

**Clearing order:** clear the innermost layer first and the outermost last, so each clear doesn't
just get immediately re-filled from a stale copy sitting in a layer you haven't cleared yet — a
plugin-level cache, then the host's server-level cache, then the CDN/edge cache. [KB-WEBOPS-002]
directly supports clearing a theme/plugin-level cache before the host's own layer; the full
inner-to-outer ordering through the CDN/edge layer is `(internal doctrine, retrieved 2026-09-27)` —
generalized from that same source's layering description, not itself stated by it. Confirm the
exact layer names and clearing order for the host/CDN combination actually in use before assuming
this generic three-layer order applies as-is.

**Static-file caching is a distinct, longer-lived trap.** Images, CSS, and JS assets are commonly
cached for a year or more at the edge and in visitors' browsers, keyed by filename (internal
doctrine, retrieved 2026-09-27 — the same content-hashed-filename mechanism `static-site-ops.md` §2
cites to web.dev's HTTP-caching guidance applies here; WordPress has no automatic filename-hashing
step, which is exactly why the discipline below must be manual). Re-uploading a file under the
*same* filename (replacing a logo, swapping a hero image) does not reliably reach visitors who
already have the old file cached — always publish a *new* filename for any static asset
replacement, and treat "swap this image in place" as a request that will not do what it sounds like
it does.

## 4. Never treat a redirect or setting change as instant — and never classify one as Class O

A redirect rule, `noindex` flip, or other settings-table change is Class H, not Class O (§1),
because its effect propagates outside the site's own database: a 301 response is heuristically
cacheable by browsers and intermediaries (RFC 9110 §15.4.2, "301 Moved Permanently," official,
retrieved 2026-09-27: https://www.rfc-editor.org/rfc/rfc9110#section-15.4.2 / RFC 9111 §4.2.2, which
governs the actual heuristic-freshness lifetime — the RFC states no unbounded or indefinite lifetime
itself; treat "browsers commonly cache 301s for a long time in practice" as a separate, weaker claim,
`(internal doctrine, retrieved 2026-09-28)`), and a search engine acts on a 301 or
`noindex` by re-crawling and re-indexing on its own schedule, entirely outside the site's control.
Reverting the database row does not undo either effect for a visitor or a crawler that already saw
it — the same layered-caching problem §3 describes for content applies here, plus a second,
externally-propagated layer that a database revert cannot reach at all.

**Mitigation:** pilot a new redirect as a temporary 302/307 first and verify it resolves correctly
before switching it to a permanent 301 — a 302/307 is not supposed to be cached long-lived, so a
mistake is cheaper to walk back. Set an explicit `Cache-Control` on redirect responses where the
host/CDN configuration allows it, rather than relying on the default heuristic behavior. Treat
every redirect/settings change with the same verify-the-public-response discipline as §3, and never
call a redirect batch complete until you've confirmed both the added and the removed forms of the
URL resolve correctly, post-cache-clear, from an anonymous request.

## 5. The six-step pre-flight, every change, no exceptions

0. **Staging first, always, no exceptions** — per `shared/web-dev-safety.md`'s core principle,
   which governs this file on conflict. Use the host's staging environment (most managed WordPress
   hosts offer one-click staging with a push-to-live promotion step) or a local clone; verify the
   change there before it ever touches production. **A staging DB push can overwrite live-only data
   captured since the staging copy was made** (form entries, orders) — the same unscoped-restore
   trap §6 describes for a full-site restore — so prefer a files-only or selective-table push when
   promoting staging work, and export any live-only data first if a full push is unavoidable. **If
   no staging environment or verification path exists for this site, that is a hard stop** per
   `shared/web-dev-safety.md` Rule 6 — escalate; it is never a license to pilot directly on
   production instead.
1. **Classify** the change (§1). Class H stops here until the backup gate (§6) clears.
2. **Capture a before-state** you can point to without ambiguity: an export of the affected
   content type, full HTML + response headers of every URL the change touches, and screenshots at
   a desktop and a mobile width. A "the site looked fine before" recollection is not a captured
   before-state. **For a builder-rendered page, the export must capture the builder's own data**
   (§2's before-state test) — a plain content-type export that omits the builder's rendering field
   does not count, even though it looks like a legitimate export.
3. **Pilot on a small slice** — one page, or a handful of rows — on staging before applying the
   change at scale. Verify the pilot fully (§3's public-response check, run against the staging
   URL) before continuing.
4. **Apply the rest in bounded batches**, not as one unreviewable bulk operation. A batch that is
   too large to individually verify is a batch you cannot safely roll back from if something in it
   is wrong.
5. **Clear caches inner-to-outer (§3), then verify from a genuinely public, anonymous request** —
   not a wp-admin reload, not a browser that was just logged in and may be serving a
   session-specific bypass. Verified means this public check passed on staging; only after that
   does the change promote to production, via the operating contract's own ask-gated deploy
   process, and the same public-response check is then re-run against the production domain itself
   before the change counts as done.

## 6. The Class H gate: what must be true before a hard-to-reverse change proceeds

Do not start a Class H change until all of the following are true:

- Someone who actually holds host-level backup/restore access has confirmed a **specific, dated**
  backup exists — not "we have backups" in the abstract, but a named backup you could ask to be
  restored from today.
- That person (or an equivalent restore path you control directly) is reachable during the change
  window. A change made on a Friday evening with nobody able to restore until Monday is a change
  that will sit broken all weekend if something goes wrong.
- You have exported everything Class O covers for the same content, so a host-level restore
  (which typically rolls back the *entire* database, undoing unrelated recent activity too — see
  below) doesn't also erase legitimate new data.

**A host-level restore is not a scoped undo.** Restoring a full site/database backup reverts
*everything* in that backup's scope back to that point in time — including anything unrelated that
happened since, most importantly any form submissions, leads, comments, or orders captured in the
interim. Before requesting any host-level restore, export whatever transactional data has
accumulated since the backup point, or you will silently destroy it.

## 7. Something else can write to the same site while you're not looking

A managed-hosting or site-management layer (a monitoring/backup service, a managed-WordPress
host's own remote administration panel, an agency's maintenance retainer) frequently has standing
permission to update plugins, update core, restore backups, and clear caches *on its own schedule*,
independent of any single change you're making. Two consequences:

- A cache that clears itself, or a plugin that updates itself, at an unpredictable time can make a
  verification you ran five minutes ago no longer describe the site's current state. If verifying
  a change happens well after it's applied, re-verify rather than trusting an earlier check.
- Ask whoever controls that layer to pause standing updates during your change window, and get a
  yes before you start — an update landing mid-change is indistinguishable, from the outside, from
  your own change having broken something.

Before any change window, confirm the site's actual core auto-update setting (the
`WP_AUTO_UPDATE_CORE` value, or the install-type default if unset) and whether a plugin's own
security posture could still trigger a forced emergency update outside owner opt-in
(`wordpress-security-backups-plugins.md` §5) — a background core or plugin update is exactly the
kind of "something else wrote to the site" event this section exists to catch.

## 8. Domain, DNS, and licenses are single points of failure that outlive any one change

A domain registrar account, a DNS zone, and paid plugin/theme licenses are commonly controlled by
whoever originally set the site up — sometimes a different party than whoever currently
administers WordPress day-to-day. This is not a per-change risk but a standing one worth
surfacing once, in writing, to whoever owns the business relationship: know who holds the
registrar login, know whether the DNS zone that serves the website also carries mail records (a
DNS-provider change made carelessly can take down email at the same time as the site), and know
which licenses would stop functioning, and what breaks, if a given account access is ever revoked.
This is an ownership/handover question, not a technical one — flag it, do not attempt to resolve
it unilaterally.

## 9. Stop-and-roll-back conditions

Stop immediately and begin rollback (per the change's own classification) if, after applying a
change (the conditions below are `(internal doctrine, retrieved 2026-09-27)`):

- Any key page returns something other than the expected response code.
- The page's rendered HTML shrinks significantly against the pre-change capture — a sign that a
  section failed to render, not that the page genuinely got shorter.
- A tracking/analytics tag that was present before the change is now missing on any page it should
  still be on.
- A form that worked before the change stops producing a test submission within a reasonable wait.
- A visual diff shows changes outside the area you intended to touch.

Roll back per the change's classification, clear caches per §3, and verify again before declaring
the rollback complete. A rollback that has not itself been verified through a public request is not
confirmed to have worked.

## Contractor bend

For home-services/contractor companies, the owner-buyer generally does not administer their own
WordPress site day to day — they pay someone (an agency, a freelancer, a managed host) to do it,
and they experience this protocol only as "the website looked right yesterday and it looks right
today, or it broke and got fixed fast." The stakes of this file are entirely about protecting that
experience: a public site that goes visibly wrong, even briefly, is disproportionately damaging for
a buyer who is already inclined to distrust vendors that "move fast and break things." Never treat
a hard-to-reverse change as routine because it's technically simple to execute — the ease of making
a change and the ease of undoing it are frequently unrelated, and this protocol exists specifically
because that gap is where real incidents happen.


## Field notes: page-builder sites, SEO plugins, caches and structured data (added 2026-09-28)

- **[KB-WEBOPS-014] Edit a JavaScript page builder through its own data store, not the rendered DOM.**
  Read and write element properties through the builder's store API and save with its own Save
  control. DOM edits are lost or corrupt the saved document (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-WEBOPS-015] Guard every batch text edit.** Apply all replacements to local copies first,
  require every planned replacement to match, scan the whole page for leftover forbidden strings,
  and only then write and save. Stored HTML often differs from the plan (`&nbsp;`, spacing, list
  markup), and this guard stops a half-edited page from being saved (internal doctrine, retrieved 2026-09-28).
- **[KB-WEBOPS-016] Snapshot and compare every edited page:** HTTP status, form markup unchanged,
  form count, phone links, tag-manager and pixel present, visible-text diff. Diff against the no-cache version first (the cached copy lags for
  minutes after a purge while the cache pre-loads); the change is verified only from the public,
  cached URL (§3) (internal doctrine, retrieved 2026-09-28).
- **[KB-WEBOPS-017] Hiding is not fixing.** A CSS rule that hides a wrong address or claim leaves it in
  the HTML, in search results and in structured data. Edit the text itself, then crawl the rendered
  HTML for the string, including every `application/ld+json` block, and check each block still parses.
  Plugins (review plugins, snippet plugins, SEO plugins) each keep their own schema settings (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-WEBOPS-018] Unpublish = a redirect (piloted as 302/307, then 301, per §4) + Draft, never
  delete.** The redirect passes the old URL's
  ranking and links to the kept page; Draft keeps the content recoverable; Trash renames slugs and
  auto-empties. Use 410 with an empty destination only for pages that should vanish from search (internal doctrine, retrieved 2026-09-28).
- **[KB-WEBOPS-019] SEO-plugin gotchas (observed on one popular WordPress SEO plugin):**
  - a redirect CSV import merges rows that share a destination into one redirect object;
  - drafted posts stay in the XML sitemap until its cache is flushed;
  - saving the plugin's titles/meta settings can drop rewrite rules, so `sitemap_index.xml` and
    `llms.txt` return 404 until Settings > Permalinks is re-saved with no change.

  After ANY SEO-plugin settings save, request both URLs and re-save Permalinks if either is not 200 (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-WEBOPS-020] Keep every structured-data source identical.** When two plugins each emit an
  Organization/LocalBusiness block, their name, address and `sameAs` must match. The stable Google
  Maps profile URL for `sameAs` is `https://www.google.com/maps?cid=<cid>`, where the CID is the
  `fid` value in the Business Profile manager URL (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-WEBOPS-021] Purge caches in order:** the page-cache plugin first (purge and preload), then the
  host's own cache, then the CDN/edge cache (§3). Header/footer menus are templates too; retire their links with a normal builder
  save. Crawl the published pages for stray test pages, which can embed staging widgets and sit in
  the sitemap (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **[KB-WEBOPS-022] WordPress REST from a logged-in admin tab:** get a nonce from
  `admin-ajax.php?action=rest-nonce` or `wpApiSettings.nonce`. Some sites echo junk before the JSON,
  so parse from the first `{`/`[` and re-read the resource instead of trusting the write reply (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
