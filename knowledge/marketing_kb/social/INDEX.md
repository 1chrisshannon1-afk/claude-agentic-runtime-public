# Social Domain — Index

Grep-reachable index for organic-social doctrine (Meta ranking mechanics, Instagram, LinkedIn B2B,
content-calendar cadence, community/DM management, AI-provenance labeling) for any company the GTM
agent department runs. This corpus is not meant to be read wholesale — find the file that answers your
question, read that file only. Every numeric/behavioral claim in every file below carries a stable id
`[KB-SOCIAL-NNN]` and a citation — `(official)`, `(third-party)`, `(internal-measured)`, or
`(internal doctrine)` — with a retrieval date, or is marked `UNVERIFIED — seeded, needs
derivation` or `UNVERIFIED (primary source unreachable: <url>)`. See house-style rules at the bottom
of this file.

**Seat status (2026-09-27):** `content-strategist` is a registered seat (see `content/INDEX.md`'s
own seat-status note) — but a dedicated social-specific seat does not yet exist, so read doctrine
here as forward-looking discipline for whoever fills a social/community-management role in the GTM
department next (most likely `content-strategist` or a future dedicated seat), not as a citation to
an already-live agent.

**Claim-id gap notice (2026-09-28):** `[KB-SOCIAL-007]`–`[KB-SOCIAL-019]` and
`[KB-SOCIAL-023]`–`[KB-SOCIAL-029]` are not assigned to any claim in this corpus as of this writing.
This is not believed to be a scrub deletion — those ids are not present at first commit, and
pre-commit history is unrecoverable from git (this corpus was never tracked before this pass, so
`git log`/`git diff HEAD` show nothing to check the gap against) — but is noted here so a future
auditor does not mistake the gap for lost content without further evidence either way. New claims
append after the highest currently-used id; a gap is never backfilled with an unrelated new claim.

| File | Answers |
|---|---|
| [`meta-organic-formats-and-ranking.md`](meta-organic-formats-and-ranking.md) | What actually decides whether an organic Facebook/Instagram post reaches anyone — the named Feed and Reels ranking signal groups, the format-decision table (which format for which goal), and why no source supports a specific posting-frequency requirement? |
| [`instagram.md`](instagram.md) | How do you actually set up and run an Instagram business account — professional-account setup, the current hashtag cap, Stories/Reels/Guides mechanics, and what's stale doctrine ported from another vertical's corpus? |
| [`linkedin-b2b.md`](linkedin-b2b.md) | What governs a B2B/SaaS company's own LinkedIn presence (not a contractor's own account) — the dwell-time ranking signal, why "turn on Creator Mode" is dead advice, and Newsletter as a distribution format? |
| [`content-calendar-doctrine.md`](content-calendar-doctrine.md) | How should a capacity-constrained account actually plan and batch social content — cadence, batching horizon, and the content-mix rotation — without inventing an algorithmic frequency requirement? |
| [`community-and-dm-management.md`](community-and-dm-management.md) | What governs comment moderation, response-time expectations, and DM automation — the engagement-bait ban, the 24-hour Messenger messaging window, and the limits of comment-hiding tools? |
| [`platform-ai-labeling.md`](platform-ai-labeling.md) | What actually triggers Meta's "AI info" label and YouTube's altered-or-synthetic-content disclosure, how detection works (metadata, not visual inspection), and what a GTM engagement must do before publishing any AI-touched asset? |
| [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) | What must a social-facing seat NEVER recommend — engagement bait, bought engagement, undisclosed AI content, off-window DM automation, hiding real complaints, stale platform-feature advice, promoting a private event in public or off-audience venues? |

## Reading order for a new task

- **Setting up or auditing an organic social presence:** start with
  `meta-organic-formats-and-ranking.md` for the ranking mechanics, then the platform-specific file
  (`instagram.md` or `linkedin-b2b.md`) for account setup and current mechanics, then
  `content-calendar-doctrine.md` for how to actually plan and sustain posting.
- **Running the community/response side of an existing account:** start with
  `community-and-dm-management.md`, checking every draft against `ANTI-PATTERNS.md` before proposing
  it; route any real complaint to `reputation/escalation-triggers.md` rather than a comment-hiding
  workaround.
- **Before publishing any image or video, on any social or video platform:** check
  `platform-ai-labeling.md` if the asset passed through any AI-assisted step at any point in its edit
  history — this applies regardless of which other file governed the content or format decision.

## House style, restated for anyone editing this corpus

- Every numeric/behavioral claim carries a citation tag with a retrieval date, a stable
  `[KB-SOCIAL-NNN]` claim id, and either a real source or an explicit UNVERIFIED marker — no
  unsourced numbers, and no claim presented as settled when its primary source could not be reached.
  See `shared/citation-style.md` for the full tag taxonomy.
- When a primary source blocks automated retrieval or returns only a page title/shell (this happened
  repeatedly in this domain — Meta's own Help Center article on the "very responsive" badge, and
  Instagram's Recommendation Guidelines page, both returned unusable content to automated fetch on
  2026-09-27), the best reachable third-party reporting is cited instead and the primary's
  unreachability is stated alongside it — never silently substituted without saying so, and never
  presented as equivalent in authority to a directly-fetched primary source.
- Platform mechanics move fast on this domain specifically (hashtag caps, feature retirements, label
  mechanisms) — treat any claim here older than ~90 days as due for re-verification before it anchors
  a live recommendation, per `shared/citation-style.md`'s re-verification-window rule. This corpus
  already documents two live examples of stale doctrine risk: the Instagram hashtag cap change
  (`instagram.md`) and LinkedIn Creator Mode's March 2024 retirement (`linkedin-b2b.md`).
  - **A claim citing a source at a URL that is itself known to no longer exist (a retired Help
    Center page, a removed feature's documentation) should say so explicitly in the claim's own
    text** — an automated staleness check keyed to a "retrieved YYYY-MM-DD" date would flag the
    claim's *age*, not the fact that its underlying link no longer resolves, so link rot must be
    called out in the prose itself rather than left for tooling to catch.
- Dental-vertical or other analogous-vertical **numbers** never port as fact — only the **mechanism**
  ports (see `instagram.md`'s and `ANTI-PATTERNS.md`'s own "mechanism, not the numbers" sections for
  worked examples already in this corpus).
- Every file ends with a "Contractor bend" section translating the doctrine for a small
  owner-operated home-services/trade business archetype — phone-first, in a truck, burned by
  software/agencies before, usually with no dedicated marketing staff running social (see
  `shared/homeowner-buyer-psychology.md` and `shared/contractor-buyer-psychology.md`) — **except**
  `linkedin-b2b.md`, whose primary audience is a B2B/SaaS company's own marketing rather than a
  contractor's own presence; that file's Contractor bend section explains this scope distinction
  explicitly rather than skipping the section outright. A company pack for a different vertical
  (e.g. a dental practice) selects and reads its own persona file from its own pack instead — see
  this same house-style bullet in each domain's own INDEX.md (the persona-selection note lives under
  House style, not Cross-domain pointers, in every domain of this corpus).

## Cross-domain pointers (things that touch this domain but belong elsewhere)

- **Reputation/review management as its own discipline** (drafting review responses, escalation
  policy, review-acquisition compliance) belongs to the `reputation/` domain, not here —
  `community-and-dm-management.md` touches it only at the boundary of "don't hide a real complaint
  instead of routing it there," and does not restate `reputation/`'s own doctrine.
- **Local/GBP social-adjacent platforms** (Nextdoor, Yelp, Angi, Houzz, Thumbtack) belong to the
  `local/` domain — this corpus covers Meta (Facebook/Instagram), LinkedIn, and YouTube's
  disclosure mechanics only, not the local-lead-marketplace platforms.
- **Paid social** (Meta Ads, LinkedIn Ads targeting/bidding/CPC-CPL benchmarks, campaign structure)
  belongs to `paid_acquisition/` — this corpus covers organic content and community management only;
  `linkedin-b2b.md` explicitly defers LinkedIn Ads to that domain.
- **Caption/headline copy craft and voice/vocabulary rules** belong to `content/headline-doctrine.md`
  and `content/voice-and-vocabulary.md` — `content-calendar-doctrine.md` schedules and buckets
  content, it does not own how the words are written.
- **CAN-SPAM/TCPA/automated-communication legal compliance beyond this corpus's floor-level DM
  disclosure guidance** belongs to the `compliance/` domain (`compliance/can-spam.md`,
  `compliance/tcpa-a2p-10dlc.md`) — `community-and-dm-management.md` states a floor requirement
  (disclose automation, honor opt-outs) as its own operational minimum; the fuller regulatory
  doctrine lives in those files and should be cited directly rather than duplicated here.
- **GA4/analytics measurement of social traffic and conversions** belongs to the `measurement/`
  domain — this corpus does not build out UTM tagging or conversion-tracking doctrine for social
  campaigns.

## How this corpus was built

Authored 2026-09-27 per the runtime GTM department plan §9 (internal doctrine, retrieved
2026-09-27), company-agnostic by design — no
company-specific facts appear in this corpus; all examples are generic. Primary sources cited
directly where reachable by automated fetch; where a primary source blocked automated retrieval
(several Meta/Instagram Help Center and policy pages returned page-title-only content, and one
Meta AI-labeling transparency URL 404'd), the best reachable third-party reporting on that same
official policy is cited instead with the primary's unreachability stated explicitly, per
`shared/citation-style.md`.
