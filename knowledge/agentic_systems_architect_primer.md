# Agentic Systems Architect Primer

Product-agnostic reference for an agent auditing *agentic-system design itself* — how agents are
decomposed, how they check their own work, whether they vote or verify, whether their knowledge
surfaces are grounded and actually read, whether the platform underneath them has quietly started
doing part of the job natively, expanded 2026-08-29 (§13/§14) to how a feedback loop (machine
or human) is actually engineered and how a repeatable multi-agent production pipeline should be
shaped or judged, and expanded again 2026-08-30 (**§15**) to **when, where, why, and why NOT to reach
for each of the twenty named agentic design patterns** — the vocabulary axis 11 judges pattern fit in.
Curated from `agentic_systems_evidence_2026_08_25.md`'s original 17-source
bibliography (primary-source standard; blogs/marketing excluded) plus the 18 further sources added
2026-08-29 for §13/§14 (control theory, Lean/TPS/Theory of Constraints, DORA/DevOps delivery-flow
research, flow-state psychology, and current Anthropic/Stripe production-agent guidance — see
Sources 18–35), plus the 28 source clusters added 2026-08-30 for §15 (Sources 36–63), whose full
per-pattern evidence, per-source verification tags and caveats live in
`agentic_patterns_evidence_2026_08_30.md` — the §15 citation-resolution surface, Read-FIRST #7.

**`agentic_systems_evidence_2026_08_25.md`**'s headline verdict on **its** original 17-source scope
(that file, not the 08-30 one): the folk
claim "feedback loop + consensus + fact store wins competitions" is **not
supported as a bundle by any primary source** — each leg has real, narrower support; the best
real-competition meta-analysis explicitly declines to attribute a win to any one pattern. This
primer is a snapshot; staleness is tracked, human-triggered per changed source until a
source-watch mechanism (Slice B, parked) closes the loop.

## 1. Start-simple doctrine — the baseline every expansion is audited against

All three major agent-vendor engineering guides converge, independently, on the same starting
posture: **build single-agent first; add agents only for a specific structural reason** —
parallelizable work, a context-window limit, too many tools for one system prompt, or workflow
branching that a single control loop can't express cleanly. Anthropic's *Building Effective Agents*
states it as the explicit gate: "building the right system for your needs… add multi-step agentic
systems only when simpler solutions fall short," and even gates its evaluator-optimizer pattern on
*clear evaluation criteria* existing, not on the pattern being generically desirable. OpenAI's
*Practical Guide to Building Agents* opens from "maximize a single agent's capabilities first" and
names exactly two orchestration patterns (Manager, Decentralized) when splitting genuinely helps.
Google's *Agents* whitepaper treats the orchestration loop as definitional to what an agent even
is, and names data stores as one core tool type. **None
of the three names consensus or voting as a default pattern.** Anthropic's own multi-agent research
system measured the real cost of departing from single-agent: **agentic (multi-step tool-use) work
runs ~4× the tokens of a single chat, and a full multi-agent configuration ~15×** — not a
per-added-agent multiplier, but the concrete cost band this audit weighs every roster expansion
against.

(Sources: 1, 2, 3, 4)

## 2. Grounded vs. ungrounded feedback loops

The one leg of the folk claim with real, direct support: Reflexion (Shinn et al., NeurIPS 2023)
moved HumanEval from 80% to 91% via self-reflection, and CRITIC shows the same mechanism,
tool-grounded. **The caveat that makes or breaks the result:** Huang et al. (ICLR 2024),
*Large Language Models Cannot Self-Correct Reasoning Yet*, shows the opposite result when the
critique step has **no external checkable signal** to ground against — ungrounded self-critique
does not reliably help, and can **degrade** the original answer. The dividing line is not "does it
reflect" but "does it reflect against something checkable outside its own judgment" — a test
result, a tool's return value, a retrieved fact, a lint/type-check pass. A loop that just asks the
same model to re-read its own output and judge it is the ungrounded case Huang et al. tested, not
the grounded case Reflexion did.

(Sources: 5, 6)

## 3. Consensus economics and non-monotonicity

Self-consistency (sampled-chain majority vote) is real and has real numbers behind it:
self-consistency (ICLR 2023) moves GSM8K **+17.9pp**, and multi-agent debate (ICML 2024)
moves GSM8K **77→85**. Google's whitepaper names self-consistency as a standard chain-of-thought
sub-technique (item 4) — it is not a separate exotic pattern. But its returns are **not monotonic
with scale**: Chen et al., *Are More LLM Calls All You Need?* (2024), find consensus accuracy rises
and then **falls** as more calls/voters are added — there is no guarantee that more voting improves
the answer, and past some point it actively hurts. *Stop Overvaluing Multi-Agent Debate* (2025,
preprint at fetch time) reports structured debate **often fails to beat single-agent
self-consistency** even at far higher compute — the evidence note's own comparison puts multi-agent
debate/consensus at **3–40× base cost**, non-monotonic, for a result that a cheaper self-consistency
pass frequently matches or beats. This is corroborated outside the lab:
in DARPA AIxCC (a real seven-finalist security competition), explicit voting was used by only **2
of 7 finalists** (item 13), and the ICPC 2025 winner used **sequential fallback between two
models, not voting**. Consensus/voting is a minority pattern among real winners, not the default
recipe folk wisdom assumes — a standing consensus/voting layer needs the same stated structural
justification §1 requires for adding agents at all.

(Sources: 4, 7, 8, 13)

## 4. Verification vs. generation — budget-dependent, not a strict hierarchy

Lightman et al., *Let's Verify Step by Step* (ICLR 2024), established that **process supervision
beats outcome supervision** — rewarding each reasoning step, not just the final answer. This is
real support for "add a verification step." But *When To Solve, When To Verify* (2025) shows the
economics are budget-dependent, not a strict hierarchy: **generative verification can need up to
~8× the compute of self-consistency just to match it**, and compute-optimal spend favors plain
generation at most budgets. The audit question is never "is verification good" (yes, in principle)
but "at this compute budget, does the specific verification step used actually beat the cheaper
alternative it's displacing" — the same question the runtime's own review-cost ladder already
answers operationally (§9 below): a full Opus adversarial pass is the expensive generative-
verification end of this spectrum, and the risk-tier/targeted-verification rules exist to avoid
paying its cost when a cheaper check would match it.

(Sources: 9, 10)

## 5. Adaptive decomposition — the plateau-triggers-split rule, not a numeric cap

ADaPT (Prasad et al., NAACL 2024) is the one decomposition result in the curated bibliography with
real numbers: **+27–33pp** over non-adaptive baselines on ALFWorld/WebShop/TextCraft. Critically,
the gain comes specifically from **adaptive** decomposition — the system splits a unit of work only
when that unit *fails to execute*, not from splitting everything maximally up front. This is the
audit's operative rule for judging unit size: the right question about any oversized module, agent
definition, or task is never "is it under N lines/files" (no numeric cap is supported by the
evidence) but **"did it plateau — fail or stall repeatedly — before anyone split it, and did
splitting happen at that plateau or only much later / never?"** A module that grew large without
ever plateauing is not, on this evidence, automatically a decomposition finding.

(Source: 12)

## 6. Fact stores and their three failure modes

Google's whitepaper (item 4) names data stores/retrieval as a core tool type. But the evidence note
documents fact storage as **the only leg absent from every winning-architecture record the note
reviewed** — neither the ICPC 2025 winners nor any of the seven DARPA AIxCC finalists (item 13)
describe a knowledge-store component. And where fact stores are used, THIS SECTION DOCUMENTS THREE
FAILURE MODES: two externally documented (immediately below), plus a third from this runtime's own
incident record (**judge-input insufficiency**, at the end of this section — read it, it is the one
that is invisible to the other two). The first two apply
regardless of retrieval quality: **lost-in-the-middle** (Liu et al., TACL 2023, item 11) — accuracy
is U-shaped by the retrieved fact's *position* in context, even when the correct fact was
successfully retrieved, meaning a bloated or badly-ordered knowledge surface can defeat a retrieval
that technically "worked" — and **staleness**, where a similarity-based retriever has no mechanism
to prefer a current fact over an outdated one of equal textual similarity. Both apply directly to
this runtime's own knowledge surfaces (primers, dossiers, the recommendation ledger): a primer with
no reader is a fact store no one queries; a recommendation ledger entry never re-scored is staleness
by construction.

**A THIRD failure mode — JUDGE-INPUT INSUFFICIENCY (added 2026-09-03, #4831, from a real
missed defect).** Lost-in-the-middle and staleness both ask *"is the retrieved fact good?"* Neither
asks the prior question: **does the artifact handed to a judging/reviewing agent actually contain
what that agent needs to render the verdict it is being asked for?** A reviewer can have perfect
knowledge-surface access and still be structurally unable to decide, because its *input packet*
omits a field the verdict depends on. This is not a retrieval failure — retrieval never runs — and
it is invisible to both modes above, which is exactly why it survived undetected.

The incident: in ExampleApp's trade-review loop, nine trade agents plus a GC were asked to
judge whether estimate QUANTITIES were correct. Their review packet carried the output line items
and the raw scope input, but omitted (a) the per-dimension SUPPLIED vs ASSUMED vs MISSING state and
(b) the per-line `flags` array — both of which the engine already computed. So a trade could not
distinguish *"this quantity is wrong"* from *"this quantity is right for a guessed input"*, and
graded partly blind for weeks. This agent had audited that loop's DISPATCH shape (fan-out sizing,
which grounding docs each trade reads) and passed it — the packet's CONTENTS were never the unit of
audit. Found only when the operator asked directly; fixed in `baedf3fe6`.

**The check this adds, applicable to any judge/reviewer agent in any loop:** for each such agent,
enumerate the decision it is asked to return, then verify its input artifact carries every field
that decision depends on. A verdict about quantities requires the quantity's provenance; a verdict
about a fix requires the pre-fix state; a verdict about a regression requires the baseline. Where a
required field exists in the producing system but is dropped in projection to the reviewer, that is
a finding of THIS class — report it as judge-input insufficiency, not as a grounding-doc gap.

**Cadence corollary:** this class is introduced by a change to a packet-builder or dispatch prompt,
so a monthly audit can miss it by weeks (it did). Treat any diff to a reviewer's input-construction
path as a trigger to re-run this check, independent of the monthly cycle.

(Sources: 4, 11, 13; third mode: #4831 incident record)

## 7. The harness confound

*Stop Comparing LLM Agents Without Disclosing the Harness* (2026, item 14) is the structural
caveat that undercuts most cross-system architecture claims: the harness — context construction,
tool orchestration, verification scaffolding — **often dominates model choice**, with documented
ranking reversals when the harness changes and the model doesn't. Comparing "our architecture" to
an external benchmark's winning architecture is unreliable unless the harnesses are matched, which
they almost never are in public write-ups. The corollary for this runtime, stated in the evidence
note itself: **our own ledgers are better evidence about our own harness than any external result.**
This is why this agent must read `~/.claude`'s own ledgers, dossiers, and enforcement logs before
forming any verdict, rather than importing an externally-reported "best practice" architecture
wholesale.

(Source: 14)

## 8. Evaluation methodology and limits

Two sources bound how confidently this agent should attribute an outcome to an architectural
choice. METR's *Measuring AI Ability to Complete Long Software Tasks* (2025, item 15) is an
external, independently-tracked capability trendline — useful as an outside check on whether a
platform-capability-drift finding ("the base model now does X natively") is plausible on its own
merits, separate from anything this runtime built. The DARPA AIxCC SoK (item 13) is the sharper
methodological warning: it is a systematic meta-analysis covering all seven finalists' real
architectures and outcomes, and even so its authors state attribution of the win to any single
technique **"is inherently difficult."** The operative discipline: before crediting (or blaming) an architectural choice for a
runtime outcome — a clean review streak, a ship, a regression — rule out the obvious confounds
first (cadence changes, headcount changes, an unrelated fix landing the same week) rather than
attributing the result to the one pattern that happens to be newest or most visible.

(Sources: 13, 15)

## 9. Standing decisions — do not re-litigate

Settled operator/reviewer decisions this agent must treat as closed, not re-derive from first
principles each run (sources: `CLAUDE.md` §7/§10/§13; `oversight_install.md` §0/§6):

- **Enforcement stays globally ON** (`~/.claude/.enforce`, decided 2026-08-23 — see `CLAUDE.md` §7
  for the decision record); a per-repo opt-out marker never overrides it. Do not re-propose
  disabling enforcement or report a per-repo opt-out marker as live without checking it against
  the global marker first.
- **The four model-default regressions** (07-09, 07-19, 08-03, 08-20) are closed by
  `settings_drift_guard.py` (self-heals `model`/`effortLevel` at every SessionStart, and since 2026-09-23 removes a client-written `modelSettings` block that HEAD does not carry) plus
  `pre_commit_ratchet.py` (blocks a commit that reintroduces `xhigh` or drops `effortLevel`); the
  08-20 live drift's root cause traced to the Claude Code **client itself** (org-default /
  Auto-mode), outside this repo's ability to fix directly. Do not re-open this investigation from
  scratch; if it recurs, check client-side Auto-mode settings first.
- **Opus is reserved for the two §10 review boundaries plus the §13 sanctioned-Opus extension**
  (`launch-director`, `test-architect`, `trust-architect`, `agentic-systems-architect` itself, and
  `code-quality-architect` added 2026-08-30) — never a scheduled-session default, never a worker pin. `no_unattended_opus_loops` forbids
  defaulting a scheduled session to Opus or running one in a loop; this agent's own monthly dispatch
  is deliberately a single bounded run from a `--model sonnet` session, not an exception to that
  rule.
- **The review ladder is settled policy**, not a per-run judgment call: risk-tier `trivial` gets a
  cheaper-model confirmatory pass (never zero review); a fix-and-recheck round is targeted
  falsifiability verification, not a repeated full Opus pass, capped at two targeted rounds before
  escalating back to full review; one reviewer substitutes for another at a boundary, never stacks;
  and a CODE-REVIEW full re-review round runs WARM (continue the round-1 reviewer at FULL scope;
  cold dispatch is the fallback; max two consecutive warm rounds per boundary; a risk-tier OR
  reviewer-of-record change breaks the warm chain — `CLAUDE.md` §10, 2026-08-30, #4686). Encoded machine-readably in
  `model_policy.json`'s `session_rules`. Do not propose a different cadence without new
  review-outcome-ledger data.
- **GH #4415 — ROOT-CAUSED 2026-08-27: a telemetry bug, not an enforcement gap.** The log's
  `enforce` field read `CSA_ENFORCE` (set nowhere → `false` in EVERY session, interactive
  included) instead of `_lib.enforcing()`, which returned True throughout (global marker,
  environment-independent — verified under `env -i HOME PATH`); fixed in `c9759f1` (08-25). The
  denied agent could not attribute the denial because `_lib.emit_pretooluse_deny` omitted
  `permissionDecisionReason` (fixed 08-27). A third cause of the original probe's `git add` wall:
  its `/private/tmp` directory was an UNTRUSTED workspace, where project `permissions.allow` is
  ignored. A re-probe in a scratch clone landed `GATE-3B-FIRES` with every gate self-attributed,
  and showed hooks resolve BEFORE the harness permission layer. The `loop` job (`com.oversight.csa.loop`)
  was installed and loaded 2026-08-27T18:50 MDT once its preconditions read satisfied, and later
  REMOVED entirely 2026-09-08, superseded by THE ISSUE WHEEL (`com.oversight.wheel.csa`) — see
  `oversight_install.md` §0 for the full history. Do not re-open the "headless runs log-only"
  investigation (its findings still hold for the wheel, which inherits the same gate-3b/permission-
  layer mechanics verbatim); verify the wheel's own current activation status in
  `oversight_install.md` §0 before asserting either way.
- **GH #4412 (Write-vs-heredoc permission asymmetry)** is filed, not resolved; the standing
  workaround (scheduled jobs write heartbeats/results via Bash heredoc, not `Write`) is deliberate,
  not a gap to re-flag.
- **CronCreate is disqualified as a standing scheduling mechanism** (session-scoped, in-memory,
  dies with the session, 7-day expiry); `launchd` is the only sanctioned standing trigger. Do not
  propose CronCreate as the fix for a scheduling gap.
- **Agentic security is trust-architect's lane** (operator assignment 2026-08-27, on this agent's
  own recommendation), with a written split trigger in `trust_architect_primer.md` §8 — two
  consecutive `plateaued` monthly audits, or a real incident — that trust-architect itself
  evaluates. Do not re-propose a dedicated agentic-security specialist; a candidate finding that
  merely restates the plateau⇒split doctrine against this lane is dropped. Seam: this agent judges
  an in-app agent or gate as DESIGN (wired, grounded, converging — axes 4 and 6); trust-architect
  judges the same gate as a security CONTROL (is the untrusted-input path actually closed). Same
  gate, two verdicts — filed once, cross-referenced, never duplicated.

## 10. Cost and context economics — money, not token headcount (added 2026-08-27)

This section exists because this agent's own 2026-08-27 self-audit found it had NO cost axis while
reading the oracle that measures cost, and had been grading fan-out on token headcount — the
wrong unit. **Real spend is dominated by cached prefix reads, and a bare token total hides it.**
The oracle's four token fields are `input`, `output`, `cache_read`, `cache_creation`
(`~/.claude/.agent_budget/spend.jsonl`, `tokens.*`; `~/.claude/hooks/churn_report.py` metric 5
prints them raw per agent, and its docstring states the rule: *"cache_read dominates real spend;
a bare total hides that"*). **The oracle does not price them** — every money figure below is
derived with the platform's published weights (source 16, `prompt-caching.md` § Economics: cache
reads ~0.1× base input; cache writes 1.25× at the 5-minute TTL and **2× at the 1-hour TTL this
runtime's sessions use**; output at 5× input per `models.md`'s $5/$25 card). Measured 2026-08-27
over 549 raw `spend.jsonl` lines (~28 carry `"tokens": null` — lifetime, NOT the oracle's deduped
dispatch count; re-derived 2026-08-27T21:00Z after this section's own review): `cache_read` =
**97.1%** of input-side tokens; price-weighted at the 5-minute write rate, input-side = **94.0%**
of the bill, `cache_read` alone **68.7%**, naive/real = **7.1×**; at the 1-hour write rate
`cache_read` = **59.7%** and naive/real = **6.2×**. As-of figures, not constants — the log is
append-only, so re-derive and state the write weight you used:
```python
import json, os; t={'input':0,'output':0,'cache_read':0,'cache_creation':0}
for l in open(os.path.expanduser('~/.claude/.agent_budget/spend.jsonl')):
    try: d=json.loads(l).get('tokens')
    except Exception: continue
    if not isinstance(d,dict): continue  # ~28 rows carry "tokens": null
    for k in t:
        if isinstance(d.get(k),int) and not isinstance(d.get(k),bool): t[k]+=d[k]
w={'input':1.0,'output':5.0,'cache_read':0.1,'cache_creation':1.25}  # 2.0 at the 1-hour TTL
m={k:t[k]*w[k] for k in t}; M=sum(m.values())
print({k:round(100*v/M,1) for k,v in m.items()}, 'naive/real=%.2fx' % (sum(t.values())/M))
```

The mechanics (platform source of record: the bundled `claude-api` skill, `shared/prompt-caching.md`
— cite by skill + doc, never by its version-keyed path): **prompt caching is a prefix match — any
byte change anywhere in the prefix invalidates everything after it.** Render order is tools →
system → messages; changing the tool list or the model mid-conversation invalidates the entire
cache; a fork (a sub-agent, a compaction pass) that rebuilds `system`/`tools`/`model` with any
difference misses the parent's cache entirely; the silent invalidators are timestamps in a system
prompt, non-deterministic serialization, per-user IDs in the prefix, and conditional system
sections.

Consequences for THIS roster, each an audit rule:
- **A primer or dossier is a prefix that is re-read every turn.** An agent's mandatory Read-FIRST
  payload scales cost as O(turns × prefix bytes) — growing it is multiplicative, not additive.
  **Never publish a frozen byte count here — it goes stale the moment any file it counts changes
  again**, which happened to this very bullet: a prior "re-measured 2026-08-28" figure stood here
  and no longer matched its own cited `wc -c` command by the same day, because other files in the
  same set were still being edited concurrently — exactly the frozen-number failure this primer's
  own §11 elsewhere warns about. Roughly 200 KiB for the six runtime files (`CLAUDE.md`, its
  agent definition, this primer, the evidence note, `oversight_install.md`, the recommendation
  ledger), somewhat more for the full set this agent actually reads once the repo dossier
  (Read FIRST #2) and the repo's own `CLAUDE.md` are added — re-derive the EXACT figure fresh,
  every run, with:
  `wc -c ~/.claude/CLAUDE.md
  ~/.claude/agents/agentic-systems-architect.md ~/.claude/knowledge/agentic_systems_architect_primer.md
  ~/.claude/knowledge/agentic_systems_evidence_2026_08_25.md ~/.claude/knowledge/oversight_install.md
  ~/.claude/knowledge/agentarch_recommendations.jsonl <repo>/CLAUDE.md
  <repo>/.claude/oversight/agentic-systems-architect.md`. Every audit reports the Read-FIRST prefix
  bytes of each agent it reviews the same way, computed fresh in that run, never copied from a
  prior report; a knowledge-surface expansion is judged as prefix growth × expected turns, and
  §6's lost-in-the-middle evidence is the quality half of the same trade.
- **Fan-out is NOT cheaper per token than its parent — never price it as if it were.** §1's
  4×/15× is a token band, and the cache discount is UNIFORM: it applies to the parent's turns and
  to every child's turns alike, so a 15× token fan-out is still ~15× money. (This section's first
  draft claimed "≈1.5× money" — wrong by ~10×, caught in review; the error was applying the
  per-token discount to one side of a ratio.) Worse, a sub-agent is a cache FORK: its own agent
  definition is a different system prefix, so it misses the parent's cache and pays the write
  premium on its own prefix — measured 2026-08-27, `implement` paid 64.4M `cache_creation` tokens
  across 85 dispatches. The real cache lever is PREFIX REUSE ACROSS TURNS within one agent, not
  headcount. Weigh a fan-out on whether the work is genuinely parallel (§1's structural reasons)
  and on total money across the four fields — never on a headcount discount that does not exist.
- **Model tier is a uniform multiplier** (~5× between tiers) — a real lever, but not the only one,
  and not the largest at high cache-read shares.
- **Any roster change that alters a shared tools list or system prefix mid-session is a
  cache-invalidation event** and is priced as one.

(Sources: 16, house oracle `churn_report.py`)

## 11. Self-preference — same-family judges over-rate same-family work (added 2026-08-27)

Panickssery, Bowman & Feng, *LLM Evaluators Recognize and Favor Their Own Generations* (2024):
LLM evaluators recognize their own outputs and rate them higher, and the effect is causally linked
to self-recognition — not to output quality. Any metric where the same model family both
GENERATES and JUDGES therefore carries an unknown positive bias toward "clean". This runtime's
headline review metric is exactly that shape: `churn_report.py` metric 4, the code-review catch
rate (precommit era, LIFETIME — e.g. blockers=77 / clean=726 → 0.096 on the morning of
2026-08-27 and 84 / 739 → 0.102 that afternoon; always re-derive with `python3
~/.claude/hooks/churn_report.py --days 30`, metric 4, and quote the as-of time, never a frozen
number), is an Opus-family reviewer judging Opus/Sonnet-family work, and "substitution never
stacking" swaps one same-family reviewer for another — it does not decorrelate.

Audit rules: (a) when this agent cites any review-efficacy or catch-rate number, it names the
estimator's family relationship and states the discount in prose — the blocker count is a FLOOR
on defects present, and the catch rate says nothing about review efficacy on its own (a low rate
is consistent with a perfect reviewer over clean work and with a blind one over defective work);
it is never proof the ladder works;
(b) evidence that DOES decorrelate is preferred wherever it exists — falsifiability RED/GREEN runs
against pre-fix code, mutation checks, or an out-of-family probe; (c) this agent's own verdicts
are subject to the same caveat and its reports say so.

(Source: 17 — venue and identifier cited from memory; VERIFY before citing in a report)

## 12. Cycle telemetry — the shared runtime schema (added 2026-08-28)

Every self-correcting agent loop in ANY repo — a finder/consolidator/verifier pipeline that
re-runs itself against a corpus, whatever domain it audits — emits one **cycle record** per run,
at the canonical, repo-agnostic location `~/.claude/telemetry/cycles/<system>/<cycle_id>.json`
(schema_version 1 OR 2 — v2 is purely additive over v1, see `~/.claude/telemetry/schema.json`;
`<system>` is a slug identifying the loop, e.g. `<product>-estimate-loop` — never hardcoded to one
repo's name anywhere in this runtime's own tooling). This section is this agent's CONSUMPTION
contract for that schema: what to read, what to compute, and — the hard-won rule below — what NOT
to conclude without proof.

**Schema (data, not this runtime's to redefine) — cite the real files, never hand-copy the
shape here:** the authoritative, current field list — schema_version 1's required top-level keys
(`schema_version, system, repo, cycle_id, started_at, ended_at, dispatches, calibration, findings,
cost, notes`) AND v2's nine purely-additive optional top-level arrays (`runs, reviews, changes,
decisions, issues_filed, evidence, corrections, verdicts, stages`) plus their per-item extensions
(e.g. `dispatches[].tokens_reported/.tokens_source/.tool_use_id/.agent_id/.session`,
`findings[].found_at_stage/.issue_refs`) — lives in `~/.claude/telemetry/schema.json`
(machine-checkable) and is explained field-by-field in `~/.claude/telemetry/README.md`. **Both
files are TRACKED** (corrected 2026-08-28 — a prior version of this line claimed the opposite;
re-verified 2026-08-30 with `git ls-files telemetry/schema.json telemetry/README.md`, which lists
both — that is the check to run, and it is true at HEAD independent of any ignore rule, since a
tracked file ships regardless of `.gitignore`. **Do NOT cite `git check-ignore`, or `.gitignore`
negation entries, as the justification here — whatever `.gitignore` happens to contain:**
`check-ignore` consults the INDEX by default and reports a tracked path as not-ignored no matter
which rules match it (only `--no-index` exposes the raw rule match), so its exit code conflates
"no rule matches this" with "this path is tracked" and can never establish that a file ships.
`git ls-files` can. That conflation is not hypothetical — it is how this passage went wrong the
first time: it cited "verified via `git check-ignore`, exit 1" as proof of negation entries that did
not exist, when the exit code was merely reporting the index. Two later versions then pinned the
claim to `.gitignore`'s contents in opposite directions — one false at the HEAD it was written
against; the next true when written and false the moment a pending commit landed, which is exactly
what happened. Cite tracked-ness: it does not move when ignore rules do). Only the per-cycle JSONL/JSON runtime DATA under
`telemetry/cycles/` is untracked and genuinely absent-by-default on a fresh checkout. If `schema.json`/`README.md` are
unreadable despite being tracked, declare this whole axis DEGRADED rather than trust a remembered
shape (see `agents/agentic-systems-architect.md`'s Read FIRST #5 git-state caveat, the authoritative
statement of this). **Read those two files fresh every time
when present; do not hand-maintain a second copy of this shape in this primer.** The schema has
already changed once (v1→v2) since a hand-copied block last stood here,
and that block went stale exactly the way a frozen number does — labeled `schema_version: 1` while
missing every v2 array. `hooks/cycle_telemetry.py`'s own module docstring carries the identical
v1/v2 field-by-field description as a third, load-bearing source (the module validates every
record against it), so `schema.json`, `README.md`, and the module docstring agree by
construction — this primer needs no fourth copy.

**Discovery-first computation (mirrors the spend/churn ORACLE rule, Evidence discipline) — the
ONE canonical oracle, never re-derived by hand:** `~/.claude/hooks/cycle_telemetry.py`'s
`compute_metrics()` (single record) and `aggregate_metrics()` (pooled across records) are the
exact, current, executable implementation of every derived metric this schema defines. **Read that
source before ever stating a formula, and never hand-copy the arithmetic into this or any other
doc** — a hand-copied formula drifts the moment the module changes, and a prior version of this
section did exactly that: it stood in direct, unnoticed contradiction with its own worked example
below because its formulas were re-derived from memory instead of read from the module (up to 6×
off on `usd_per_confirmed_defect`'s denominator, and structurally unable to ever match on
`plant_catch_by_slot`). Run it read-only —
`python3 ~/.claude/hooks/cycle_telemetry.py metrics <path> [--json]` (single record) or
`... metrics --system <slug> [--json]` (pooled) — and label the finding
`ORACLE: cycle_telemetry.py`. **Search `~/.claude/hooks/`, `~/.claude/telemetry/`, AND
`~/.claude/scripts/` when confirming whether an oracle script exists at all** — a search that
stops at the first two directories misses `~/.claude/scripts/render_cycle_log.py`, which also
implements `plant_catch_by_slot` for its own rendering purposes (its own docstring: "MUST mirror
cycle_telemetry.plant_catch_by_slot()"). That file is DERIVATIVE, never a second source of truth —
`hooks/cycle_telemetry.py` is the one canonical oracle for every formula; a metrics question is
answered from it, never from the renderer, even when both exist. If `cycle_telemetry.py` is ever
missing entirely (it should not be), fall back to reading the record's raw JSON directly against
`~/.claude/telemetry/schema.json` + `README.md`'s field definitions (TRACKED, not gitignored — see
the correction above; DEGRADED if unreadable), never against a formula memorized from a
prior audit, and label the finding `ORACLE: direct-computation (fallback —
cycle_telemetry.py absent)`.

**The seven derived metrics this agent consumes** — `symptom_precision`, `cause_precision`,
`duplicate_rate`, `ruling_conflict_rate`, `plant_catch_by_slot`, `usd_per_confirmed_defect`,
`consolidation_ratio` — are named here so this agent knows what to ask the oracle for and how to
INTERPRET each one; that interpretation is this agent's own judgment and stays below, but their
exact computation belongs to `cycle_telemetry.py` alone, never to this prose. Two interpretation
points are worth stating plainly, because getting either wrong once already produced a materially
different (and wrong) number in a prior draft of this section:
- `symptom_precision`'s numerator counts a verifier verdict of `ALREADY_TRACKED_ELSEWHERE`
  alongside `CONFIRMED`/`PARTIALLY_CONFIRMED` as "the symptom was real" (a re-hit on a real,
  already-known issue is still a real symptom), and its denominator is every finding the verifier
  actually judged — excluding both a `null` verdict (not yet verified) and `UNVERIFIABLE` (a
  judgment that was never reachable) — never "every finding raised." **This metric alone can
  overstate a loop's real accuracy** — see the motivating case below for why `cause_precision`
  matters even more.
- `usd_per_confirmed_defect`'s denominator is the UNION of `CONFIRMED` and `PARTIALLY_CONFIRMED`
  verdicts, never `CONFIRMED` alone — a partially-confirmed finding still cost real money to raise,
  consolidate, and verify, and excluding it overstates true cost-per-defect. `cost.total_usd`
  MUST already be spend-ledger-sourced (`cost.source == "spend_ledger"`) before this ratio is
  reported as real money; a `cost.source == "reported"` cycle record gets this ratio reported as
  `UNVERIFIED (reported-cost only)`, per the guardrail below. A `cost.source == "unavailable"`
  cycle record has no `total_usd` to divide by at all — it is the producer's own honest-refusal
  signal, a DIFFERENT category from `"reported"` (see below) — and is reported
  `UNKNOWN (source: unavailable)`, never computed from a fallback or estimate.
- `plant_catch_by_slot` groups on the identifiers actually present in
  `calibration.caught_by[]`/`missed_by[]` (which the harness in practice populates with
  BATCH-POSITION identifiers, not `calibration.slot` — every real record observed as of this
  writing carries `calibration.slot: null`) — never on `calibration.slot`, and never by checking
  whether a plant_id string literal appears inside a finding's `raised_by` (`raised_by` holds
  RAISER labels, never plant ids, so that check can never match by construction). Read
  `plant_catch_by_slot()`'s own source before reporting this metric; do not re-derive its grouping
  key from this prose.

**Why `cause_precision` matters most (a motivating case, kept generic — illustrative, not an
authority tied to any one repo/run):** in an early real run of a loop like this, a human manually
read nine finder reports by hand and found the finders right about the SYMPTOM 8 times out of 9,
but right about the ROOT CAUSE only 1 time out of 9. `symptom_precision` alone would have reported
that run as ~89% accurate; `cause_precision` reports the same run at ~11% — the number that
actually matters, because a fix aimed at the wrong cause does not fix anything. Any report that
cites `symptom_precision` without also citing `cause_precision` in the same breath has
under-reported the loop's real accuracy.

**Why `cost.source` matters (a motivating case, kept generic, same rule):** a documented case
compared a run's own harness-reported token/cost figures against reality and found the harness
field roughly 26× too low — the real, spend-ledger-derived figure was tens of millions of tokens
higher. The harness's own per-agent "tokens" field is payload-ish accounting, not billed spend.
**Any cost figure this agent reports MUST come from `cost.source == "spend_ledger"` (or this
agent's own independent re-derivation from `~/.claude/.agent_budget/spend.jsonl`) and MUST state
which source it used** — a `cost.source == "reported"` cycle costs nothing to report AS reported,
but drawing a real-money conclusion from it is exactly the mistake that produced a confidently
wrong verdict once already.

**Three-way `cost.source`, not two — `unavailable` is a DIFFERENT failure mode, never a synonym
for `reported` (added 2026-08-28, schema v2):** `cost.source` takes one of `"spend_ledger"`,
`"reported"`, or `"unavailable"` (`~/.claude/telemetry/schema.json` — TRACKED, see the
git-state correction above). `"unavailable"` is the
producer's own HONEST-REFUSAL signal — `hooks/cycle_telemetry.py`'s `resolve_cost()` could not
confidently attribute spend to this cycle and declined to guess, carrying a human-readable
`cost.reason`. That is the mechanized form of this very primer's own anti-fabrication guardrail,
not a violation of it — treat it as its own category, **never** folded into the `"reported"`
bucket above: a record that honestly says "I don't know" is not the same failure as a record that
confidently reports a fabricated or 26×-low number, and conflating the two reads an honest refusal
as if it were the harness-fabrication failure mode it exists to prevent. Report an
`"unavailable"` cycle's cost as **UNKNOWN (source: unavailable — <cost.reason>)**, distinct from
the **UNVERIFIED (reported-cost only)** label used for `"reported"` cycles. Every real
`<system>/<cycle_id>` record observed as of this writing carries `schema_version: 2` and
`cost.source: "unavailable"` — do not assume `"reported"` or `"spend_ledger"` is the common case;
verify against the actual records in scope each run (see the real files under
`~/.claude/telemetry/cycles/` for a live worked example — never hardcode a specific system/cycle
name here; this primer is repo-agnostic by its own rule at the top of this section).

**Disambiguator fields, when present (v2, `dispatches[].tokens_reported` /
`dispatches[].tokens_source`):** these are the producer's own anti-laundering fields, built
specifically for the 26×-low harness-figure case above — `tokens_reported` preserves the harness's
raw (possibly untrustworthy) per-dispatch token figure rather than deleting it, and
`tokens_source` (one of `harness_reported`, `spend_ledger`, `estimated`, `unavailable`) states
where that number actually came from. When a cycle's own `cost.source` is `"unavailable"`, check
whether individual `dispatches[]` entries still carry a `tokens_source` of `spend_ledger` or
`estimated` — that is real, if partial, evidence this agent can cite even when the cycle-level
rollup could not be computed. Never silently upgrade a cycle-level `UNKNOWN` to a real number from
this alone; cite it only as a per-dispatch data point alongside the cycle-level `UNKNOWN`.

**The ledger-correspondence guardrail — mandatory before ANY cost conclusion, no exceptions
(added 2026-08-28, closing a real near-miss; extended to a 4th signal 2026-08-28, round 3):** this
agent once reached a CORRECT conclusion ("reported cost is far too low, so batching is not a cost
lever") from the WRONG evidence — it compared a run's reported numbers against spend-ledger rows
that belonged to a DIFFERENT run entirely (the audited run never reached the ledger at all; the
rows it used included an agent type that run never dispatched). Right answer, wrong instrument —
pure luck, and luck is not evidence. The real, mechanized version of this check is
`hooks/cycle_telemetry.py`'s `resolve_cost()` — it is the oracle for correspondence too, not only
for the derived metrics; **read it, do not re-derive its logic by hand.** It checks FOUR signals,
not three:
1. **TIME WINDOW** — every candidate ledger row's timestamp falls inside `[started_at -
   tolerance_sec, ended_at + tolerance_sec]`. `ended_at: null` (the schema's own "still in
   progress" state) means the window cannot be bounded at all — `resolve_cost()` REFUSES outright
   in that case (`cost.source: "unavailable"`), and this agent reports the same:
   **UNVERIFIED (cycle still in progress — no ended_at)**, never an open-ended window treated as
   acceptable. `tolerance_sec` defaults to `DEFAULT_LEDGER_TOLERANCE_SEC = 600.0` (±10 minutes)
   and is bounded to `[MIN_LEDGER_TOLERANCE_SEC, MAX_LEDGER_TOLERANCE_SEC] = [0.0, 3600.0]`
   (0 seconds to 1 hour) — an out-of-range value is itself refused, never silently clamped. State
   the actual tolerance used; never say "the tolerance used" without naming its real value.
2. **AGENT-TYPE SET** — the distinct `agent_type` values present in the candidate ledger rows are
   a SUBSET of the distinct `agent_type` values the cycle record's own `dispatches[]` actually
   list. A ledger row for an agent_type the cycle never dispatched is not noise to average away —
   it is proof the slice is contaminated by a different run, exactly the failure mode above.
3. **PER-TYPE COUNT** — the number of candidate ledger rows for EACH agent_type equals the number
   of dispatches of that type the cycle recorded, exactly (accounting for and STATING any known
   ledger gaps, e.g. rows with `"tokens": null` — count them, never silently drop them from the
   denominator) — any mismatch is refused rather than guessed at.
4. **IDENTITY — REQUIRED for any `spend_ledger` verdict**, not merely an optional strengthening of
   1-3. A dispatch may carry the ledger's own `tool_use_id` / `agent_id` / `session` field (schema
   v2, `OPTIONAL_DISPATCH_KEYS`). When ALL of a cycle's dispatches uniformly carry the same one of
   these fields, `resolve_cost()` matches candidate rows by that exact identity value; signals 1-3
   alone can never, by themselves, establish true correspondence — a single foreign session is
   mathematically indistinguishable from a single own session under window+type+count alone (see
   the function's own "DESIGN DECISION" docstring in `resolve_cost()`). **When NO
   dispatch in the cycle uniformly declares an identity field at all, `resolve_cost()` REFUSES
   UNCONDITIONALLY** — regardless of whether the window+type candidate set happens to span one
   session or several; there is no single-session exemption. Report this as
   **UNVERIFIED (no uniform dispatch identity declared)**. Two related, STRICTER refusal modes,
   neither a fallback: (a) any dispatch that DECLARES an identity value the ledger cannot
   corroborate 1:1 refuses the WHOLE cycle outright, even when a sibling dispatch in the same cycle
   declares no identity at all (`resolve_cost()`'s step 4a declared-identity-mismatch refusal); and
   (b) a dispatch that declares an identity field as an EMPTY STRING is also refused, as a data
   defect, never read as "no identity declared" (`resolve_cost()`'s empty-string identity guard,
   BLOCKER 2's second door). The measurement that motivated removing the old heuristic (also in
   `resolve_cost()`'s "DESIGN DECISION" docstring section, round-3 redesign): **48% of ledger rows carried
   `session: null`**, which silently emptied the old "candidates all share one session" fallback
   regardless of true ambiguity — that heuristic is REMOVED, not weakened; window+type+count alone
   can never yield a `spend_ledger` verdict without identity.

A shared correlation ID (signal 4's identity fields) is strictly stronger evidence than 1-3 alone
and is used first when present; window+type+count alone can never substitute for a missing
identity declaration — there is no fallback path from signal 4 back down to 1-3. **The producer
already records the fields needed to verify this for free** —
a `resolve_cost()`-produced cost block carries `cost.window: {start, end, tolerance_sec}` and
`cost.matched_rows` (the count of ledger rows actually attributed) whenever
`cost.source == "spend_ledger"`; read those fields directly rather than re-deriving the window or
row count from `dispatches[]` and `started_at`/`ended_at` by hand when they are already present.

**Any one of signals 1-4 failing, being impossible to check with the data on hand, or hitting the
`ended_at: null` / no-uniform-identity-declared refusal cases above, means the cost finding is
recorded `UNVERIFIED` — not hedged with "likely" or "probably," not asserted with a caveat buried
at the end.** State plainly which signal failed and why. This is the same evidence discipline this
primer already applies everywhere else (Evidence discipline, §10's oracle-provenance rule, §11's
same-family discount) — a cost conclusion is not exempt from it just because the arithmetic is
trivial once the (possibly wrong) slice is in hand.

**Degradation is honest, never improvised:** a `system` slug with zero files under
`~/.claude/telemetry/cycles/<system>/` is reported DEGRADED for that system, explicitly, in the
same run that reports full findings for a system that HAS emitted records — one system's silence
never becomes an assumption about another system's, or about the same system's next run.

## 13. Feedback-loop and delivery-flow design doctrine (added 2026-08-29)

Doctrine for auditing — and PRESCRIBING a concrete redesign of — any feedback loop in scope: an
agent self-correction loop (§12's cycle telemetry), this runtime's own review/commit pipeline, or
the human operator's own edit→verify→commit working loop with Claude Code. §2's grounded-vs-
ungrounded test stays the narrow case (does a model's self-critique check against something
checkable); this section is the general theory any loop is judged against, machine or human. A
finding on axis 9 (below) always names the SPECIFIC mechanism it would change — gain, latency,
batch size, or the stop condition — never "the loop seems imperfect."

**Vocabulary (control theory).** A closed loop is Wiener's own definition (formalizing, five years
earlier, Rosenblueth, Wiener & Bigelow's 1943 modeling of purposeful behavior as feedback-driven
error-correction — source 19): a sensor's reading is compared against a target and a correction is
fed back to shrink the gap — his own examples are a railway signalman's telltale and a thermostat's
damper. **Negative feedback** opposes the current
departure from target (a governor slowing an overspeeding engine); an **open-loop** system has no
such return path at all — logging a defect with nothing that reads and acts on the log is
open-loop, whatever it calls itself. **Gain** that is too high does not merely correct faster —
Wiener's own math (`Y = X − λAY`) shows it can drive the loop into **unrestrained oscillation**: a
review ladder that escalates to the most expensive check on every finding, or a fix-and-recheck
cycle with no round cap, is a high-gain loop with no damping (CLAUDE.md §10's own two-round cap
before escalating back to full review is this runtime's own damping term, not an arbitrary limit).
**Loop latency / dead time** (Smith's 1957 dead-time-compensation paper, the origin of the "Smith
Predictor") is a separate failure axis from gain: a loop can be correctly grounded and
proportionate and still be too SLOW for the cost of what it exists to catch — a monthly audit
cadence is a 30-day dead time; a per-commit gate is near-zero. **Hysteresis** — an instrument or
process whose response differs depending on whether the input is rising or falling — behaves like
a variable extra lag on top of true dead time. Every loop-design finding names which failure mode
it is (mis-tuned gain, excess latency, or hysteresis-like inconsistency), not "the loop seems off."

**Boyd's OODA loop is about tempo AND orientation, not raw speed alone** — his own briefings frame
the goal as acting "more inconspicuously, more quickly, and with more irregularity" than an
opponent, never merely "faster," and his own diagram foregrounds Orientation as the hub shaping
everything else, wired with explicit feedback loops, not a bare 4-box sequential cycle. The
popular "whoever loops fastest wins" reading is a DOCUMENTED oversimplification Boyd himself never
formalized (Osinga's dissertation calls it exactly that; a British Army officer's harder critique
states flatly that a literal sequential OODA "does not... model how real organizations act"). The
audit corollary: a faster loop that is not also correctly ORIENTED — grounded, per §2 — is Huang
et al.'s ungrounded-self-critique failure restated in OODA vocabulary, not an improvement.
Speeding up a loop's cadence is never itself the fix; it is only a fix once §2's grounding question
is already answered yes.

**A loop without a real stop condition isn't closed, it's just logging (jidoka/andon).** Ohno's
Toyota Production System gives every line worker authority to halt the line the instant a defect
signal appears — precisely documented by Spear & Bowen's HBR study of real Toyota plants: pull a
cord, a light turns on, and if unresolved within a fixed interval the line actually stops. The
audit test this yields: does the loop's "stop" signal carry real authority, and is that authority
actually exercised, not merely logged? A working instance already on disk: the nightly
finishing-loop's own review-blocker handling refuses to commit over a recorded blocker and
requires an actual re-review before proceeding — a real stop, exercised, not merely recorded.
Contrast that with axis 4's existing false-negative case (a Stop/PreToolUse emitter registered in
no hook) — the identical theoretical failure, jidoka with no authority, now named by source.

**Theory of Constraints (Goldratt): throughput is governed by the single tightest bottleneck.**
An hour lost at the bottleneck is an hour lost for the whole system; an hour saved at a
non-bottleneck is a mirage (widely-attested paraphrase of the book's teaching, not a page-verified
quote — see the evidence note). Before recommending a new gate, reviewer, or verification layer
anywhere in a pipeline, axis 9 asks whether that step is actually the system's CURRENT
constraint — a review layer added at a non-bottleneck step does not raise throughput and can hurt
it by piling up work-in-process ahead of the real constraint (a growing parked-item backlog; a
recommendation ledger of `open` entries nobody is re-scoring). This cuts only ONE way: §9's
standing decisions (e.g. gate 3b's pre-commit review boundary) are never re-derived from a ToC
argument that they sit at a non-bottleneck — that is the identical first-principles re-litigation
§9 already forbids, restated in bottleneck vocabulary, and is dropped rather than proposed.

**Small batches shorten the loop and bound the cost of a wrong turn** (Reinertsen's queueing-
theory treatment of batch size and cost of delay; Ohno's own practice of aggressively shrinking lot
sizes and changeover times — the concept is corroborated by an HBR study of real Toyota plants,
though no verbatim Ohno sentence for it could be sourced, so treat "lower the water level to expose
the rocks" as this discipline's own summary of that practice, not an Ohno quotation — problems
large batches and high inventory otherwise hide). This runtime's own path-scoped, one-item-at-a-time commit discipline
(CLAUDE.md §3; the finishing loop's per-item 3-strike design) IS small-batch flow already
implemented — a finding that an agent batched several unrelated fixes into one commit is a
small-batch violation with a named cost (bigger blast radius per wrong turn, slower localized
feedback), not a style nit.

**DORA's delivery metrics are the empirically validated org-level proxy for delivery-loop
health.** **⚠ MODEL UPDATED 2026-09-16 — read this before citing any figure below.** DORA's
current (2025) model is **FIVE metrics in TWO factors**, not the four keys:
**Throughput** = lead time for changes · deployment frequency · **failed deployment recovery
time** (moved here from stability); **Instability** = change fail rate · **rework rate**
(unplanned deployments resulting from a production incident). The category was renamed
"stability" → "instability" deliberately, because these metrics *detect problems* rather than
confirm health. **And the Elite/High/Medium/Low tiers are RETIRED** — replaced by seven team
archetypes from cluster analysis; a full-text search of the 2025 report returns zero hits for
"Elite." Full treatment, with attribution grades:
`~/.claude/knowledge/devops_architect_primer.md` §1 (`devops-architect`'s lane).

The **2024** figures below are therefore HISTORICAL and must be cited as such, by edition, never
as current: elite performers showed 127× faster lead time, 182× more deployments, 8× lower
change-failure rate, 2293× faster failed-deployment recovery than low performers (cite the 2024
report specifically — a widely-repeated "208×" figure traced to no confirmable primary source and
should not be cited). That same report's finding that its Medium cluster had a LOWER
change-failure rate than its High cluster is the operative caveat, and it survives the model
change intact: throughput and stability are correlated but **separable**, so a loop that got
FASTER this month is never itself evidence it also stayed SAFE — check both, independently, every
time. The 2025 model reinforces this by splitting the factors explicitly.

**Seam with `devops-architect` (added 2026-09-16):** that seat measures these metrics against the
**product's deploy pipeline**; you measure them against **this runtime's own agent loops and
ledgers**. Same metric family, different subject. **When either of you cites DORA in a context the
other touches, name the edition** — the two primers previously taught mutually exclusive models,
which is exactly the cross-surface contradiction `consistency-auditor` exists to catch.

Mapped onto this runtime's own available ledgers (§7's "our own ledgers are the best evidence"
rule, applied here rather than to an external benchmark): deployment frequency ≈ items landed per
loop run / commit cadence; lead time ≈ issue-filed-to-fix-committed latency; change failure rate ≈
review-blocker rate (§11's same-family discount still applies) and park/rollback rate; failed-
deployment recovery ≈ park-to-landed-fix latency; **rework rate ≈ the share of loop items that are
re-opens or fix-the-fix commits** (the new fifth metric — this runtime has the data and was not
reading it). A finding that cites only one of these proxies has under-reported the loop's health,
the same rule §12 already applies to symptom-vs-cause-precision.

**Continuous Delivery's thesis (Humble & Farley): fast, staged, automated feedback is what makes
frequent change safe** — the "deployment pipeline," and its explicit warning that long-lived
branches recreate "integration hell." This runtime's local-CI-before-push, pre-commit review gate,
and per-item path-scoped commits already ARE a deployment pipeline in this sense; a proposed
change to that pipeline is judged on whether it preserves fast/staged/automated feedback or
reintroduces a slow, manual, or big-batch step.

**The Three Ways (Kim, Behr & Spafford's *Phoenix Project*; formalized in *The DevOps Handbook*)
are the synthesis lens** — and the direct answer to "how do we code/function more efficiently and
stay on track," extended here from delivery pipelines to the human operator's own working loop:
**Flow** — is work visible and small-batched, with defects stopped before they flow downstream (a
growing parked-item backlog, or a pile of unscored ledger entries, is a Flow violation, not
background noise)? **Feedback** — is it fast, constant, and flows back to whoever needs it (a slow
or ambiguous signal — a CI queue, an unclear partial pass — is a Feedback violation even when the
underlying check is correct)? **Continual learning** — does an incident actually become a standing
rule, or only a one-off fix? This runtime already does the third one visibly (CLAUDE.md's own
recurring pattern of "added after incident X" bullets IS Third-Way learning in practice) — this
axis's job is to verify that pattern holds, and flag a REPEATED failure that has NOT yet been
captured as a standing rule.

**A noisy or non-actionable signal gets ignored — a distinct failure mode from no loop at all.**
Google's own measurement found roughly 16% of ~4.2M tests exhibited flakiness at a scale large
enough to push engineers toward treating CI failures as noise (Micco et al.; independently
corroborated by a separate peer-reviewed flaky-test study); Google's own SRE book names the
identical failure for paging and prescribes the fix as a design constraint: "every page must be
actionable." Generalized: a hook, gate, or ledger entry that fires often but is routinely dismissed
or overridden is functionally Google's alert fatigue, and is reported as a telemetry-truth finding
(axis 5), never excused as "the checker is just noisy."

**Goodhart's Law: a correction signal that becomes an explicit target is at risk of being gamed**,
degrading the very thing it was meant to measure. This is not a new caveat this section invents —
CLAUDE.md §10 already writes explicit anti-gaming rules against exactly this (classifying a
commit's risk tier from a subset of paths chosen to obtain a cheaper review; splitting one logical
change across commits to dodge full review on the risky half) — axis 9's job is to check those
written rules are actually being followed, the same discipline §9's standing-decisions list already
applies elsewhere: name the gaming risk, don't re-derive the rule from first principles.

**Why the operator's own "flow" is not a metaphor here.** Csikszentmihalyi's documented
preconditions for a flow state are exactly three: a challenge-skill balance, and "clear proximal
goals and immediate feedback about the progress that is being made" (his own later restatement,
co-authored with Nakamura, of the same framework popularized in the 1990 book). This is the
literal scientific grounding for why a well-scoped single ranked item beats an open-ended "audit
everything" (clear goal), why a fast local check beats waiting on a slow or ambiguous CI signal
(immediate feedback), and why routing mechanical work to a cheap/fast model tier while reserving
Opus for genuine judgment calls (`model_policy.json`'s own escalation ladder) is a flow
precondition, not merely a cost optimization — a challenge-skill MISMATCH (an expensive reviewer on
trivial work, or a cheap model thrown at a genuine judgment call) breaks flow independent of
whether the work still gets done correctly. Violating any one of the three measurably disrupts the
operator's own working loop; this is the axis-9 lens for "help us stay on track and gain flow,"
evaluated against real evidence (ledger latencies, ask-gate frequency, rework rate), never vibes
about productivity.

(Sources: 18–32)

## 14. Agentic software-factory design doctrine (added 2026-08-29)

Doctrine for the axis-10 capability: designing, or judging the SHAPE of, a repeatable multi-agent
production pipeline — a distinct question from auditing an EXISTING system's internals (axes 1-9,
and axis 11's per-pattern fit).
Extends §1's start-simple gate; does not replace or re-litigate it.

**A sharper, later decision framework than §1's original three vendor guides.** Anthropic's 2026
follow-up to *Building Effective Agents* names exactly THREE scenarios that justify multi-agent
complexity — **context pollution** (an earlier subtask's accumulated context would derail a later
one), **parallelization** (a search space too large for one agent to cover serially), and
**specialization** (genuinely different tools/prompts/domains per task) — and states the overhead
plainly: multi-agent runs **3–10× the tokens of a single-agent approach for the same task** (a
different, non-contradictory baseline from §1's 15×-vs-single-chat figure — state which baseline a
citation uses, never blend the two into one number). Its own prescribed FIRST lever, before adding
an agent at all, is cutting token usage per call — naming the Tool Search Tool specifically, the
exact deferred-tool-loading pattern this runtime's own `ToolSearch` already implements. Axis 10
applies this three-scenario test as the operative start-simple gate, sharper than "a specific
structural reason": a proposed pipeline that names none of the three is a §1 finding regardless of
how it is justified in prose.

**Context isolation is a platform property, not a design choice this agent grants or withholds.**
The Claude Agent SDK's own subagent model: each subagent "starts fresh unless... a fork," only its
FINAL message returns to the parent, and — a hard platform constraint — **a subagent cannot itself
spawn a subagent** (the dispatch tool is never granted to a subagent's own tool list). A proposed
two-level-deep fan-out is invalid on this platform outright, not merely expensive; axis 10 rejects
such a proposal on this ground alone, before even reaching §10's cache-fork cost analysis (which
still applies on top: each fork is a cache miss on the parent's prefix and pays its own write
premium — §10, unchanged by this section).

**A pipeline-vs-parallel split is Anthropic's orchestrator-worker pattern, made concrete at the
tool level.** Anthropic's own production research system fans a lead agent out to isolated
parallel subagents and runs a verification/citation-check gate AFTER synthesis — and documents its
own failure mode plainly: a fully synchronous orchestrator "can be blocked while waiting for a
single subagent to finish." Where this session's own orchestration tooling exposes a staged
multi-agent primitive, its documented default is exactly the fix for that failure mode: stage
independently per item with NO barrier unless a stage genuinely needs every prior item's result at
once (a barrier reserved for real cross-item synthesis — e.g. deduplicating findings before an
expensive verification pass, or an early-exit when a discovery stage found nothing). This is a
platform-tool behavior, cited and verified the same way axis 7 verifies any platform-capability
claim (the tool's own current spec, not a hand-copied restatement) — never asserted as a written
runtime policy under `~/.claude/`. A proposed design that reaches for a barrier merely because "the
stages are conceptually separate," with no cross-item dependency named, is repeating Anthropic's
own documented blocked-orchestrator failure, not a stylistic preference.

**A real, named, production case study — Stripe's "Minions" (Stripe's own 2026 engineering post),
not a hypothetical.** Unattended agents turn a Slack task into a complete PR: each run starts in
an **isolated, pre-warmed sandbox** (no production access); verification is **cost-bounded, not
unbounded** — "at most two rounds of CI... If tests fail after an initial push, we prompt the
minion to fix... and push a second time, but are then done"; and a **mandatory human checkpoint**
sits before the hard-to-reverse step (an engineer reviews and opens the PR). Scale claimed: over a
thousand PRs merged weekly, entirely minion-produced. This is the external benchmark axis 10
checks a proposed factory against.

**This runtime's own THE ISSUE WHEEL job (formerly the nightly finishing loop, whose worked
mechanics it absorbed verbatim when it superseded that job 2026-09-08) is a convergent,
independently-arrived-at instance of the same pattern — the reference implementation, not a
hypothetical, for every future factory proposal.** Side by side with Stripe's own description: worktree-isolated execution (≈ Stripe's
isolated devbox); a BOUNDED retry structure — capped hook-rewrite retries, capped commit-contest
retries, a global 3-strike stop (≈ Stripe's hard 2-round CI cap, same shape: bounded, never
open-ended); and a mandatory review gate immediately before the hard-to-reverse step (gate 3b's
pre-commit review — never skippable — ≈ Stripe's pre-merge human review). It also carries hardening
Stripe's own post does not describe: snapshot-diff-CLASSIFY leak detection (proving a parallel
writer touched only its declared scope, rather than merely trusting isolation) and a
NON-DESTRUCTIVE undo (`apply -R` + `restore --staged`) so a denied or blocked item never leaves the
shared tree dirty. That two independently-built systems converged on isolate → bound-the-retries →
gate-before-commit is itself evidence the pattern generalizes, not a coincidence to discount.

**The five-point decision procedure axis 10 applies to every proposal or judgment** (a finding or
proposal on this axis states its answer to each, not a prose impression):
1. **Single-agent-first** — does one of the three named scenarios (context pollution,
   parallelization, specialization) actually apply? If none, the proposal is a §1 finding.
2. **Pipeline vs. a real barrier** — is genuine cross-item synthesis needed, or does a no-barrier
   pipeline dominate (the orchestration tool's own documented default, verified as a
   platform-capability claim per axis 7 — and the fix for Anthropic's own documented
   blocked-orchestrator failure)?
3. **Does it need FILESYSTEM isolation** (a worktree/sandbox), or does SDK-level context isolation
   already suffice? Filesystem isolation is priced against its real cost (setup/disk; a real
   measured per-worktree cost exists — CLAUDE.md §2 records ~1.95 GB for one product repo's
   `node_modules`, never assumed identical elsewhere) and reserved for genuine concurrent writers,
   never defaulted to.
4. **Where does the mandatory verification/review gate sit** — BEFORE the hard-to-reverse step
   (this runtime's gate 3b; Stripe's pre-merge review), never after.
5. **What is the stop condition** — a capped retry count with an explicit park-vs-hard-stop
   distinction (this runtime's own pattern; Stripe's 2-round CI cap), never an unbounded retry. An
   unattended factory with no answer to this question is not a design, it is a runaway-loop risk.

A proposal answering all five is delivered as a NAMED target design — a concrete component list,
data/control flow, and gate placement — never a vague direction like "add more review here."

(Sources: 33–35, plus 1–3 already cited in §1)

## 15. The pattern catalog — when, where, why, and why NOT (added 2026-08-30)

> **Reference corpus (added 2026-08-31):** `~/.claude/knowledge/karpathy/corpus.md` —
> distilled primary-source notes on Software 2.0, HydraNet, BEV-space fusion, DenseCap,
> AutoResearch's bounded keep/revert loop, agentic engineering, and minimal-implementation
> pedagogy, each with a generic applicability index. Cite it when a pattern-fit judgment leans
> on one of these mechanisms; its evidence-quality notes state which sections are primary-read
> vs secondary-corroborated.

Doctrine for **axis 11 (pattern fit and selection)**. These twenty patterns are the working vocabulary
of agentic design; this section is what lets a finding say *"this reaches for debate where routing plus
one grounded check would do"* instead of *"the architecture seems heavy."* Per-pattern evidence, every
source's verification tag, and the could-not-source list live in
`agentic_patterns_evidence_2026_08_30.md` (Read-FIRST #7), cited `[patterns-evidence: <pattern> / S<n>]`.

**Four rules govern every use of this section.**
1. **Cross-reference, never restate.** Where a row points at §§1–14, that section remains
   authoritative for its own scope; §15 adds only what it does not cover. A §15-vs-§§1–14 conflict is
   itself a finding, not something to resolve silently in favour of the newer text.
2. **Platform precedence.** Rows marked `[plat]` are platform-dependent. **Where §15 conflicts with the
   bundled `claude-api` skill's `shared/` docs or the installed client's `sdk-tools.d.ts`, the platform
   source wins and §15 is the finding** (axis 7). AA-0035 is the ledger record of what a stale primer
   clause costs.
3. **Cost bands name their baseline inline, always.** §14's no-blending rule binds here: `3–10× vs
   single-agent` and `~15× vs single chat` are different measurements. An unbaselined multiplier is a
   defect.
4. **Evidence grade is stated, never implied.** `primary-measured` · `vendor-guidance` ·
   `practitioner-consensus` · `no-primary-source`. **Reporting a `no-primary-source` pattern as though
   it were evidenced is a finding-quality defect** — several of these twenty are substantially
   practitioner folklore, and saying so plainly is the point, not a hedge.

### 15.1 Selection table

`[plat]` = platform-dependent · `[lane]` = another agent owns the doing (see 15.4)

| # | Pattern | WHEN (trigger) | Dominant WHY-NOT | Cost band (baseline named) | Cheaper first | Evidence |
|---|---|---|---|---|---|---|
| 1 | Prompt Chaining | Step list writable before seeing input | Error compounding; self-conditioning worsens it and model size does not fix it | direction only, no multiplier sourced | one well-prompted call + retrieval | vendor-guidance |
| 2 | Routing `[plat]` | Distinct categories AND classification is accurate | **Routing plateau** — routers converge far below oracle, failing exactly on the hard tail; adversarially invertible | `>2× cost cut vs all-GPT-4`; `up to 98% vs GPT-4 alone` | single generalist prompt | primary-measured |
| 3 | Parallelization `[plat]` | Subtasks genuinely independent; aggregation cheap | **Aggregator noise is its own error term**; more scaffolding measurably hurts | `~15× vs single chat` (agentic alone `~4× vs single chat`) | one agent, serial | primary-measured |
| 4 | Reflection | An external checkable signal exists | Ungrounded self-critique degrades the answer (§2) | +1 critique +1 revision per round; no cited multiplier | one prompt with explicit success criteria | primary-measured |
| 5 | Tool Use `[plat]` | Enumerable actions needing typed args; <20 tools = flat list | Hallucinated names/args are routine; **unbounded tool loops** | `~0.15× vs all-defs-loaded` (58+ tools) | prune the set; tighten descriptions | primary-measured |
| 6 | Planning | Structure knowable AND static | **LLMs are weak at plan generation** (34.3% valid, GPT-4/Blocksworld); fixed plans are brittle | +1 pass (prompt-only); ADaPT cost unverified | "plan then solve" in one prompt | primary-measured |
| 7 | Multi-Agent | Parallel low-interdependency work + centralized topology | Failure is **architectural, not capability**; can go **−70%** vs single-agent | `3–10× vs single-agent` | single agent; then centralize verification | primary-measured |
| 8 | Memory Mgmt `[plat]` | Cross-session recall compaction cannot preserve | **Poisoning ≥95% ISR**; aggressive write/retrieve = more exploitable | `~10× cheaper vs full-context stuffing` | compaction + flat append-only log | primary-measured |
| 9 | Learning & Adaptation | Trustworthy held-out eval + machine-scorable metric + a gate | **All credible evidence is OFFLINE — no online production loop is sourced**; evil-twin prompts; self-modification drift | `up to 35× fewer rollouts vs GRPO`; optimizer methods span 350×+ **among themselves**, not vs a baseline | hand few-shot + held-out eval | primary-measured |
| 10 | Goal Setting & Monitoring | Externally checkable condition, cheaper to verify than achieve | **Self-monitoring is unreliable and overconfident**; mechanical half ≠ self-report half | no sourced multiplier | a hard external check | practitioner-consensus |
| 11 | Exception & Recovery | Possibly-transient failure; side effects mid-workflow | **Context contamination: 7.1× per-step error** when the failure text rides along | `>2× call-volume cut vs unjittered` / `7.1× errors vs clean context` | classify before retry; strip error text | primary-measured |
| 12 | Human-in-the-Loop `[lane]` | Irreversible / high-blast-radius action | **Automation bias**; volume alone turns a real gate into theater | no measured multiplier exists | risk-tiered routing, not a blanket gate | practitioner-consensus |
| 13 | Retrieval (RAG) | Knowledge exceeds window / changes fast / per-tenant | **Hard dimensional ceiling on embeddings**; context rot starts inside the window | no clean multiplier (real gap) | BM25 + off-the-shelf embeddings | primary-measured |
| 14 | Inter-Agent Comms `[plat]` | Independently-deployed agents across a trust boundary | **No source measures it beating plain function calls**; MCP cannot enforce its own security rules | none measured for protocol overhead | in-process calls / shared filesystem | no-primary-source |
| 15 | Resource-Aware Opt. `[plat]` | Heterogeneous difficulty + repeated prefix | Cascades are **adversarially invertible**: `+148.9%` cost, `−84.6%` accuracy | cache read `0.1×`, 1h write `2×` vs no caching | **caching before any router** | primary-measured |
| 16 | Reasoning Techniques | Combinatorial search a single pass misses | CoT **hurts** on identifiable shapes; traces are unfaithful; hard info ceiling | ToT `5–100× vs a single CoT completion`; SC `≈40× vs one greedy decode (at K=40)` | one CoT prompt, then small-K | primary-measured |
| 17 | Evaluation & Monitoring `[lane]` | Regression risk with a scorable golden set | **Judge caught 0–22% of real defects** on multi-turn agent traces | no multiplier sourced | sampled human review + A/B | primary-measured |
| 18 | Guardrails & Safety `[plat]` `[lane]` | Untrusted input or real-world action | Filtering is **bypassable up to 100%**; OWASP says RAG/fine-tuning don't fix injection | bypass rate, not a cost band | **least-privilege + sandboxing first** | primary-measured |
| 19 | Prioritization `[lane]` | Heterogeneous backlog with checkable ground truth | **No study shows an LLM ranking beating a formula or a human**; κ 0.06–0.10 vs experts | not computable | deterministic weighted-sum formula | **no-primary-source** |
| 20 | Exploration & Discovery `[lane]` | Retrieval measurably near-random on the task | A **staged non-agentic pipeline beat it** on cost and accuracy; the label is an **umbrella over ≥2 distinct mechanisms**, evidenced separately | no clean multiplier | staged pipeline; plain retrieval | practitioner-consensus |

### 15.2 The selection procedure (six points; answer each, don't impression-match)

1. **Is the WHEN-condition actually met, as written?** Not "could this help" but "does the stated
   trigger hold." Most misfits fail here.
2. **Has the cheaper-first alternative been tried and measured to fall short?** §1's start-simple gate,
   applied per-pattern. A pattern adopted without this is a §1 finding regardless of its prose
   justification.
3. **Is the pattern doing a job its layer can actually do?** The recurring structural error is a
   **probabilistic mechanism placed where a structural one is required** — a content filter guarding an
   irreversible tool (18), an LLM judge gating a multi-turn trajectory (17), a self-report standing in
   for an external check (10). Name the layer mismatch, not just the weak result.
4. **What is the cost, in §10 money terms, with its baseline named?** (Rule 3 above.)
5. **What is the stop condition?** Every pattern that loops (4, 5, 7, 11, 16, 20) needs one — pattern 1
   is deliberately excluded: a prompt chain is a *fixed* sequence, a workflow rather than an agent, so
   it terminates by construction; if it is looping, that is itself the finding. **In the mined study,
   every one of the 68 confirmed infinite-agentic-loop failures (across 47 projects) traced to a
   missing strong bound** (source 42) — that is the study's own confirmed set, not a claim about all
   agentic loops everywhere.
6. **Does the pattern's own evidence grade support the weight being put on it?** A
   `no-primary-source` pattern carrying a load-bearing design decision is itself the finding.

### 15.3 Per-pattern doctrine

**XREF rows — the existing section stays authoritative; only the delta is here.**

- **3 Parallelization → §1/§14.** New: sectioning does not merely inherit its parts' errors — the
  aggregation step contributes **its own measured error term** ("aggregator noise"), and chunking wins
  only when model noise grows superlinearly AND cross-chunk dependence is manageable (38). Independently,
  **composition itself taxes accuracy**: across a full factorial, *"the best proper subset matches or
  exceeds the five-component All-In system"* (F1 0.233 vs 0.177 on HotpotQA), attenuating but not
  vanishing with model scale (38). Anthropic names coding as a domain where this is currently the wrong
  choice (source 2). *Caveat: the composition result studies single-agent scaffolding, not sectioning —
  adjacent evidence, not direct.*
- **4 Reflection → §2.** §2's grounded-vs-ungrounded line is the whole test and is unchanged. New only:
  each round costs a full critique plus a full revision generation, and **no source gives a multiplier** —
  the round count is the knob, so an uncapped reflect loop is an axis-9 gain problem, not a cost unknown.
- **7 Multi-Agent → §1/§14.** New: failure is **architectural, not model-capability** — 14 modes over
  1,600+ traces across 7 frameworks, led by step repetition 15.7%, reasoning-action mismatch 13.2%,
  unaware-of-termination 12.4% (39). **Topology, not headcount, contains error**: independent agents
  amplified errors **17.2×** vs **4.4×** for a centralized orchestrator (40). And the sign flips by task:
  **+80.8% on decomposable reasoning, −70.0% on sequential planning** (40). *Use the per-mode figures;
  the category roll-ups disagreed across extractions.*
- **13 Retrieval → §6.** §6's lost-in-the-middle and staleness stand. New and sharper: embedding
  retrieval has a **proven dimensional ceiling** — some correct top-k patterns are unrepresentable by
  any single-vector model regardless of training, with leading models under 20 Recall@100 on trivial
  queries (48). **Context rot is confirmed by three independent benchmarks and begins well inside the
  advertised window** — only half of "32K" models hold up at 32K; a 200K-window model degrades at 50K
  (49). This cuts against "just use long context" as hard as against naive RAG. The LC-vs-RAG question
  is **genuinely unresolved**: four papers agree only that RAG is cheaper (50).
- **15 Resource-Aware → §10.** §10's money model stands; the exact multipliers are now vendor-sourced:
  cache read `0.1×`, 5m write `1.25×`, 1h write `2×` (source 16). New why-not: a cascade's **confidence
  mechanism is itself attackable**, inverting the whole premise — `+148.9%` cost, `−84.6%` accuracy,
  `+81.4%` jailbreak success, transferring black-box to unseen configurations (37).
- **16 Reasoning → §3/§4.** §3's non-monotonicity and §4's budget-dependence stand. New: **CoT actively
  hurts on identifiable task shapes** (up to 36.3% absolute drop) (55); **a CoT trace is not a faithful
  audit log** — accuracy drops up to 36% under a silent bias the stated reasoning never mentions (55),
  so *a reviewer's stated reasoning is not evidence that reasoning drove its verdict*; ToT costs
  `5–100× vs a single CoT completion` by its authors' own stated range
  [patterns-evidence: Reasoning Techniques / S2]; and test-time compute has a **hard
  information ceiling** — it *"cannot introduce new information about the ground-truth answer"*, with
  longer reasoning measurably inverse-scaling and even amplifying self-preservation expressions (56).
  **For a fact-shaped bottleneck, add retrieval, not thinking budget.**
- **17 Evaluation → §8/§11.** §8's confounds and §11's same-family discount stand — and §11 now has a
  numeric backbone: GPT-4 favoured its own answers at **+10pp** over human judges, Claude-v1 at **+25pp**
  (53). Position consistency is **65.0% (GPT-4) / 23.8% (Claude-v1)** on order-swapped identical pairs;
  verbosity-attack failure **8.7% vs 91.3%** (53). The decisive new datum: in production, an LLM-judge
  gate on multi-turn agent transcripts caught **0 of 23** confirmed defects in one batch and **22%** in
  another, emitting suspicion on 125/220 rounds while triggering **0/220** gate failures (54). **The 80%+
  MT-Bench agreement figure is single-turn; treating it as transferring to trajectory judging is exactly
  the blended-baseline error rule 3 forbids.**

**FULL rows — no existing section owns these.**

- **1 Prompt Chaining.** Use when the step list is writable in advance and you are buying accuracy with
  latency. The failure is compounding, made worse by **self-conditioning** — a model whose context holds
  its own prior errors becomes measurably likelier to err again, and **scaling the model does not fix
  it** [patterns-evidence: Prompt Chaining / S4]. A per-step inspector recovers *"up to 96.4%"* of
  injected errors — not all — at one extra call per step; and **chain SHAPE measurably changes fault
  tolerance**: a hierarchical structure showed the *lowest* performance drop at **5.5%**, versus
  **10.5% and 23.7%** for the other two structures — the extracted quote does not resolve which of
  those two is the flat ungated chain, so do not attribute a specific figure to it
  [patterns-evidence: Prompt Chaining / S5]. Note honestly: the canonical vendor source for this
  pattern carries **zero benchmark numbers**, and **no head-to-head chaining-vs-single-call benchmark
  exists** — the compounding case is mechanistic, not a demonstrated regression.
- **2 Routing `[plat]`.** Both vendor conditions must hold — distinct categories *and* accurate
  classification. The second is where it breaks: across **21 routing methods on 5 benchmarks**, methods
  converge into a narrow band **far below the oracle router**, from a *predictability bottleneck* — they
  learn averaged patterns and so fail on precisely the hard, ambiguous queries where correct routing
  matters (36). Model-tier routing is the one variant whose numbers point at **saving** — `>2× vs
  all-GPT-4` [patterns-evidence: Routing / S3] and `up to 98% vs GPT-4 alone`
  [patterns-evidence: Routing / S4]. **Those two are NOT one result and must never be blended: they
  are different systems (RouteLLM vs FrugalGPT), different baselines, different benchmark suites** —
  the evidence file states the do-not-blend rule explicitly. Both are also *model-tier* routing and
  do not transfer to capability routing among peer specialists. See 15 for how the saving inverts
  adversarially. Out-of-
  distribution collapse is real and mitigating it costs in-domain labelled data per deployment.
- **5 Tool Use `[plat]`.** Below ~20 tools use a flat list. Above that, both token overhead and
  selection accuracy degrade — 58 tools ≈ 55K tokens before the first turn, and deferred loading buys
  **85% token reduction** with MCP-eval accuracy **49%→74% (Opus 4)** and **79.5%→88.1% (Opus 4.5)**
  (41). It does **not** repeal the underlying rule (*"Limit tool count"*): it manages what is in context
  per turn. Independent of count, hallucinated tool names and wrong arguments are routine and
  model-dependent (overall success 0.73 down to 0.10 across models) (42). **Unbounded tool loops are a
  real, mined failure class** — 68 confirmed across 47 projects, **100% traced to a missing bound** (42).
  Least-privilege grants are the structural control (57).
- **6 Planning.** Extends §5's plateau rule, which stays authoritative for *when to split*. New: **LLMs
  are demonstrably weak at plan generation** — GPT-4 produced valid Blocksworld plans on **206/600
  (34.3%)**, InstructGPT-3 on **6.8%** (44). Fixed plans are brittle *by construction* against unknowable
  subtask difficulty — the stated reason adaptive decomposition beats them by up to 33pp (source 12).
  Cheapest real gain: a **prompting-only** plan step beat zero-shot CoT on every arithmetic set (44),
  which argues against reaching for a plan-and-execute architecture at all.
- **8 Memory Management `[plat]`.** Distinct from §6, which covers retrieval only. Memory is measurably
  load-bearing where it applies (removing it entirely cost ~8 SD of judged quality in the seminal
  ablation; a production memory layer cut tokens **>90%** and p95 latency **91%** vs full-context
  stuffing) (45). But: **poisoning is a query-only attack with ≥95% injection success**, and existing
  prompt-injection defenses **do not cover it** — with the design tension stated outright, *"agents
  designed to write and retrieve memory more aggressively are more exploitable"* (46). Unbounded growth
  degrades retrieval by the seminal authors' own admission, and staleness is benchmarked at a ~30%
  accuracy drop over sustained interaction (47). **Whether long context has displaced memory is
  genuinely open — report it as open** (47).
- **9 Learning & Adaptation.** Real measured gains exist (`up to 50% on BBH vs best human prompt`;
  `beats GRPO by 6–20% using up to 35× fewer rollouts`) (51). **The blunt caveat: every credible source
  optimizes offline against a fixed benchmark and ships a frozen artifact. No primary evidence was found
  for a genuinely online, continuously self-improving production loop** — treat any such claim with the
  skepticism §11 applies to same-family judging. Failure modes: **evil-twin prompts** that score well
  and are unreadable to the next human or agent, overfitting to the optimization set, non-transfer
  across model families, and — for self-modifying loops — reward hacking and **safety-property erosion
  that worsens the more autonomously the loop runs** (52).
- **10 Goal Setting & Monitoring.** **The finding is a split, and conflating the halves is the defect.**
  The *mechanical* half — an external gate checking a hard criterion — is sound and is what this
  runtime's own gates already are. The *self-monitoring* half is evidenced unreliable: self-correction
  without an external check degrades performance (source 5) — that one is solid. **The three claims
  usually stacked on top of it are NOT**: that verbalized confidence skews optimistic exactly where
  stakes are highest, that self-knowledge does not transfer across domains, and that models edit unit
  tests to pass are each `[from memory — VERIFY]` in the evidence file, two with unconfirmed citation
  metadata [patterns-evidence: Goal Setting & Monitoring / S5–S7]. **Cite them as unverified or not at
  all** — the pattern's own lesson is not to launder a weak signal under a strong one. As usually
  described (KPIs, tracking, course-correction) this is Management-by-Objectives relabeled; nothing in
  the agentic literature makes an agent's self-reported progress a reliable signal.
- **11 Exception Handling & Recovery.** **Say which half is imported.** Backoff/jitter, circuit breaker,
  bulkhead, sagas are distributed-systems doctrine (43) and assume the retried operation is idempotent —
  which an agent tool call frequently is not. What is agent-specific and measured: **retrying with the
  failed attempt still in context raises the per-step error rate ~7.1×**, and an independent-attempts
  model overestimates 3-attempt success by **17.4pp (98.6% predicted vs 81.2% actual)** (43). Retry is a
  *transient*-failure remedy; a large class of agent failures are **structural**, and retrying those
  compounds rather than recovers. A circuit breaker is blind to an agent calling a working tool with
  wrong arguments forever. **Classify before retrying, and strip the failed attempt's text.**
- **12 Human-in-the-Loop `[lane]`.** Place the gate at the **point of side effects**, before the
  irreversible step — §14 point 4 owns placement in a factory pipeline; this row owns everything else.
  **No source gives a positive measured catch rate for approval gates; every measured result is about
  their failure.** Automation bias is the central why-not: participants with a highly-but-imperfectly
  reliable aid **under-performed those with no aid**, and constant-reliability automation degrades
  vigilance within ~20 minutes (62). The vendor advocating the pattern concedes approval volume
  *"reduc[es] their ability to meaningfully consider each one"* (63). **Degradation is a function of gate
  VOLUME, not gate existence** — the same gate flips from control to theater with no code change.
  Risk-tier rather than blanket-gate.
- **14 Inter-Agent Communication.** The trigger is narrow: **independently-deployed agents crossing a
  trust boundary.** A coordinator and its own subagents in one container need none of it. MCP and A2A
  are genuinely formal specs (59), but two things must be said: **no primary source anywhere measures a
  formal protocol beating plain function calls at small scale** — every source is a specification or an
  adoption announcement — and **MCP explicitly cannot enforce its own security rules at the protocol
  level** (*"implementors SHOULD"*), while A2A mandates no TTL at all and defines the envelope, not an
  authorization model. Anthropic's own multiagent product uses a shared container and thread events with
  **no A2A/MCP** between its own agents (59). **Recorded correction:** the "10-15×" figure widely
  attributed to Cognition's *Don't Build Multi-Agents* **does not appear in that post**; the real 4×/15×
  figures are Anthropic's (source 2) — do not "correct" our citation toward the phantom number.
- **18 Guardrails & Safety `[lane]`.** Two layers, and conflating them is the failure: filtering is
  **probabilistic**, sandboxing and least-privilege scoping are **structural**. OWASP states its own
  #1 risk is not solved by the first thing teams reach for — *"RAG and fine-tuning… do not fully
  mitigate prompt injection"* (57) — and measured evasion against six commercial defenses reaches **up
  to 100%** (58). The mechanism is structural, not a patchable leak: *competing objectives* and
  *mismatched generalization* imply **safety-capability parity** (58). Decisive asymmetry: tightening a
  probabilistic filter to close bypasses **necessarily raises false positives on legitimate traffic**,
  because it cannot distinguish crafted-to-look-legitimate from genuinely legitimate. **A correctly
  scoped permission boundary has no such tradeoff and fails closed** — an agent that cannot physically
  call a destructive tool cannot be talked into calling it.
- **19 Prioritization `[lane]`. The most important honesty item in this section.** **No primary study
  was found in which an LLM ranking a work queue by value×effort×urgency×risk beats a deterministic
  formula or a human.** The closest evaluation found **Cohen's κ 0.06–0.10 ("none to slight")** against
  expert judgment and compared against **no heuristic baseline at all** (60). LLM pairwise rankings are
  **internally inconsistent**, with no model dominating on both consistency axes and inconsistency that
  does not shrink with scale (60). Position, verbosity and self-preference bias (53) all bear directly
  on a ranked backlog. And the formula itself (RICE/WSJF) is a **practitioner heuristic with no
  peer-reviewed validation** — layering an LLM on top adds measured biases to an unvalidated base.
  **Prefer a deterministic weighted-sum; reserve the model for estimating an input, never for owning the
  ranking.**
- **20 Exploration & Discovery `[lane]`.** Treat as an **umbrella over ≥2 distinct mechanisms**, not one
  pattern. Where it is real, it is measured: agentic repository exploration reaches ~64% file hit-rate
  vs ~8–14% for sparse retrievers (61). But **a fixed, non-agentic staged pipeline (localize → repair →
  validate) beat every agent-based approach on cost and, at publication, accuracy** — *"Do we really
  have to employ complex autonomous software agents?"* (61). **The comparison that matters is
  exploration-vs-staged-pipeline, not exploration-vs-nothing.** The advantage also collapses at
  granularity: line-level recall ~15–19% against strong file-level recall — scope any claimed benefit to
  region-level discovery.

### 15.4 Lane fences — five patterns another agent owns

Doctrine here equips this agent to **audit a mechanism's design**. It never authorizes performing the
activity. **A finding on a fenced row that omits its lane note is a defect.**

- **19 Prioritization → `launch-director`.** This agent's own Boundaries: *"never used to rank other
  work."* Audit whether a ranking mechanism is sound; **never produce the ranking.**
- **20 Exploration & Discovery → `sentinel`.** Audit the loop's design; sweeps are sentinel's schedule.
- **18 Guardrails & Safety → `trust-architect`** (§9). Seam: this agent judges a guardrail as **DESIGN**
  (is a probabilistic mechanism doing a structural job); trust-architect judges it as **security
  CONTROL**. Filed once, cross-referenced, never duplicated.
- **12 HITL** and **17 Evaluation & Monitoring → §9's settled review ladder.** These rows equip an audit
  of an eval or gate *design*. They are **never** grounds to propose a different cadence for this
  runtime's own gates without new review-outcome-ledger data, and never grounds to relax CLAUDE.md §4's
  ask-gates. §9 is not re-litigated by evidence from this section.

(Sources: 36–63, detailed below; full per-pattern evidence in
`agentic_patterns_evidence_2026_08_30.md`)

## 16. The `metric_command` guard — full spec (moved from the agent definition 2026-09-08)

   **`metric_command` guard — apply mechanically BEFORE running any stored command; when in
   doubt, do not run:**
   1. `shlex.split` the string; a parse failure → `UNVERIFIED`.
   2. The command must match ONE of EIGHT recognized forms, drawn from ONE shared per-form
      argument-grammar table (`agentarch_metric_check.FORM_GRAMMARS`, root-cause fix, round-4
      security review, 2026-08-30 — the single source both `validate_agentarch_ledger.guard_check`
      and `agentarch_metric_check.find_hardcoded_paths` consult; no other module defines a
      competing notion of a form's flags, arity, or positional roles). `grep` and `rg` are now
      SEPARATE forms — merging them under one flag table was itself a security defect: real grep
      and real ripgrep define DIFFERENT ARITIES for the same letters. grep's arities are verified
      live against this machine's `/usr/bin/grep` (BSD grep, GNU-compatible); rg's are sourced from
      ripgrep's own published documentation (`rg --help`/`man rg`, ripgrep 14.1.1), NOT
      live-execution-verified in this environment (corrected, round-5 security review, 2026-08-30 —
      a prior version of this doc, and of `agentarch_metric_check.py`'s own comments, overclaimed
      "verified live against this machine's `rg` 14.1.1"; in fact this machine's interactive shell
      resolves a typed `rg` through a Claude Code wrapper shell function, not a real ripgrep binary
      reachable by `subprocess.run`'s bare PATH lookup — `shutil.which("rg")` returns `None` here,
      so no `rg`-headed ledger row is actually executable in this environment at all; the arities
      themselves are still correct for real ripgrep). EVERY token beginning with `-` must be in its
      form's flag set (unlisted flag → `UNVERIFIED`):
      - `grep`: `-c -n -l -r -i -E -F -h -o --count` (all boolean) plus `-e PATTERN`
        (VALUE-consuming — never `-g`, which real grep does not recognize at all) —
        `--include=…` prefix form allowed.
      - `rg`: `-c -n -l -i -F -h -o --count` (boolean) plus `-e PATTERN`, `-g GLOB`,
        `-r REPLACEMENT`, `-E ENCODING` (ALL value-consuming — unlike grep's own boolean `-r`/`-E`
        above, this is the exact arity mismatch that made a merged flag table unsafe) —
        `--glob=…` prefix form allowed.
      - `wc`: `-l -c -w` · `ls`: `-l -a -1 -t -S` · `cat`: no flags.
      - `jq`: `-r -c -s -e` (boolean) plus `--arg NAME VALUE`, `--argjson NAME VALUE`,
        `--slurpfile NAME FILE`, `--rawfile NAME FILE` — each a TWO-token flag (never `-f`/
        `--from-file`); `--arg`/`--argjson`'s second (VALUE) token is a literal string/JSON value
        jq never reads from disk, exempt from path-bounds-checking exactly like its NAME half —
        `--slurpfile`/`--rawfile`'s second (FILE) token IS a real filesystem target jq actually
        opens and stays fully bounds-checked, never exempted.
      - `git log`/`git show`: `-n COUNT` (value-consuming) plus `--oneline --since=… --until=…
        --format=… --pretty=… --stat --name-only` (boolean/prefix; never `--output`, `-o`,
        `--ext-diff`, `--textconv`). A literal `--` is NOT one more boolean flag in that list — it
        is the one token this grammar treats as structurally special (git's own end-of-options
        marker), never "a flag that happens to be legal": it ends flag-parsing for every token
        AFTER it, so `git log -- -n secrets.txt` treats BOTH `-n` and `secrets.txt` as literal
        pathspecs, never the `-n COUNT` flag.
      - `python3 ~/.claude/hooks/churn_report.py`: `--days N`, `--json` only.
      Single-dash BOOLEAN (arity-0) flags may be CLUSTERED (e.g. `-rl` = `-r -l`, `grep -rl`/
      `ls -la`): a cluster is legal iff EVERY constituent letter is individually in that form's
      flag set AND is itself boolean — never for a `--long` flag, never for a value-consuming
      flag (clustering it would make its own value's position ambiguous), and never partially
      (one illegal or non-boolean character fails the whole cluster, not just that character).
   3. **First, the standing caveat this rule depends on: whatever (2) currently is — a flag
      allowlist, an argument grammar, or its successor — it NEVER establishes which tokens are
      paths, and no token's role can be inferred from its position alone.** A
      value-taking flag changes the role of every other positional — with `-e` supplying grep's
      pattern, grep's remaining positionals are FILE operands, so a token that reads like a pattern
      is actually a file that gets opened (`grep -c .env -e SECRET` → `.env:1`, i.e. `.env` was
      read — a DIFFERENT, corrected example from an earlier version of this line, which used `grep
      -H -c .env -e SECRET`: `-H` is not in grep's recognized flag set at all, so that exact string
      is refused for an UNRELATED reason — an unlisted flag — never by this rule specifically;
      dropping `-H` isolates the actual shape this caveat is about). Treat any token whose role you
      cannot positively establish as a path, and refuse rather than guess: `UNVERIFIED` is always
      available and is the correct answer whenever role assignment is ambiguous. This caveat holds
      regardless of what the guard's implementation currently models. **Current state (round-4
      security review, 2026-08-30; unified onto a single left-to-right consuming scanner, round-5
      security review, 2026-08-30): CLOSED for the `grep -c .env -e SECRET` shape named above** —
      `agentarch_metric_check.classify_tokens` assigns NO `POSITIONAL_ROLE` at all whenever an `-e`
      flag is CONSUMED anywhere in a grep/rg command (real grep/rg semantics: `-e` supplies the
      pattern, so every remaining non-flag token is a FILE and is bounds-checked accordingly —
      `.env` is now correctly refused). jq's own FILTER role is the mirror case, verified NOT
      symmetric with grep's: jq's filter is ALWAYS positional regardless of `--arg`/`--argjson`/
      `--slurpfile`/`--rawfile`, since `-f`/`--from-file` (the one real jq flag that would change
      this) is never allowed. Do not re-derive either rule from scratch; `classify_tokens` (item 2)
      is the single place either can drift out of sync with the other again — every downstream
      consumer (the bounds check below, and `agentarch_metric_check.find_hardcoded_paths`) reads its
      per-token classification as a lookup, never re-derives it via its own independent scan (a
      failure mode that recurred TWICE: round-4's fix replaced a flag *allowlist* with a flag
      *table* but not with an argument *scanner* — three functions still re-walked the token list
      independently with different filters, closed only by round-5's single consuming pass).

      **Four points a prior round of this doc left implicit, stated plainly (round-5 security
      review, 2026-08-30 — closing a real, working arbitrary-file-read exploit the implicit phrasing
      allowed to recur: `grep -c -e -e ../../../etc/hosts` and `grep -rl -e -e ../../../etc/ssh`
      were both guard-legal and actually executed, reading real filesystem content, because a
      RELATIVE traversal token in flag-value position was checked for an absolute/`~` prefix but
      never for `..`, and a doubled value-consuming flag let the second occurrence's own VALUE be
      wrongly re-classified as a second flag, exempting the real path that followed it):**
      - **(a) A flag VALUE is not automatically exempt from bounds-checking merely because it sits
        in "value position."** A value-consuming flag's own VALUE token (grep/rg's `-e PATTERN`,
        rg's `-g GLOB`/`-r REPLACEMENT`/`-E ENCODING`, git's `-n COUNT`, jq's `--arg`/`--argjson`
        NAME and VALUE halves, and jq's `--slurpfile`/`--rawfile` NAME half specifically — never its
        FILE half, which stays fully bounds-checked per (below) — see
        `FlagSpec.second_token_is_path`) is exempt from the FULL resolve+roots-containment check
        ONLY when it does not itself look like a real path: absolute (`/`-leading), `~`-prefixed, OR
        carrying a `..` path component are ALL bounds-checked exactly like an ordinary path token,
        regardless of position — no legitimate value of this kind is ever spelled that way.
      - **(b) A bare word (no slash, no leading `~`) IS a path candidate, not automatically
        exempt.** For `wc`, `ls`, `cat`, `git log`/`git show`, jq's own FILE operand(s), and
        grep/rg's SECOND (or any non-pattern) non-flag token, a slashless token is bounds-checked
        exactly like a slash-containing one — `cat secrets.txt` is exactly as bounds-checked as
        `cat ./secrets.txt`. The only bare-word exemptions are (1) the ONE positional ROLE a form's
        grammar assigns (grep/rg's PATTERN, jq's FILTER — see (c) for when that role doesn't even
        apply) and (2) `churn_report`'s blanket carve-out (d).
      - **(c) The "sole argument" shape is never exempted as a pattern/filter.** `rg -l <path>` or
        `grep -l <path>` — one non-flag token, no separate file operand — is a real search TARGET,
        not prose: the positional PATTERN role only applies when at least one FURTHER non-flag
        token also follows it (the ordinary `PATTERN FILE` shape; jq's FILTER role has no such
        requirement — it is always positional). A lone argument is always bounds-checked.
      - **(d) `churn_report`'s bare-word exemption is a BLANKET, form-scoped carve-out, not merely
        `--days`'s own numeric value.** This form's entire flag spec (`--days N`, `--json` only)
        never defines a path-shaped positional argument at all, so EVERY bare word in a `python3
        ~/.claude/hooks/churn_report.py ...` invocation is exempt from bounds-checking, not only
        the token that happens to follow `--days` — there is no path this form can ever smuggle
        regardless of which bare token carries it.

      Every token that names a path must resolve under `~/.claude/` — EXCLUDING
      `~/.claude/projects/` (per-session transcripts, named after the session's own cwd: a path
      under it almost always encodes a specific product repo's name and is absent from every
      OTHER session, so it is never automatically safe just because it sits under `~/.claude/`) —
      `/tmp`, or a repo being audited. A repo other than the runtime itself is NEVER named as a
      bare literal path in `metric_command`; it is expressed as `${REPO:<slug>}`, resolved at run
      time against `knowledge/repo_registry.json` via `hooks/agentarch_metric_check.py`'s
      `resolve_command`/`load_registry`. An unregistered slug is its own `unknown-repo-slug`
      violation; a bare hardcoded repo path is its own `hardcoded-repo-path` violation — both are
      enforced mechanically by `validate_agentarch_ledger.py` (which also runs
      `agentarch_metric_check.find_hardcoded_paths` internally) and by `agentarch_metric_check.py`'s
      own CLI, never left to this agent's own discipline alone when authoring or re-scoring a row.
      **A third violation class (added by `10dfa46`, 2026-08-30):** a registered or CLI-passed root
      that is overbroad, nonexistent, or not a real repo checkout (no `.git` entry) is its own
      `extra-repo-root-rejected` violation, **never silently accepted** —
      `agentarch_metric_check.root_is_acceptable` is the ONE shared acceptance test both producers
      use (`load_registry`'s JSON-registered roots and `validate_agentarch_ledger.check_ledger`'s
      CLI `extra_repo_root`), factored out precisely because the two had already drifted: the CLI
      path applied only the overbroad and isdir checks, never `.git`, and `extra_repo_root=~/.ssh`
      was live-reproduced as an accepted bounds root under which a `cat .ssh/id_rsa`-shaped command
      ran with zero violations. **A fourth reason applies to a REGISTRY entry only** (never a
      CLI-passed root — that path never reaches this check): a root containing whitespace is
      rejected before `root_is_acceptable` even runs, since substituting it into a command string
      would silently mis-tokenize at `shlex.split` time — reported the identical
      `extra-repo-root-rejected` way. Treat a root's legality as a checked property, never an assumed one.
      No token may contain `>`, `<`, `|`, `;`, `&`, a backtick, or `$(` even inside quotes.
   4. `python3 -c`, `python -c`, `bash -c`, `sh -c`, `eval`, `xargs`, `find -exec` are forbidden
      outright.
   5. Anything else — another command, an unrecognized flag, an ambiguous token — is recorded
      `UNVERIFIED` and NOT run.
   **A ledger row `validate_agentarch_ledger.py` itself flags `id-format` or
   `metric-command-illegal`** (a malformed id, or a command this guard refuses to run at all)
   cannot be re-scored by running its `metric_command`, since running a guard-refused command to
   satisfy the re-score mandate below would defeat the guard's own purpose. Report such a row as a
   checker-as-audit-subject finding (the ledger itself failed its own schema/guard) and record it
   in the re-score table as `UNVERIFIED (guard-refused: <verdict>)` rather than a numeric current
   value, which satisfies the mandate's "every open entry gets a row in the table" requirement
   without ever executing a command the guard has already refused.

## Sources

Sources 1–17 are fully detailed (verdict tables, per-source caveats) in
`agentic_systems_evidence_2026_08_25.md`'s original curated bibliography, numbering matching that
file exactly. Sources 18–35 (added 2026-08-29, §13/§14) are cited here with their bibliographic
detail; the caveats that must travel with specific ones of them (an unverified statistic, an
unverified verbatim quote, two non-blendable baselines) are in that same evidence note's
"Feedback-loop, delivery-flow, and agentic-factory doctrine (added 2026-08-29)" section and its
"Flagged" list, not duplicated here:

1. Anthropic — *Building Effective Agents* (the start-simple doctrine, §1)
2. Anthropic — *How we built our multi-agent research system* (90.2% self-reported result; 4×/15× cost, §1)
3. OpenAI — *A Practical Guide to Building Agents* (against premature multi-agent split, §1)
4. Google — *Agents* whitepaper (model + tools + orchestration + data stores, §1/§3/§6)
5. Huang et al. — *LLMs Cannot Self-Correct Reasoning Yet* (ICLR 2024) — counter-evidence to ungrounded reflection, §2
6. Shinn et al. — *Reflexion* (NeurIPS 2023) — the canonical grounded feedback-loop result, §2
7. *Stop Overvaluing Multi-Agent Debate* (2025, preprint at fetch time) — counter-evidence to consensus-by-default, §3
8. Chen et al. — *Are More LLM Calls All You Need?* (2024) — consensus is non-monotonic, §3
9. *When To Solve, When To Verify* (2025) — compute-optimal verification vs. consensus, §4
10. Lightman et al. — *Let's Verify Step by Step* (ICLR 2024) — process > outcome supervision, §4
11. Liu et al. — *Lost in the Middle* (TACL 2023) — the fact-store failure mode any KB must design for, §6
12. Prasad et al. — *ADaPT* (NAACL 2024) — adaptive decomposition, with numbers, §5
13. Zhang et al. — *SoK: DARPA AIxCC* (USENIX Security 2026) — the one real competition meta-analysis, §3/§6/§8
14. *Stop Comparing LLM Agents Without Disclosing the Harness* (2026) — the harness confound, §7
15. METR — *Measuring AI Ability to Complete Long Software Tasks* (2025) — external capability trendline, §8
16. Anthropic — bundled `claude-api` skill, `shared/prompt-caching.md` (platform doc; cite by skill + doc, never by path) — prefix-caching mechanics and silent invalidators, §10
17. Panickssery, Bowman & Feng — *LLM Evaluators Recognize and Favor Their Own Generations* (2024) — self-preference in same-family evaluation, §11 [venue/identifier from memory — verify before citing]
18. Wiener — *Cybernetics: Or Control and Communication in the Animal and the Machine* (1948, Ch. IV) — the closed-loop feedback chain, negative feedback, gain/oscillation instability, §13 [page-verified against the MIT Press text]
19. Rosenblueth, Wiener & Bigelow — *Behavior, Purpose and Teleology* (Philosophy of Science, 1943) — the pre-Cybernetics antecedent, feedback-driven goal-directed behavior, §13
20. Boyd — *Patterns of Conflict* / *The Essence of Winning and Losing* (1976–96 briefings), as reproduced and analyzed in Richards, *Boyd's OODA Loop* (Necesse, 2020) — the OODA loop, tempo-and-orientation not raw speed, §13 [Richards article page-verified]
21. Osinga — *Science, Strategy and War: The Strategic Theory of John Boyd* (2005 dissertation; 2007, Routledge) — the documented "fastest loop wins" oversimplification and its critics (incl. Storr, Hankins 2021, Van Riper via Brown 2018), §13
22. Smith — *Closer Control of Loops with Dead Time* (Chemical Engineering Progress, 1957) — loop latency/dead time, the "Smith Predictor"; Lipták (ed.), *Instrument Engineers' Handbook, Vol. 1* (2003) — hysteresis as a variable-lag failure mode, §13
23. Goodhart — *Problems of Monetary Management: The U.K. Experience* (1975); Strathern — *"Improving ratings": audit in the British university system* (European Review, 1997) — Goodhart's Law and its canonical compressed restatement, §13
24. Ohno — *Toyota Production System: Beyond Large-Scale Production* (1978/1988); Spear & Bowen — *Decoding the DNA of the Toyota Production System* (Harvard Business Review, 1999, Shingo Prize winner) — jidoka/andon, real stop-the-line authority, §13
25. Goldratt (with Cox) — *The Goal: A Process of Ongoing Improvement* (1984) — Theory of Constraints, bottleneck-governs-throughput, the Five Focusing Steps, §13
26. Reinertsen — *The Principles of Product Development Flow: Second Generation Lean Product Development* (2009) — batch-size economics, cost of delay, §13
27. Forsgren, Humble & Kim — *Accelerate: The Science of Lean Software and DevOps* (2018); DORA, *Accelerate State of DevOps Report* 2019 and 2024 (primary reports, text-extracted directly) — the Four Key Metrics and the elite-vs-low performance gap, §13
28. Humble & Farley — *Continuous Delivery: Reliable Software Releases through Build, Test, and Deployment Automation* (2010) — the deployment pipeline, fast constant feedback, trunk-based delivery, §13
29. Kim, Behr & Spafford — *The Phoenix Project* (2013); Kim, Debois, Willis & Humble — *The DevOps Handbook* (2016, publisher-hosted excerpt read directly) — The Three Ways (Flow / Feedback / Continual Learning), §13
30. Micco et al. (Google, ICSE-SEIP/ICST 2017); Luo, Hariri, Eloussi & Marinov — *An Empirical Analysis of Flaky Tests* (ACM SIGSOFT FSE 2014) — flaky signal eroding trust in a feedback loop, §13
31. Beyer, Jones, Petoff & Murphy (eds.), Google — *Site Reliability Engineering*, Ch. "Monitoring Distributed Systems" (2016, read directly at sre.google) — alert fatigue, "every page must be actionable," §13
32. Nakamura & Csikszentmihalyi — *The Concept of Flow*, in *Handbook of Positive Psychology* (2002, read directly) — the three documented flow-state preconditions, §13
33. Anthropic — *When to use multi-agent systems (and when not to)* (claude.com/blog, 2026) — the three justifying scenarios (context pollution, parallelization, specialization), 3–10× overhead, the Tool Search Tool as the cheaper first lever, §14
34. Anthropic — *Subagents in the SDK* (docs.claude.com, 2025) — context-isolation semantics; a subagent cannot itself spawn a subagent, §14
35. Stripe — *Minions: Stripe's one-shot, end-to-end coding agents* (stripe.dev engineering blog, 2026, read directly) — a real, named production agentic-factory case study: isolated sandbox, cost-bounded verification, mandatory human checkpoint, §14

Sources 36–63 were added 2026-08-30 for §15. Each is a CLUSTER (related sources under one number,
as 22/29/30 already are). **Per-source verification tags — `[read directly]` vs `[via WebSearch
snippet]` vs `[from memory — VERIFY]` — and every caveat live in
`agentic_patterns_evidence_2026_08_30.md`, not here; a §15 citation used without its caveat is an
evidence-discipline defect.** Sources cited only in that file carry no number here and are cited as
`[patterns-evidence: <pattern> / S<n>]`. Many are 2025–2026 arXiv preprints — the evidence note marks
which, and a preprint is weaker evidence than a peer-reviewed venue. **A `[plat]` prefix on a source
means that source is platform/vendor-revisable, so §15 rule 2 applies to every row it backs: the live
platform source wins and the §15 text is the finding.** Placement is always a prefix, never a suffix:

36. `[plat]` *The Routing Plateau* (arXiv:2606.07587, preprint); Ong et al. — *RouteLLM* (arXiv:2406.18665); Chen, Zaharia & Zou — *FrugalGPT* (arXiv:2305.05176) — routing's ceiling and its cost wins, §15 rows 2/15
37. Sun, Chen & Li — *When Efficiency Backfires: Cascading LLMs Trigger Cascade Failure under Adversarial Attack* (arXiv:2605.17288, preprint) — the adversarial inversion of cascade routing, §15 rows 2/15
38. `[plat]` Liu (Amazon) — *More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding* (arXiv:2605.05716, preprint); *When Does Divide and Conquer Work for Long Context LLM?* (arXiv:2506.16411, preprint) — the composition tax and aggregator noise, §15 row 3
39. Cemri, Pan, Yang, Agrawal et al. — *Why Do Multi-Agent LLM Systems Fail?* (MAST; arXiv:2503.13657, NeurIPS 2025 poster) — 14 failure modes over 1,600+ traces; failure is architectural, §15 row 7
40. Kim, Gu, Park et al. — *Towards a Science of Scaling Agent Systems* (arXiv:2512.08296) + Google Research blog; Hasan & BusiReddyGari — *DPBench* (arXiv:2602.13255, preprint) — topology bounds error amplification (17.2× vs 4.4×); +80.8%/−70.0% by task, §15 row 7
41. `[plat]` Anthropic — *Advanced tool use on the Claude Developer Platform*; bundled `claude-api` skill, `shared/tool-use-concepts.md` + `shared/agent-design.md` — tool-count degradation and deferred loading, §15 row 5
42. Kokane et al. (Salesforce) — *ToolScan* (arXiv:2411.13547, preprint); Hou, Wang, Zhao & Wang — *When Agents Do Not Stop* (arXiv:2607.01641, preprint) — tool-error taxonomy; 100% of the study's 68 confirmed infinite loops (47 projects) traced to a missing bound, §15 rows 5/11
43. Yang — *Why Retrying Fails: Context Contamination in LLM Agent Pipelines* (arXiv:2605.08563, preprint); Brooker — *Exponential Backoff and Jitter* (AWS); Google SRE Book chs. 21–22 — the 7.1× cascade ratio, plus the imported retry doctrine it is distinct from, §15 row 11
44. Yao et al. — *ReAct* (ICLR 2023); Wang et al. — *Plan-and-Solve* (ACL 2023); Valmeekam et al. — *PlanBench* (NeurIPS 2023 D&B) — interleaved vs plan-first, and LLM weakness at plan generation, §15 row 6
45. `[plat]` Park et al. — *Generative Agents* (UIST 2023); Chhikara et al. — *Mem0* (arXiv:2504.19413) — memory's measured value and its cost band vs full-context stuffing, §15 row 8
46. `[plat]` Dong et al. — *MINJA* (NeurIPS 2025, arXiv:2503.03704); *From Untrusted Input to Trusted Memory* (arXiv:2606.04329, preprint) — ≥95% memory-injection success; prompt-injection defenses do not cover it, §15 row 8
47. `[plat]` Wu et al. — *LongMemEval* (ICLR 2025); *AMA-Bench* (arXiv:2602.22769, preprint) — memory staleness benchmarked; long-context-vs-memory left explicitly unresolved, §15 row 8
48. Weller et al. (Google DeepMind) — *On the Theoretical Limitations of Embedding-Based Retrieval* (arXiv:2508.21038) — the sign-rank dimensional ceiling and the LIMIT benchmark, §15 row 13
49. Hsieh et al. — *RULER* (arXiv:2404.06654); Chroma — *Context Rot*; Modarressi et al. — *NoLiMa* (ICML 2025) — three independent confirmations that degradation starts inside the advertised window, §15 row 13
50. Anthropic — *Contextual Retrieval*; Barnett et al. — *Seven Failure Points When Engineering a RAG System* (IEEE/ACM AI Engineering 2024); the four-paper LC-vs-RAG cluster (arXiv:2310.03025 / 2409.01666 / 2501.01880 / 2407.16833) — the ablation ladder, the failure taxonomy, and the unresolved contest, §15 row 13
51. Khattab et al. — *DSPy*; Yang et al. — *OPRO* (ICLR 2024); Agrawal et al. — *GEPA* (ICLR 2026 oral) — measured offline prompt-optimization gains, §15 row 9
52. Ramnath et al. — *A Systematic Survey of Automatic Prompt Optimization Techniques* (EMNLP 2025); Melcer et al. — *Textual Gradients are a Flawed Metaphor* (arXiv:2512.13598); Shao, Ren, Qian, Wei et al. — *Your Agent May Misevolve* (arXiv:2509.26354) — evil-twin prompts, instability, self-modification drift, §15 row 9
53. Zheng et al. — *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena* (NeurIPS 2023 D&B); Wang et al. — *LLMs are not Fair Evaluators* (ACL 2024); Ye et al. — *Justice or Prejudice?* — position/verbosity/self-enhancement bias with effect sizes; the numeric backbone for §11's discount, §15 rows 17/19
54. Zhang, Wang & Lei — *Catching One in Five* (arXiv:2606.10315, preprint); Pan, Arabzadeh et al. — *Measuring Agents in Production* (arXiv:2512.04123); Anthropic — *Demystifying Evals for AI Agents*; Zhu et al. — *Establishing Best Practices for Building Rigorous Agentic Benchmarks* (NeurIPS 2025) — 0–22% judge recall in production; 75% of teams run no formal benchmark, §15 row 17
55. Liu, K. et al. — *Mind Your Step (by Step)* (ICML 2025); Turpin et al. — *Language Models Don't Always Say What They Think* (NeurIPS 2023); Stechly, Valmeekam & Kambhampati — *Chain of Thoughtlessness?* (NeurIPS 2024) — where CoT hurts, and why a trace is not a faithful audit log, §15 row 16
56. Gema, Hägele et al. (Anthropic + Fellows) — *Inverse Scaling in Test-Time Compute* (TMLR 2025); *When More Thinking Hurts* (arXiv:2604.10739, preprint); Zhao, Ng & Ng — *Test-Time Scaling… Not Effective for Knowledge-Intensive Tasks Yet* (COLM 2026) — the hard information ceiling on inference-time compute, §15 row 16
57. `[plat]` OWASP GenAI Security Project — *Top 10 for LLM Applications 2025* (**a 2026 edition supersedes it; entries not extractable — treat as last-confirmed**); OWASP *AI Agent Security Cheat Sheet*; Greshake et al. — *Not what you've signed up for* (arXiv:2302.12173) — the risk taxonomy and indirect injection, §15 rows 5/18
58. Hackett et al. — *Bypassing LLM Guardrails* (LLMSec 2025, arXiv:2504.11168); Wei, Haghtalab & Steinhardt — *Jailbroken* (NeurIPS 2023); Wang, Ji et al. — *SoK: Evaluating Jailbreak Guardrails* — up to 100% evasion; safety-capability parity, §15 row 18
59. `[plat]` Model Context Protocol *Specification* + the 2026-07-28 revision; A2A *Specification*; bundled `claude-api` skill `shared/managed-agents-multiagent.md`; Cognition — *Don't Build Multi-Agents* — what the protocols actually mandate, and the in-house counter-example, §15 row 14
60. Pokharel, Farabi, Fowler & Das — *Can LLMs Rank?* (arXiv:2606.30412, preprint); Al Haddad et al. — *Prompting the Priorities* (arXiv:2510.18508) — LLM ranking inconsistency; κ 0.06–0.10 vs expert judgment, §15 row 19
61. *SWE-Explore* (arXiv:2606.07297, preprint); Agarwal et al. — *AutoDiscovery* (NeurIPS 2025); *Agentless* (arXiv:2407.01489) — exploration's real gap over retrieval, and the staged pipeline that beat it, §15 row 20
62. Parasuraman & Riley (Human Factors, 1997); Skitka, Mosier & Burdick (IJHCS, 1999); Parasuraman, Molloy & Singh (Int. J. Aviation Psych., 1993); Drew et al. — *Alarm Fatigue* (PLoS ONE, 2014) — automation bias and vigilance decay. **The first three are paywalled/scanned: citations triangulated 3+ ways, wording is PARAPHRASE not quotation.** §15 row 12
63. Shavit, Agarwal, Brundage, Adler et al. — *Practices for Governing Agentic AI Systems* (OpenAI, 2023); OpenAI — *Guardrails and human review* (API docs); Anthropic — *Effective context engineering for AI agents* — where an approval gate belongs, and the compaction-before-memory escalation, §15 rows 12/8

---

## How this agent applies it

- **Every expansion of the roster or of a single agent's scope is weighed against §1's cost band**
  — a new agent, a new voting step, or a new standing review layer needs a stated structural
  reason (parallelizable work, a real context/tool-count limit, real workflow branching), not
  "more oversight is always better."
- **Feedback loops are graded grounded-vs-ungrounded, per §2, not present-vs-absent.** A review or
  retry loop that critiques against a test result, a ledger read, or a tool's return value is scored
  as the Reflexion case; a loop that just re-reads and re-judges its own prior output with the same
  model is scored as the Huang et al. counter-case and flagged, not credited.
- **Any standing consensus/voting/debate pattern is checked against §3's full record** — real gains
  exist (self-consistency GSM8K +17.9pp; multi-agent debate GSM8K 77→85) alongside the
  non-monotonicity and 3–40× cost band. Found without a stated structural reason, it is reported
  with its cost and the open structural question, not presumed a band-aid outright.
- **The review-cost ladder itself (§4/§9) is graded as already-correct budget-aware policy** — this
  agent does not re-derive "verification is expensive" from first principles each run; it checks
  whether the ladder is actually being followed (risk-tier shortcuts taken when eligible, rounds
  capped, no silent full-Opus-every-time drift) and reports drift from it, not its existence.
- **Unit size and convergence (§5) is judged by the plateau rule, never a line/file count**: did a
  module or task loop stall or fail repeatedly before it was split, and did the split happen at that
  plateau — this is the axis, a large-but-never-plateaued file is not automatically a finding.
- **Grounding quality is checked as §6's THREE failure modes, applied to this runtime's own knowledge
  surfaces**: every primer/dossier/ledger gets checked for (a) at least one Read-FIRST pointer that
  actually reads it — an unread knowledge file is dead weight regardless of quality — and (b), for
  the recommendation ledger specifically, whether `open` entries are being re-scored on schedule
  (staleness) rather than accumulating unchecked — and (c) **judge-input sufficiency** (§6's third
  mode, added 2026-09-03 / #4831): for every judging or reviewing agent in any audited loop,
  enumerate the decision it must return and verify its INPUT ARTIFACT carries every field that
  decision depends on. Auditing a loop's dispatch shape (fan-out, which grounding docs each judge
  reads) does NOT cover this and has already missed it once — a reviewer with perfect doc access
  still cannot decide if its packet drops the field the verdict turns on. Any diff to a reviewer's
  input-construction path (packet builder, dispatch prompt) re-triggers this check off-cycle.
- **The recommendation ledger's schema** (`agentarch_recommendations.jsonl`, ten fields per line):
  `id, issued_at, claim, metric, metric_command, baseline_value, target_direction, status:
  open|moved|withdrawn, checked_at, checked_value`. `no-change` is a REPORT-table outcome only,
  never a stored status — a re-scored `open` entry that didn't move stays `open` until it
  actually moves or is withdrawn. `metric_command` is a stored shell
  string this agent runs with `Bash` on re-score; the agent definition's Read-FIRST #4 carries
  the authoritative flag-allowlist guard (`shlex.split`, per-command flag sets, path bounds) — a
  command that fails it is recorded `UNVERIFIED` and not run.
  Recommendations to be tracked are emitted IN THE REPORT in this shape, never written
  directly — the orchestrator is the writer, appending new lines and recording re-score outcomes
  back to the file; a recommendation with no measurable `metric` goes in the findings, not here.
- **Every spend/churn number follows the ORACLE rule**: if `~/.claude/hooks/churn_report.py`
  exists, run `python3 ~/.claude/hooks/churn_report.py --days 30` (read-only) and label the finding
  `ORACLE: churn_report.py`; otherwise read the four ledgers directly
  (`~/.claude/.review_state/plan_reviews.jsonl`, `~/.claude/.review_state/last_reviewed`,
  `~/.claude/.enforcement/log.jsonl`, `~/.claude/.agent_budget/spend.jsonl` — may not exist,
  report ABSENT, never zero) and label it `ORACLE: direct-ledger`. Either way, cite the number's
  provenance line and as-of date. **That report's metrics 1 (plan-review rounds) and 4
  (code-review catch rate) are LIFETIME counts — `--days` applies only to metrics 2/3/5/6** —
  never read a 7/30-day header as a lifetime catch rate.
- **Platform-capability drift is checked against a live platform source — the bundled `claude-api`
  skill's `shared/` docs** (`agent-design.md`, `prompt-caching.md`, `tool-use-concepts.md`,
  `models.md`, `model-migration.md`, `live-sources.md`), located with
  `ls /tmp/claude-501/bundled-skills/*/*/claude-api/shared/` (a repo-cwd `Glob` cannot reach them;
  more than one version-hash match may resolve — read either, they are the same corpus) and cited
  by skill name + doc + heading, never by their version-keyed temporary path. A drift finding grounded there is
  VERIFIED; only a finding sourced from model memory alone stays UNVERIFIED. (Corrected 2026-08-27:
  the previous text asserted no platform source existed, which condemned every finding on this axis
  to UNVERIFIED by construction — the skill had been bundled all along. The §-level staleness
  caveat at the top of this file is a different, still-true statement about the primer's OWN
  source-watch, not about platform docs.)
- **Before crediting or blaming an architectural pattern for a runtime outcome, §8's confound check
  runs first** — cadence, headcount, and unrelated concurrent fixes are ruled out before a finding
  attributes it to one design choice.
- **Cost is judged in money via the oracle's four token fields (§10), never in token headcount.**
  Each audit reports the Read-FIRST prefix bytes of every agent it reviews; a roster or
  knowledge-surface change is priced as prefix growth × expected turns; a fan-out is weighed on
  cache economics, not agent count.
- **Every review-efficacy number this agent cites carries the §11 same-family discount, stated in
  prose** — and decorrelated evidence (RED/GREEN falsifiability, mutation checks) is preferred
  wherever it exists.
- **§9's standing decisions are never re-litigated as findings.** A candidate finding that merely
  restates one of those eight items is dropped, not filed — the job is to notice *new* drift or
  gold-plating, not re-argue settled ground.
- **Cycle telemetry (§12) is read across every system, every repo it exists for.** The
  recommendation ledger's re-score step now also weighs each entry against any relevant system's
  derived metrics, not only its own `metric_command`; a system with no cycle records yet is
  DEGRADED for that system, stated plainly, not treated as "no problem found." Any cost conclusion
  drawn from cross-referencing the spend ledger against a specific cycle FIRST passes §12's
  ledger-correspondence guardrail — FOUR signals (time window + agent-type set + count + REQUIRED
  declared dispatch identity, never a fallback to the first three alone) — skipping that check is
  itself a finding-quality defect, not a shortcut.
- **Every loop in scope — an agent self-correction loop, this runtime's own review/commit pipeline,
  or the human operator's own working loop with Claude Code — is graded by §13's doctrine: gain
  (mis-tuned = oscillation, e.g. an uncapped fix-and-recheck cycle), latency (a correct loop that is
  simply too slow for what it catches), whether it actually closes (a real stop/escalation
  authority, exercised — the jidoka/andon test), batch size (small-batch flow vs. a bundled,
  high-blast-radius change), and signal quality (a noisy/ignored gate is Google's alert fatigue, a
  telemetry-truth finding, axis 5). A redesign proposal names the specific mechanism it would
  change; "the loop seems imperfect" is not a finding.** DORA's delivery metrics, mapped onto this
  runtime's own ledgers (§13), are the standing proxy for "is delivery-loop health improving" — the
  **2025 five-metric model** (throughput: lead time, deployment frequency, failed-deployment
  recovery time; instability: change fail rate, rework rate), not the retired four-keys/elite-tier
  framing — and are checked as two separable factors, never assumed to move together.
  The Three Ways (Flow/Feedback/Learning) are the synthesis lens for the human operator's own
  workflow specifically: is work small-batched and visible (Flow), is feedback fast and unambiguous
  (Feedback), does a repeated failure actually become a standing rule (Learning) — and
  Csikszentmihalyi's documented flow-state preconditions (clear goals, immediate feedback,
  challenge-skill balance) are the literal scientific grounding for why violating any of these
  measurably disrupts the operator's own flow, not a metaphorical use of the word.
- **On request, or when auditing a genuinely new class of repeatable agent work, axis 10 applies
  §14's factory-design doctrine and delivers a NAMED target design** — never a vague "add more
  review." The test is Anthropic's own sharper 2026 framework (context pollution, parallelization,
  or specialization — one must actually apply, or the proposal is a §1 finding), the orchestration
  tool's own pipeline-vs-barrier default (verified as a platform-capability claim, per axis 7), a
  filesystem-isolation cost check (§10's cache-fork economics plus a real measured per-worktree
  cost — CLAUDE.md §2 records ~1.95 GB for one product repo's `node_modules`, never assumed
  identical elsewhere), a mandatory gate placed BEFORE the hard-to-reverse step, and
  an explicit stop condition — the same five-point shape as this runtime's own nightly
  finishing-loop and Stripe's published "Minions" pipeline, both cited as convergent, real
  precedent, never as a hypothetical.
- **Pattern fit is judged per-pattern against §15's catalog (axis 11), and axis 11 yields to every
  other axis that can express the finding.** For each pattern PRESENT, is its stated WHEN-condition
  actually met, and has the cheaper-first alternative been tried and measured to fall short? The
  recurring structural error to look for is a **probabilistic mechanism placed where a structural one
  is required** — a content filter guarding an irreversible tool, an LLM judge gating a multi-turn
  trajectory, an agent's self-report standing in for an external check. **Absent-pattern findings are
  fenced**: "this system is missing pattern X" is pattern advocacy — the very failure this agent exists
  to catch — so it must first pass §14's three-scenario start-simple gate AND state its cost in §10
  money terms, or be **dropped, not reported**. Every cost band cited carries its baseline inline (§14's
  no-blending rule); every pattern's **evidence grade** is stated, and a `no-primary-source` pattern
  (Prioritization is the clearest) carrying a load-bearing design decision is itself the finding.
  §15's five fenced rows — Prioritization (`launch-director`), Exploration & Discovery (`sentinel`),
  Guardrails & Safety (`trust-architect`, §9), HITL and Evaluation (§9's settled review ladder) — equip
  an audit of the MECHANISM only, never performance of the activity or a re-litigation of §9.
