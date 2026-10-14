# Thumbtack — Doctrine

Corpus for the `local/` domain. Company-agnostic: every example below is generic. Citation format
per `shared/citation-style.md`; claim ids continue the `[KB-LOCAL-NNN]` sequence. Retrieval date for
every claim below: 2026-09-27, unless noted otherwise.

---

## 1. Two lead types: Direct Leads (Instant Match) vs. Opportunities

**[KB-LOCAL-022]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/pay-for-leads
and https://help.thumbtack.com/article/how-thumbtack-works/)** — both pages were unreachable during
this pass's automated retrieval, so the mechanism below could not be directly confirmed against
Thumbtack's own current help documentation. It is recorded here as third-party-corroborated
platform mechanics pending re-verification (third-party, aggregated Thumbtack pro-guide sources,
retrieved 2026-09-27), describing two structurally different ways a pro receives a lead —
re-verify against a live Thumbtack Pro account or the help-center pages above before citing either
mechanism as officially confirmed:

- **Instant Match (Direct Leads):** when a pro's profile is judged a strong match for a customer's
  project, Thumbtack automatically shares the pro's contact info with that customer — the pro pays a
  lower, fixed price per lead and can reach out immediately with the customer's phone number already
  in hand. This is a **passive** channel: if the customer never calls, the pro has paid for a contact
  opportunity that went nowhere, but the price point is deliberately lower to reflect that risk.
- **Opportunities (quote-based / "Open leads"):** the price is shown to the pro **upfront**, before
  they commit to anything. The pro reaches out to the customer first (rather than being
  auto-matched), and — this is the key mechanical difference — **the pro only pays the shown price
  if the customer responds to them.** No response, no charge. Because the pro only pays on a
  response, per-lead price here runs meaningfully higher than a Direct Lead (third-party
  characterization of the pricing differential — see [KB-LOCAL-024] for the specific 2x-4x figure
  and its provenance caveat).

**[KB-LOCAL-023]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/set-lead-prices)**
— this page was unreachable during this pass's automated retrieval. The claim that a pro sets their
own **max lead price** and a **weekly budget** as the levers that control spend, and that setting a
higher price for a job type increases competitiveness for that specific job type, is recorded here
as third-party-corroborated platform mechanics (third-party, aggregated Thumbtack pro-guide
sources, retrieved 2026-09-27) pending re-verification against the live help-center page or a live
Thumbtack Pro account's own pricing settings.

**[KB-LOCAL-024]** A commonly cited third-party characterization states Opportunities cost roughly
2x-4x what a comparable Direct Lead costs, because the pro only pays on customer response
(third-party, aggregated contractor-guide sources, retrieved 2026-09-27 — this specific multiple is
**UNVERIFIED**: third-party sources describe the mechanism [pay only on response, higher price], but
Thumbtack's own help pages describing it were unreachable this pass ([KB-LOCAL-022]) and so could
not confirm a fixed 2x-4x ratio; treat the mechanism as third-party-corroborated and the exact
multiplier as directional only, pending re-fetch of the official pages).

---

## 2. Refund / credit policy

**[KB-LOCAL-025]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/refund-policy)**
— this page was unreachable during this pass's automated retrieval, so Thumbtack's refund policy
for pros could not be directly confirmed against its own current documentation. The claim that pros
get a **45-day window** to request a refund on a qualifying charge, with a typical response time of
24-48 hours after the request is submitted, is recorded here as third-party-corroborated (third-
party, aggregated Thumbtack pro-guide sources, retrieved 2026-09-27) pending re-verification against
the live help-center page.

**[KB-LOCAL-026]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/refund-policy)**
— same source-reachability caveat as [KB-LOCAL-025]. The claim that some refunds are **automatic
and require no request** (e.g. when Thumbtack's Trust and Safety team flags a lead as bad, or when a
pro declines a Smart Match/Instant Match lead as not a fit) is recorded as third-party-corroborated
(third-party, aggregated Thumbtack pro-guide sources, retrieved 2026-09-27) pending
re-verification.

**[KB-LOCAL-027]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/refund-policy)**
— same source-reachability caveat as [KB-LOCAL-025]. The claim that refunds are issued as **account
balance/credit**, not a cash refund to the original payment method, is recorded as
third-party-corroborated (third-party, aggregated Thumbtack pro-guide sources, retrieved
2026-09-27) pending re-verification. This would mirror the store-credit structure seen on
HomeAdvisor/Angi (see `angi-homeadvisor.md` [KB-LOCAL-016]) even though the two platforms are
unrelated companies — a pro budgeting cash flow should not assume either platform's "refund"
returns actual cash until this is confirmed.

**[KB-LOCAL-028]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/refund-policy)**
— same source-reachability caveat as [KB-LOCAL-025]. The claim that a pro who received
**promotional credits** (as opposed to their own deposited funds), whose lead paid for using those
credits turns out to qualify under the refund policy, can still request a refund on that lead is
recorded as third-party-corroborated (third-party, aggregated Thumbtack pro-guide sources,
retrieved 2026-09-27) pending re-verification. If confirmed, this would establish that
refund-eligibility rules apply to the lead itself, not to which balance originally paid for it —
that inference should not be relied on until re-verified.

---

## 3. Profile and job-preference setup basics

**[KB-LOCAL-029]** **UNVERIFIED (primary source unreachable: https://help.thumbtack.com/article/new-pro-guide-1)**
— this page was unreachable during this pass's automated retrieval. The claim that joining
Thumbtack Pro and creating a business profile is free — the cost sits entirely on the per-lead
side, not on account creation or listing — and that setting up a service walks the pro through
defining job preferences (travel area, job types offered, availability) which directly determine
lead-matching quality and can be adjusted at any time, is recorded here as third-party-corroborated
(third-party, aggregated Thumbtack pro-guide sources, retrieved 2026-09-27) pending re-verification
against the live help-center page or a live Thumbtack Pro account.

---

## Contractor bend

The single most important thing for a GC to internalize about Thumbtack is that it runs two
genuinely different games under one roof: Instant Match is cheap and fast but entirely passive-risk
(you paid for the intro whether or not the phone gets answered on the other end), while an
Opportunity is more expensive per lead but only charges on an actual response — so a cash-tight GC
should weight budget toward Opportunities when volume is tight and toward Instant Match when the
goal is maximum call volume regardless of hit rate. As with HomeAdvisor/Angi, a Thumbtack "refund" is
**reported to come back as platform credit, not cash — UNVERIFIED, [KB-LOCAL-027]; confirm in the
pro's own account before advising** a contractor either way.

---

*File maintained under `knowledge/marketing_kb/local/`. See `INDEX.md` for the domain map and
`ANTI-PATTERNS.md` for what a GTM agent must never recommend on this platform.*


## Field note (added 2026-09-28)

- **[KB-LOCAL-063] "You're not showing up in search results. Set targeting preferences" means zero
  exposure.** No targeting means no spend and no leads, however complete the profile. Check it first
  when a Thumbtack account reports no leads (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
