# Google Local Services Ads (LSA) for Contractors

Nothing in this file is ported from the prior internal ads discipline (it had no LSA doctrine).
This entire file is built fresh from external research (retrieved 2026-09-05), because LSA is
arguably the single highest-fit paid channel for a residential remodeling GC and this corpus would
be incomplete without it.

---

## What LSA actually is, and why it's structurally different from standard Search

Local Services Ads are a **separate Google product from standard Google Ads**, not a campaign type
inside the same account. The differences are not cosmetic — they change the entire operating model:

- **Placement:** LSA listings appear at the very top of the search results page — above standard
  Google Ads, above the map pack, above organic results — for local-service queries like "kitchen
  remodel contractor near me" (`UNVERIFIED — seeded, needs derivation`: recorded 2026-09-05 as
  unnamed "industry guides" with no publisher or URL).
- **Pricing model: pay-per-LEAD, not pay-per-click.** A click that doesn't result in someone
  contacting the business costs nothing. This is the single biggest structural difference from
  standard Search, where every click costs money regardless of what happens after: "You're charged
  for each valid lead you receive through your Local Services ad" (official, Local Services Help,
  "How leads work", `support.google.com/localservices/answer/7195435`, retrieved 2026-09-28).
- **No keywords and no Search bid-strategy ladder — but the budget is still derived.** LSA has no
  keyword targeting, no match types, and none of the Search bid strategies in
  [`bid-strategy-ladder.md`](bid-strategy-ladder.md). Its budget is an **average weekly budget**:
  "Set an average weekly budget based on the average number of leads you want to receive in any
  given week"; a single week may run over it, but not the monthly maximum (average weekly budget ×
  weeks per month) (official, same page, retrieved 2026-09-28). Bidding is either a maximum
  per-lead bid you set or Google's "Maximize Leads" mode (official, Local Services Help, "About ad
  rankings", `support.google.com/localservices/answer/7527305`, retrieved 2026-09-28). **The LSA
  cap is still derived, never a round number:** target cost-per-lead × expected weekly lead count,
  shown as math, per [`budget-as-formula.md`](budget-as-formula.md) and
  [`ANTI-PATTERNS.md`](ANTI-PATTERNS.md) #1. **Setting or changing an LSA budget or lead cap, a
  service area, or a job type is a `$` item (primer §4: budgets/caps, plus its pay-per-lead
  area/category line, which extends plan §20.6's Thumbtack/Angi row to LSA)** — before migration and after it (see the
  migration section below). A max per-lead bid set inside an operator-approved range is
  within-ceiling, like any bid inside an approved range.

## The Google Guarantee / Google Verified badge

- The **Google Verified** badge signals that a Local Services advertiser has "completed
  verification requirements" (official, Local Services Help, "About Google Verified badge",
  `support.google.com/localservices/answer/7549288`, retrieved 2026-09-27). **The money-back
  guarantee is discontinued:** "Google will be discontinuing the Money Back Guarantee associated
  with the Google Guarantee badge," with reimbursement requests accepted only for services booked
  before December 7, 2025 (same page). Never describe the badge to a customer or in ad copy as a
  Google-backed money-back guarantee. The previously-quoted "$2,000 US lifetime cap" applied to
  the discontinued guarantee and does not appear on the current page — do not cite it.
- Getting verified requires a real background check and license/insurance verification process —
  this is not instant, and it is a genuine prerequisite gate, not a formality. Budget calendar time
  for it before promising a launch date.
- **This verification requirement is itself a trust asset for a GC's marketing**, independent of
  the ad spend — the badge can be referenced in other marketing materials once earned.

## Pay-per-lead pricing and the dispute mechanism

- **Reported per-lead pricing for contractors runs roughly $25–$150+ depending on trade and
  market**, with remodeling specifically running toward the higher end because job values are
  larger and the buying decision takes longer (`UNVERIFIED — seeded, needs derivation`: recorded
  2026-09-05 as "multiple industry benchmark aggregations" with no publisher or URL).
- **A specific remodeling-contractor benchmark: average LSA cost-per-charged-lead around $73**,
  per one unnamed third-party aggregator's own client-campaign data (`UNVERIFIED — seeded, needs
  derivation`: no publisher or URL recorded 2026-09-05; small sample — 2 client campaigns cited —
  directional only, not a market-wide figure).
- **A blended home-services benchmark across trades: roughly $53/lead**, per a larger third-party
  aggregation (~888 contractors, ~$6.7M spend cited; `UNVERIFIED — seeded, needs derivation`: no
  publisher or URL recorded 2026-09-05).
- **Invalid and low-quality leads are credited mostly automatically now.** "Leads are first
  assessed when the potential customer makes initial contact, and leads determined to be invalid or
  low quality are not charged"; charged leads are reassessed over time and may be credited
  automatically, and "in most cases, credits will be applied to your account balance within 30
  days." **"Google no longer supports credits for 'job type not serviced' and 'geo not serviced'
  leads"** — so a lead for a service or area the business doesn't cover is not creditable; keep
  job types and service areas accurate instead. Credits "aren't available for health care
  verticals, tax specialists, or advertisers in EMEA," and automatic credits apply only in the US
  and Canada (official, Local Services Help, "About Automated Local Services Ads lead credits",
  `support.google.com/localservices/answer/15100654`, retrieved 2026-09-28). A poor-quality lead
  can also be reported through that lead's feedback survey (official, "How leads work",
  `answer/7195435`, retrieved 2026-09-28). Whether a separate manual dispute flow still exists,
  and its window, is `UNVERIFIED — needs a direct fetch` (the credits page links "How to dispute
  charges" but does not describe it).
- **Dispute discipline matters financially.** Third-party sources report contractors recovering
  roughly 6–20% of LSA spend back through disputes depending on trade (roofing and HVAC often see
  the higher end, likely due to storm-chasing and emergency-service spam calls) — treat this as
  UNVERIFIED, seeded from third-party aggregation with no controlled methodology disclosed, needs
  the account's own dispute-rate tracking once live to confirm.

## The 2026 structural shift: LSA is migrating into Google Ads as a Performance Max campaign type

**This is a live, in-progress platform change — re-check it before building any LSA-dependent
doctrine into a production workflow.** Google's own Help Center now documents it: existing Local
Services Ads campaigns move into Google Ads as a specialized Performance Max campaign type with
pay-per-lead goals, in three phases — "The first phase of the migration begins for select home and
storefront service advertisers in the United States" in **August 2026** (plumbing, HVAC,
electrical, appliance repair, house cleaning, lawn care, roofing, pest control, and moving); **late
2026** expands to service-area businesses without storefronts and to accounts with custom bidding
or booking configurations; **2027** covers non-U.S. accounts and the remaining business categories
(official, [Google Ads Help: Local Services Ads transition to Performance Max campaigns with
pay-per-lead goals](https://support.google.com/google-ads/answer/17213585), retrieved 2026-09-28;
this replaces an earlier, unsourced third-party citation). A general-contractor or remodeling
account is not in the named August 2026 list; which phase covers it is not stated on that page —
`UNVERIFIED`, check the account itself.

What the same official page says carries over, and what does not:

- **Carries over:** "You still only pay for valid leads (such as phone calls and messages) rather
  than ad clicks"; the Google Verified badge for eligible businesses in select verticals; and past
  customer lead history (contact details, message history, older call recordings), which transfers
  automatically (official, same URL, retrieved 2026-09-28).
- **Does not carry over:** "Your previous campaign-level performance metrics (such as past
  impressions, clicks, weekly spend, and ad-level performance reports) will not migrate to Google
  Ads" — export them before an account migrates; manual bidding is "no longer supported in Google
  Ads"; the historical average weekly budget "is automatically divided by 7 to determine your daily
  average budget" (official, same URL). After migration the cap is a daily budget (the old weekly
  budget ÷ 7), still derived as math per [`budget-as-formula.md`](budget-as-formula.md), and any
  change to it — or to service areas or job types — is a `$` item (primer §4), exactly as before
  migration.
- **Still not documented on that page as of 2026-09-28:** whether the dispute-credit process
  survives unchanged, and how the migrated campaign shares account and billing surfaces with
  standard Search — `UNVERIFIED`.
- **Do not assume LSA's current standalone-account structure will still be accurate by the time
  this file is used in a real launch.** Re-check the current state directly against
  [Google's official LSA Help pages](https://support.google.com/localservices) before advising an
  operator on setup steps, since a migration this significant is likely to change specific UI
  flows even if the underlying pricing philosophy holds.

## How LSA fits alongside standard Search for a remodeling GC

LSA and standard Search are not competitors for the same budget — they capture different points in
the buyer's decision:

- **LSA captures immediate, high-intent "find me someone now" searches** — well-suited to smaller,
  faster-decision jobs (a leak repair, a single-room quick job) where the buyer wants to see
  verified, reviewed contractors and pick one quickly.
- **Standard Search (with a real landing page and message-matched ad copy) is better suited to
  larger, higher-consideration remodeling projects** — a full kitchen or bathroom remodel — where
  the buyer is researching, comparing portfolios, and wants more information before ever making
  contact.
- **Running both is common and often complementary** for a GC whose service mix spans both quick
  jobs and large remodels, but they should be evaluated on separate cost-per-booked-job metrics
  (see [`measurement-and-attribution.md`](measurement-and-attribution.md)), never blended into one
  combined "paid search CPL" number — the pricing models and buyer intent are too different to
  average together meaningfully.
- **Reviews and responsiveness directly move LSA cost and ranking**, in a way standard Search does
  not. Google's own ranking page names the bid, how likely the ad is to produce a lead
  ("Missed calls may negatively affect your responsiveness"), and profile quality — "Your rating,
  number of reviews, average response time, use of high-quality images, the verification checks
  you have completed" — and adds that "higher quality profiles ... may rank higher and may also pay
  lower costs per lead" (official, Local Services Help, "About ad rankings",
  `support.google.com/localservices/answer/7527305`, retrieved 2026-09-28). This creates a direct link
  between LSA performance and the business's review-generation discipline (an organic/GBP-lane
  concern, out of scope for this file, but worth flagging as a real cross-dependency).

## Contractor bend

**Scope:** applies only to a company whose pack declares `business_model: local_service` and
whose line of business is home-services/contractor work — see [`INDEX.md`](INDEX.md)'s scope note
(no pack field records line of business yet, so read it from that company's dossier).

- **LSA is arguably the single best-fit paid channel for this exact buyer**, more than standard
  Search or Meta: it requires no keyword strategy, no bid-strategy ladder, and no ad-copy
  A/B-testing discipline to get real leads flowing — which matters enormously for a phone-first GC
  in a truck who has no time or appetite to manage a complex campaign. Consider recommending LSA
  as the FIRST paid channel for a genuinely new-to-paid-marketing GC, ahead of standard Search,
  specifically because of this lower operational burden.
- **The Google Verified verification process is itself a credibility asset a GC should be told
  about explicitly** (a verification badge only — the money-back guarantee it once carried is
  discontinued, see above) — many GCs don't realize the badge exists independent of running ads, or that
  earning it is itself a marketing signal worth having even before evaluating spend levels.
- **The pay-per-lead model is easier to explain to a GC burned by prior software/marketing spend**
  than a CPC/CPA formula: "you only pay when someone actually contacts you" is a genuinely simpler,
  more trustworthy pitch than "we bid on your behalf using a Target CPA algorithm" — lean on this
  in any conversation introducing LSA.
- **The 2026 PMax migration is exactly the kind of platform change a GC will never track on their
  own** and will only notice as "something changed and I don't understand why." Any agent advising
  on LSA should proactively flag this migration and its uncertainty rather than waiting for the
  operator to ask why their setup looks different than a screenshot from a year-old blog post.
- **Lead-quality discipline is a real, recurring task a GC needs help with**, not a
  set-and-forget feature — credits are now mostly automatic, but a busy GC will not check weekly
  that credits arrived, report poor-quality leads through the feedback survey, or notice that a
  wrong job type or service area is producing uncreditable leads (see the credits bullet above).
  This is a concrete, recurring value-add task for an agent managing the account, not a one-time
  setup step; a job-type or service-area change it finds necessary is still a `$` item.

## Sources

- support.google.com/localservices/answer/7195435 (official, Local Services Help, "How leads
  work", retrieved 2026-09-28) — backs: pay-per-valid-lead charging, the average weekly budget and
  monthly maximum, the feedback-survey path.
- support.google.com/localservices/answer/7527305 (official, Local Services Help, "About ad
  rankings", retrieved 2026-09-28) — backs: bid / Maximize Leads, responsiveness, profile-quality
  factors, and lower cost per lead for higher-quality profiles.
- support.google.com/localservices/answer/15100654 (official, Local Services Help, "About
  Automated Local Services Ads lead credits", retrieved 2026-09-28) — backs: automatic credits,
  the 30-day credit timing, no credits for 'job type not serviced'/'geo not serviced', and the
  health care / tax / EMEA exclusions.
- support.google.com/localservices/answer/7549288 (official, retrieved 2026-09-27) — backs: the
  Google Verified badge and the discontinued money-back guarantee.
- support.google.com/google-ads/answer/17213585 (official, retrieved 2026-09-28) — backs: the
  migration into Performance Max with pay-per-lead goals.


## Field notes: running Local Services Ads (added 2026-09-28)

- **LSA can stop silently on an overdue balance.** The account shows "Your ads aren't running — Make
  a payment" only inside LSA. Check billing whenever lead flow drops (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **The Google Verified badge (formerly Guaranteed/Screened) depends on license and insurance.**
  Re-check the badge whenever
  insurance lapses or is reinstated (internal doctrine, retrieved 2026-09-28).
- **The LSA business name and address come from verification and can differ from the Business
  Profile.** The address is not editable in the LSA profile; a wrong or old address needs LSA
  support. Check both match the company's single canonical name and address (NAP) (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **Direct LSA URLs loop (too many redirects) unless they carry the `bid=` parameter.** Open each
  account from a working LSA tab's main menu. Job-type switches are unlabeled toggles: map each to
  its row text before clicking, then Save (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
- **Target service ZIPs by evidence.** One owner restricted remodeling LSA to the ZIP codes where the
  company has sold jobs. It's a defensible starting rule for a small budget; widen only on data, and any
  service-area change needs the operator's spend sign-off (a `$` item, see above) (internal doctrine, retrieved 2026-09-28).
