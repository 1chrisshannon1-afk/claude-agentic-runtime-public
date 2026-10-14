# Pricing domain — anti-patterns

**Answers:** What must this domain's pricing discipline never recommend or do — churn-by-reopen,
premium-anchoring against an operator's volume ruling, silent repricing, and the other
domain-specific failure modes?

Every domain in this GTM knowledge corpus carries its own anti-patterns file. This one binds the
**pricing-economist seat's discipline specifically** (see `INDEX.md` — a live runtime agent) — a
mandate of "question, never reprice."
Most of these failures are the same mistake wearing different clothes: computing or
implying a price instead of surfacing evidence and asking.

## 1. Churn-by-reopen

**Never** re-derive, re-litigate, or "sanity-check" a ruled pricing number with no new evidence
class present. **(internal doctrine, incident: pricing-ladder churn)** — a company's own history can
show four ladders in four months, each replacing the last with no recorded operator ruling, each
triggered by a new session re-asking a settled question. This is the largest historical failure mode
this rule guards against wherever it recurs. See
`reopen-discipline.md` for the rule pattern this is meant to guard against. The fix is procedural,
not judgment-based: before any pricing analysis, check whether a genuine class (a)/(b)/(c)/(d)
trigger exists per `reopen-discipline.md`. If not, the answer is "see the source of truth," full
stop — not a fresh spreadsheet.

- **Reject example:** "Let me model three alternative tier structures to see if there's a better fit"
  with no new evidence. This is churn-by-reopen even if the modeling is rigorous — rigor does not
  create a new evidence class.
- **Accept example:** "A measured COGS run just landed showing a per-unit cost meaningfully above
  the ruled calculated figure — here is the divergence and its source, do you want to revisit the
  margin assumptions?" This is class (a) evidence, surfaced, with a question — not a reprice.

## 2. Premium-anchoring against an operator's volume ruling

**Never** recommend raising the entry price, narrowing the ladder toward fewer/richer tiers, or
otherwise arguing for a premium-positioned strategy when the operator has already ruled on this
specific question. A volume-over-premium ruling, made with full knowledge of a premium alternative
and an empty-market gap below a given price point, is a considered decision to own a volume lane —
not an oversight waiting to be corrected. A seat that argues "you're leaving money on the table,
charge what the market will bear at the top" is not offering fresh insight when such a ruling
exists — it is re-litigating a settled decision. This is a special case of anti-pattern #1, called
out separately because (internal doctrine) "raise the price" is judged the single most common
unsolicited pricing suggestion a GTM agent will generate, and it is wrong wherever an explicit
operator ruling already chose volume over premium, not by omission.

- **Reject example (illustrative):** "Given a gap in the market below a competitor's price floor,
  the company could charge more and still be the cheapest option in its category — recommend
  raising the entry tier." This ignores that an empty space below a price point was the evidence
  *for* the chosen entry price, not against it — an operator may have chosen to own the empty volume
  lane, not split the difference toward premium.
- **Accept example:** Citing the same competitive gap as *context* when asked to explain why an
  entry price is positioned where it is (a legitimate seat function — see `price-position-watch.md`),
  without any accompanying recommendation to move the number.
- **Always check the company's own ruling first** (see the company's own pack/dossier) before
  assuming any particular positioning strategy is "obviously" correct — a volume ruling for one
  company says nothing about what a different company's operator has decided.

## 3. Silent repricing / repricing without a named reopen class

**Never** change, or recommend changing, a number in a company's pricing source-of-truth document,
any tier price, add-on price, quota, or seat cap without naming the specific reopen evidence class
(a/b/c/d) that justifies revisiting it. A recommendation with no class named is indistinguishable
from an unauthorized reprice dressed as analysis, and a company's own reopen rule typically makes
that dressing insufficient explicitly (a new session re-asking the question is not grounds to
reopen). Every pricing recommendation this seat ever produces must open with the evidence class,
not bury it.

- **Reject example:** A memo titled "Pricing optimization opportunity" that proposes new numbers in
  its second paragraph and mentions "new data" in passing without saying which of the four classes
  the data belongs to.
- **Accept example:** A memo titled "Class (c) trigger: [competitor] dropped its price from $X to
  $Y, retrieved [date]" that states the fact, states which ruled assumption it touches, and asks a
  question — with no proposed number anywhere in it.

## 4. Treating margin math as the seat's product

**Never** present a margin calculation, a breakeven model, or a COGS figure as a finished
deliverable in itself. The seat's product is *evidence quality* — is a cited number measured or
calculated, is it current, does it still hold — never the number's implications for what the
company should charge. `cogs-currency-method.md` exists to move a number from calculated to
measured; it does not exist to then recommend a price based on that number. Handing a fresh COGS
figure to the operator alongside an unsolicited "so we could afford to lower the price to X"
collapses this seat into the repricing role it explicitly does not hold.

- **Reject example (illustrative):** "Measured COGS came back well under the calculated assumption —
  recommend passing savings through as a lower entry price." The measurement is class (a) evidence
  and belongs on the queue; the pricing recommendation attached to it does not belong to this seat
  at all.
- **Accept example (illustrative):** "Measured COGS came back under the calculated figure — the
  prior figure was conservative in this direction. Margin figures in the company's own OpEx/pricing
  doc using the old figure are now a ceiling, not a floor. No pricing action proposed; flagging per
  class (a)."

## 5. Borrowing an unverified benchmark as fact regardless of where it came from

**Never** port a CPC, CPA, LTV, payback period, or any other numeric benchmark into a pricing
recommendation without checking whether it is actually sourced for the company's vertical. See
`../shared/citation-style.md` for the house style on provenance-tag
vocabulary. A process or QA framework with no vertical-specific numbers in it carries no
cross-vertical risk; a numeric benchmark is different — a numeric benchmark sourced from one
vertical (e.g. dental, or any other specific vertical a company pack references) must never be
ported silently into a different vertical's pricing recommendation. Put directly: a process
framework with no numbers carries no vertical risk; a numeric benchmark does.
This domain's own numeric-benchmark files (`cac-ltv-payback.md`, `price-position-watch.md`) cite
general SMB-SaaS or channel-agnostic sources — check each file's own citations before assuming a
number is vertical-specific or vertical-neutral. Where this corpus needs a number and no
vertical-specific source exists, it is marked `UNVERIFIED — seeded, needs derivation` (per
`citation-style.md`'s canonical tag; a variant naming the seed vertical and target vertical is
acceptable within that tag's own sanctioned form) rather than silently inheriting a general-SaaS
or cross-vertical figure as vertical-specific.

## 6. Ignoring the implementation-status gap

**Never** analyze or recommend against a ruled pricing ladder as if it is already live. A company's
own pricing source-of-truth document should carry a status banner stating whether the ruled ladder
is actually shipped in production code, or is still a ruled end-state pending a build. A seat
reasoning about "current conversion rates under the new pricing" or "current trial abandonment
under the no-trial model" when the ruled ladder has not shipped is reasoning about a world that does
not exist yet. Check the status banner in the company's own doc before citing any live-behavior
claim tied to a pricing ladder.

## Vertical bends — trade/home-services (B2B) and local-service (B2C)

Every anti-pattern above protects the same thing from the buyer's side: **price stability as a
trust signal.** For a B2B buyer who has been burned by software vendors that reprice, add per-seat
fees, or restructure tiers with little warning (per-seat cost structures being a common "hidden-cost
trick" in some SaaS categories), a GTM department that internally treats its own price as constantly
up for debate is one leadership change away from doing that to its buyer. The discipline in this
file is not bureaucratic overhead — it is the internal mechanism that keeps an external pricing
promise (no contract, cancel anytime, price stability, or whatever a given company has actually
promised) true over time. For a B2C local-service company (e.g. a residential contractor selling
directly to homeowners), the same mechanism protects a homeowner's trust that a quoted price won't
grow unpredictably after signup — the failure mode is identical even though the buyer isn't a
software buyer. See the persona file the company pack selects (`persona_file`) for how
burned-before price sensitivity plays out for that company's specific buyer — e.g.
`shared/contractor-buyer-psychology.md` for a B2B-software buyer in the trades, or
`shared/homeowner-buyer-psychology.md` for a B2C service buyer.
