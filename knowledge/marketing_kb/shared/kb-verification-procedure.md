# KB verification procedure — the 1:1 claim_id contract

This file defines **how a knowledge-base authoring pass gets checked** before it is treated as
trustworthy doctrine. It is a process specification, not a citation-bearing content file — it is
about *how citations get audited*, not a source of facts about home services or marketing. It exists
because a citation tag (`citation-style.md`) only prevents an *unsourced* claim; it does nothing to
catch a claim whose cited source doesn't actually say what the claim says, or whose citation was
never opened at all. This is the gap `kb-verification-procedure.md` closes.

## Who runs this, and when

Per the GTM Autonomous Department plan §9: every knowledge-base directory (`local/`, `social/`,
`measurement/`, `web_ops/`, `sales/`, `compliance/`, `shared/`, and any future domain) is **authored**
by one sonnet `general-purpose` dispatch (explicit `model: "sonnet"`), then **verified** by a
**separate** sonnet `general-purpose` dispatch running this exact procedure. The two dispatches are
never the same agent instance and never share context — an author re-checking their own claim_ids is
not verification, it is the author re-reading their own work with the same blind spots intact.

**This is not any product-repo-local trade/domain verification agent a specific company might also
run** (e.g. a trade-scoped verifier for catalog/pricing/construction-code claims, defined in that
company's own repo). That kind of agent, where one exists, is a completely different verification
target with a different corpus, scoped to one company's own domain facts. This procedure is the GTM
knowledge base's own verification contract and applies only to files under the runtime's
`knowledge/marketing_kb/`.

## The contract: one verdict per claim_id, never a file-level verdict

**The unit of verification is the claim_id, never the file.** A verifier who reads a file end to end
and writes "looks good, sources seem reasonable" has not verified anything — that is exactly the
failure mode this procedure exists to prevent. For **every** `[KB-<DIR>-<NNN>]` tag found in the
file(s) under review, the verifier must independently produce a `PASS` / `FAIL` / `UNVERIFIABLE`
verdict, and the collected verdicts are what gets reported back — not a paragraph of prose impression.

### Per-claim steps (all four, every time)

1. **Extract the claim** — the specific factual or behavioral assertion the claim_id is attached to,
   stated in the verifier's own words, separate from the source's wording. This step exists to catch
   a citation that is *topically* related but doesn't actually support the specific number or
   assertion being made (a common failure: citing a page about Google Ads policy generally to support
   a specific numeric threshold that page doesn't contain).
2. **Open the cited source** — the verifier fetches or reads the actual cited URL/document/file
   section, not a memory of what that kind of source "usually says." A citation to a primary source
   (a platform help center page, a statute, a regulator's guidance, an official developer doc) is
   opened directly. A citation to an internal file (`see pricing/cogs-currency-method.md`) is opened
   at the referenced section, not assumed.
3. **Confirm the quote supports the claim** — read the actual text at the cited location and check,
   word by word where it matters (numbers, thresholds, dates, enum values), that it says what the
   claim says. A source that supports a *weaker* or *differently-scoped* version of the claim than
   what's asserted is a **FAIL**, not a pass with a note — the fix is narrowing the claim to match the
   source, not accepting the gap.
4. **Record the verdict** — `PASS` (source opened, confirmed, matches), `FAIL` (source opened,
   contradicts or does not support the claim as stated — quote both the claim and the actual source
   text that conflicts), or `UNVERIFIABLE` (the source could not be opened — paywalled, 403,
   authentication-gated, link rotted — record the exact failure, e.g. "403 Forbidden on GET", not just
   "couldn't check it").

### What `UNVERIFIABLE` means for the file under review

An `UNVERIFIABLE` verdict is not a pass by default. Per `citation-style.md`'s own tag definition: a
claim whose primary source could not be reached must already be marked in the file as `UNVERIFIED
(primary source unreachable: <url>)` by the *author* — the verifier's job on an `UNVERIFIABLE` claim
is to confirm that marking is actually present and accurately describes the failure, not to silently
wave the claim through as if it were sourced. **A claim that is asserted as settled fact but turns out
to be unverifiable on the verifier's own attempt is a FAIL of the authoring pass, not an
UNVERIFIABLE verdict** — the distinction is whether the author already disclosed the gap or asserted
confidence they hadn't earned.

## What the verifier reports

A structured result, not free-form prose:

- **Per-claim table:** `claim_id | verdict | note`. The note is required for FAIL and UNVERIFIABLE
  (what was actually found), optional for PASS.
- **Totals:** claims checked, PASS count, FAIL count, UNVERIFIABLE count.
- **File-level flags, separate from the per-claim table:** any claim with no `claim_id` tag at all
  (a bare unsourced sentence that should have been tagged and wasn't — this is itself a defect, not
  something to silently tag on the verifier's behalf), any `(internal-measured)` tag on a claim that
  is actually a *calculated* figure rather than a measured one (see `citation-style.md`'s own worked
  example of this exact mistake), and any claim ported from a different vertical or a different
  company's own numbers presented as fact rather than marked `UNVERIFIED — seeded from an
  analogous-vertical analog, needs derivation`.

A verification pass that finds **any** FAIL is not "mostly clean" — the specific FAILed claims must
be corrected (either the claim text narrowed to match the source, or a better source found, or the
claim re-tagged `UNVERIFIED`) and the corrected claims re-verified before the file is treated as
trustworthy. A verification pass never rubber-stamps a file with known FAILs still in it "because most
of it checked out."

## Why a second, separate dispatch — not the author re-checking their own work

This mirrors the same maker-checker principle the GTM department applies to every mutating action
(`approval-gate-triad.md`) and the same principle this runtime's own code-review discipline applies to
commits: the person who wrote something is the worst-positioned person to catch their own mistake in
it, because the mistake usually comes from a blind spot (a source skimmed rather than read closely, a
plausible-sounding number that "felt right" and was never actually re-checked) that re-reading the
same output doesn't surface. A genuinely separate dispatch, with no shared context and no stake in the
original draft being right, is what makes the check real rather than ceremonial.

## Adapted third-party material (marketingskills, MIT)

A section adapted from `github.com/coreyhaines31/marketingskills` (MIT-licensed) carries its own
attribution/MIT-notice requirement at the top of the file it appears in (per this KB's own
house rule) — verification treats an adapted section exactly like any other: every factual claim in
it still needs its own `claim_id` and citation, and the MIT attribution line itself is checked for
presence (a missing attribution line on adapted material is a file-level flag, not a per-claim one).

## Contractor bend

Not applicable in the direct sense — this file governs how the department checks its own internal
doctrine, not customer-facing content. The indirect connection is the same one `citation-style.md`
draws: every downstream claim that eventually reaches a buyer's inbox or landing page (per
`contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`) is only as trustworthy as the KB
claim it was built on, and this procedure is the mechanism that keeps a confidently-wrong internal
"fact" from quietly becoming a confidently-wrong claim in front of a buyer who has already been
burned by confident-sounding software or vendor claims before.
