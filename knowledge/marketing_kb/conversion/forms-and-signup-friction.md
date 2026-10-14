# Forms and Signup Friction

Field count, field types, button copy, and trial/signup shape — grounded in Baymard's checkout/form
research (the closest evidence-graded proxy for any form a company puts in front of a visitor) and
a CRO procedure's form-optimization section, reconciled against a company's own already-ruled
signup model (see the company's own pack/dossier for what that model actually is).

## What the evidence says about form field count

- **The average US checkout displays 23.48 form elements (14.88 counting only actual input fields);
  Baymard's own usability testing puts the optimum at 12–14 elements (7–8 real fields)** (official,
  Baymard Institute, retrieved 2026-09-05).
- **Completion rates drop 4–6% for every field beyond the eighth** (official, Baymard Institute,
  retrieved 2026-09-05). This is a hard, numeric gate: an 11-field form is measurably worse than an
  8-field form, not just "probably a bit worse."
- **Nearly 1 in 5 shoppers has abandoned specifically because a checkout felt "too long /
  complicated"** (official, Baymard Institute, retrieved 2026-09-05).
- **A 20–60% reduction in shown form elements is achievable on most checkouts without losing
  needed information** — much of the excess is optional fields shown by default, not fields the
  business actually needs (official, Baymard Institute, retrieved 2026-09-05).

**Numeric gate, with pass/reject examples (worked for a B2B SaaS signup form):**

- **REJECT:** A signup form with 11 visible fields (name, company name, company address, phone,
  email, password, confirm password, company size, industry, how did you hear about us, referral
  code). Three fields beyond the 8-field threshold — expect a measurable completion-rate hit
  per the 4–6%/field-beyond-8 finding. REJECTED as written; push "how did you hear about us,"
  "referral code," and "company address" to post-signup onboarding.
- **PASS:** A signup form with 6 fields (name, email, password, company name, phone, and the
  required card fields, if a card-required model applies — see the company's own pack/dossier).
  Under the 7–8 optimum. PASS.

## Form mechanics that matter regardless of count

- **Field labels must be understandable in isolation, especially on mobile** — "Billing Phone," not
  just "Phone," because mobile users tend to focus on each field as an isolated task rather than
  reading the whole form's context (official, Baymard Institute, retrieved 2026-09-05).
- **Use correct HTML input types** (`type="tel"`, `type="email"`) so mobile keyboards adapt
  automatically — a real, near-zero-cost fix (internal doctrine, retrieved 2026-09-05).
- **Leverage autofill and address/postal lookups** to reduce manual entry and prevent avoidable
  errors (official, Baymard Institute, retrieved 2026-09-05).
- **Inline validation, specific error messages** — "Please enter a valid phone number," never
  "Invalid input" (internal doctrine, retrieved 2026-09-05).
- **Button copy should name the specific action**, not a generic verb. The source CRO doctrine is
  explicit: "'Get My Free Quote' converts better than 'Submit'. Avoid 'Submit' — it is generic and
  creates anxiety" (internal doctrine, retrieved 2026-09-05). Translate this to the actual action
  for the product being reviewed — e.g. "Start estimating" or "Create my first estimate" for an
  estimating tool — never a bare "Submit" or "Sign up."
- **Privacy assurance near the form reduces anxiety about handing over contact/payment info**
  (internal doctrine, retrieved 2026-09-05) — directly relevant to a card-required-at-signup model,
  where one exists (see below): a line near the card field restating the money-back guarantee does
  real anxiety-reduction work here.

## Trial/signup shape — what the evidence says about card-required vs. not

- **Card-required ("opt-out") trials convert at 35–55% trial-to-paid (median ~44%)**; **no-card
  ("opt-in") trials convert at only 8–22% (median ~14%)** — card-required trials convert
  roughly 3–4x higher, because the friction-to-cancel exceeds the friction-to-convert
  (third-party, aggregated SaaS-benchmark research incl. ChartMogul/Growth Unhinged/ProductLed
  Jan-2026 report and First Page Sage's 50+-client dataset, retrieved 2026-09-05). **Caveat, stated
  honestly:** card-required trials also produce lower raw signup VOLUME than no-card trials — the
  same research notes this explicit tradeoff (third-party, retrieved 2026-09-05); the 3–4x
  conversion-rate gap is not a free lunch, it trades quantity of signups for quality/conversion of
  the ones who do sign up.
- **A company may have already resolved this question in the harder direction — check the
  company's own pack/dossier before assuming either model.** Some companies settle on no free trial
  at all: "card required at signup; charged day one," typically justified by a documented free-trial
  farming/abuse exposure. Where that is the case, this is even further along the friction-for-
  quality spectrum than a card-required trial — a conversion-architect reviewing that company's
  signup flow should NOT recommend reverting to a no-card trial (that would reopen whatever farming
  exposure the ruling specifically closed), but SHOULD treat the risk-reversal mechanism (e.g. a
  an N-day money-back guarantee, no conditions) as doing the persuasion work a trial would otherwise
  do, and check that the guarantee is stated AT the point of card entry, not just buried on a terms
  page.

## The A/B test priority order for a company's own forms

Per a CRO procedure's own priority-ranked list of form tests (internal doctrine, retrieved
2026-09-05): (1) number of fields, (2) button text, (3) form placement, (4) multi-step vs.
single-step, (5) with/without a specific field (e.g., phone) to see if removing it lifts signups
before a follow-up call qualifies the lead. This order is a genuinely portable prioritization
heuristic — apply it unchanged to any company's own signup-form backlog rather than inventing a
different order.

## Multi-step forms — when they help

The source material's guidance: for a genuinely complex form (not a basic signup, but perhaps a
higher-tier qualification form), break into steps with a progress bar, easiest fields first, harder
fields later — leaning on the commitment-and-consistency principle that people who've started tend
to finish (internal doctrine, retrieved 2026-09-05). For a basic 6-ish-field signup, a single step
is almost certainly correct per the field-count math above; multi-step is a tool for genuinely long
forms, not a default pattern to apply everywhere.

## Buyer-segment bend (B2B software sold to trade-business owners; persona: `shared/contractor-buyer-psychology.md`)

1. **Mobile field-type correctness matters more, not less, for this buyer.** "Phone-first, in a
   truck" means a meaningful share of signups will happen on a phone keyboard with a spotty
   connection — the `type="tel"`/`type="email"` fix and aggressive field-count discipline aren't
   nice-to-haves here, they're the difference between a completed signup and an abandoned one on a
   job site with one bar of signal.
2. **The guarantee has to be visible AT the moment the card field appears, not just referenced
   earlier on the page.** This buyer's prior is that software companies make it easy to sign up and
   hard to get money back — restating a real money-back guarantee's actual terms directly next to
   the card field (not just in the hero or a footer link) is the specific anxiety this buyer carries
   into that exact moment, and it is the form-privacy-assurance principle above applied to his
   specific fear.
3. **Never ask for anything that reads as "sales qualification" before the product is even seen.**
   A field like "estimated annual revenue" or "number of employees" on the signup form itself (as
   opposed to inside onboarding, after signup) reads to this buyer as being sorted into a sales
   funnel rather than just starting to use a tool. This is a known real-world failure mode (internal
   doctrine, retrieved 2026-09-05): a qualification screen that fires only after the visitor has
   already used the product once reads as a sales-lead-scoring gate rather than a feature toggle, and
   lands as a small bait-and-switch moment — exactly the kind of weakness a competitor teardown can
   flag (see the company's own pack/dossier for its own competitive-teardown citations, where one
   exists). Collect that data later, inside the product, framed as account setup — never on the door
   into the product.
