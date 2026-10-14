# Company-pack authoring — how to write a `company.json`

This file explains **how to author a company pack** (`<home>/.claude/gtm/company.json`) for a new
GTM company — the human-readable companion to the machine-readable
[`tools/gtm/company_schema.json`](../../../tools/gtm/company_schema.json) (which documents every key
for `company.py`'s own error messages) and [`tools/gtm/README.md`](../../../tools/gtm/README.md)
(which documents the five pack tools). This file does not restate every key's syntax — read
`company_schema.json` directly for that — it explains the *authoring workflow*: what order to fill
keys in, what each section is *for*, and the mistakes that make `company.py validate` refuse a pack.
Company-agnostic: no company's actual values appear here, only the shape and the reasoning.

**[KB-SHARED-301]** A company pack's presence — not any separate registry flag — is what makes a
registered repo a GTM company (internal doctrine, `tools/gtm/README.md` §"company.py", retrieved
2026-09-27: "A 'company pack' is `<home>/.claude/gtm/company.json`. Its presence... is what makes a
registered repo a GTM company"). This is quoting the runtime's own README describing how its own
tooling works, not a measured number from any company's data.
Everything below assumes the home directory already exists and is (or will be)
registered in one of the two registries `company.py resolve` checks, in order: the runtime's
GTM-only `knowledge/gtm_company_registry.json` (for a home with no GitHub remote — most home-services
and local-only companies) or the runtime's `knowledge/repo_registry.json` (for a home that already has a
GitHub-registered repo, e.g. an existing product repo). **A slug present in both registries is
invalid** — pick one, register there, and never duplicate.

## Authoring order (why this order, not just a key list)

Fill sections in this order — later sections depend on earlier ones being settled, and validation
errors are easier to read in this order than key-alphabetical order:

### 1. Identity — `schema_version`, `slug`, `legal_name`, `display_names`, `business_model`, `brands[]`
Get the identity facts right first because almost everything else references them: `slug` must match
the registry key this pack resolves by (a mismatch is a validation error), and every `accounts[]`
entry's `brand` field must reference a real `brands[].id`. `business_model` is one of
`local_service | b2b_saas | ecommerce | other` — this single field is what a channel seat should
check before assuming, e.g., that local SEO is even relevant (a `b2b_saas` company likely has
`scope.local_seo: false`; see §3 below).

**If the company has more than one brand under one legal entity** (e.g. two separate service lines
run by the same owner), each gets its own `brands[]` entry with its own
`id`, `domains`, `phones`, and `nap` — this is what lets `host_systems`' path-prefix disambiguation
(see §5 below) tell two brands apart when they share a host like `facebook.com` or
`business.google.com`.

### 2. Persona — `persona_file`
Points at that company's own customer persona doc — the company-specific counterpart to one of this
shared corpus's own persona-file shapes: [`homeowner-buyer-psychology.md`](homeowner-buyer-psychology.md)
(for a `local_service` company selling to a homeowner end customer) or
[`contractor-buyer-psychology.md`](contractor-buyer-psychology.md) (for a `b2b_saas` company selling
software to a trade/home-services business). These two are shared, reusable *shapes*, not the only
possible persona files a company pack may select — a company in a different vertical (e.g. a dental
practice, or a different B2C/B2B split entirely) may need its own persona-file shape authored fresh.
`persona_file` may either reference one of these shared corpus files directly (when a company's
actual buyer genuinely matches the shared shape closely enough that no specialization is needed) or
point at that company's own file that specializes one of them with its own real facts (its actual
revenue band, its actual stated objections, its actual buying behavior) — **author or select the
persona file before or alongside the pack**, never leave `persona_file` pointing at a placeholder —
every seat's output quality depends on this being a real, specific description of the company's
actual customer, not a generic restatement of the shared corpus file it's supposed to specialize.

### 3. Scope — `scope.local_seo`, `scope.channels_in_scope`, `scope.channels_out_of_scope`
Decide which channels this company actually runs before writing `accounts[]` — an account entry for
a channel not in `channels_in_scope` is a mismatch a reviewer should catch. `channels_out_of_scope`
requires a `reason` and `ruling_ref` per entry — this is deliberate: "we're not doing paid search"
must be a traceable decision (an operator ruling, a plan citation), not a silent omission a future
seat might assume was an oversight and try to "fix."

### 4. Accounts — `accounts[]`
One entry per real account this company operates: `system` (e.g. `google_ads`, `gbp`, `facebook`),
`brand` (must reference `brands[].id`), `account_id`, `access` (`api | browser | operator_only`), and
`credential_ref` (`gsm:<secret>` | `browser:playwright-gtm` | `none`). **A `credential_ref` value
other than `none` that appears in more than one registered pack is invalid** — this is the mechanical
check that catches a credential accidentally shared across two companies. The operator runs multiple
unrelated businesses under one identity; a company's own house rule against cross-connecting its
operator's other businesses exists at the product level for exactly this reason, and this schema
check is the same principle enforced at the pack level.

### 5. Identity allowlist and host mapping — `identity_allowlist`, `host_systems`
`identity_allowlist` is the positive list of every real identifier this company owns (Facebook Page
ids, Instagram ids, GBP location ids, ad account ids, domains, listing URLs) — this is what the
G-A browser gate and the cross-company isolation checks use to confirm a navigation or action target
actually belongs to this company before allowing it. **Populate this list completely and accurately
before shadow-mode work begins** — an incomplete allowlist doesn't just under-protect, it also
produces false "off-target" denials on the company's own legitimate accounts, which is its own kind
of authoring defect (a pack that's too strict to actually operate is not more correct than one that's
accidentally too loose).

`host_systems` lets a pack override or extend the default host→system mapping
(`harvest_tool_trail.py`'s `DEFAULT_HOST_SYSTEMS`) for its own domains. **Remember the multi-brand
caveat:** a plain `{host: system}` entry is host-level only and cannot distinguish two brands sharing
a host — use the `<host>/<path-prefix>` form (a real GBP location id or Facebook Page id as the
path-prefix) whenever two of this pack's own brands share a host, checked before any plain host-only
fallback entry for the same host.

### 6. Claims policy — `claims_policy`
Every `terms[]` entry needs a `regex`, a `rule` (`no_new` — the term may already exist in copy but no
*new* instance may be added; or `forbid_any` — the term may never appear at all going forward), and a
`ruling_ref` tracing back to why this term is restricted. `never_claim_file` points at a company-
specific file listing capability/accuracy claims this company must never make — the company-specific
analog of the shared corpus's `department-anti-patterns.md` items 1–3, but for facts specific to this
company's own product/service (its own quarantined capabilities, its own unproven claims). **Author
this before any content-generating seat is dispatched for the company** — `act.py` (planned; not yet
built)'s content checks (§6.6 of the department plan) refuse a proposal whose `after` text trips a
`forbid_any` term or adds new matched text under `no_new`, but only if the terms are actually in the
pack to check against.

### 7. Shared identifiers — `shared_identifiers[]`
Any identifier (a system, an account, a domain) this company's operations touch that is *also*
claimed by another registered pack — each entry needs `with` (the other pack's slug), `relationship`,
`ruling_ref`, and `source`. This is the mechanical trace for a legitimately-shared-but-sensitive
touchpoint (e.g. one registered company being a paying customer/tenant of another registered
company's product) — every row in the department's tier table maps "anything touching a
system/identifier declared in `shared_identifiers`" to a mandatory operator card, never autonomous,
regardless of what tier the action would otherwise be. **Never leave a known cross-company touchpoint
undeclared** — an undeclared one doesn't remove the risk, it just removes the gate that would have
caught it.

### 8. AI content policy — `ai_content_policy`
`mode` is one of `disclose_never_strip | strip_before_publish | forbid`. This is a **per-company
decision that must trace to that company's own actual practice or ruling** — do not default to one
mode across every company. A software company selling *to* a skepticism-sensitive buyer (see `contractor-buyer-psychology.md`,
fact 3, "burned by software before") may rule that any AI-detectable content is unsafe for its own
public marketing and require `strip_before_publish` — record the ruling that selects this mode in
the company's own pack (`ruling_ref`), never copy another company's mode without its own ruling. A
`local_service` company whose brand voice is comfortable disclosing
AI-assisted content (a labeled AI-generated seasonal graphic, for instance) may instead choose
`disclose_never_strip`, which requires `disclosure_caption_line` and a `caps.feed_28d_max` limiting
how much of the company's visible feed volume can be AI-disclosed content in a rolling 28 days.
`forbid` means no AI-generated/AI-edited asset is used on any surface, full stop. Whichever mode is
chosen, `surfaces_forbidden` can carve out specific surfaces (e.g. customer-facing invoices) where
even a generally-permitted mode is still off-limits.

### 9. Autonomy — `autonomy`
See [`autonomy-tiers.md`](autonomy-tiers.md) for the full plain-language explanation of what
`level` (`shadow | autonomous`) and `standing_approvals[]` actually authorize. Author this section
**last, and only with the company's actual operator present** — every `standing_approvals[]` entry
needs a `verbatim` (the operator's actual words authorizing it), a `ts`, and `rows` (a list of real
`tier_table.json` (planned; not yet built) row ids the approval covers — **a bare `*` wildcard
anywhere in this list is invalid**, by design: every standing approval is scoped to named, specific
action types, never a blanket grant).

### 10. Spend, budget, cadence, paths — the operational plumbing
`spend` (currency, monthly cap, per-channel caps, `cap_ruling_ref`) and `budget` (weekly AI-spend
caps in USD for opus/sonnet dispatch, plus per-cadence dispatch caps) are both real caps that must
trace to an actual operator-approved number (`cap_ruling_ref` is required for `spend`, and the AI
`budget` figures are themselves signed off by the operator per the money rule in
`autonomy-tiers.md`). `paths.*` values are all home-relative — **no leading `/` or `~`, and no `..`
path component anywhere; an absolute or escaping path is invalid** — this is a deliberate containment
rule: a company pack cannot point any of its own state outside its own home directory.

## Common authoring mistakes (and what `company.py validate` will say)

- **Unknown top-level key** — `company.py` refuses keys not documented in `company_schema.json`;
  there is no silent pass-through. If a new field is genuinely needed, that's a schema change to
  propose, not a field to add ad hoc.
- **`slug` mismatch** — the pack's own `slug` value must equal the registry key used to resolve it.
  Copy-pasting one company's pack as a template for another and forgetting to update `slug` is the
  most common version of this mistake.
- **A wildcard in `standing_approvals[].rows`** — always refused; every standing approval must name
  its exact covered row ids.
- **A `credential_ref` or identity value reused across two packs with no `shared_identifiers` entry**
  — refused as an undeclared cross-company touchpoint (§7 above exists to make this declarable and
  gated, not to make it disappear).
- **A `paths.*` value that is absolute or contains `..`** — refused outright (§10 above).
- **Secret-shaped content pasted directly into `company.json` or `<home>/.claude/gtm/mcp.json`** —
  `company.py validate` runs a secret-key-name and secret-value-pattern scan and refuses a pack that
  looks like it's carrying a live credential inline; every real secret is a `gsm:<secret>` reference,
  never a literal value in the pack.
- **Registering the same slug in both registries** — `company.py resolve` raises rather than picking
  one silently; deregister from whichever registry is wrong (`company.py unregister <slug>` only
  touches the GTM-only registry — it will never remove a `repo_registry.json` entry).

## Contractor bend

Not applicable in the usual sense (this file is about pack mechanics, not customer-facing content),
but the same discipline this shared corpus applies everywhere else applies here too: a company pack
is itself a claim about what's true and what's authorized for that company, and an inaccurate or
incomplete pack (a missing `shared_identifiers` entry, an over-broad `identity_allowlist`, a
`persona_file` nobody actually wrote) produces exactly the same category of harm — a confidently
wrong output reaching a real customer or a real cross-company boundary — that the rest of this
corpus's citation and anti-pattern discipline exists to prevent in written content.
