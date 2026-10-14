# Content Domain — Anti-Patterns

Things a content-strategist seat must NEVER recommend or write. Each entry names the rule, the
incident or citation that created it, and a concrete reject example. This file is the fast
pre-publish check — grep it before shipping any headline, email, script, or review response.

## 1. Never claim an unmeasured speed number

**Rule:** For a company whose real, measured speed claim is fast but variable, the only sanctioned
claim is the measured, hedged phrasing that company has actually verified (e.g. "typically
[measured range]") — never a rounder, punchier, unmeasured figure like "20 minutes," "instant," "in
seconds," or any other time figure the company has not actually measured.

**Citation (internal doctrine — mechanism, re-derive the exact phrasing and figure from the
current company's own positioning doc before use):** a company's own positioning doc should state
its one sanctioned speed phrasing explicitly and ban any looser internal-strategy shorthand (an
unhedged before/after comparison used only for internal planning) from leaking into
customer-facing copy.

**Why this recurs:** an audited company's own shipped email sequences have been found carrying
exactly this defect — an internal, unmeasured, or superseded speed figure surviving into a live
subject line or body after the sanctioned claim was set. Treat any looser speed figure found in
live copy as a live defect needing a fix-forward pass (file as an issue per that company's own
process discipline), not a hypothetical example. A claim about the length of a *human* call or
walkthrough is a different referent than the product's own generation-speed claim and is not this
violation.

- REJECT: "Get a full estimate in under 20 minutes."
- REJECT: "From photos to proposal — instantly."
- ACCEPT: "Typically [measured range] from job description to estimate." (re-derive the current
  company's own measured figure — do not reuse an unqualified round number.)

## 2. Never claim a capability that isn't shipped and gate-cleared for the current company

**Rule:** Never claim a capability in copy that is not actually shipped, proven, and cleared for
customer-facing claims by the current company's own product/engineering source of truth. Before
writing any capability claim, check that company's own never-claim list or positioning doc for
what is and isn't currently claimable — a capability that is real for one company in this KB's
roster (e.g. a shipped photo-measurement feature, a permit-drawings deliverable, a
site-visit-elimination workflow) may be entirely unshipped or unproven for another, so no specific
capability is universally banned or universally safe here; the company's own list governs.

**Citation (internal doctrine — mechanism):** a company piloting an AI capability under a
quarantine/shadow-mode gate (i.e. the capability runs internally but is not yet trusted enough to
be a customer-facing claim) should never let marketing copy claim it as live before that gate
clears. Re-derive the current gate status from the company's own positioning doc or engineering
ruling record before writing copy that touches any such capability.

**Illustrative example (photo-measurement) — for a company whose AI-assisted product does not
measure rooms, dimensions, or scope from photos** (photos are a customer-supplied context input a
human or model uses, never something the product "reads," "measures," or "identifies scope
automatically" from, for that company):

- REJECT: "Just snap a photo and let the AI measure your bathroom."
- REJECT: "Upload a photo — we'll figure out the dimensions."
- ACCEPT: "Upload photos of the existing space for context — you tell us the measurements."

This is one illustrative instance of the general rule above, not a standalone universal ban — check
the current company's own never-claim list before applying it verbatim.

## 3. Never turn an operational workflow choice into a capability claim

**Rule:** Copy may describe an operational workflow choice the way it actually works (e.g. "no site
visit needed for our process") but must never turn that workflow choice into a claim about a
capability the company does not actually produce — most commonly, a deliverable like permit-grade
drawings that a "no site visit" framing can be misread as implying.

**Citation (internal doctrine — mechanism):** re-derive the current company's own never-claim list
for the exact workflow-vs-capability line it draws; check that list before writing any copy that
frames an operational shortcut as a customer-facing outcome.

- REJECT: "Skip the site visit — we'll generate permit-ready drawings from your photos." (turns a
  workflow choice into an unshipped-deliverable claim)
- ACCEPT: "No site visit needed to get started." (describes the workflow choice only, makes no
  claim about a deliverable beyond what's actually true today)

## 4. Never present a ruled/assumed default as if the user's exact input drove it

**Rule:** For a company whose engine fills gaps with defaults, every such default must be shown to
the user as accept-or-change (per that company's own product ruling, where one exists). Copy must
never describe generated numbers as though they came purely from what the user typed, when a
default filled a gap.

**Citation:** re-derive the exact ruling reference from the current company's own positioning doc /
internal ruling record.

- REJECT: "Every number is calculated exactly from what you told us."
- ACCEPT: "We fill in typical values where you didn't specify — you can always change them before
  you send."

## 5. Never promise accuracy guarantees pre-convergence

**Rule:** No "always accurate," no guaranteed-correct claims, no implication an AI-driven engine has
already cleared its own accuracy bar while it is still early in its measured track record — the
bar is a meaningful sample size of real usage, not the first job.

**Citation:** re-derive from the current company's own positioning doc.

- REJECT: "Guaranteed accurate estimates every time."
- ACCEPT: "[The company's concrete mechanism claim] — not an AI guess." (a company-specific
  differentiator line; re-derive the current company's own equivalent phrasing rather than
  inventing one here.)

## 6. Never fabricate testimonials, stats, or claim unshipped features

**Rule:** Never invent a customer quote, a stat, or describe a capability that isn't actually
shipped for the current company's product. Where a company has retired an export/feature (e.g. a
scope-of-work or material-list export superseded by a different shipped export), copy must track
what's actually live today, not what shipped historically or was once planned. This is the same
mechanism as #2 above, applied to fabricated proof points and retired features specifically.

**Citation (internal doctrine — mechanism):** re-derive the current company's shipped-feature list
from its own positioning doc or product/engineering source of truth before writing a capability
claim; check the current company's own never-claim list (see #2 above).

- REJECT: "Export a full scope of work and material list in one click."
- ACCEPT: "Convert your estimate into a work order your sub can act on."

## 7. Never author a rival or duplicate policy/guardrails/tracker document

**Rule:** A content-strategist seat proposes copy and doctrine, never a second "master" tracker,
positioning doc, or pricing-analysis doc alongside the ones a given company already maintains.

**Citation (internal doctrine, mechanism):** a knowledge-base search finding no existing policy
doc for a company is not license to author one — check the company's own docs/pack for its
canonical positioning, pricing-analysis, or tracker doc first; that doc governs uniformly. Many
companies name their own single canonical cost/pricing-analysis doc explicitly ("the ONLY cost or
pricing analysis doc — never create another") — respect that rule wherever a company states it.

- REJECT: writing a new "positioning guide v2" doc for a company that already has a canonical
  positioning doc.
- ACCEPT: proposing an edit to the existing doc, or escalating a contradiction via that company's
  own decision-queue/operator-input surface.

## 8. Never gate reviews or condition an incentive on sentiment

**Rule:** Illegal review gating (asking for star rating first, routing only happy customers to
the public review link) and any incentive conditioned — explicitly or implicitly — on a review
being positive, are both banned outright. See `../reputation/never-do.md` for the full FTC citation
and mechanics.

**Citation:** FTC Consumer Review Rule, 16 CFR Part 465, effective 2024-10-21 (official, retrieved
2026-09-05, ftc.gov: `https://www.ftc.gov/legal-library/browse/rules/consumer-review-rule`). Related
FTC guidance (16 CFR Part 255, Endorsement Guides §255.5, material connections — official, retrieved
2026-09-28, `https://www.ecfr.gov/current/title-16/chapter-I/subchapter-B/part-255`): if
incentivizing referrals, the referrer must disclose the incentive.

**(internal doctrine):** review-gating is a critical-severity finding wherever an audit surfaces it.

## 9. Never write a defensive or argumentative public review response

**Rule:** Every negative-review response acknowledges, never argues, never discloses private
customer/job details, and always offers an offline resolution path.

**Citation (internal doctrine — mechanism, not a platform-policy citation):** never post a
defensive or templated response; a draft must be reviewed by a human before submission;
acknowledge the concern, apologize without admitting liability, offer a resolution path, take the
conversation offline. Never ignore a negative review. Never argue publicly. (Google Business
Profile's own review-reply guidance, support.google.com/business/answer/3474050, retrieved
2026-09-27, describes only that replies are public and the reviewer is notified by email — it does
not itself state the behavioral rules above; do not attribute this rule's substance to that page.)

- REJECT: "That's not what happened — our crew has photos proving otherwise."
- ACCEPT: "I'm sorry the framing timeline didn't match what we discussed. I'd like to make this
  right — please call me directly at [number] so we can sort it out."

## 10. Never auto-post a review response or SMS/email send without an approval gate

**Rule:** No review reply, Google Business Profile post, or automated marketing send goes out
without the account owner's (or a designated reviewer's) approval step recorded.

**Citation (internal doctrine — mechanism):** never take this class of action without explicit
human confirmation — the confirmation step is non-optional for any public post or review response.

**Per-company bend:** where a company has no dedicated review-management platform integration or
automated approval-card mechanism for this domain, treat "draft, then get a human's go-ahead before
it posts publicly" as the standing practice until/unless a real approval mechanism exists for that
company. Whether a given company builds this as an automated capability or keeps it fully manual is
a per-company decision, not a runtime-KB ruling.

## 11. Never let a case study/testimonial use a founder-invented dollar figure not tied to a real
customer

**Rule:** A named customer proof point (a dollar figure, a percentage improvement, a named
customer) in shipped copy must be traceable to a real customer story on file, never invented to
sound plausible — this applies to email sequences, landing pages, and any other customer-facing
copy for any company.

**Citation (internal doctrine — mechanism):** treat any unsourced customer-proof figure found in
live copy as a structural risk flag until confirmed — verify with whoever owns customer-story
sourcing for that company before further reuse, or before letting an agent write new proof points
without a real source on file. Group multiple such findings in the same live files into one
tracked issue per root-cause cluster, per that company's own issue-tracking process, rather than a
scattered, unowned flag per finding.

## Per-vertical bend

For a phone-first, software-skeptical buyer (e.g. a residential-trades contractor) who has been
burned by overclaiming software before, a single overclaim (a speed number that doesn't hold, a
"measures from photos" claim that turns out false in the field) does more damage to that buyer's
trust than it would to a typical SaaS prospect, because word travels fast in a tight trade network
and this buyer already assumes software people lie about what their product does. Treat every
anti-pattern above as higher-stakes for this kind of vertical than in a generic B2B SaaS content
program. Adjust the stakes framing per the current company's own buyer, using its own persona pack
(see `../shared/` for reusable buyer-psychology persona files).
