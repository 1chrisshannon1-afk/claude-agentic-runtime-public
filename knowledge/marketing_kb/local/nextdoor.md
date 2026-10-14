# Nextdoor — Doctrine

Corpus for the `local/` domain. Company-agnostic: every example below is generic. Citation format
per `shared/citation-style.md`; claim ids continue the `[KB-LOCAL-NNN]` sequence. Retrieval date for
every claim below: 2026-09-27, unless noted otherwise.

---

## 1. Business Page vs. Ads Manager — two separate surfaces

**[KB-LOCAL-035]** A **Nextdoor Business Page** is the free, foundational surface: claiming one is
free, and Nextdoor's own marketing describes it as a "digital storefront" used to introduce the
business, share updates, and let neighbors know how to reach it (official, Nextdoor Business,
https://business.nextdoor.com/en-gb, and "Create a Free Business Page on Nextdoor,"
https://business.nextdoor.com/en-us/getting-started/business-page, both retrieved 2026-09-27). A
claimed Business Page includes **unlimited free organic posts** — Nextdoor's own current page
states plainly: "Reach local customers with unlimited free posts: updates, expert advice, and
more!" (official, same "Create a Free Business Page on Nextdoor" source, re-verified live
2026-09-27). Posts can be targeted by adjusting "the radius around your business" and by manually
selecting or deselecting specific neighborhoods, but the page does not state a fixed default radius
in miles. A prior version of this entry cited a third-party figure of "2 free posts per month...
within 2 miles" as UNVERIFIED — that figure is now **contradicted** by the live official page (which
states unlimited posts, not a monthly cap) and has been removed rather than merely re-hedged; do not
cite "2 free posts" or "2 miles" as fact going forward.

**[KB-LOCAL-036]** **A Business Page is a prerequisite for Ads Manager access — not a parallel,
independent product.** Nextdoor's own documentation states the Ads Manager account is where a
business manages audiences, creative, ads, performance tracking, user permissions, and billing, and
explicitly requires a claimed Business Page first: "You must have a business page to access the Ads
Manager" (official, Nextdoor Business, "Nextdoor Ads Manager: Quick Create,"
https://business.nextdoor.com/en/en-ca/nam/nextdoor-ads-manager-quick-create, retrieved 2026-09-27).
This is the single structural fact that matters most for onboarding sequencing: a GC (or an agent
setting up their account) must claim/verify the free Business Page *before* any paid-ads work can
begin — there is no way to skip straight to Ads Manager.

**[KB-LOCAL-037]** **UNVERIFIED (primary source unreachable: https://business.nextdoor.com/en-us/advertise)**
— this pass could not locate a live, reachable official Nextdoor page confirming a "no minimum
spend requirement" claim or the specific price points previously recorded here ("Local Deals
starting at $3," Promoted Posts pitched as testable "for the cost of a takeout dinner"); the
advertise-product URL returned 404, and the reachable Ads Manager landing page
(https://business.nextdoor.com/en-us, retrieved 2026-09-27) contains no pricing information at all.
These figures are recorded here as a third-party/legacy-marketing characterization only (third-party,
retrieved 2026-09-27) and must be re-verified against the current live Ads Manager account or a
current official rate-card page before being cited to a contractor as fact — do not quote "$3" or
"no minimum spend" as confirmed platform policy.

---

## 2. User roles and permissions — confirmed structure, unverified role names

**[KB-LOCAL-038]** **UNVERIFIED (primary source unreachable: https://adsmanager.help.nextdoor.com)**
— this page (title "About user roles and permissions") was unreachable during this pass's
automated retrieval; see [KB-LOCAL-039] below, which documents the same reachability failure for
this exact URL. The claim that **both** surfaces (Business Page and Ads Manager) support adding
additional users with differentiated access, managed centrally via a "Business Settings" area
("manage which teams and users have access to each account, add or remove user access, update your
billing methods for each advertiser, and create new advertisers"), plus a parallel Business
Page-side settings flow (account profile menu → "Business settings" → "Users" → "Invite," per
Nextdoor Help, https://help.nextdoor.com/s/article/Business-Page-Ads-Inviting-Additional-Users,
retrieved 2026-09-27 — this second URL's own reachability was not independently re-confirmed in
this pass either), is recorded here as third-party-corroborated (third-party, aggregated Nextdoor
business-help mirror sources, retrieved 2026-09-27) pending re-verification. **Before citing that
both surfaces support differentiated user access as confirmed fact, re-verify directly against the
live help-center pages (ideally in a headed browser) or a live account's own Business Settings
screen** — see [KB-LOCAL-039] for the same caveat applied to the specific role names.

**[KB-LOCAL-039]** **UNVERIFIED (primary source unreachable:
https://adsmanager.help.nextdoor.com/namhelpcenter/s/article/About-user-roles-and-permissions):**
the exact named role tiers (e.g. whether Nextdoor uses an Owner/Admin/Standard/Analyst-style
ladder, a simpler Admin/Editor split, or some other naming) could not be confirmed during this
pass — the specific help-center pages titled "About user roles and permissions" (that URL and its
`help.nextdoor.com` mirror) returned only page chrome/navigation content when fetched, with the
substantive role-list content not rendering through the available fetch path. Per [KB-LOCAL-038]
(itself unverified for the same reachability reason), the *claim* is that role-based, per-account,
per-advertiser user permissions exist and are managed from a central Business Settings → Users
area — but that claim is third-party-corroborated only, not officially confirmed. Not confirmed at
all: the specific role names, the exact permission boundaries of each role, or whether Business
Page-side user access and Ads Manager-side user access are the same role set or two separate ones.
**Before citing a specific Nextdoor role name or permission boundary — or even the existence of
role-based permissions itself — in any deliverable, an agent must re-verify directly against the
live help-center page (ideally in a headed browser, since this pass's automated fetch could not
render it) or against a live account's own Business Settings → Users screen** —
never state a specific Nextdoor role name as settled fact based on this file alone.

---

## Contractor bend

The one fact worth remembering cold is [KB-LOCAL-036]: nothing on Nextdoor's paid side is reachable
until the free Business Page is claimed and verified — so the first step for a GC who has never
touched Nextdoor is always claiming that page, never "setting up an ad." Because the exact user-role
names are unverified here, do not hand a contractor a specific role-name recommendation ("give your
office manager the X role") sourced from this file — walk the live Business Settings → Users screen
with them instead and match whatever roles actually appear there to the same judgment used elsewhere
in this corpus (who needs to post/respond vs. who needs to touch billing).

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend on this platform.*
