# Consent Mode

How Google Consent Mode (v2) actually behaves — the four consent signals, the default-vs-update
command sequence, and why a hard-gated tag silently under-reports rather than visibly failing. This
file governs any property with EU/UK/California traffic or any property subject to a consent
banner, which as of 2026 is the safe-default assumption for any public-facing site given how many
US states now have their own consumer-privacy statutes.

---

## 1. The four consent signals

**[KB-MEAS-017]** Google Consent Mode v2 uses four consent parameters, each set to `granted` or
`denied`:

| Signal | Controls |
|---|---|
| `ad_storage` | Whether advertising cookies may be stored |
| `analytics_storage` | Whether analytics-measurement cookies may be stored |
| `ad_user_data` | Whether user data may be sent to Google for advertising purposes |
| `ad_personalization` | Whether personalized-advertising features may use the data |

(official, Google for Developers, "Consent Mode," retrieved 2026-09-27:
https://developers.google.com/tag-platform/security/guides/consent)

`ad_user_data` and `ad_personalization` were added in Consent Mode v2 specifically to satisfy the
EU's Digital Markets Act consent requirements, which are stricter and more granular than the
original `ad_storage`/`analytics_storage` pair from v1 — a container still running v1-only consent
signals is running a deprecated configuration and should be flagged in any governance review.

## 2. `default` then `update` — order and timing matter

**[KB-MEAS-018]** The `default` command sets the baseline consent state and must fire on **every
page, before any measurement data is sent** — this is what makes it safe to install tags at all on
a site with a consent requirement, since nothing measures anything until a consent posture (even a
denied-by-default one) is established. The `update` command reflects the user's actual choice after
they interact with the consent banner, and Google's own guidance is explicit that "consent updates
[must be] tracked on the page where they occur, before any page transition" (official, Google for
Developers, "Consent Mode," retrieved 2026-09-27:
https://developers.google.com/tag-platform/security/guides/consent).

**Reject example:** a consent banner that fires its `update` call only on the *next* page load after
the user clicks "Accept," because the update script is bundled with page-transition logic instead of
running immediately in the banner's own click handler — every tag that already fired on the current
page under the stale `default` state never gets corrected. **Pass example:** the consent banner's
accept/reject handler calls `gtag('consent', 'update', {...})` synchronously, in the same event
handler, before any navigation.

## 3. Denied consent triggers modeling, not silent loss — but a hard-gated tag defeats this

**[KB-MEAS-019]** Consent Mode's entire design premise is that a `denied` state should not simply
lose the conversion — Google models an aggregate, privacy-safe estimate of what conversion volume
would have occurred under denied consent, based on the pattern of conversions observed under granted
consent from similar traffic. When `ad_storage` is denied, "data sent to Google will still include
the full page URL," and a hard-gated tag can additionally be configured with `ads_data_redaction` to
strip ad-click identifiers from the request while still sending the (reduced) signal that lets
modeling work (official, Google for Developers, "Consent Mode," retrieved 2026-09-27:
https://developers.google.com/tag-platform/security/guides/consent). URL passthrough is a
complementary mechanism that carries ad-click and session information through URL parameters when
cookie storage itself is denied.

**[KB-MEAS-020] The failure mode this file exists to name:** a tag implementation that checks
`hasConsent('analytics_storage')` (or an equivalent boolean gate) and **only fires when the check
returns true, with no modeled fallback**, defeats Consent Mode's whole purpose. This does not error.
It does not fail the 4-signal test (`reconciliation.md`) on the sessions where consent WAS granted —
those fire and verify cleanly. It simply **silently under-reports** on every session where consent
was denied, and because Consent Mode is designed to close that gap via modeling, a hard-gated
implementation looks indistinguishable from a correctly-modeled one to anyone reading the dashboard
— the reported number is just quietly smaller than reality, with no error state anywhere to flag it
(sourced from this corpus's own paid-acquisition doctrine,
`paid_acquisition/measurement-and-attribution.md`, itself citing standard, widely-documented Consent
Mode mechanics — treat the specific hard-gate-vs-modeling behavioral claim as consistent with
official Consent Mode documentation above but re-verify the exact current modeling mechanics against
Google's own Consent Mode implementation guide before stating a specific modeled-recovery percentage
to a client, since Google has not published a fixed, guaranteed recovery rate).

**Correct behavior:** implement Consent Mode via the standard `gtag`/GTM built-in consent
integration (which handles the default/update/modeling lifecycle correctly out of the box) rather
than a hand-rolled `if (hasConsent) { fireTag() }` gate. Before reading any CPA or conversion-rate
number from a property with a consent banner, explicitly check which implementation pattern is in
place — a hard-gated property's numbers should be treated as a known under-report, with the size of
the gap growing with the local consent-decline rate, never treated as complete.

## 4. What a consent-mode audit checks

1. All four signals (`ad_storage`, `ad_user_data`, `ad_personalization`, `analytics_storage`) are
   present — not just the v1 pair.
2. `default` fires before any measurement tag on every page.
3. `update` fires synchronously in the banner's own accept/reject handler, not deferred to next
   navigation.
4. No tag is hard-gated on a boolean consent check with no modeled fallback — verify by reading the
   actual tag-firing logic in GTM, not by trusting that "we have a consent banner" means Consent
   Mode is correctly wired.
5. The consent default matches the property's actual privacy policy and applicable jurisdiction
   requirements — this is a legal/compliance judgment outside this file's scope; flag it to the
   relevant compliance doctrine (`compliance/` domain, per the department's KB build plan) rather
   than asserting a jurisdiction's specific legal requirement here.

---

## Contractor bend

- A small owner-operated home-services business's website almost never has region-specific consent requirements top of mind —
  they are not thinking about GDPR/CCPA, they are thinking about getting the phone to ring. This is
  exactly why a hard-gated, silently-under-reporting implementation is dangerous specifically for
  this buyer: nobody on their side is positioned to notice the gap, and a marketing agency reporting
  a lower lead count than reality, with no visible error, looks like the campaign underperforming —
  not like a fixable tracking defect.
- When explaining this to the GC, skip the GDPR mechanics entirely and lead with the concrete
  consequence: "if your consent setup isn't wired correctly, we might be under-counting your real
  leads without either of us knowing it — that's why we check this specifically before trusting any
  lead-count number."
