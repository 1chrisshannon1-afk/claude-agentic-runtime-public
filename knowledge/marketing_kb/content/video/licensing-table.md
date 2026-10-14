# Licensing Table — Voice, Music, Photos

Which voice, music, and photo sources are commercially safe to use in a demo or marketing video,
which are legally risky, and the exact citation for each verified fact. Read this before sourcing
any asset for a video, not after.

## 1. What this table covers

**(internal doctrine — mechanism):** the verified licensing verdicts below — what voice/music/photo
sources are commercially safe (Pexels, Pixabay Content License, Apache-2.0 Kokoro, paid-tier
ElevenLabs) and which are not (free-tier ElevenLabs, edge-tts, YouTube Audio Library off-platform).
This mechanism is portable across companies; a given company's own choice of voice/music/photo
asset (which specific voice, which specific track) is that company's own fact — see its own
pack/dossier for its current asset choices and licenses.

## 2. Voice (text-to-speech)

| Source | Verdict | Why | Citation |
|---|---|---|---|
| **Google Cloud Text-to-Speech (Chirp3-HD voices)** | SAFE — Google Cloud Text-to-Speech output, billed as ordinary cloud usage under the account's Google Cloud terms | Billed as ordinary cloud infra, not a separate licensing question. Which specific voice a company picks is a company choice (see the company's own pack/dossier for its current voice pick and how it was chosen, e.g. an A/B test across several free options). | (internal doctrine — mechanism; re-derive and cite Google Cloud's service terms if a dated primary source is needed) |
| **ElevenLabs, paid tier (Starter, ~$5-6/mo)** | **SAFE (internal doctrine, verified 2026-09-05 — re-verify before a new asset)** | An internal review found paid-tier commercial use permitted. Verified once already; re-verify against ElevenLabs' current ToS (`elevenlabs.io/terms` or equivalent) with a fresh retrieval date before relying on this for a new asset. | (internal doctrine, verified 2026-09-05 — no dated primary-source URL on file for that verification; re-derive and cite a URL + retrieval date at time of use) |
| **ElevenLabs, FREE tier** | **REJECTED (internal doctrine, verified 2026-09-05 — re-verify before a new asset)** | An internal review found the free tier's terms did not extend to commercial output. Treat as unsafe for commercial video (the same REJECTED posture as edge-tts, §5's fallback rule) until re-verified against a dated primary source. | (internal doctrine, verified 2026-09-05 — no dated primary-source URL on file for that verification; re-derive and cite a URL + retrieval date at time of use) |
| **Kokoro-82M** | SAFE — genuinely open | Apache-2.0 licensed, no attribution or commercial restriction. | Apache-2.0 license text, per the model card at `huggingface.co/hexgrad/Kokoro-82M` (`license: apache-2.0` in the card's metadata) — re-verify against the live model card and record a fresh retrieval date before relying on this for a new company's asset pipeline; no retrieval date is on file for this table's original entry |
| **edge-tts** (Microsoft Edge's TTS API, unofficial wrapper) | **REJECTED** — ToS-gray | Not an outright ban, but treat as unsafe for commercial video on ToS-ambiguity grounds rather than risk it, unless a future legal review reverses that call. | (internal doctrine — mechanism) |

**Delivery note (internal doctrine):** ~130-150 WPM reads right for demo narration pacing.

## 3. Music

| Source | Verdict | Why | Citation |
|---|---|---|---|
| **Pixabay Content License tracks** | SAFE — free for commercial use, no attribution required | Pixabay's own Content License terms (free for commercial use, no attribution) — see the company's own pack/dossier for the specific track(s) it uses and their license lines. | Pixabay Content License (pixabay.com/service/license-summary/) |
| **YouTube Audio Library, used OFF-PLATFORM** | **BANNED** in this context | YouTube's Audio Library license generally covers use *within* YouTube-hosted content; using those tracks in a video distributed elsewhere (site embed, sales deck, ad) is outside what the library's terms grant. | (internal doctrine — this is a category-level caution, not a claim about every individual track's terms; if a specific track's own license page grants broader rights, that page controls, but verify before assuming.) |

**Sourcing/attribution rule (internal doctrine — mechanism):** never commit a track without its
license line recorded in the same change. Port this mechanism directly: any new music asset gets
its license line written down in the same commit that adds the file, not after — see the company's
own pack/dossier for its own asset/license record.

## 4. Photos

| Source | Verdict | Why | Citation |
|---|---|---|---|
| **Pexels** | SAFE — free for commercial use, no attribution required | Pexels License terms (free for commercial use, no attribution required) confirmed directly. See the company's own pack/dossier for which photos it has sourced this way. | Pexels License (pexels.com/license/) |

**EXIF-strip practice (internal doctrine — mandatory):** every sourced photo should be re-saved
with EXIF/metadata stripped before use. This is a privacy/provenance hygiene step, not a licensing
requirement per se, but it travels with every photo asset regardless of source and should be
treated as non-optional: a stock photo's EXIF can carry the original photographer's GPS/device
metadata, which has no business riding along in shipped marketing material.

## 5. The pattern underneath the table

Every SAFE verdict above rests on a **specific, checkable license grant** (Pexels License, Pixabay
Content License, Apache-2.0, a paid ToS tier, once re-verified) — never on "it's probably fine" or
"everyone uses this." Every BANNED/REJECTED verdict rests on either an explicit tier restriction
(ElevenLabs free tier — internal doctrine, verified 2026-09-05, REJECTED) or a scope mismatch
between what the license covers and how the asset would actually be used (YouTube Audio Library
off-platform, edge-tts's ToS ambiguity). When sourcing a NEW asset not on
this table:

1. Find the license page for the specific asset (not the platform's general reputation).
2. Confirm it covers **commercial use** and the **specific distribution channel** intended (a site
   embed and a paid ad placement are not always covered by the same grant).
3. Record the license line in the same commit/change that adds the asset — never after.
4. If the license terms are ambiguous or you cannot find them, treat it as REJECTED, the same
   posture the pipeline took with edge-tts — do not guess a permissive interpretation.

## 6. Per-vertical bend (for companies selling to contractors/trades)

None of this table changes for a contractor buyer — a licensing violation is exactly as legally
risky whether the video is aimed at a working residential GC or a Fortune 500 buyer, and this buyer
will never see or care about the sourcing table itself. What *does* change is the cost of getting
caught: this buyer already assumes software companies cut corners ("burned by software before" —
see `../voice-and-vocabulary.md`'s contractor buyer framing), so any authenticity gap the buyer CAN
perceive — a voice that sounds like a robotic free-tier TTS demo, stock b-roll that looks like
generic corporate stock rather than an actual trade job site — reads as one more reason not to
trust the product. Paying for real TTS/quality-tier voice and sourcing real trade-relevant photos
(a genuine dated bathroom or job site, not a staged office) is not just a licensing-safety choice,
it is also the credibility choice for this specific audience.
