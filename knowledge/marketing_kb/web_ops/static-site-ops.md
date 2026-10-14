# Static-Site Ops

Doctrine for a marketing site built as a static or pre-rendered site (a static-site generator, a
build step that emits plain HTML/CSS/JS to a `dist/`-style output directory, served from a CDN or
static host) — the structural counterpart to `wordpress-safe-change-protocol.md` and
`wordpress-security-backups-plugins.md`, which cover a database-backed CMS instead. Company-agnostic;
every example below is generic. A GTM seat working on a company whose marketing site is static-built
reads this file instead of the two WordPress files; a company running WordPress reads those instead
of this one; a company running both (a static marketing site plus a separate WordPress blog, for
example) reads whichever file matches the specific surface being touched.

## Why a static site is a different risk shape, not just "simpler"

A database-backed CMS (WordPress, and equivalents) fails in the ways
`wordpress-safe-change-protocol.md` describes: content lives in a database that a builder plugin
renders from, multiple cache layers sit between a save and a visitor seeing it, and a second party
(a host's management layer) can write to production independently of any one change. A static site
removes an entire failure class by construction — **there is no live database render step and no
"a change saved in the admin panel is not yet public" gap**, because there is no admin panel: the
published output is exactly the files the build step produced, and nothing renders differently at
request time based on stored state. This does not make a static site risk-free; it relocates the
risk to a different set of failure modes, listed below, that a team used to WordPress's failure
shape can easily miss because they are watching for the wrong thing.

## 1. The build step is the new single point of truth — and the new single point of failure

Because there is no live render step, **the only way content reaches production is through the
build.** This has two consequences that don't exist on a database-backed CMS:

- **A change that never runs through the build never reaches production**, no matter how correct it
  looks in source control. There is no equivalent of "it's saved in wp-admin, it just hasn't cleared
  cache yet" — if the build didn't run, or ran against the wrong source commit, the live site is
  simply still serving the old output. Verification therefore always means checking the *deployed*
  output, not the source files that fed the build.
- **A build that partially fails can still deploy a partially-stale site.** If a build pipeline emits
  output incrementally, or a deploy step publishes an output directory before every page finished
  generating, a visitor can receive a mix of old and new pages with no error surfaced anywhere. Treat
  a build's own reported exit status as necessary, not sufficient — confirm the actual page count and
  a sample of pages in the deployed output match what the build was supposed to produce.

**The undo path for a static site is source control, and only source control.** Because the
deployed output is a pure function of the build input, `wordpress-safe-change-protocol.md`'s Class
O/Class H distinction collapses into a single, simpler rule here: if the change is committed and the
previous commit's build is known-good, rolling back is re-running the build from the prior commit
(or re-deploying the prior build artifact, if the deploy pipeline retains one) — a real, mechanical,
self-held undo path for *every* content and code change, not just a subset. This is a structural
advantage over a database-backed CMS's Class H changes, which frequently have no self-held undo path
at all. Confirm before relying on this that the deploy pipeline actually retains prior build
artifacts or makes re-running an old commit's build trivial — a pipeline that only ever builds and
deploys the current `HEAD` with no retained history of prior deployed artifacts has a weaker
rollback story than the source-control history alone suggests, because reproducing an old build
exactly can depend on pinned dependency versions, environment variables, or external data fetched at
build time that may no longer resolve the same way later.

## 2. Cache-busting is still required, just for a smaller, more predictable set of assets

A static site removes the multi-layer page-cache problem `wordpress-safe-change-protocol.md` §3
describes (there is no page cache to desync from a database, because the page *is* the cached
artifact), but it does not remove caching entirely — CDN and browser caching of the deployed files
themselves still applies, with the same trap: **re-deploying a file under its existing filename does
not reliably reach a visitor whose CDN edge node or browser already cached the old version at a long
TTL.**

[KB-WEBOPS-012] The standard, platform-agnostic fix used across static-site tooling is
**content-hashed (fingerprinted) filenames**: a build step names each generated asset (a CSS bundle,
a JS bundle, an image) with a hash of its own content baked into the filename (e.g.
`main.a1b2c3d4.css`), so that any change to the file's content necessarily produces a new filename.
Google's own developer documentation states the resulting rule directly: "When responding to
requests for URLs that contain 'fingerprint' or versioning information, and whose contents are never
meant to change, add `Cache-Control: max-age=31536000` to your responses," and further recommends
adding the `immutable` directive "as a further optimization, though it will be ignored in some
browsers"; it also notes that "build tools like webpack can automate the process of assigning hash
fingerprints to your asset URLs" (official, web.dev, "Prevent unnecessary network requests with the
HTTP Cache," retrieved 2026-09-27: https://web.dev/articles/http-cache). A long, aggressive
cache-control lifetime (a year or more) is safe specifically because the filename itself changes
whenever the content does — the browser or CDN cache is never asked to serve stale content under a
name that now means something different. **This is the direct static-site equivalent of
`wordpress-security-backups-plugins.md`'s and `wordpress-safe-change-protocol.md`'s "always publish
a new filename for a replaced image" rule** — the mechanism is identical (a cache keyed to a
filename can't tell the difference between "this filename never changes" and "this content never
changes" unless the filename itself encodes the content), it's simply automated by the build tool
here instead of requiring a human to remember it.

**The entry-point HTML file is the one thing that must NOT be cached the same way.** [KB-WEBOPS-012]
The same source is explicit that HTML is the opposite case: "every web application needs HTML
files — those files are (almost!) never going to include versioning information," and the
recommended directive for them is `no-cache`, which "instructs the browser that it must revalidate
with the server every time before using a cached version of the URL" (official, web.dev, same
source as above, retrieved 2026-09-27). The page `index.html` (or any page's own HTML file)
references the hashed asset filenames, so it must always be fetched fresh — if the HTML itself is
cached at a long TTL, a visitor can be served an old page that still points at asset filenames from
a prior deploy, some of which may no longer exist in the current deployed output. Confirm the
CDN/host configuration applies `no-cache` (revalidate-always) to HTML specifically and a long,
immutable lifetime to content-hashed assets specifically — a single blanket cache-control setting
applied to the whole `dist/` output is a common misconfiguration that reintroduces the exact
stale-content problem hashing was meant to solve, just at the HTML layer instead of the asset layer.

## 3. Deploy previews and a genuinely public verification step

Because there is no wp-admin session to confuse with a public view, static-site verification avoids
one WordPress trap (a logged-in admin's cache-bypassed reload looking right when the public response
doesn't) — but introduces a parallel one: many static-hosting platforms generate a **deploy
preview** URL for a build before it's promoted to the production domain. Verifying against the
preview URL is not the same as verifying the production domain — a preview deploy can carry
different environment variables, a different base path, or different CDN cache state than what
production will actually serve. Treat a preview-URL check as a useful pre-flight step (catching
build errors before they reach production), never as a substitute for checking the actual production
domain after promotion, mirroring the same "verify the real public response, not a proxy for it"
discipline `wordpress-safe-change-protocol.md` §3 states for cache-cleared verification.

## 4. Redirects and headers live in configuration, not a live settings panel

A static host commonly manages redirects, custom headers (including `Cache-Control` and security
headers), and rewrite rules through a **configuration file checked into the same repository as the
site's content** (a per-platform config file, or a headers/redirects file adjacent to the build
output) rather than through a database-backed settings UI. This is a real advantage — the redirect
map is versioned, reviewable, and rolls back with the same commit-based mechanism as content (§1) —
but it means a redirect change is a code change subject to the same build-and-deploy step as
everything else: it does not take effect until the next successful deploy, and a malformed
redirect-config entry can fail an entire build rather than silently doing nothing (a difference in
failure mode from a database-backed CMS's redirect plugin, where a bad entry more commonly just
fails to match rather than blocking every other page's deploy). Verify a redirect change the same
way as any static-site change (§3): check the production domain's actual response, not the
configuration file's apparent correctness.

## 5. Third-party embeds and tag-manager snippets are still a live runtime surface

A static site removes server-side render-time risk, but any client-side script it loads — a
tag-manager container, a chat widget, a form-embed script, an analytics snippet — still executes
live in the visitor's browser exactly as it would on any other site, and can still be changed
independently of the site's own deploy pipeline if that script is managed through its own separate
platform (a tag-manager's own versioning and publish step, for example). **A static site's own
deploy history does not capture changes made inside a separately-managed tag container** — treat
those as a distinct system with its own change history and its own rollback mechanism, and confirm
which one actually governs a given script before assuming "we redeployed the site" reverted it.

## 6. What does NOT need a security/backup posture rebuild from the WordPress files

`wordpress-security-backups-plugins.md`'s core concerns — a compromised Administrator account
installing a malicious plugin, an out-of-date plugin's known vulnerability, a missing native audit
log — are specific to a CMS with a live admin surface, a plugin ecosystem, and a database. A static
site has none of these attack surfaces in the same shape: there is no admin login to compromise into
arbitrary code execution on the production server, no plugin marketplace introducing third-party
code at runtime, and the "audit log" is source control's own commit history plus the deploy
platform's own build/deploy log — both of which typically already exist without installing anything
extra, unlike WordPress's structural gap (`wordpress-security-backups-plugins.md` §6). The genuine
remaining surfaces are: who has push access to the source repository (the real equivalent of "who
holds an Administrator account"), who can trigger a production deploy independent of a normal
commit-and-build flow, and whether any build-time secret (an API key fetched at build time and baked
into a client-side bundle) is something that should never have been client-visible in the first
place — a static site's JS bundle is fully readable by anyone who requests it, so a secret meant to
stay server-side must never be included in a client-side build, regardless of how it's stored in
source control.

## Contractor bend

For home-services/contractor companies, the owner-buyer experiences a static marketing site exactly the same way they'd experience
any other website: it either looks right or it doesn't, loads fast or doesn't, and stays up or
doesn't. The one place this file's doctrine surfaces visibly to them is speed and reliability — a
well-built static site is typically faster and has fewer moving parts to break than a database-backed
CMS doing the same job, which is a real, if invisible-to-them, advantage worth stating plainly when
recommending a rebuild or a new build: "this will be simpler to keep running correctly," not "this is
more modern," is the honest framing — see `shared/contractor-buyer-psychology.md` on this buyer's low
tolerance for vendor claims that sound like fashion rather than substance.
