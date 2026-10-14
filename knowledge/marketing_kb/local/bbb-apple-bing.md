# BBB, Apple Maps, and Bing Places

Domain doctrine for the three local-presence platforms outside the Google/Yelp/marketplace cluster:
Better Business Bureau accreditation, Apple Business Connect (Apple Maps listing management), and
Bing Places for Business. Company-agnostic. Every claim carries a `[KB-LOCAL-NNN]` id per
`shared/citation-style.md`.

---

## 1. Better Business Bureau (BBB) accreditation

**[KB-LOCAL-023]** BBB accreditation is a paid, application-based program distinct from simply
having a BBB business profile (any business can have an unaccredited profile with a letter rating;
accreditation is the additional paid/vetted tier). Baseline eligibility requires the business to
have been actively selling products or services for at least six months prior to application (or
have a prior operating track record), and requires the business to maintain a **B rating or
better** to be approved. (official, BBB, "How to get BBB Accredited" / accreditation-standards
pages, retrieved 2026-09-27: https://www.bbb.org/business/accreditation/how-to-get-accredited,
https://www.bbb.org/get-accredited)

**[KB-LOCAL-024]** Accreditation is granted against BBB's **8 Standards for Trust** — the
application is vetted against these standards, and a recommendation is then made to BBB's Board of
Directors to approve or deny. Two of the eight standards, stated directly: maintain sensitive data
(payment info, SSN, financial/health information) securely and dispose of it properly; and approach
all marketplace dealings with integrity, good faith, and intent to do what is reasonably expected.
(official, BBB, "Get Accredited" / accreditation-standards pages, retrieved 2026-09-27:
https://www.bbb.org/get-accredited)

**[KB-LOCAL-025]** BBB charges a fee for accreditation. UNVERIFIED (primary source unreachable in
this pass — a specific fee schedule is not published as a single flat number on BBB's national
site and varies by local BBB chapter and business size; re-verify against the applicable regional
BBB's own fee page before quoting a dollar figure to any operator or customer).

**Mechanism worth stating plainly:** an existing negative complaint history or a rating below B
is a real, cited gate on accreditation eligibility — recommending a BBB accreditation push without
first checking the business's current BBB rating and complaint history is a wasted-effort mistake,
not merely a cosmetic omission.

**Reject example:** recommending a BBB accreditation application without first pulling the
business's existing BBB profile (if one already exists) to check current rating and any open
complaints.

**Pass example:** checking the existing BBB profile and rating first; if a rating issue exists,
resolving the underlying complaint(s) before applying, since a denied application is visible in a
way that never having applied is not.

## 2. Apple Business Connect (Apple Maps)

**[KB-LOCAL-026]** Apple Business Connect is Apple's own free platform for businesses to claim and
manage how their business appears across Apple Maps, Siri, Messages, Wallet, and other
Apple-surface products — the Apple-ecosystem equivalent of a Google Business Profile. (official,
Apple, Apple Business Connect, retrieved 2026-09-27: https://businessconnect.apple.com/,
redirecting to https://business.apple.com/)

**[KB-LOCAL-027]** Managing a listing there requires claiming the business location(s) and keeping
core identity fields (name, address, phone, hours, category, photos) current — the same NAP
discipline this folder's `nap-consistency.md` covers applies here as one more platform in that
canonical-record pass. UNVERIFIED (primary source specifics — exact verification method, whether a
phone/mail/document-based verification is required, and any listing-eligibility restrictions —
were not independently re-confirmed from the live Apple Business Connect help documentation in this
pass; re-verify against Apple's own onboarding flow at time of use rather than assuming Google's
verification mechanics apply identically).

**Mechanism worth noting for a phone-first, in-a-truck buyer base:** Apple Maps is the default
navigation and "nearby search" surface on every iPhone, and a stale or unclaimed Apple Business
Connect listing means the business's presence on that surface is either outdated or entirely
absent — this is a real, separate gap from GBP, not a redundant one, since a meaningful share of
homeowners search "near me" from an iPhone's native Maps app rather than a Google-branded surface.

## 3. Bing Places for Business

**[KB-LOCAL-028]** Bing Places for Business is Microsoft's local-listing platform for Bing Search
and Bing Maps — the Bing-ecosystem equivalent of a Google Business Profile, with its own separate
claim/verification flow. (official mechanism; Microsoft's canonical top-level help page for Bing
Places was not independently re-fetched at a stable URL in this pass — treat the platform's
existence and general purpose as confirmed via Microsoft Q&A / support documentation cross-
references, retrieved 2026-09-27, and re-verify the current canonical help-center URL at time of
use rather than relying on this citation for a specific mechanic).

**[KB-LOCAL-029]** Bing verification is typically completed by one of several methods — email,
phone, or postcard-by-mail — but the set of methods actually offered for a given listing is
narrowed by Bing based on what it can already confirm from public records for that business; a
postcard-only requirement is not user-selectable and cannot be swapped for phone/email on demand.
The postcard method, when used, typically arrives within about 14 days and contains a code entered
into the Bing Places account to complete verification. (third-party, aggregated from Microsoft Q&A
official support threads, retrieved 2026-09-27:
https://learn.microsoft.com/en-us/answers/questions/5815760/getting-verified-on-bing-places-for-business,
https://learn.microsoft.com/en-us/answers/questions/2343504/verification-process-at-bing-places-for-business)

**[KB-LOCAL-030]** If postcard verification fails twice or the postcard never arrives, and no
phone/email option is offered, the sanctioned path is Bing Places' own support form requesting a
manual review — not repeated resubmission of the same request. (third-party, aggregated from
Microsoft Q&A official support threads, retrieved 2026-09-27, same sources as [KB-LOCAL-029])

**Mechanism note:** Bing Places drives a smaller share of local search volume than Google or Apple
for most residential-services searches, but it is a genuinely free, low-effort listing to claim and
keep current, and it is one more NAP-consistency surface per `nap-consistency.md` — the marginal
cost of keeping it current is low relative to leaving it stale or unclaimed.

---

## Contractor bend

None of these three platforms is where this buyer's attention or budget should go first — Google
and reviews dominate for a residential remodeling GC. Frame all three as "finish the job cheaply,"
not as growth levers:

- **BBB accreditation** is worth recommending mainly as a trust signal for the specific homeowner
  demographic that still checks it before hiring — older or more risk-averse buyers, larger-ticket
  jobs (kitchen/whole-home remodels) — and it is worth flagging plainly that a rating problem
  should be fixed before applying, not papered over with an application.
- **Apple Business Connect and Bing Places** are free, low-effort, "claim it and keep it correct"
  items — never worth a paid engagement or a dedicated recurring cadence on their own, but worth a
  one-time claim-and-verify pass as part of any broader local-presence setup, since an unclaimed
  listing on either platform is a small but real gap in "does this business look real and current
  everywhere a homeowner might look."
