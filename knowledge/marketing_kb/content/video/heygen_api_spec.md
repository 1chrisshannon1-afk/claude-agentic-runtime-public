# HeyGen API — Implementer Spec (Photo Avatar + Own-Audio Lip-Sync Video)

Pinned implementer reference for the HeyGen `/v3` API: exact endpoints, field names, request/
response shapes, limits, and pricing for the photo-avatar + own-audio lip-sync pipeline. Retrieved
2026-09-09 directly from `https://developers.heygen.com/openapi/external-api.json` (103 paths) and
Mintlify doc pages under `developers.heygen.com`. Re-derive by re-fetching the OpenAPI spec URL
above and the doc pages cited in each section if this file is ever suspected stale — HeyGen's API
has already moved once (v1/v2 paths below are noted stale/superseded). Consumed by
`ai_talking_avatar_playbook.md`, which is the strategy/craft/cost layer above this file.

## 0. Terminology (UNVERIFIED→VERIFIED correction)

"Talking Photo" as a first-class resource is legacy. In the current API, uploading one portrait creates a **Photo Avatar** (`POST /v3/avatars` with `"type":"photo"`), which returns an avatar **look id** used everywhere as `avatar_id`. "Talking photo" now survives only as the `character_type: "talking_photo"` enum value inside the older Studio-scene composition path (source: `llms-full.txt` lines 17387-17388) — not the endpoint to use for this pipeline. **Avatar IV is the current default rendering engine and is what powers photo avatars today**; Avatar III is a distinct, older v3 engine tier; Avatar V is the highest-fidelity opt-in engine. (Source: `https://developers.heygen.com/avatar-iv.md`, `avatar-iii.md`, `avatar-v.md`, retrieved 2026-09-09.) **Major finding: HeyGen's public API has moved to `/v3/*` everywhere** — `/v1/talking_photo`, `/v1/asset`, `/v1/video_status.get`, and `/v2/photo_avatar/*`/`/v2/video/generate` are stale/superseded; `docs.heygen.com` now 404s/redirects into the same Mintlify site as `developers.heygen.com`.

## 1. Auth

Header: `x-api-key: YOUR_API_KEY` (OpenAPI `securitySchemes.ApiKeyAuth`, `in: header, name: x-api-key`). OAuth Bearer is a separate, alternate scheme for the CLI/MCP path — not relevant here. Base URL: `https://api.heygen.com` (docs subdomain is only `developers.heygen.com`/`docs.heygen.com`).
Source: `openapi.json` `components.securitySchemes`, retrieved 2026-09-09.

## 2. Upload the portrait PNG (and later the audio) — `POST /v3/assets`

- Method/path: `POST /v3/assets`
- Headers: `x-api-key: <key>`; multipart form, `Content-Type: multipart/form-data` (curl `-F`)
- Body (multipart field): `file` — binary, required. Max 32 MB. Supported: png, jpeg, mp4, webm, mp3, wav, pdf, srt.
- Response `data`: `asset_id` (string), `url` (string, public URL), `mime_type` (string), `size_bytes` (integer). All four required in schema.
- For files >32MB use the direct-upload flow instead: `POST /v3/assets/direct-uploads` (presign) → PUT bytes → `POST /v3/assets/{asset_id}/complete` (finalize). Not needed for a PNG portrait or a WAV/MP3 under 32MB/50MB (see §6 limits — note a size discrepancy below).

Source: `openapi.json` `paths./v3/assets.post`, retrieved 2026-09-09.

```bash
curl -X POST "https://api.heygen.com/v3/assets" \
  -H "x-api-key: $HEYGEN_API_KEY" \
  -F "file=@portrait.png"
```

## 3. Create the Photo Avatar (once, reusable id) — `POST /v3/avatars`

- Method/path: `POST /v3/avatars`
- Headers: `x-api-key`, `Content-Type: application/json`
- Body (discriminated union on `type`), for the photo case — **required fields: `type`, `name`, `file`**:
```json
{
  "type": "photo",
  "name": "Sarah — Marketing",
  "file": { "type": "asset_id", "asset_id": "YOUR_IMAGE_ASSET_ID" },
  "avatar_group_id": null
}
```
  - `file` is itself a discriminated union: `{"type":"url","url":"..."}`, `{"type":"asset_id","asset_id":"..."}`, or `{"type":"base64","media_type":"image/png","data":"..."}`.
  - `avatar_group_id` (optional, nullable): attach to an existing identity group; omit to create a new one.
- Response `data.avatar_item.id` — **this is the stable, reusable `avatar_id`** to pass to `POST /v3/videos` forever (this is the "look" id, per the schema description: "Unique look identifier. Pass this as avatar_id to POST /v3/videos"). Also returns `avatar_item.avatar_type` (`photo_avatar` for this case), `group_id`, `preview_image_url`.

Source: `openapi.json` `paths./v3/avatars.post` (resolved schema), and `https://developers.heygen.com/photo-avatar.md`, both retrieved 2026-09-09.

```bash
curl -X POST "https://api.heygen.com/v3/avatars" \
  -H "x-api-key: $HEYGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type":"photo","name":"Sarah — Marketing","file":{"type":"asset_id","asset_id":"RETURNED_ASSET_ID"}}'
```

## 4. Generate video lip-synced to YOUR audio — `POST /v3/videos`

This is a **discriminated union** on top-level `type` (`avatar` | `image` | `cinematic_avatar` | `studio`). Use `type: "avatar"`. Do **not** pass `script`/`voice_id` — `audio_url`/`audio_asset_id` are explicitly documented as "Mutually exclusive with script."

- Method/path: `POST /v3/videos`
- Headers: `x-api-key`, `Content-Type: application/json`
- Required body fields for the `avatar` branch: `type` (const `"avatar"`), `avatar_id`.
- Exact field names for own-audio lip-sync (confirmed against both the OpenAPI schema and the dedicated "Audio to Video" doc page):

| Field | Type | Notes |
|---|---|---|
| `type` | string | `"avatar"` |
| `avatar_id` | string | Your Photo Avatar look id from step 3 |
| `audio_url` | string, nullable | Public HTTPS URL of audio; mutually exclusive with `script` and with `audio_asset_id` (pass exactly one) |
| `audio_asset_id` | string, nullable | Asset id of uploaded audio (from `POST /v3/assets`); mutually exclusive with `script`/`audio_url` |
| `resolution` | enum, nullable | `"4k"` \| `"1080p"` \| `"720p"` |
| `aspect_ratio` | enum, default `"16:9"` | `"16:9"` \| `"9:16"` \| `"4:5"` \| `"5:4"` \| `"1:1"` \| `"auto"` |
| `fit` | enum, nullable | `"cover"` \| `"contain"` — how avatar fills canvas |
| `background` | object, nullable | `{"type":"color","value":"#RRGGBB"}` (color) or `{"type":"image","url"|"asset_id":...}` |
| `remove_background` | boolean, nullable | Avatar must be trained with matting to work |
| `output_format` | enum | `"mp4"` (default) \| `"webm"` (alpha-channel transparent) |
| `engine` | object, nullable | Defaults to Avatar IV when omitted. `{"type":"avatar_iv"}` explicit, or `{"type":"avatar_v"}` if the look's `supported_api_engines` allows it, or `{"type":"avatar_iii"}` |
| `motion_prompt` | string, nullable | Body-motion/gesture control; supported for photo avatars on either engine |
| `expressiveness` | enum, nullable | `"high"`\|`"medium"`\|`"low"` (default `"low"`), photo avatars only, Avatar IV only (rejected on `avatar_v`) |
| `title` | string, nullable | Dashboard display name |
| `folder_id` | string, nullable | Destination workspace folder |
| `callback_url` / `callback_id` | string, nullable | Webhook instead of polling |
| `caption` | object, nullable | `{"file_format":..., "style":...}` — sidecar SRT always generated via `subtitle_url`; `style` also burns captions in |

**Resolution/dimension mapping for a fixed 9:16/16:9 spec:**
- 1080×1920 (portrait) → `"resolution": "1080p", "aspect_ratio": "9:16"`
- 1920×1080 (landscape) → `"resolution": "1080p", "aspect_ratio": "16:9"`
- (`aspect_ratio: "auto"` derives dimensions from source and is NOT what you want when exact fixed dimensions are wanted both ways — use explicit `9:16`/`16:9`.)

**Example solid-color background:**
```json
"background": { "type": "color", "value": "#RRGGBB" }
```

**Transparent background:** set `"output_format": "webm"` — this automatically applies background removal and rejects/is mutually exclusive with the `background` field in the same request (per the dedicated Transparent Background Videos doc). **UNVERIFIED**: that doc's matting-prerequisite warning is phrased around "video avatar" (digital twin/studio avatar) training; whether a **photo avatar** look supports matting/webm transparency by default is not explicitly confirmed on any page retrieved — test this in a sandbox call before relying on it, or use green-background color (`"background":{"type":"color","value":"#00FF00"}`) as the safer alternative for chroma-key compositing.

Example request (avatar + own audio + a solid-color background + 1080p landscape):
```bash
curl -X POST "https://api.heygen.com/v3/videos" \
  -H "x-api-key: $HEYGEN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "avatar",
    "avatar_id": "YOUR_PHOTO_AVATAR_LOOK_ID",
    "audio_asset_id": "YOUR_AUDIO_ASSET_ID",
    "resolution": "1080p",
    "aspect_ratio": "16:9",
    "background": { "type": "color", "value": "#RRGGBB" },
    "title": "Own-audio lip-sync"
  }'
```

**Response (200)** — schema `CreateAvatarVideoResponse`, required `video_id`, `status`:
```json
{ "data": { "video_id": "v_abc123def456", "status": "waiting", "output_format": "mp4" } }
```
Note: the initial status example given is `"waiting"` in this response; the polling status enum (§5) is a different, narrower set — treat `waiting` as effectively equivalent to `pending`.

**Error responses documented in the OpenAPI spec for this endpoint:** `400` (with `error.code`, e.g. `invalid_parameter`; `error.param`; `error.errors[]` for batch/graph cases), `401`, `429`, `409`. Same envelope shape for all.

Source: `openapi.json` `paths./v3/videos.post` (resolved schema, full property dump), and `https://developers.heygen.com/generate-avatar-video.md` (Audio to Video section, lines ~370-540 of `llms-full.txt`), both retrieved 2026-09-09.

## 5. Poll status and download — `GET /v3/videos/{video_id}`

- Method/path: `GET /v3/videos/{video_id}`
- Headers: `x-api-key`
- Response `data` fields (from resolved OpenAPI schema): `id` (⚠ **note: field is `id`, not `video_id`**, differing from the docs' own sample Python code which reads `data["video_id"]` inconsistently in one place — trust the schema: `id`), `title`, `status`, `created_at` (unix ts), `completed_at` (unix ts, nullable), `video_url` (nullable — presigned download URL), `thumbnail_url`, `gif_url`, `captioned_video_url`, `subtitle_url`, `duration` (seconds, number), `failure_message` (string, nullable, only when `status=failed`), `failure_code` (string, nullable, only when `status=failed`).
- **Status enum (authoritative, from schema): `pending`, `processing`, `completed`, `failed`.** (This differs from the doc-page table which lists `pending`/`processing`/`completed`/`failed` too — consistent — but the initial POST response example showed `"waiting"`, which is not in this enum; treat `waiting` as a very-early pre-`pending` sub-state, or as the doc's informal phrasing — **flagged as a minor inconsistency between the POST example and the GET schema enum**.)
- Poll loop pattern (from official Python example): sleep 10s between polls; stop on `completed` (read `video_url`) or `failed` (read `failure_message`/`failure_code`).
- **Typical render time:** not stated as a fixed number anywhere retrieved in the official docs pulled (a dedicated "HeyGen Video Processing Times" help-center article exists at `help.heygen.com` but was not fetched — **UNVERIFIED**, out of fetch budget; do not assume a number).

```bash
curl -X GET "https://api.heygen.com/v3/videos/YOUR_VIDEO_ID" -H "x-api-key: $HEYGEN_API_KEY"
```

Then download `data.video_url` (a presigned URL, e.g. `https://files.heygen.ai/video/abc123.mp4`) with a plain GET/curl.

Source: `openapi.json` `paths./v3/videos/{video_id}.get` (resolved schema) and `https://developers.heygen.com/photo-avatar.md` polling table, both retrieved 2026-09-09.

## 6. Limits

From `https://developers.heygen.com/docs/usage-limits.md` (retrieved 2026-09-09):

| Limit | Value |
|---|---|
| Max concurrent video jobs (Pay-As-You-Go plan) | 10 — exceeding returns `429` with `Retry-After` header |
| Video input to `/v3/videos` (URL resource) | MP4/WebM, max 100 MB, <2K resolution |
| Image input | JPG/PNG, max 50 MB, <2K resolution |
| **Audio input (as a resource URL to `/v3/videos`)** | WAV/MP3, **max 50 MB** |
| **Audio input length ("Avatar Input" section)** | **Maximum 10 minutes (600 seconds)** — ⚠ this directly **contradicts** the separate "Audio to Video" doc page's claim of "up to 30 minutes" per request (see the Output Video Specifications row below, which independently states 30 min/scene as the general cap). **Flagging both as found, unresolved which governs for the audio-lip-sync-on-photo-avatar case specifically** — treat 10 minutes as the conservative/safe number until confirmed with a real account. |
| Asset upload via `POST /v3/assets` | Max 32 MB (same cap for URL-provided files); larger → direct-upload flow, per-upload cap returned as `max_bytes` |
| Output frame rate | 25 fps for avatar videos |
| Output resolution | width & height each 128–4096px; default 1080p |
| Output aspect ratio (this section's own line) | states only "16:9 or 9:16" here, though the `/v3/videos` schema separately allows `4:5`/`5:4`/`1:1`/`auto` too — this "Output Video Specifications" list is likely just the two most common, not exhaustive/restrictive |
| Max scenes (Studio, not relevant here) | 50 |
| Max duration per scene | 30 minutes; for `avatar`/`image` type (single scene) this is also the whole-video cap |

Rate limiting: all endpoints enforce limits; `429` returns `Retry-After` header (seconds to wait). No specific requests-per-minute number was stated on this page for `/v3/videos` itself (a `30 requests/minute per workspace member` figure exists elsewhere in the docs but that was for TTS synthesis, not video generation — do not conflate).

## 7. Pricing (per-second, this exact path)

**Source: official HeyGen Help Center article "HeyGen API Pricing Explained"**, `https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained`, **`lastUpdatedDate` field = 2026-06-09** per the page's own metadata, retrieved via WebFetch 2026-09-09:

- General rule: **$1 USD = 1 minute of generated avatar video in 720p or 1080p (standard generation)** → **$0.01667/sec**
- **Avatar IV specifically: $4 per 1 minute of 1080p output → $0.0667/sec** — this is the engine that powers the photo-avatar pipeline (Avatar IV is the current default engine for photo avatars, per §0).
- Video translation: $2/minute translated (not relevant to this pipeline)
- Video Agent (prompt-driven, not what this pipeline uses): $2/minute of prompted video

**Cross-check (third-party, UNVERIFIED against official source but directionally consistent):** WebSearch aggregation reported "$0.0667/sec (premium fidelity)" and "Avatar V API rate is $0.05/sec" and "cheapest avatar video $0.0167/sec (Avatar III Digital Twin)" — the $0.0667/sec figure matches the official Avatar IV rate exactly, which corroborates it; the Avatar III/$0.0167 figure aligns with the official "$1/min standard" rule. Treat these third-party numbers ([eesel.ai](https://www.eesel.ai/blog/heygen-pricing), [g2.com](https://www.g2.com/articles/heygen-api-pricing), [realtimeavatar.ai](https://realtimeavatar.ai/blog/heygen-api-pricing-explained)) as **UNVERIFIED supplementary color only** — the two boldfaced numbers above (from help.heygen.com directly) are the only ones to rely on.

**Not found / UNVERIFIED:** a more detailed official per-operation cost breakdown page is referenced by the help article ("developers.heygen.com/docs/pricing") but that page **returns HTTP 404** as of retrieval — it appears to have been retired/moved without the internal link being updated. Its replacement could not be located within fetch budget. **Recommend checking `app.heygen.com/developers/usage` directly (requires login) or contacting HeyGen support for a binding rate, since this is billing-critical and the only live confirmation is the $4/min Avatar IV figure from the help article.**

## 8. Full pipeline pseudocode (field names as-verified)

```python
# 1. Upload portrait
img_asset = POST /v3/assets  (multipart file=portrait.png)  -> data.asset_id

# 2. Create Photo Avatar (ONE TIME — save avatar_id forever)
avatar = POST /v3/avatars
  {"type":"photo","name":"...","file":{"type":"asset_id","asset_id":img_asset.asset_id}}
  -> data.avatar_item.id   # this is the reusable avatar_id

# 3. Upload your own narration audio (WAV/MP3, <=32MB via /v3/assets, <=50MB if hosted at a public URL instead)
audio_asset = POST /v3/assets  (multipart file=narration.wav) -> data.asset_id

# 4. Generate video, per orientation, with your own audio (no script/voice_id/TTS)
video = POST /v3/videos
  {
    "type": "avatar",
    "avatar_id": avatar_id,
    "audio_asset_id": audio_asset.asset_id,
    "resolution": "1080p",
    "aspect_ratio": "9:16" | "16:9",
    "background": {"type":"color","value":"#RRGGBB"}
  }
  -> data.video_id, data.status ("waiting")

# 5. Poll
while True:
  v = GET /v3/videos/{video_id} -> data.status in {pending, processing, completed, failed}
  if completed: download data.video_url  # break
  if failed: read data.failure_message / data.failure_code  # break
  sleep(10)
```

## Sources (all retrieved 2026-09-09)

- [OpenAPI spec (live, direct)](https://developers.heygen.com/openapi/external-api.json) — authoritative field names/types/required-ness for every endpoint above
- [Photo Avatar guide](https://developers.heygen.com/photo-avatar.md)
- [Audio to Video guide](https://developers.heygen.com/generate-avatar-video.md) (contains the "Audio to Video" section — own-audio lip-sync)
- [Photo to Video CLI recipe](https://developers.heygen.com/photo-to-video.md)
- [Avatar IV](https://developers.heygen.com/avatar-iv.md), [Avatar III](https://developers.heygen.com/avatar-iii.md) (index only), [Avatar V](https://developers.heygen.com/avatar-v.md) (header only)
- [Transparent Background Videos](https://developers.heygen.com/transparent-background-videos.md)
- [Usage Limits](https://developers.heygen.com/docs/usage-limits.md)
- [Error Codes](https://developers.heygen.com/docs/error-codes.md)
- [HeyGen API Pricing Explained (Help Center, official)](https://help.heygen.com/en/articles/10060327-heygen-api-pricing-explained) — `lastUpdatedDate` 2026-06-09
- Docs index: [llms.txt](https://developers.heygen.com/llms.txt), [llms-full.txt](https://developers.heygen.com/llms-full.txt)
- Photo avatar free-plan limits: [Photo Avatar Limits by Plan](https://help.heygen.com/en/articles/10034438-how-to-get-started-with-photo-avatars), retrieved 2026-09-09 by the reviewing pass (see `ai_talking_avatar_playbook.md` §4/§5 for the table)

## Explicitly UNVERIFIED / flagged conflicts

1. **Photo-avatar + webm/matting compatibility** — not explicitly confirmed for photo avatars specifically (the transparent-bg doc's language centers on "video avatar" training).
2. **Audio length limit conflict**: "10 minutes" (usage-limits.md, Avatar Input section) vs. "30 minutes" (Audio to Video doc, and the general Output Video Specifications 30-min/scene cap). Unresolved which applies to `audio_asset_id` lip-sync on a photo avatar.
3. **Typical render/processing time** — not found in the pages retrieved; a help-center article likely covers it but wasn't fetched (budget).
4. **`developers.heygen.com/docs/pricing`** — the "detailed per-operation cost breakdown" page the official help article links to returns 404; only the two headline rates ($1/min standard, $4/min Avatar IV) are confirmed.
5. **Field-name micro-inconsistency**: `GET /v3/videos/{id}` response schema names the id field `id`, while some doc-page sample code reads it as `video_id` — go by the OpenAPI schema (`id`).
