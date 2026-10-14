# Dental-Practice Local-Marketing Notes — Where This Directory's Doctrine Diverges

Corpus for the `local/` domain. Company-agnostic: every example below is generic, not a real
practice's account or numbers. Citation format per `shared/citation-style.md`; claim ids continue
the `[KB-LOCAL-NNN]` sequence (continuing from `lead-marketplace-economics.md`'s 040-046 — this file
starts at 047). Retrieval date for every claim below: 2026-09-27, unless noted otherwise.

**Scope boundary, stated up front:** this file covers *local-presence and local-marketplace*
doctrine differences for a dental/medical practice buyer archetype — GBP category and multi-location
setup quirks, review-platform dynamics specific to patient reviews, and local-listing platform
differences from the residential-GC archetype the rest of this directory is written for. **This file
contains zero HIPAA, PHI, or patient-privacy doctrine.** Every compliance question — what a practice
may say in a review reply, what may be tracked on a web page, what may be sent to a patient list, what
ad-platform health-data restrictions apply — is owned entirely by
`compliance/hipaa-marketing-for-practices.md` and its `[KB-COMPLIANCE-NNN]` claim series. Any GTM
seat working a practice account reads that file for compliance and this file only for the
local-presence mechanics that differ from the home-services default. Where the two files might seem
to overlap (e.g. "can we respond to a bad review"), the compliance file's ruling controls without
exception — this file never restates or paraphrases a compliance rule, it only points to it.

---

## 1. Why a separate file exists at all

**[KB-LOCAL-047]** Every platform doctrine file in this directory (`gbp-optimization.md`,
`yelp.md`, `nap-consistency.md`, etc.) is written company-agnostic but with a residential-remodeling
GC buyer archetype in mind for its "Contractor bend" section — for home-services/contractor
(`local_service`) companies, whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md` (`shared/contractor-buyer-psychology.md` is a different,
B2B software-buyer persona, used elsewhere only as an owner-operator behavior illustration). A
dental or medical practice shares
the *mechanism* of every rule in those files (one GBP profile per business location, the NAP-
consistency discipline, the no-review-solicitation rule) but differs in three structural ways
covered below: multi-location/multi-provider profile structure, the category-selection stakes tied
to licensure, and review-reply content risk being categorically higher than for a home-services
business. **Mechanism, not itself requiring an external citation** — this is a restatement of why
the buyer-archetype split exists in this corpus's own house style (see `seo/INDEX.md`'s "Contractor
bend" convention, generalized here to a second buyer archetype).

## 2. GBP: locations, providers, and the specialty-category stakes

**[KB-LOCAL-048]** The one-profile-per-business rule and the multi-brand/same-owner rules in
`gbp-optimization.md` §1–§2 apply to a dental practice exactly as written — a multi-location practice
group needs one profile per genuinely separate location, not one shared profile, and two practices
under common ownership at different addresses are not the "duplicate" case `gbp-optimization.md`
[KB-LOCAL-002] describes (different addresses is not the trigger condition; re-read that claim's
exact trigger list before assuming a multi-location group has a duplicate-profile problem it does
not have).

**[KB-LOCAL-049]** **Where this differs from the GC archetype:** a dental practice's GBP category
selection (`gbp-optimization.md` §3) is not merely a ranking-optimization choice the way "kitchen
remodeler" vs. "general contractor" is for a GC — claiming a specialty category or naming a
"specialist" designation the practice's state dental board does not recognize is a *separate,
board-enforced advertising violation*, independent of and in addition to any GBP policy question.
This is not a GBP-platform rule; it is a state-licensing rule that happens to surface on the GBP
category field and in GBP Posts/Q&A copy. **This exact rule, with its citation, already lives in
`compliance/hipaa-marketing-for-practices.md` §7** ([KB-COMPLIANCE-057]) — this file does not
re-derive or re-cite it, it only flags that the GBP category field is one of the surfaces where that
compliance rule applies, so a GTM seat editing a practice's GBP category does not treat it as a pure
SEO decision the way it would for a GC.

**[KB-LOCAL-050]** Provider-level structure: some practices maintain a GBP profile per individual
practitioner in addition to (or sometimes instead of) a practice-level profile — this is the
"individual practitioners at a shared location" exception `gbp-optimization.md` [KB-LOCAL-004]
already names as a legitimate multi-profile case, not a novel rule for dental specifically. The
practical difference from the GC archetype is only that this pattern is *far more common* for
practices (a multi-dentist group routinely wants each dentist findable by name) than for a
remodeling GC, so a GTM seat should expect and plan for it by default on a practice account rather
than treating it as an edge case.

## 3. Review platforms: the content-risk asymmetry

**[KB-LOCAL-051]** The mechanical review-platform doctrine in this directory — Yelp's
no-solicitation rule (`yelp.md` §1), the recommendation/filter algorithm (`yelp.md` §2), platform
account-access risk (`yelp.md` §3) — applies identically to a dental practice; nothing about being a
healthcare provider changes what Yelp's own policy permits or how its algorithm works.

**[KB-LOCAL-052]** **Where this differs, and differs sharply:** for a GC, the worst outcome of a
badly-drafted review reply is reputational (an unprofessional-sounding response, a public argument
with a customer). For a dental or medical practice, a badly-drafted review reply carries an
*enforcement* risk with real settlement money attached in two documented HHS OCR cases for exactly
this failure mode (`compliance/hipaa-marketing-for-practices.md` [KB-COMPLIANCE-055],
[KB-COMPLIANCE-056]). **Both of those cases are UNVERIFIED against a primary source as of this
writing** — the compliance file's own citations mark each `UNVERIFIED (primary source unreachable)`:
the live HHS.gov pages returned HTTP 403 to that pass's automated fetch, so only third-party legal/
trade reporting (corroborated across multiple independent outlets) backs the settlement amounts and
facts, not HHS's own text directly. **This file does not restate those cases, their verification
status, or the reply-drafting rules that follow from them** — every review
reply for a dental/medical practice must be drafted per
`compliance/hipaa-marketing-for-practices.md` §6.1's non-confirming template guidance, full stop,
before any of this directory's own platform-specific review doctrine (tone, timing, escalation
routing) is applied on top of it. Treat the compliance file's reply rules as a mandatory pre-filter,
never as an alternative to this directory's platform mechanics.

**[KB-LOCAL-053]** Review-volume and review-velocity expectations also run differently: a dental
practice's patient base is typically smaller and lower-frequency than a remodeling GC's customer
base relative to typical review-request cadence doctrine elsewhere in this corpus
(`reputation/review-velocity-metrics.md`, if further detail is needed) — but the *solicitation
mechanics* (never ask directly, never incentivize, never gate) are identical and covered fully by
`yelp.md` §1; this file adds no new solicitation rule for dental, because none exists beyond the
platform-universal one already documented there.

## 4. NAP consistency: provider-name complexity

**[KB-LOCAL-054]** The canonical-source NAP discipline in `nap-consistency.md` §1–§2 applies
unchanged. **Where this differs:** a dental practice's "Name" field is more often unstable across
platforms than a GC's, because practices commonly operate under a DBA that differs from the
practice-owner-dentist's own legal/professional name (e.g. "Main Street Family Dental" as the DBA,
with an individual dentist's name appearing separately on state licensing/insurance-panel records),
and because practice ownership changes (an associate buying in, a practice being acquired by a
dental service organization) trigger exactly the rebrand-discipline pass `nap-consistency.md` §4
([KB-LOCAL-021]) already describes — the mechanism is identical, but a practice's name volatility
from ownership/provider changes makes the NAP audit cadence in `nap-consistency.md` §5
([KB-LOCAL-022]) worth running more frequently than the default cadence used for a stable-ownership
GC.

## 5. Local-marketplace platforms: mostly not applicable

**[KB-LOCAL-055]** Angi/HomeAdvisor, Thumbtack, and Houzz Pro (this directory's marketplace-lead
platforms) are built for home-services trades and are **not** relevant local-marketplace channels
for a dental or medical practice — a practice's local-presence channel mix is GBP, Yelp, and
practice-specific platforms (e.g. Healthgrades, Zocdoc) that sit outside this directory's current
scope entirely. **Do not port `lead-marketplace-economics.md`'s cost-per-booked-job method to a
dental account by substituting "leads" from a home-services marketplace** — that file's method is
channel-agnostic in principle, but its worked inputs (§3 of that file) assume the specific platforms
this directory documents; a practice-specific lead-economics analysis needs its own inputs from
whatever practice-specific platforms it actually uses, which are UNVERIFIED — seeded, needs
derivation (no practice-specific marketplace doctrine exists in this corpus as of this writing).

## 6. What this file explicitly defers

**[KB-LOCAL-056]** The following are out of scope for this file and must not be improvised from it:
patient-communication rules (email/SMS to a patient list, appointment reminders, recall campaigns) —
`compliance/hipaa-marketing-for-practices.md` §2, §4; ad-platform health-data/audience restrictions
— same file, §5; state dental-board specialty-claim verification for a *specific* state — same file,
§7, which is itself marked UNVERIFIED per-state pending independent derivation; any tracking
technology or pixel decision on a practice's web presence — same file, §3. A GTM seat that finds
itself needing to answer one of these from this file instead is using the wrong file.

---

## Contractor bend

This file's buyer is not the contractor persona the rest of this directory otherwise addresses — it
is a dental or medical practice owner, per `compliance/hipaa-marketing-for-practices.md`'s own note
that no GC-style "contractor bend" applies to that file. The same holds here: when explaining any
local-presence mechanic to a practice owner, skip the SEO-optimization framing this corpus otherwise
leads with for a GC, and lead instead with licensure and liability, because that is what actually
worries this buyer and what actually differs from the home-services default documented elsewhere in
this directory — "your GBP category isn't just about ranking, it's a claim your state board can act
on" lands with this buyer the way "don't let Google think your two businesses are the same business"
lands with a multi-brand GC owner (`gbp-optimization.md`'s own Contractor bend). Never let a
practice-account review reply, GBP category choice, or patient-list touch skip the compliance file's
gate on the theory that "it's basically the same as the GC playbook" — the mechanism is the same,
the stakes and the required checks are not.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend across these platforms. Every claim id
in this file is unique within the `local/` domain; do not reuse `[KB-LOCAL-NNN]` numbers already
used by a sibling file in this directory (047-056 claimed by this file as of 2026-09-27; check every
sibling file's own range before adding a new claim to any file in this directory).*
