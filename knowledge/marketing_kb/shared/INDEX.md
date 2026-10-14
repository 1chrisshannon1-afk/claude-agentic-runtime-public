# Shared — Index

Cross-seat shared doctrine for the GTM department — company-agnostic, serving any company the
department runs a mission for. This is the department's common ground — every seat (paid-
acquisition, SEO, content, brand, pricing, conversion, and any future seat) reads this domain before
its own, and before that company's own pack/dossier; it is not itself a channel playbook and it
carries no single company's facts, rulings, or account details (those live in that company's own
`company.json` pack and its own dossier — see `company-pack-authoring.md`). Grep-reachable on demand
— read the file that answers the question, not the whole corpus.

**Registered domains** (each with its own `INDEX.md`, not duplicated here — this is the one
cross-domain link surface, since no top-level `marketing_kb/INDEX.md` exists):
[`paid_acquisition/`](../paid_acquisition/INDEX.md) ·
[`seo/`](../seo/INDEX.md) ·
[`content/`](../content/INDEX.md) ·
[`brand/`](../brand/INDEX.md) ·
[`pricing/`](../pricing/INDEX.md) ·
[`conversion/`](../conversion/INDEX.md) ·
[`compliance/`](../compliance/INDEX.md) ·
[`local/`](../local/INDEX.md) ·
[`measurement/`](../measurement/INDEX.md) ·
[`reputation/`](../reputation/INDEX.md) ·
[`sales/`](../sales/INDEX.md) ·
[`social/`](../social/INDEX.md) ·
[`web_ops/`](../web_ops/INDEX.md).

| File | Answers |
|---|---|
| [`citation-style.md`](citation-style.md) | The provenance-tag house style every claim in this corpus (and every seat's output) must follow — `(official)` / `(third-party)` / `(internal-measured)` / `(internal doctrine)` / `UNVERIFIED` (both forms), with retrieval dates and worked examples of each. |
| [`contractor-buyer-psychology.md`](contractor-buyer-psychology.md) | One example persona-file shape for a **B2B software buyer** — a busy, time-poor, skepticism-earned small-business owner who buys software for their own trade business (a general contractor is the worked archetype), how they decide, what "burned by software before" means concretely, and how a seat must bend its default doctrine for this kind of buyer. A specific company's own version of this persona lives in its own pack (`persona_file`); this file is a reusable shape, not any one company's actual buyer. |
| [`homeowner-buyer-psychology.md`](homeowner-buyer-psychology.md) | A companion persona-file shape for the **end consumer** of a `local_service` company (e.g. a homeowner hiring a remodeling/renovation company) — the five behavioral facts that govern how they research and trust a service provider, and photo-release/consent doctrine for before/after content. Selected instead of (or alongside) `contractor-buyer-psychology.md` depending on whether the company being served sells B2B software or a B2C service. |
| [`home-services-playbooks.md`](home-services-playbooks.md) | Home-services-specific operating doctrine: seasonality and demand cycles, referral-program mechanics, and before/after photo and project-gallery rules — the practical playbooks a `local_service` company runs on. |
| [`phase-gate-model.md`](phase-gate-model.md) | The collect → analyze → plan → approve → execute → verify phase-gate model every GTM engagement runs through (ported mechanism, internal doctrine), with completion-artifact requirements per phase. |
| [`approval-gate-triad.md`](approval-gate-triad.md) | The approval-gate / reversal-pointer / idempotency-key pattern that governs every mutating action a GTM agent takes — why all three are required together, and what each looks like in practice. |
| [`autonomy-tiers.md`](autonomy-tiers.md) | Plain-language summary of the tier table (T0/T1/T2/T2-review, identity-irreversible, `$`, shared systems, NEVER — the plan §20.6 class names; within-ceiling optimizations sit in the autonomous class) and the two-level autonomy ladder (shadow/autonomous) that decide how much oversight any given GTM action needs — including the money rule that never bends. |
| [`experiment-discipline.md`](experiment-discipline.md) | How to run an A/B or split test honestly — setting the stop condition in advance, why peeking early inflates false positives (with measured figures), sample-ratio-mismatch as a silent test-invalidating bug, and what to do instead when traffic is too low to test formally. |
| [`web-dev-safety.md`](web-dev-safety.md) | Staging-first, backup-verified, audit-logged website change discipline (ported mechanism, internal doctrine), for any seat that touches a marketing site or landing pages. |
| [`competitor-audit-method.md`](competitor-audit-method.md) | The full competitor-audit procedure — discovery methods, competitor tiers, the seven analysis dimensions, the gap-analysis matrix, and the GREEN/YELLOW/RED scoring rubric — company-agnostic method; each company's own competitor set and read live in its own positioning doc. |
| [`department-anti-patterns.md`](department-anti-patterns.md) | Cross-seat anti-patterns every GTM seat must never do — fabricated testimonials, contradicting the product's never-claim list, unverified accuracy claims, and more — each with the failure mode it prevents. |
| [`company-pack-authoring.md`](company-pack-authoring.md) | How to author a `company.json` company pack — the authoring workflow, section-by-section, and the mistakes that make `company.py validate` refuse a pack. |
| [`kb-verification-procedure.md`](kb-verification-procedure.md) | The 1:1 claim_id verification contract every knowledge-base authoring pass goes through — a separate sonnet dispatch that opens every cited source and records a PASS/FAIL/UNVERIFIABLE verdict per claim, never a file-level impression. |

## How this domain relates to the rest of the GTM corpus

This is the *shared* domain — doctrine that is true regardless of which channel seat is acting.
Channel-specific mechanics (Google Ads bid ladders, SEO technical checklists, pricing formulas)
live in their own domain directories (`paid_acquisition/`, `seo/`, `pricing/`, `content/`, `brand/`,
`conversion/`, `compliance/`, `local/`, `measurement/`, `reputation/`, `sales/`, `social/`,
`web_ops/`) and are not duplicated here. When a channel seat's own doctrine conflicts with a file
in this domain, this domain wins — these are department-level constraints, not one seat's opinion.
