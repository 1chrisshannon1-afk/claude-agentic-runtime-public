# Consistency Auditor Primer

Runtime-level oversight primer. Product-agnostic: contains no app-specific paths, account names,
or counts belonging to any one repository. Distilled from external research on cross-surface
content consistency auditing (docs-as-code, single-source-of-truth architecture, terminology
management, drift detection); every claim below carries its source. Scope is deliberately narrow
to cross-surface *content/fact* consistency (docs, UI copy, marketing) — it does not cover
usability/heuristic evaluation, which is a separate discipline out of scope for this primer.

## 1. Content-audit method: inventory → audit → reconcile

Three distinct, sequential steps — do not collapse them:
1. **Inventory** — a purely quantitative listing of every content item: name/title, URL, owner,
   topic, format, created/modified date, page metadata, storage location. No quality judgment
   happens at this step; it is a census, not a review.
2. **Audit** — a qualitative pass over that inventory, judging each item's accuracy, relevance,
   and quality against current standards.
3. **Reconcile** — assign a disposition per item: keep / update (naming what needs doing and who
   owns it) / remove.
(Source: "Content Audits" — Nielsen Norman Group, https://www.nngroup.com/articles/content-audits/
— VERIFIED, opened directly)

The discipline this enforces on an agent: never skip straight to judgment. Build the full
inventory first, so the audit is checked against a complete surface list rather than whatever
happened to be sampled.

## 2. Single-source-of-truth architecture for product facts

General principle: each fact (a price, a tier name, a limit) is mastered in exactly one system;
every surface that displays it — docs, UI, marketing — reads or renders from that master rather
than re-typing the value locally. The mechanism that actually *prevents* drift, as opposed to
merely detecting it after the fact, is structural: if there is only one writable location for the
fact and everything else is a reference to or render of it, divergence becomes impossible rather
than something a linter has to keep catching.

Two concrete tooling patterns found:
- **Structured authoring (DITA) `@conref` / `@conkeyref`** — a "warehouse" topic holds the
  canonical value (e.g. a price or product name); every document pulls it by reference, so an
  edit in one place propagates everywhere it's used.
  (Sources: OASIS DITA 1.1 spec, "conref"; Heretto, "How Can I Reuse Content?")
- **Purpose-built SSOT tooling for SaaS pricing/entitlements** — a single schema (plans,
  features, entitlements, price) consumed identically by billing, provisioning, docs, and
  go-to-market surfaces, rather than four systems each keeping their own copy of the same facts.
  (Source: dev.to, "Tier: Like Terraform for Stripe")

## 3. Terminology management / controlled vocabulary

Practice: define approved terms and their synonyms centrally (a termbase), and enforce them via
tooling, not policy alone — a style guide nobody checks against is not enforcement.

Concrete mechanized version: **Vale** (vale.sh) is an offline, open-source prose linter — the
same category of tool as a code linter, applied to writing — driven by a single `.vale.ini`
config. A "vocabulary" in Vale is two plain-text files: `accept.txt` (approved terms/spellings,
e.g. canonical tier or feature names) and `reject.txt` (banned or deprecated terms, flagged as
lint errors). Teams commonly import a base style (the Microsoft Writing Style Guide or the Google
Developer Documentation Style Guide) and layer custom vocabulary rules on top. Vale runs in git
hooks and CI, so a docs or UI-copy pull request using a deprecated tier name, or an unapproved
synonym, fails the same mechanical way a code lint error would — not caught later by a human
skim.
(Sources: vale.sh; hetfs.github.io, "Create vocab .txt File" — Vale Linter documentation)

## 4. Docs-as-code QA

**"Docs as Tests"** reframes each doc as a test suite: each procedure becomes a test case, each
step becomes an assertion, executed against the real product (its actual UI or API), not just
validated against code snippets in isolation.
(Source: "Intro: Docs as Tests" — docsastests.com,
https://www.docsastests.com/docs-as-tests/concept/2024/01/09/intro-docs-as-tests.html)

**Doc Detective** (open-source, github.com/doc-detective) is the cited reference implementation:
it parses documentation and runs the steps it describes directly against live UIs and APIs, and
ships agent-tooling (a Claude plugin / Agent Skills) so an LLM agent can write, run, and debug
these doc-as-test cases.
(Source: github.com/doc-detective; github.com/doc-detective/agent-tools)

**GitLab's production docs CI pipeline** is the concrete example of docs-as-code fully wired into
delivery, verified directly at docs.gitlab.com/development/documentation/testing/:
- A `docs-lint markdown` job runs Vale (content/style) plus markdownlint (structure) together.
- A separate `docs-lint links` job checks relative and anchor link validity.
- `rubocop-docs` / `eslint-docs` validate doc links referenced from source code files.
- `docs-lint redirects` catches orphaned pages left behind by a rename or deletion.
- `graphql-verify` and `docs-lint deprecations-and-removals` fail the build outright if generated
  docs were not regenerated alongside the source change that should have updated them — a
  mechanical "these docs are now stale" gate, not a style check.
(Source: "Documentation Testing" — GitLab Docs, https://docs.gitlab.com/development/documentation/testing/
— VERIFIED, opened directly)

## 5. Detecting drift between UI copy, docs, and marketing

This is a less mature discipline than docs-as-code proper — no single canonical methodology
emerged in the research. The mechanical techniques actually reported:
- **PR-triggered flagging**: when a pull request touches a settings/pricing/feature-flag surface,
  auto-flag every doc page that references that surface; when a parameter or tier name is
  renamed, surface every remaining doc still using the old name. (Reported technique from a
  vendor blog — not independently verified against a live, named tool; treat as a pattern to
  implement, not a specific product to adopt.)
  (Source: cogley.jp, "Automating Vendor Doc Drift Detection")
- **Support-inbox signal**: repeated "this article didn't help" tickets on the same doc are a
  live, real-world drift indicator worth routing back into the audit queue.
  (Source: document360.com, "Documentation Drift")
- **API-contract testing** — the backend/docs-specific case of the same problem. Tools **Dredd**
  and **Schemathesis** send real HTTP requests and validate the live API's actual responses
  against its OpenAPI spec, catching undocumented endpoints/methods and response-schema drift
  (added or missing fields). This is the closest mechanized analog found to "the doc says X, the
  backend actually does Y" for API-shaped facts specifically.
  (Sources: wiz.io, "API Drift"; beeceptor.com, "OpenAPI Contract Drift Detection"; dev.to,
  "Enforcing API Correctness: Automated Contract Testing with OpenAPI and Dredd")

## 6. Standing corpus rotation

This fixed 4-week RULE-DOC-COHERENCE rotation runs ALONGSIDE any repo dossier's own named
audit-slices list, never instead of it (established 2026-09-01 after a product repo's decided-but-parked
defaults policy sat contradicted by a later strict-abstention ruling with no cross-reference —
example only, per the contract's preamble: the record is ExampleApp's
catalog_rules_and_rulings.md §43 ancestry paragraph and its EPIC #4742): when the orchestrator or the scheduled slot names a rotation
week, that corpus is the slice; otherwise the dossier's slice list governs as before. Cadence
against the twice-weekly slot (Tue/Sat): the FIRST firing of a calendar week may take the rotation
corpus; the second firing always takes a dossier slice — one bounded rotation slice per calendar
week, then the cycle repeats:
- **wk1** — product rule docs cross-surface: the repo's own doc-to-doc contradiction sweep (docs
  site, in-app copy/FAQ, marketing source-of-truth, pricing/tier code constants) per §§1-5's
  content-audit discipline applied to that repo's product docs.
- **wk2** — skills + dossiers vs disk: every `.claude/skills/` skill and every
  `.claude/oversight/*.md` dossier's factual claims (paths, commands, counts) checked against what
  is actually on disk in that repo.
- **wk3** — runtime contract vs agent files: `~/.claude/CLAUDE.md`'s claims about agent behavior,
  tool grants, and sanctions checked against the actual `~/.claude/agents/*.md` definitions.
- **wk4** — primers vs schedules/install doc: `~/.claude/knowledge/*_primer.md` claims about
  cadence, triggers, and mechanics checked against `~/.claude/schedules/` job prompts/plists and
  `~/.claude/knowledge/oversight_install.md`.

When both this standing rotation and a repo dossier's own audit-slices list exist, state plainly
which one a given invocation is drawing its slice from — never silently merge them into one
unlabeled rotation.

---

## Finding shape (mandatory)

Every contradiction this agent reports must be written with both sides cited and an
authoritativeness call made explicit — never a one-sided "doc X looks wrong":

```
Surface A says: <exact claim>  (cite: <heading/section or exact page + doc title>)
Surface B says: <exact claim>  (cite: <heading/section or exact page + doc title>)
Authoritative side: <A | B | neither — per the repo dossier's stated source-of-truth mapping>
Basis: <the specific rule/mapping in the repo dossier that makes that side authoritative>
```

- Citations are to a **heading or named section**, never a bare line number — line numbers shift
  on the next unrelated edit and silently invalidate the citation; a heading survives reflow.
- If the repo dossier does not state which surface is authoritative for the fact in question, say
  so explicitly rather than guessing — an unresolved-authority finding is itself a valid,
  reportable finding (it means the SSOT architecture in §2 has a gap for that fact), not a reason
  to skip reporting the contradiction.
- Any count cited in a finding (e.g. "N pages reference the old name") must state how it was
  derived (the search/grep method used) so it is re-checkable, not asserted as a bare number.
