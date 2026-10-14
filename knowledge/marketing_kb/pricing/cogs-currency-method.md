# COGS currency method — moving a calculated figure to measured

**Answers:** What does "COGS currency" mean, why is a company's per-unit COGS figure often
calculated-not-measured, and what is the general method (routing fix, instrumented cost-audit run,
unpriced-stage resolution) that converts it to a measured, trustworthy number?

"Currency" here means **evidence freshness and provenance**, not money — a COGS figure is "in
currency" when it is measured against real, tracked execution rather than derived from a token-count
or unit-cost assumption someone wrote down once. This file is this discipline's primary standing job
(see `INDEX.md` — the pricing-economist seat is a live runtime agent): a company's per-unit COGS is
often not currency-grade at launch (internal doctrine), and closing that gap is often explicitly
named as a blocker in the company's own OpEx/pricing doc where the gap exists.

## Why a calculated figure is not measured — the general shape of the gap

See the company's own pack/dossier for where its OpEx/pricing doc and pricing source-of-truth doc
live (both are that company's own repo docs, not runtime files). The pattern below is the general
shape this discipline watches for (internal doctrine, retrieved 2026-08-28 — generalized from a
real case).

**The number itself** is typically derived from a per-unit cost model: for an AI-product company,
this is commonly a sum of per-call model costs (a vision/analysis call, a synthesis call, an
embeddings call, etc.) at assumed token counts and assumed per-model rates — a TYPICAL/LOW/HIGH
range depending on usage (e.g. number of photos analyzed, if the product is photo-based).
(internal doctrine)

**A calculated figure like this is prone to repeated correction** as its component assumptions are
checked: a rate error (a model billed at the wrong per-token rate), a call-count error (a
duplicate call the pipeline no longer makes but the cost model still prices), or a mislabel (a call
attributed to the wrong model tier). **(internal doctrine, incident: COGS figure corrected five
times in a month, never checked against a bill)** — five corrections in one month, each moving the
number meaningfully, with the figure never yet checked against a real bill. A calculated figure that
has never been checked against a real bill should be treated as provisional, however many times it
has already been "corrected."

**Two gap types to check for (internal doctrine):**
1. **A routing/pricing-table mismatch** — calls actually running on one model but priced as if
   running on a different (usually more expensive) model, or vice versa.
2. **Entirely unpriced stages** — pipeline stages confirmed to run on some model but carrying no
   cost line at all in the cost model, because it was never confirmed whether that stage is a
   distinct billable round-trip or a structured field folded into an existing call. The honest
   framing for this kind of gap: it is a floor, not a ceiling, on the true cost.

**Net effect, when both gap types are present simultaneously (internal doctrine):** the calculated
figure can be known-wrong in both directions at once — inflated by a mismatch on some calls, deflated
by unpriced stages on others. Nobody knows the net direction without measuring.

## The method that closes the gap

The exact method should be named in the company's own OpEx/pricing or pricing source-of-truth doc,
not invented here. The general shape, three steps, in order:

1. **Fix any routing mismatch first.** Any calls priced as one model but actually executing on
   another must be routed through the company's tracked cost dispatcher (whatever instrumentation
   the company already uses for correctly-routed calls) *before* measuring — measuring against a
   known-mismatched routing table would just produce a differently-wrong number with false
   confidence attached.
2. **Run the company's own cost-audit harness with real API calls enabled, against a full scenario
   corpus** (not a handful of examples) — a real cost-instrumented run that executes real API calls
   and records real billed tokens per stage, rather than an assumed token count per stage.
3. **Resolve any unpriced-stage gap.** Confirm, from the actual call sites (not from a model-policy
   table, which only says which model a stage runs on, not whether it is a separate round-trip),
   whether each ambiguous stage is a distinct billable call. Add real token-count lines to the
   company's own cost-model config for whichever are.

**What this seat's discipline does and does not do here:** the job is to know this method
exists, confirm whether it has been run, and push for it to run — not to write the
routing fix or run the harness itself if that is implementation work better suited to an engine or
platform agent; it owns the *evidence-currency* outcome, not necessarily every keystroke. Once a
real measured figure exists, the next job is purely evidentiary: compare it to the prior calculated
figure, decide whether the divergence is material (see `reopen-discipline.md`'s note on
materiality), and — if so — card it as a class (a) trigger. **This discipline never computes a new
margin table or a new price from the measured figure itself; it hands the number and the divergence
to the operator with a question.**

## Numeric gate: what counts as "material" — UNVERIFIED, seeded, needs derivation

**Every threshold in this gate is `UNVERIFIED — seeded, needs derivation` (see
`../shared/citation-style.md`) — no operator ruling sets ±15%/±30%
explicitly for any given company.** There is typically no explicit numeric threshold in a company's
own source docs for what divergence between measured and calculated COGS counts as "material" under
reopen class (a). The ±15%/±30% bands below are a **seeded default**, not calibrated to any given
company: they should be replaced by a band derived from that company's own historical correction
pattern once its pack supplies one (if past corrections each moved the figure by roughly 1.3x-3x,
that pattern is the working scale for "material" for that company specifically):

- **Pass `UNVERIFIED` (not material, no card needed):** measured figure lands within roughly ±15% of
  the prior calculated figure. Log the measured figure in the company's own OpEx/pricing doc as the
  new evidence basis, no reopen card.
- **Reject `UNVERIFIED` (material, class (a) triggers):** measured figure diverges by more than
  ~30% in either direction — e.g. an open routing-mismatch or unpriced-stage gap resolves in a way
  that roughly doubles or halves the per-unit cost, consistent with a company's own history of prior
  corrections at that scale.
- **This heuristic is `UNVERIFIED — seeded, needs derivation`.** No operator ruling sets this
  threshold explicitly for any company by default; it is a seeded default only, offered until a
  company's own pack supplies a band derived from its own correction history, or an operator states
  a real materiality bar for their own company.

## Vertical bends — trade/home-services (B2B) and local-service (B2C)

This entire method is invisible to most end buyers — they never see a COGS figure. The bend that
matters is what a *wrong* COGS figure risks for the buyer: if a company's margin math is wrong
enough in the deflated direction, a future operator could feel pressure to raise prices or cut a
usage quota to protect margin — exactly the kind of surprise repricing a price-sensitive, previously
burned buyer distrusts (see `ANTI-PATTERNS.md`'s vertical-bend note and `reopen-discipline.md`'s
vertical bend). Getting COGS right *before* it becomes a pricing conversation is how a company's
price stays stable for its buyer. A phone-first buyer in a truck (or any busy small-business buyer)
will never read a margin memo, but they will absolutely notice if their monthly price quietly climbs
a year or two in — the currency work in this file is preventive, not academic. The same holds for a
B2C local-service company: a homeowner client never sees a COGS figure either, but notices a
creeping price just the same.
