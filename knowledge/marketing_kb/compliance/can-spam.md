# CAN-SPAM Act — commercial email compliance

Company-agnostic doctrine. Governs every commercial email a GTM seat drafts, schedules, or sends —
nurture sequences, cold outreach, review-request emails, newsletters with any promotional content,
and transactional-looking emails whose primary purpose is actually promotional. See
[`privacy-and-consent.md`](privacy-and-consent.md) for the separate question of what consent is
needed to *collect and use* the email address in the first place (CAN-SPAM does not require opt-in
consent to send commercial email at all — it's an opt-out regime — but state privacy law and platform
policy may impose additional consent requirements on top of it).

---

## 1. Scope — what counts as "commercial" (and the B2B trap)

**[KB-COMPLIANCE-019]** CAN-SPAM applies to "any electronic mail message the primary purpose of which
is the commercial advertisement or promotion of a commercial product or service," including email
promoting content on a commercial website. It has **no B2B exception** — a cold outreach email to a
business contact promoting the sender's product/service is fully in scope, contrary to a common
misconception that only consumer email is regulated. (official, FTC CAN-SPAM Act Compliance Guide for
Business, retrieved 2026-09-27,
https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business)

**[KB-COMPLIANCE-020]** A message with mixed content (some transactional/relationship content, some
commercial content) is judged by its "primary purpose" — if the commercial content dominates or the
subject line would lead a recipient to believe it's primarily commercial, it's a commercial message
and the full rule set applies, even if it also contains an order confirmation or account notice.
**Reject example:** an "Your invoice is ready" subject line on an email that's actually 80% upsell
copy for a paid tier — this misrepresents the primary purpose in the subject line, which is its own
independent violation (§2.2 below) on top of whatever else applies.

---

## 2. The five required elements — every commercial email, every time

**[KB-COMPLIANCE-021]** (official, FTC CAN-SPAM Act Compliance Guide, retrieved 2026-09-27, same
source as [KB-COMPLIANCE-019]):

1. **Accurate header information.** The "From," "To," "Reply-To," and routing information —
   including the originating domain name and email address — must be accurate and identify the
   entity that initiated the message. Never spoof the From address or use a domain that obscures who
   actually sent it.
2. **Non-deceptive subject line.** The subject line must accurately reflect the message's content.
   Never use a subject line designed to look like a personal, transactional, or non-commercial
   message when the content is commercial.
3. **Clear identification as an advertisement.** Disclose clearly and conspicuously that the message
   is an advertisement. (In practice, most compliant senders satisfy this via the footer disclosure
   pattern combined with plainly promotional body content — the Rule does not require a literal "This
   is an advertisement" banner if the message's commercial nature is otherwise unambiguous, but when
   in doubt, state it.)
4. **A valid physical postal address.** Current street address, a USPS-registered P.O. box, or a
   private mailbox registered with a commercial mail-receiving agency. A registered agent's address
   or a virtual-office address that the sender can actually receive mail at is acceptable; a fake or
   unstaffed address is not.
5. **A clear and conspicuous opt-out mechanism.** An easy, working way for the recipient to opt out of
   future commercial email from the sender, described clearly in the message.

**[KB-COMPLIANCE-022]** Opt-out processing: the sender must honor an opt-out request within **10
business days**, must not charge a fee, require the recipient to provide any information beyond an
email address, or require more than a single step (e.g., replying "STOP" or clicking one link) to
opt out, and must not sell/transfer the opted-out address to anyone else after receiving the request
(except to a service provider engaged specifically to help comply with the opt-out). The opt-out
mechanism must keep working for at least 30 days after the message is sent. (official, same source.)

---

## 3. Penalties

**[KB-COMPLIANCE-023]** Each separate email sent in violation is subject to a civil penalty of up to
**$53,088** — this is the same inflation-adjusted FTC Act §5(m)(1)(A) ceiling cited in
[`ftc-endorsements-and-fake-reviews.md`](ftc-endorsements-and-fake-reviews.md) [KB-COMPLIANCE-004],
current as of the 2026 freeze at the January 2025 adjustment level (official/calculated, retrieved
2026-09-27, same two sources cited there). **"Each separate email" means the exposure scales with
send volume** — a single bad campaign sent to a large list is not one violation, it's one violation
per recipient, which is what makes a CAN-SPAM miss dramatically more expensive than most other
compliance misses in this corpus at any real sending scale. Aggravated violations (harvesting
addresses via dictionary attacks, unauthorized relay through someone else's server, using scripts to
register for multiple email accounts to send spam) can carry criminal penalties including
imprisonment. (official, same source.)

---

## 4. Working checklist before any commercial email sends

1. From/Reply-To/routing headers accurate and traceable to the real sender? 
2. Subject line matches the actual content — no disguised-as-personal or disguised-as-transactional
   subject line?
3. Is it clear, from the subject line or body, that this is promotional?
4. Does the footer include a real, current physical postal address?
5. Is there a one-step, no-fee, no-extra-information-required opt-out link, and is the un­subscribe
   pipeline actually wired to suppress future sends within 10 business days (not just cosmetically
   present)?
6. Is the send list itself clean of anyone who has already opted out? (A resurrected old list, an
   imported list, or a merged list from an acquisition/partnership is the most common way a stale
   opt-out silently gets ignored — verify against the current suppression list before every send, not
   just at signup time.)

---

## 5. Contractor bend

A small owner-operated home-services/trade business's own outbound email is usually small-scale (a nurture sequence to estimate leads, a
seasonal promo to past customers) — the real exposure risk for this buyer isn't malicious spam, it's
**a marketing tool or CRM template that ships without a working unsubscribe link, or a stale list
that gets re-emailed after people already opted out** (e.g., a list imported from a spreadsheet the
office manager kept, merged with the CRM's list, without deduplicating against opt-outs). Because the
penalty scales per-recipient, this is a case where a boring, well-configured ESP/CRM with automatic
one-click unsubscribe and suppression-list enforcement is dramatically safer than a hand-rolled send
— when this seat recommends an email tool or reviews an existing one for this buyer, verify the
unsubscribe mechanism actually suppresses the address for future sends (test it, don't just look at
the link), not just that a link is present in the template.
