# Review Gating — the selective-solicitation violation

Company-agnostic doctrine. Review gating is closely related to, but legally and mechanically
distinct from, the fake/bought/suppressed-review violations covered in
[`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) — that file is the
umbrella for all of 16 CFR Part 465; this file is the deep-dive on gating specifically because it is
the single most common shortcut a well-meaning, non-malicious business reaches for, and because the
compliant alternative is simple enough that there's no reason to risk the non-compliant version.

---

## 1. What gating is, precisely

**[KB-COMPLIANCE-013]** Review gating is **using information about a customer's expected sentiment
to decide whether, or how, to solicit a public review from them** — most commonly, asking only
customers who indicated satisfaction (via a private survey, an internal happiness score, or a
human's judgment call) to leave a public review, while quietly not asking (or routing to a private
feedback form instead of the public review link) customers who seemed unhappy. The FTC's own
guidance describes this exact mechanism: selectively soliciting reviews only from satisfied
customers, or from a subset of customers likely to be satisfied, is prohibited because it
"substantially skews the favorability of the reviews" a prospective customer sees. (official, FTC
Endorsement Guides FAQ, retrieved 2026-09-27,
https://www.ftc.gov/business-guidance/resources/ftcs-endorsement-guides-what-people-are-asking)

**[KB-COMPLIANCE-014] (official)** Gating is codified today as part of 16 CFR Part 465's review-suppression
framework (§ 465.7) — the Rule reaches not just removing/hiding reviews that already exist, but the
upstream act of engineering *which* reviews get created in the first place by controlling who's
asked. See [`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) §1 for the
full section-by-section Part 465 breakdown and penalty exposure (the same $53,088-per-violation
ceiling applies).

---

## 2. The mechanism that makes it a violation (not just "smart marketing")

**[KB-COMPLIANCE-015] (internal doctrine)** The violation isn't the sentiment survey itself — a "how did we do?" private
follow-up is normal, legitimate customer-service practice. The violation is **using the answer to
that survey as a gate that determines whether the person is invited to leave a *public* review.**
The distinguishing test: does every customer who completed the same type of job, at the same
lifecycle touchpoint, get the same public-review ask, regardless of what they said on any private
survey? If yes, there's no gate. If the public-review ask is conditioned — explicitly or via a "route
happy customers to Google, unhappy customers to a private form" branching flow — on a sentiment
signal, that's gating.

**[KB-COMPLIANCE-016] (internal doctrine)** A common disguised form of gating is a two-step "Net Promoter Score" funnel
where a 9–10 score routes to the public review platform and a lower score routes to a private
"tell us more" form, marketed as "protecting the business from unfair reviews" or "making sure we
fix problems before they go public." This is exactly the prohibited mechanism — the private-feedback
routing option itself isn't illegal (routing complaints to support so they get resolved is good
service), but making the *public* ask conditional on the score is. **Reject example:** "If you had a
great experience, click here to leave us a Google review! If not, click here to tell us how we can
improve." — presented as the only two options, with the review link never surfaced to the low-score
branch. **Accept example:** ask every customer, at the same touchpoint, for a public review; *also*
and *separately* offer a private complaint/support channel that's always available regardless of what
they said, so an unhappy customer has somewhere to go without that option replacing their chance to
leave a public review.

---

## 3. What legitimate review solicitation looks like

**[KB-COMPLIANCE-017] (internal doctrine)** The compliant pattern, restated as an operational recipe:

1. Pick one lifecycle touchpoint (e.g., job completion + 3 days) and ask **every** customer who
   reaches it, no exceptions, for a public review — same channel (SMS/email), same wording, same
   timing.
2. Never precede the ask with a sentiment-gating question whose answer determines whether the ask
   happens.
3. If a private feedback/support channel exists, offer it as an *addition*, never a *replacement* —
   e.g., "We'd love your feedback — leave us a review here [link]. If anything about your experience
   wasn't right, please also reach out to us directly at [contact] so we can make it right" sent to
   everyone, not a branching flow.
4. Never make the review ask, or any post-review outreach, conditional on the star rating given.
5. Respond to negative reviews publicly and professionally (see `reputation/` in this KB for
   response-template doctrine) rather than trying to prevent them from existing.

**[KB-COMPLIANCE-018] (internal doctrine)** This recipe produces a review set that's an honest sample of the customer
base — which, done consistently, is also simply better long-term positioning: a business with 4.6
stars across 200 unfiltered reviews is more credible to a skeptical buyer than one with a suspicious
5.0 across 12 reviews, and it's the only version that carries zero regulatory exposure.

---

## 4. Cross-reference: gating vs. the adjacent violations

| Mechanism | Section | File |
|---|---|---|
| Selectively soliciting only likely-happy customers | § 465.7 (as codified gating) | This file |
| Hiding/removing negative reviews that already exist | § 465.7 (suppression) | [`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) §2 |
| Paying/incentivizing for a review, or for a specific rating | § 465.4 | [`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) §2 |
| Fabricating a review from a nonexistent or non-experiencing customer | § 465.2 | [`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) §2 |

Never treat these as interchangeable in a finding or a card to the operator — cite the specific
mechanism and section, because the fix for each is different (gating's fix is "ask everyone the same
way"; suppression's fix is "stop removing/hiding true negative reviews"; incentivizing's fix is
"remove the incentive entirely").

---

## 5. Contractor bend

This is, concretely, the single most tempting shortcut for a small owner-operated home-services business's review program,
because it doesn't feel like manipulation from the inside — it feels like "why would I ask someone
who just yelled at my crew lead to also leave us a public review, that's just asking for trouble."
The honest answer for this buyer: you're not required to ask them warmly or immediately, but you are
required to not *systematically exclude* unhappy customers from the same ask everyone else gets. In
practice, for this buyer, the simplest compliant pattern is: automate the review-request send (SMS or
email, same message, same timing, sent by the CRM/scheduling tool to every closed job) so there's no
human in the loop deciding who gets asked — removing the human judgment call removes the gating risk
by construction, and it's also less work for an owner who is already stretched thin. When drafting
this recipe for this buyer, lead with "set it and forget it, and it protects you legally" rather than
the CFR citation — this buyer will act on the practical framing, not the regulatory one.
