# Video/Content Licensing, Platform Policy & Safety — Worker Rules

Terse, applicable rules for an agent assembling or publishing marketing video/social content.
All hard constraints below are operator rulings or per-company policy — never contradict them
regardless of what a cited source implies is merely "allowed."

**Provenance:** aggregated from third-party creator-tool, vendor, and practitioner guides unless a source is marked OFFICIAL (published by the platform, standards body, regulator, or licensor itself). Every non-OFFICIAL source in this file is practitioner opinion, not platform documentation; any platform-behaviour claim (a platform limit, cap, spec, ranking behaviour, or policy) that rests only on such a source is UNCONFIRMED-PRIMARY (the `INDEX.md` flag set) until a platform page confirms it — never report it as the platform's own rule.

## Hard constraints (operator rulings — never violate)

- B-roll: each shot ≤2.5s; b-roll totals ≤20% of runtime; never two b-roll shots back-to-back;
  no b-roll shot starts before the 3.0s mark of the video.
- Every video/page opens product-first (the hook IS the product on screen), never a logo or b-roll.
- Vocabulary and claims are per company, not universal: banned terms, numeric-claim restrictions,
  and any other wording rule: follow the company pack's `claims_policy` and that company's own
  video-producer dossier; where neither states them, DEGRADED — never invent, assume, or carry over another company's list
  (see `INDEX.md`'s precedence note).
- Viewing review: the rendered cut is watched — contact sheets against the timed transcript, per shot (primer §4/§7) — before any upload; the seat's own frame-viewing review satisfies this, no separate human viewer is required.
- **AI-content handling is per company.** Follow the company pack's `ai_content_policy.mode`
  (`disclose_never_strip` | `strip_before_publish` | `forbid`, defined in
  `tools/gtm/company_schema.json`), else that company's dossier, else DEGRADED — never publish an
  AI-assisted asset without knowing which mode applies. Under every mode, run the provenance
  metadata check below on the exact final file before upload, so you know whether the platform
  will label it.

## Stock footage/photo licensing — Pixabay

- Pixabay Content License grants free commercial + non-commercial use, worldwide, royalty-free,
  irrevocable, non-exclusive; modification/adaptation is permitted. [Pixabay License Summary,
  retrieved 2026-09-12]
- Attribution is NOT required. Crediting is welcomed, not mandatory (suggested form: "by
  [Contributor] via Pixabay"). [Pixabay License Summary, retrieved 2026-09-12]
- Prohibited: reselling/redistributing Pixabay content "as is" on stock/wallpaper marketplaces
  without adding substantial original value; printing on physical products/merch for resale
  without added value; using content as part of a trademark/trade name/service mark. [Pixabay
  License Summary; Pixabay FAQ, retrieved 2026-09-12]
- Prohibited: using recognizable trademarks/logos/brands in the content for commercial purposes
  tied to goods/services (e.g., merch); using identifiable people in an immoral, illegal,
  misleading, or deceptive way. [Pixabay License Summary, retrieved 2026-09-12]
- Caveat: identifiable people, logos, brands, or audio samples IN the content may carry separate
  rights (privacy, trademark, publicity) not cleared by the Pixabay license — verify before using
  content with a recognizable face/brand for anything commercial-facing. [Pixabay License
  Summary, retrieved 2026-09-12]

## Stock footage/photo licensing — Pexels

- Pexels license: free for personal + commercial use, no attribution required (credit
  appreciated, not necessary). [Pexels License, retrieved 2026-09-12]
- Allowed use cases explicitly include: websites, blogs, e-commerce, newsletters, presentations,
  ads, marketing campaigns, print materials, social media. [Pexels License, retrieved 2026-09-12]
- Prohibited: selling unaltered copies of a photo/video as a poster/print/physical product without
  first modifying it; redistributing/reselling on other stock/wallpaper platforms; using as part
  of a trademark/trade name/service mark; showing identifiable people "in a bad light or
  offensive way"; implying a depicted person or brand endorses your product. [Pexels License;
  Pexels Help Center, retrieved 2026-09-12]
- Exception: if Pexels content is pulled via the Pexels API (not the website UI), attribution IS
  required — a prominent link back to Pexels and, where possible, credit + link to the
  photographer's page. [Pexels Help Center, retrieved 2026-09-12]

## Music/SFX licensing — YouTube Audio Library

- Two license types exist per track: (1) standard YouTube Audio Library license — royalty-free
  and Content-ID-safe, but restricted to use IN YouTube videos only; (2) Creative Commons
  Attribution (CC BY 4.0) — usable on any platform, but requires crediting the artist. [YouTube
  Help: "Use music and sound effects from the Audio Library", retrieved 2026-09-12]
- Filter the library to "Attribution not required" to find tracks that need no credit at all;
  filter to "Attribution required" / Creative Commons icon to see tracks that do, and use the
  library's own "Copy" attribution-text feature. [YouTube Help, retrieved 2026-09-12]
- Using a standard-license (non-CC) Audio Library track OUTSIDE YouTube (a website, another
  social platform, a podcast) is a terms-of-service violation — only CC BY tracks are portable
  off-YouTube, and only with the required credit. [YouTube Help, retrieved 2026-09-12; vidiq
  summary, retrieved 2026-09-12]
- Practical rule for cross-platform marketing videos (posted to more than just YouTube): only use
  tracks explicitly marked CC BY, and always paste the generated attribution text into every
  platform's description/caption field the track appears under.

## Font licensing

- Google Fonts catalog: nearly every font is released under either the SIL Open Font License (OFL) or
  Apache 2.0 (a few families use the Ubuntu Font License). OFL and Apache 2.0 are OSI-approved; all three permit commercial use, including self-hosted
  webfonts, app embedding, and ebook embedding — no extra tier, no fee, no attribution required
  for use. [Google Fonts FAQ; font-converters.com Licensing Guide, retrieved 2026-09-12; Ubuntu Font License families: google/fonts repository `ufl/` directory, checked 2026-10-13]
- SIL OFL's only real restriction: the font file itself cannot be sold as a standalone product;
  selling/shipping products or media that USE the font is unrestricted. A modified/forked version
  of an OFL font must stay under the OFL. [SIL Open Font License overview, retrieved 2026-09-12]
- Practical rule: prefer Google Fonts (OFL/Apache2) for any on-screen title/lower-third typography
  in marketing video — zero licensing risk, no attribution line needed anywhere (video
  description, end card, or elsewhere).
- A non-Google "free for personal use" font is NOT the same as commercial-cleared — verify the
  license explicitly grants commercial use and web/video embedding before using it in anything
  published under the company name (uncited practitioner consensus — verify per-font license text
  directly).

## AI-content disclosure — YouTube

- YouTube's "Altered or synthetic content" disclosure is required when content is realistic
  enough that "a viewer could easily mistake [it] for a real person, place, scene, or event" and
  it was meaningfully altered/generated by AI. Triggering examples: swapping a real person's face,
  cloning a real person's voice, making it look like a real building/place did something that
  didn't happen, or realistically depicting a fictional major event. [YouTube Blog: "How we're
  helping creators disclose altered or synthetic content", retrieved 2026-09-12]
- NOT required to disclose: AI used for scripts/ideas/auto-captions (production assistance only);
  animation/stylized/illustrated content that doesn't look like real footage; color/lighting
  filters, ordinary special effects, beauty filters. [YouTube Blog, retrieved 2026-09-12]
- Mechanism: check the "Altered or synthetic content" box in YouTube Studio at upload. Most
  videos get a label in the description; sensitive-topic videos (health, news, elections,
  finance) additionally get an on-player label. [YouTube Blog, retrieved 2026-09-12]
- YouTube can detect and apply this label itself even if the creator didn't disclose, and a
  creator cannot remove a YouTube-applied label; deceptive synthetic content can be removed
  outright. Voluntarily disclosing does NOT hurt reach, ranking, recommendations, or monetization.
  [YouTube Blog; minimatters.com summary, retrieved 2026-09-12]
- Practical reading: AI-voiced narration that is not a synthetic clone of a real identifiable
  person, over real screen-captured product footage, likely does NOT trigger YouTube's disclosure
  checkbox under its stated scope; re-verify per video if any AI-generated b-roll/imagery of
  realistic people/places is used, and apply the company's own `ai_content_policy` (above).

## AI-content disclosure — Meta (Facebook/Instagram)

- Meta applies an "AI Info" label across Facebook/Instagram/Threads either from creator
  self-disclosure or from its own detection. [Meta Transparency Center: "Labeling AI Content",
  retrieved 2026-09-12]
- Detection is metadata-driven first: Meta reads the IPTC "Digital Source Type" field (e.g.
  `TrainedAlgorithmicMedia`) in a file's XMP header and any C2PA manifest — the same standard
  used by Google/OpenAI/Microsoft/Adobe/Midjourney/Shutterstock generation tools — then falls back
  to its own proprietary content classifiers, then self-disclosure. [Meta Transparency Center;
  davidtamachi.ca C2PA summary, retrieved 2026-09-12]
- Self-disclosure is REQUIRED (Meta states it "may apply penalties" for skipping it) specifically
  for organic posts containing photorealistic video or realistic-sounding audio that was
  digitally created or altered. Ordinary AI-generated still images don't carry that same hard
  self-disclosure mandate, but Meta auto-labels them anyway whenever it detects AI metadata.
  [auditsocials.com Meta policy summary, retrieved 2026-09-12]
- For ADS specifically: as of 2026, Ads Manager has a mandatory disclosure control for
  AI-generated/AI-manipulated ad creative, and from June 1, 2026 Meta also runs automated
  detection on ads independent of advertiser input. Ordinary AI-assisted edits (color correction,
  cropping, upscaling, object cleanup) do not require disclosure; disclosure is required once AI
  generates the actual depicted subject (a person, product, or scene). Political/social-issue/
  election ads have a stricter, mandatory disclosure rule for any AI-created or -edited
  photorealistic image/video or realistic audio depicting a real person or event. [Meta
  Transparency Center; cinerads.com; auditsocials.com, retrieved 2026-09-12]
- Practical rule (mechanical check, any company): run `strings <file> | grep -ci
  'TrainedAlgorithmicMedia\|jumdc2pa\|c2pa'` before publishing any image/video to a public Meta
  or YouTube surface — non-zero means the platform's own detection will label it regardless of
  whether disclosure is offered. This is a metadata check, not a visual guess. What to do with a
  non-zero result depends on the company's `ai_content_policy`: `strip_before_publish` runs the
  company's own sanitizer (named in its dossier) and re-checks for zero hits on the exact final
  file; `disclose_never_strip` discloses and never strips; `forbid` does not publish the asset.
  An AI-assisted editing pass after sanitizing can reintroduce the marker, so always check the
  final file.

## PII and faces in screen recordings

- Screen recordings of live product/CRM/admin screens routinely capture real customer PII in
  side panels, ticket history, and list views even when the recording's subject is something
  else entirely. [supportbench.com PII guide, retrieved 2026-09-12]
- GDPR/CCPA can treat an unredacted recording containing real PII as a personal-data exposure;
  whether it is reportable depends on the facts. GDPR administrative fines reach up to €20M or 4% of
  worldwide annual turnover, whichever is higher (Art. 83(5)); CCPA/CPRA carries per-violation civil penalties and a
  private right of action for some breaches (Cal. Civ. Code § 1798.150) (check the current amounts in the statute).
  [supportbench.com, retrieved 2026-09-12]
- Before recording or publishing any product screen capture: use a seeded/synthetic demo tenant
  with fake names/emails/addresses, never a real customer's data (the primer's no-PII hard rule; the
  company's dossier names its demo tenant); the same requirement applies to anything captured on
  camera for marketing.
- If a real customer environment must ever appear on screen (rare, and should be avoided by
  policy), redact/blur every visible PII field before export — name, email, phone, address,
  account/case numbers — never rely on cropping alone since off-screen panels can still be
  captured in a wider shot or a later re-edit.
- Best practice for any recorded session involving a real person's participation (a testimonial,
  a live customer walkthrough): get explicit recorded/written consent stating the purpose and how
  the recording will be stored/used before recording begins. [spinach.ai recording consent
  guide, retrieved 2026-09-12]

## Faces/biometrics — legal exposure (uncited practitioner-consensus items flagged)

- Three US states have standalone biometric privacy statutes covering facial geometry/faceprints:
  Illinois (BIPA), Texas (CUBI), Washington (RCW 19.375). [recordinglaw.com Biometric Privacy Laws
  by State, retrieved 2026-09-12]
- Illinois BIPA requires written notice of purpose/retention period AND a signed release BEFORE
  collecting a faceprint from a real person, and uniquely allows private lawsuits with statutory
  damages ($1,000/violation negligent, $5,000/violation intentional) — this is the highest-risk
  jurisdiction if any face-detection/recognition technology (not just "a face is on camera") is
  applied to footage of real people. [recordinglaw.com, retrieved 2026-09-12]
- Texas and Washington require consent (not necessarily written) before capturing biometric
  identifiers, enforced only by the state AG (no private lawsuit right). [recordinglaw.com,
  retrieved 2026-09-12]
- Practical rule: this exposure is about running facial-recognition/biometric-identification
  software on footage of real identifiable people, not merely filming a person's face — ordinary
  video of a consenting employee or contractor on camera is not itself a BIPA/CUBI/RCW event
  unless a faceprint/biometric template is extracted and stored. Flag for legal review only if
  any planned pipeline step does face matching/recognition/verification against footage of real
  people. (Uncited beyond the state-law summary above — confirm with counsel before relying on
  this distinction for anything high-stakes.)

## YouTube community guidelines — duplicate/reused/spam content

- YouTube's "inauthentic content" policy (renamed from "repetitious content" July 2025) targets
  mass-produced, low-effort, templated content with no meaningful original human input —
  including AI tools "churning out high volumes of similar content with minimal changes."
  [YouTube Spam Policy; Music Ally policy-update summary, retrieved 2026-09-12]
- Reposting/reusing someone else's footage is fine if you add "significant original commentary,
  modifications, or educational/entertainment value"; it becomes a violation when there's no
  meaningful original contribution (near-identical narrated slideshows, repeated near-duplicate
  uploads). [YouTube Spam Policy; vidiq Reused Content guide, retrieved 2026-09-12]
- Consequence scope: enforcement is at the CHANNEL level, not per-video — repeated violations can
  suspend the whole channel from the YouTube Partner Program (demonetization), independent of any
  single video's individual standing. [vidiq Reused Content guide, retrieved 2026-09-12]
- Separately prohibited under the Spam policy: misleading titles/thumbnails/descriptions
  ("clickbait" that doesn't deliver what's promised); engagement manipulation (bots, coercion,
  rewards-for-likes/subs/views); repetitive/templated low-effort community posts or polls.
  [YouTube Spam Policy, retrieved 2026-09-12]
- Practical rule: never upload the same finished video twice (even to "fix" something small) —
  unpublish/replace or edit metadata on the existing upload instead of duplicating; never post
  near-duplicate cuts (same footage, trivial edits) across multiple uploads; each published video
  needs a genuinely distinct edit/narration/value, not just a re-render.

## Appeals — appealing a disputed takedown or restriction

- YouTube: appeal from YouTube Studio → Dashboard → "Channel violations" card → "Appeal" (mobile:
  Content tab → select the restricted video → Appeal). One appeal per restriction — if rejected,
  it cannot be re-appealed. Appeal window is 90 days from the strike/warning. Typical review time
  is 5–10 business days; deleting the video does NOT remove the strike, only a successful appeal
  does. [YouTube Help: "Appeal a Community Guidelines strike or video removal", retrieved
  2026-09-12]
- Meta (Facebook/Instagram): first request Meta's own re-review of the removed/restricted content
  from the in-app notification ("request another look"); if that in-app review is unfavorable,
  Instagram content specifically can be escalated to the independent Oversight Board within 15
  days of the decision (window closes after that). Not all violation types are appealable — Meta
  excludes the most severe categories (e.g., child-exploitation material) from appeal entirely.
  Typical Meta appeal turnaround is reported around 7–10 business days (practitioner figure,
  UNCONFIRMED-PRIMARY). [Instagram Help Center:
  "Appeal Instagram's content decision to the Oversight Board"; Meta Transparency Center:
  "Appealed content", retrieved 2026-09-12]
- Practical rule: an appeal of a takedown, strike, or restriction **that is disputed on the
  merits** is filed from the affected channel/account's own session, under whatever tier the
  company's autonomy rules assign to it (governing plan §20.6). Whether a company appeals every
  disputed takedown by standing policy (for example an "always appeal" ruling) is that company's
  own rule, recorded in its pack or dossier — never assumed here for every company. Card it only
  if the platform's own appeal UI presents a genuine judgment call requiring account-owner
  identity/context the agent doesn't have.
- **Carve-out — a correct takedown is fixed, not appealed.** When the takedown is right — real PII
  on screen, a consent failure, or an actual policy breach (content the no-PII hard rule says
  should never have been published) — remove or replace the content and do not appeal. YouTube
  allows one appeal per restriction, so a reflexive appeal on a correct takedown burns it, and
  arguing for content that exposes real people's data is itself a second failure.

## Sources

- [Pixabay Content License Summary](https://pixabay.com/service/license-summary/) (OFFICIAL) — retrieved 2026-09-12
- [Pixabay FAQ](https://pixabay.com/service/faq/) (OFFICIAL) — retrieved 2026-09-12
- [Pexels License](https://www.pexels.com/license/) (OFFICIAL) — retrieved 2026-09-12
- [Pexels Help Center: license/commercial use](https://help.pexels.com/hc/en-us/articles/360042295174-What-is-the-license-of-the-photos-and-videos-on-Pexels) (OFFICIAL) — retrieved 2026-09-12
- [YouTube Help: Use music and sound effects from the Audio Library](https://support.google.com/youtube/answer/3376882?hl=en) (OFFICIAL) — retrieved 2026-09-12
- [YouTube Blog: How we're helping creators disclose altered or synthetic content](https://blog.youtube/news-and-events/disclosing-ai-generated-content/) (OFFICIAL) — retrieved 2026-09-12
- [Meta Transparency Center: Labeling AI Content](https://transparency.meta.com/governance/tracking-impact/labeling-ai-content/) (OFFICIAL) — retrieved 2026-09-12
- [Meta Transparency Center: Appealed content](https://transparency.meta.com/policies/improving/appealed-content-metric/) (OFFICIAL) — retrieved 2026-09-12
- [Instagram Help Center: Appeal Instagram's content decision to the Oversight Board](https://help.instagram.com/675885993348720) (OFFICIAL) — retrieved 2026-09-12
- [YouTube Help: Appeal a Community Guidelines strike or video removal](https://support.google.com/youtube/answer/185111?hl=en) (OFFICIAL) — retrieved 2026-09-12
- [YouTube Help: Spam, deceptive practices & scams policy](https://support.google.com/youtube/answer/2801973?hl=en) (OFFICIAL) — retrieved 2026-09-12
- [Google Fonts FAQ](https://developers.google.com/fonts/faq) (OFFICIAL) — retrieved 2026-09-12
- [SIL Open Font License — Wikipedia overview](https://en.wikipedia.org/wiki/SIL_Open_Font_License) — retrieved 2026-09-12
- [Recording Law: Biometric Privacy Laws by State (BIPA, CUBI, RCW)](https://www.recordinglaw.com/us-laws/data-privacy-laws/biometric-privacy-laws/) — retrieved 2026-09-12
- [Supportbench: Screenshots & Recordings — PII Safety Guide](https://www.supportbench.com/collect-screenshots-screen-recordings-pii-considerations/) — retrieved 2026-09-12
- [Spinach AI: Recording Consent for Enterprise Teams](https://www.spinach.ai/blog/meeting-recording-consent-it-policy) — retrieved 2026-09-12 (practitioner source, uncited legal authority)
