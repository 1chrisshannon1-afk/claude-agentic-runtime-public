# Platform AI-provenance labeling — Meta "AI info" and YouTube altered/synthetic disclosure

What actually triggers a visible AI-content label on Meta (Facebook/Instagram) and YouTube, what
that label does to reach, and what a home-services or SaaS marketing account must do before
publishing anything AI-touched. This file is the platform-mechanics doctrine; a company's own
mandatory sanitization procedure (if it has one) lives in that company's own pack/dossier — this
file explains *why* such a rule exists and generalizes it company-agnostically for any GTM
engagement, including one with no such pipeline of its own yet.

## Meta's "AI info" label — two separate mechanisms, ads vs. organic

**Ads:** Meta's own Help Center states the AI info label "will appear on the About this ad screen
in the three-dot menu in the top right-hand corner of the ad," and may also appear "next to the
Sponsored label at the top of the ad" [KB-SOCIAL-036] (official, Meta Help Center, "How AI-generated
images in ads are identified and labeled on Meta," retrieved 2026-09-27:
https://www.meta.com/help/artificial-intelligence/355108217670024/). It labels ad images "created or
significantly edited using our generative AI creative features or ad images created or edited using
third-party AI tools" [KB-SOCIAL-037] (official, same source, retrieved 2026-09-27) — minor edits
like resizing or color correction are explicitly excluded from triggering it [KB-SOCIAL-038]
(official, same source, retrieved 2026-09-27).

**Organic (unpaid) content is a separate mechanism, per Meta's own words: "Labeling is different for
organic, or unpaid content"** [KB-SOCIAL-039] (official, same source, retrieved 2026-09-27). Meta's
own 2024 policy announcement states the label mechanism directly: "We will begin adding 'AI info'
labels to a wider range of video, audio and image content when we detect industry standard AI image
indicators or when people disclose that they're uploading AI-generated content" [KB-SOCIAL-040]
(official, Meta Newsroom, "Our Approach to Labeling AI-Generated Content and Manipulated Media,"
published April 2024, retrieved 2026-09-27:
https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/).
The label name itself changed from "Made with AI" to "AI info" in a July 1, 2024 update appended to
Meta's own April 2024 Newsroom post: "We're updating the 'Made with AI' label to 'AI info' across our
apps, which people can click for more information" [KB-SOCIAL-041] (official, Meta Newsroom, same
source as KB-SOCIAL-040 — the rename appears as a dated update within that same post — re-fetched and
confirmed 2026-09-27:
https://about.fb.com/news/2024/04/metas-approach-to-labeling-ai-generated-content-and-manipulated-media/).

## The detection mechanism

Meta's own February 2024 announcement states the mechanism plainly: Meta uses "industry standard AI
image indicators" — in practice, C2PA (Coalition for Content Provenance and Authenticity) Content
Credentials and the related IPTC metadata fields that AI generation tools embed directly into the
image file — to detect and label AI-generated images across Facebook, Instagram, and Threads
[KB-SOCIAL-042] (official, Meta Newsroom, "Labeling AI-Generated Images on Facebook, Instagram and
Threads," published February 2024, retrieved 2026-09-27:
https://about.fb.com/news/2024/02/labeling-ai-generated-images-on-facebook-instagram-and-threads/).
Metadata (C2PA/IPTC provenance) is the documented primary signal for images, and it is
**necessary but not sufficient to reason about** — Meta's own words describe more than a pure
metadata read: the same February 2024 post states Meta is "building classifiers to help us
proactively detect AI-generated content, even where that content lacks invisible markers"
[KB-SOCIAL-042] (official, same source, retrieved 2026-09-27), i.e. Meta itself says a metadata-free
image can still be flagged once such classifiers are in production. A clean metadata check
(`strings <file> | grep -ci 'TrainedAlgorithmicMedia\|jumdc2pa\|c2pa'` below) is therefore a reliable
way to know a file **carries** the documented marker-based trigger — and stripping it removes that
specific trigger — but it is not a guarantee the platform's other detection paths (marker-free
classifiers on images; YouTube's own content-analysis systems, see below) will never flag the same
file. Tools whose generative-fill/upscale/background-removal features embed C2PA data into an
otherwise genuine photo carry the documented metadata trigger too — the file's provenance chain, not
the photo's origin story, is what the metadata check reads.

**Operational consequence for any GTM engagement, company-agnostic — disclosure, not evasion, is the
default posture:** per `ANTI-PATTERNS.md` #4 and #10, whether and how a company handles AI-provenance
metadata is that company's own ruling (see the company's own pack/dossier), never a runtime mandate to
strip it. The doctrine this file supports is: (a) **content that is genuinely a real capture** (a real
photo/video) whose provenance metadata was incidentally added by an editing step (a one-click
"enhance," a generative-fill touch-up) is a candidate for metadata sanitization before publish, because
the underlying content is not synthetic and nothing is being concealed about the actual work shown;
(b) **content that is fully AI-generated, or realistically altered** (a fabricated scene, a synthetic
person/voice, a materially altered real event) must be **disclosed**, never stripped to avoid a
label — YouTube's altered-or-synthetic-content toggle (below) and Meta's own AI-disclosure options are
the sanctioned mechanism, consistent with both platforms' own policies. Stripping metadata specifically
to defeat detection on genuinely synthetic/realistic content is the anti-pattern `ANTI-PATTERNS.md` #4
names, not a company-agnostic best practice. `(internal doctrine)`: the mechanical
`strings <file> | grep -ci 'TrainedAlgorithmicMedia\|jumdc2pa\|c2pa'` check (or reading the file's C2PA
manifest directly) is how any company confirms whether a given file currently carries this
provenance — a purely diagnostic check, not itself a sanctioning of stripping.

## Does the label suppress reach? — mixed evidence, do not overstate either direction

Meta's own April 2024 policy statement, in its own words: "we will keep this content on our
platforms so we can add informational labels and context, unless the content otherwise violates our
policies" [KB-SOCIAL-043] (official, same Newsroom source as KB-SOCIAL-040, retrieved 2026-09-27) —
i.e., the label itself is not stated by Meta as a ranking demotion mechanism; it is a disclosure
mechanism layered on top of whatever the content's normal ranking would be. **This does not mean the
label is reach-neutral in practice** — a labeled post is a trust signal a human viewer reacts to
independent of any algorithmic effect, and that reaction (fewer comments/shares/saves — the actual
named ranking inputs in `meta-organic-formats-and-ranking.md`) can suppress a labeled post's reach
indirectly even if Meta's ranking system applies no explicit penalty for the label itself. **Do not
claim "labeling costs reach" as an algorithmic fact** — no primary source located in this pass states
that; the honest claim is narrower: labeling is a disclosure Meta commits to keep visible while
leaving normal ranking signals (which a labeled, visibly-synthetic post may perform worse on with a
skeptical audience) otherwise in force.

**For a home-services or B2B-software brand specifically, the practical risk is not the algorithm —
it is the buyer.** `shared/contractor-buyer-psychology.md` and `shared/homeowner-buyer-psychology.md`
both establish that this audience is primed to distrust software/marketing claims; a visible "AI
info" label on what was presented as a real project photo or a real testimonial is a credibility
event with this specific buyer regardless of what Meta's ranking system does with it.

## YouTube's altered-or-synthetic-content disclosure — a creator-toggle policy, distinct from Meta's metadata read

YouTube requires creators to disclose, via a toggle in YouTube Studio at upload, when a video
contains realistic AI-altered or -generated content that could be mistaken for something real.
YouTube's own policy names three trigger conditions: content that "makes a real person appear to say
or do something they didn't do," "alters footage of a real event or place," or "generates a realistic
scene that didn't actually occur" [KB-SOCIAL-044] (official, YouTube Help Center, "Disclosing
altered or synthetic content" policy, retrieved 2026-09-27:
https://support.google.com/youtube/answer/14328491) — and applies to content "fully or partially
altered or created using AI tools" [KB-SOCIAL-045] (official, same source, retrieved 2026-09-27).

**What is exempt — production-assistance uses do not require disclosure:** beauty filters, color
adjustment, voice cloning of the creator's own voice for their own voiceover, auto-caption
generation, and "production assistance, like using generative AI tools to create or improve a video
outline, script, thumbnail, title, or infographic" [KB-SOCIAL-046] (official, same source, retrieved
2026-09-27). **Operational read: an AI-written video script or an AI-generated thumbnail concept does
NOT require the toggle; a video that shows a fabricated realistic scene, or synthetically alters a
real person's words, does.**

**The "Made with AI" label** appears on video when a creator manually discloses via the toggle, when
YouTube's own generative tools (e.g. DreamScreen) were used, or when the uploaded file itself carries
valid C2PA 2.1+ Content Credentials data showing the video was AI-made [KB-SOCIAL-047] (official,
YouTube Help Center, "Understanding 'How this content was made' disclosures on YouTube," retrieved
2026-09-27: https://support.google.com/youtube/answer/15447836). **YouTube can and does apply the
label itself, proactively, on undisclosed content it detects as AI-altered — and a creator cannot
remove a label YouTube applied this way** [KB-SOCIAL-048] (official, same source, retrieved
2026-09-27) — this is the same "detection is not optional even if you don't self-disclose" mechanism
as Meta's C2PA read, via a different technical path (YouTube's own content-analysis systems plus the
same C2PA standard, rather than Meta's metadata-only read).

**Enforcement:** "Creators who consistently choose not to disclose this information may be subject to
manual application of a label, or penalties from YouTube, including removal of content or suspension
from the YouTube Partner Program" [KB-SOCIAL-049] (official, same source as KB-SOCIAL-044, retrieved
2026-09-27). YouTube explicitly states honest disclosure itself does not hurt distribution or
monetization eligibility [KB-SOCIAL-050] (official, same source, retrieved 2026-09-27) — the penalty
is for *non-disclosure of qualifying content*, not for the content being AI-assisted per se.

## Anti-pattern this file exists to name directly

**Never assume a video/image is "safe" because it looks real to a human reviewer.** Both platforms'
documented detection paths start from metadata/provenance and creator-declared signals, not a visual
Turing test — a photorealistic AI image with intact C2PA data is labeled regardless of how convincing
it looks, and a genuine camera photo that passed through one AI-assisted editing step (a one-click
"enhance," a generative-fill touch-up) can pick up the same provenance and get labeled even though
the underlying photo is real. **Reading the file's own metadata before publish is the mechanical
floor, not a guarantee** (`strings <file> | grep -ci 'TrainedAlgorithmicMedia\|jumdc2pa\|c2pa'` for
Meta-relevant provenance, or the file's C2PA manifest directly) — it tells you whether the documented
marker-based trigger is present, never whether a marker-free classifier (Meta says it is building
these) or YouTube's own content-analysis systems will independently flag the file. Treat a clean
metadata check as diagnostic — it rules out the known, checkable trigger — never as proof the file
cannot be labeled by some other mechanism; see the company's own pack/dossier for any additional
company-specific gate built on top of it.

## Contractor bend

A small owner-operated home-services business's own social account is exactly the account most likely to publish something
AI-touched by accident — a homeowner-provided "after" photo that was run through a phone's built-in
AI enhance feature, a stock "inspiration" image pulled from a design tool that embeds C2PA data by
default, a quick AI-cleaned photo from a design app. This buyer has no marketing/legal team checking
provenance before posting. The operational floor for this buyer: treat every image/video that passed
through *any* app fancier than the phone's native camera roll as suspect, and run the metadata check
above before it goes on the business's own Instagram, Facebook, or YouTube account — a labeled post
on a contractor's own page is a worse trust hit for this buyer's own customers than for a SaaS brand,
because a homeowner hiring a GC is explicitly buying trust in real, physical craftsmanship — a "this
was AI" label undercuts the entire pitch.
