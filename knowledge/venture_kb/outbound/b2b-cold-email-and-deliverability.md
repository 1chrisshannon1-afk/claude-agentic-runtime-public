# B2B Cold Email and Deliverability

**What this file answers:** how does a solo founder or a tiny team run a legally compliant B2B
cold-email campaign — sourcing the list, building the sending infrastructure, warming it up,
writing the sequence, and reading the signals that say "stop" — without a compliance team, a
deliverability specialist, or a big-company budget. It assumes the reader already knows CAN-SPAM's
five required elements and TCPA/A2P basics; those are not repeated here. Read
[`../../marketing_kb/compliance/can-spam.md`](../../marketing_kb/compliance/can-spam.md) and
[`../../marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md)
first — this file links to them rather than restating their content, and assumes the reader has
already internalized both. This file's own claim ids use the `[KB-VOUT-NNN]` prefix, numbered from
001, unique within the two `outbound/` files.

---

## 1. CAN-SPAM for B2B specifically — the trap and the checklist

**[KB-VOUT-001]** CAN-SPAM (16 CFR Part 316, the FTC's implementing rule for the CAN-SPAM Act, 15
U.S.C. §§ 7701–7713) has **no business-to-business exemption**. A cold email to a named person at a
company, promoting a product or service, is a commercial email and is fully in scope — see
[`can-spam.md`](../../marketing_kb/compliance/can-spam.md) [KB-COMPLIANCE-019]/[KB-COMPLIANCE-020]
for the "primary purpose" test that governs whether a given message counts as commercial at all.
This is the single most common misconception a first-time founder brings to B2B outreach: "it's not
spam, it's a sales email to a business" is not a legal distinction CAN-SPAM recognizes.

**[KB-VOUT-002]** The five required elements from
[`can-spam.md`](../../marketing_kb/compliance/can-spam.md) [KB-COMPLIANCE-021] apply to every cold
email exactly as written there (accurate headers, non-deceptive subject line, clear identification
as an ad where the commercial nature isn't otherwise obvious, a valid physical postal address, and a
working one-step opt-out). Nothing about B2B loosens any of the five. The opt-out processing rule
(10 business days to honor, no fee, no extra info required, mechanism live for 30+ days) is also
unchanged — see [KB-COMPLIANCE-022]. Yahoo's own bulk-sender best practices separately require
unsubscribe requests to be honored within **2 days** (§3 below), which is stricter than CAN-SPAM's
10-business-day legal floor. **The `bizdev-outbound-strategist` agent's own operating rule is
stricter still: honor opt-outs within ONE business day.** [KB-VOUT-002b] `(internal doctrine)` — this
is a department-level operating standard, tighter than either the CAN-SPAM legal floor or Yahoo's
2-day rule; when the two conflict, treat the 1-business-day figure as this corpus's actual practice
standard, and the 10-day/2-day figures as the outer legal/provider floors it is deliberately beating,
not as the operating target.

**[KB-VOUT-003]** The per-email penalty ceiling is **$53,088 per violation**, confirmed by direct
fetch of the FTC's own guide, which states: "Each separate email in violation of the CAN-SPAM Act is
subject to penalties of up to $53,088" (official, FTC CAN-SPAM Act Compliance Guide for Business,
retrieved 2026-09-28, https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business).
**Dating note, to avoid confusion:** the page itself carries two date markers that both predate the
January 2025 inflation-adjustment cycle this KB's compliance files otherwise cite — "August 2023" and
a note "Edited January 2024 to reflect Inflation-Adjusted Civil Penalty Maximums." Despite those
earlier dates, the live page still states the $53,088 figure as of this file's own 2026-09-28
retrieval, which is the January 2025-cycle amount; the page's "January 2024" edit note does not mean
the figure is stale or from an earlier adjustment cycle — it is simply the last time the page's own
copy was edited, and the number on it currently matches the more recent (January 2025) ceiling cited
elsewhere in this corpus. This is the same $53,088 figure and same FTC Act §5(m)(1)(A)
inflation-adjustment mechanism cited in [`can-spam.md`](../../marketing_kb/compliance/can-spam.md)
[KB-COMPLIANCE-023] — restated here with its own independent fetch confirmation rather than assumed.
The rule text itself (16 CFR Part 316)
sits on eCFR, which returned a redirect/blocked response to a direct automated fetch at retrieval
time; **UNVERIFIED (primary source unreachable: https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-316)**
for the regulation's own hosted text specifically — the FTC's own compliance-guide restatement above
is what is actually confirmed by direct fetch, and it cites 16 CFR Part 316 as its basis.

**[KB-VOUT-004]** "Per violation" means **per recipient email**, not per campaign — a single send to
a 2,000-name list with a broken unsubscribe link is up to 2,000 violations, not one. This is what
makes even a small, well-intentioned B2B campaign a real exposure event if the mechanics are wrong,
and it is why a founder sending a few hundred emails a week should still treat this as seriously as
a company sending millions (official, same FTC guide as above; restated from
[`can-spam.md`](../../marketing_kb/compliance/can-spam.md) [KB-COMPLIANCE-023]).

### 1.1 Aggravated violations — the line between "non-compliant" and "criminal"

**[KB-VOUT-005]** The FTC guide names specific "aggravated violations" that carry additional
penalties, including potential **criminal** penalties (up to imprisonment). The guide's own wording
(read directly, not paraphrased from an "Additional Rules Clarified" section — the guide does not
have a section by that name; this list appears in plain paragraph form within its penalties
discussion): accessing someone else's computer to send spam without permission; **using false
information to register for multiple email accounts or domain names** (the guide does not say
"automated creation of multiple email accounts" — the operative conduct is using FALSE INFORMATION
to register accounts/domains, not automation as such); relaying or retransmitting multiple spam
messages through a computer to mislead others about the message's origin; and **harvesting** email
addresses or generating them through a **dictionary attack** ("the practice of sending email to
addresses made up of random letters and numbers in the hope of reaching valid ones," in the guide's
own words — e.g. trying `john.smith@`, `jsmith@`, `j.smith@` at every domain in a target list without
confirming any of them are real). (official, FTC CAN-SPAM Act Compliance Guide for Business, retrieved
2026-09-28 via direct fetch, same URL as [KB-VOUT-003]).

**[KB-VOUT-006] (internal doctrine)** For a solo-founder list-building workflow, this means: never
use a scraper, bot, or automated crawler to pull email addresses off a website — even a public
"Team" or "Contact" page — without a human confirming each address individually, and never guess an
address pattern and blast variations at a domain to see which ones bounce. Both are exactly the
aggravated-violation conduct named in [KB-VOUT-005], not a gray area. The compliant alternative is
manual or semi-manual: a human (or an agent acting as a research assistant, never as a scraper)
visits a company's published "Contact," "Team," or "About" page and records the specific address
listed there for that specific purpose (e.g., a general inquiries address, or a named person's
published address), or uses a paid B2B data provider whose own terms of service represent that
addresses were collected with notice (see §1.3 below).

### 1.2 No-harvest notices

**[KB-VOUT-007]** A website's terms of service or a page footer sometimes carries an explicit
notice prohibiting automated collection of the addresses on that page (commonly phrased as
prohibiting "harvesting," "collection by automated means," or citing anti-spam terms). **[KB-VOUT-008]
(internal doctrine)** Treat any such notice as a hard stop for that domain, whether or not it is
phrased as a legal requirement: (a) it independently establishes that any address collection from
that page was not done with the site owner's consent, which forecloses the "we found it publicly
posted" defense a founder might otherwise lean on when asked how a contact was sourced, and (b) it
is a fast, cheap, and unambiguous signal that skipping the domain costs nothing and controversy over
it costs a great deal. If a no-harvest notice is spotted on a target page mid-list-build, the
correct action is to skip that specific domain/page — not to look for a workaround such as pulling
the same addresses via a search engine's cache or a third-party aggregator instead, which does not
cure the underlying non-consensual collection.

### 1.3 Bought B2B lists — what to check before using one

**[KB-VOUT-009] (internal doctrine)** A founder without time to hand-build a list will often
consider buying one from a B2B data vendor (a firmographic/contact database provider). Before using
any bought list for cold email, check:
1. **Does the vendor represent how the data was collected?** A reputable vendor's terms or data
   documentation should describe its collection method (opt-in forms, public business directories,
   licensed data-sharing agreements) — a vendor that cannot or will not say how it collected an
   address is a red flag that the underlying collection may itself have been a harvesting operation,
   which does not become compliant just because a third party resold it.
2. **Does the vendor's own terms of service permit cold outreach use of the data**, as opposed to
   limiting it to internal CRM enrichment or account-based marketing research only? Some data
   licenses restrict the purposes the data may be used for; using purchased data for a purpose the
   license doesn't cover is a contract problem even where it isn't a CAN-SPAM problem.
3. **Is the list scrubbed against known suppression/opt-out lists** (the vendor's own, plus the
   sender's own accumulated suppression list from prior campaigns) before the first send? A bought
   list is exactly the kind of "imported list" scenario
   [`can-spam.md`](../../marketing_kb/compliance/can-spam.md) §4/§5 flags as the most common way a
   stale opt-out gets silently re-emailed.
4. **How old is the list?** Contact data decays quickly (job changes, company changes); a list more
   than a few months old should be treated as needing re-verification (bounce/complaint monitoring
   tightened, see §5 below) rather than sent to at full confidence.
5. **Does the recipient list stay within the sender's actual addressable market?** A cheap, broad,
   loosely-targeted list produces a worse complaint rate (recipients who have never heard of the
   sender and see no relevance are far more likely to mark spam) which directly threatens
   deliverability (§5) even before any compliance question is reached.

None of these five checks were independently fetched from a specific named vendor's terms for this
file — they are internal doctrine derived from the collection/consent principles CAN-SPAM and this
corpus's compliance files already establish, applied to the bought-list use case
`UNVERIFIED — seeded, needs derivation` only in the narrow sense that no single vendor's terms were
cited; the underlying legal principles (harvesting, no-harvest notices, suppression-list
enforcement) are `(official)`-sourced above.

**Tension with Yahoo's own guidance, worth surfacing rather than smoothing over:** Yahoo's bulk
sender best-practices page states plainly, "Don't purchase mailing lists" (official, Yahoo bulk sender
best practices, retrieved 2026-09-28, https://senders.yahooinc.com/best-practices/) — a blanket
recommendation against bought lists at all, not a set of conditions under which a bought list becomes
acceptable. This file's own checklist above treats a bought list as usable if it passes the five
checks; that is this KB's own risk-management position, not one Yahoo endorses. A founder sending to
Yahoo/AOL/Verizon-family addresses in particular should weigh Yahoo's flatter "don't do this" guidance
against this file's conditional approach, and lean toward Yahoo's stricter position for volume sent to
those domains specifically.

---

## 2. Sending infrastructure — domains, authentication, and why they matter together

**[KB-VOUT-010] (internal doctrine)** A cold-email program should never send from the company's
primary/root domain (the one used for the website, main inbox, and any transactional mail like
password resets or invoices). Use one or more **separate sending domains** so
that a deliverability problem — a spike in spam complaints, a blocklist hit, a warm-up mistake —
degrades the reputation of a disposable domain rather than the domain the company's real customers
and transactional mail depend on. This is standard cold-email industry practice, though no single
official regulator or platform page mandates it by name; it is grounded in the mechanics of how
mailbox providers compute sender reputation per-domain (§2.1–2.3 below are the `(official)`-sourced
mechanics this recommendation follows from). **Important qualification confirmed directly against
Google's own bulk-sender FAQ (§3):** Google counts the 5,000-message threshold against a sender's
**primary domain, subdomains included** — so a sending domain that is a SUBDOMAIN of the company's
primary domain (e.g. `outreach.example.com` under a primary domain of `example.com`) is counted
together with the root domain's own volume, not separately. Only a sending domain that is a genuinely
**separate primary domain** (e.g. `try-example.com` or `example-outreach.com`, not
`*.example.com`) is counted on its own for Google's bulk-sender purposes — this is the specific
reason to use a separate primary domain, not merely "a separate domain" loosely defined, and it is
also why choosing a subdomain of the main site for cold outreach does not actually isolate deliverability
risk from the main domain's own volume the way a genuinely separate domain does.

**[KB-VOUT-011]** Each sending domain needs its own SPF and DKIM records, and the root/parent domain
needs a DMARC policy that the sending domain aligns with (or its own separate DMARC policy).
**SPF** (Sender Policy Framework) publishes which mail servers are authorized to send for a domain.
**DKIM** (DomainKeys Identified Mail) cryptographically signs outgoing mail so the receiving server
can verify it wasn't altered in transit and genuinely came from an authorized sender. **DMARC**
(Domain-based Message Authentication, Reporting and Conformance) tells receiving mail servers what
to do when a message fails SPF/DKIM alignment (e.g. quarantine or reject it) and can request
reporting on failures. All three together are what both Google and Yahoo require of bulk senders
(§3 below) (official, Google's and Yahoo's own bulk-sender documentation, both retrieved 2026-09-28,
cited fully in §3).

**[KB-VOUT-012] (internal doctrine)** For a brand-new sending domain, publish SPF, DKIM, and at
least a monitoring-only DMARC policy (`p=none`) before the first send, not after — Google's own
guidance explicitly allows `p=none` as an acceptable DMARC enforcement level for bulk-sender
compliance (§3.1), so a founder does not need to commit to strict quarantine/reject enforcement on
day one, but the record must exist and pass. Sending with no DMARC record at all, or with SPF/DKIM
misconfigured so they fail, is one of the fastest ways a brand-new domain gets flagged before it
ever has a chance to build reputation.

---

## 3. Google and Yahoo bulk-sender requirements

**[KB-VOUT-013]** Google requires senders of **5,000 or more messages per day to Gmail addresses**
to: set up SPF and DKIM authentication for the sending domain, set up a DMARC policy for the domain
(enforcement may be set to `p=none`, i.e. monitoring-only, and still satisfy the requirement), keep
spam rates reported in Google Postmaster Tools **below 0.30%**, and support one-click unsubscribe
(with a visible unsubscribe link in the message body) for marketing and subscribed/bulk messages
(official, Google's bulk sender guidelines and its bulk-sender FAQ, retrieved 2026-09-28,
https://support.google.com/mail/answer/81126 and https://support.google.com/a/answer/14229414).
Google's own guidance recommends aiming for **below 0.10%** spam rate as a safety margin against
occasional spikes, rather than treating 0.30% as a comfortable target to run at continuously
(official, same source). **This 0.1%/0.3% spam-rate guidance is not itself limited to formally
bulk-classified senders** — Google's FAQ states plainly that "senders should keep their spam rate
below 0.1% and should prevent spam rates from ever reaching 0.3% or higher," and separately notes
that "user-reported spam rates greater than 0.1% have a negative impact on email inbox delivery" even
apart from the bulk-sender mitigation mechanic, which is itself keyed to the bulk-sender status
described in [KB-VOUT-013b].

**[KB-VOUT-013b]** **The 5,000-message count is by PRIMARY DOMAIN, subdomains included — not by
individual sending domain, and not a per-campaign count.** Google's bulk-sender FAQ states this
directly: "When we calculate the 5,000-message limit, we count all messages sent from the same
primary domain," and gives the worked example of a sender who sends 2,500 messages/day from
`example.com` and 2,500/day from `promotions.example.com` — the FAQ states this sender "is
considered a bulk sender because all 5,000 messages were sent from the same primary domain." A
sending domain that is a subdomain of the company's primary domain does NOT get its own separate
5,000-message allowance; only a genuinely separate primary/root domain does. **Bulk-sender status is
also permanent, not something a sender can later undo:** Google's FAQ states "senders who meet the
above criteria at least once are permanently considered bulk senders" and that bulk sender status
"doesn't have an expiration date" — changing sending practices afterward does not remove it.
**(official, Google's bulk-sender FAQ, retrieved 2026-09-28,
https://support.google.com/a/answer/14229414)** [KB-VOUT-013b]

**[KB-VOUT-014]** Yahoo's parallel bulk-sender requirements: implement both SPF and DKIM, publish a
DMARC policy of at least `p=none` that actually passes (domain alignment between the From-header
domain and the SPF or DKIM domain, relaxed alignment acceptable), keep the spam complaint rate
**below 0.3%** (measured against mail that reached the inbox, not total mail sent), and support
one-click unsubscribe — Yahoo's own documentation states its List-Unsubscribe-Post/RFC 8058
one-click method is "highly recommended" while a `mailto:`-based List-Unsubscribe header is
"acceptable" as a fallback, and unsubscribe requests must be honored within **2 days** (official,
Yahoo's bulk sender best-practices documentation, retrieved 2026-09-28,
https://senders.yahooinc.com/best-practices/).

**[KB-VOUT-015]** The 5,000-message/day Google threshold applies **per primary domain (subdomains
included), not per campaign, and not summed loosely across unrelated domains** (see [KB-VOUT-013b]) —
a founder sending 500/day from each of ten sending SUBDOMAINS of the same primary domain is still a
bulk sender under Google's rule once the combined volume across those subdomains crosses the
threshold, because they share one primary domain; a founder sending 500/day from each of ten
genuinely separate primary domains is not, under this rule alone, since each primary domain is
counted on its own. **A founder sending well under the threshold is not exempt from good practice** —
the spam-rate and one-click-unsubscribe requirements are the mechanics that keep any sender's mail
landing in the inbox rather than spam regardless of whether the formal "bulk sender" threshold is
crossed, and both mailbox providers' spam-filtering systems respond to the same signals (complaint
rate, authentication, engagement) below the formal threshold too — the threshold changes which
requirements are contractually/technically enforced, not which signals the spam filter actually uses.
`(internal doctrine)`, applying the mechanics in [KB-VOUT-013]/[KB-VOUT-013b]/[KB-VOUT-014] to the
sub-threshold sender's practical incentives.

### 3.1 One-click unsubscribe and RFC 8058

**[KB-VOUT-016]** RFC 8058 defines the "One-Click" method for email unsubscription: the sending
message includes a `List-Unsubscribe` header and a `List-Unsubscribe-Post` header with the
literal value `List-Unsubscribe=One-Click`; a compliant receiving mail client can then send a single
HTTP POST to the URL with no further user interaction (no landing page, no login, no second
confirmation click) to unsubscribe the recipient. Both Google and Yahoo's documentation cite RFC
8058 by name as the specification bulk senders should implement to satisfy the one-click
requirement (official, Google's bulk sender guidelines and Yahoo's bulk sender best practices, both
retrieved 2026-09-28, URLs as in [KB-VOUT-013]/[KB-VOUT-014]).

**The RFC's own text was read directly for this pass (rfc-editor.org/rfc/rfc8058.txt) and confirms
two MUSTs beyond the header names above:** (1) the `List-Unsubscribe` header **MUST contain one HTTPS
URI** (it may also contain a `mailto:` URI as a fallback, but the one-click mechanism itself requires
HTTPS — an HTTP-only or non-HTTPS URI does not satisfy one-click); and (2) the message **MUST have a
valid DKIM signature that covers at least the `List-Unsubscribe` and `List-Unsubscribe-Post` headers**
themselves (included in the DKIM signature's `h=` tag) — a message with no such DKIM coverage of
these headers is not eligible for one-click treatment, and the RFC states the receiving mail client
"SHOULD NOT offer a one-click unsubscribe" for a message that lacks it. The RFC also specifies that
the mail sender MUST NOT return an HTTPS redirect from the unsubscribe endpoint (redirected POSTs
have historically been unreliable) and that the POST request MUST NOT carry cookies or other
web-session context. **(official, RFC 8058, retrieved 2026-09-28 via direct fetch of
https://www.rfc-editor.org/rfc/rfc8058.txt)** [KB-VOUT-016b]

**[KB-VOUT-017] (internal doctrine)** For a solo founder, the practical takeaway is: use an email
sending platform/ESP that implements RFC 8058 one-click unsubscribe automatically (most mainstream
cold-email and marketing platforms do) rather than hand-rolling unsubscribe headers. A visible
unsubscribe *link in the email body* is required by both CAN-SPAM (a working link, no login/fee)
and by Google/Yahoo's bulk-sender rules — but the body link and the RFC 8058 header mechanism are
**two different things that both need to work**: the header is what lets Gmail/Yahoo's own native
"Unsubscribe" button (shown next to the sender name in the inbox) function without the recipient
ever opening the email, while the body link is what a recipient who does open the email clicks. A
platform that implements only one of the two has not fully satisfied either regulator's/provider's
requirement in practice, even if it technically satisfies CAN-SPAM's narrower "a working link
exists" bar.

---

## 4. Warm-up and per-mailbox sending volume

**[KB-VOUT-018] (internal doctrine)** A brand-new sending domain or mailbox has no sending
reputation with mailbox providers, and sending at full target volume from day one is one of the
most common ways a cold-email program gets flagged or blocklisted before it produces a single
reply. The standard practice this corpus recommends: start a new domain/mailbox at a low daily
volume (commonly cited in industry practice as starting in the **10–20 emails/day** range) and
increase gradually over **2–4 weeks** as engagement signals (opens, replies, low bounce/complaint
rates) stay healthy, rather than jumping to hundreds or thousands of sends per day immediately.
`UNVERIFIED — seeded, needs derivation`: the specific 10–20/day starting figure and 2–4 week ramp
window are common industry-practice numbers repeated across cold-email tooling vendors' own
documentation, not independently verified against a single authoritative source for this file — the
*mechanism* (gradual, engagement-gated volume increase on a new domain) is the load-bearing
doctrine; the exact numbers are a reasonable starting point to adjust from actual bounce/complaint
data (§5), not a rule to follow blindly.

**[KB-VOUT-019] (internal doctrine)** Per-mailbox daily send caps exist independently of domain
warm-up: even a well-warmed domain sending from a single mailbox at very high volume (many hundreds
per day from one address) reads as anomalous to mailbox-provider spam filters regardless of content
quality. Spreading volume across multiple mailboxes on the warmed sending domain(s), each sending a
moderate daily volume, is the standard mitigation — this is a deliverability mechanism, not a
compliance requirement, and does not change any CAN-SPAM obligation (every mailbox sending
commercial email still needs the same five elements and the same suppression-list discipline).

---

## 5. Bounce and complaint thresholds — stop rules

**[KB-VOUT-020] (internal doctrine)** A founder running cold email without a deliverability
specialist needs mechanical stop rules, because by the time a human notices "replies have dried
up," the domain reputation damage is often already done. Treat the following as hard pause
triggers, checked at least daily during an active campaign:
1. **Hard bounce rate above ~2-3%** on a single send — indicates a stale or poorly-verified list;
   pause the campaign, re-verify the remaining list (an email-verification tool, not a resend-and-see
   approach), and remove every hard-bounced address permanently before resuming.
2. **Spam complaint rate approaching the regulator/provider ceiling** in [KB-VOUT-013]/[KB-VOUT-014]
   (0.3% is the hard ceiling both Google and Yahoo cite — and Google's own guidance applies this
   0.1%/0.3% spam-rate guidance to senders generally, not only to formally-classified bulk senders, so
   this applies below the 5,000/day threshold too; treat 0.1%–0.15% as the founder's own
   internal amber-alert line, well below the ceiling, since a small sender's volume means a handful
   of complaints moves the percentage fast) — pause immediately, review recent send content and
   targeting for a relevance mismatch, and do not resume at the same volume until complaints trend
   back down over multiple sends.
3. **Any spam-trap hit** (a flagged, non-real address that exists specifically to detect
   poorly-sourced lists) — treat as a signal the list itself is compromised (likely an old, bought,
   or scraped list with stale/fabricated addresses mixed in), not a one-off mistake; stop sending
   from that list entirely and re-source.
These thresholds are `(internal doctrine)` synthesizing the regulator/provider ceilings named above
with standard deliverability practice; they are conservative on purpose because a solo founder has
no deliverability team to catch a slow-building reputation problem before it becomes a blocklisting
event.

---

## 6. Sequence design — steps, spacing, reply handling

**[KB-VOUT-021] (internal doctrine)** A B2B cold-email sequence for a solo founder or tiny team
should be short and clearly targeted rather than long and generic — quality of targeting and
relevance to the specific recipient matters more to both compliance risk (complaint rate) and
actual reply rate than sequence length. A workable default shape:
1. **Email 1 (Day 0):** a short, specific, personalized opener — names something true and specific
   about the recipient's company, states the value proposition in one or two sentences, ends with a
   low-friction ask (a question, not a meeting request).
2. **Email 2 (Day 3–4):** a brief, non-repetitive follow-up — adds a new piece of information
   (a relevant case, a specific detail) rather than just restating email 1; never opens with
   "just following up" with no new content.
3. **Email 3 (Day 7–9):** a different angle — a different value proposition facet, a short case
   example, or a direct, polite "should I close the loop on this?" that signals this is the last
   scheduled touch.
4. **Stop.** For a tiny operation without dedicated sales capacity, 3 touches is a defensible
   default; a 4th–5th touch adds diminishing reply value while continuing to accrue complaint-rate
   risk on non-responders. If a longer sequence is used, taper spacing further out (10+ days between
   later touches) rather than maintaining a tight cadence.
- **Reply handling:** any reply — including a "not interested," an out-of-office, or a bounce —
  should immediately pull that address out of the active sequence. Continuing an automated sequence
  to someone who has replied (even negatively) is both a poor practice and a step toward the kind of
  irrelevant, unwanted mail that drives complaint rates up.
- **Unsubscribe/opt-out requests** pulled from replies (a reply saying "remove me," "stop," "not
  interested") must be honored with the same discipline as a formal unsubscribe-link click — add to
  the suppression list immediately, not only when the recipient uses the literal unsubscribe
  mechanism. `(internal doctrine)`, but grounded in the "any reasonable means" revocation principle
  the TCPA file documents for calls/texts
  ([`tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md) [KB-COMPLIANCE-027]) —
  CAN-SPAM does not require honoring a *reply-based* opt-out the same way TCPA requires honoring any
  reasonable revocation, but treating a plain-English "stop" the same way regardless of channel is
  the safer and more relationship-preserving default for a founder-led operation where every
  recipient is a potential future customer, partner, or reference regardless of today's answer.

**[KB-VOUT-022] (internal doctrine)** Never chain an email sequence directly into an automated SMS
or call step without separately obtained, channel-specific consent for that channel — see
[`tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md) [KB-COMPLIANCE-025] on why
email consent (or the absence of any TCPA consent requirement for cold email in the first place)
never carries over to authorize a text or autodialed/prerecorded call. A cold-email platform that
offers a "multi-channel sequence" feature blending email and SMS/calls automatically is not, by
itself, compliant just because the platform supports it — the underlying consent question is
unchanged by what the tool makes easy to click.

---

## 7. Measuring replies and meetings

**[KB-VOUT-023] (internal doctrine)** For a solo founder without a sales-ops stack, track at
minimum, per campaign/list segment:
- **Send volume**, **bounce rate**, **complaint rate** (the deliverability health signals from §5).
- **Reply rate** (any reply, positive or negative) as the primary engagement signal — a healthy
  reply rate is evidence the targeting and message are landing even before any meeting is booked.
- **Positive-reply rate** (replies indicating genuine interest) separately from total reply rate —
  a sequence can have a high total reply rate driven mostly by "not interested" or out-of-office
  replies, which is a different signal than genuine interest and should not be conflated with it in
  a founder's own read of "is this working."
- **Meetings booked** as the down-funnel conversion metric, and **meetings held** separately (a
  booked-but-no-show meeting is not the same outcome and conflating the two overstates a sequence's
  real effectiveness).
No industry-benchmark reply/meeting rate is cited here as a target `UNVERIFIED — seeded, needs
derivation` — B2B cold-email reply and meeting-booking rates vary enormously by list quality,
targeting specificity, offer, and industry, and this corpus was not able to independently verify a
single portable benchmark figure worth citing as a target for a first-time founder's campaign. Track
the founder's own trend over successive sends/lists rather than importing an external "good" number.

---

## 8. Non-US recipients — flag only

**[KB-VOUT-024]** Cold email to recipients outside the US is governed by different regimes than
CAN-SPAM, each materially stricter on consent: **CASL** (Canada's Anti-Spam Legislation) generally
requires **prior opt-in consent** before commercial electronic messages, a marked departure from
CAN-SPAM's opt-out model; **UK PECR** (Privacy and Electronic Communications Regulations, sitting
alongside UK GDPR) similarly restricts unsolicited commercial email absent an existing customer
relationship or consent; and the **EU** (under the ePrivacy Directive as implemented in each member
state, plus GDPR's lawful-basis requirements for processing the email address at all) is
generally opt-in for B2C and often requires a lawful basis and member-state-specific rules even for
B2B. `UNVERIFIED — seeded, needs derivation; flag only per this file's brief` — none of CASL, UK
PECR, or EU ePrivacy/GDPR mechanics were independently fetched and verified for this file. **Doctrine
until independently researched: do not cold-email a non-US recipient on a CAN-SPAM-only compliance
basis.** If a target list includes non-US domains/companies, either exclude them from the cold-email
motion entirely or route the question to counsel/a dedicated research pass on the specific
country's regime before sending — this is flagged, not resolved, here.

---

## Decision rules

1. **Is this a commercial email to a business contact?** → CAN-SPAM's five elements apply in full,
   no B2B exception (§1).
2. **Is the list being built by any automated/scraping method, or from a page with a no-harvest
   notice?** → Stop. Manual/semi-manual collection or a vetted paid vendor only (§1.1–§1.3).
3. **Is this domain new or low-volume historically?** → Warm up gradually before scaling volume
   (§4); do not send at target volume on day one.
4. **Are SPF, DKIM, and at least a monitoring DMARC policy published on the sending domain?** → If
   no, do not send yet — fix this first (§2).
5. **Does any one primary domain (subdomains included) send 5,000 or more messages a day to Gmail
   addresses — bulk status is permanent once reached — or any meaningful volume to Yahoo?** → Treat Google's and Yahoo's full bulk-sender requirements as
   binding, not aspirational (§3), regardless of whether the sender self-identifies as "bulk."
6. **Has the spam complaint rate crossed the amber-alert line (§5) or a bounce-rate spike occurred?**
   → Pause immediately; do not "wait and see for a few more sends."
7. **Did a recipient reply with any negative/stop signal, in any channel or wording?** → Suppress
   immediately; never require the exact "unsubscribe" mechanism to honor an obvious opt-out (§6).
8. **Does the target list include any non-US company/domain?** → Flag for CASL/UK-PECR/EU-specific
   review before sending to those recipients; do not extend US CAN-SPAM compliance as if it covers
   them (§8).
9. **Is the next planned step in the sequence an automated call or text to the same list?** → Stop;
   separately verify channel-specific TCPA consent exists before adding SMS/calls to any
   email-sourced list (§6, linking to the TCPA file).

## Anti-patterns

- Scraping email addresses off a website (even a public "Team" page) with a bot or crawler, or
  guessing address patterns and blasting variations to see what bounces — both are named aggravated
  violations, not gray-area growth hacking (§1.1).
- Sending cold email from the same domain used for the company's main website/transactional email,
  with no separate sending domain to absorb deliverability risk (§2).
- Publishing no DMARC record at all, or letting SPF/DKIM fail silently, because "it's just a small
  campaign" — Google and Yahoo's spam filters respond to authentication signals regardless of
  formal bulk-sender-threshold status (§3, §3.1).
- Treating a body-only unsubscribe link as sufficient without also implementing RFC 8058's
  `List-Unsubscribe`/`List-Unsubscribe-Post` headers — the two serve different recipient behaviors
  and a platform must support both (§3.1).
- Ignoring a bounce-rate or complaint-rate spike because replies are still trickling in — by the
  time a human notices reply volume has dropped, domain reputation damage is often already
  underway; mechanical stop rules exist precisely because this signal lags (§5).
- Continuing an automated sequence to someone who has already replied "not interested," even though
  they didn't click the formal unsubscribe link (§6).
- Chaining an email sequence directly into automated SMS/calls without separately obtained,
  channel-specific TCPA consent (§6, §8's parallel non-US flag).
- Buying a B2B list from a vendor that won't say how the data was collected, or using a bought list
  without scrubbing it against the sender's own accumulated suppression list first (§1.3).
- Treating CAN-SPAM compliance as sufficient cover for cold-emailing non-US recipients (§8).

## Sources

- FTC, "CAN-SPAM Act: A Compliance Guide for Business," retrieved 2026-09-28, official,
  https://www.ftc.gov/business-guidance/resources/can-spam-act-compliance-guide-business
- eCFR, 16 CFR Part 316 (CAN-SPAM Rule), attempted retrieval 2026-09-28 — redirected/blocked to
  automated fetch; UNVERIFIED (primary source unreachable:
  https://www.ecfr.gov/current/title-16/chapter-I/subchapter-C/part-316)
- Google, bulk sender guidelines, retrieved 2026-09-28, official,
  https://support.google.com/mail/answer/81126
- Google, bulk sender FAQ, retrieved 2026-09-28, official,
  https://support.google.com/a/answer/14229414
- Yahoo, bulk sender best practices, retrieved 2026-09-28, official,
  https://senders.yahooinc.com/best-practices/
- RFC 8058 (One-Click List-Unsubscribe), retrieved 2026-09-28, official, read directly,
  https://www.rfc-editor.org/rfc/rfc8058.txt
- [`../../marketing_kb/compliance/can-spam.md`](../../marketing_kb/compliance/can-spam.md) —
  linked, not repeated, for the five required elements and penalty structure.
- [`../../marketing_kb/compliance/tcpa-a2p-10dlc.md`](../../marketing_kb/compliance/tcpa-a2p-10dlc.md)
  — linked, not repeated, for consent-revocation and channel-separateness doctrine referenced in
  §6/§8.
