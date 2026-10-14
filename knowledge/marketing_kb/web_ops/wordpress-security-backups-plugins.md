# WordPress Security, Backups, and Plugin Hygiene

Doctrine for how an agent (or an agency operating on a client's behalf) should be provisioned to
touch a WordPress site, what a real backup posture requires, and how to reason about plugin risk.
Company-agnostic; every example below is generic.

## 1. The agent user must be least-privilege, and least-privilege has a specific shape on WordPress

**Never provision an automation/agent identity as an Administrator.** WordPress ships six roles;
[KB-WEBOPS-003] the Administrator role is the only single-site role with the capabilities to
install/delete/edit plugins and themes, edit theme files directly, and create/delete/promote other
users — every capability an attacker (or a careless automated process) would need to fully
compromise or destroy a site (official, WordPress.org Documentation, "Roles and Capabilities,"
retrieved 2026-09-27: https://wordpress.org/documentation/article/roles-and-capabilities/). An
automation identity does not need any of that to do its actual job of publishing and managing
content.

[KB-WEBOPS-004] The **Editor** role can publish and edit posts and pages — including other users'
posts and pages, categories, links, comments, and (on a single-site install) `unfiltered_html` —
but explicitly cannot install/activate/edit plugins or themes, cannot edit theme files, cannot
manage users, and cannot touch site-wide settings under `manage_options` (official, WordPress.org
Documentation, "Roles and Capabilities," retrieved 2026-09-27, same source as above — see that
page's capability table, where every plugin/theme/user-management/`manage_options` row shows "yes"
only for Administrator and above, "x" for Editor). **Editor is the correct default ceiling for a
content-publishing automation identity**: it can do the entire job of writing, editing, and
publishing pages and posts, and it is directly incapable of installing a plugin, deleting another
user, or changing a site-wide setting through its own granted capabilities.

**This containment is not absolute, and the gap runs through `unfiltered_html`.** A single-site
Editor's `unfiltered_html` capability lets it store arbitrary script in a post or page. That script
then executes in an Administrator's own browser session the next time the Administrator views or
edits the affected content — a classic stored-XSS-via-session escalation path, and a well-known one:
a compromised Editor credential can use it to act with the Administrator's own session privileges,
including installing a plugin or creating a new admin user, entirely through the victim
Administrator's browser rather than through any capability the Editor role was granted directly. So
"Editor cannot install a plugin" is true of the role's own capability grant; it is not the same
claim as "a compromised Editor credential cannot lead to a plugin being installed" — the second
claim is false when `unfiltered_html` and an Administrator who will view the content are both
present. §4's `DISALLOW_UNFILTERED_HTML` constant is the recommended control that closes this
specific gap for any automation identity provisioned as Editor — but it is not a small companion
setting to flip alongside provisioning: it is a site-wide `wp-config.php` constant that removes
`unfiltered_html` from *every* user on the install, Administrators included, and can break an
existing human workflow that depends on posting raw HTML (a page-builder widget, a custom-code
embed). Treat enabling it as a Class H change (`wordpress-safe-change-protocol.md` §1/§5/§6): test
on staging first and confirm no builder widget or embed a human editor relies on breaks, rather
than flipping it in production as a routine part of setting up the automation identity. Where a
site-wide flip would disrupt human editors, prefer a custom role that lacks `unfiltered_html` scoped
to the automation identity alone, over the blanket constant.

**When a task genuinely needs more than Editor** — a page-builder's own template/header/footer/
global-block editing is commonly gated by the *builder's own* internal permission system, not
WordPress's role system, and may be denied even to an Administrator by policy choice, separate
from this question entirely (see `wordpress-safe-change-protocol.md` §2) — that is a signal to get
a human with the higher-privileged account to make that specific edit, not to escalate the
automation identity's standing role. A standing Administrator credential used for routine content
work is a standing full-compromise blast radius sitting unused 99% of the time.

## 2. Application Passwords: the correct authentication mechanism, and its real limits

[KB-WEBOPS-005] WordPress core (since 5.6) supports Application Passwords: a per-application
credential generated from a user's own Edit User screen, used over HTTPS via Basic Authentication
against the REST API, stored as a distinctly-named, individually revocable entry — each one is
tracked separately and can be revoked on its own without touching any other application password
the same user has issued (official, WordPress.org Developer Resources, "Authentication," and the
core Application Passwords integration guide, retrieved 2026-09-27:
https://developer.wordpress.org/rest-api/using-the-rest-api/authentication/#application-passwords
and https://make.wordpress.org/core/2020/11/05/application-passwords-integration-guide/).

**What this buys you:** a named, individually-revocable credential for exactly one integration
(the agent's own access), so revoking it if the credential ever leaks does not affect the human
user's own password or any other integration's Application Password.

**What it does not buy you** — and this is the limit that most affects an automation identity's
threat model: [KB-WEBOPS-005] as of the core integration guide's own published roadmap, an
Application Password inherits the *full* role/capability set of the user it belongs to — there is
no native way to scope one down to "this application password may only do X" independent of the
user's own role (same source as above; the guide names finer per-credential scoping as a
*future* direction, not a shipped capability). **This is exactly why role selection (§1) is the
real control, not the Application Password mechanism by itself**: an Application Password issued
to an Editor-role user is bounded by Editor's capabilities; the same mechanism issued to an
Administrator-role user is bounded by nothing. Provision the least-privilege *user* first, then
issue that user's own Application Password to the agent — never provision an Administrator user
"because it's simpler" and rely on some other layer to restrain what the automation actually does.

## 3. Backups: what a real backup posture requires, and the traps that defeat it

[KB-WEBOPS-006] WordPress.org's own backup guidance: back up both the files (core, themes,
plugins, uploads, configuration) *and* the database — "you need both to be able to fully restore a
typical WordPress site" — keep at least three backups on file, stored in different places and on
different mediums (not only on the hosting server itself), and periodically verify that
automated/scheduled backups are actually succeeding by testing one manually rather than trusting
that a backup schedule is silently working (official, WordPress.org Developer Resources, "Backing
Up Your WordPress Site," retrieved 2026-09-27:
https://developer.wordpress.org/advanced-administration/security/backup/). **Backup frequency
scaling with how often the site changes** — a low-activity brochure site can reasonably back up
weekly, a site with a working blog, e-commerce, or frequent form submissions should back up daily —
is `(internal doctrine, retrieved 2026-09-27)`, not itself stated by the cited source; re-cite to a
source that states it directly if one is found, or keep as doctrine.

**Three traps that make a "we have backups" claim false in practice:**

1. **A backup you cannot restore is not a backup.** If a backup lives entirely in a third party's
   account (a hosting-management layer, a maintenance vendor's own tooling) and nobody on the
   site-owner's side has confirmed they can actually trigger and receive a restorable copy, the
   backup's existence is unverified from the site owner's perspective — treat it as absent until
   confirmed otherwise.
2. **A content export is not a database backup.** Exporting individual pages/posts through the
   REST API or an admin "export" screen commonly captures only a subset of a record's metadata —
   for a page built with a page-builder plugin, a plain content export can omit the specific
   metadata field the builder actually renders from entirely, making the "export" useless as a
   restore source for that content. Confirm what a given export tool actually captures before
   relying on it as a Class O recovery path (see `wordpress-safe-change-protocol.md` §1).
3. **A restore is not scoped.** Restoring a full site/database backup reverts everything in its
   scope to that point in time, including legitimate activity that happened after the backup —
   most importantly form submissions, orders, and comments. Never request or perform a full
   restore without first exporting whatever transactional data has accumulated since the backup
   point.

## 4. wp-config.php hardening constants worth knowing (and their tradeoffs)

[KB-WEBOPS-007] WordPress supports several `wp-config.php` constants relevant to reducing the
blast radius of a compromised or over-privileged account (official, WordPress.org Developer
Resources, "wp-config.php" reference page, retrieved 2026-09-27:
https://developer.wordpress.org/apis/wp-config-php/):

- **`DISALLOW_FILE_EDIT`** (set to `true`) removes the built-in plugin/theme file editor from
  wp-admin entirely — "to prevent overzealous users from being able to edit sensitive files." This
  closes one of the fastest paths from "compromised low-privilege account" to "arbitrary PHP
  execution" and has no legitimate workflow cost for a site that doesn't hand-edit theme/plugin
  files through the admin UI (which should be essentially every managed site — code changes belong
  in version control, not a browser textarea).
- **`DISALLOW_FILE_MODS`** (set to `true`) additionally blocks plugin/theme installation and
  update from the admin area entirely — a stronger, and more disruptive, lock: it also blocks the
  legitimate "click update" workflow non-technical site owners rely on for plugin patching, so
  weigh it against §5's update-cadence guidance before recommending it broadly. It also disables
  WordPress's own background automatic updater entirely, including core security releases, not just
  the admin-UI "click update" button — a site running with this constant set gets no automatic core
  security patching either, so pair it with a deliberate manual update cadence rather than assuming
  core will keep patching itself in the background (`UNVERIFIED — seeded, needs derivation`: this
  interaction is inferred from §5's `AUTOMATIC_UPDATER_DISABLED`/`auto_update_$type` mechanics, not
  itself stated by the wp-config.php reference page for `DISALLOW_FILE_MODS` specifically; confirm
  directly before relying on it).
- **`WP_POST_REVISIONS`** controls how many revisions of a post/page are retained (`false` disables
  revisions entirely; an integer caps the count). This is unrelated to security but directly
  relevant to `wordpress-safe-change-protocol.md`'s recovery-path question: confirm what this is
  set to before assuming "the builder probably keeps revisions" as a Class O recovery path — it may
  not.
- **`WP_AUTO_UPDATE_CORE`** governs whether WordPress core installs updates in the background —
  see §5.
- **`DISALLOW_UNFILTERED_HTML`** (set to `true`) removes the `unfiltered_html` capability from every
  role that would otherwise hold it on a single-site install, Editor included (`UNVERIFIED — seeded,
  needs derivation`: neither the wp-config.php reference page nor the WordPress.org Hardening page
  documents this constant as of 2026-09-28; re-cite to a source that states it, or confirm by direct
  test, before relying on this claim). This closes the stored-script-via-Administrator-session
  escalation path §1 describes — but it is a **site-wide constant, applying to every user including
  Administrators**, not a scoped setting for just the automation identity. Treat enabling it as a
  Class H change (`wordpress-safe-change-protocol.md` §1/§5/§6): test on staging first and confirm no
  human editor's page-builder widget, custom-code block, or embed that depends on posting raw
  HTML/script breaks — the cost falls on every human editor too, not only on the automation identity
  losing a capability it has no legitimate reason to use anyway. Where the job genuinely needs raw
  HTML for the automation identity, or where the site-wide flip would disrupt human editors, prefer a
  custom role without `unfiltered_html` scoped to the automation identity alone over the blanket
  constant.

## 5. Update cadence: plugins are where the risk actually lives

[KB-WEBOPS-008] Independent security research tracking WordPress vulnerability disclosures reports
that the large majority of newly disclosed WordPress vulnerabilities are found in third-party
plugins, not WordPress core itself. This claim is currently `UNVERIFIED — seeded, needs
derivation`: the wp-scan.org source previously cited here is not WPScan (wpscan.com, the actual
WordPress vulnerability database) — its own page metadata lists a 2024 founding date and it reuses
WPScan's branding, which makes it an unverified secondary source, not a citable aggregator of
WPScan's data. Re-cite to a primary annual dataset before relying on a specific figure — Patchstack's
"State of WordPress Security" report or WPScan's/Wordfence's own published statistics are candidate
sources — and state the figure with its year once re-verified. Until then, treat only the
qualitative conclusion (plugins are the dominant risk surface relative to core) as directional, not
the specific percentage.

[KB-WEBOPS-009] WordPress core's own default update behavior depends on install type, not a single
universal default: a fresh installation created on WordPress 5.6 or later receives both minor *and*
major core updates automatically by default (unless WordPress detects a version-control checkout),
while an existing/upgraded installation's default remains minor/security releases only. The
`WP_AUTO_UPDATE_CORE` constant governs this explicitly when set (`true` = all updates including
major, `false` = none, `'minor'` = minor/security only) — `'minor'` is the *existing-install*
default, not a universal one, when the constant is undefined (official, WordPress.org Developer
Resources, "Upgrading WordPress," retrieved 2026-09-27:
https://developer.wordpress.org/advanced-administration/upgrade/upgrading/). **Plugin and theme
auto-updates are not on by default for routine releases** — each must be individually enabled
per-plugin/per-theme in the admin UI — but this is not absolute: the WordPress security team
retains the ability to force-push an emergency security update to a plugin without owner opt-in for
severe, actively-exploited vulnerabilities (same source). A change made mid-window can therefore be
overwritten not only by core's own background update but by a forced plugin security push — confirm
the site's actual core auto-update setting (the `WP_AUTO_UPDATE_CORE` value, or the install-type
default if unset) as part of §7's "something else can write to the site" check.

**The practical doctrine this implies:** core patches itself (more aggressively on a fresh 5.6+
install than an existing one); plugins do not self-update for routine releases unless someone
explicitly turns that on per plugin, though a severe vulnerability can still trigger a forced
security push outside anyone's control — so an unmaintained-looking plugin (no update in 12+
months, few active installs, closed or abandoned support forum) is a materially higher risk than an
outdated *core* version would be on the same site, and should be flagged for replacement or removal
rather than left running because "it still works." Never recommend installing a new plugin without
checking its last-updated date and active-install count first.

## 6. WordPress core has no native audit log — this is a real, structural gap

WordPress core does not ship a built-in activity/audit log of who changed what, when (internal
doctrine, retrieved 2026-09-28 — not itself stated by any single official source found; consistent
with WordPress core's documented role/capability system (§1), which tracks permissions, not a
change history). This is not an oversight the site owner can fix by looking harder in wp-admin — the
data simply isn't recorded anywhere core exposes. [KB-WEBOPS-010] A dedicated activity-log plugin
closes this gap by hooking into WordPress's own action/filter system to record events core doesn't
log on its own — user logins/logouts and failed login attempts, content changes (status, body,
title, URL, custom fields), user account changes (creation, deletion, role/password/email changes),
plugin/theme installs/activations/deactivations/updates, and file-system-level changes (new,
modified, or deleted files) — each entry timestamped with the acting user, role, and IP
(third-party, the plugin vendor's own WordPress.org Plugin Directory listing describing its own
feature scope, retrieved 2026-09-27: https://wordpress.org/plugins/wp-security-audit-log/ — a
vendor self-description, not an independently verified or platform-official claim, cited for what an
activity-log plugin's feature scope covers as a category, not as an endorsement of that specific
plugin over any equivalent one; verify current maintenance status and reviews before installing
any specific plugin, per §5).

**Why this matters for a multi-writer site** (more than one Administrator, an agency with its own
access, an automated agent identity): without an activity log, "who changed this and when" is
frequently unanswerable after the fact, which is precisely the situation
`wordpress-safe-change-protocol.md` §7 describes — something else can write to the site, and
without a log there is no way to distinguish "my change broke this" from "someone else's unrelated
change happened to land at the same time." Installing an activity-log plugin is the standing fix;
absent one, an agent's own before/after captures (`wordpress-safe-change-protocol.md` §5) are the
only record that exists, which is a weaker and more effortful substitute for a real log, not
equivalent to one.

## 7. Hacked/injected content is a named, actively-enforced violation category

[KB-WEBOPS-011] Google's own spam policies explicitly define and penalize "hacked content" as its
own violation category, distinct from a site owner's own intentional actions: code injection
(malicious code added to existing pages), page injection (whole new spammy/malicious pages added by
an attacker), content injection (hidden links/text inserted into legitimate pages), and malicious
redirects (code that redirects some visitors, often based on referrer or user-agent, to harmful
destinations) (official, Google Search Central, "Spam policies for Google web search," retrieved
2026-09-27: https://developers.google.com/search/docs/essentials/spam-policies). This matters
beyond the immediate security concern: a hacked site risks a *search-visibility* penalty on top of
whatever direct damage the compromise causes, which is a second, slower-to-notice failure mode a
site owner might not connect back to the original compromise for weeks.

**The doctrine this implies:** least-privilege provisioning (§1), locked-down file editing (§4),
current plugin hygiene (§5), and a real activity log (§6) are not independent nice-to-haves — they
are the layered defense against the specific attack categories Google itself treats seriously
enough to name and penalize. Recommending any one of them in isolation, without the others,
leaves the gap the missing layer exists to close.

## Contractor bend

None of this is visible to the buyer unless it fails. For home-services/contractor companies, the owner-buyer has no way to judge
whether their website's WordPress backend is provisioned safely — they experience the *outcome*
only: the site stayed up, or it didn't; a hacked-content penalty tanked their organic leads for
weeks, or it never happened. The obligation to get §1 through §7 right is entirely on whoever
administers the site on the buyer's behalf; a buyer who has been burned by a "the website guy" who
over-scoped access or skipped backups before (see `shared/contractor-buyer-psychology.md`) will not
distinguish "we followed best practice and got unlucky" from "we cut corners" — both look identical
from outside, which is exactly why the corners should never be cut in the first place.
