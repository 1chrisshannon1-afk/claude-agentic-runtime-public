# AI talking-avatar playbook — HeyGen vs Synthesia, and how to not waste credits

Grounds a GTM department's synthetic-persona talking-avatar work — a generated (not-a-real-person)
host, lip-synced to the company's own TTS narration WAVs (see the company's own pack/dossier for its
voice choice; no HeyGen/Synthesia TTS voice) — for YouTube Shorts (9:16) and 16:9 explainers.
Written per `brand/ANTI-PATTERNS.md` and `brand/brand-asset-usage.md` house style: every fact
carries a source URL + retrieval date; `UNVERIFIED` where a claim could not be confirmed against a
primary source. Reuses the pinned HeyGen v3 API contract ([`heygen_api_spec.md`](heygen_api_spec.md),
retrieved 2026-09-09) rather than re-deriving field names — that file is the implementer spec; this
file is the strategy/craft/cost layer above it.

## 1. HeyGen vs Synthesia for an AI-generated (not-a-real-person) persona — verdict first

**Verdict: Synthesia cannot be used for a synthetic-persona project of this shape. HeyGen can.**

Synthesia's Personal Avatar pipeline requires a **live, uncircumventable consent video of the
actual real person** who will appear as the avatar — the video cannot be uploaded (it must be
recorded live in-app), must show the same person as the reference footage, must include an
on-screen passcode, and identity mismatches are rejected. `docs.synthesia.io/docs/personal-avatars`
(retrieved 2026-09-09): *"Consent videos must be recorded live and cannot be uploaded. The person
in the consent video must be the same individual shown in the uploaded photo."* Synthesia's own
framing is unconditional: *"Synthesia will never create an AI avatar without your clear consent"*
(`synthesia.io/ethics`, retrieved 2026-09-09, via search aggregation). A generated portrait has no
real person who can sit for that live recording — there is no path through this flow for an
AI-generated face. Synthesia's **stock avatars** (pre-built, licensed) are a separate product from
Personal Avatars and are not a company's own persona — using one would mean the synthetic host is
literally a stock Synthesia actor, not the company's own generated identity, so it does not satisfy
the project's requirement either way. Synthesia's Acceptable Use Policy also separately restricts
stock-avatar use in paid social ads without written consent (`synthesia.io/legal/acceptable-use-policy`,
retrieved 2026-09-09, via search aggregation) — a further reason it doesn't fit a paid-media-adjacent
GTM asset even setting the consent-video blocker aside.

HeyGen's photo-avatar path accepts an **uploaded image** (`POST /v3/avatars` with
`file: {type: "asset_id"|"url"|"base64"}`, per the pinned API spec) with no live-recording
requirement gating creation. HeyGen's consent language, however, is written in terms of *real
people whose likeness is used*: *"AI generated avatars and videos depicting these avatars should
only be created or shared with expressed permission from those individuals,"* and *"Our Terms and
Acceptable Use policy requires users to demonstrate the expressed consent of the depicted person to
create a custom avatar"* (`heygen.com/ethics`, retrieved 2026-09-09, via search aggregation). A
community-forum thread titled exactly "CONSENT for create video and interactive avatar with
**artificial personas**" exists at HeyGen's own community site
(`community.heygen.com/.../consent-for-create-video-and-interactive-avatar-with-artificial-personas-gap4cubom7`)
— the URL text confirms HeyGen users have asked this exact question, but the thread itself
redirected (301) to a marketing page (`heygen.com/geniverse`) on fetch and could not be read
directly. **UNVERIFIED**: no HeyGen policy page explicitly states "an AI-generated portrait with no
real-world counterpart is permitted" in so many words — every consent clause found is phrased
around "the depicted person," which presupposes a person exists to consent. Because a fully
synthetic host depicts no real individual, there is no one whose consent could be withheld or
required, and nothing found prohibits uploading a synthetic portrait. This is the reading the
credit-safe test protocol (§4) is built to de-risk cheaply, not something to assume without
checking against a live account: **before spending real render credits, verify HeyGen's upload flow
accepts a fully synthetic portrait without a real-person identity-verification prompt** (some avatar
creation flows do include liveness/identity checks for certain avatar types — confirm which apply
to a plain photo avatar in-app, free tier, before committing API spend).

**Sources:** `docs.synthesia.io/docs/personal-avatars` (2026-09-09) · `synthesia.io/ethics`
(2026-09-09, via search) · `synthesia.io/legal/acceptable-use-policy` (2026-09-09, via search) ·
`heygen.com/ethics` (2026-09-09) · HeyGen community thread URL (2026-09-09, redirect only, content
UNVERIFIED) · pinned [`heygen_api_spec.md`](heygen_api_spec.md) §3 (2026-09-09).

## 2. HeyGen product map — what each piece actually is

| Term | What it is | Source |
|---|---|---|
| **Photo Avatar** | Created from one or more uploaded still images (`POST /v3/avatars`, `type:"photo"`). Returns a reusable `avatar_id` ("look id"). This is the synthetic host's path — no video/live-recording step. | pinned [`heygen_api_spec.md`](heygen_api_spec.md) §3 |
| **Digital Twin / Video Avatar** | Created from ≥2 minutes of recorded video of a real person, face continuously visible, uncovered. Distinct resource type from Photo Avatar; not applicable here (no real person). | `help.heygen.com/.../9964694-avatar-looks-explained` (2026-09-09) |
| **Avatar Groups / "identity"** | All Looks (visual variations — outfit/background/angle/pose) belonging to one avatar are consolidated under a single identity. *"Each avatar can now have up to 500 looks... all tied to the same identity."* All looks must feature the same person/persona who provided the original photo/consent — you cannot mix identities under one avatar. | `help.heygen.com/.../9964694-avatar-looks-explained` (2026-09-09) |
| **"Looks"** | Visual variations generated from a base Look via (a) a text prompt describing outfit/environment/styling/framing/mood changes, (b) reference images for additional visual guidance, or (c) a "Look Pack" — a predefined coordinated set (outfit+setting+pose). | same, (2026-09-09) |
| **Avatar III** | Older/base motion engine. Cheaper (~$1/min standard rate). | pinned [`heygen_api_spec.md`](heygen_api_spec.md) §0, §7 |
| **Avatar IV** | Current **default** engine for photo avatars; audio-to-expression diffusion-style engine — analyzes vocal tone/rhythm/emotion to drive facial motion, head movement, pauses, cadence from a single source image. $4/min. This is the engine a synthetic host typically uses. | `help.heygen.com/.../11269603-heygen-avatar-iv-complete-guide` (2026-09-09); pinned spec §0, §7 |
| **Avatar V** | Newest, highest-fidelity opt-in engine; only usable if the specific avatar look's `supported_api_engines` allows it. | pinned [`heygen_api_spec.md`](heygen_api_spec.md) §4; `help.heygen.com/.../14602974` (2026-09-09, index only) |

**"Training" a photo avatar group — what it actually means:** the phrase suggests a multi-photo
fine-tuning process, but for a plain **Photo Avatar** (as opposed to a Digital Twin/video avatar),
HeyGen's own "How to Get Started with Photo Avatars" article does **not** specify a required photo
count, camera-angle set, or lighting-variety requirement for the base upload — it only states
per-image content rules (below). `developers.heygen.com/docs/create-and-train-photo-avatar-groups`
(the originally-cited page) **returned HTTP 404 on fetch, 2026-09-09** — it may have been
renamed/retired under the same `/v3` doc restructuring the pinned API spec already found for other
endpoints. **UNVERIFIED**: the "Avatar Groups" multi-photo training workflow as a named, separate
feature could not be directly confirmed from a live doc page; treat "Avatar Group training" and
"generating new Looks from one uploaded portrait" as possibly the same underlying mechanism rather
than two different features, until confirmed in a live account.

**Per-image requirements confirmed** (`help.heygen.com/.../10034438-how-to-get-started-with-photo-avatars`,
2026-09-09): face close to human proportions; eyes clearly visible (normal size/placement); mouth
and lips visible for accurate lip-sync; recognizable face shape (forehead/cheeks/jaw distinct);
subject occupies a substantial portion of the frame (not too small). Avoid: very small/hard-to-detect
eyes, unclear/invisible lips, anything obscuring the mouth, overly stylized/exaggerated proportions.
Separately, from the Avatar Looks doc: for a *video-ready* look specifically, use half/upper-body
framing, face clearly visible, natural expression, hands in a neutral resting position (so they
adapt to any script) — and avoid poses implying lower-body motion (mid-step, on a bicycle), which
causes frozen/looping artifacts in the rendered video.

**How consistency across Looks is preserved:** select an existing Look as the base/reference when
generating a new one, and supply reference images for anything you need preserved precisely — per
the doc, *"whatever the AI cannot see in your references, it may need to invent."* This is the
mechanism behind §3's "one identity anchor image" rule below.

## 3. Getting the best results

**The one-identity-anchor-image rule (synthesized from §2's consistency mechanism, not a named
HeyGen feature):** pick ONE generated portrait as the canonical anchor for the synthetic host, save
it outside HeyGen as the ground truth, and generate every subsequent Look by referencing that same
anchor image (or a Look already derived from it) rather than re-generating a fresh portrait each
time. Every new generation is a new random draw on facial geometry even with an identical prompt —
consistency has to be enforced by reusing the SAME image/Look as the seed, not by prompting
similarly. This is the single highest-leverage practice for face consistency across every video
(internal doctrine — a company's own dossier may state this as its top production concern).

**Motion prompts (Avatar IV/V):** free-text, plain English, controlling facial expression, body
posture, hand gestures. Keep prompts to **under two short clauses** — HeyGen's own guidance is that
short prompts are more stable and small wording changes can swing output significantly.
(`help.heygen.com` Avatar IV/V best-results articles, 2026-09-09, via search.)

**Expressiveness setting:** Avatar IV/photo-avatar-only control, `"low"` (default) vs `"medium"` vs
`"high"` per the pinned API spec's `expressiveness` field. If output shows expressiveness artifacts
(exaggerated/uncanny motion), turn "More Expressive" off in Advanced Settings / drop to `"low"`.
(`help.heygen.com` Avatar IV best-practices, 2026-09-09, via search.)

**Common failure modes** (`help.heygen.com` Avatar IV/V guidance + Avatar Looks doc, 2026-09-09, via
search and direct fetch):
- **Hand/gesture artifacts** — more source footage/reference material helps *facial* expression
  range but does **not** automatically improve hand gestures; a gesture only appears reliably if it
  was clearly present in the reference material. Don't expect hand-waving from a still-portrait
  photo avatar with no such reference.
- **Head drift / frozen-loop artifacts** — poses implying lower-body motion (mid-stride, seated on
  a bicycle) in the source photo cause looping/frozen segments in the output video.
- **Accessory artifacts** — glasses, jewelry, watches, facial hair, and makeup are all allowed but
  "may sometimes create small visual artifacts" — worth a first cheap test render (§4 step 2) if
  the synthetic host's design includes any of these.
- **Lip-sync desync with music beds** — not directly documented for HeyGen; treat as a general
  cross-tool risk: mixing narration under a music bed before lip-sync generation risks the model
  reading music transients as speech cues. **Recommendation (not sourced to a HeyGen doc — general
  audio-video practice):** always render lip-sync against the clean narration WAV alone; add any
  music bed in a separate edit pass downstream of HeyGen, never bake it into the audio file HeyGen
  receives.

**Audio prep** — no HeyGen doc page found stating a required sample rate, silence-trim, or loudness
target for `audio_asset_id`/`audio_url` input; the pinned API spec's only confirmed audio
constraints are file type (WAV/MP3) and size ceiling (§6 below). **UNVERIFIED**: treat generic TTS
best practice as the safe default until a HeyGen-specific number is found — trim leading/trailing
silence from the narration WAV before upload (reduces wasted seconds at $4/min on Avatar IV), and
normalize loudness to a consistent target across all narration files so lip-sync timing behaves
consistently clip to clip.

**Aspect/fit/background:**
- 9:16 → `"resolution":"1080p","aspect_ratio":"9:16"`; 16:9 → `"resolution":"1080p","aspect_ratio":"16:9"`
  (pinned API spec §4 — use explicit values, not `"auto"`, since exact dimensions are wanted both ways).
- `fit`: `"cover"` or `"contain"` controls how the avatar fills the canvas — relevant when the same
  portrait crop needs to serve both a tall Short and a wide explainer without the head being cropped
  oddly; test both settings on the cheap validation render (§4 step 2) rather than guessing.
- `background`: solid color object `{"type":"color","value":"#RRGGBB"}` is the safe, cheap default.
  Transparent/webm output is **UNVERIFIED for photo avatars specifically** per the pinned spec
  (§4/"Explicitly UNVERIFIED" item 1) — if a transparent background is ever wanted for compositing,
  test it on the cheap validation render first rather than assuming it works, or use a chroma-key
  green solid color as the safer fallback.

## 4. Credit-safe test protocol — the actual money-saver

A common operator worry is burning credits on unusable renders. The fix is sequencing spend so
every dollar buys a real go/no-go signal before the next, larger dollar is spent.

| Step | What | Cost | Validates |
|---|---|---|---|
| **1. Free-tier look validation** | Upload the anchor portrait as a Photo Avatar in the **HeyGen app** (free plan, mobile or web). Generate one **10-second** Avatar IV video with any built-in voice — do NOT bother with the company's own audio yet, and stay inside the free plan's 30-seconds-of-Avatar-IV-video-per-month allowance (below) so a single validation render doesn't exhaust it. | **$0** — the Free [Mobile] and Free [Web] plans both allow **3 photo avatar slots** (VERIFIED, official table below); Avatar IV video is capped at **10 seconds per video, 30 seconds total per calendar month** on both free tiers. | Whether HeyGen even accepts the portrait as a valid photo avatar (face-proportion/visibility rules from §2), whether the face looks right at all, and surfaces any consent/identity-verification prompt (§1's open question) with zero spend. |
| **2. One short API render with the company's own WAV** | Via API (PAYG credits), one 10–15 second `POST /v3/videos` call using a trimmed clip of an actual TTS narration WAV, `audio_asset_id`, the current company's actual brand-color background value (see the company's own pack/dossier for its hex value), actual target `aspect_ratio`. | Avatar IV = $4/min → 10–15s ≈ **$0.67–$1.00** (per pinned spec §7's confirmed $4/min rate). | Real lip-sync quality against the company's own voice (not HeyGen's TTS), background/fit correctness, whether accessory or motion artifacts from §3 appear, and confirms the API pipeline (asset upload → avatar → video → poll) end to end on the pinned spec's exact field names. |
| **3. Full-length clips** | Only after step 2 passes review: render actual 60-second (or whatever the script calls for) clips at full resolution. | 60s × $4/min = **$4.00 per clip** (Avatar IV) — budget per video, not per attempt. | Production output. |

**Pre-flight checklist (run before every step-2/step-3 spend — this is the actual money-saver):**
- [ ] Anchor image confirmed as the single source for this Look (§3) — not a fresh generation for
      "just this one video."
- [ ] Face occupies a substantial portion of the frame; eyes, mouth, lips clearly visible (§2).
- [ ] No implied lower-body motion (mid-stride, seated-on-bicycle-style pose) in the source image (§2, §3).
- [ ] Narration WAV is the clean voice track only — no music bed mixed in yet (§3).
- [ ] Silence trimmed from WAV head/tail (§3, UNVERIFIED-but-recommended).
- [ ] Correct `aspect_ratio`/`resolution` pair for the actual target (9:16 Shorts vs 16:9 explainer) — not `"auto"` (§3).
- [ ] Background color/value matches brand token, not a placeholder (§3; see the company's own
      pack/dossier for its actual brand color values to use instead of guessing — method:
      `brand/color-and-contrast.md`).
- [ ] Motion prompt (if any) is ≤2 short clauses (§3).
- [ ] This is a NEW render, not a retry of an already-failed combination with one variable changed
      blindly — change one variable, re-derive expected effect from this doc's §3 guidance, then render.

## 5. Costs (official, dated)

| Item | Rate | Source | Retrieved |
|---|---|---|---|
| HeyGen standard avatar video (Avatar III / most engines) | **$1.00/min** ($0.01667/sec) | `help.heygen.com/en/articles/10060327-heygen-api-pricing-explained`, `lastUpdatedDate` 2026-06-09 | 2026-09-09 |
| HeyGen **Avatar IV** (typical synthetic-host engine) | **$4.00/min** ($0.0667/sec) | same | 2026-09-09 |
| HeyGen API pay-as-you-go top-up | Minimum **$5**; credits expire 12 months after purchase; no monthly commitment; standalone from subscription plans | search aggregation of HeyGen pricing-explainer articles (Anam, admakeai, others) citing HeyGen's own PAYG terms | 2026-09-09, UNVERIFIED against a primary HeyGen page directly (the linked `developers.heygen.com/docs/pricing` detail page 404s per the pinned API spec §7) — check the company's own pack/dossier for whether its own top-up amount is consistent with this minimum |
| HeyGen free API credits | **None since February 2026** — API access exists on the Free plan but requires funding the PAYG balance from $5; there is no free API allotment | same search aggregation | 2026-09-09, UNVERIFIED against primary source, consistent across multiple aggregator sources |
| HeyGen free plan, photo avatars (app, not API) — **official "Photo Avatar Limits by Plan" table** | **VERIFIED.** Photo Avatar Slots: **3** on both Free [Mobile] and Free [Web] (Unlimited on all paid plans). Training: **1/month** on Free [Mobile], **0** on Free [Web] (so avatar-group *training* needs a paid plan or API credits on web; a paid-plan/API equivalent is 60 credits). Looks Generations: **40 per calendar month** on both free tiers (1 = 1 credit on paid plans) — free, not blocked. Avatar IV Video: **10 seconds/video, 30 seconds/month total** on both free tiers (16 credits/min on paid plans). Watermark presence/exact resolution for free-tier renders is **not stated in this table** — do not assert a resolution or watermark rule beyond what §6's policy phrasing covers. | `help.heygen.com/en/articles/10034438-how-to-get-started-with-photo-avatars` | 2026-09-09, official primary source (reviewer-retrieved) — supersedes the prior aggregator-sourced row |
| Synthesia Basic (free) | $0/mo, 1,200 credits/mo ≈ 10 min video/mo, 9 stock avatars, **no Personal Avatars** | `synthesia.io/pricing` | 2026-09-09 |
| Synthesia Starter | $29/mo (or $18/mo billed annually), 10 min/mo, 125+ avatars, **no Personal Avatars** | same | 2026-09-09 |
| Synthesia Creator | $89/mo (or $64/mo annually), 30 min/mo, 180+ avatars, **5 Personal Avatars**, API access | same | 2026-09-09 |
| Synthesia Enterprise | Custom pricing, unlimited minutes, unlimited Personal Avatars | same | 2026-09-09 |

Note the Synthesia comparison is moot per §1's verdict (no path to a synthetic-persona Personal
Avatar regardless of tier) — included only so a company has the number if the calculus ever
changes (e.g., a real person stands in for the synthetic host on camera later).

## 6. Never claim or imply a synthetic host is a real practitioner or employee

- **Never claim or imply the synthetic host is a real person or a real employee.** The host is a
  synthetic, AI-generated persona narrating over the company's own real voice recordings — this is
  a fabricated-persona risk of exactly the shape `brand/brand-asset-usage.md` already flags for
  testimonial headshots (never pair an AI-generated face with a claim of a real identity/quote); the
  same logic applies here even without a "testimonial" framing. State plainly in any video
  description or on-screen text if disclosure is warranted for the platform/context.
- **FTC endorsement-rules fence.** If the synthetic host's on-screen delivery could be read as an
  endorsement or testimonial ("I used this and it changed my business") rather than neutral product
  narration, that crosses into FTC Endorsement Guides territory for a fabricated persona — keep the
  host's script in neutral-narrator/host voice, never first-person-customer-testimonial voice.
  (General FTC endorsement-guide principle — not a HeyGen/Synthesia-specific citation; a given
  company's own brief may treat this as a live constraint — check the company's own pack/dossier.)
- **Never publish a render that carries a HeyGen watermark.** Which exact plan tiers watermark
  output is not confirmed in the official Photo Avatar Limits table (§5) — the policy holds
  regardless of which tier turns out to apply it: any video destined for actual publication must
  come from protocol step 3 (a full, reviewed paid/PAYG render), never from step 1's free-tier
  validation clip, which is for internal look-validation only and must never ship. (Internal-measured
  observation, not a HeyGen policy citation — see the company's own pack/dossier for its own dated
  first-paid-render watermark check.)
- **Never let AI-generated on-screen "UI" or fake app text appear in a talking-avatar shot.** Mirrors
  `brand-asset-usage.md`'s existing photo-library rule (screens face away/out of focus, real UI
  composited in separately) — the same "garbled fake text reads as AI-generated" tell applies to any
  screen visible behind or near the synthetic host in a generated shot.

## 7. Layered assets — never regenerate an unchanged layer

**(internal doctrine — mechanism):** each layer of a composited video is its own independently
stored artifact — an avatar/talking-bust clip that is good should never need regenerating just
because a different layer (e.g. a background app-screen recording) turns out stale or broken.
Everything is stored separately and layered together only at final assembly, so no working
component is ever thrown away to fix a broken one. See the company's own pack/dossier for its own
verbatim operator ruling on this, where one exists.

**Layers, each its own artifact, each keyed by a hash of its own inputs:** avatar/talking-bust
clip · app screen recording · narration audio per scene · captions · music bed · thumbnail · end
card. Store every layer separately; composite only at the final post-production/assembly step —
never bake one layer into another upstream of that step. Regenerate a layer **only** when that
layer's own inputs change; every other layer is reused as-is. The assembly log for each posted
video must state, per layer, whether it was **reused** or **rebuilt**, so a broken layer's fix is
traceable without guessing what else moved.

**HeyGen clip specifically — cache key = `avatar look id + narration-audio sha256 + aspect +
background color`.** Honest consequence, stated plainly: re-narration changes the audio hash and
therefore *does* require a new avatar render — there is no way around that one. A re-recorded app
screen, new captions, a new music bed, or a new thumbnail do **not** touch this cache key and must
never trigger a HeyGen re-render.

## 8. HeyGen skills / CLI / MCP — evaluated 2026-09-09 (verdict: reference only)

Sources read: developers.heygen.com/skills/overview, /skills/install, /skills/heygen-{avatar,video,translate},
/cli, /mcp/overview, /reference/create-video, /models, /avatar-iv; the `heygen-com/skills` GitHub repo
(MIT, v3.2.0 @ 1bd5e4d, vendored read-only under `video/heygen_skills_ref/`).

**What they are.** A HeyGen "skill" is an agent SKILL.md package (three: `heygen-avatar`,
`heygen-video`, `heygen-translate`) whose workflows call HeyGen through the **CLI or the MCP server**.
`heygen-video` renders through the **Video Agent** (`create_video_agent`: prompt in → HeyGen's own
auto-editor picks avatar/voice/layout/b-roll/style) — a *different, less controllable* pipeline than
a direct `POST /v3/videos type=avatar` call made with a company's own narration WAV and one pinned
look. The CLI is a thin wrapper over the same v3 REST schema (`heygen video create -d '{json}'`, `--wait`,
`--request-schema`); `heygen auth login` **persists the API key in plaintext at `~/.heygen/credentials`**.
The MCP server is **remote** (`https://mcp.heygen.com/mcp/v1/`), OAuth-only — a HeyGen-hosted proxy,
never a company's own secrets-manager-held key (internal doctrine: never route a production API key
through a remote, OAuth-only proxy outside the company's own credential custody). The vendored
`heygen-video/SKILL.md:125` lists EXACTLY 14 MCP tools, by name:
`create_video_agent`, `get_video_agent_session`, `get_video`, `list_avatar_groups`,
`list_avatar_looks`, `get_avatar_look`, `create_photo_avatar`, `create_prompt_avatar`,
`create_digital_twin`, `list_voices`, `design_voice`, `create_speech`, `list_video_agent_styles`,
`create_video_translation` — no lipsync tool and no batch tool are in this list (`heygen lipsync
{create,get}` is a **CLI-only** command per the same vendored file, and the vendored
`heygen-video/references/troubleshooting.md:131` says explicitly "no MCP tool yet" for it; likewise
"batch" only appears as CLI translation-flag syntax, never an MCP tool name). No `create_lipsync`,
`clone_voice`, or `get_current_user` tool exists anywhere in the vendored tree (grepped, zero hits).
developers.heygen.com/mcp/overview (read 2026-09-09, not vendored, so its own tool count/names are
UNVERIFIED against a pinned source) described more than these 14 — treat anything beyond the vendored
list as UNVERIFIED, not fact.

**Verdict.** Keep a pinned REST client as the ONLY production path. Do not install the skills into
`~/.claude/skills/` (their workflows steer agents to the CLI/MCP and the Video Agent); do not install the
CLI (a plaintext key on disk breaks the never-persist-credentials principle — internal doctrine;
nothing it exposes is missing from REST); do not wire the MCP into the pipeline (remote proxy,
different trust/telemetry surface, OAuth rather than the company's own held key). A credit-balance
check is a `GET /v2/user/remaining_quota` read-only probe, run manually ad hoc (no MCP tool for this
is confirmed in the vendored list — a given company's own pipeline may or may not wire this in; see
its own pack/dossier). `heygen lipsync create` (CLI-only, no MCP equivalent per the vendored docs) to
re-dub an already-rendered clip, and `heygen-translate` for multi-language dubs, are the two narrow
manual uses that MAY be worth it later — via the CLI's `HEYGEN_API_KEY` env var scoped to a single
command, never `heygen auth login`.

**The quality levers that DO matter (all `POST /v3/videos` fields a caller controls):**
- `expressiveness` — `high|medium|low`, photo avatars, Avatar IV only. **Server default is `low`**
  when omitted; a company may choose its own non-default (e.g. `medium` baseline, `high` for a
  hook/CTA beat) — see the company's own pack/dossier/pipeline code for its own default and how it
  is wired per-scene. Whatever caching mechanism a company's pipeline uses, an all-default render
  should key identically to no-levers-set (so it never invalidates an already-paid-for clip), while
  a genuinely different lever value should change the cache key and force a re-render.
- `motion_prompt` — natural-language body/gesture control for photo avatars on Avatar IV
  (e.g. "subtle nods, hands still, stays centered"). Off by default; use sparingly — hands in frame are
  the classic artifact source. Also belongs in any render-cache key.
- `fit` — `contain` vs `cover` for the chosen `aspect_ratio` (omit = server auto). Also belongs in
  any render-cache key.
- `aspect_ratio` — set explicitly per output (`9:16` for Shorts band placement, `16:9` for the corner
  bust); `4:5`/`5:4`/`1:1`/`auto` exist.
- `caption` — `{file_format:"srt"}` returns a sidecar SRT; `style` burns captions in. If a company
  already burns its own captions in a downstream assembly step, leave this off (double captions
  otherwise).
- Engine: Avatar IV is the right engine for a **photo** avatar (Avatar III's 4K does not apply to photo
  avatars; Avatar V needs opt-in and its motion_prompt targets video avatars). 1080p is the ceiling.
- Transparent background: `output_format: "webm"` + a matting-capable avatar; rejects any `background`.

**Mechanism note:** a paid render (protocol step 2/3 above) should show no watermark; look id
resolves via `GET /v2/avatar_group.list` + `GET /v2/avatar_group/{id}/avatars` (the pinned v3 spec
has no list endpoint). See the company's own pack/dossier for its own first-paid-render numbers
(duration, wall time, cost) once it has run one.

## 9. Which seat owns this — proposed split, not a decision

Proposing (not deciding) a lane split for the operator/director to ratify: **`content-strategist`
owns talking-avatar script craft** — what the synthetic host says, pacing, motion-prompt wording as
it serves the script, and keeping delivery in neutral-narrator voice per §6's endorsement fence —
since script and voice-guide ownership already sits in that seat's lane per its dossier.
**`brand-architect` owns the look** — anchor-image selection and consistency discipline (§3),
background/aspect/fit choices as brand-surface decisions, and verdicting whether a given render
passes the "real company, not a template" bar before it ships, since visual-identity verdicts are
that seat's existing lane. Neither seat currently holds a HeyGen/Synthesia-specific dossier entry
naming this split explicitly — this file is the shared reference both would read, and the split
above is offered for the operator or `marketing-director` to confirm, amend, or reject.

---

**All sources, consolidated (retrieved 2026-09-09 unless noted):**
`docs.synthesia.io/docs/personal-avatars` · `synthesia.io/ethics` (via search) ·
`synthesia.io/legal/acceptable-use-policy` (via search) · `synthesia.io/pricing` ·
`heygen.com/ethics` · HeyGen community consent thread (URL only, content unread — redirected) ·
`help.heygen.com/en/articles/9964694-avatar-looks-explained` ·
`help.heygen.com/en/articles/10034438-how-to-get-started-with-photo-avatars` ·
`help.heygen.com/en/articles/11269603-heygen-avatar-iv-complete-guide` ·
`help.heygen.com/en/articles/10060327-heygen-api-pricing-explained` (official; this file's own §5
records this same page's `lastUpdatedDate` metadata field as 2026-06-09, while this consolidated
sources list separately says "last updated Apr 21 2026" — the two dates disagree and neither has
been re-checked against the live page since; treat both as unreliable until a fresh retrieval
confirms one) · HeyGen Avatar IV/V best-results guidance and free-plan/PAYG figures (via search aggregation
of multiple third-party pricing explainers, flagged UNVERIFIED where not confirmed against a HeyGen
primary page) · pinned [`heygen_api_spec.md`](heygen_api_spec.md) (retrieved 2026-09-09, reused per
task instruction). `developers.heygen.com/docs/create-and-train-photo-avatar-groups` was
requested but returned HTTP 404 on fetch — noted in §2 as unconfirmed/possibly retired.
