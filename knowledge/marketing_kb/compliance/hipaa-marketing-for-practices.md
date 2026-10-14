# HIPAA Marketing Doctrine for Practices

Doctrine for any GTM seat producing, reviewing, or approving a marketing action for a HIPAA
covered-entity client (e.g. a dental or medical practice, generically referred to here as "the
practice"). This file is company-agnostic — no company facts, no real patient data, no real
account names. Generic examples only.

**Seat status (2026-09-28):** this file's own "content reviewer" / "security-trust reviewer"
language (§6.1 item 5, §8 item 1) describes review ROLES, not yet-registered agent names — no
dedicated `hipaa`-lane or practice-vertical agent seat is a registered agent seat as of this
writing. Per `social/INDEX.md`'s own seat-status note, treat this as forward-looking discipline for
whichever existing GTM seat a company assigns to that role in its own pack/dossier, not as a
citation to an already-live agent.

**Standing rule for this file:** every factual claim below carries a stable claim id
`[KB-COMPLIANCE-NNN]` and a citation to a primary/official source, with retrieval date
2026-09-27, per `shared/citation-style.md`. **Anything not verified from a primary source is
marked UNVERIFIED, and this doctrine treats an UNVERIFIED item as prohibited until it is
verified** — never treat an unverified claim as a green light. Where a primary regulator source
(hhs.gov, ecfr.gov) blocked automated fetching, the claim is instead verified against the best
reachable mirror or the regulator's own settlement/press-release page reached via search, and
that substitution is stated on the claim.

This file is the `hipaa` review lane's checklist source — the doctrine floor any GTM seat applies
before a practice's public item or data-flow change goes out (internal doctrine: a company running
a HIPAA-covered practice routes such changes through a dedicated compliance review before
publication; that lane's own mechanics, reviewer assignment, and checklist item numbering are that
company's own pack/dossier concern, not restated here). It is not a substitute for the practice's own
legal counsel or its own HIPAA compliance officer — it is the floor a GTM agent must never go below
without a documented, verified exception.

---

## 1. What "marketing" means under HIPAA, and why it matters here

**[KB-COMPLIANCE-043]** HIPAA's Privacy Rule defines "marketing" as "a communication about a
product or service that encourages recipients of the communication to purchase or use the
product or service" (45 CFR § 164.501, official — regulator text via
`law.cornell.edu/cfr/text/45/164.501`, an eCFR mirror, retrieved 2026-09-27; `ecfr.gov` and
`hhs.gov` blocked automated retrieval with a 403/bot-check at retrieval time, so this claim is
sourced to the Cornell Legal Information Institute's mirror of the same regulatory text, not a
secondary summary).

**[KB-COMPLIANCE-044]** The definition carries built-in exceptions — a communication is **not**
"marketing" (and so needs no patient authorization under §164.508, see claim 46) when it is:
- a **refill reminder** or similar communication about a drug currently prescribed to the
  individual, provided any financial remuneration received for making the communication is
  reasonably related to the covered entity's cost of making it; or
- made for **treatment** of the individual (including case management, care coordination, or
  recommending alternative treatments, therapies, providers, or care settings); or
- describing the entity's own **health-related products or services** (or those included in the
  individual's health plan) —
- **provided, in both of the last two cases, that the covered entity receives no financial
  remuneration from a third party in exchange for making the communication.**
(45 CFR § 164.501, same source and retrieval as claim 43.)

**Why this matters for a GTM agent:** the exceptions are narrow and remuneration-gated. A practice
telling its own existing patients about its own services (a recall reminder, a "we now offer clear
aligners" email to the existing patient list) can fit the treatment/own-services exception — but
the instant a third party is paying for that communication (a co-marketing arrangement, a paid
newsletter placement, an insurer or vendor sponsoring the message), it becomes "marketing" and
needs patient authorization. **A GTM agent never makes this call itself — see §4 (patient-list
communications) — this section only supplies the definition the compliance lane applies.**

## 2. Authorization requirement for marketing uses of PHI

**[KB-COMPLIANCE-045]** Where a communication meets the "marketing" definition (claim 43) and
does not fit an exception (claim 44), the covered entity must obtain the individual's prior
written **authorization** before using or disclosing protected health information (PHI) to make
that communication (45 CFR § 164.508(a)(3), official — same Cornell mirror,
`law.cornell.edu/cfr/text/45/164.508`, retrieved 2026-09-27, subject to the same
ecfr.gov/hhs.gov fetch-blocking noted in claim 43).

**[KB-COMPLIANCE-046]** Two narrow exceptions to the authorization requirement exist: (a) a
**face-to-face communication** made by the covered entity to the individual, and (b) a
**promotional gift of nominal value** provided by the covered entity. Neither exception covers a
digital ad, an email blast, an SMS campaign, or a paid social post — those are not face-to-face
and are not a nominal-value gift. (45 CFR § 164.508(a)(3), same source and retrieval as claim 45.) When remuneration from a third party is involved, the authorization itself must state that
the remuneration is involved (same section).

**Applied rule (internal doctrine, derived from claims 44–46 above):** email or SMS
communications to a practice's own patient list are **prohibited by default** for any GTM agent
unless the `hipaa` lane has verified, in writing, either (a) the specific communication fits the
treatment/own-services exception with no third-party remuneration (claim 44), or (b) a documented
patient authorization exists on file covering that use (claim 45–46). Absent that written
verification, treat the action as prohibited — do not assume the exception applies because the
message "sounds like" a reminder.

## 2.1 Patient photos, before-and-afters, and testimonials

**[KB-COMPLIANCE-058]** A patient's photograph, video, or written testimonial that identifies them
(by name, face, voice, or other recognizable detail) **and** references their treatment, condition,
or outcome is protected health information — a photo is PHI the moment it is tied to an
identifiable individual and a health/treatment context, exactly as any other identifiable health
record would be. Using that PHI in marketing (a before-and-after photo, a video testimonial, a
written quote naming the patient or showing an identifiable image) is a "marketing" use under claim 43 and is not covered by any exception in claim 44 (it is not the practice's own health-related
services described to that same patient for their own treatment — it is the patient's image used
to promote the practice to *other* prospective patients). It therefore requires the individual's
prior written authorization under 45 CFR § 164.508(a)(3) (same source and retrieval as claims 45–46, re-confirmed directly reachable this pass, 2026-09-27:
`law.cornell.edu/cfr/text/45/164.508`) before any GTM seat may publish it. **Note (2026-09-27, from
this pass's direct re-check of that source):** §164.508(a)(3)'s text states the general
marketing-authorization requirement and does not itself name photographs, videos, or testimonials —
the application of that general rule to patient photos/testimonials specifically is this file's own
doctrinal extension (the same "identifiable + health context = PHI" logic HIPAA applies uniformly to
any record type), not a provision-specific HHS holding naming that exact fact pattern. Treat the
underlying authorization requirement as verified (claims 45–46) and its extension to
photos/testimonials as this file's reasoned application of it, not as independently confirmed
against primary text naming that scenario — the `hipaa` lane should confirm this specific
application against HHS's own marketing-guidance FAQ or counsel before treating it as a
litigation-tested bright-line rule. **Applied rule (internal doctrine, derived from claim 58
above):** no
patient name, face, photo, voice, before-and-after image, or testimonial may be used in any
practice's marketing material — website, ad, social post, GBP post, brochure, or video — without a
documented authorization reference (the specific signed authorization's identifier or file
location) attached to the action. Absent that documented reference, treat the asset as prohibited
for publication regardless of how it was obtained or who supplied it (a patient handing over their
own photo and enthusiastically consenting verbally is not a substitute for the written,
element-complete authorization this section requires — see claim 59).

**[KB-COMPLIANCE-059]** `(third-party)` — **UNVERIFIED, not independently confirmed against a
primary HHS source in this pass** (hhs.gov's authorization-form guidance blocked this session's
automated fetch, same pattern as claims 47/48/50/55/56): a HIPAA marketing authorization is
commonly described as needing several specific elements to be valid — a description of the specific
PHI covered (e.g. "photograph of face" or "video testimonial," not a generic "medical information"
catch-all), the name of the person/entity authorized to make the disclosure, the recipients or
categories of recipients, the purpose, an expiration date or event, the individual's signature and
date, a statement of the individual's right to revoke, and a statement that treatment is not
conditioned on signing the authorization (multiple independent marketing-compliance and health-law
sources describe this same element set consistently, retrieved 2026-09-27, but none is an HHS
primary source directly confirming these are the exact required elements for a *marketing*
authorization specifically, as opposed to the general-purpose authorization elements at 45 CFR §
164.508(c)). **Treat this element list as informative, not as a substitute for the practice's own
counsel drafting or approving its actual authorization form** — the `hipaa` lane confirms 45 CFR §
164.508(c)'s core-elements text directly before relying on any specific element list, and never
accepts a GTM-drafted authorization form as sufficient on its own.

**Reject example (mirrors the general pattern claims 55–56 establish for review replies, applied
here to photos):** publishing a before-and-after smile photo captioned "Sarah's smile makeover with
Dr. [Name]!" because the patient posted the same photo publicly on her own social media and tagged
the practice. The patient's own public posting is not authorization for the *practice* to
separately use, re-host, or republish that image in its own marketing — the practice still needs
its own signed authorization on file. **Pass example:** a before-and-after image used in an ad only
after the `hipaa` lane confirms a signed, dated, non-expired authorization exists on file naming
that specific image/video and that specific use, with the authorization's identifier recorded on
the action per the applied rule above.

## 3. Online tracking technologies — what the AHA v. Becerra ruling actually changed

**[KB-COMPLIANCE-047]** **UNVERIFIED (primary source unreachable:
`hhs.gov/hipaa/for-professionals/privacy/guidance/hipaa-online-tracking/index.html`)** — that HHS
page returned HTTP 403 to this session's automated fetch tool at retrieval time (2026-09-27), same
as the direct re-check performed in this pass. In *American Hospital Association v. Becerra* (N.D.
Tex., No. 4:23-cv-01110-P, decided June 20, 2024), the district court vacated HHS OCR's
online-tracking guidance **only** as applied to the specific combination of (1) an individual's IP
address connected with (2) a visit to an **unauthenticated, public-facing webpage** addressing
specific health conditions or health care providers, where no other identifying information is
submitted. HHS OCR withdrew its appeal of this ruling on August 29, 2024. (`(third-party)` —
corroborated independently across multiple law-firm client alerts describing the same order and
withdrawal date, all retrieved 2026-09-27: American Bar Association
(`americanbar.org/groups/health_law/news/2024/09/hhs-voluntarily-dismisses-appeal-online-tracking-technology-lawsuit/`),
Quarles & Brady (`quarles.com/newsroom/publications/hhs-ocr-withdraws-tracking-technologies-appeal-in-aha-v-becerra`),
Morrison Foerster (`mofo.com/resources/insights/240930-a-mofo-privacy-minute-q-a-hhs-withdraws`),
Holland & Knight (`hklaw.com/en/insights/publications/2024/06/american-hospital-assn-v-becerra-are-tracking-tools-ok-again`),
and the American Hospital Association's own news page
(`aha.org/news/headline/2024-08-29-hhs-will-not-appeal-aha-court-victory-online-tracking-case`,
itself a party to the case, reporting the August 29, 2024 dismissal date). The withdrawal date and
vacated scope are consistent word-for-word across five independent sources describing the same
primary order — strong convergent evidence — but the HHS guidance page and the court order itself
remain unreachable to this session, so this claim stays UNVERIFIED against a primary source until
the `hipaa` lane re-fetches one directly (a headed browser render, not an automated text fetch, per
this corpus's standing pattern for bot-blocked pages, `shared/citation-style.md`).

**[KB-COMPLIANCE-048]** **UNVERIFIED (primary source unreachable:
`hhs.gov/hipaa/for-professionals/privacy/guidance/hipaa-online-tracking/index.html`)** — same
unreachable HHS page and same 403 result as claim 47 at retrieval time (2026-09-27). **What did
NOT change:** the ruling is narrow. It does **not** touch guidance for (a) **authenticated pages** —
a patient portal, a scheduled-appointment confirmation page reached after login — or (b) any page,
authenticated or not, where the visitor **submits identifying information** (fills out an
appointment-request form, a symptom checker, a "request a callback" form naming a condition).
Tracking technology on those surfaces that transmits identifiable data to a third party (Google,
Meta, an analytics vendor) still implicates HIPAA in the same way OCR's original guidance described.
(`(third-party)` — same corroborating sources and retrieval as claim 47; none of those law-firm
alerts is itself HHS's primary guidance text, so this claim is UNVERIFIED against a primary source
on the same basis as claim 47, until the `hipaa` lane re-fetches the HHS page directly.)

**Applied rule (internal doctrine, derived from claims 47–48 above):** no pixel, tag, GA4 event, or third-party script may
transmit health information from an **appointment, treatment, or portal page**, or from **any form
submission**, for the practice's public web presence. Generic, non-identifying analytics on an
ordinary public informational page (e.g. a page-view event on a general "our services" page, with
no condition-specific query string or form-submit payload attached) is not per se prohibited by
this specific ruling — but see §5 below: Google's and Meta's own advertising policies restrict
health-related signals independently of HIPAA, and those are the actual operative gate for ad
platforms regardless of the HIPAA analysis.

## 4. Patient-list and third-party data restrictions

**[KB-COMPLIANCE-049]** **Customer Match, enhanced conversions for leads, and any offline/online
conversion upload built from a patient list are prohibited for a HIPAA-covered practice's Google
Ads account until the compliance lane has independently verified the specific use against both
this file's HIPAA analysis (§1–2) and Google's own advertiser data policy** (see claims 52–53
below — Google Ads Help, "Health in personalized advertising,"
`support.google.com/adspolicy/answer/16701855`, and "Customer Match policy,"
`support.google.com/adspolicy/answer/6299717`, both official, retrieved 2026-09-27, both directly
naming Customer Match/advertiser-curated audiences as restricted for sensitive-interest-category
(health) data — this is a platform-policy prohibition independent of, and in addition to, the HIPAA
authorization question). This restates this file's own §1–2 HIPAA analysis together with claims
52–53's Google-policy prohibition
as a standing prohibition, not a request
for review — the default is **no**, and only a specific, KB-cited, dated approval changes that for a
specific use. This claim is itself a standing policy restatement, not a new primary-source fact —
its evidentiary weight rests entirely on claims 43–46 (HIPAA) and 052–053 (Google policy) above
and below; see those for the underlying citations.

**[KB-COMPLIANCE-050]** **UNVERIFIED (primary source unreachable:
`hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/northcutt/index.html`)** — that
page, and HHS's own hosted PDF of the resolution agreement/corrective action plan
(`hhs.gov/sites/default/files/northcutt-dental-racap.pdf`), both returned HTTP 403 to this session's
automated fetch tool at retrieval time (2026-09-27). A patient list used for any purpose beyond
direct treatment/operations of the practice itself is a live enforcement risk independent of
marketing framing. **Northcutt Dental-Fairhope, LLC** settled with HHS OCR for $62,500 after
impermissibly disclosing a spreadsheet of 3,657 patients' names and addresses to a campaign manager,
who mailed letters to those patients announcing the practice owner's state Senate campaign (a
second, related disclosure to a third-party marketing firm, Solutionreach, added roughly 1,727 more
patients by email for the same campaign, bringing the combined total reached to 5,385) — a
disclosure with no treatment purpose and no valid authorization on file. (`(third-party)` —
corroborated across independent reporting, all retrieved 2026-09-27: Becker's Dental
(`beckersdental.com/dentists/38210-alabama-dental-practice-to-pay-62k-after-sending-senate-campaign-announcement-to-patients.html`),
JD Supra/COSMOS Compliance Universe (`compliancecosmos.org/ocr-targets-three-dentists-new-enforcement-actions-nixes-political-use-phi-review-backlash`),
GovInfoSecurity (`govinfosecurity.com/hhs-ocr-issues-4-hipaa-enforcement-actions-a-18807`), and
DrBicuspid (`drbicuspid.com/dental-practice/article/15379297/practice-settles-claim-it-used-patient-data-in-political-bid`)
— settlement amount ($62,500) and patient count (3,657) agree across sources; GovInfoSecurity
specifically reports the 5,385 figure as the combined total (3,657 original recipients plus 1,727
newly-added patients whose information was added for the Solutionreach email disclosure), not the
size of the second batch alone — corrected here to match what that source actually reports. The
announcement month is reported as 2022 across these sources, and this file's prior "March 2022" is
not independently confirmed by any of them, so the specific announcement month is left unstated here
pending direct confirmation. This claim stays UNVERIFIED against a primary HHS source until the
`hipaa` lane re-fetches the resolution agreement directly.) **Relevance to this doctrine:** this case's
facts are about a patient-list export used for a non-treatment, non-marketing purpose (political
campaigning), not a review reply — it is cited here, distinct from the review-reply cases in §6,
specifically because it is the clearest available precedent (third-party sourced; see the UNVERIFIED
marking above) for the patient-list-export risk underlying claim 49's prohibition. Any request to
export, upload, or share a patient list for
*any* purpose outside direct patient care is a `hipaa`-lane review item, never an autonomous GTM
action.

**[KB-COMPLIANCE-051]** Vendors that will receive PHI as part of a marketing or communications
workflow (a call-recording/transcription vendor, a form-hosting vendor, a chat/booking-widget
vendor) need a signed Business Associate Agreement (BAA) on file before that data flow is enabled.
(internal doctrine, standard HIPAA business-associate practice.) **UNVERIFIED (primary source unreachable:
`law.cornell.edu/cfr/text/45/164.502` / `law.cornell.edu/cfr/text/45/164.308`):** the BAA
requirement itself is well-established HIPAA doctrine, but this file does not independently cite
the specific regulatory provision (45 CFR § 164.502(e) / § 164.308(b) govern business associate
arrangements) — no direct fetch of either provision's text was attempted in this pass, so the
provision numbers above are stated from general knowledge, not confirmed against the text this pass
— the `hipaa` lane must confirm the current BAA requirement text
directly against 45 CFR Part 164 Subpart E before treating any specific vendor as cleared, rather
than relying on this restated summary alone.

## 5. Ad-platform health-data policies (independent of, and in addition to, HIPAA)

These are the platforms' own advertising policies. They apply **regardless of** whether a given
data flow would separately violate HIPAA — a use can be perfectly fine for HIPAA purposes and
still be a platform policy violation (account suspension, ad disapproval), or vice versa. Treat
both gates as independently binding.

**[KB-COMPLIANCE-052]** Google Ads: health is a named **sensitive interest category** under
Google's personalized-advertising policy. "Advertisers promoting products and services that fall
within sensitive interest categories are unable to use advertiser-curated audiences" — this
explicitly includes **Customer Match audiences, an advertiser's own data segments, audience
expansion, and lookalike/similar segments.** (Official, Google Ads Help / Advertising Policies
Help, "Health in personalized advertising,"
`support.google.com/adspolicy/answer/16701855`, retrieved 2026-09-27 — page content fetched
directly.) Health content is defined broadly: "physical or mental health conditions, diseases,
sexual health, chronic health conditions, products and services to treat or manage chronic health
conditions, and any health issues associated with intimate body parts or functions" (same source
and retrieval).

**[KB-COMPLIANCE-053]** Google's separate Customer Match policy independently states: "Advertisers
can't use sensitive interest categories to target ads to users or to promote advertisers' products
or services," and "You can't use data from your Customer Match campaigns to identify sensitive
interest categories related to your customers." It also names pharmaceutical-adjacent advertising
specifically as a restricted use within Customer Match. (Official, Google Ads Help, "Customer
Match policy," `support.google.com/adspolicy/answer/6299717`, retrieved 2026-09-27 — page content
fetched directly.) **Note (2026-09-27, from the same research pass):** Google has since carved out
an exception allowing Customer Match/remarketing for campaigns that target **licensed healthcare
professionals in their professional capacity** — this exception is about targeting *providers*,
never about using a *patient* list, and does not change claims 49/52/53 as applied to
the practice's own patient data. (`(third-party)`, reported consistently across trade coverage,
retrieved 2026-09-27 — not independently re-verified against Google's own primary text in this
pass; treat as UNVERIFIED for the exact scope/eligibility mechanics if it is ever relied on.)

**[KB-COMPLIANCE-054]** Meta: Meta operates a "Sensitive Health Information" / restricted-data
policy for Meta Business Tools (Pixel, Conversions API, SDK, Custom Audiences) that is understood
to prohibit sharing data tied to health or medical conditions for use in audience-building —
`(third-party)`, consistently reported across multiple independent marketing-compliance sources
(retrieved 2026-09-27), naming prohibited categories such as medical conditions, mental-health
states, medical devices/procedures/treatments, medications, and health-condition-indicating
locations, with tiered enforcement (restricted businesses may lose custom-event/parameter sharing
entirely). **UNVERIFIED (primary source unreachable:
`facebook.com/business/help/361948878201809`)** — Meta's own Business Help Center pages
(that URL, "About Sensitive Health Information," and
`facebook.com/business/help/1057016521436966`, "About restricted Meta Business Tools data") render
as JavaScript-driven pages that returned only a page title with no readable body text to this
session's fetch tool at retrieval time (2026-09-27); the mechanism above is corroborated by multiple independent
third-party compliance write-ups agreeing on substance, but the exact policy wording is not
independently confirmed here. **Treat the exact enforcement mechanics (which specific event types,
which tier thresholds) as UNVERIFIED and prohibited-until-verified** — the `hipaa`/trust-architect
lane must re-fetch these pages directly (a headed browser render, not an automated text fetch,
per this corpus's own standing pattern for JS-heavy or bot-blocked pages, `shared/citation-style.md`) before
approving any Meta Pixel/CAPI event design for the practice that carries even indirectly
health-adjacent signal.

## 6. PHI in review replies and social-media responses — two enforcement cases (third-party sourced;
primary HHS pages unreachable — see claims 55–56)

**[KB-COMPLIANCE-055]** **UNVERIFIED (primary source unreachable:
`hhs.gov/about/news/2019/10/02/dental-practice-pays-10000-settle-social-media-disclosures-of-patients-phi.html`)**
— the live HHS.gov page, and a pagefreezer.com archived snapshot of it located this pass
(`public3.pagefreezer.com/content/HHS.gov/31-12-2020T08:51/https:/www.hhs.gov/about/news/2019/10/02/dental-practice-pays-10000-settle-social-media-disclosures-of-patients-phi.html`),
both returned HTTP 403 to this session's automated fetch tool at retrieval time (2026-09-27); no
reachable copy of the primary HHS text was found this pass. **Elite Dental Associates** (Dallas, TX)
settled with HHS OCR for $10,000 plus a two-year corrective action plan, after responding to a
patient's negative Yelp review by disclosing that patient's name along with details of her
treatment plan, insurance, and cost information. OCR's investigation found the practice had
impermissibly disclosed PHI of **multiple** patients across several Yelp review replies, not just
the one that triggered the complaint. (`(third-party)` — corroborated across independent legal
reporting, all retrieved 2026-09-27: Ballard Spahr
(`ballardspahr.com/insights/alerts-and-articles/2019/10/ocr-announces-10000-settlement-for-disclosure-of-patients-phi-through-social-media`),
HIPAA Journal (`hipaajournal.com/dental-practice-fined-10000-for-phi-disclosures-on-yelp/`), the
National Law Review (`natlawreview.com/article/dental-practice-pays-10000-hipaa-settlements-disclosing-personal-health-information`),
and AccountsRecovery.net
(`accountsrecovery.net/2019/10/04/dental-practice-accused-of-posting-phi-on-social-media-settles-with-hhs-for-10k/`)
— settlement amount, practice name, and disclosure mechanism agree across sources; the "October 2,
2019" announcement date matches the HHS URL's own date segment (`/2019/10/02/`), which is
corroborating structural evidence even though the page body itself could not be fetched. This claim
stays UNVERIFIED against a primary source until the `hipaa` lane re-fetches the HHS press release or
a reachable archived copy of it directly.)

**[KB-COMPLIANCE-056]** **UNVERIFIED (primary source unreachable:
`hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/new-vision/index.html`)** — that
page, and the related resolution-agreement/CAP page
(`hhs.gov/hipaa/for-professionals/compliance-enforcement/agreements/new-vision-ra-cap/index.html`),
both returned HTTP 403 to this session's automated fetch tool at retrieval time (2026-09-27). **New
Vision Dental** (B. Brandon Au, DDS, Inc., California) settled with HHS OCR for $23,000 (announced
December 14, 2022) plus a two-year corrective action plan, after OCR investigated a complaint that
the practice's owner had responded to negative Yelp reviews by disclosing patient identities —
including, per some third-party reporting, patients who had used only a pseudonym/moniker on the
review platform — along with treatment and insurance information. The corrective action plan
required removal of social media posts containing PHI (some reporting states as far back as January
1, 2014) and breach notification to affected patients. (`(third-party)` — corroborated across
independent legal/trade reporting, all retrieved 2026-09-27: HIPAA Journal
(`hipaajournal.com/ocr-fines-california-dental-practice-for-phi-disclosures-on-yelp/`), SC Media
(`scmagazine.com/analysis/privacy/dentist-settles-hipaa-violations-for-disclosing-information-replying-to-yelp-reviews`),
Bloomberg Law (`news.bloomberglaw.com/health-law-and-business/hhs-dental-practice-resolve-alleged-health-privacy-violation`),
and ComplianceHome (`compliancehome.com/californian-dental-practice-issued-23000-fine-for-sharing-phi/`)
— settlement amount, date, and practice identity agree across sources. This claim stays UNVERIFIED
against a primary source until the `hipaa` lane re-fetches one of the two HHS agreement pages
directly.)

**Applied rule (internal doctrine, derived from claims 55–56 above — and the anchor
for this KB's non-confirming
review-reply template guidance below):** these two cases establish, with real enforcement money
attached, that the *specific mechanism* to avoid is: (a) confirming that a reviewer is a patient at
all, (b) disclosing any treatment, condition, insurance, or cost detail in a public reply, and (c)
doing this even when the *patient themselves* posted identifying or health-related information
first — OCR's position in both cases was that the practice's *own* disclosure was the violation,
regardless of what the patient volunteered publicly. A GTM agent handling a negative review for a
regulated practice must never draft a reply that does any of (a)–(c), regardless of what
information the original review contains or how sympathetic a factual correction would be.

### 6.1 Non-confirming review-reply template guidance

Every reply to a public review, for a HIPAA-covered practice, drafted by any GTM seat, must:

1. **Never use language that confirms or implies the reviewer is or was a patient** — no "Thank
   you for being our patient," no "We're sorry your treatment didn't meet expectations," no
   "We've reviewed your chart." Use neutral language that would be equally true whether or not the
   commenter has ever set foot in the practice.
2. **Never restate, correct, or reference any clinical, financial, or insurance detail the
   reviewer included in their post** — even to dispute it. Correcting "that filling cost $400, not
   $600" is itself a PHI disclosure under both settled cases' logic, because it confirms the
   commenter's specific billing/treatment facts.
3. **Never disclose or reference dates of service, treatment names, provider names paired with the
   reviewer, or outcomes.**
4. **Invite the conversation offline** to a channel that itself does not confirm patient status
   publicly (a phone number or a generic "please contact our office" — never "please call about
   your appointment," which itself implies the person had one).
5. **Escalate, don't draft-and-publish autonomously, for any reply where the review names a
   specific clinical detail, alleges malpractice, or threatens legal action** — those go to the
   practice's own compliance/legal contact as a card, per the company's own `hipaa`-lane
   reviewer-of-record assignment (a content-judgment reviewer for the reply text; a security/
   trust reviewer for anything touching a tracking/data-flow decision — see the company's own
   pack/dossier for the specific seat names).

**Reject example (mirrors the Elite Dental Associates facts, claim 55):** "Hi [Name], we're sorry
your root canal on the upper left molar didn't go as expected — your insurance covered most of the
$1,200 cost and we'd like to make it right." (Confirms patient status, procedure, tooth location,
and cost — three separate PHI elements in one sentence.)

**Pass example:** "We take all feedback seriously and would appreciate the chance to learn more —
please call our office at [number] so we can look into this." (Confirms nothing; invites private
follow-up; equally sendable to a non-patient troll review.)

## 7. Dental-board / state advertising-claims pointer

**[KB-COMPLIANCE-057]** Every U.S. state prohibits false, deceptive, or misleading dental (and
more broadly, health-professional) advertising, enforced by the state's own dental board with
penalties ranging from a fine to license suspension or revocation. A specific, recurring violation
pattern: a practice advertising itself as a "specialist" in an area the state board does not
recognize as an accredited specialty (e.g. "cosmetic dentistry specialist" in a state that does not
recognize cosmetic dentistry as a specialty) is treated as false/misleading advertising in its own
right, independent of any HIPAA question. North Carolina's rule is illustrative and directly
sourced: it is false or misleading for a dentist to hold themselves out as a specialist "unless
they have completed a qualifying postdoctoral educational program accredited by an agency
recognized by the U.S. Department of Education." (`(third-party)`, consistent reporting across
multiple state-bar/health-law sources on this general pattern, retrieved 2026-09-27; the North
Carolina rule text is itself reachable at the state's own administrative-code mirror,
`reports.oah.state.nc.us`, 21 NCAC 16P — **UNVERIFIED (primary source unreachable:
`reports.oah.state.nc.us/ncac/`)**, not independently opened and quoted in this
pass; treat the exact NC rule text as needing direct verification before citing it in a specific
practice-specific claims-policy document, and treat every OTHER state's specific specialist-recognition
list as fully UNVERIFIED and state-specific until independently pulled for whichever state
the practice operates in.)

**Applied rule (internal doctrine, derived from claim 57 above — `claims_policy`;
the specific state board / claims-policy terms for a given practice live in that company's own
pack/dossier):** before any GTM seat drafts ad copy,
website copy, or a GBP post for the practice using the words "specialist," "specialize(s) in," or an
equivalent claim of advanced/exclusive expertise in a named area, the `hipaa` lane confirms (a)
which state dental board governs the practice, (b) whether that board formally recognizes the named
area as a specialty, and (c) if recognized, that the specific practitioner named holds the
accredited credential the board requires. Absent that confirmation, treat any specialist-type claim
as prohibited — use accurate, non-specialty framing instead ("experienced in," "offers," "focuses
much of the practice on") which makes no formal specialty claim.

## 8. Standing procedure for this lane

1. **Default-deny.** Every item in §1–7 above that is marked UNVERIFIED is treated as prohibited
   until a `hipaa`-lane reviewer (a content reviewer for copy/creative; a security/trust reviewer
   for tracking/pixel/conversion/form/call-recording/chat/booking changes — see the company's own
   pack/dossier for its specific reviewer-of-record assignment) verifies it
   from a primary source and updates this file's claim with a resolved citation and retrieval date.
2. **Never let a downstream seat re-derive HIPAA doctrine from memory.** Any GTM seat touching a
   practice's public item or data-flow change cites the specific `[KB-COMPLIANCE-NNN]` claim it is
   relying on; a claim not found in this file is not assumed — it is raised to the `hipaa` lane as
   a new research item, not guessed.
3. **A verified claim's shelf life:** platform ad policies (§5) move faster than HIPAA regulation
   or settled case law (§1–4, §6) — re-verify any §5 claim older than 90 days before it anchors a
   new campaign or pixel-configuration decision, per `shared/citation-style.md`'s general
   re-verification guidance.
4. **This file never contains real patient data, real practice names, or real account
   identifiers** — it is doctrine, not a working file. The specific practice's own facts (which state
   board, which vendors, which specific claims policy) live in that company's own pack, not here.

---

## Contractor bend

There is no home-services-contractor bend for this file — its audience is a HIPAA-covered
practice (e.g. a dental office), a different buyer archetype from the rest of this corpus. The
equivalent translation for that buyer: a solo or small-group practice owner has no in-house
compliance staff and is far more likely to have seen a competitor post something like the Elite
Dental or New Vision Dental reply and assume it is normal or even a savvy way to "clap back" at an
unfair review. When explaining a refusal to this buyer, skip the CFR citations and lead with the
concrete consequence: "the last two dental practices that did exactly this each paid a five-figure
settlement to the federal government and had to let regulators monitor them for two years — over a
single Yelp reply." The obligation to refuse the shortcut is entirely on the agent, exactly as
`seo/ANTI-PATTERNS.md`'s contractor-bend section states for its own domain — never wait for the
practice owner to ask whether something is allowed.
