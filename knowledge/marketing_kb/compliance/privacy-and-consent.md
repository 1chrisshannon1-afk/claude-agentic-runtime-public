# Privacy & Consent — collecting, storing, and using personal data in marketing

Company-agnostic doctrine. Governs what consent and disclosure are required to **collect, store, and
use** a lead's or customer's personal data (name, phone, email, address, browsing/analytics data,
and — where a client operates in a regulated vertical — health-adjacent data) for marketing purposes.
This is the layer *underneath* channel-specific rules: [`can-spam.md`](can-spam.md) and
[`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md) govern what you may *send* once you have someone's contact
info; this file governs what you needed to have collected and disclosed in the first place, and what
extra restrictions attach to sensitive categories of data (health data specifically). See
[`hipaa-marketing-for-practices.md`](hipaa-marketing-for-practices.md) for the HIPAA-covered-entity
case specifically — that file is the deeper, sector-specific doctrine for an actual HIPAA covered
entity; this file is the general-purpose privacy/consent layer that applies to every client,
including ones with no HIPAA exposure at all but who still collect health-adjacent signals (e.g. a
home-services company running remediation-after-injury or accessibility-related campaigns, or any
business whose website analytics could capture a visitor's health-related browsing).

**Standing rule for this file:** every claim carries a stable id `[KB-COMPLIANCE-NNN]` per
`shared/citation-style.md`. This file continues the numbering [`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md)
started, from **036**, for the same reason stated there — see this file's §6 for the pre-existing
numbering collision this corpus has not yet fixed.

---

## 1. General consumer privacy law — the state-patchwork problem

**[KB-COMPLIANCE-036] Correction (2026-09-27), three issues fixed:** (1) an earlier version of this
claim cited the IAPP US State Privacy Legislation Tracker for the entire claim below, including the
"no comprehensive federal law" premise and the HIPAA/COPPA/GLBA list; fetched directly and asked
specifically, that page is scoped only to tracking state legislation and does not state either of
those things — it does not mention HIPAA, COPPA, or GLBA at all. (2) the specific figure "twenty US
states... as of January 1, 2026" was also unconfirmable from the IAPP citation specifically: the IAPP
tracker page's fetchable/extractable text contains no specific numeric state count (the count lives
in an interactive chart/map that HTML-to-text conversion does not capture) — fetched twice, including
with a targeted prompt asking specifically for any state count stated in the page's text, with the
same result both times: no count found. Re-sourced below, split by what each source actually
supports. (3) **a subsequent edit of this claim, made while re-sourcing to the MultiState tracker,
introduced a transcription error** — it stated the MultiState-sourced count as "nineteen" while
citing a source titled "20 State Privacy Laws in Effect in 2026." Fetched directly (2026-09-27): the
MultiState page states, verbatim, "**Twenty states now have comprehensive privacy laws on the books**
(counting Florida, which has a narrower scope than other state privacy laws)" and "In 2026, twenty
states have comprehensive privacy laws in effect." The correct figure from this source is **twenty**,
not nineteen; corrected below.
Privacy obligations for marketing data (what must be disclosed, what consent is required, what
rights a consumer has to access/delete/opt out) are governed by a growing patchwork of **state**
comprehensive privacy laws — California's CCPA/CPRA and a growing number of other states now have a
comprehensive consumer privacy law in effect. A secondary compliance-vendor tracker (not
independently primary-source-confirmed by this corpus against the IAPP tracker itself) puts the count
at **twenty** states in effect as of 2026, growing further during 2026 as additional states'
effective dates arrive (secondary source, MultiState, "20 State Privacy Laws in Effect in 2026,"
retrieved 2026-09-27,
https://www.multistate.us/insider/2026/2/4/all-of-the-comprehensive-privacy-laws-that-take-effect-in-2026
— confirmed verbatim: "Twenty states now have comprehensive privacy laws on the books").
**UNVERIFIED (primary source unreachable: the IAPP tracker,
https://iapp.org/resources/article/us-state-privacy-legislation-tracker/, does not expose a specific
state count in machine-fetchable text; the twenty-state figure above rests on a secondary
compliance-vendor source, not on a directly-read primary government or IAPP count)** — always
re-pull a current count (the IAPP tracker's own interactive chart, viewed directly, or a current
secondary tracker) before citing an exact state number in a client-facing document, rather than
relying on this file's figure, which will drift out of date as more states' laws take effect — plus
sector-specific federal law layered on top: the FTC's own business-guidance site
confirms COPPA (children's data) and the Gramm-Leach-Bliley Act (financial-institution data-sharing
disclosure and safeguarding) as federal privacy statutes it enforces, and references HIPAA-adjacent
obligations via its Health Breach Notification Rule (official, FTC "Privacy and Security" business
guidance, retrieved 2026-09-27, https://www.ftc.gov/business-guidance/privacy-security). The
premise that no single comprehensive federal consumer privacy law exists (as opposed to this
sector-specific patchwork) is widely corroborated in secondary legal/compliance commentary (e.g.
Foley & Lardner, Osano, Bloomberg Law state-privacy trackers, retrieved 2026-09-27) but was not
confirmed against a single reachable primary government source stating it in those terms at
retrieval time — **UNVERIFIED (primary source unreachable: no single federal statute or agency
page was found that states the absence-of-comprehensive-federal-law premise directly; treat as
well-corroborated by secondary sources, not as independently primary-sourced)**.

**[KB-COMPLIANCE-037] (internal doctrine, retrieved 2026-09-27) Correction (2026-09-27):** an earlier version of this claim attributed the
specific 3-part structural pattern below to "the same source's own comparison methodology" (the
IAPP tracker). Fetched directly and asked specifically, that page does not describe or confirm this
3-part pattern — it states only that its tracker "identif[ies] and map[s] out fourteen provisions
that commonly appear in comprehensive privacy laws," organized into two categories (consumer rights
and business obligations), with no itemized breakdown reachable in the page's fetchable content
(the detail sits behind IAPP membership access). The 3-part pattern below (disclosure +
opt-out-of-sale/sharing + deletion/access right) reflects this corpus's own generalization from the
well-known structure of CCPA/CPRA and its state-law descendants, not a claim the cited page itself
makes — restated below as doctrine, not as a sourced structural finding. A GTM seat proposing a
data-collection mechanism (a lead form, a cookie/pixel-based retargeting audience, a CRM import, a
review-platform integration) for a client operating or targeting customers in **any** state with a
comprehensive privacy law in effect should verify, before recommending it, whether that state's law
imposes: (a) a disclosure requirement (a privacy notice naming what's collected and why), (b) an
opt-out right for "sale" or "sharing" of personal data for cross-context behavioral advertising
(most comprehensive state laws define ad retargeting/analytics-sharing broadly enough to trigger
this), and (c) a deletion/access-request mechanism the business must be able to honor. Never assume
a small home-services business is exempt by size alone — several state laws' revenue/volume
thresholds are low enough that even a small owner-operated home-services business's website analytics and ad-pixel setup can
trigger obligations once it processes personal data of a state's residents above the statute's
volume threshold; the exact threshold is state-specific and must be checked per state, not assumed,
against that state's own comprehensive privacy statute (the IAPP tracker, claim 036, is a starting
index of which states have one, not a substitute for reading the state's own law).

---

## 2. State consumer-health-data laws — a distinct, stricter category

**[KB-COMPLIANCE-038]** Washington State's **My Health My Data Act (MHMDA)**, effective March 31,
2024 (with a later compliance date for small businesses), is a state law that regulates "consumer
health data" **independent of HIPAA** — it applies to *any* business (not just HIPAA covered
entities) that collects or processes health-related data about a Washington consumer, and it defines
"consumer health data" broadly enough to include data that identifies a consumer's efforts to
research or seek health care services, reproductive/gender-affirming care information, and
biometric or location data that could reveal an attempt to receive health care services — not just
clinical records. It requires **opt-in consent** (not merely an opt-out) before collecting or
sharing consumer health data, and a **consumer health data privacy policy** that "clearly and
conspicuously discloses" the required categories (what data is collected/processed and why, its
sources, what categories are shared and with which third parties, and how a consumer exercises
their rights), with a link that must be "prominently publish[ed]... on its homepage" — **correction,
2026-09-27:** an earlier version of this claim characterized this as "a specific standalone
consumer health data privacy policy separate from a general privacy policy." Direct fetch of the
cited statute (RCW 19.373.020) shows it does not state or require that; the statute's own language
does not distinguish between a standalone document and equivalent disclosures integrated into a
general privacy policy — either satisfies it, so long as the required disclosure content and the
homepage link are present. It also **prohibits the use of a geofence around a facility that
provides health care services (including, by the statute's own example, mental health and
reproductive/sexual health facilities) to identify, track, or target consumers**, or to send them
notifications/messages/ads related to their health data. (official, Washington State My Health My
Data Act, RCW 19.373.010/.020/.080, text via the Washington State Legislature's own hosted statute
site, retrieved 2026-09-27, https://app.leg.wa.gov/rcw/default.aspx?cite=19.373.020 — reached
directly without a 403 at retrieval time.)

**[KB-COMPLIANCE-039] (internal doctrine)** MHMDA's geofencing prohibition (claim 038) is directly relevant to any GTM
seat running location-based ad targeting for a client in or near a healthcare-adjacent vertical —
this includes not just medical/dental practices but potentially a home-services business running
campaigns near facilities the statute's broad "consumer health data" definition could reach (e.g. a
mobility-accessibility remodeling contractor geofencing a rehabilitation clinic's parking lot to
target patients as they leave). **Never propose a geofence drawn around a healthcare facility of any
kind for any client, in any state, without first checking that state's own consumer-health-data or
geofencing-specific statute** — MHMDA is the most-cited example because it was an early, broad
mover, but treat its existence as a signal that other states may have or adopt similar geofencing
prohibitions, not as proof that only Washington restricts this. (This claim states a doctrine
recommendation built on claim 038's cited prohibition — the recommendation itself is not
independently sourced beyond the MHMDA text it generalizes from.)

**[KB-COMPLIANCE-040] UNVERIFIED (this corpus has not independently confirmed which other states, if
any, have enacted a consumer-health-data statute materially similar to MHMDA, as of retrieval date
2026-09-27)** — other states (commonly cited in third-party legal-compliance commentary as having
considered or enacted similar consumer-health-data-specific legislation, e.g. Nevada's SB 370) may
impose comparable obligations, but this file does not assert which are currently in effect,
because a primary-source, state-by-state re-verification was not completed for this claim. **Doctrine
until re-verified:** treat MHMDA's opt-in-consent-plus-no-geofencing pattern as the conservative floor
for any consumer-health-data-adjacent campaign in any state, rather than assuming only Washington
residents are protected.

**[KB-COMPLIANCE-041]** MHMDA creates a **private right of action** under Washington's Consumer
Protection Act — meaning an individual consumer, not just the state Attorney General, can sue for a
violation, which is a meaningfully different (and for a business, riskier) enforcement structure
than most comprehensive state privacy laws, which typically reserve enforcement to the state AG
alone. **Correction (2026-09-27):** an earlier version of this claim said "the statute's own
enforcement section confirms the private right of action," citing only RCW 19.373 (MHMDA itself).
Fetched RCW 19.373.090 (MHMDA's enforcement section) directly: it states only that a violation "is
an unfair or deceptive act in trade or commerce" under the general Consumer Protection Act, chapter
19.86 RCW — it does **not** itself state that a private individual may sue; that mechanism comes
from a separate statute, RCW 19.86.090, the CPA's own private-suit provision ("Any person who is
injured in his or her business or property by a violation of RCW 19.86.020, 19.86.030, 19.86.040,
19.86.050, or 19.86.060 ... may bring a civil action in superior court"), verified directly. The
underlying conclusion — an MHMDA violation is privately actionable — is correct once RCW 19.373.090
and RCW 19.86.090 are read together, but citing only RCW 19.373 as "confirming" the private right
of action misstated what that statute's text says on its own. (official, RCW 19.373.090 and RCW
19.86.090, Washington State Legislature's own hosted statute site, retrieved 2026-09-27,
https://app.leg.wa.gov/rcw/default.aspx?cite=19.373.090 and
https://app.leg.wa.gov/rcw/default.aspx?cite=19.86.090.)

---

## 3. Cookies, pixels, and consent-mode mechanics (pointer, not doctrine)

**[KB-COMPLIANCE-042] (internal doctrine)** The mechanical implementation of consent for cookies/pixels (Google Consent
Mode v2, a cookie-consent banner's technical wiring, GTM container consent-gating) is a
**measurement-domain** concern, not a compliance-domain one — this file states the *legal
requirement* (claim 037's opt-out-of-sale/sharing right, and for consumer health data claim 038's
opt-in requirement), but the implementation doctrine belongs in
[`measurement/consent-mode.md`](../measurement/consent-mode.md) (per the runtime GTM department plan
§9 registry). Do not duplicate Consent Mode implementation detail in this file; cite the measurement
domain's file directly.

---

## 4. Working checklist before any lead-capture, retargeting, or health-adjacent campaign launches

1. Does the client's public privacy notice actually disclose the categories of personal data
   collected and the purposes, matching what's actually collected (not a generic template that
   doesn't match the real tech stack)?
2. Is there a working opt-out-of-sale/sharing mechanism if the campaign uses any cross-context ad
   retargeting or analytics-sharing (claim 037)?
3. **If the campaign touches health-adjacent data or targeting in or near any healthcare facility:**
   is consent opt-in (not opt-out), does the client's consumer-health-data privacy policy actually
   disclose the required categories with a homepage link (a separate document or integrated into the
   general privacy policy both satisfy this — see claim 038's correction), and does the targeting
   avoid any geofence around a healthcare facility (claims 038–039)?
4. Has the volume/revenue threshold question been checked per state the campaign targets, rather
   than assumed exempt by business size (claim 037)?
5. Is a deletion/access-request process actually reachable and functional (test it), not just named
   in a policy document?

---

## 5. Contractor bend

A small owner-operated residential remodeling business is very unlikely to be directly regulated by MHMDA-style
consumer-health-data law in the ordinary course of business — but two realistic scenarios bring it
into scope: (1) a **mobility/accessibility remodeling** line of business (grab bars, walk-in tubs,
ramps, aging-in-place remodels) that markets by geofencing senior centers, rehab facilities, or
assisted-living parking lots — this is exactly the pattern claim 039 flags, and it is a genuinely
tempting, high-intent targeting tactic that must never be proposed; and (2) a general privacy-notice
gap that most small contractors share with every other small business regardless of vertical — no
real privacy policy, or a copy-pasted one that doesn't match what the website's own analytics/ad
pixels actually collect. For this buyer, lead with the practical framing: "your website's ad
tracking almost certainly already qualifies as needing a real privacy notice and an opt-out link —
this is a one-time fix, and skipping it is a lawsuit risk that scales with how many visitors your
site gets, not a one-time fine." Never propose location-based targeting anywhere near a medical,
rehab, senior-living, or mental-health facility for any campaign, for any client, without an
explicit state-law check first — this is one of the few areas in this corpus where the "ask
forgiveness" instinct that might apply to a minor SEO shortcut is never appropriate, because the
enforcement mechanism (claim 041's private right of action) means a single consumer, not just a
regulator, can bring the claim.

---

## 6. Known corpus defect this file does not fix — FIXED, see INDEX.md

Continuing from [`tcpa-a2p-10dlc.md`](tcpa-a2p-10dlc.md) §6: `hipaa-marketing-for-practices.md`
previously, independently, and collidingly numbered its own claims `[KB-COMPLIANCE-001]`–
`[KB-COMPLIANCE-017]` against `ftc-endorsements-and-fake-reviews.md`'s `001`–`012` and
`review-gating.md`'s `013`–`018`. This has since been fixed by renumbering the HIPAA file's claims
to `043`–`059`; see [`INDEX.md`](INDEX.md)'s "Known corpus defect" section for the full before/after.
This file's own ids (036–042) never collided and are unchanged.
