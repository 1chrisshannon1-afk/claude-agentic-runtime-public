# Claude Code — Notification Sounds (macOS)

Make your Mac speak a short word (or play a chime) when something in Claude Code needs
you — so you only look over when it matters, and you can tell *what* happened without
looking. It works by writing hooks into your Claude Code `settings.json`. The installer
*merges* into whatever you already have (never clobbers other hooks/settings) and backs
the file up first.

Default style is **spoken words** (`say`); a **chime** style is also available.

---

## The cues — what you hear, and when

| You hear (voice / tone) | When | Hook event |
|---|---|---|
| **"question"** / Ping ×2 | Claude is **idle, waiting on your next prompt** | `Notification` (matcher `idle_prompt`) |
| **"approval"** / Ping ×2 | An **approval prompt is waiting** — even while Claude works in the background | `PermissionRequest` |
| **"denied"** / Basso | A tool call was **denied / blocked** | `PermissionDenied` |
| **"done"** / Glass | Claude **finished a turn cleanly** — fires **once**, silent on re-wakes | `Stop` (gated) |
| **"error"** / Sosumi | A turn **failed** on a non-throttle API error | `StopFailure` (other error types) |
| **"throttled"** / Submarine | A turn **failed on rate-limit (429) or overload** | `StopFailure` (`rate_limit\|overloaded`) |
| **"credits"** / Funk | A turn **failed on a billing / quota error** | `StopFailure` (`billing_error`) |
| **"compacting"** / Pop | Context was **auto-summarized** (cache "bust") or manual `/compact` | `PreCompact` (`auto\|manual`) |

Design notes:

- **Approvals ring even mid-work.** `PermissionRequest` fires the instant the approval
  dialog appears, regardless of background activity — a plain idle "attention" signal
  can stay silent while Claude is busy.
- **"done" fires once, not per message.** The `Stop` cue reads the event's
  `stop_hook_active` flag and only speaks on a *genuine* turn-end; if another `Stop` hook
  (a review/CI gate, a completion check) re-wakes Claude, it stays silent on those
  re-wakes instead of repeating.
- **Failures are split three ways.** `StopFailure` carries an error-type matcher, so a
  429/overload says **"throttled"**, a billing/quota error says **"credits"**, and
  anything else says **"error."** (Claude Code exposes no *proactive* "you're near your
  usage limit" event — the earliest hook-visible signal is a turn that already failed.)

---

## Install

```bash
bash ~/.claude/tools/notification-sounds/install.sh
```

Then, in Claude Code, type **`/hooks`** once — or restart it. **Required:** Claude Code
only loads hook changes at startup, so nothing happens until you do.

Chime style instead of voice:

```bash
CC_CUE=tone bash ~/.claude/tools/notification-sounds/install.sh
```

Your other settings and hooks are untouched, and a timestamped backup
(`settings.json.bak.<epoch>`) is written first.

---

## Change the words, voice, or sounds

Everything is controlled by environment variables passed to `install.sh`. Set some, re-run,
reload with `/hooks`. Re-running is safe — it replaces the module's own hooks in place.

**Voice style (`CC_CUE=voice`, the default):**

| Variable | Default | |
|---|---|---|
| `CC_SAY_QUESTION` | `question` | word for the idle "waiting on you" cue |
| `CC_SAY_APPROVAL` | `approval` | word for an approval prompt |
| `CC_SAY_DENIED` | `denied` | word for a denied tool call |
| `CC_SAY_DONE` | `done` | word for a clean finish |
| `CC_SAY_ERROR` | `error` | word for a failed turn |
| `CC_SAY_THROTTLE` | `throttled` | word for rate-limit / overload |
| `CC_SAY_CREDITS` | `credits` | word for a billing / quota failure |
| `CC_SAY_COMPACT` | `compacting` | word for context compaction |
| `CC_SAY_VOICE` | *(system default)* | a named voice — list them with `say -v '?'` |
| `CC_SAY_RATE` | *(default)* | speaking rate in words/min, e.g. `250` |

```bash
# A specific voice, faster, and reword a couple of cues:
CC_SAY_VOICE=Samantha CC_SAY_RATE=240 CC_SAY_DONE=ready CC_SAY_COMPACT="cache reset" \
  bash ~/.claude/tools/notification-sounds/install.sh
```

**Chime style (`CC_CUE=tone`):** `CC_SOUND_RATE` sets pitch (lower = deeper), and each cue
has its own `CC_SOUND_QUESTION` / `_APPROVAL` / `_DENIED` / `_DONE` / `_ERROR` / `_THROTTLE`
/ `_CREDITS` / `_COMPACT`, each a filename from `/System/Library/Sounds`. List them:

```bash
ls /System/Library/Sounds   # Basso Blow Bottle Frog Funk Glass Hero Morse Ping Pop Purr Sosumi Submarine Tink
```

A filename that isn't there is rejected and your settings are left untouched.

### Optional: a global mute switch

Install with a guard prefix to gate every cue on one env var (handy for shared/automated
runs). This mutes everything when `QUIET_SOUNDS=1` is set in the environment Claude Code
runs under:

```bash
CC_HOOK_PREFIX='[ "${QUIET_SOUNDS:-0}" = "1" ] && exit 0; ' \
  bash ~/.claude/tools/notification-sounds/install.sh
```

---

## Uninstall

```bash
bash ~/.claude/tools/notification-sounds/uninstall.sh
```

Removes every hook this module added (identified by its `: cc-notify;` marker or a legacy
tone command), drops now-empty hook events, and leaves all your other hooks and settings in
place. Backs up first. Reload with `/hooks` afterward.

---

## Test

```bash
bash ~/.claude/tools/notification-sounds/test.sh
```

52 checks, no audio (it stubs `say`/`afplay` and counts calls). Covers install
merge/preserve/upgrade/idempotency (incl. the 3 `StopFailure` matcher entries), every cue's
runtime behavior and spoken word, the `stop_hook_active` gate (silent on re-wake, speaks on
turn-end, fails open on missing input *or* missing `jq`), the knobs and guard prefix, the
tone style, and uninstall.

---

## How it works

Each hook is a `type: "command"` entry that backgrounds `say`/`afplay` with `&` so the UI
never waits on audio, and starts with a `: cc-notify;` marker (a shell no-op) that the
installer/uninstaller use to find and manage the module's own hooks.

- **Finished cue** (`Stop`):
  `: cc-notify; jq -e '.stop_hook_active==true' >/dev/null 2>&1 && exit 0; say "done" >/dev/null 2>&1 &`
  `stop_hook_active` is `true` only when a Stop hook re-woke Claude; on `true` it exits before
  speaking (silent), otherwise it speaks. If `jq` is missing the `&&` fails and it falls
  through to the cue — the finished signal is never silently lost.
- **Failure cues** (`StopFailure`) use the event's error-type matcher to route 429/overload,
  billing, and everything-else to three different words. `StopFailure`'s exit code is ignored
  by Claude Code (it's a logging/notify hook) — perfect for a pure sound side-effect.
- Command hooks on `PermissionRequest` / `PermissionDenied` that exit 0 with no stdout are
  pure side-effects — they do **not** change the approve/deny outcome.

Event semantics were verified against the Claude Code hooks reference; matcher values
(`idle_prompt`, `rate_limit|overloaded`, `billing_error`, `auto|manual`) come from that doc.

---

## Requirements & notes

- **macOS only** — uses `say` / `afplay` and `/System/Library/Sounds`.
- **`jq`** — used by the installer, and by the finished cue at runtime (`brew install jq`). If
  it's ever missing at runtime the finished cue still fires.
- Hooks live in **`~/.claude/settings.json`** under `.hooks`, so they apply to **all** projects.
- **No usage-limit pre-warning.** Claude Code exposes no proactive "near your quota" hook; the
  earliest hook-visible signal is a turn that already failed (`StopFailure` → "credits"/"throttled").
