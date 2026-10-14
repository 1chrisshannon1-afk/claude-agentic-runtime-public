# The approval-gate / reversal-pointer / idempotency-key triad

Every mutating action a GTM agent takes — a live ad-account write, a website edit, a pricing-page
change, a published landing page — is governed by three mechanisms working together. This pattern
recurs across every mutation-capable discipline this department has inherited (an ads-execution
procedure, an ads-approval procedure, `web-dev-safety.md`), and it recurs because each piece alone is
insufficient. Ported mechanism (internal doctrine, retrieved 2026-09-27); the platform-specific plumbing (a given ads
API's result shapes, a given CMS's backup tooling) is source-specific and re-derived generically
below for whatever this department eventually mutates (a marketing CMS, an ads account, an email
platform).

## Why all three, together

- **Approval-gate alone** stops an unauthorized change from happening, but says nothing about what
  happens if an approved change turns out to be wrong. Without a reversal pointer, "approved" and
  "irreversible" become synonyms — which turns every approval into a much bigger, scarier decision
  than it needs to be, and makes the human approver slower and more conservative than the actual
  risk warrants.
- **Reversal-pointer alone** (a promise "we can undo this") is worthless if nobody recorded *how*
  at the moment the change was made — reconstructing a rollback path after the fact, under
  pressure, with a live site or account already broken, is exactly the incident this pattern exists
  to prevent (see the incident cited in `web-dev-safety.md`).
- **Idempotency-key alone** protects against a network retry duplicating a mutation, but does
  nothing about whether the mutation should have happened at all, or whether it can be undone if it
  shouldn't have.

Together: nothing mutates without a human decision on record (approval-gate); every mutation that
happens carries, at the moment it happens, an explicit description of how to undo it (reversal-
pointer); and no mutation can be silently duplicated by a retry, a race, or an agent re-running a
call it isn't sure landed (idempotency-key).

## 1. Approval-gate

**The rule:** nothing that mutates a live system — an ad account, a website, a pricing page, a
published document — executes without an explicit, recorded human approval: a checked checkbox or
unambiguous chat approval (internal doctrine, ported ads-approval procedure, retrieved 2026-09-27). Two refinements that matter as much
as the headline rule:

- **A platform recommendation is not an approval.** A queued "Google recommended it," an
  auto-apply default, or a backlog item is a request to *evaluate*, never authorization to act
  (internal doctrine, ported ads-execution procedure, retrieved 2026-09-27, verbatim: "'Google recommended it' or 'it's in the backlog' is
  never authorization.") This generalizes past ads: a platform's own suggested action, a
  competitor's publicly visible move, or an old ticket sitting in a backlog is not consent from
  anyone who can actually give it.
- **Approval authorizes completion, not initiation.** Once approved, the agent completes 100% of
  the implementation — every setting, every asset, every step. The human is not expected to log
  in and finish anything themselves (internal doctrine, ported ads-approval procedure, retrieved 2026-09-27: "the user is not expected
  to manually log in and finish steps; only to review the plan beforehand and approve"). An
  approval that results in a half-applied change with "the rest is a UI step" is a process failure,
  not a completed engagement — see `phase-gate-model.md`'s execute-phase gate.
- **Prior approval never carries over.** Each mutating action needs its own approval; approving one
  campaign launch, one page edit, or one pricing change does not pre-authorize the next.

## 2. Reversal-pointer

**The rule:** every applied change is recorded, at the moment it's applied, with its before-value,
its after-value, and the exact mechanism to undo it — never just "this can probably be reverted."
A ported ads-execution discipline (internal doctrine, ported ads-execution procedure, retrieved 2026-09-27) requires this literally: "For every applied change record the
date, the exact before and after values, and how to reverse it... A change with no recorded
reversal path is incomplete."

A ported ads-write layer's result-payload pattern (internal doctrine) is the clearest worked example
of this discipline done right, and it generalizes well beyond ads. A mutation result should always
carry a `reversal` block
answering, without inference:

- **Was anything actually applied?** (`available: false` means nothing happened — there's nothing
  to reverse, and the system states that plainly rather than making the caller guess.)
- **If something was applied, exactly what, named precisely enough to undo it.** A ported
  discipline's result payloads name the exact fields holding what was confirmed — never "check the
  account and figure out what changed."
- **The reversal note is honest about uncertainty**, not just about success. When a mutate call
  returns an ambiguous result (nothing exploded, but nothing confirmable came back either), the
  correct reversal note says exactly that — "no confirmed resources, re-read the live state" — not
  a false "reverted" or a false "nothing happened."

**Generalized checklist for any mutation this department makes:**
1. Record the before-state (a screenshot, an exported config, a copy of the prior page HTML/copy)
   *before* the change, not reconstructed after.
2. Apply one logical change at a time — never batch several structural changes into one
   unreversible blob (a ported "one lever per campaign per window" / "one logical change per save"
   rule exists for exactly this reason: a batched change is a batched, harder-to-diagnose rollback).
3. Record the after-state and the literal undo mechanism (re-apply the prior value; restore from
   the named backup; re-import the exported template) in the same log entry as the change itself.
4. Never treat "we have backups somewhere" as a reversal pointer. A reversal pointer names the
   *specific* backup/prior-value for *this specific* change, findable without archaeology.

## 3. Idempotency-key

**The rule:** a mutating call that might have already landed is never blindly retried — an
identical repeat is either recognized as a replay of a prior result, or the live state is checked
before acting again. A ported ads-write layer's own discipline (internal doctrine, ported ads-execution procedure, retrieved 2026-09-27) implements this literally: an identical repeat
call returns the *stored* result plus an `_idempotency_replay: true` flag, with idempotency records
retained for a bounded window (UNVERIFIED — seeded, needs derivation: the ported system's own retention
window was on the order of weeks-to-months; re-derive the actual figure for whatever mutation layer
this department eventually builds rather than assuming a specific number). This solves a real, non-hypothetical failure
mode: a mutate call that raises no exception but returns an ambiguous result (empty, short, or
count-mismatched) is genuinely *unknown*, not confirmed-failed — and retrying it blind risks a
duplicate (a second identical negative-keyword list, a second identical conversion action, a
double-published page).

**Generalized checklist for any mutation this department makes:**
1. Give every mutating action a stable identity (a request id, a proposal id, a change-log entry
   id) so a retry of "the same" action can be recognized as the same action, not treated as new.
2. On an ambiguous outcome (no exception, but no clean confirmation either), the correct move is to
   **verify the live state**, never to auto-retry and never to assume failure. The ported rule is
   explicit: "Do NOT retry the same call automatically... Instead, verify the actual live state...
   before deciding whether to act again" (internal doctrine, ported ads-execution procedure, retrieved 2026-09-27).
3. A replayed/cached result may be stale relative to the current code or current live state —
   treat an old stored result's absence of a field as *unknown*, never as a negative answer.
4. This is a strict complement to the reversal-pointer, not a substitute: an idempotency key
   prevents an accidental *duplicate* mutation; a reversal pointer undoes a *deliberate* one that
   turned out to be wrong. A system needs both.

## Contractor bend

This entire triad is invisible to the end buyer and must stay that way — they experience it only as
"the vendor never broke anything, and when something didn't look right, it got fixed fast with no
drama." A buyer who has been burned by software or a vendor before (see
`contractor-buyer-psychology.md` / `homeowner-buyer-psychology.md`) is *more*, not less, sensitive to
a vendor who visibly fumbles a change — a broken pricing page, a website edit that goes live wrong, a
duplicated charge from a retried mutation. The bend here is about internal discipline producing
external reliability: because this kind of buyer's tolerance for a visible mistake is low (one bad
experience confirms their prior "software/vendors always break something" belief), the department
holds itself to this triad even for changes that feel small or internal — there is no "this one
doesn't matter enough for a reversal pointer" exception when the downstream audience is this kind of
buyer.
