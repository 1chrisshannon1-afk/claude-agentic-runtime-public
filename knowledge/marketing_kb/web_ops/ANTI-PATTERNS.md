# Web Ops Anti-Patterns — Things a Seat Must NEVER Do

Every item below is something any GTM seat touching a company's website infrastructure must refuse
to do, even when a founder/operator asks for it directly, even when it would be faster, and even
when "just this once" feels low-risk. Cite this file when refusing. Applies across platforms
(WordPress-equivalent CMS or static-site build) unless an item says otherwise.

---

## 1. Editing production directly with no staging step and no confirmed rollback path

**What it is:** Making a content, template, plugin, configuration, or code change directly against
the live production site/domain without first verifying it on a staging copy or a deploy-preview
URL, and without having confirmed — not assumed — that the change can be undone.

**Why it's banned:** This is the exact mechanism `wordpress-safe-change-protocol.md` §6 and §1 exist
to prevent: a Class H change (one that needs a host-level backup) started with no confirmed,
dated, restorable backup and no reachable restore path is a change that, if it goes wrong, leaves
the site broken for however long it takes to improvise a fix with no real undo path. On a static
site the equivalent failure is skipping the deploy-preview check (`static-site-ops.md` §3) and
promoting an unverified build straight to the production domain.

**Reject example:** Editing a global header template directly on the live WordPress site because
"it's just a text change." **Pass example:** Verifying the change on the host's staging environment
first (`wordpress-safe-change-protocol.md` §5 step 0, per `shared/web-dev-safety.md`'s
staging-first rule), classifying it (Class O vs. Class H per `wordpress-safe-change-protocol.md`
§1), capturing a before-state, piloting on one page there, then promoting and verifying on
production — or, for a static site, confirming the deploy preview looks correct before promoting to
production and confirming the actual production domain afterward.

## 2. Provisioning a standing Administrator/root credential for routine automation

**What it is:** Setting up an agent or automation identity with the WordPress Administrator role
(or an equivalent full-privilege credential on any platform) to do ordinary content-publishing
work, "because it's simpler than figuring out the right role."

**Why it's banned:** [KB-WEBOPS-003]/[KB-WEBOPS-004] The Administrator role is the only single-site
WordPress role that can install/delete/edit plugins and themes, edit theme files directly, and
manage users — none of which routine content work needs — while the Editor role can do the entire
job of publishing and editing content through its own granted capabilities, none of which include
any of that (official, WordPress.org Documentation, "Roles and Capabilities," retrieved 2026-09-27,
cited in full in `wordpress-security-backups-plugins.md` §1). This containment is not absolute if
the credential leaks: Editor's `unfiltered_html` capability is a known escalation path to a viewing
Administrator's own session privileges, which `wordpress-security-backups-plugins.md` §1 explains
and §4's `DISALLOW_UNFILTERED_HTML` constant closes — but that constant is a site-wide,
Class H change in its own right (`wordpress-security-backups-plugins.md` §4), not a routine setting
to flip alongside provisioning; a standing Administrator credential remains the worse baseline
either way, whether or not that constant is in place. A standing full-privilege
credential sitting mostly unused is pure downside: it turns any credential leak, any misdirected API
call, or any prompt-injection-style attack surface into a full-site-compromise event instead of a
content-only one that a second control can still contain.

**Reject example:** Creating the automation user as Administrator "to be safe, in case we need more
access later." **Pass example:** Provisioning the automation identity as Editor (or the
lowest-privilege role that covers the actual job), and escalating to a human with a
higher-privileged account for the specific rare task that genuinely needs it — see
`wordpress-security-backups-plugins.md` §1.

## 3. Trusting a backup, export, or "we can restore" claim that was never personally confirmed

**What it is:** Proceeding with a hard-to-reverse change on the strength of "there are backups" or
"the host does daily backups" without personally confirming a specific, dated, restorable backup
exists and that whoever can trigger the restore is reachable during the change window.

**Why it's banned:** [KB-WEBOPS-006] Verified, structural traps make this claim false in practice
far more often than it's checked: a backup that lives entirely in a third party's account with no
confirmed restore path is unverified from the site owner's side (official, WordPress.org Developer
Resources, "Backing Up Your WordPress Site," retrieved 2026-09-27, cited in full in
`wordpress-security-backups-plugins.md` §3). On top of that — a content export commonly omits the
exact metadata field a page builder actually renders from, making it useless as a restore source
even though it looks like a legitimate export, and a full restore is never scoped — it reverts
everything in its backup window, including legitimate activity (leads, form submissions, orders)
captured since (internal doctrine, retrieved 2026-09-28 — see
`wordpress-safe-change-protocol.md` §2/§6). Acting on an unconfirmed backup is functionally
identical to acting with no backup at all — the difference only becomes visible at the exact moment
it's too late to matter.

**Reject example:** Running a site-wide database find-and-replace because "the host definitely
backs up daily." **Pass example:** Getting a named person who holds host-level restore access to
confirm a specific, dated, restorable backup exists and that they're reachable during the change
window, before starting — the Class H gate in `wordpress-safe-change-protocol.md` §6.

## 4. Treating "it looked right when I reloaded it" as verification

**What it is:** Declaring a change complete because reloading the page in the CMS admin panel, or a
just-refreshed browser tab, shows the expected new content — without checking the actual public,
cache-intact response an anonymous visitor receives.

**Why it's banned:** [KB-WEBOPS-002] A managed host commonly stacks two to three independent
caching layers between the admin panel and a visitor's browser (official, Kinsta Docs, "WordPress
Hosting — Caching," retrieved 2026-09-27, cited in full in `wordpress-safe-change-protocol.md` §3),
and a logged-in admin session frequently bypasses some or all of them (internal doctrine, retrieved
2026-09-28), so "it looks right in wp-admin" and "the public sees the new version" are two
different, independently-verifiable facts that this reload conflates. The same trap exists on a
static site in a different shape: a deploy-preview URL is not the production domain and can carry
different cache state or environment configuration (`static-site-ops.md` §3).

**Reject example:** Marking a per-page noindex change "verified" because the setting shows toggled
on in the CMS panel. **Pass example:** Fetching the actual public URL (a fresh, cache-intact
request, not a cache-busted or admin-session request) and confirming the new value is what's
actually served — `wordpress-safe-change-protocol.md` §3's public-response check.

## 5. Re-uploading a replacement asset under its existing filename

**What it is:** Swapping a logo, hero image, or other static asset "in place" by uploading a new
file under the same filename the old one used, expecting visitors to see the new version
immediately.

**Why it's banned:** Static assets are commonly cached for a year or more at the CDN edge and in
visitors' browsers, keyed by filename — re-using the same filename does not reliably reach a
visitor who already has the old file cached, on either a WordPress-style upload or a static-site
build's own asset pipeline (`wordpress-safe-change-protocol.md` §3's static-file-caching finding
and [KB-WEBOPS-012]'s content-hashing mechanism, `static-site-ops.md` §2 — the fingerprinting
pattern exists precisely because relying on a human to remember a new filename is fragile; a manual
WordPress upload has no such automatic protection, which is exactly why the discipline must be
manual there).

**Reject example:** Uploading `logo.png` over the existing `logo.png` to update a company's branding
and calling the update done once it displays correctly in a private/incognito tab that happened to
not have the old file cached. **Pass example:** Uploading the new logo under a new filename (e.g.
`logo-2026.png`) and re-pointing every reference to it, or — on a static-site build — trusting the
build's own automatic content-hashing rather than hand-managing filenames at all.

## 6. Recommending or performing a database-wide find-and-replace without checking what else it touches

**What it is:** Running a search-and-replace across an entire CMS database to fix one class of
content (an old address, an old phone number, a stale claim) without first confirming what *else*
shares that same database table.

**Why it's banned:** A plain string search-and-replace has no concept of semantic context — it will
happily rewrite the same string wherever it appears, including inside content that must never
change verbatim (customer testimonials/reviews stored in the same table as pages, for example) and
will silently miss format variants of the same fact that don't match the exact search string
(a phone number in three different formats, an address with "Blvd" vs. "Boulevard"). This class of
change is also frequently irreversible without a full host restore (`wordpress-safe-change-protocol.md`
§1's Class H reasoning) — once run, there is no way to distinguish content the replace correctly
changed from content it incorrectly changed, because both now read identically.

**Reject example:** Running one global find-and-replace for an old business address across the
entire database and calling it done. **Pass example:** Enumerating every known variant of the
target string first, confirming which content types/tables are in scope, excluding tables that hold
verbatim customer content (reviews, testimonials), and — for anything not fully reversible — getting
the Class H backup gate cleared first.

## 7. Assuming a static site has no security/backup discipline because "it's just files"

**What it is:** Treating a static-site-generator/pre-rendered site as needing none of this corpus's
discipline because there's no database and no plugin ecosystem to compromise.

**Why it's banned:** A static site removes WordPress's specific attack surfaces (a compromised
Administrator account installing a malicious plugin, an outdated plugin's known vulnerability) but
does not remove the underlying question this whole domain exists to answer — it relocates the risk
to who holds push access to the source repository, who can trigger a production deploy outside the
normal build flow, and whether a build-time secret ends up baked into a client-visible bundle
(`static-site-ops.md` §6). Skipping this domain's discipline entirely for a static site because "it's
simpler" is exactly how a real but differently-shaped risk goes unmanaged.

**Reject example:** Granting broad repository push access to an automation identity with no review,
because "it's just a static site, what could go wrong." **Pass example:** Applying the same
least-privilege reasoning `wordpress-security-backups-plugins.md` §1 uses for WordPress roles to the
static-site equivalent — scoped repository/deploy-trigger access, never a standing broad credential
used for routine work.

## 8. Recommending a plugin, theme, or third-party script install without checking its maintenance status

**What it is:** Installing a new WordPress plugin (or equivalent third-party script on any
platform) to solve an immediate problem without checking when it was last updated or how actively
it's maintained.

**Why it's banned:** [KB-WEBOPS-008] Security research tracking WordPress vulnerability disclosures
indicates a large majority of newly disclosed vulnerabilities are found in third-party plugins, not
core — treat the specific percentage as `UNVERIFIED — seeded, needs derivation` pending re-citation
to a primary source, per `wordpress-security-backups-plugins.md` §5. [KB-WEBOPS-009] Plugin/theme
auto-updates are not on by default for routine releases — each must be individually enabled — though
WordPress's own security team can still force-push an emergency plugin security update outside
owner opt-in for a severe vulnerability (official, WordPress.org Developer Resources, "Upgrading
WordPress," retrieved 2026-09-27, same file §5). An unmaintained-looking plugin (no update in 12+
months, few active installs, an abandoned support forum) is a materially higher risk than an
outdated core version on the same site.

**Reject example:** Installing a plugin to solve an immediate need with no check of its last-updated
date or active-install count. **Pass example:** Checking maintenance status first, preferring an
actively-maintained alternative when one exists, and flagging an existing unmaintained plugin found
during an audit for replacement rather than leaving it "because it still works."

## 9. Publishing hacked or injected content, or ignoring signs of one

**What it is:** Failing to treat unexplained content changes, unexpected redirects, or unfamiliar
new pages as a possible compromise — assuming instead that "someone on the team must have made that
change" without checking.

**Why it's banned:** [KB-WEBOPS-011] Google's own spam policies define and actively penalize
"hacked content" as its own violation category — code injection, page injection, content injection,
and malicious redirects — and a hacked site risks a search-visibility penalty on top of whatever
direct damage the compromise causes, a second, slower-to-notice failure a site owner might not
connect back to the original compromise for weeks (official, Google Search Central, "Spam policies
for Google web search," retrieved 2026-09-27, cited in full in `wordpress-security-backups-plugins.md`
§7). WordPress core ships no native audit log (internal doctrine, retrieved 2026-09-28), so an
unexplained change is frequently unattributable after the fact without a dedicated activity-log
plugin already in place — [KB-WEBOPS-010] closes that gap (third-party, a plugin vendor's own
feature listing, cited in full in `wordpress-security-backups-plugins.md` §6) — which is exactly why
an unexplained change should be investigated as a possible compromise rather than shrugged off, not
assumed innocent by default.

**Reject example:** Noticing an unfamiliar redirect or an unexpected new page and assuming it was a
teammate's forgotten test, without checking who (or what) actually made it. **Pass example:**
Treating any unexplained production change as a possible compromise until the activity log (or, in
its absence, before/after captures and whoever holds access) rules it out, and recommending an
activity-log plugin be installed if none exists, per `wordpress-security-backups-plugins.md` §6.

## 10. Claiming a change is verified without checking the production domain itself

**What it is:** Reporting a change as "done and verified" based on a build succeeding, a deploy
pipeline reporting green, or a preview environment looking correct — without an actual fetch of the
live production URL confirming the change is what a visitor receives.

**Why it's banned:** A build's own exit status is necessary but not sufficient — a partial-failure
deploy can publish a mix of old and new pages with no error surfaced anywhere
(`static-site-ops.md` §1), and a deploy-preview URL can differ from production in cache state,
environment variables, or base path (`static-site-ops.md` §3). "Verified" in this domain means the
public check passed, never "the pipeline said success" or "it looked right in the preview" —
mirroring `wordpress-safe-change-protocol.md` §3 and §5 step 5: a change is verified only by a
public, anonymous, cache-intact fetch, never a wp-admin reload or a preview URL.

**Reject example:** Reporting a redirect batch complete because the deploy pipeline finished with no
errors. **Pass example:** Fetching the actual production URLs (both the old and new forms) after
promotion and confirming both resolve as intended, per `wordpress-safe-change-protocol.md` §3's
verify-redirects discipline, adapted to the static-site deploy flow.

---

## Contractor bend

For home-services/contractor companies, none of the above changes for their buyer, or any
comparable small-business owner with no in-house technical staff — if anything the stakes are
higher, because this buyer has nobody else
watching for a bad web-ops decision before it costs them downtime, a lost lead form, or a
search-visibility penalty. This buyer will never see any of these mechanisms directly and will
never be able to judge whether they were followed — they experience only the outcome: the site
stayed up and leads kept arriving, or it broke and they found out from a customer instead of from
whoever manages their site. When something in this file blocks a shortcut the buyer is asking for
("just make the change, it's simple"), the obligation to hold the line is entirely on the agent —
never assume this buyer will push back on a shortcut being offered, and never let "it's a small
change" be the reason a genuinely irreversible step skips its gate.
