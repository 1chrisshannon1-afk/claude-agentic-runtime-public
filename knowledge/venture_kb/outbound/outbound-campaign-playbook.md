# Outbound Campaign Playbook — launch method, levers, list layering, replies

**What this file answers:** how does a solo founder or tiny team go from "we think outbound could work" to a
live, measurable, compliant B2B campaign in days, and what does a practitioner who runs many campaigns
do differently from a first-timer — the order of work, the five things worth competing on, how to segment
and write per-segment, how to layer a list, how to route contacts by the data held, how to handle
replies, and how to combine content with outreach. It is the *method* counterpart to
[`b2b-cold-email-and-deliverability.md`](b2b-cold-email-and-deliverability.md) (the legal and
infrastructure rules) and [`founder-led-relationships.md`](founder-led-relationships.md) (the by-hand
channel). This file's claim ids continue the `[KB-VOUT-NNN]` numbering from 044.

**Source and evidence grade.** The method below is distilled from one long-form practitioner interview
(published 2026-10-09; transcript on file; retrieved 2026-10-11) by someone who runs outbound for many
clients, from inside a tool-vendor ecosystem. It is a single, self-reported source. What the source
asserts about effectiveness is tagged `UNVERIFIED — seeded, needs derivation` and every figure from it
must never be quoted as a benchmark; rules this corpus adopts are tagged `(internal doctrine)`. Verify a
lever against the company's own results before treating it as a rule for that company. The general
(non-venture) version of sections 2, 3 and 5 is
[`../../marketing_kb/sales/outreach-levers-and-drafting.md`](../../marketing_kb/sales/outreach-levers-and-drafting.md)
and of section 6 is [`../../marketing_kb/sales/reply-handling.md`](../../marketing_kb/sales/reply-handling.md);
this file links to them and adds only the venture-specific parts.

Compliance is not restated here. Every tactic in sections 1-6 operates inside
[`b2b-cold-email-and-deliverability.md`](b2b-cold-email-and-deliverability.md), the CAN-SPAM and TCPA
files it cites, and the venture-wide lines in the `bizdev-outbound-strategist` primer. Section 7 lists
the tactics from the same source that this corpus **rejects**, and the rule each one hits.

---

## 1. Test the idea before buying tools

**[KB-VOUT-044] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** The most common
failure is spending on tools and subscriptions and never testing whether outbound works for the
offer. Run the smallest stack that can get a campaign live: a source of target companies, a source of
contacts at them, one sequencer, one sending setup. Add a tool only when a specific step of a live
campaign is blocked without it.

**[KB-VOUT-045] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** Launch an imperfect
campaign now rather than perfecting for days: market feedback (replies, objections, bounce and
complaint data) is worth more than another draft, and the campaign improves by iteration. This does
not waive any compliance gate in the bizdev primer: a template still needs `venture-director`
approval and a `gtm-checker` pass before it is used.

**[KB-VOUT-067] (internal doctrine)** Compare a data tool's pricing model, not only its features, before
subscribing. Pay-per-credit suits a first test; a flat or "unlimited" plan can cost less once use is
steady and high, but only after the test shows the campaign works ([KB-VOUT-044]) and after reading its
fair-use and permitted-use terms, since "unlimited" may be capped or limited to internal use, and
[KB-VOUT-009] still applies to the data. Prefer monthly terms until there are results. A connector an
assistant can read through is a convenience, not a reason to buy, and the operator keeps every credential
that can send or book ([KB-VOUT-058]). The seat prepares the comparison; any subscription is spend that
goes to the operator. `UNVERIFIED — seeded, needs derivation` The source says per-credit databases cost more over time than the
unlimited plan it recommends and that a tool built to run from an assistant is a plus; it gives no usage
figures.

**[KB-VOUT-068] (internal doctrine)** Launching fast does not mean sending big. The first send goes to a
small approved segment (`../../marketing_kb/sales/outreach-levers-and-drafting.md` §4); volume then rises
only inside the warm-up, per-mailbox and stop rules ([KB-VOUT-018], [KB-VOUT-019], [KB-VOUT-020]), and only
once the first segment's replies show the lead lever works. Volume is never added to cover a weak offer or
list. `UNVERIFIED — seeded, needs derivation` The source says the founder who launches today and scales volume hard beats the one who
spends ten days perfecting; this corpus adopts the launch-now half only.

## 2. The five levers (what is worth competing on)

**[KB-VOUT-046] (internal doctrine)** The five levers are the offer (including a guarantee), a unique
mechanism, a free value hook, segmentation and social proof; the definitions and the checks that must pass
before each is claimed are in `../../marketing_kb/sales/outreach-levers-and-drafting.md` §1. For every
campaign plan, state the lead lever at the top before writing a word of copy.

**[KB-VOUT-047] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)**
Test the levers against each other before testing surface details (subject-line wording, CTA phrasing,
signature layout), which the source says make no difference at all (this corpus does not adopt the
absolute form). This is a priority order, not a ban: `../../marketing_kb/conversion/ab-testing-discipline.md`
governs how any test is run. That two or three levers (offer and free value hook) carry most of the effect
was an opinion voiced in the interview and agreed to by the guest, not a measurement; it is unverified.

**[KB-VOUT-048] (internal doctrine)** A guarantee, a free offer or a named-customer proof line is a claim.
It goes through the `gtm-checker` claims checklist and the compliance corpus before use. A guarantee the
company cannot honor, or social proof it cannot document, is a defect even if it would lift replies.
`UNVERIFIED — seeded, needs derivation` The source's 5X figure is a hypothetical (a guarantee is worth it
if it gives a 5X lift in reply rate), not a reported result.

## 3. Segment by one variable, write to that segment's pain

**[KB-VOUT-049] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** Pick one segmenting
variable that changes what the buyer cares about (for example the channel an agency sells, the
equipment a business owns, the size band). Classify every company in the list on that variable, then
write each segment its own angle. The test of a good segment email: it could not be sent unchanged to
a different segment.

**[KB-VOUT-050] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** The human supplies the
pain points; an AI assistant does not know the customer better than the founder does. Workflow:
founder writes (or dictates) each segment's pain, the assistant drafts, the founder edits. An
AI step is a good classifier for the segmenting step (the source reports its data vendor's feature
classified a demo list for about 11 cents, list size not given, `UNVERIFIED — seeded, needs derivation`)
and an assistant is a good drafter, never the source of the insight.

**[KB-VOUT-051] (internal doctrine)** When the assistant's first pass shows that a segment does not fit
the offer (the source's example: a sub-group that sells a different service), that is a result, not
noise: drop the sub-group or write it a separate angle. Do not paper over it with generic copy.

## 4. Layer the list, then route each contact by the data held

**[KB-VOUT-052] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** Build the list in
layers: (a) start from a seed company the target resembles and pull look-alike companies; (b) have an
assistant validate each company against the target definition by reading its **public website**, and
drop false matches (the source's example: software vendors whose pages share keywords with the target
service businesses); (c) find people at each remaining company; (d) filter titles to the real buyer
for that company size (for example founder, owner or managing director under about 50 employees) and
strip functions that would never buy (HR, finance, legal, IT, engineering). Then ask the assistant to
list the other titles that hold the same buying role at that company size (clients often know only one),
and have the founder approve that title list before the filter runs. Each step is list hygiene that costs far
less than sending to the wrong person.

**[KB-VOUT-053] (internal doctrine)** Only public pages and published or bought-list business
addresses feed step (b)-(d). Honor no-harvest notices and the address rules in
`b2b-cold-email-and-deliverability.md`; do not log in to a site, and do not collect a person's data
from a source whose terms forbid it.

**[KB-VOUT-054] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** The source
routes each contact by the data held: a valid email to the email campaign, a public email only to a
separate campaign, no email but a profile to a network sequence. **(internal doctrine)** This corpus keeps
a public or role address in its own campaign with its own stop rules, and turns the third route into a
**hand-sent** profile message drafted for the operator (see
[`founder-led-relationships.md`](founder-led-relationships.md) §4), never an automated sequence. A public
address counts only if a person, or an agent acting as a research assistant (never as a scraper),
recorded it from the company's own published page, or the data vendor passes the [KB-VOUT-009] checks
([KB-VOUT-006]).

## 5. Draft with an assistant, edit as a human

**[KB-VOUT-055] (internal doctrine)** Draft with an assistant and edit as a human: about four variants of
email one, stitch the best opener, body and call to action, have the assistant fix the joins, then a human
pass to cut generic phrasing (method and the source's unverified 80% claim:
`../../marketing_kb/sales/outreach-levers-and-drafting.md` §3).

**[KB-VOUT-056] (internal doctrine)** Keep a swipe file of strong copy and learn its cadence, not its words;
reuse structure, never text.

**[KB-VOUT-057] (internal doctrine)** The drafter never checks its own draft: `bizdev-outbound-strategist`
drafts, `venture-director` approves, `gtm-checker` (dispatched by venture-director) checks the claims,
identity and compliance lanes. Every edit after the check is a new draft that is checked again.

**[KB-VOUT-058] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** The source
has the assistant write the campaign's settings and copy into the sequencer through a connector and leaves
only the list upload by hand, because most sequencers lack a bulk-upload API; its settings are weekdays only,
9 to 5 Central, open tracking off, and a clear campaign naming scheme. **(internal doctrine)** Write the
settings down once as a checklist the operator applies, with sending inside the recipients' business hours
in their own time zone and stop on reply added, and name each campaign by lever, segment and date in the
lowercase underscore form of `../../marketing_kb/measurement/utm-standard.md` [KB-MEAS-034] so results map
back to the lever tested. The operator, not an agent, holds the sequencer account and uploads the list; an
agent has no sending access under the venture-wide lines.

## 6. Replies, speed and content

**[KB-VOUT-059] (internal doctrine)** Set the operator's reply target before launch from the campaign's own
measured reply times, and have drafts ready for the common answers (method, evening-reply claim and
anti-patterns: `../../marketing_kb/sales/reply-handling.md`; response-time research:
[`speed-to-lead.md`](../../marketing_kb/sales/speed-to-lead.md)).

**[KB-VOUT-060] (internal doctrine)** Build the reply knowledge base once, before launch (contents:
`../../marketing_kb/sales/reply-handling.md` §2). `bizdev-outbound-strategist` drafts replies from it
**for the operator to send**, except where the company's deal folder records a standing approval for
automatic replies ([KB-VOUT-065]). The seat itself never sends, replies or books.

**[KB-VOUT-061] UNVERIFIED — seeded, needs derivation (single vendor-affiliated practitioner interview)** Content that the target
reader already knows amplifies outreach: a recipient who has seen the sender's posts is more likely to
reply and to look the sender up. A **by-hand** version is in scope: the operator reads who engaged with
his own post, checks they fit the target, and writes a personal connection note. The source's other
tactics here (scraping the engagers of any creator, paid or competitor, and automated sequencing) are
rejected in section 7. Never name-drop another creator in an outreach message.

**[KB-VOUT-069] (internal doctrine)** Before a campaign goes out, the operator searches his own name and
the company the way a recipient would and reports what turns up, and the checker compares that report
with the message:
the profile's name, title and photo, the website, and a recent post or page that fits the claims in the
email. An interested recipient often looks the sender up, and a mismatch or an empty result costs the
reply. Fix a gap by correcting the profile or page for real, never by adding proof that is not true.
`UNVERIFIED — seeded, needs derivation` The host of the source interview says recipients will probably research the sender; no
figure is given.

**[KB-VOUT-070] (internal doctrine)** A paid post by an industry creator is an endorsement: the payment is
a material connection the post itself must disclose clearly and conspicuously, in the same medium and where
the audience will see it, for example "#ad" or "Paid by [Brand]"; a platform's own label may not be
enough by itself ([KB-COMPLIANCE-011], with
[KB-COMPLIANCE-002], in `../../marketing_kb/compliance/ftc-endorsements-and-fake-reviews.md`). The creator
describes only real experience ([KB-COMPLIANCE-012]); the brief gives facts and links, never results the
creator has not had; engagement is never bought ([KB-COMPLIANCE-010]). `gtm-checker` checks the brief and
the finished post; the operator signs and pays, and no seat contacts a creator or commits spend. A
lead-magnet form states who will contact the person and how, and follow-up stays inside that statement.
Commenters and likers are never scraped or loaded into a sequence ([KB-VOUT-063]); watch for mentions of
the company by hand or with the platform's own search and alerts. Whether a business audience changes the
disclosure rule is unverified; apply it in full. `UNVERIFIED — seeded, needs derivation` The source says well-run startups pay
business creators for posts and lead-magnet drops, monitor brand mentions, and run outreach to everyone
who engages; this corpus keeps the first two (mentions watched by hand or with the platform's own search
and alerts) and rejects the last.

**[KB-VOUT-071] (internal doctrine)** Pick a channel by whether the target can be found on it. A
professional network lets the operator search by role, company and size, so a hand-built target list is
possible; a platform with no such filters yields only people who engaged with something, so use it only
for a target known to be active there. The channels the venture rulings approve are listed in the
`bizdev-outbound-strategist` primer; any other platform needs an operator ruling first and, like every
channel, no scraping, bots, scheduling tools or rented profiles. `UNVERIFIED — seeded, needs derivation` The source says direct
messages on another large social platform are very limited and its users cannot be filtered to an ideal
customer profile, while the professional network can; the platforms' current terms were not checked.

## 7. Rejected and bounded tactics from the same source (and the rule each hits)

**[KB-VOUT-062] (internal doctrine)** **Rented or borrowed profiles of real people** are rejected: it is
sending as an identity that is not the sender's, against the platform's user agreement
(`founder-led-relationships.md` §4 cites it) and against the `gtm-checker` identity lane. The source's
"ethics are up to you" framing does not change this.

**[KB-VOUT-063] (internal doctrine)** **Scraping profile or post audiences and automated profile
sequencing** are rejected by the 2026-09-27 operator ruling (no scraping, bots or scheduling tools on the
professional network); the by-hand route in [KB-VOUT-061] is the sanctioned version.

**[KB-VOUT-064] (internal doctrine)** **Burner (disposable) domains and mailboxes used to outrun
complaints** are rejected as evasion; the source uses "burner" for inboxes that let a sender scale volume
and for a rented profile that protects a main one. Sending infrastructure follows [KB-VOUT-010] in `b2b-cold-email-and-deliverability.md`
(separate sending domain or domains with SPF, DKIM and DMARC, warm-up, per-mailbox volume and the stop
rules); a domain is added for capacity or isolation, never to outrun complaint or bounce signals. `UNVERIFIED — seeded, needs derivation` The
source warns that constantly buying new infrastructure marks weak campaign fundamentals, which would make
it a campaign problem to fix at its source.

**[KB-VOUT-072] (internal doctrine)** **A service that registers sending domains and creates mailboxes**
is bounded, not rejected. The company is the registrant and owner of every domain, with accurate
registrant details (false registration data is an aggravated violation, [KB-VOUT-005]); every mailbox
belongs to a real person or a named role at the company, never an invented persona; SPF, DKIM and DMARC are
published before the first send ([KB-VOUT-011], [KB-VOUT-012]); and fast setup does not shorten warm-up or
raise per-mailbox volume ([KB-VOUT-018], [KB-VOUT-019]). Giving a service the sequencer's API key gives it
access to the sending account, so grant it only for setup, revoke it afterwards, and note which service
holds what. Any new subscription is spend that goes to the operator. A service used to keep replacing
domains is the rotation [KB-VOUT-064] rejects. `UNVERIFIED — seeded, needs derivation` The source says one such service sets up
domains, inboxes and sequencer connections from a single form in under a couple of hours.

**[KB-VOUT-065] (internal doctrine)** **Automatic replies and booking** (the source's AI reply agent
that answers within seconds and books meetings) are a per-company operator decision, never a default.
Without a recorded ruling, every reply is a draft the operator sends. Where the company's deal folder
records a standing approval (for example: an obvious yes gets one short approved reply offering two real
open times from the operator's calendar, the operator copied, every send logged, then a person takes
over), it runs in the operator's own sending tool, configured to exactly that scope and using the
approved reply text ([KB-VOUT-060]). Questions, objections, maybes, anything about price, legal terms or data,
and any second reply stay drafts for the operator. A seat relies on an approval only when it can cite
the deal-folder entry (date and the operator's words). No venture seat sends, replies or books as the
operator, whatever the approval says.

**[KB-VOUT-066] (internal doctrine)** **Calling the number found in a reply's signature** follows the
company's own calling rules. By default the operator places no cold calls, so the answer is a prompt
written reply offering times. Where the company's deal folder records the operator's own calling rules
(for example manual B2B calls he dials himself, only to states cleared by a per-state check, business
landlines only, within local calling hours, checked against the internal do-not-call list), he may phone
a person who replied, under those rules; a reply that asks for a call is the strongest case. The same
rules apply to a number found in a data tool's record: where a number came from does not turn an
unrequested call into a requested one. A seat relies on the calling rules only when it can cite the
deal-folder entry (date and the operator's words). Agents never call. No automated, prerecorded or AI-voice call, ringless voicemail or cold text is ever in scope (TCPA,
see the venture-wide lines).

## Decision rules

- Campaign not yet live and a tool is proposed: name the blocked step first ([KB-VOUT-044]); no step, no tool.
- Drafting a campaign: state the lead lever ([KB-VOUT-046]) and the single segmenting variable ([KB-VOUT-049]) at the top of the plan.
- Source claims a figure from this interview: repeat it only with its UNVERIFIED tag.
- A tactic needs scraping, an automated sequence, a borrowed identity or a rotating domain: refuse and offer the by-hand or draft-for-operator version. An automatic reply is allowed only inside a standing approval the deal folder records ([KB-VOUT-065]).
- Reply arrives: operator-approved draft within the reply target ([KB-VOUT-059]); an automatic reply only within a recorded standing approval ([KB-VOUT-065]); no agent sends.
- No lever is defensible for the offer: say so and stop; do not compensate with volume.

## Anti-patterns

- Buying a database, sequencer and enrichment tool before one message has been sent ([KB-VOUT-044]).
- Splitting a campaign into many surface-detail tests while the offer and list are unproven ([KB-VOUT-047]).
- One generic email to every segment ([KB-VOUT-049]).
- Sending an unedited assistant draft, or letting the drafter check itself ([KB-VOUT-055], [KB-VOUT-057]).
- Adding a guarantee, free offer or named customer the company cannot document ([KB-VOUT-048]).
- Treating the source's numbers as benchmarks (all are UNVERIFIED).

## Sources

- Practitioner interview on building an email-and-professional-network campaign with an AI assistant,
  published 2026-10-09, transcribed locally and retrieved 2026-10-11; single source, self-reported.
  Transcript and analysis are in the operator's research folder for it (outside every repo). The
  five-lever list is credited in the interview to a third party's post. Neither the speaker, the
  interview's title nor that post is named in this corpus; the grade rests on the source type, not on
  who said it.
- [`b2b-cold-email-and-deliverability.md`](b2b-cold-email-and-deliverability.md),
  [`founder-led-relationships.md`](founder-led-relationships.md) — linked, not repeated.
- [`../../marketing_kb/sales/speed-to-lead.md`](../../marketing_kb/sales/speed-to-lead.md),
  [`../../marketing_kb/sales/follow-up-cadences.md`](../../marketing_kb/sales/follow-up-cadences.md) —
  linked, not repeated.
- [`../../marketing_kb/conversion/ab-testing-discipline.md`](../../marketing_kb/conversion/ab-testing-discipline.md)
  — governs how any lever test is run.
