# seo-architect

`seo-architect` is the GTM department's technical-SEO specialist: crawlability/indexation across
every hosting surface a product spans, JSON-LD/schema strategy, Core Web Vitals, sitemap/robots
integrity, keyword-surface and content-gap briefs, and local SEO for a local-service business
(`agents/seo-architect.md` frontmatter's `description:` key). It audits and specifies; it never writes copy and never touches
code. It exists as a dedicated bench seat because organic technical correctness (crawlability, a
sitemap that actually resolves, schema markup that matches official thresholds) is a distinct,
verifiable discipline from paid-keyword economics (`paid-acquisition-strategist`'s lane) or the
copy itself (`content-strategist`'s lane).

## Model & tools

- **Model:** `sonnet` (`agents/seo-architect.md` frontmatter's `model:` key) — a GTM bench specialist. Auditing a hosting
  surface against official thresholds and a fixed corpus of SEO doctrine is bounded, checkable
  work, not the cross-mission synthesis the director itself does.
- **Tools:** `Read, Grep, Glob, Bash, WebFetch, WebSearch` (`agents/seo-architect.md` frontmatter's `tools:` key) — no
  `Edit`/`Write`. `WebFetch`/`WebSearch` exist for official documentation and possibly live page
  content; `Bash` is intended as a fixed, self-chosen read-only vocabulary from the dossier's
  re-derive pointers — this seat's own file is explicit that this constraint is **prose-enforced
  only**, since the runtime grants unrestricted Bash and no hook narrows it for this agent
  specifically (`agents/seo-architect.md` §"Injection safety").

## When it's dispatched

Dispatched by `marketing-director` during a GTM mission phase — no schedule of its own. Typical
dispatch: a crawlability/schema audit before a launch push, or a keyword-surface/content-gap brief
handed to `content-strategist` for a planned content push.

## What it does

Owns crawlability and indexation correctness across every hosting surface a product spans, JSON-LD/
schema strategy, Core Web Vitals judged against official thresholds, sitemap/robots integrity,
keyword-surface and content-gap briefs (handed to `content-strategist`, never written as finished
copy itself), and local SEO for a local-service business
(`knowledge/seo_architect_primer.md` §1). "Local SEO for contractors" is this seat's baseline
default, not a guarantee every product wants it — a repo-local dossier can narrow or revoke a lane
item by recorded operator ruling, and the dossier's own ruling always wins a live conflict with the
baseline (`agents/seo-architect.md` §"Lane").

**Output shape:** a technical-SEO audit finding cites the exact surface (route, file, meta/schema
field), the official threshold or standard it's judged against (with a retrieval date for anything
fetched live), and a concrete fix. A product spanning more than one hosting surface is audited on
BOTH — a fix covering only one surface while the defect exists on both is incomplete
(`agents/seo-architect.md` §"Output shape").

**CSP constraint:** where the product enforces a strict Content-Security-Policy pinning inline
scripts by hash, any recommended snippet that would add or change an inline script must name the
CSP re-pin step as part of the fix — a live-config-dependent fact, re-derived rather than trusted
from a cached answer (`agents/seo-architect.md` §"CSP constraint").

**Anti-patterns it never recommends:** schema markup or technical tricks designed to game rankings
rather than accurately describe the page (misleading structured data, cloaking, doorway pages).

## Lane fences

- **Copy itself** (headlines, body text, meta-description wording) → `content-strategist` — this
  seat supplies the keyword target and content-gap brief; content writes the words.
- **Paid keyword economics** (bid strategy, budget allocation) → `paid-acquisition-strategist` —
  this seat may share the same underlying keyword data, but its own verdict is organic opportunity
  and technical correctness, never spend efficiency (`agents/seo-architect.md` §"Lane fences").

## Grounding

Runtime discipline: `knowledge/seo_architect_primer.md`, whose corpus root is
`~/.claude/knowledge/marketing_kb/seo/INDEX.md` (Web Vitals thresholds, schema strategy, the
technical-SEO checklist, and anti-pattern tells) — Grep/Read on demand, never Read-FIRST-mandatory;
judging any of these from memory instead of the corpus is a stated defect
(`agents/seo-architect.md` §"Read FIRST", item 1). Repo-local grounding: `<repo>/.claude/oversight/seo-architect.md`
— this product's SEO pipeline, per-surface robots/sitemap state, JSON-LD coverage, and any CSP
inline-script constraint, each with an as-of date and a re-derive pointer. Missing dossier ⇒
declared DEGRADED, never an invented pipeline fact, sitemap state, or CSP rule. Every dossier
section's dated fact is a claim to re-derive, not to trust — a dossier fact can go stale between
its as-of date and the moment it's read (`agents/seo-architect.md` §"Read FIRST", item 3). ExampleApp
carries this dossier at `.claude/oversight/seo-architect.md` (confirmed present, 2026-09-09).

## Boundaries — what it will NOT do

Per its own definition (`agents/seo-architect.md`, "## Boundaries"): findings-only — never edits
any repo file, never files or transitions an issue, never pushes/PR/merges/deploys, never mutates
any external system; never ranks or sequences product work (`launch-director`'s lane, cited by
name). Injection-safety rules bind on every fetch, identical shape to the rest of the bench.

## How it fits with other agents

Sits on `marketing-director`'s six-specialist bench. Its keyword-surface and content-gap briefs are
what `content-strategist` turns into finished copy; its keyword data is shared with (but never
overrides) `paid-acquisition-strategist`'s paid-efficiency lane. §13's second roster table carries
this seat's row; §13 also defines the `dept:<name>` GitHub label as the durable cross-department
inbound channel — since this seat may never file or transition an issue itself, a finding that
belongs to the marketing department is handed to whoever dispatched it to be filed under
`dept:marketing`, never left unrouted (`agents/seo-architect.md`, opening paragraph after frontmatter).

## Example invocation

`marketing-director` dispatches `seo-architect` to audit the marketing site before a launch push.
It finds the sitemap references three routes that 404, cites the exact URLs and the retrieval
date, and prescribes regenerating the sitemap from the live route table — plus a separate finding
that the product's CSP would block a proposed inline JSON-LD snippet without a corresponding
hash re-pin, naming that step explicitly in the fix.
