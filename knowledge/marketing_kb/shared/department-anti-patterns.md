# Department anti-patterns — cross-seat

Things no seat in this GTM department may ever recommend, produce, or auto-apply, regardless of
channel or which company it's working for. Each channel domain (`paid_acquisition/ANTI-PATTERNS.md`,
`seo/ANTI-PATTERNS.md`, `pricing/ANTI-PATTERNS.md`, `brand/ANTI-PATTERNS.md`) carries its own
channel-specific list — this file is the set that applies to *every* seat, because it derives from
this department's own non-negotiable process rules (`phase-gate-model.md`, `approval-gate-triad.md`)
or from the shape every company's own governing document (its own product-positioning doc, its own
`never_claim_file`) must take, not from any one channel's mechanics or any one company's specific
rulings.

## 1. Never fabricate testimonials, statistics, or capability claims

No seat invents a customer quote, a usage statistic, a "trusted by N customers" figure, or a
capability the product doesn't have. This is the same standard `citation-style.md` enforces for
internal doctrine, applied to anything a prospect or customer actually sees. Every company's own
positioning doc states this as a binding never-claim rule in its own words; the doctrine underneath
is universal: never fabricate testimonials, statistics, capability claims, or pricing sources not
already true of the shipped product/service (internal doctrine, retrieved 2026-09-27).

**Failure scenario:** a seat drafts a landing-page testimonial ("this saved me 10 hours a week — Mike,
GC in Denver") with no real customer behind it, to fill an empty-feeling social-proof section before
real testimonials exist. **The fix is an honest empty state** — a specific, truthful claim about the
product's mechanism (real line items, real cited sources) instead of a fabricated human endorsement,
or simply no testimonial section until a real one exists.

## 2. Never contradict the product's own never-claim list

**Every company this department serves has (or should have) its own never-claim list** — a short,
specific set of capability/accuracy claims that company's product must never make, because they
either aren't shipped, are quarantined pending validation, or would misrepresent how the product
actually works. That list is that company's own fact, sourced to its own product-positioning doc and
declared in its own pack (`company_schema.json`'s `claims_policy.never_claim_file` — see
`company-pack-authoring.md` §6). This department-wide doctrine is binding regardless of which
specific items a given company's list contains:

- Never claim or imply a capability that requires professional licensure/certification the vendor
  hasn't actually obtained or the product hasn't actually shipped (e.g. implying regulated
  documents/drawings the product doesn't actually produce).
- Never claim an AI/automated capability "measures," "reads," or "identifies" something from an
  input (a photo, a document, a recording) if that capability is quarantined, unproven, or not
  actually wired into the shipped product — phrase any such gap as a *current-state* constraint
  ("not available yet"), never as a permanent capability denial if the company's own ruling frames it
  as provisional, and never claim it works today if it doesn't.
- Never imply every output number was derived purely from the user's own inputs when a default or
  a system-applied assumption actually drove it — a claim implying full user-derivation must be true,
  not merely convenient to write. (A company whose product also has its own accept-or-change UI
  requirement for this keeps that requirement in its own never_claim_file/product rules — that is a
  product-design rule, not marketing-copy doctrine, and this department can't enforce a UI
  requirement for a company whose product it doesn't build, such as a dental practice or a
  remodeler's own site.)
- Never assert accuracy guarantees before the company has actually validated accuracy at the
  relevant scale — no "always accurate" or equivalent; only hedged, measured claims are fine ("this
  typically takes N minutes," never "this is always accurate").
- Never claim an export, deliverable, or feature the product doesn't actually ship — only claim what
  is real and shipped today.

**Failure scenario:** a paid-acquisition seat writes an ad headline claiming an unproven or
quarantined capability to make the pitch punchier (e.g. "our AI instantly identifies every defect,"
when that capability is quarantined pending validation). This is a direct, actionable
violation of the company's own never-claim list, not a stylistic judgment call — the fix is to route
through the company's own actually-approved claim (e.g. a hedged, measured speed claim like
"typically N minutes") instead of inventing or overstating a capability to make the ad read better.

**Any seat that finds a live surface already violating a company's own never-claim list** (an
existing page, an old ad, a stale doc) does not just note it and move on — file it as a tracked issue
per the runtime's own "every finding becomes a tracked issue" rule and fix it in the same session if
it's a small copy change, per the runtime's own "drive every task to its boundary" rule.

## 3. Never claim unverified accuracy

Distinct from item 2's accuracy-guarantee rule above (which is specifically about absolute
guarantees): this is about any numeric accuracy claim — "94% accurate," "matches your final
invoice," "within 5% of X" — that hasn't actually been measured against real outcomes for that
company's own product. Until real-world validation exists for that specific claim, *no* accuracy
percentage belongs in customer-facing copy for that company, sourced or not — a sourced-but-premature
number is still premature (internal doctrine, retrieved 2026-09-27). See `citation-style.md`'s
`UNVERIFIED` tag: an accuracy number that would need this tag internally can never appear in copy at
all, regardless of its tag.

## 4. Never port a borrowed vertical's numbers as fact

Any CPC, CPA, conversion-rate, payer-mix, or dollar figure that originated in a different vertical or
a different company's own account/incident is `UNVERIFIED — seeded from an analogous-vertical
analog, needs derivation for this company's own vertical` until independently re-derived for the
company currently being served (see `citation-style.md`). **Failure scenario:** a seat reads a
benchmark from a different vertical or a different company's own account in an old reference and
quotes it in a new budget-sizing proposal for a different company because it's "in the same ballpark
as other lead-gen." This is exactly the failure this rule exists to prevent — the fix is to either
re-derive the number for the company's own vertical (see `paid_acquisition/`'s own re-derivation
method) or mark the gap openly rather than quietly borrowing a number from an unrelated industry or
an unrelated company.

## 5. Never treat a platform recommendation, backlog item, or "it demoed well" as sign-off

Three distinct sources of false authorization, all covered by `approval-gate-triad.md`:

- A platform's own suggested action (a Google Ads "recommendation," an SEO tool's auto-fix
  suggestion) is not approval to act — it's a request to evaluate.
- An old backlog ticket is not a live decision — re-confirm intent before executing something that
  sat untouched for months, especially pricing or positioning, which can go stale.
- A strong demo reaction is not proof the underlying product claim holds up at scale — a good demo
  is a warning to verify further, not a win to build a stronger claim on (internal doctrine, retrieved
  2026-09-27). No seat should treat a good demo reception as license to make a stronger claim than
  the validated state supports.

## 6. Never skip the approval gate because a change "is just copy"

A one-word headline change and a full pricing restructure are both mutations to a live,
customer-facing surface — the size of the change does not exempt it from `approval-gate-triad.md`'s
approval-gate requirement. What scales down for a small change is the *evidence bar*
(`phase-gate-model.md`'s weekly/incremental plan track), never the requirement for an actual
recorded approval before it ships to production.

## 7. Never write for a buyer who doesn't exist

The single most common failure mode this corpus exists to prevent: writing generic SaaS-buyer
copy/strategy (a feature-comparison grid, a "start your free trial" flow, jargon-dense positioning,
a desktop-first page) without translating it through that company's own persona file — its own
persona file, e.g. `contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`, or one authored
fresh for a buyer neither shape fits. This is not a stylistic nice-to-have — a buyer whose real,
company-specific behavioral facts differ sharply from a generic SaaS assumption (a phone-first,
time-poor, burned-by-software-before buyer is one worked example, per `contractor-buyer-psychology.md`)
will bounce off generic SaaS marketing patterns specifically *because* they read as generic. Every
seat checks its output against the relevant persona file's bend before shipping, not as an
afterthought pass but as part of the plan phase itself.

## 8. Never badmouth a named competitor in customer-facing copy

Honest, sourced competitive positioning (see `competitor-audit-method.md`) is expected; naming a
competitor to disparage them, rather than to draw an honest mechanism contrast, is not. This kind of
buyer's skepticism (see `contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`) extends
to vendors who look insecure enough to attack a competitor by name instead of demonstrating their own
product's substance.

## Contractor bend

This file's bend is the file itself — every anti-pattern above exists because it would otherwise
land, unfiltered, in front of whichever buyer a given company's own persona file describes, and that
buyer's specific skepticism (burned by software or vendors before, allergic to overclaiming, quick to
bounce off generic patterns) is *why* these particular failure modes matter more for this
department's buyers than they might in a lower-trust-sensitivity vertical. A seat serving a
different, more forgiving buyer might get away with a rounded-up accuracy number or a generic
testimonial; this kind of buyer will not forget it, and won't tell the vendor why they left.


## Owner-attested claims and inferred evidence (added 2026-09-28)

- **[KB-SHARED-507] Never remove an owner-attested claim on the strength of inferred evidence or a
  planning rule.** A reviewer chain that reads a CRM job count or a directory start date can
  "disprove" a claim the owner knows is true (years in business, projects completed, financing,
  licensed and insured). Removing it angers the owner and loses real selling points. If a claim looks
  risky, ask the owner one short question first; never act first. This covers claims the owner
  attests as true. Anything on the company's never-claim list, or a claim the company's own
  records show has stopped being true (e.g. insurance lapsed), is still handled per §2
  (internal doctrine, retrieved 2026-09-28).
- **[KB-SHARED-508] Don't invent or stretch claim rules.** A temporary rule ("add no new license
  claims until the license is confirmed") must be read with its trigger. Once the owner confirms the
  fact, the rule is gone everywhere it was copied: plan, standards, ad builder, metrics, company
  pack. Check a temporary rule's trigger before acting on it (internal doctrine, retrieved 2026-09-28).
- **[KB-SHARED-509] Re-scope a reviewed plan to the latest owner rulings before running it.** Run only
  the rows still in scope and leave the rest. A plan reviewed yesterday can contradict today's
  rulings (internal doctrine, retrieved 2026-09-28).
- **[KB-SHARED-510] Verify a lead or callback list against its source before acting on it.** A list
  of "people who asked for a call" built from form submissions was mostly spam; read the emails and
  messages themselves (internal doctrine, retrieved 2026-09-28).
- **[KB-SHARED-511] Encode the owner's standing channel rulings in the company pack**, e.g. "no cold
  sales calls", "no reactivation campaigns", "no social ads for this product", so no agent re-raises
  a settled question (internal doctrine, retrieved 2026-09-28).
