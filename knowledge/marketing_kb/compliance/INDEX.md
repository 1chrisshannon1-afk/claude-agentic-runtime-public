# Compliance Domain — Index

Corpus for compliance doctrine consulted by every GTM seat (`content-strategist`, `conversion-architect`,
`paid-acquisition-strategist`, `pricing-economist`, `marketing-director`, and the operational `sales`/
`social`/`local` domains) before publishing copy, running an ad, sending an email/SMS, soliciting a
review, or handling personal/health data. Grep-reachable on demand — this index is how an agent finds
the right file without reading the whole corpus. Every numeric/behavioral claim in every file below
carries a citation tag with a retrieval date, or is marked `UNVERIFIED — seeded, needs derivation` /
`UNVERIFIED (primary source unreachable: <url>)`. See house-style rules at the bottom of this file.

| File | Answers |
|---|---|
| `ANTI-PATTERNS.md` | What must this domain NEVER let any seat recommend — review gating, fake/incentivized reviews, incomplete CAN-SPAM elements, consent-less autodialed texts/calls, off-window sends, mismatched A2P registration, health-adjacent geofencing, PHI in review replies, unverified claims stated as settled. |
| `ftc-endorsements-and-fake-reviews.md` | What does 16 CFR Part 465 (binding, 2024) and the older Part 255 Endorsement Guides (non-binding) actually prohibit for reviews, testimonials, and endorsements — fake reviews, buying reviews, insider reviews, fake review-sites, suppression, fake social influence — section by section, with penalty exposure? |
| `review-gating.md` | The deep-dive on the single most common review-program shortcut: selectively soliciting only likely-happy customers. What exactly makes it a violation (vs. legitimate private-feedback routing), and what does a fully compliant review-request recipe look like? |
| `can-spam.md` | What are the five mandatory elements of any commercial email (headers, subject line, ad disclosure, physical address, opt-out), the 10-business-day opt-out enforcement window, and the per-recipient penalty exposure? |
| `tcpa-a2p-10dlc.md` | What consent does the TCPA require for autodialed/prerecorded texts and calls (channel-specific, written), what are the quiet-hours/calling-window rules (federal floor + the state-variation gap), how does A2P 10DLC carrier registration work and how is it distinct from TCPA legal consent, and what per-message damages apply? |
| `privacy-and-consent.md` | What general state privacy-law obligations (disclosure, opt-out-of-sale/sharing, deletion rights) attach to lead-capture/retargeting data collection, and — as a stricter, HIPAA-independent category — what do state consumer-health-data laws (Washington's My Health My Data Act) require and prohibit, including the geofencing ban? |
| `hipaa-marketing-for-practices.md` | What does HIPAA's Privacy Rule actually require for a covered-entity practice's marketing communications — the "marketing" definition and its exceptions, when patient authorization is required, the *AHA v. Becerra* tracking-pixel ruling's actual (narrower-than-commonly-assumed) scope, PHI-in-review-replies enforcement precedent, and ad-platform Customer Match/Custom Audience health-data prohibitions? Cross-reference this file for any HIPAA-covered-entity client; use `privacy-and-consent.md` for the general (non-HIPAA-covered) case. |

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a citation tag with a retrieval date, or is marked
  `UNVERIFIED — seeded, needs derivation` (a number ported from an analogous vertical) or
  `UNVERIFIED (primary source unreachable: <url>)` (a claim whose primary regulator source blocked
  automated fetch — cited to the best reachable mirror, e.g. Cornell's Legal Information Institute
  for CFR/USC text, and explicitly labeled unverified rather than presented as settled). See
  `shared/citation-style.md`.
- Every file ends with a "Contractor bend" section translating the doctrine for a small
  owner-operated home-services/trade business archetype — phone-first, in a truck, no in-house
  legal/compliance staff, burned by software/agencies before. Compliance doctrine leads with
  dollar/business-continuity stakes for this buyer, not statutory citations.
  `shared/homeowner-buyer-psychology.md` and `shared/contractor-buyer-psychology.md` are two of
  several persona files a company pack may select — a company pack for a different vertical (e.g. a
  dental practice) selects and reads its own persona file instead, which is why
  `hipaa-marketing-for-practices.md`'s own "Contractor bend" section states plainly that no
  home-services-contractor translation applies to it and translates for the practice-owner
  archetype instead (see that file's own closing section).
- A finding that a proposed action is prohibited cites the specific file **and claim id**, not just
  "compliance says no" — this is what lets a future auditor or the operator trace exactly which rule
  fired and why.
- MIT-licensed material from `github.com/coreyhaines31/marketingskills` may be adapted into this
  corpus only with an attribution + MIT-notice line in the adapting file's header. No file in this
  directory currently carries such a notice — none of the doctrine in this directory was adapted
  from that source as of this authoring pass (2026-09-27); a future edit that does adapt from it
  must add the notice in the same change.

## Known corpus defect — claim-id numbering collision (FIXED 2026-09-27)

**Prior state:** `ftc-endorsements-and-fake-reviews.md` numbers its claims `[KB-COMPLIANCE-001]`
through `[KB-COMPLIANCE-012]`. `hipaa-marketing-for-practices.md`, written independently, **also**
numbered its own claims `[KB-COMPLIANCE-001]` through `[KB-COMPLIANCE-017]` — the same id space,
colliding, and additionally colliding with `review-gating.md`'s `013`–`017` (of its `013`–`018`
range). This meant `[KB-COMPLIANCE-001]` (and `013`–`017`) referred to multiple unrelated claims
depending on which file was open, breaking the "stable claim id" guarantee `shared/citation-style.md`
promises.

**Fix:** `hipaa-marketing-for-practices.md`'s claims were renumbered in place to the free
`[KB-COMPLIANCE-043]`–`[KB-COMPLIANCE-059]` range (its former `001`–`017`, preserving each claim's
original relative numbering — note this is NOT the same as file order: two claims added to the file
later, now numbered `058`–`059`, appear physically earlier in the file than `047`–`057`, so "in
order" describes the id assignment, not the reading order), including every
internal cross-reference (`claim NNN`, `claims NNN–NNN`) and every external citation this corpus
found referencing the old numbers: `paid_acquisition/competitor-targeting-doctrine.md` (`007`→`049`,
`010`→`052`, `011`→`053`, `012`→`054`, three call sites), `paid_acquisition/measurement-and-attribution.md`
(`007`→`049`, `012`→`054`), and `paid_acquisition/meta-ads-doctrine.md` (`012`→`054`).
`ftc-endorsements-and-fake-reviews.md` (001–012), `review-gating.md` (013–018), `can-spam.md`
(019–023), `tcpa-a2p-10dlc.md` (024–035), and `privacy-and-consent.md` (036–042) are unchanged and
were already non-colliding among themselves. As of this fix, every claim id in this directory
(001–059) is unique and traceable to exactly one claim.

## Verification pass, 2026-09-27

A direct-fetch verification pass against every citation in `tcpa-a2p-10dlc.md` and
`privacy-and-consent.md` found and fixed: two dead primary-source URLs (`campaignregistry.com`'s
"what is A2P 10DLC" page, 404; RCW 19.373 cited alone for a private-right-of-action holding it
doesn't itself state), two FCC consumer-facing URLs that return 403 to automated fetch and were
wrongly labeled `(official)`/reachable with no unreachable flag (claims 024 and 027 in
`tcpa-a2p-10dlc.md`), one claim misdated (claim 027's "any reasonable means" TCPA-revocation
standard actually originates from the FCC's 2015 Omnibus ruling, codified by a February 2024 order —
not a single "2023 ruling"), and several claims (025, 036, 037, and parts of 032–035) that presented
this corpus's own doctrine inference or generalization as if the cited primary source stated it
directly — all corrected in place with a dated correction note, per this corpus's own house style
(never delete a wrong claim silently; correct it in place with what the source actually says, or
mark it UNVERIFIED and say why). No file's substantive doctrine recommendations changed as a result
— every correction either re-sourced the claim to a source that actually supports it, narrowed the
claim to what the source supports, or relabeled a corpus-authored inference as doctrine rather than
as a sourced legal holding. The pre-existing `KB-COMPLIANCE-001`–`017` numbering collision was fixed
by the renumbering documented above (`hipaa-marketing-for-practices.md`'s claims moved to
`043`–`059`), not merely flagged.

**Follow-up correction, same date:** a second pass on claim 036 found the specific figure "twenty US
states... as of January 1, 2026" was *also* unsupported as an IAPP-tracker citation — the cited IAPP
tracker page's fetchable/extractable text carries no specific numeric state count at all (the count
sits in an interactive chart the HTML-to-text conversion does not capture), confirmed by fetching the
page twice, once with a prompt asking specifically for any stated count. The figure was re-sourced to
a secondary tracker (MultiState) and explicitly marked `UNVERIFIED (primary source unreachable)`
against the IAPP tracker itself for that specific count, with a standing instruction to re-pull a
current count before citing an exact figure.

**Third-pass correction, 2026-09-27:** a verification pass found the re-sourced figure itself had been
mistranscribed as "nineteen" states while citing a MultiState page titled "20 State Privacy Laws in
Effect in 2026." Direct fetch of that page (performed twice) confirms it states, verbatim, "Twenty
states now have comprehensive privacy laws on the books" — not nineteen. Corrected in place in
`privacy-and-consent.md` claim 036 to **twenty**, matching what the cited source actually says. This
is the kind of error the house style above exists to catch: a claim can carry a real, reachable,
correctly-labeled citation and still assert a specific number that citation does not actually
contain — and, as this instance shows, the error can be introduced by a correction pass itself, not
just by the original authoring.

**Fourth-pass correction, 2026-09-27:** an independent verifier found claim 038 (MHMDA privacy-policy
requirement) asserted the required consumer health data privacy policy must be "a specific standalone
consumer health data privacy policy separate from a general privacy policy." Direct fetch of the
cited statute (RCW 19.373.020) confirms it requires the policy to disclose specific categories and
have a link "prominently publish[ed]... on its homepage," but does not state or imply the policy must
be a standalone document distinct from a general privacy policy — either a separate document or
disclosures integrated into a general privacy policy satisfies the statute's actual language.
Corrected in place in `privacy-and-consent.md` claim 038 (and its downstream checklist reference at
claim 038's item in the "Working checklist" section) to state only what the statute requires; the
rest of claim 038 (effective date, HIPAA-independence, broad consumer-health-data definition,
opt-in-consent requirement, and the geofencing prohibition) was independently confirmed against
RCW 19.373.010/.020/.080 and was already correctly sourced.

**Fifth-pass correction, 2026-09-27:** an independent verifier found `hipaa-marketing-for-practices.md`
claim 050 (Northcutt Dental-Fairhope settlement) phrased the 5,385-patient figure as if it were the
size of the second (email) disclosure alone. The cited corroborating source (GovInfoSecurity) actually
reports 5,385 as the *combined* total across both disclosures (3,657 original mailed recipients plus
1,727 patients newly added for the second, email disclosure via Solutionreach) — the email disclosure
alone was ~1,727 patients, not 5,385. Corrected in place in `hipaa-marketing-for-practices.md` claim
050 to state the combined-total framing explicitly, with a note on what was corrected and why; the
claim's overall `UNVERIFIED (primary source unreachable)` status is unchanged, since the HHS primary
source remains unreachable to automated fetch. The same verifier pass re-confirmed that every claim in
that file marked as relying on an unreachable primary source already carries the required
`UNVERIFIED (primary source unreachable: <url>)` format — no other correction was needed for that file.

## Cross-domain pointers (things adjacent to compliance that belong to a different domain)

- **Consent Mode / cookie-banner technical implementation** belongs to the `measurement` domain
  (`measurement/consent-mode.md`, per the runtime GTM department plan §9 registry) — this domain
  states the legal requirement (`privacy-and-consent.md`), not the GTM-container wiring.
- **Review-response drafting and reputation-management operational workflow** (response templates,
  escalation policy, review-request campaign mechanics beyond the gating violation itself) belongs to
  the `reputation` domain — this domain covers only the compliance boundary (`review-gating.md`,
  `ftc-endorsements-and-fake-reviews.md`), not the full operational playbook.
- **CRM/scheduling-tool auto-texting configuration** (the actual workflow-builder mechanics of when a
  text fires) belongs to the `sales` domain (`sales/crm-hygiene.md` per the runtime GTM department
  plan §9 registry) — this domain covers only what consent must exist before that workflow is
  allowed to fire (`tcpa-a2p-10dlc.md`).
- **Paid-ad platform policy beyond health-data prohibitions** (Google Ads/Meta general ad-content
  policy, account-suspension risk unrelated to health data) belongs to the `paid_acquisition` domain —
  this domain covers only the health-data-specific Customer Match/Custom Audience prohibitions
  referenced in `privacy-and-consent.md` and `hipaa-marketing-for-practices.md`.
