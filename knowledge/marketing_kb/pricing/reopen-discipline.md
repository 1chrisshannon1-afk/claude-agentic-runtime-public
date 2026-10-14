# Reopen discipline — when a settled price may be revisited

**Answers:** When may a pricing decision already ruled by a company's own pricing source-of-truth
document be revisited — what are the four evidence classes, what does the reopen rule typically
look like, and what does a seat do when it *thinks* it has found one?

## The general rule pattern (internal doctrine)

Many companies that have gone through repeated, undisciplined pricing churn (multiple ladders in a
short span, each replacing the last with no recorded operator ruling, each re-derived from scratch
by a new session with no memory of the prior decision) benefit from writing a single canonical
pricing source-of-truth document and an explicit **reopen rule** guarding it. The pattern, once a
company has ruled its pricing:

**Nothing in the pricing source-of-truth document is revisited unless a NEW CLASS of evidence
arrives:**
1. **(a)** measured per-unit COGS materially contradicting the ruled calculated figure
2. **(b)** real post-launch conversion/churn data
3. **(c)** a competitor materially repricing
4. **(d)** an explicit operator ruling

A new session re-asking the question is not grounds to reopen.

This is internal doctrine distilled from the general shape of that failure mode, not itself a
quote from any one company's document — **see the company's own pack/dossier for that company's
actual reopen rule, quoted verbatim, and its own operator ruling establishing the source-of-truth
document's authority.** Read that document directly before ever touching pricing for a real
company; do not re-derive pricing from this file alone, and do not card the operator about anything
that document already answers.

## The four reopen evidence classes, enumerated

1. **(a) Measured per-unit COGS materially contradicting the ruled calculated figure.**
   "Materially" is rarely defined numerically in a company's own source doc — treat it as a change
   large enough to move a tier's margin analysis by more than a rounding correction (a company's own
   history of rate-error corrections, if any, is a reasonable scale for "material"; a 5-10% wobble
   from real-world usage variance typically is not). See `cogs-currency-method.md` for how a figure
   moves from calculated to measured — that is the seat's own standing work, and it is explicitly
   the trigger condition for evidence class (a), not a side project.
2. **(b) Real post-launch conversion/churn data.** A company that has never shipped its ruled ladder
   cannot have class (b) evidence yet — check the company's own doc for its "implementation status"
   banner before assuming this class is available. A pre-launch A/B test, a survey, or a
   competitor's churn number is NOT class (b) — it is either class (c) if it's a competitor
   repricing, or not a reopen trigger at all.
3. **(c) A competitor materially repricing.** See `price-position-watch.md` for the monitoring
   method. A competitor adding a feature, changing marketing copy, or running a limited-time
   discount is not "materially repricing" — a published list-price change on a plan the company's
   own ladder was benchmarked against is.
4. **(d) An explicit operator ruling.** The only evidence class with no threshold — a new operator
   statement supersedes everything above it, the same way a company's canonical pricing ruling
   supersedes whatever churn preceded it. A session's own inference about what the operator "would
   probably want" is never class (d); only a real operator statement is.

## What "reopen" does NOT mean

- It does not mean re-litigating the *reasoning* behind a ruled number when no new evidence exists.
  A company's own pricing source-of-truth doc should already trace every number to its basis
  (market-sizing data, the operator's own books, competitor audits, operator rulings) — a seat
  re-deriving those same numbers from the same evidence is churn, not diligence.
- It does not mean computing a new price and presenting it as a
  recommendation, per this domain's discipline (see `INDEX.md` for the pricing-economist seat).
  Per this domain's ANTI-PATTERNS.md, the role when a
  reopen trigger genuinely fires is to **surface the evidence and ask a question** — never to
  reprice. The operator decides; this discipline instruments the decision.
- It does not mean silence when a trigger *does* fire. A reopen rule that says "do not card the
  operator about anything answered here" binds requests to relitigate settled ground — it does not
  bind a seat that has found a genuine measured-COGS divergence, a real churn signal, or a
  competitor reprice. Those go on the operator-input queue exactly as any other decision does (see
  `~/.claude/CLAUDE.md` §11's operator-input queue rule), framed as "here is new evidence in
  class (a)/(b)/(c) — do you want to revisit the ruling," never as a proposed new number.

## Worked examples (illustrative pattern — see the company's own doc for its real numbers)

**Reject — not a reopen trigger:** A new session asks "should the entry tier be a different, rounder
number — market research suggests round numbers convert better?" This is a new session re-asking
the question with no new evidence class. Answer: point to the company's own source-of-truth doc, do
not re-derive, do not card the operator.

**Accept — class (a):** A cost-audit harness is run against the full scenario corpus after a
known routing mismatch is fixed (see `cogs-currency-method.md`), and the measured figure comes back
meaningfully higher than the calculated figure — nearly double, say. This is class (a): material
divergence, measured not calculated. Action: file the measured number with its method on the
operator queue, note which margin figures it invalidates, and ask whether the ruling should be
revisited. Do not propose a new price.

**Accept — class (c):** `price-position-watch.md`'s monitoring surfaces that a named competitor has
dropped its month-to-month price by a large margin — a competitor the company's own entry-tier basis
was benchmarked against. This is class (c). Action: card it with the old and new price, retrieval
date, and source URL; ask whether the underlying market-position claim still holds. Do not propose a
new price.

**Reject — not yet possible:** A session cites "early beta tester feedback suggests the price feels
[cheap/expensive]." Beta testers who are pre-launch and comped are neither class (b) (post-launch
data) nor a competitor reprice; it is anecdote. Log it as a note for when class (b) data exists; it
is not a trigger today.

## Vertical bends — trade/home-services (B2B) and local-service (B2C)

Most buyers never see a company's pricing source-of-truth document and never should — this is an
internal governance rule for the agents that produce the buyer's price, not copy aimed at the
buyer. The bend that matters is indirect: many B2B buyers, especially in trades that have been
burned by SaaS vendors whose pricing grows unpredictably after signup, treat price stability itself
as a trust signal (see `ANTI-PATTERNS.md`'s vertical bend and `price-position-watch.md`'s vertical
bend for the adjacent angles, and the persona file the company pack selects (`persona_file`) — e.g.
`shared/contractor-buyer-psychology.md` for a B2B-software buyer, or
`shared/homeowner-buyer-psychology.md` for a B2C service buyer — for the specifics of a given
company's own buyer). The same trust mechanism applies for a B2C local-service company toward its
homeowner clients. Every time this discipline holds the line
against churn-by-reopen, it is *protecting* the buyer's trust that the price they signed up at is
stable — which is a real, if invisible, product feature for that buyer. A seat that reopens pricing
casually is not just wasting internal effort; it is one bad ladder-flip away from becoming the
vendor that buyer already distrusts.
