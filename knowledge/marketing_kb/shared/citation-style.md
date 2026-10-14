# Citation style — provenance tags

## The rule

Every numeric or behavioral claim in this corpus — and every claim a GTM agent makes in a
proposal, audit, or piece of copy — carries one of six provenance tags plus a retrieval date (or
an origin date for `internal-measured`; no date at all for the two `UNVERIFIED` tags). No
unsourced numbers survive in this corpus. This is not
a formatting nicety: it is what makes a stale or fabricated benchmark visible at a glance instead
of quietly rotting into "fact" the way a number ported from an analogous vertical or a different
company would if ported without a tag.

| Tag | Means | Retrieval-date format |
|---|---|---|
| `(official)` | From the platform/vendor's own documentation, help center, or published policy (Google Ads Help, Meta Business Help, GSC documentation, a vendor's own pricing page). | `(official, retrieved 2026-09-05)` |
| `(third-party)` | From an independent research firm, industry benchmark report, or news outlet reporting on the vendor (WordStream, a marketing-agency benchmark blog, a trade-press article). Directional, not authoritative — the source's own methodology and sample size should be named if known. | `(third-party, retrieved 2026-09-05)` |
| `(internal-measured)` | From the company's own account data, the operator's own reported experience, or a number produced by running the company's own tooling (a real ads account export, a real conversion funnel, the company's own internal measurement harness). Origin date is when the measurement was taken, not when it was read. | `(internal-measured, 2026-09-02)` |
| `(internal doctrine)` | A mechanism this corpus itself asserts as a general, portable rule — not sourced to an outside vendor/platform page and not measured from any one company's data — including a mechanism generalized from a real, concrete case (e.g. direct pixel sampling of a real logo asset set, or a ported incident per the "Ported-incident citations" section below). The doctrine is the claim; the retrieval date marks when it was written/reviewed into this corpus, not an external fetch. | `(internal doctrine, retrieved 2026-09-05)` |
| `UNVERIFIED — seeded, needs derivation` | A number ported from an analogous vertical or a different company's own account (most often a benchmark carried over from a different vertical this department has served) or asserted from general knowledge with no direct source check. Must be visually distinct so nobody mistakes it for a real citation. | No date — the whole point is that it hasn't been retrieved yet. |
| `UNVERIFIED (primary source unreachable: <url>)` | The claim's primary source (an official vendor/platform page, a statute, a regulatory site) was identified but could not actually be fetched/retrieved during this pass (blocked, 403, gone, or otherwise unreachable) — the claim is not sourced from a live read and must be treated as unverified, and as prohibited-until-verified wherever the doctrine making the claim says so. Never silently upgrade this to `(official)` from memory of what the page "probably says." | `UNVERIFIED (primary source unreachable: https://example.com/page)` — no retrieval date, since no retrieval succeeded; the `<url>` is the specific source that could not be reached. |

## Worked examples

**Correct — official, dated:**
> Google's Local Services Ads program requires a background check and license verification before
> a contractor can display the Google Guaranteed badge (official, Google Ads Help, retrieved
> 2026-09-05).

**Correct — third-party, dated, methodology named:**
> Remodeling-specific Google Ads accounts see CPCs in the $8–$18 range and CPL in the $150–$400
> range, per managed-account aggregate data (third-party, BG Collective "Google Ads Statistics for
> Remodelers in 2026," retrieved 2026-09-05 — aggregate across the agency's own managed accounts,
> sample size not disclosed; treat as directional, not a guarantee for any single account).

**Correct — internal-measured:**
> The company's own real customer-acquisition cost, from the operator's own reported books, is
> ~$X/lead (internal-measured, `<company pack's own pricing dossier>` §N, `<date>` — the operator's
> actual paid-funnel spend divided into actual leads, not a projection).

**Incorrect — a calculated (not measured) figure tagged as if it were measured (never do this):**
> The company's own marginal cost per unit is ~$A typical, ~$B worst-case (internal-measured,
> `<company pack's own cost dossier>`, `<date>`).

This is exactly the mistake this file exists to prevent. A figure like this is often a *calculated*
cost model, not a measured bill — a company's own cost documentation may say so in its own words
("this figure is calculated, not measured, and known-wrong in both directions") and name a real
measurement run as the trigger condition that could reopen the underlying pricing ruling. Tagging a
calculated, known-wrong-in-both-directions figure `(internal-measured)` erases exactly the
distinction this tag exists to preserve. The correct tag for it in that case is `UNVERIFIED —
seeded, needs derivation`, cited to `pricing/cogs-currency-method.md` (see that file for the
calculated-to-measured method) — never `(internal-measured)` until that measurement actually runs.

**Correct — UNVERIFIED, seeded from an analogous vertical:**
> An analogous vertical's CPA benchmark for a comparable new-customer campaign was $A–$B/customer
> (UNVERIFIED — seeded, needs derivation; benchmark carried over from a different vertical's own
> account — not independently re-verified here, and not portable as a number). The *mechanism* — CPA
> gated against a segment-adjusted lifetime-value floor before a budget increase is approved — is
> `(internal doctrine)` and ports directly (see `paid_acquisition/bid-adjustment-framework.md`). The
> *number* does not: this vertical's CPA per booked job is UNVERIFIED — seeded from an
> analogous-vertical analog, needs derivation specific to this company's own trade, geography, and
> average job value.

**Incorrect (never do this):**
> Contractors typically convert at 12% and pay $45 per lead.

No tag, no date, no source — this sentence is not distinguishable from a guess and must never
appear in this corpus or in agent-authored copy/proposals.

## Retrieval-date discipline

- Use the date the *agent* actually looked at the source, not the source's own publish date if
  they differ. A 2026-01 blog post retrieved 2026-09-05 is tagged `retrieved 2026-09-05` — the
  content may have been true in January and stale by September; the retrieval date is what lets a
  future agent judge that.
- A number this corpus has been citing for more than ~90 days should be treated as due for
  re-verification before it anchors a new proposal, especially for fast-moving platform mechanics
  (bid strategies, ad formats, API scopes). CPC/CPA benchmarks move slower but still drift
  quarter-to-quarter; re-pull rather than trust an old retrieval date on anything touching budget
  sizing.
- When a number appears in more than one file in this corpus, cite the canonical source file once
  and reference it from the others (`see pricing/cogs-currency-method.md`) rather than restating
  the number with its own citation in multiple places — this is the same rule this corpus's sibling
  domains already use to avoid drift between duplicated numbers.

## Ported-incident citations — a special case of `(internal doctrine)`

When a hard rule in this corpus exists *because* something broke at a prior engagement (a real
incident, not a hypothetical), cite it as `(internal doctrine, incident: <short label>)` — keep the
incident description as originally recorded, because it is real evidence a rule is load-bearing, not
theoretical caution, but never name the company or codebase the incident happened at. Do not invent
an incident to make a rule sound more urgent than it is, and do not port an incident's *numbers*
(CPA figures, patient/customer counts, dollar amounts specific to the business involved) as if they
apply to a different company — port the mechanism the incident justifies, tag any borrowed number
`UNVERIFIED` per above.

## Contractor bend

None — this file is about how the *department* writes internally, not about content a customer ever
sees. A citation tag never appears in customer-facing copy; it exists so an agent (or a human
auditor) can trace where a number came from. The bend that matters for the buyer is indirect:
because this discipline exists, a claim that reaches an actual buyer's inbox or landing page — "loads
in under N seconds," "typically N minutes," "$X/month" — has already been checked against a real
source (that company's own ruled pricing/positioning doc, not a remembered or generic number) before
it was allowed to sound confident. A buyer who has been burned by confident-sounding software or
service claims before (see `contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`) is the
reason this file's discipline is non-negotiable, even though they will never read it.
