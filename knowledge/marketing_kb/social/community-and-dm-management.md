# Community and DM management — comment moderation, response-time signals, and messaging automation limits

How to run the reply/comment/DM side of a social account without tripping a platform policy or
manufacturing the engagement `meta-organic-formats-and-ranking.md` says is supposed to be earned
genuinely. Read that file and `ANTI-PATTERNS.md` in this directory first — this file assumes both.

## Response time is a named business signal, not just good manners

Meta operates a **"very responsive" badge** on a Facebook Page's Messenger presence, tied to a
published response-rate and response-time threshold: a 90%-or-higher response rate combined with a
response time under 15 minutes [KB-SOCIAL-051] **UNVERIFIED (primary source unreachable:
https://www.facebook.com/business/help/201893553741970)** — third-party sources report this as Meta's
own published badge criteria, but Meta's own Help Center article returned only a page title on
automated fetch on 2026-09-27; its body text could not be independently confirmed. Before this exact
threshold anchors any specific commitment (a promised response SLA, a badge-earning plan), re-fetch
that Help Center page directly (a headed browser can reach what automated fetch could not) and re-cite
it as primary. **Automated away-messages and instant-reply auto-responders do not count toward earning
the badge** — the badge measures genuine human response behavior, not whether an auto-reply fired
[KB-SOCIAL-052] **UNVERIFIED (primary source unreachable:
https://www.facebook.com/business/help/201893553741970)** — same sourcing caveat as KB-SOCIAL-051.

**The mechanism-level fact worth acting on regardless of the exact badge threshold:** the
"very responsive" badge above is itself Meta's own named, measured response-time signal on the
platform — **replying fast, with a real human, is a measured business signal on this platform, not
just a courtesy.** (A broader claim once stood here — that Meta's ranking documentation for
click-to-Direct-message ad delivery and profile "Active" status also treats response time as a
ranking input — but no official or third-party source could be found to support it as of
2026-09-27; it has been removed rather than left uncited. If a specialist later finds a real source
for a response-time signal in ad delivery or the "Active" indicator specifically, re-add it here
with a `[KB-SOCIAL-NNN]` citation rather than restating it from memory.)

## Engagement bait is a named, banned ranking-suppression trigger — not a style complaint

Meta's own Transparency Center defines engagement bait explicitly: "Posts that explicitly request
engagement (such as votes, shares, comments, tags, likes or other reactions)" outside of specific
carved-out exceptions (helping find a missing person, fundraising, sharing a petition)
[KB-SOCIAL-053] (official, Meta Transparency Center, "Engagement bait," retrieved 2026-09-27:
https://transparency.meta.com/en-gb/features/approach-to-ranking/content-distribution-guidelines/engagement-bait).
**Correction (2026-09-27, re-verified directly against the cited page):** Meta's page does NOT name
compound tactic labels like "vote baiting," "tag baiting," "share baiting," "comment baiting," or
"react baiting" anywhere in its text — it names only the plain interaction types themselves (votes,
shares, comments, tags, likes, other reactions) in the single sentence quoted above [KB-SOCIAL-054]
(official, same source, re-fetched and confirmed 2026-09-27; a prior version of this claim asserted
Meta uses these five compound terms — that assertion did not match the source and has been removed).
Meta's own stated rationale is direct user feedback: "people dislike spammy posts on Facebook that
ask them to interact by liking, sharing, commenting and taking other actions on posts" [KB-SOCIAL-055]
(official, same source, retrieved 2026-09-27) — and the consequence is reduced distribution for posts
that use these patterns, not merely a style ding.

Instagram's own Recommendation Guidelines (which Threads also follows) are third-party-reported to
separately name "clickbait, engagement bait, or which promotes a contest or giveaway" as content that
is actively demoted in recommendation surfaces [KB-SOCIAL-056] **UNVERIFIED (primary source
unreachable: https://help.instagram.com/1580067092348264)** — Instagram's own Recommendation
Guidelines page returned only a page-title shell on automated fetch on 2026-09-27, so the exact quoted
phrase could not be independently re-confirmed against the primary source; the underlying "engagement
bait is a named demotion category on this platform" fact is separately corroborated by Meta's own
Transparency Center source above for the Facebook/Instagram-shared ranking system, so treat that
narrower mechanism-level fact as confirmed while the exact Instagram-specific wording stays unverified.

**The bright line, worked against `meta-organic-formats-and-ranking.md`'s legitimate-engagement
doctrine:** "Comment YES if you're renovating this year" is banned engagement bait — a generic
vote-prompt with no substantive content. "Which finish do you like better on this actual bathroom
we're mid-project on, matte or gloss?" — tied to a real, specific, in-progress project photo — is a
legitimate call-to-comment that earns the comment signal honestly, per the format-decision doctrine
already in this directory's ranking file. The difference is not the presence of a question; it's
whether the question is attached to genuine content a viewer would want to answer regardless of
being asked, versus a content-free prompt designed only to farm the interaction.

## DM automation — the messaging-window rule that governs what a bot can send and when

Meta's Messenger Platform policy defines a **24-hour standard messaging window**: "Businesses have up
to 24 hours to respond to a user. Messages sent within the 24-hour window may contain promotional
content" [KB-SOCIAL-057] (official, Meta for Developers, Messenger Platform Policy Overview, retrieved
2026-09-27: https://developers.facebook.com/docs/messenger-platform/policy/policy-overview/). Outside
that window, a business needs a specific message tag or permission to send anything at all — **but this
is not a blanket ban on promotional content outside the window.** The policy names specific,
approved-use-case tags for outside-window messaging: "Message tags enable sending important and
personally relevant updates to users outside the 24-hour standard messaging window, for a set of
approved use cases." Most tags (e.g. account-update, confirmed-event-update) are restricted to
non-promotional, personally-relevant updates — but the **Sponsored Messages** mechanism is an explicit
exception: "Sponsored Messages allow businesses to reengage with people who have an open conversation
with their Page in Messenger. Sponsored messages can be sent outside the 24-hour standard messaging
window and can include both promotional and non-promotional content" [KB-SOCIAL-058] (official, same
source as KB-SOCIAL-057/059, retrieved 2026-09-27 — the same Messenger Platform Policy Overview page
that KB-SOCIAL-057 and KB-SOCIAL-059 quote directly; an earlier version of this claim marked this
specific citation UNVERIFIED as unreachable, which contradicted the two adjacent claims quoting the
identical URL as read successfully in the same pass — that contradiction is corrected here in favor
of the page having been reachable, consistent with 057/059; re-fetch if a future pass finds the page
unreachable again). Sponsored Messages is a paid, tag-adjacent placement distinct from the free
message tags, with its own approval/cost mechanics not detailed here. **The accurate, narrower rule:**
outside the 24-hour window, the *free* message tags are restricted to their named non-promotional use
case (e.g. news messaging "must not be used for promotional content"), and any general promotional
send outside the window requires the paid Sponsored Messages placement, not a free tag.
A separate **Human Agent tag extends this to a 7-day window specifically for a real human
representative** manually responding to a user's message, as distinct from automated/bot messaging,
which stays bound to the 24-hour window [KB-SOCIAL-059] (official, same source, retrieved 2026-09-27).

**Operational read:** an automated DM responder (a chatbot answering "what are your hours," routing a
lead to a booking link) is legitimate and platform-sanctioned *inside* the 24-hour window opened by
the user's own message — this is not the same thing as cold-messaging strangers, which the platform's
API design blocks structurally, not just by policy: "A person must initiate the conversation" before a
business can message them via the Messenger Platform API, and the messaging flow is triggered by an
inbound webhook notification when a person messages the business first — there is no API call that lets
a business originate a first contact to a person who hasn't messaged it [KB-SOCIAL-060] (official, Meta
for Developers, "Overview for the Messenger Platform," retrieved and confirmed by direct fetch
2026-09-28: https://developers.facebook.com/docs/messenger-platform/introduction — quoted verbatim:
"Messenger from Meta lets a business' Facebook Page or Instagram Professional account respond to
people who message them through Facebook, Instagram, or a Meta plugin on your mobile app or website. A
person must initiate the conversation." — corrected 2026-09-28: a prior pass marked this page
unreachable and cited third-party reporting instead; the page is directly fetchable and confirms the
claim verbatim, so this is now a primary-source citation) — this is consistent with the 24-hour-window
mechanism itself (KB-SOCIAL-057, above) — a business cannot bulk-upload a contact list and message it,
because there is no window open to send into until the person messages first.

**AI/bot disclosure — treat as a compliance requirement, not just a courtesy:** when an automated
system, not a human, is drafting or sending DM replies, disclose that plainly on first contact ("Hi,
this is [Business]'s automated assistant") rather than letting a customer believe they're texting a
person — this is consistent with general consumer-protection expectations around automated
communications. **As of this corpus's current state, `compliance/` has no filed claim specifically
covering automated-DM/chatbot disclosure** (its `tcpa-a2p-10dlc.md` covers autodialed/prerecorded
calls and texts, a different legal category from a platform DM chatbot) — this paragraph states this
corpus's own operational floor, not a cited legal holding, and should be re-pointed to a `compliance/`
claim in the same edit that adds one. **Honor an opt-out instruction immediately and unconditionally** — a user saying "stop,"
"unsubscribe," or the equivalent must end automated outreach to that user; this is a hard rule
regardless of how the sanctioned messaging window is otherwise being used.

## Comment moderation — hiding is a sanctioned tool, not evasion, but has a real limit

Instagram's own comment-management tools (Hide, Restrict, Limit, Hidden Words) are third-party-reported
to be built-in, sanctioned moderation features, not a policy workaround [KB-SOCIAL-061] **UNVERIFIED
(primary source unreachable: https://help.instagram.com/253643061710253)** — Instagram's own
comment-moderation Help Center page returned only a page-title shell on automated fetch on 2026-09-27,
so the primary documentation of these tools' existence and intended use could not be independently
re-confirmed this pass. **The real limit reported alongside it: hiding a comment does not notify the
commenter and the comment remains visible to its author** — they will not know it's hidden from others
unless they check from a different account [KB-SOCIAL-062] **UNVERIFIED (primary source unreachable:
https://help.instagram.com/253643061710253)** — same sourcing caveat as KB-SOCIAL-061. **Never use
hide/restrict
as a way to suppress a legitimate negative review or complaint disguised as a comment** — a genuine
service complaint belongs in the reputation-management flow (`reputation/escalation-triggers.md`,
`reputation/never-do.md`), not silently hidden from an account's own public feed; hiding is for spam,
abuse, and off-topic noise, never for making a real complaint invisible while leaving the commenter
unaware it was suppressed.

## Contractor bend

A small owner-operated home-services business's owner checking their own business DMs and comments from a truck between job sites cannot
sustain a sub-15-minute response SLA manually all day — the honest recommendation is a lightweight
automated first-response (confirming receipt, offering a booking link, disclosing it's automated) that
buys time to a genuine human reply within the same business day, never a fully automated conversation
that pretends to be the owner. This buyer is also the person most likely to see a stranger's
"comment YES for a free quote!" post from a competitor and want to copy it — the engagement-bait
doctrine above is the specific, sourced reason not to, phrased in the business-consequence terms this
buyer responds to: it gets the post suppressed by the platform, not just disliked by viewers.
