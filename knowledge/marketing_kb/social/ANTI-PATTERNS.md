# Social Anti-Patterns — Things a Seat Must NEVER Recommend

Every item below is something any GTM agent touching organic social (Instagram, Facebook, LinkedIn,
YouTube) must refuse to propose, even when a founder/operator asks for it directly, even when a
competitor is visibly doing it, and even when it would plausibly work short-term. Cite this file when
refusing.

---

## 1. Claiming a specific algorithmic posting-frequency requirement

**What it is:** Stating that a platform's algorithm requires a specific number of posts per week/day
("you must post 3x/week or the algorithm punishes you") as an established ranking fact.

**Why it's banned:** No primary source located across this corpus's research states a specific
optimal posting frequency as a named ranking input — `meta-organic-formats-and-ranking.md` explains
in detail why ranking evaluates each post against named signal groups (engagement quality,
watch-through, shares), not a cadence count. **Reject example:** "Instagram's algorithm requires at
least 5 posts a week to stay in the algorithm's good graces." **Pass example:** "post less often but
make each post earn a real comment or share — cadence itself is not a documented ranking input; see
`content-calendar-doctrine.md` for how to actually decide how often to post."

## 2. Engagement bait

**What it is:** A post that explicitly asks for votes, tags, shares, comments, or reactions with no
substantive content behind the ask — "Comment YES if you agree," "Tag a friend who needs this," "Like
if you're excited."

**Why it's banned:** Named, official Meta Transparency Center policy: "Posts that explicitly request
engagement (such as votes, shares, comments, tags, likes or other reactions)" are demoted in
distribution [KB-SOCIAL-053]/[KB-SOCIAL-054]/[KB-SOCIAL-055] (see `community-and-dm-management.md`
for the full citation and the worked legitimate-vs-bait comparison). This is a named ranking
suppression, not a style preference — a post using this pattern gets less reach, not just a worse
reader reaction. **Reject example:** "Comment YES if you're renovating this year!" with no other
content. **Pass example:** a real project photo with a genuine, specific question tied to that
project's actual details.

## 3. Buying followers, engagement, or comments

**What it is:** Purchasing followers, likes, comments, or views from a third-party service, or using
engagement-pod/reciprocal-engagement schemes (groups of accounts that mutually like/comment on each
other's posts regardless of genuine interest) to inflate metrics.

**Why it's banned:** This is a synthetic, non-organic signal that misleads both the platform's ranking
systems and any human viewer reading follower/engagement counts as social proof. It directly
undermines the trust doctrine this corpus is built around (`shared/contractor-buyer-psychology.md`,
`shared/homeowner-buyer-psychology.md`): a purchased engagement count that later collapses or reads as
obviously fake (foreign-language spam comments, follower counts wildly out of proportion to real
engagement) is a worse credibility event than slow, real growth. Platforms also actively purge
detected fake engagement, which can crater a follower count visibly and without warning.

## 4. Posting AI-labeled or AI-detectable content without disclosure or sanitization

**What it is:** Publishing an image or video that carries AI-provenance metadata (C2PA/IPTC
`DigitalSourceType=TrainedAlgorithmicMedia`) to a public social account without either sanitizing that
metadata (where the underlying content is genuinely the business's own real work) or honestly
disclosing AI use (where required, e.g. YouTube's altered-or-synthetic-content toggle).

**Why it's banned:** See `platform-ai-labeling.md` for the full platform-mechanics doctrine. Both
Meta and YouTube detect and label this content via metadata/provenance signals, not a visual check —
an agent cannot "eyeball" a file into being safe. A publicly labeled post is a trust-destroying event
for a buyer already primed to distrust software/marketing claims (`shared/contractor-buyer-
psychology.md`). **Reject example:** posting a design-tool "inspiration" render with intact C2PA
metadata as if it were a real completed project. **Pass example:** a real phone photo of a real job,
or a genuine capture whose provenance metadata came only from an incidental AI-editing step (a
one-click "enhance," a generative-fill touch-up), run through the company's own sanitization gate
before publish (see the company's own pack/dossier for its concrete implementation) — fully
AI-generated or realistically altered content is disclosed instead, per `platform-ai-labeling.md`,
never stripped and passed off as a plain sanitization candidate.

## 5. Automated DM outreach outside the sanctioned messaging window

**What it is:** Bulk-messaging a list of contacts who have not first messaged or engaged the account,
or continuing automated promotional messaging to a user beyond the platform's sanctioned response
window.

**Why it's banned:** Meta's Messenger Platform Policy structurally and by-policy limits businesses to
a 24-hour response window opened by the user's own message, with narrower tag-based exceptions outside
it [KB-SOCIAL-057]–[KB-SOCIAL-059] (see `community-and-dm-management.md`). Messaging strangers at
scale outside a user-initiated conversation is not a gray area — it is blocked by API design and
against policy, and risks the business's messaging access entirely.

## 6. Undisclosed automated/bot conversation presented as a real person

**What it is:** Letting a customer believe they are DMing a human employee when a bot is actually
drafting or sending the replies, with no disclosure.

**Why it's banned:** This corpus treats automated-communication disclosure as a compliance floor
(`community-and-dm-management.md`) — `compliance/` does not yet carry a filed claim specifically for
automated-DM/chatbot disclosure (see that file's own note) — misrepresenting
a bot as a person is a trust violation on top of any regulatory exposure, and directly undermines the
same buyer-trust foundation this entire corpus protects.

## 7. Hiding a genuine complaint disguised as a comment, instead of routing it to reputation management

**What it is:** Using Instagram's Hide/Restrict comment tools to make a real service complaint
disappear from public view rather than addressing it.

**Why it's banned:** Hiding a comment does not notify its author, who remains unaware it's hidden from
everyone else [KB-SOCIAL-062] — using this mechanism to silently suppress a legitimate grievance while
the commenter believes it's still visible is deceptive and forecloses the actual resolution path this
corpus's reputation-management doctrine exists for (`reputation/escalation-triggers.md`,
`reputation/never-do.md`). Comment-hiding tools exist for spam and abuse, not for making inconvenient
truths invisible.

## 8. Porting a specific engagement-rate, growth-rate, or "best time to post" number from one
## vertical's corpus as fact for another

**What it is:** Quoting a dental-vertical (or any other analogous-vertical) social-media benchmark
(a specific engagement rate, follower growth target, or optimal posting-time claim) as if it applies
to a residential remodeling GC or a B2B SaaS audience, without independent re-derivation.

**Why it's banned:** These numbers are vertical-specific by construction — dental-patient social
behavior and remodeling-homeowner or B2B-software-buyer social behavior differ in search/discovery
patterns, purchase cycles, and platform usage. Only the **mechanism** (e.g. "before/after visual proof
performs well for a service business selling a visible outcome") ports; any specific **number** must
be marked `UNVERIFIED — seeded from [source vertical] analog, needs [target vertical] derivation`
(e.g. `seeded from dental analog, needs home-services derivation`, or the reverse direction) per
`shared/citation-style.md` and this corpus's house style (see `INDEX.md`).

## 9. Recommending a defunct or retired platform feature

**What it is:** Instructing an agent or operator to use a UI control or feature that the platform has
since removed — e.g. "turn on LinkedIn Creator Mode" (the toggle was removed March 2024
[KB-SOCIAL-034] (official, LinkedIn Help Center, "Updates to Creator Mode," retrieved 2026-09-27:
https://www.linkedin.com/help/linkedin/answer/a5999182); see `linkedin-b2b.md` for the full claim
and quote), or building a content strategy around Instagram Guides without first re-verifying
the feature still exists and is discoverable.

**Why it's banned:** Platform mechanics change fast, and stale doctrine that survives unchallenged in
a corpus is exactly how an agent ends up instructing a real operator to hunt for a control that no
longer exists — wasting their time and eroding trust in the doctrine itself. Any platform-mechanics
claim older than ~90 days should be treated as due for re-verification before it anchors a live
recommendation, per `shared/citation-style.md`'s re-verification-window rule.

## 10. Claiming a "safe" AI-touched image based on visual inspection alone

**What it is:** Judging whether an image will trigger an AI-content label by looking at it ("this
looks like a real photo, it's fine") instead of checking its actual embedded metadata.

**Why it's banned:** Embedded provenance metadata (C2PA/IPTC) is the documented primary detection
signal for both Meta and YouTube — see `platform-ai-labeling.md` — but it is not the only one: Meta
itself states it is building classifiers to catch AI content that carries no markers at all, and
YouTube runs its own content-analysis systems alongside its C2PA read. A visually convincing image
with intact AI-provenance metadata is labeled regardless of how it looks to a human; a genuine photo
that passed through one AI-assisted editing step can pick up the same metadata and get labeled too.
Reading the file's metadata directly before publish is the reliable floor for the known, checkable
trigger — never a visual judgment call — but a clean metadata check is not by itself a guarantee
against every detection path either platform runs.

## 11. Promoting an invitation-only or audience-limited event in public or off-audience venues

**What it is:** Posting a private, members-only or audience-limited event (a professional peer group, a
customer-only workshop, a referral-partner evening) in general community, events or networking
groups, in groups outside its geographic area, or as a public Facebook Event. Usually done because
"more reach is better" or because the groups were easy to find.

**Why it's banned:** The owner decides who an event is for, and broad reach breaks that promise.
The event's audience and privacy are part of the brief, not a detail to infer from the flyer.
Reach is also hard to take back. In the incident behind this rule, the public Event's edit screen
offered no Private option, so it could only be deleted, together with its RSVPs and other people's
shares of it. The group posts had to be removed one group at a time, and a post held for admin
approval looked the same as a deleted one until the group's pending view was checked.
[KB-SOCIAL-066] (internal doctrine, incident: private-event outreach run, observed once,
2026-10-02: six group posts and a public Page Event taken down after the owner clarified the
audience; client record kept in that client's own folder.) Whether Facebook ever allows a public
Event to be made private again is UNVERIFIED — seeded, needs derivation; plan as
if it does not.

**Reject example:** "Let's also post it in the statewide events group and make a public Event so
anyone can share it." **Pass example:** "Before choosing venues, confirm with the owner: who is this
event for (role, area), is it private or open, and may invitees forward it? Then post only where the
members match that audience, and use a members-only group Event rather than a public one."

---

## Contractor bend

None of the above changes for the small owner-operated home-services/trade business buyer — if anything the stakes are higher, because
this buyer has no in-house social-media staff to catch a bad recommendation before it costs a labeled
post, a suppressed account, or a publicly visible complaint that looks ignored. When explaining why
something is off-limits to this buyer, skip the platform-policy framing and lead with the business
consequence in plain terms: "if we do this, the platform shows your posts to fewer people" or "if we
hide that complaint instead of answering it, the person who wrote it knows you saw it and chose to
bury it instead of fixing it — that's worse than the original complaint." Never assume this buyer will
push back on a shortcut being offered; the obligation not to offer it is entirely on the agent.
