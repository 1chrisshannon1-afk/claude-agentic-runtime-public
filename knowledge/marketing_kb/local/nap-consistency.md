# NAP Consistency (Name, Address, Phone)

Domain doctrine for keeping Name/Address/Phone identical across every platform a local business
appears on — the single cheapest, highest-leverage local-SEO hygiene item and the one most often
broken silently by call-tracking numbers, rebrands, and moves. Company-agnostic. Every claim
carries a `[KB-LOCAL-NNN]` id per `shared/citation-style.md`.

---

## 1. What NAP consistency means and why it is a ranking signal

**[KB-LOCAL-017]** "NAP" is the standard local-SEO shorthand for Name, Address, Phone — the three
identity fields that every local-business directory, map platform, and review site asks for, and
that local-search ranking systems cross-reference across the web as a trust/legitimacy signal.
Every local ad platform effectively creates its own citation of the business's NAP data; keeping
NAP identical everywhere prevents that cross-referencing from reading as a fragmented or
untrustworthy business identity. (third-party, Whitespark's annual Local Search Ranking Factors
survey, retrieved 2026-09-28: https://whitespark.ca/local-search-ranking-factors/ — the 2026 edition
lists citation signals, including NAP consistency, among the top-5 background ranking factors for
the local pack, weighted at roughly 7% of overall local-pack ranking weight and an estimated 35%
within the "Prominence" pillar specifically; re-verify the exact current-year weighting against the
live report before quoting a specific percentage to a customer, since Whitespark republishes this
figure annually and it drifts year to year). This
mechanism is fully vertical-agnostic — it is a property of how ranking systems weight consistency,
not something specific to any one industry.

**[KB-LOCAL-018]** Google's own guidance requires a business's public-facing name to "reflect your
business's real-world name, as used consistently on your storefront, website, stationery, and as
known to customers" — i.e., the canonical name itself is defined by real-world consistency, not by
whatever a marketer decides is more keyword-rich. (official, Google Business Profile Help,
"Guidelines for representing your business on Google," retrieved 2026-09-27:
https://support.google.com/business/answer/3038177)

## 2. The canonical-source discipline

**[KB-LOCAL-019]** Before touching any listing, establish ONE canonical NAP record — the exact
legal/DBA name, the exact address format (suite/unit conventions, abbreviation style), and the
exact primary phone number — and treat every platform's listing as something to be brought into
agreement with that canonical record, never the reverse. A canonical record with no single source
of truth is how drift starts: one platform gets updated after a move, another does not, and now
there are two "correct" answers with no way to tell which is current without an audit.

**Reject example:** updating the address on the website after an office move but leaving the old
address live on three directory listings because "the phone number still works."

**Pass example:** a single canonical-NAP record (even a plain document) that every listing update
is checked against, updated as one coordinated pass whenever the canonical facts change.

## 3. Call-tracking numbers — the most common source of engineered NAP inconsistency

**[KB-LOCAL-020]** Lead-generation and ad platforms frequently swap in a tracking phone number in
place of the business's real number, for legitimate attribution purposes — but this creates
exactly the phone-inconsistency NAP doctrine warns against, since the number shown on that
platform now differs from the number shown everywhere else. (third-party, Sterling Sky, "How to
Track Calls on your Website from the Google Business Profile," retrieved 2026-09-28:
https://www.sterlingsky.ca/how-to-track-gmb-onsite-calls/ — confirms the mitigation mechanism too:
keeping the real number in a GBP listing's "additional phone number" field while a tracking number
sits in "primary phone" lets Google still match the real number across other directories/citations,
which is the practical form of the platform-by-platform tradeoff this section already describes).

**Mechanism, stated as a tradeoff to weigh per platform, not a blanket rule:** the attribution
value of a tracking number must be weighed against the citation-consistency cost on that specific
platform. A platform where the tracking number is the ONLY number ever shown to the searcher (never
crawled/indexed elsewhere as the business's canonical number) carries less NAP risk than one where
the tracking number gets scraped into other directories or citation-aggregator databases.

**Reject example:** deploying a call-tracking number on every platform simultaneously with no
review of which platforms' listings get picked up by third-party citation aggregators.

**Pass example:** using call-tracking selectively on platforms where the ROI of attribution data
clearly outweighs the citation risk (e.g., a paid channel with its own closed reporting loop),
while keeping the real number as the NAP of record on GBP, the website, and any platform whose data
feeds citation aggregators.

## 4. Rebrand, move, and merger discipline

**[KB-LOCAL-021]** Any legal-name change, address change, or phone-number change requires an
explicit, tracked pass across every platform the business appears on, because there is no
single "push once, updates everywhere" mechanism across independent third-party platforms — each
one must be updated directly, and each one that lags becomes a live inconsistency until it is
caught. This is a direct consequence of [KB-LOCAL-017]/[KB-LOCAL-019] and is not itself a claim
requiring a separate external citation — it follows mechanically from NAP being tracked
independently per platform.

**Pass example:** a rebrand or move triggers a checklist pass across every platform listed in this
folder's `INDEX.md`, tracked to completion rather than updated ad hoc as inconsistencies are
noticed by customers.

## 5. Auditing for existing inconsistency

**[KB-LOCAL-022]** Before recommending any NAP fix, the actual live state of each platform's
listing must be read directly — never inferred or assumed from memory of "how it was set up." This
mirrors the general local-doctrine honesty rule already established for GBP-specific claims (see
`seo/local-seo-for-contractors.md` §6's "HARD PRECONDITION" on live reads before any GBP-fact
claim) — the same discipline applies to every platform's NAP field, not only GBP's.

---

## Contractor bend

For home-services/contractor (`local_service`) companies — whose relevant end-customer persona is
`shared/homeowner-buyer-psychology.md`, not `shared/contractor-buyer-psychology.md` (a different,
B2B software-buyer persona) — this buyer will not understand "NAP consistency" as a phrase and does not need to — translate it
as "does your business look like the same business everywhere someone might find you online."
The concrete, buyer-legible failure mode worth naming directly: a homeowner searches, finds the
business on two different sites with two different phone numbers, and — because this buyer's
target customer has often been burned by a fly-by-night contractor before — reads the mismatch as
a red flag ("which one is real?") rather than a harmless technicality. Frame every NAP fix as
protecting the buyer's credibility with a skeptical homeowner, not as an SEO technicality; the
ranking benefit is real but secondary to the trust benefit for this specific buyer.
