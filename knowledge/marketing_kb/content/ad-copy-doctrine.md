# Content Domain — Paid Ad Copy Doctrine

Added 2026-09-19 (operator-directed knowledge-base upgrade). Governs every character of copy that
renders inside a Google or Meta paid-ad unit: RSA headlines/descriptions, Meta primary
text/headline/description, and video ad scripts. This is the content-strategist seat's doctrine
for that surface — `paid-acquisition-strategist` owns targeting, campaign/ad-group structure,
budget, and bidding; this seat owns every word that displays. See
`~/.claude/knowledge/marketing_kb/paid_acquisition/competitor-targeting-doctrine.md` for the parallel targeting-side doctrine (what is
and isn't possible on each platform's audience/segment tooling) — read that file before any
targeting question, this one before any ad-copy question.

**Root cause this file closes:** as of 2026-09-19 paid ad copy was an orphaned lane — neither this
seat's primer/dossier nor `paid-acquisition-strategist`'s corpus claimed ownership of ad-unit text,
so no seat's doctrine governed it. See this seat's primer §1 and dossier for the lane-fence line
this file backs.

## 1. Google RSA field inventory and asset-count doctrine

A Google Responsive Search Ad takes up to **15 headlines at 30 characters each** and **4
descriptions at 90 characters each**, plus two optional display-path fields of 15 characters each.
Deliver the FULL set — 15 headlines and 4 descriptions — never a partial set. Google assembles
combinations at auction time; an under-filled ad has strictly less material to test.

- Every headline must stand alone AND read correctly in any order — Google will combine them in
  ways the writer does not control.
- Write each of the 4 descriptions to a DIFFERENT selling point (never four rephrasings of the
  same claim).
- Google recommends **at least 2 RSAs with Good or Excellent Ad Strength per ad group** and
  reports, on average: 15% more clicks and conversions moving an ad group from Poor to Excellent
  Ad Strength; a 6.6% conversion increase from adding a second RSA; a 3.7% increase from adding a
  third. Deliver asset sets for **2–3 distinct RSAs per ad group**, not one.

Source: https://support.google.com/google-ads/answer/7684791 (field limits, 15 headlines/4
descriptions, character counts) and https://support.google.com/google-ads/answer/6167122 ("at
least 2 responsive search ads (RSA) with Good or Excellent Ad Strength per ad group"; 15% / 6.6% /
3.7% figures), both retrieved 2026-09-19.

## 2. Ad Strength is a diagnostic, not a performance score — and pinning suppresses it

Ad Strength is a feedback tool for asset diversity and combination testing. Google states
explicitly it is **not** used to calculate Ad Rank, Quality Score, or auction wins, and does not
directly influence serving eligibility. "Excellent" means only that Google has enough diverse
material to test combinations.

- **Never report Ad Strength to the operator as a result**, and never rewrite good copy purely to
  move the label.
- **Pinning reduces the total number of headlines/descriptions that can be shown.** Google warns
  against pinning multiple identical or highly similar headlines to one position — it blocks A/B
  testing and lowers Ad Strength. Pin only where a specific campaign goal requires consistent
  messaging.
- **Pin ONLY where a claim must never be dropped** — typically: the never-claim-governed speed
  line (see `ANTI-PATTERNS.md` #1), and any required offer/billing disclosure (see §8). Everything
  else runs unpinned. Pinned positions remain honored in AI-powered Search ads.

Source: https://support.google.com/google-ads/answer/9921843 ("Ad Strength is a feedback tool for
asset diversity and combination testing. It isn't used to calculate Ad Rank, Quality Score, or
auction wins"; pinning-reduces-shown-count and pinning-lowers-Ad-Strength language) and
https://support.google.com/google-ads/answer/6167122 ("Only pin your headlines if you have
specific campaign goals that require consistent messaging"), retrieved 2026-09-19.

## 3. Google can auto-generate ad text from the landing page — hard gate

Google's "text customization" (formerly "automatically created assets") uses extractive techniques
plus generative AI drawing on our domain, landing page, existing ads, and ad-group keywords to
generate headlines/descriptions we never wrote. Google states campaigns using text customization
will be automatically upgraded to AI Max starting September 2026. Google instructs advertisers to
ensure site content is accurate and not misleading, and to monitor generated ad content for
accuracy in the asset details report — **responsibility for the generated text is ours**, not
Google's. In Performance Max, suggested assets an advertiser accepts carry full advertiser
ownership and report with "Advertiser" as their source.

**Consequence:** the never-claim list is not enforceable by careful copywriting alone once text
customization is on. Two binding duties:

1. **For launch, specify text customization OFF** so the never-claim list holds by construction.
   State this explicitly in every ads handoff — never leave the default unaddressed.
2. **The landing page is now ad-copy surface.** Banned phrasing living on the page can be extracted
   into a live ad. The page must pass the never-claim gate BEFORE the campaign launches, and this
   seat has a recurring duty to read the asset details / combinations report and flag any
   generated line that breaches the never-claim list.

Source: https://support.google.com/google-ads/answer/11259373 ("your domain, landing page,
existing ads, and keywords in your ad group"; "extractive techniques and generative AI"; September
2026 AI Max auto-upgrade; "Ensure your website content is accurate, not misleading"; asset details
report monitoring) and https://support.google.com/google-ads/answer/16683066 ("When you add an
asset from suggested assets, you have full ownership and control over it"; "They'll show Advertiser
as their source in asset reports"), retrieved 2026-09-19.

## 4. Meta field inventory, mobile truncation, and creative-volume doctrine

Meta ad text is three fields: **primary text** (~125 characters visible on mobile before the "See
More" cut), **headline** (~40 characters baseline, far shorter in some placements — Reels overlay
as little as 10 characters), and **description** (~25 characters, frequently not rendered at all;
reliably shown only in a handful of placements such as Marketplace, Audience Network, Facebook
Search Results, and In-Stream Video).

- Write primary text so the **complete proposition lands inside the first ~125 characters** —
  anything after the fold is a bonus, never where the offer or the claim lives.
- **Never place a required disclosure below the fold**, and never rely on the description field to
  carry one (it may not render at all).
- Deliver many genuinely distinct copy variants built on different angles (pain, mechanism, offer,
  objection) — not one message reworded. Practitioner guidance for Advantage+ converges on roughly
  **10 or more varied creatives** as the working input volume — cite this as a practitioner
  benchmark, not a platform rule.

Source: https://adsuploader.com/blog/meta-ad-copy-specs (practitioner; ~125-char mobile cutoff,
Reels overlay 10-char headline, description hidden on most placements) and
https://www.1clickreport.com/blog/advantage-plus-shopping-best-practices-2026 (practitioner; "aim
for 10 or more active creatives"; "ASC rewards variety because the algorithm's job is to match the
right ad to the right person"), retrieved 2026-09-19.

## 5. Meta Advantage+ creative enhancements are default-on and can rewrite our text

Meta applies Advantage+ creative enhancements by default. Meta states some enhancements may be
turned on by default and can be turned off at any time, and recommends checking and approving
previews of all ads before they go live. Enhancements include text improvements — Meta may alter
the words we shipped.

Same consequence as Google text customization (§3): for a product governed by a never-claim list,
**specify in the handoff which enhancements are OFF** (text/copy-altering ones at minimum), and
**preview every rendered variant before launch**. Never assume the copy delivered is the copy that
serves.

Source: https://www.facebook.com/business/ads/meta-advantage-plus/creative ("Some enhancements may
be turned on by default, but you can turn them off at any time"; "We recommend checking and
approving the previews of all your ads before they go live and toggling off any that do not work
for you"; text improvements listed as an enhancement), retrieved 2026-09-19.

## 6. Meta AI-content disclosure vs. a company's own no-AI-label directive (where one exists)

Meta reads AI-provenance signals written into a file at generation time — the IPTC Digital Source
Type property in the XMP header, and C2PA manifests where present — and requires disclosure of
AI-generated or AI-manipulated creative via Ads Manager's disclosure control. Failure to disclose
can result in ad rejection, and Meta's automated systems can retroactively flag previously approved
ads. The cited source itself cautions that metadata-based detection alone is unreliable, so
self-disclosure (not silence) is the defensible posture.

Where a company has its own standing directive to never publish anything labeled or detectable as
AI content, this platform behavior collides with that directive. **Resolve by SOURCE, never by
omitting a required disclosure:** paid creative should use real product screenshots, licensed
stock, or real photography, sanitized through that company's own image-provenance-stripping
pipeline where one exists (a company that has built this should have its own tool/script for it —
see that company's own dossier or pack for the current path). Never advise skipping a
platform-required disclosure to satisfy a no-AI-label directive — that trades a public label for a
policy strike, which is worse. If a proposed asset can only be produced AI-generated, that is a
STOP and an operator/decision-queue card for that company, not a judgment call this seat makes
alone.

Source: https://www.auditsocials.com/blog/meta-ai-generated-content-label-policy-2026
(practitioner; Meta "reads industry signals... most directly the IPTC Digital Source Type property
in the media file's XMP header, and provenance asserted through C2PA manifests where present";
disclosure "an enforced advertising requirement rather than an optional disclosure"; "failure to
disclose can result in ad rejection"), retrieved 2026-09-19; corroborated by independent search
results (Browser Media, Cinerads, davidtamachi) that Meta scans creatives for C2PA/IPTC markers and
applies labels automatically. Consistent with, and reinforces, a company's own image-provenance
stripping pipeline and no-AI-label directive where one exists (this section, above) — does not
contradict it.

## 7. Competitor names are restricted in ad text — the obvious challenger play is unavailable

Google restricts using trademarks in an ad from a direct competitor. Permitted uses are narrow —
resellers, informational sites, and ordinary descriptive use — none of which describes the current
company's product's relationship to any named competitor.

- **Never write a competitor brand name into a Google headline or description**, including
  comparison forms ("X vs Y," "the better alternative to Y") — these are takedown-eligible.
- **Split that trips people up:** Google does NOT restrict trademarks used as keywords, nor in the
  second-level domain of the display URL. `paid-acquisition-strategist` may legitimately BID on
  competitor terms while this seat still may not NAME the competitor in ad text.
- This matters for competitor-URL custom-segment targeting: Google states entering URLs reaches
  people who browse **similar** sites, and explicitly that this does not mean ads show on those
  URLs — the resulting audience is a lookalike, not a confirmed user of a named product. Write
  switching-intent copy that names the problem and the mechanism, never the rival brand.

Source: https://support.google.com/adspolicy/answer/6118 (restricts "Using trademarks in an ad
from a direct competitor"; exceptions for resellers, informational sites, descriptive use; will NOT
restrict "Using trademarks as keywords" or "Using trademarks in the second-level domain of the ad's
display URL") and https://support.google.com/google-ads/answer/9805516 ("Your ads will reach people
who browse websites similar to the URLs you enter... This doesn't mean your ads will show on those
URLs"), retrieved 2026-09-19.

## 8. Ad-policy compliance for a card-required, no-trial, money-back-guarantee offer

Some companies in this KB's roster run a negative-option subscription offer shape: card required up
front, no free trial, a money-back guarantee window instead. Where that is the current company's
offer, four binding consequences apply to ad copy (re-derive the exact guarantee window and price
from that company's own pricing source of truth before writing copy that states them):

1. Google prohibits failure to clearly and conspicuously disclose the payment model or full
   expense a user will bear before and after purchase, and prohibits pricing practices that create
   a false or misleading impression of cost. Any ad or landing page mentioning the money-back
   guarantee must make the recurring charge and its amount plain in the same view.
2. Where results are guaranteed, Google requires a clear and easily accessible refund (money-back)
   policy — a money-back guarantee therefore requires a real, linked, findable refund page, not
   just a copy line.
3. **Never write "free" or imply a trial** where the current company does not actually offer one.
   Google expressly prohibits promoting a free trial without clearly stating the trial period or
   that the user will be automatically charged at the end.
4. ROSCA remains in force and is enforced independently of the vacated Click-to-Cancel Rule: clear
   and conspicuous disclosure of material terms BEFORE billing information is collected, express
   informed consent, and a simple cancellation mechanism. The Eighth Circuit vacated the
   Click-to-Cancel Rule in July 2025, and the FTC restarted negative-option rulemaking January 30,
   2026 — treat this area as live and re-check before any campaign relaunch. (Draft ANPRM submitted
   to OIRA 2026-01-30; publicly announced 2026-03-11 — see `pricing_economist_primer.md`'s "March
   2026" framing of the same rulemaking; both dates refer to the same event at different stages.)

Source: https://support.google.com/adspolicy/answer/6020955 ("Failure to clearly and conspicuously
disclose the payment model or full expense that a user will bear before and after purchase is not
allowed"); https://support.google.com/adspolicy/answer/15938375 ("Promoting a free trial without
clearly stating the trial period or that the user will be automatically charged at the end of the
trial"); https://support.google.com/adspolicy/answer/15936857 ("If you guarantee certain results,
you're required to have a clear and easily accessible refund (money-back) policy"); all retrieved
2026-09-19. FTC/ROSCA timeline: https://www.gibsondunn.com/ftc-restarts-negative-option-rulemaking-after-eighth-circuit-vacatur-enforcement-under-rosca-continues/
(8th Cir. vacatur July 2025; ANPRM to OIRA January 30, 2026; "ROSCA standards remain fully
operative"), retrieved 2026-09-19. Check the current company's own pricing source of truth for its
locked, current offer terms (trial status, price, guarantee window, which plans it covers) before
stating any of them in ad copy.

## 9. Unreliable/improbable-outcome claims — broader than the existing never-claim list

Google prohibits inaccurate claims and claims that entice the user with an improbable result (even
if that result is possible) as the likely outcome. This seat's existing never-claim list is
necessary but not sufficient: a line can be literally true about the product and still violate
this rule by presenting an atypical business outcome as typical.

- **Never imply a revenue, win-rate, or job-count outcome from using the product.**
- Where a testimonial claims specific results, Google requires a visible disclaimer that there is
  no guarantee of specific results and that results can vary.
- This binds ANTI-PATTERNS.md #11 (never let a testimonial use a founder-invented dollar figure not
  tied to a real, verifiable source) into a platform-enforcement rule, not only an internal honesty
  rule: an unsourced dollar figure in an ad is both a truth defect and a policy violation.
- For a pre-revenue company with no customer outcomes yet, ads must carry mechanism and offer only
  — never outcome proof that doesn't exist yet.

Source: https://support.google.com/adspolicy/answer/15936857 ("Making inaccurate claims or claims
that entice the user with an improbable result (even if this result is possible) as the likely
outcome a user can expect is not allowed"; testimonial-disclaimer requirement), retrieved
2026-09-19. Internal: `ANTI-PATTERNS.md` #11 (unsourced founder-invented dollar figures). For a
company still in an early-access/beta phase, this is consistent with optimizing for activation and
feedback rather than conversion — check the current company's own stated goal for that phase before
assuming conversion is the ad's real objective.

## 10. Meta Personal Attributes policy — house style risk

Meta prohibits ads that assert or imply personal attributes of the audience, including vulnerable
financial status, health, age, race, religion, and others — specifically barring implying knowledge
of a user's or their family's financial information. Meta permits "you/your" language WITHOUT a
personal attribute; what it forbids is second-person phrasing implying knowledge about the viewer
(Meta's own non-compliant example: "Are you bankrupt? Check out our services").

This seat's direct-response house style (name the pain, address the reader as "you") sits close to
that line whenever pain-naming touches a covered attribute — financial struggle above all. Rewrite
to describe the **work or the product** rather than the reader — illustrative only (re-derive the
current company's own measured claim per `voice-and-vocabulary.md` #1 rather than reusing an
unqualified time figure): "Estimates that take an evening, done fast" is safe; "Tired of losing
your evenings?" is riskier; "Can't afford another underbid job?" is the violating form.

**This fence applies to Meta only** and does not bind Google RSA copy, where second-person is
normal — the same message legitimately gets two different drafts per platform. Never ship one copy
set to both platforms unchecked.

Source: https://transparency.meta.com/policies/ad-standards/objectionable-content/privacy-violations-personal-attributes/
(vulnerable financial status is a covered attribute; prohibits ads that "Imply knowledge of
personal or organizational financial information of a user or user's family"; permits "Use
you/your language without a personal attribute"; non-compliant example "Are you bankrupt? Check out
our services."), retrieved 2026-09-19. Internal: `headline-doctrine.md` §1 ("you statements
outperform vague claims") and §2 ("name the actual pain: the evening lost to a spreadsheet").

## 11. Message match between ad copy and the landing page is this seat's obligation

Ad copy and the landing page it points to are ONE artifact for continuity of promise. Whatever the
ad promises must be the first thing the page says, in the same words — a mismatch between the ad
CTA and the page CTA is a defect **in the ad copy**, not merely a page problem.

This does not reopen the layout fence (primer §5, dossier lane fences): this seat does not
restructure the page — it specifies the exact promise string the page must carry and hands
structural conflicts to `conversion-architect`. Offer-specific: never let an ad imply a trial or a
no-card start when the page requires a card — that is both a message-match failure and the Google
dishonest-pricing exposure in §8.

Source: https://www.saashero.net/google-ppc/roi-b2b-saas-ad-strategies/ (practitioner; supports
"tight message match between ad and page is essential" — no specific lift figure is claimed here;
do not cite a numeric lift for this practice — never quote an unmeasured number as fact), retrieved
2026-09-19.

## 12. Recording ad-copy provenance

Once live ad copy exists for a company, record where it lives, which campaigns/ad groups it maps
to, and the text-customization / Advantage+-enhancement settings it was approved under (§3, §5) —
approved copy is only truthful under the platform settings it was approved with. See that
company's own dossier/pack for the current state of its ad-copy provenance inventory — this
runtime file is doctrine only, never the record of any one company's live copy.
