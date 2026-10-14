# GTM Container Governance — Workspaces, Versions, Publish Permissions

How a Google Tag Manager (GTM) container should be governed so that a mistaken or malicious tag
change can't reach live traffic unreviewed, and how workspace/version mechanics actually work so an
agent doesn't reinvent an unsafe process out of not knowing the platform already has a safer one
built in.

---

## 1. The permission ladder — never grant more than the seat needs

**[KB-MEAS-009]** GTM has four container-level access tiers, each strictly additive:

| Level | Can do |
|---|---|
| **Read** | Browse tags/triggers/variables. Cannot make any changes. |
| **Edit** | Create workspaces and make edits. Cannot create versions or publish. |
| **Approve** | Everything Edit can, plus create versions. Cannot publish. |
| **Publish** | Everything Approve can, plus publish live. |

(official, Google Tag Manager Help, "User permissions," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/6107011)

**Reject example:** granting a GTM agent seat **Publish**-level access as its standing permission so
it "doesn't have to ask each time." **Pass example:** an agent seat holds **Edit** or **Approve**
by default (it can build and version a change in its own workspace) and a human or a
separately-gated reviewer step holds **Publish** — mirroring this corpus's own maker-checker
discipline (see `shared/approval-gate-triad.md`). A GTM tag change reaches live traffic on every
page load of the property it's attached to; treat the Publish action with the same standing as a
production deploy, never as a routine edit.

**[KB-MEAS-010]** Google's own documentation warns that a container with a single administrator
risks the account becoming permanently inaccessible: "if a sole admin becomes unavailable, the
account risks deletion after 30 days without administrative access" (official, Google Tag Manager
Help, "User permissions," retrieved 2026-09-27: https://support.google.com/tagmanager/answer/6107011).
Every managed container needs at least two humans (or one human plus one documented recovery path)
holding Admin/Publish access — a single point of failure here is an availability risk, not just a
governance nicety.

## 2. Workspaces — how concurrent, unpublished work is isolated

**[KB-MEAS-011]** A workspace is GTM's unit of in-progress, unpublished work. A standard (non-360)
account supports the default workspace plus up to 2 additional workspaces; GTM 360 accounts allow
unlimited workspaces (official, Google Tag Manager Help, "Workspaces," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/7059647). Each team member (or agent seat) works in
their own workspace so in-progress, unreviewed changes never appear in another workspace's diff or
accidentally get bundled into someone else's publish.

**[KB-MEAS-012]** When two workspaces touch the same tag/trigger/variable, GTM surfaces a
color-coded conflict at publish time: blue = changed in both the synced version and the current
workspace, red = changed in the synced version but missing from the current workspace, green =
changed in the current workspace but absent from the synced version. Each conflict is resolved
individually — accept the synced change or keep the workspace's own change (official, Google Tag
Manager Help, "Workspaces," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/7059647). **An agent must never resolve a workspace
conflict by blanket-accepting "mine" without reading what the conflicting change actually was** —
a silently-discarded conflicting edit from a human teammate is exactly the clobber this corpus's
own multi-agent file-claim discipline (runtime CLAUDE.md §2) exists to prevent, applied to a GTM
container instead of a git tree.

## 3. Versions — the audit trail, and how rollback actually works

**[KB-MEAS-013]** A version is an immutable snapshot of the entire container configuration at a
point in time. "Every time a container is published, a version of that container is recorded"
(official, Google Tag Manager Help, "Publishing, versions, and approvals," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/6107163) — publishing and version creation are the
same act; there is no way to publish without leaving a version behind. A user with **Approve**
access or higher can also create a version without publishing it (a reviewable checkpoint before
going live).

**[KB-MEAS-014] Rollback mechanic:** open **Versions**, select the target version's **Actions**
menu, choose **Set as Latest Version** — this replaces the current workspace/live version with the
selected historical one (official, Google Tag Manager Help, "Publishing, versions, and approvals,"
retrieved 2026-09-27: https://support.google.com/tagmanager/answer/6107163). This is the correct,
sanctioned way to undo a bad container publish — never attempt to hand-reconstruct a prior state by
re-editing tags from memory; the version history already holds the exact prior state.

**Pass example:** a tag misconfiguration reaches live traffic, breaking conversion tracking →
identify the last known-good version in the version list by its name/timestamp → **Set as Latest
Version** → verify via the 4-signal test (`reconciliation.md`) that tracking is restored → THEN
re-attempt the original change in a fresh workspace with the fix. **Reject example:** trying to
manually undo each individual tag edit in the live workspace one at a time under time pressure,
risking missing one and leaving a partially-broken state.

## 4. Naming versions descriptively — the audit trail is only as good as its labels

**[KB-MEAS-015]** Google's own guidance is to give each version a descriptive name (e.g., "GA page
view tag - initial launch") rather than an empty or generic name, specifically because the version
history is how a future person (or agent) reconstructs what changed and when (official, Google Tag
Manager Help, "Publishing, versions, and approvals," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/6107163). Every published version this department
creates carries a version name that states what changed and cites the ticket/action-log entry that
authorized it (see the department's own activity-log tool, per the department's own logging rule) —
mirroring the runtime's own commit-message discipline applied to a non-git system of record.

## 5. Approval workflow (GTM 360 only) — use it if the account has it

**[KB-MEAS-016]** GTM 360 accounts support a built-in approval workflow: a user requests approval to
publish (optionally assigning specific reviewers and adding comments), and a user with Approve or
Publish access reviews the pending request, choosing Approve, Send Back, or Withdraw (official,
Google Tag Manager Help, "Publishing, versions, and approvals," retrieved 2026-09-27:
https://support.google.com/tagmanager/answer/6107163). Where a managed container is on GTM 360,
this built-in workflow is the preferred mechanism over an out-of-band approval (a card or a Slack
message) because it keeps the approval record inside the same system as the change itself. Where
the account is on standard (free) GTM, no built-in approval exists — the department's own
maker-checker pattern (a separate reviewing seat/human holding Publish, per §1) is the substitute,
and the version name (§4) is where that approval gets recorded since the platform provides no other
place to put it.

## 6. What a governance review checks

Before any GTM change reaches Publish, confirm:

1. The change traces to a tracking-plan row (`ga4-event-design.md` §5) or a stated business reason.
2. It was built in a workspace, not directly against a version (versions are read-only snapshots;
   there is no "direct edit" path that skips a workspace).
3. Any conflict from a concurrent workspace was resolved by inspecting both sides, never
   blanket-accepted.
4. The version about to be published carries a descriptive name and a citation to the authorizing
   action-log entry.
5. The Publish action itself is being taken by (or approved by) a seat holding Publish-level access
   under the department's maker-checker rule — never the same agent that authored the change,
   mirroring this corpus's shared approval-gate-triad doctrine.
6. A rollback plan exists implicitly by definition (§3) — but confirm the *last known-good* version
   is identified by name/timestamp *before* publishing the new one, so a rollback under pressure
   doesn't require hunting through unlabeled history.

---

## Contractor bend

- A GC's GTM container is usually managed by whoever set up their website originally (a web
  developer, a prior agency, or nobody) — assume no prior governance discipline exists and that
  version names in the existing history, if any, are unlabeled or generic. Establishing the naming
  and workspace discipline above from this department's first touch is itself a fix, not just
  process overhead.
- A tag change breaking conversion tracking on a live site is invisible to the GC in the way a
  broken storefront checkout would be blindingly obvious — there's no error message, the phone still
  rings, the forms still submit, and only the *measurement* silently goes dark. This is exactly why
  the rollback mechanic (§3) and the 4-signal verification (`reconciliation.md`) after every publish
  matter more here than for a business that would notice a broken funnel immediately by its own
  lost revenue.


## Field note (added 2026-09-28)

- **[KB-MEAS-055] Pausing and unpausing tags in the Tag Manager UI can mis-click.** The yellow
  "Unpause" banner button overlaps the tag menu's "Copy" item; one mis-click created a duplicate
  tag. Review the workspace changes list before every Submit, and delete stray copies before
  publishing (internal doctrine, incident: local-remodeler platform session, observed once, 2026-09-28).
