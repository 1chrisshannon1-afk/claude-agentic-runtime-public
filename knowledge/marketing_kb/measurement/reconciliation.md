# Reconciliation — Ads vs. CRM vs. GA4

No single system's own reported numbers can be trusted in isolation. This file defines the 4-signal
validation test for calling any conversion "live," and the reconciliation loop that catches drift
between what an ad platform claims, what GA4 recorded, and what the CRM shows actually happened.

---

## 1. Why three systems, and why they disagree

**[KB-MEAS-044] (internal doctrine)** Google Ads, GA4, and the CRM each measure a different thing, using different
attribution logic, on different timelines — some disagreement between them is expected and does not
by itself indicate an error:

- **Google Ads** reports conversions it can attribute to its own clicks, using its own attribution
  model and lookback window, and (per [`enhanced-and-offline-conversions.md`](enhanced-and-offline-conversions.md))
  frequently lags behind real-world outcomes by the length of the sales cycle.
- **GA4** reports events fired by its own tag across *all* traffic sources, using GA4's own
  session-based attribution and its own default channel grouping — a session GA4 attributes to
  "Organic Search" and a click Google Ads attributes to a paid campaign are not contradictory if the
  user's actual path involved both an ad click and a later organic return visit that happened to be
  the session where the form was submitted.
- **The CRM** reports what a human recorded as actually happening (a lead qualified, an estimate
  given, a job booked) — this is the only one of the three systems capable of knowing whether a
  "conversion" was a real business outcome or a wrong number/spam/duplicate.

**Correct posture:** treat CRM data as the ground truth for *business outcome* (was this a real,
qualified lead that became revenue), and treat Ads/GA4 as ground truth for *platform-side event
delivery* (did the tag fire, did the platform record it) — reconciliation is checking that these two
kinds of truth stay connected to each other, not expecting all three systems' raw numbers to match
exactly.

## 2. The 4-signal test — what makes a conversion "verified," not just "configured"

**[KB-MEAS-045] Adapted from `paid_acquisition/measurement-and-attribution.md` (internal doctrine):** a conversion action or tracked event is not verified merely because it
was set up in a platform's UI. Verification requires all four of:

1. **The trigger actually fires on a real interaction** — tested by performing the real action
   (submitting the actual form, clicking the actual call number) on a live or staging environment,
   not by inspecting the configuration and assuming it will fire.
2. **GA4's DebugView (or the platform's equivalent real-time debug tool) shows the event landing**
   with the expected parameters populated — confirms the client-side firing mechanism actually
   reaches the measurement platform, not just that a tag manager rule is configured to try.
3. **The downstream conversion action (Google Ads, Meta, etc.) reads a real, non-zero, recently
   updated status** — confirms the event is not just landing in GA4 but is actually being picked up
   and counted by whatever ad platform is supposed to optimize against it; a GA4-linked Google Ads
   conversion action can be correctly receiving events in GA4 while still misconfigured on the
   Google Ads side (wrong linked property, disabled conversion action) and showing zero.
4. **Tested on both desktop and mobile viewport/interaction paths** — a click handler or trigger
   condition bound to a desktop-only interaction pattern (a hover state, a specific element that
   renders differently on mobile) is a common way an event silently never fires for the majority-
   mobile traffic a home-services site usually sees; passing signals 1-3 on desktop only is not a
   complete verification.

(Sourced from this corpus's own paid-acquisition measurement doctrine,
`paid_acquisition/measurement-and-attribution.md`, generalized here as the department-wide standard
any measurement-architect verification applies — restated identically in
[`ga4-event-design.md`](ga4-event-design.md) §6, which this file is the canonical definition for;
cite this file, not a restated copy, per this corpus's own citation-style rule against duplicating a
canonical definition across files.)

**A conversion action or event that has been configured but not run through all four signals is
"pending verification," not "live," and must not be reported as an active, trustworthy signal in any
dashboard or optimization decision** until it passes.

## 3. Reconciliation cadence and what a mismatch means

**[KB-MEAS-046] (internal doctrine)** On a fixed cadence (weekly, at minimum, per [`reporting-and-dashboards.md`](reporting-and-dashboards.md)),
compare: (a) Google Ads' reported conversion count for a settled date range, (b) GA4's event count
for the corresponding key event, and (c) the CRM's count of leads/qualified-leads/booked-jobs
attributed to that channel for the same window. A material, sustained divergence between these is a
signal to investigate, in this order of likely cause:

1. **A tracking gap** — the 4-signal test (§2) would have caught this before go-live; re-run it if a
   gap appears after a site/tag change.
2. **An attribution-window or date-range mismatch** — confirm all three systems are being read for
   the *same* settled window, accounting for [`enhanced-and-offline-conversions.md`](enhanced-and-offline-conversions.md)'s
   upload lag before treating a recent-period gap as a real discrepancy.
3. **A genuine lead-quality gap** — Ads/GA4 counts match each other but the CRM's *qualified* count
   is materially lower; this is not a tracking bug, it's the business-relevant signal that raw
   conversion volume and real lead quality have diverged (see [`call-tracking.md`](call-tracking.md)
   §3's qualified-vs-raw-count discipline for the same distinction applied to phone leads
   specifically).
4. **A double-counting or attribution-overlap artifact** — e.g., a lead counted once as a form
   submission in GA4 and again as a phone call in call tracking because the same visitor did both;
   deduplicate in the CRM (a single lead record with multiple touch-point fields) rather than
   summing raw event counts across systems as if they were independent leads.

## 4. Platform change-history — a mechanism for catching *who* changed what, when reconciliation flags a break

**[KB-MEAS-047]** When a reconciliation break coincides with a sudden shift (a conversion count that
drops to near-zero on a specific date with no corresponding traffic change), the platform's own
change-history is the first place to check for a coincident configuration change, before assuming a
code/tag regression elsewhere:

- **Google Ads** exposes the strongest audit trail: its `change_event` resource records
  `user_email` and `client_type` (distinguishing an API-made change from a UI-made change) alongside
  timestamps and before/after values. The query date range "must be within the past 30 days," and
  results are capped at 10,000 rows per query, with pagination via the last returned timestamp for
  anything beyond that (official, [Google Ads API — Change Event service](https://developers.google.com/google-ads/api/docs/change-event),
  retrieved 2026-09-27; API-documented limits are revised across versions, so re-confirm against the
  live reference before relying on a specific number in a time-sensitive investigation).
- **GA4** exposes a UI-based change-history view (user, before/after values); Google's own help
  documentation states "Change history provides a record of changes made to an account over the last
  2 years" and defaults the change-history table to that same 2-year window (official,
  [Google Analytics Help — About change history](https://support.google.com/analytics/answer/9305465),
  retrieved 2026-09-27). As of the retrieved documentation there is no dedicated public read API for
  this view — checking it is a manual/browser step, not an automated pull.
- **GTM** container versions (per [`gtm-container-governance.md`](gtm-container-governance.md) §3)
  record the publisher and timestamp for every version; comparing two versions' tag/trigger
  configurations directly shows what changed.
- **GBP** has no reliable per-user change audit log in the way Ads/GTM do — reconciliation for GBP-
  sourced breaks relies on comparing profile snapshots taken over time, not a definitive audit trail.

A reconciliation break with no coincident change in any of the above logs, and no traffic-volume
explanation, escalates to re-running the full 4-signal test (§2) rather than assuming the gap will
self-resolve.

## 5. What counts as "settled" before trusting a reconciled number

**[KB-MEAS-048] (internal doctrine)** Per [`enhanced-and-offline-conversions.md`](enhanced-and-offline-conversions.md)
§5, a recent date range is structurally incomplete for any metric depending on offline-conversion
uploads or a multi-day sales cycle. Reconciliation performed against an unsettled window will show a
"mismatch" that is not actually a data-quality problem — it's an artifact of comparing a complete
CRM number against an intentionally-still-filling Ads number. State the settling window explicitly
(e.g., "compare only cohorts 30+ days old") before drawing any conclusion from a reconciliation pass
on recent data.

---

## Contractor bend

- The GC has no reason to trust any single platform's dashboard number over another, and no way to
  arbitrate a disagreement themselves — reconciliation is entirely this department's internal
  discipline, invisible to the buyer, whose only visible effect is that the numbers this department
  eventually reports have already been cross-checked rather than copy-pasted from whichever platform
  showed the best-looking figure.
- When a reconciliation break happens, the GC should be told plainly and promptly (per this corpus's
  broader honesty-under-pressure doctrine) rather than having a quietly-corrected number appear in a
  later report with no explanation — "we found a tracking gap last week, here's what it affected and
  here's the fix" preserves trust; a silently-revised historical number does not.
