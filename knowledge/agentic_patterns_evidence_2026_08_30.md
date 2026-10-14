# Agentic design patterns: when, where, why, and why NOT (evidence base, 2026-08-30)

Citation-resolution surface for **primer §15**. The primer carries the compressed, operative doctrine;
this file carries the full per-pattern record — measured results with their baselines, counter-evidence,
cost bands, and every source's own verification tag. Open it whenever a finding rests on a §15 claim.

**Relationship to the other evidence note.** `agentic_systems_evidence_2026_08_25.md` covers primer
§§1–8 (sources 1–17) and is unaffected by this file. Where a pattern here overlaps a primer section,
this file ADDS to it and says so; it never restates or silently contradicts it. On any conflict, the
primer section is authoritative for its own scope and the conflict is itself a finding.

**How to cite from a report.** A source that has a primer Sources number (36+) is cited by that number.
A source living only here is cited as **`[patterns-evidence: <pattern> / S<n>]`** — e.g.
`[patterns-evidence: Routing / S3]`. Never cite this file by section number alone.

**Verification tags are the researchers' own and are preserved verbatim.** `[read directly]` = the page
or PDF was actually fetched and read in the research pass. `[via WebSearch snippet]` = a live extracted
quote from the indexed page, not a full render. `[from memory — VERIFY]` = not fetched; **never
load-bearing**. A caveat travels with its source; using a source without its caveat is an
evidence-discipline defect, exactly as for sources 1–35.

**Provenance.** Eight parallel primary-source research passes, 2026-08-30, ~299 KB raw. 120 sources
tagged `[read directly]`, 65 claims explicitly flagged unverified/from-memory. 85 distinct arXiv IDs,
**zero future-dated**. That was a mechanical check run ONCE, on 2026-08-30, against the raw research
passes — which were session scratch and are **not preserved**, so it is **not re-runnable by a later
reader**: treat it as a recorded one-time result, not a standing guarantee. What IS re-runnable
against this file: `grep -ohE "[0-9]{4}\.[0-9]{4,5}" agentic_patterns_evidence_2026_08_30.md | cut -d. -f1 | sort -u`
— every prefix should be ≤ the current year-month, and any later addition to this file should be
re-checked that way. This file is the durable record; the raw passes are gone.

**A standing caveat on preprints.** Many 2025–2026 sources here are arXiv preprints, marked as such.
A preprint is weaker evidence than a peer-reviewed venue and its numbers may move; where a claim rests
only on a preprint, say so in the finding.

---

## 1. Prompt Chaining

**Definition.** A fixed sequence of LLM calls, each consuming the previous one's output, optionally
with programmatic (non-LLM) validation gates between steps. The step list is knowable before seeing
the input — that is what makes it a *workflow*, not an agent.

**WHEN.** You can write the step list in advance, and you have latency budget to spend buying a higher
per-step success rate by making each call an easier task than the composite would be. Anthropic states
the goal plainly: *"The main goal is to trade off latency for higher accuracy."* [S1]

**WHERE.** Orchestration layer; the inter-step validation gates are a lightweight gate layer inside the
same path.

**WHY.** Narrowing each call lowers that inference's difficulty. Anthropic's worked examples: generate
copy then translate it; write an outline, programmatically check it against criteria, then write the
document [S1]. Independent HCI evidence: *AI Chains* (CHI '22) found chaining *"improved the quality of
task outcomes"* plus *"significantly enhanced system transparency, controllability, and sense of
collaboration"* in a 20-person study [S2] — **qualitative/HCI evidence, GPT-3-era, no accuracy delta**.

**WHY NOT.**
- **Error compounding is the dominant failure mode**, named by Anthropic itself as a cost of agentic
  complexity: *"higher costs, and the potential for compounding errors"* [S1]. The arithmetic is
  unforgiving and checkable by calculator: 0.95^10 ≈ 0.599.
- **Self-conditioning makes it worse than passive propagation.** *The Illusion of Diminishing Returns*
  finds models *"become more likely to make mistakes when the context contains their errors from prior
  turns,"* and that this *"does not reduce by just scaling the model size"* — a bigger model per step is
  not insurance [S4].
- **A verification step recovers most, not all, damage, at added cost.** An "Inspector" after each step
  recovered *"up to 96.4%"* of injected errors — leaving ~3.6% surviving, and costing an extra LLM call
  per step. Same study: a hierarchical structure showed *"the lowest performance drop of 5.5%"* vs
  *"10.5% and 23.7% of other two structures"* [S5] — i.e. **chain SHAPE measurably changes fault
  tolerance**, and both non-hierarchical structures are worse. **The extracted quote does NOT identify
  which of the 10.5%/23.7% structures is the flat ungated chain, so no specific figure is attributable
  to it** — an earlier draft of this line inferred "the flat chain is the worst-performing shape" from
  these numbers, which the quote does not support. `[S5]` covers the quoted figures only, never that
  inference.
- **Honest gap:** no head-to-head chaining-vs-single-call benchmark showing chaining losing was found.
  The case is mechanistic, not a demonstrated regression.

**COST.** Direction only, no multiplier in any source. Minimum bound: N sequential calls = ≥N× the
latency of one (serial by construction). **Unverified at the multiplier level.**

**CHEAPER FIRST.** One well-prompted call with retrieval and in-context examples — Anthropic's own
ordering: *"For many applications... optimizing single LLM calls with retrieval and in-context examples
is usually enough."* [S1]

**EVIDENCE GRADE: vendor-guidance.** The canonical naming source carries **zero benchmark numbers for
any of its three patterns** — confirmed by direct full read across two fetches [S1]. That absence is
itself the finding.

**Sources.** S1 Anthropic, *Building Effective Agents*, anthropic.com/engineering/building-effective-agents `[read directly]` · S2 Wu, Terry & Cai, *AI Chains*, CHI '22, arXiv:2110.01691 `[read directly]` · S3 compounding-error table (95%/10→59% etc.) `[from memory — VERIFY]` — arithmetic checkable, attribution untraced · S4 Sinha, Arun, Goel et al., *The Illusion of Diminishing Returns*, arXiv:2509.09677 `[read directly]` · S5 Huang, Zhou, Jin et al., *On the Resilience of LLM-Based Multi-Agent Collaboration with Faulty Agents*, ICML 2025, arXiv:2408.00989 `[read directly]`

---

## 2. Routing

**Definition.** A classification step inspects the input and dispatches it to one of several specialized
prompts, agents, or model tiers. `platform-dependent`

**WHEN.** Both vendor conditions must hold: (a) the input space decomposes into a **small number of
genuinely distinct categories**, and (b) **classification itself can be done accurately**. Anthropic:
routing *"works well for complex tasks where there are distinct categories that are better handled
separately, and where classification can be handled accurately"* [S1]. OpenAI's equivalent is the
decentralized/handoff pattern, for *"conversation triage, or whenever you prefer specialized agents to
fully take over"* [S2].

**WHERE.** Orchestration layer, at the **entry point**; or purely at the model-selection layer (cheap
vs. expensive model for the *same* task).

**WHY.** Measured, and this is the one pattern in its family whose numbers point toward *saving*
resources: **RouteLLM** *"significantly reduces costs—by over 2 times in certain cases—without
compromising the quality of responses,"* with *"cost reductions of over 85% on MT Bench, 45% on MMLU,
and 35% on GSM8K as compared to using only GPT-4"* [S3]. **FrugalGPT** (cascade variant) matches GPT-4
*"with up to 98% cost reduction"* or *"improve[s] the accuracy over GPT-4 by 4% with the same cost"*
[S4]. **Do not blend S3 and S4** — different systems, baselines, benchmarks.

**WHY NOT.**
- **The routing plateau — a measured structural ceiling.** Across *"21 routing methods across five
  benchmarks"*: *"many methods, including kNN, achieve very similar accuracy and converge to a narrow
  performance range that remains far below the oracle router."* Root cause named a **predictability
  bottleneck** — routers learn broad averaged patterns, so they succeed on easy queries and
  collectively underperform on exactly the hard, ambiguous ones where correct routing matters most
  [S5]. **This directly falsifies condition (b) above for the hard tail of any distribution.**
- **Out-of-distribution collapse.** Routers trained on one distribution perform *"at a near-random
  level"* off it [S6 — secondary summary of RouteLLM's own limitations, **lower confidence**].
- **Adversarial inversion — the sharpest why-not.** A cascade/router's *confidence mechanism itself* is
  attackable: up to **84.6% accuracy drop**, **148.9% increase in normalized token cost**, up to
  **108.9% latency increase**, up to **81.4% higher jailbreak success** — and the suffixes **transfer
  black-box to unseen cascade configurations** [S7]. The paper's framing: a cascade *"behaves like a
  chain whose strength is limited by its weakest links: once a query is filtered out at an early stage,
  the later, more accurate models never have a chance to respond."* **The entire cost saving inverts
  under attack.**
- **Misroute cascades**: an input sent to the wrong branch inherits pattern 1's compounding dynamics.
  Mechanistic; **no named production postmortem found** (see Could-not-source).

**COST.** Cost *reductions*: `over 2× vs all-GPT-4` [S3]; `up to 98% vs GPT-4 alone` [S4]. Under
adversarial input: `+148.9% vs the same cascade on benign traffic` [S7].

**CHEAPER FIRST.** A single generalist prompt/model over the whole distribution; escalate only once it
demonstrably fails on a distinguishable subset — OpenAI: *"maximize a single agent's capabilities
first."* [S2]

**EVIDENCE GRADE: primary-measured** (both the wins and the ceiling).

**Sources.** S1 Anthropic, *Building Effective Agents* `[read directly]` · S2 OpenAI, *A Practical Guide to Building Agents*, PDF pp.1–24 `[read directly]` · S3 Ong, Almahairi, Wu et al., *RouteLLM*, arXiv:2406.18665 `[read directly]` · S4 Chen, Zaharia & Zou, *FrugalGPT*, arXiv:2305.05176 `[read directly]` · S5 *The Routing Plateau*, arXiv:2606.07587 (preprint) `[read directly]` · S6 RouteLLM OOD limitation `[from memory — VERIFY]` · S7 Sun, Chen & Li, *When Efficiency Backfires*, arXiv:2605.17288 (preprint) `[read directly]`

---

## 3. Parallelization (sectioning)

**Extends primer §1/§14 — does not restate them.** Adds the aggregation failure mode and the
composition tax. `platform-dependent`

**WHEN.** Subtasks are **genuinely independent** (no subtask needs another's output) and aggregation is
cheap relative to the work combined. Anthropic: effective *"when the divided subtasks can be
parallelized for speed, or when multiple perspectives or attempts are needed for higher confidence"*
[S1].

**WHY (new).** Skeleton-of-Thought reports *"considerable speed-ups across 12 LLMs"* by expanding
skeleton points in parallel [S3] — a **latency** win, a different axis from the token-cost trades.
Anthropic's own system: multi-agent beat single-agent Opus 4 by 90.2% on an internal research eval, and
*"token usage by itself explains 80% of the variance"* — the win is substantially **spending more
tokens in parallel**, not a different kind of reasoning [S2].

**WHY NOT (the new material).**
- **Aggregator noise is its own measured error term.** A noise-decomposition framework separates
  *"cross-chunk dependence (task noise), confusion that grows with context size (model noise), and the
  imperfect integration of partial results (aggregator noise)"* [S4]. Sectioning does not merely inherit
  its parts' errors — **the aggregation step adds error of its own**. Chunking wins only when model
  noise *"grows superlinearly"* AND cross-chunk dependencies are *"manageable"*.
- **Anthropic names the domains where it is currently wrong**, in production: *"some domains that
  require all agents to share the same context or involve many dependencies between agents are not a
  good fit for multi-agent systems today. For instance, most coding tasks involve fewer truly
  parallelizable tasks than research."* [S2] Converges with S4 from an independent direction.
- **Cross-Component Interference — more scaffolding measurably hurts.** Full factorial over five
  scaffolding components: *"in every setting tested, the best proper subset matches or exceeds the
  five-component All-In system."* HotpotQA, Llama-3.1-8B: single-tool F1 **0.233 vs All-In 0.177** — a
  32% degradation (paired t-test p=0.023, Cohen's d_z=0.87). GSM8K: a three-component subset **0.43 vs
  0.24**. The effect follows a capability gradient — *"strong at 8B (gap=32%), attenuated at 70B
  (gap=19%), and saturating to within-noise on Claude Haiku [4.5]"* [S5]. **Scope caveat: this studies
  single-agent scaffolding composition, not sectioning directly** — cite as adjacent complexity
  evidence. Practical read: a stronger base model buys back the over-composition tax **partially, not
  fully**.
- **Observed coordination failures, not hypotheticals**: *"agents spawning 50 subagents for simple
  queries,"* subagents *"scouring the web endlessly for nonexistent sources,"* and duplicated work [S2].

**COST.** `~15× vs a single chat interaction` (agentic alone `~4×`) [S2]. Skeleton-of-Thought spends
*more* tokens to buy *lower wall-clock* — **opposite axis; never merge the two** [S3].

**CHEAPER FIRST.** One agent working the task serially. For a latency problem specifically, a single
long generation — unless latency is the *measured* bottleneck.

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Anthropic, *Building Effective Agents* `[read directly]` · S2 Anthropic, *How we built our multi-agent research system* `[read directly]` · S3 Ning et al., *Skeleton-of-Thought*, ICLR 2024, arXiv:2307.15337 `[read directly]` (a secondary "1.9×/ten LLMs" figure **conflicts** with the abstract's "12 LLMs" — unreconciled) · S4 *When Does Divide and Conquer Work for Long Context LLM?*, arXiv:2506.16411 (preprint) `[read directly]` · S5 Liu (Amazon), *More Is Not Always Better: Cross-Component Interference in LLM Agent Scaffolding*, arXiv:2605.05716 (preprint) `[read directly, PDF pp.1–3]`

---

## 4. Reflection / Self-Critique

**Extends primer §2 — the grounded-vs-ungrounded dividing line is already authoritative there.** Adds
the cost band and sharper boundary conditions.

**WHEN.** An **independently checkable signal** exists to critique against — a test result, a tool's
return value, a retrieved fact, a lint/type-check pass. Absent that, §2's Huang et al. case applies and
the loop can *degrade* the answer.

**WHY (new).** Self-Refine and CRITIC reproduce the Reflexion mechanism tool-grounded [S1, S2]. A
survey of LLM self-correction reinforces the same boundary [S3].

**WHY NOT (new).** *The Self-Correction Illusion* and the broader survey line up with §2: without an
external signal, apparent gains are often artifacts of oracle labels or of the evaluation setup rather
than real correction [S3, S4]. Per-task deltas for Self-Refine could not be pinned this pass.

**COST.** Each critique+revise round adds one full critique generation plus one full revision
generation on top of the base answer — **no cited multiplier**; the round count is the knob. Treat any
stated reflection multiplier as architectural estimate, not measured.

**CHEAPER FIRST.** A single well-specified prompt with explicit success criteria stated up front —
before adding a critic pass at all.

**EVIDENCE GRADE: primary-measured** (for the grounded case; the ungrounded case is measured as a
*negative*).

**Sources.** S1 Madaan et al., *Self-Refine* `[read directly]` · S2 Gou et al., *CRITIC* `[read directly]` · S3 Kamoi et al., survey of LLM self-correction, TACL `[read directly]` · S4 *The Self-Correction Illusion* `[read directly]`. Reflexion and Huang et al. are primer sources 6 and 5 — cite those numbers from the primer, not here.

---

## 5. Tool Use / Function Calling

**Definition.** Discover/expose tool definitions, select one, construct typed arguments, execute, feed
the result back, repeat to a stop condition. Four separable engineering problems: definition design,
selection accuracy, discovery/loading strategy, failure handling. `platform-dependent`

**WHEN.** The task needs an action or data outside the model's context, with a small number of
enumerable operations that benefit from typed, validated arguments. **Below ~20 tools a flat list is
viable**; above that, selection accuracy and token overhead both degrade measurably.

**WHERE.** Single-agent control loop (the `tool_use` → execute → `tool_result` cycle) plus a thin
registry/discovery infrastructure layer.

**WHY.** **Tool count degrades selection accuracy — with the vendor's own numbers.** A five-server setup
(58 tools) consumes *"approximately 55K tokens before the conversation even starts,"* some systems
reaching *"134K tokens before optimization"*; the named failure is *"wrong tool selection and incorrect
parameters, especially when tools have similar names."* The Tool Search Tool measured against
all-definitions-loaded: **85% token reduction**, and MCP-eval accuracy **Opus 4 49%→74%**, **Opus 4.5
79.5%→88.1%** [S1]. Tool-use examples in the schema moved *"accuracy from 72% to 90% on complex
parameter handling"* [S1]. Independent confirmation: an adaptive per-query shortlist hit *"90.3%"*
coverage showing ~7 tools vs *"90.8%"* for a fixed 50-tool list; on ToolBench (3,251 tools),
*"93.1% versus 87.1%"*, widening to *"76.8% vs 60.9%"* on medium-difficulty queries [S3].

**WHY NOT.**
- **A seven-category error taxonomy that tool search does not fix**: insufficient calls, incorrect
  argument value/name/type, repeated calls, hallucinated function name, invalid format. Measured
  per-model overall success ranges GPT-4-0125 **0.73** down to Mixtral-8x7B **0.10** [S4]. Hallucinated
  tool names and wrong arguments are *routine and model-dependent*, independent of tool count.
- **Unbounded tool loops are a mined, real-world failure class.** 6,549 repositories scanned; **68
  confirmed infinite-agentic-loop failures across 47 projects** (91.9% precision). Root causes: retry
  feedback without bound 25.0%, tool-call iteration without bound 23.5%, multi-agent chat without turn
  bound 20.6%, workflow loop without effective bound 13.2% — **100% traced to a missing strong bound**.
  Impact: API cost exhaustion 95.6%, model DoS 95.6%. Explicit recommendation: *"developers deploy agent
  runs with explicit stopping rules"* and *"not rely on the model to eventually stop producing tool
  calls."* [S5]
- **Tool count is a stated cost even with search available**: *"Limit tool count: Too many tools can
  confuse the model."* Tool search manages *which* tools are in context per turn; **no source claims it
  repeals the underlying degradation** [S2].
- **Security.** OWASP **LLM06:2025 Excessive Agency** names the root causes as *"excessive functionality,
  permissions, or autonomy"* — unneeded functions left reachable, legacy tools still callable, a
  *"generic high-privileged identity"* instead of per-user least privilege, missing independent approval
  for high-impact actions [S6].

**COST.** `~0.15× (85% reduction) vs all-definitions-loaded, in a 58+ tool regime` [S1] — **this is a
saving within one agent's tool surface and does not offset** `~4× (single agent) / ~15× (multi-agent)
vs a single chat turn` [S7]. Never blend the two.

**CHEAPER FIRST.** Below ~20 tools, a flat well-described list. Before reaching for tool search: prune
the set to the task path, and tighten tool *descriptions* with explicit trigger conditions — stated to
give measurable lift with no infrastructure change [S2].

**EVIDENCE GRADE: primary-measured** (vendor engineering + two independent preprints).

**Sources.** S1 Anthropic, *Advanced tool use on the Claude Developer Platform* `[read directly]` · S2 bundled `claude-api` skill, `shared/tool-use-concepts.md` and `shared/agent-design.md` `[read directly]` · S3 Repantis, Gawde, Singh & Blackwell II, *How Many Tools Should an LLM Agent See?*, arXiv:2605.24660 (preprint) `[read directly]` · S4 Kokane et al. (Salesforce), *ToolScan*, arXiv:2411.13547 (preprint) `[read directly]` · S5 Hou, Wang, Zhao & Wang, *When Agents Do Not Stop*, arXiv:2607.01641 (preprint) `[read directly]` · S6 OWASP GenAI, *LLM06:2025 Excessive Agency*, official repo `[read directly]` · S7 Anthropic, *How we built our multi-agent research system* `[read directly]`

---

## 6. Planning

**Extends primer §5 (ADaPT) — §5 owns the plateau-triggers-split rule.** Adds the plan-first-vs-
interleaved comparison and the classical-planning counter-evidence, neither of which §5 covers.

**WHEN.** **Plan-first** when the task structure is knowable in advance and static. **Interleaved
(ReAct)** when each step's outcome is uncertain until observed. **Adaptive (ADaPT)** when subtask
difficulty is itself unknown per-instance.

**WHY.** ReAct beat imitation/RL baselines on ALFWorld by *"an absolute success rate of 34%"* [S1].
Plan-and-Solve (a *prompting-only* plan step) beat Zero-shot-CoT on every arithmetic set — GSM8K
56.4%→59.3%, MultiArith 83.8%→91.8%, AQuA 38.9%→46.0% [S2]. ADaPT vs ReAct, same executor: ALFWorld
43.3%→**71.6%**, WebShop 32.0%→**44.0%**, TextCraft 19.0%→**52.0%** [S3]. *(The paper's abstract
summarizes WebShop as "27% higher" against unspecified plural baselines — does not reconcile with the
ReAct-specific 12.0pp; both quoted, not silently merged.)*

**WHY NOT.**
- **LLMs are demonstrably weak at classical planning.** PlanBench, Blocksworld: GPT-4 produced valid
  plans on **206/600 (34.3%)**; InstructGPT-3 on **41/600 (6.8%)**. *"On many critical capabilities —
  including plan generation — LLM performance falls quite short, even with the SOTA models."* [S4]
  **This falsifies any assumption that an LLM reliably produces a correct plan up front, even in a toy
  domain with unambiguous ground truth.**
- **Fixed plans are brittle by construction**, and this is ADaPT's own stated reason for beating them:
  *"it is challenging to anticipate the difficulty of such a sub-task in advance... their non-adaptive
  nature poses a limitation when confronting unachievable sub-tasks."* [S3]
- **Kambhampati et al.**: *"auto-regressive LLMs cannot, by themselves, do planning or
  self-verification"* — proposing external model-based verifiers around LLM plans [S5 `[from memory —
  VERIFY]`, but corroborated by S4's measured numbers].
- **The cheap alternative captures much of the gain**, which argues against the heavy architecture:
  Plan-and-Solve is prompting-only, zero extra tool calls, and still beats bare CoT by several points.

**COST.** ADaPT vs ReAct: additively more calls on harder instances for the accuracy gains above —
**paper states no token multiplier; unverified on cost**. Plan-and-Solve vs Zero-shot-CoT: ~1 extra
generation pass.

**CHEAPER FIRST.** Add a "first devise a plan, then solve" instruction to a single prompt before
building a plan-and-execute architecture. For tool-use tasks: **attempt directly, decompose on failure**
(ADaPT) rather than decomposing everything up front.

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Yao et al., *ReAct*, ICLR 2023, arXiv:2210.03629 `[read directly]` · S2 Wang et al., *Plan-and-Solve Prompting*, ACL 2023, arXiv:2305.04091 `[read directly, full table]` · S3 Prasad et al., *ADaPT*, Findings of NAACL 2024, arXiv:2311.05772 `[read directly, full table]` · S4 Valmeekam et al., *PlanBench*, NeurIPS 2023 D&B, arXiv:2206.10498 `[read directly, Table 1]` · S5 Kambhampati et al., *LLMs Can't Plan, But Can Help Planning in LLM-Modulo Frameworks*, ICML 2024, arXiv:2402.01817 `[from memory — VERIFY]`

---

## 7. Multi-Agent Collaboration

**Extends primer §1/§14 — the three-scenario test and cost bands are authoritative there.** Adds the
failure taxonomy and the topology result, which are the material §14 lacks.

**WHEN.** The task decomposes into **genuinely parallel, low-interdependency** sub-tasks, AND a
**centralized/orchestrator topology with verification** is used — the topology is not a detail, see
below.

**WHY (new).** Task-contingent, with both signs measured: *"Relative performance change compared to
single-agent baseline ranges from +80.8% on decomposable financial reasoning to -70.0% on sequential
planning, demonstrating that architecture-task alignment determines collaborative success."* [S2] The
same work's architecture-selection model *"correctly identifies the optimal coordination strategy for
87% of unseen task configurations."*

**WHY NOT — the strongest material in this file.**
- **MAST: most multi-agent failure is architectural, not model-capability.** 14 failure modes in 3
  categories, from **1,600+ annotated traces across 7 frameworks** (ChatDev, MetaGPT, HyperAgent,
  AppWorld, AG2/MathChat, Magentic-One, OpenManus), inter-annotator κ=0.88 [S1]. Per-mode rates
  (cross-checked across two independent extractions): **Step Repetition 15.7%** (most common),
  Reasoning-Action Mismatch 13.2%, Unaware of Termination Conditions 12.4%, Disobey Task Specification
  11.8%, Incorrect Verification 9.1%, No/Incomplete Verification 8.2%, Task Derailment 7.4%, Fail to Ask
  for Clarification 6.8%, Premature Termination 6.2%, others ≤2.8%. *Category-level roll-ups disagreed
  between extractions (44.2/32.3/23.5 vs 41.77/36.94/21.30) — **use the per-mode numbers, not the
  roll-ups**.*
- **Topology bounds error amplification — the mechanism finding.** *"Independent multi-agent systems
  (agents working in parallel without talking) amplified errors by 17.2x... Centralized systems (with an
  orchestrator) contained this amplification to just 4.4x."* [S3] **The fix for most multi-agent failure
  is centralizing verification, not adding agents.**
- **Adding agents can make the system worse, not merely costlier**: *"-70.0% on sequential planning"*;
  every multi-agent variant tested degraded PlanCraft by **39–70%** [S2, S3].
- **Coordination is a protocol property, not a capability property.** Dining-Philosophers-style
  contention: deadlock ranged **25.0% (GPT-5.2) to 90.0% (Gemini 2.5 Flash)**; *"Whether the same model
  coordinates or deadlocks is determined by the protocol, not by the model's capability."* Three
  protocol interventions each drove deadlock ~90%→~0% [S4]. *Caveat: preprint; the model identifiers it
  names are not independently corroborated — the methodology and deadlock findings stand regardless.*
- **Capability threshold**: coordination *"yields diminishing returns once single-agent baselines exceed
  certain performance"* [S2]. A *Nature Machine Intelligence* paper titled *"Capable language models can
  outgrow the benefits of collaboration"* is on-point but was **auth-blocked — title/venue only, cite no
  number from it** [S7].
- **Shared-memory failure modes are named but unquantified**: staleness, contention, information
  leakage, contradiction [S5]. **No occurrence rates are extractable — do not cite a percentage.**

**COST.** `3–10× vs single-agent, same task` (primer §14). Error amplification `17.2× independent /
4.4× centralized vs single-agent error rate` [S3] — a **quality** cost; **never blend with token
multipliers**.

**CHEAPER FIRST.** A single agent with longer context/better tools. Where decomposition is genuinely
needed, prefer a **centralized orchestrator with verification** over independent agents before scaling
agent count — topology, not headcount, is what contains error [S3].

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Cemri, Pan, Yang, Agrawal et al., *Why Do Multi-Agent LLM Systems Fail?*, arXiv:2503.13657, NeurIPS 2025 poster `[read directly, 2 independent fetches]` · S2 Kim, Gu, Park et al., *Towards a Science of Scaling Agent Systems*, arXiv:2512.08296 `[read directly]` (config count differs between arXiv "260" and the blog's "180" — unresolved) · S3 Google Research blog, same paper `[read directly]` · S4 Hasan & BusiReddyGari, *DPBench*, arXiv:2602.13255v2 (preprint) `[read directly]` · S5 Margalit et al., *Governed Shared Memory for Multi-Agent LLM Systems*, arXiv:2606.24535 `[read directly, partial]` · S6 Han & Zhang, *Blackboard Architecture*, arXiv:2507.01701 `[read directly, partial]` · S7 *Capable language models can outgrow the benefits of collaboration*, Nature MI 2026, s42256-026-01268-y **`[title/venue only — auth-blocked]`**

---

## 8. Memory Management

**No primer coverage.** §6 is fact-stores/retrieval — a different concern. Confirmed behaviorally: the
agent's own RED-baseline probe stated it had *"no doctrine... for write-side concerns (concurrent
writes, provenance) — only retrieval."* `platform-dependent`

**Definition.** How an agent writes information out of its live context into external storage, organizes
and consolidates it, and later retrieves a subset — short-term (working), episodic (past runs), and
long-term (durable cross-session).

**WHEN.** (a) the task needs information from a prior session that no longer fits or was never in
context; (b) the working trace has grown to where leaving it in-context measurably degrades quality
(→ compaction, not storage); (c) cross-session continuity is a product requirement.

**WHERE.** Knowledge surface / infrastructure, read and written by the control loop.

**WHY.** **Generative Agents** ablation (TrueSkill, judged believability): full architecture μ=29.89 vs
no-reflection μ=26.88 vs no-reflection-or-planning μ=25.64 vs **no memory at all μ=21.21** — *"a
standardized effect size of d=8.16, or eight standard deviations"* [S1]. **Mem0** vs full-context
stuffing on LoCoMo: *"26% relative improvements in the LLM-as-a-Judge metric over OpenAI [Memory],"*
*"91% lower p95 latency"* and *"saves more than 90% token cost"* [S3].

**WHY NOT.**
- **Memory poisoning is measured, high-success, and not covered by prompt-injection defenses.** MINJA:
  a **query-only** attacker with no direct memory access achieves *"over 95% injection success rate...
  and over 70% attack success rate on most datasets"* [S6]. A systematic follow-up names *"four memory
  write channels and nine structural vulnerabilities"* and states *"existing prompt injection defenses
  fail to cover memory poisoning attacks"* — with the core design tension stated outright: **"agents
  designed to write and retrieve memory more aggressively are more exploitable"** [S7].
- **Unbounded growth degrades retrieval, self-reported by the seminal paper's own authors**:
  *"synthesizing an increasingly larger set of memory not only posed a challenge in retrieving the most
  relevant pieces of information but also in determining the appropriate space to execute an action"*
  [S1]. Same paper measured its own fabrication rate at **1.3% (n=6)** and named **memory hacking** —
  convincing an agent of a past event that never occurred.
- **Staleness is benchmarked, not theoretical.** LongMemEval builds explicit knowledge-update and
  abstention categories because systems otherwise fabricate rather than recognize a superseded memory;
  it measures *"a 30% accuracy drop on memorizing information across sustained interactions"* [S8].
- **"Has long context displaced memory?" is genuinely unresolved.** A 2026 survey lays out long-context,
  RAG, and agent memory and concludes only that *"all three approaches remain relevant"* [S9]. **No
  primary source resolves this either way** — report it as open, not as a settled preference.

**COST.** `~10× cheaper in tokens and ~11× lower p95 latency vs full-context stuffing of the entire
conversation history` [S3]. The one clean named-baseline multiplier here — do not blend it with RAG's.

**CHEAPER FIRST.** Context compaction plus a flat append-only session log or file-based note-taking —
no embedding index, no consolidation step, no archival tier, **and no new attack surface**. Anthropic
frames the escalation explicitly: compaction → structured note-taking → sub-agent architectures, memory
tooling being one option among these, not the default [S11].

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Park et al., *Generative Agents*, UIST 2023, arXiv:2304.03442 `[read directly, ar5iv]` · S2 Packer et al., *MemGPT*, arXiv:2310.08560 `[read directly — architecture only; numeric results UNVERIFIED]` · S3 Chhikara et al., *Mem0*, arXiv:2504.19413 `[read directly]` · S4 Zhong et al., *MemoryBank*, AAAI 2024 `[via WebSearch snippet]` · S5 Xu et al., *A-MEM*, arXiv:2502.12110 `[via WebSearch snippet — magnitude UNVERIFIED]` · S6 Dong et al., *MINJA*, NeurIPS 2025, arXiv:2503.03704 `[via WebSearch snippet]` · S7 *From Untrusted Input to Trusted Memory*, arXiv:2606.04329 (preprint) `[read directly]` · S8 Wu et al., *LongMemEval*, ICLR 2025, arXiv:2410.10813 `[via WebSearch snippet]` · S9 *AMA-Bench*, arXiv:2602.22769 `[via WebSearch snippet]` · S10 Maharana et al., *LoCoMo*, arXiv:2402.17753 `[read directly]` · S11 Anthropic, *Effective context engineering for AI agents* `[read directly]`

---

## 9. Learning & Adaptation

**No primer coverage.**

**Definition.** Feeding outcome signals back so the system changes future behavior — an optimized
prompt, an updated routing rule, a new regression test, a revised standing instruction.

**WHEN.** A **fixed, labeled, held-out eval set** exists that faithfully represents the task
distribution; the metric is **machine-scorable**; the task is stable enough that a rule learned today
still applies later; and **a human or mechanical gate sits before an optimized artifact ships**.

**WHY.** **DSPy** vs standard few-shot: *"GPT-3.5 outperforms by over 25%; llama2-13b-chat by 65%"*; vs
expert-written demonstrations, 5–46% / 16–40% [S1]. **OPRO** vs best human-designed prompt: up to 8% on
GSM8K, **up to 50% on Big-Bench Hard** [S2]. **GEPA** vs GRPO (RL): *"outperforms GRPO by 6% on average
and by up to 20%, while using up to 35x fewer rollouts"*; vs MIPROv2, *"by over 10%"* [S3].

**WHY NOT.**
- **The evidence base is entirely OFFLINE — state this plainly.** Every measured-gain source optimizes
  against a **fixed benchmark or held-out set**, then ships a **frozen artifact**. Reflexion and Voyager
  are "online" only as within-episode retrial inside a sandbox. **No credible primary evidence was found
  for a genuinely online, continuously self-improving production agent loop.** Treat any vendor claim of
  an agent that "learns in production" with the same skepticism the runtime applies to same-family judge
  claims.
- **"Evil twin" prompts — the maintenance cost, sourced.** *"Prompts have so-called 'evil twins' that
  are uninterpretable yet recover some of the performance of gold-standard prompts,"* and *"rare
  gibberish strings can serve as competitive delimiters"* [S6]. An optimizer can find a prompt that
  scores well **for reasons no human can read off the text**.
- **Textual-gradient methods are unstable and overfit.** They lack the smoothness that makes gradient
  descent reliable; instability and poor cross-setup transfer are reported [S7 `[read directly,
  partial — numeric effect sizes not extractable]`].
- **Self-modification carries emergent risk.** Reward hacking against the optimized metric rather than
  the true objective, safety-property erosion under iterated self-modification, and compounding
  misalignment — the failure mode gets **worse** the more autonomously the loop runs without an external
  check [S8 `[read directly, partial]`].
- **Degrades when:** the eval set is small, unrepresentative, or gameable (the optimizer finds the evil
  twin); the target model changes; or the loop runs with no human gate.

**COST.** `up to 35× fewer rollouts vs a GRPO/RL-finetuning baseline` [S3]. Automatic prompt
optimization is **not one cost band** — one system took *"close to 60 hours"* vs *"~10 minutes per
task"* for a lighter method, **a 350x+ spread between methods** [S6]. Never blend with the GEPA-vs-GRPO
figure.

**CHEAPER FIRST.** A small hand-curated few-shot set plus a held-out eval on every prompt change. DSPy's
own numbers show expert demonstrations are 5–46% behind the compiled result — **real but bounded, not
transformative** for a single task. Confirm the eval set is trustworthy first: every sourced failure
mode above is a symptom of over-trusting it.

**EVIDENCE GRADE: primary-measured** (offline only — the online case is `no-primary-source`).

**Sources.** S1 Khattab et al., *DSPy*, arXiv:2310.03714 `[read directly]` · S2 Yang et al., *Large Language Models as Optimizers* (OPRO), ICLR 2024, arXiv:2309.03409 `[read directly]` · S3 Agrawal et al., *GEPA*, ICLR 2026 oral, arXiv:2507.19457 `[read directly]` · S4 Shinn et al., *Reflexion* `[from memory — VERIFY]` · S5 Wang et al., *Voyager* `[from memory — VERIFY]` · S6 Ramnath et al., *A Systematic Survey of Automatic Prompt Optimization Techniques*, EMNLP 2025, arXiv:2502.16923 `[read directly]` · S7 Melcer et al., *Textual Gradients are a Flawed Metaphor*, arXiv:2512.13598 `[read directly, partial]` · S8 Shao, Ren, Qian, Wei et al., *Your Agent May Misevolve*, arXiv:2509.26354 `[read directly, partial]` · S9 Google SRE Book, *Postmortem Culture* `[read directly]` — **cross-domain borrow, not agentic-specific**

---

## 10. Goal Setting & Monitoring

**No primer coverage** (§13 is control theory; it has no goal-formation or progress-tracking doctrine).

**The finding is a SPLIT, and it is the whole point of this entry.** The *mechanical* half (an external
gate checking a hard criterion) is well-evidenced. The *self-monitoring* half (an agent narrating and
trusting its own progress) is evidenced to be **unreliable and directionally overconfident**. Scoring
them together smuggles the unreliable half in under the credible half's reputation.

**WHEN.** A task has an **externally checkable completion condition** that is **cheaper to verify than
to achieve**. It does **not** apply usefully when the only progress signal is the agent's own narrative
self-report.

**WHY (the mechanical half).** Verification-is-easier-than-generation, the same asymmetry primer §4
already prices. Voyager pairs a curriculum with *"self-verification for program improvement"* — but its
self-verification component's independent contribution is **not isolated** in the reported results [S2].

**WHY NOT (the self-monitoring half).**
- **Huang et al.** — an agent monitoring *itself* with no external check *"often lead[s] to performance
  degradation"* [S1]. This is the load-bearing counter-finding.
- **Overconfidence is directional, not neutral**: verbalized confidence skews high *exactly* in the
  high-stakes region [S6 `[from memory — VERIFY]`] — the opposite of what a safe monitoring signal needs.
- **MIRROR**: *"systematic overconfidence"*; agents' self-knowledge *"does not transfer across domains
  or update from feedback"* [S7 `[from memory — VERIFY]`, citation metadata unconfirmed].
- **This pattern is largely management doctrine relabeled.** Explicit KPIs + progress tracking +
  course-correction is Management-by-Objectives / OKRs (Grove 1983, Doerr 2018, descended from Drucker)
  [S9 `[from memory — VERIFY]`]. Nothing in the agentic literature establishes that an LLM's
  self-reported progress is a reliable signal.
- **Goodhart's Law applies** — but note it is economics, not CS [S3, S4 `[from memory — VERIFY]`].
  **Metric-gaming, however, IS backed by agentic/RL evidence**: boat-racing agents circling for points,
  ROUGE-gaming summarizers, and *"coding models that learn to change unit test[s] in order to pass"*
  [S5 `[from memory — VERIFY]`, Krakovna attribution unconfirmed].

**COST.** External-gate monitoring: the price of the check vs. an undetected regression — asymmetric and
favorable, but **no source quantifies it as a multiplier**. Self-report: near-zero marginal cost and
evidenced-unreliable — **cheap and untrustworthy, not cheap and good**.

**CHEAPER FIRST.** A hard external check (a test, a diff digest, a threshold) over an agent's narrated
self-assessment. Always.

**EVIDENCE GRADE: practitioner-consensus** for the pattern as usually described; `primary-measured` for
the negative result on self-monitoring.

**Sources.** S1 Huang et al., *LLMs Cannot Self-Correct Reasoning Yet*, ICLR 2024, arXiv:2310.01798 `[read directly]` · S2 Wang et al., *Voyager*, arXiv:2305.16291 `[from memory — VERIFY]` · S3 Goodhart 1975 `[from memory — VERIFY]` · S4 Strathern 1997 `[from memory — VERIFY]` · S5 specification-gaming examples, commonly attributed to Krakovna et al. 2020 `[from memory — VERIFY, attribution unconfirmed]` · S6 Lin, Hilton & Evans, arXiv:2205.14334 `[from memory — VERIFY]` · S7 MIRROR benchmark `[from memory — VERIFY, citation metadata unconfirmed]` · S8 Cognition/Devin SWE-bench self-report and its critique `[from memory — VERIFY]` · S9 Grove 1983 / Doerr 2018 `[from memory — VERIFY]`

---

## 11. Exception Handling & Recovery

**Partial primer coverage only** — §13's jidoka test is "does the stop signal carry authority" and §14
point 5 is bounded retries. **Neither covers retry policy, fallback chains, compensation, or graceful
degradation.**

**Be explicit about which half is imported doctrine.** Backoff, circuit breaker, bulkhead, idempotency
and sagas are **distributed-systems doctrine**, not agentic findings. What is genuinely agent-specific
is below it.

**WHEN.** Any call to an external dependency whose failure *could* be transient; any multi-step workflow
where a later step can fail after an earlier one produced a real side effect; **any step whose output —
including its error text — is fed back into the same context**.

**WHY (imported).** *"Full Jitter reduced call counts by over 50%"* at 100 contending clients; *"the
return on implementation complexity of using jittered backoff is huge"* [S1]. Google SRE: *"Always use
randomized exponential backoff when scheduling retries"*; *"Retries can destabilize a system"* [S2];
plus a **retry budget** (per-request cap, ~10% client retry ratio ceiling, backend "don't retry"
signals) [S3].

**WHY NOT — the agent-specific half.**
- **Context contamination: the measured headline.** *"When an LLM agent fails a multi-step
  tool-augmented task and retries, the failed attempt typically remains in its context window —
  contaminating the next attempt and elevating the per-step error rate beyond the base level."*
  Measured **cascade ratio 7.1×**, and an independent-attempts model **overestimates 3-attempt pass rate
  by 17.4pp (98.6% predicted vs 81.2% actual)** [S7]. **Any harness that appends a raw error string to
  the next turn is manufacturing this — a common default, not a rare misconfiguration.**
- **Retry-with-backoff is a TRANSIENT-failure remedy.** A large, hard-to-distinguish class of agent
  failures are **structural** (schema mismatch, hallucinated argument, wrong tool). Retrying a structural
  failure doesn't recover — **it compounds**, and the 7.1× above is that compounding measured.
- **Agent retries are not idempotent replays.** A classic retry re-sends the same bytes and relies on
  idempotency keys; an agent's retry is a **new non-deterministic generation** that may re-attempt a call
  whose first try already partially succeeded. *(This distinction is structural/reasoned — **no study
  measuring agent retry non-determinism directly was found**; see Could-not-source.)*
- **A circuit breaker doesn't help here.** It trips on failure signals from a *shared downstream
  resource*; it is blind to an agent calling a **correctly-functioning** tool with wrong arguments
  forever [S6].
- **100% of confirmed infinite-loop failures traced to a missing strong bound** [S6] — see pattern 5.

**COST.** `>2× reduction in call volume vs unjittered exponential backoff` [S1] — a systems-throughput
win. `~7.1× higher per-step error rate vs clean-context` when retrying with the failure in context [S7]
— an error-rate cost. **Completely different baselines; never blend.**

**CHEAPER FIRST.** **Classify before retrying** — timeout/5xx is a retry candidate; a valid-shaped but
wrong-content result or a schema error is not, and needs a different action or a human. **Strip or
summarize the failed attempt's raw error text** out of the context feeding the next attempt. Both are
far cheaper than circuit-breaker infrastructure and target the measured agent-specific failure.

**EVIDENCE GRADE: primary-measured** (imported half is `vendor-guidance`/industry-canonical).

**Sources.** S1 Brooker, *Exponential Backoff and Jitter*, AWS Architecture Blog `[read directly]` · S2 Ulrich, *Addressing Cascading Failures*, Google SRE Book ch.22 `[read directly]` · S3 *Handling Overload*, Google SRE Book ch.21 `[read directly]` · S4 Nygard, *Release It!* (2007) `[from memory — VERIFY]` · S5 Garcia-Molina & Salem, *Sagas*, ACM SIGMOD 1987 `[from memory — VERIFY]` · S6 Hou et al., *When Agents Do Not Stop*, arXiv:2607.01641 (preprint) `[read directly]` · S7 Yang, *Why Retrying Fails: Context Contamination in LLM Agent Pipelines*, arXiv:2605.08563 (preprint) `[read directly]` · S8 Anthropic, *Building Effective Agents* `[read directly]`

---

## 12. Human-in-the-Loop

**Partial primer coverage only** — §14 point 4 is gate PLACEMENT in a factory pipeline. It says nothing
about escalation triggers, confidence thresholds, or human-on-the-loop vs in-the-loop.

**LANE — defers to primer §9.** The runtime's own review ladder and ask-gates are **settled policy, not
a per-run judgment call**. This entry supplies doctrine for auditing an approval gate's *design*; it is
never grounds to propose a different cadence for this runtime's own gates without new
review-outcome-ledger data, and never grounds to relax CLAUDE.md §4's ask-gates.

**WHEN.** The action is **irreversible**, **high-blast-radius**, or one where *"there is even a small
chance that they're done wrong"* with an asymmetric downside — named example: *"independently initiating
an irreversible large financial transaction"* [S1].

**WHERE.** A gate **at the point of side effects**: *"Pause before side effects like cancellations,
edits, shell commands, or sensitive MCP actions"* [S2] — between action-selection and tool-execution.
Never inside the model's reasoning; never a blanket wrapper on every call regardless of risk.

**WHY.** **This is where primary support runs thin, and that thinness IS the finding.** No source found
gives a *positive* measured efficacy number for approval gates (e.g. "X% of bad actions caught"). Every
piece of *measured* evidence located is about the pattern's **failure** modes. The burden of proof runs
the other way in this literature.

**WHY NOT.**
- **Automation bias / complacency is the decades-old central why-not.** Parasuraman & Riley's taxonomy
  frames *misuse* (over-reliance → monitoring failures) and *disuse* [S3]. Skitka, Mosier & Burdick is
  the direct demonstration: participants with a **highly-but-not-perfectly reliable** aid
  **under-performed participants with no aid at all**, via omission errors (missing what the aid didn't
  flag) and commission errors (following the aid against their own training and other valid available
  information) [S4]. Parasuraman, Molloy & Singh: detection of automation failures was *"substantially
  worse for constant-reliability than for variable-reliability automation after about 20 minutes"* —
  **a consistently-right gate is precisely the profile that degrades vigilance** [S5].
  *All three are `[from memory — VERIFY]` at quote level — paywalled or scanned-image; citations
  triangulated across 3+ independent listings each. Treat wording as paraphrase.*
- **A measured analogy with hard numbers**: 88.8% of 12,671 annotated ICU arrhythmia alarms were false
  positives (some types 96.7%); *"Alarm fatigue occurs when clinicians are desensitized by numerous
  alarms... the cacophony of alarm sounds becomes 'background noise.'"* [S6 `[read directly]`]
  **Different domain — cite as the closest measured analogy, never as agent evidence.**
- **The vendor advocating the pattern concedes it**: *"This is also made harder when the user must
  approve many decisions and thus must make each approval quickly, reducing their ability to
  meaningfully consider each one,"* and ensuring the user *"has enough context to sufficiently
  understand the implications of the action they're approving"* is an open, unsolved problem [S1].
- **Degradation condition, stated precisely:** an approval gate degrades into a **pure latency tax with
  zero marginal safety value** once the base rate of "the agent was right" is high enough that the
  reviewer stops updating on each request. **This is a function of gate VOLUME, not gate existence** —
  the same gate flips from real control to theater with no code change.

**COST.** **No measured multiplier for approval-gate fatigue in agentic systems exists** — the clearest
thin spot in this pattern. Vendor "N FTEs rubber-stamping" estimates cite no study and are excluded.

**CHEAPER FIRST.** **Risk-tiered automation, not a blanket gate**: rate each action on read-vs-write,
reversibility, and financial impact; route only the high tier to a human; handle lower tiers with
deterministic policy checks that cost no human attention [S2].

**EVIDENCE GRADE: practitioner-consensus** for efficacy; `primary-measured` for the failure modes.

**Sources.** S1 Shavit, Agarwal, Brundage, Adler et al., *Practices for Governing Agentic AI Systems*, OpenAI 2023 `[read directly]` · S2 OpenAI, *Guardrails and human review*, API docs `[read directly]` · S3 Parasuraman & Riley, *Humans and Automation*, Human Factors 39(2) 1997 `[from memory — VERIFY]` · S4 Skitka, Mosier & Burdick, IJHCS 51(5) 1999 `[from memory — VERIFY]` · S5 Parasuraman, Molloy & Singh, Int. J. Aviation Psychology 3(1) 1993 `[from memory — VERIFY]` · S6 Drew et al., *Alarm Fatigue with Physiologic Monitor Devices*, PLoS ONE 2014 `[read directly]` · S7 OWASP Agentic AI "Overwhelming HITL" threat category `[UNVERIFIED — document not located]`

---

## 13. Retrieval (RAG)

**Extends primer §6 — lost-in-the-middle, staleness, and judge-input insufficiency (the third mode,
added 2026-09-03 / #4831) are authoritative there.** Adds the hard
mathematical ceiling, the context-rot corpus, and the honest LC-vs-RAG contest.

**WHEN.** Knowledge exceeds the context window, OR changes faster than re-prompting allows, OR is scoped
per-tenant; workload is dominated by **narrow lookups against a large corpus**; cost cannot absorb
reprocessing the corpus per call.

**WHY.** Anthropic's Contextual Retrieval gives a clean monotonic ablation, each step isolable
(baseline: top-20-chunk retrieval failure rate, embeddings only): **5.7% → 3.7%** (contextual
embeddings, −35%) **→ 2.9%** (+contextual BM25, −49%) **→ 1.9%** (+reranking, −67%) [S1].

**WHY NOT.**
- **Embedding retrieval has a proven mathematical ceiling, not a tunable defect.** DeepMind proves *"the
  number of top-k subsets of documents capable of being returned as the result of some query is limited
  by the dimension of the embedding"* via a sign-rank argument — **for any fixed embedding dimension,
  some correct top-k relevance patterns are unrepresentable by ANY single-vector model, independent of
  training quality.** Their LIMIT benchmark, on trivial queries ("who likes Apples?"), has leading models
  scoring **under 20 Recall@100** against a 50k-doc corpus, and failing on a **46-document** version at
  Recall@20 [S7]. **The strongest and most surprising counter-evidence in this file.**
- **Context rot — three independent benchmarks agree, and it starts well inside the advertised window.**
  RULER: *"while these models all claim context sizes of 32K tokens or greater, only half of them can
  maintain satisfactory performance at the length of 32K"* [S9]. Chroma, 18 frontier models: performance
  degrades for **every model tested**, and *"a model with a 200K token window exhibit[s] significant
  degradation at 50K tokens"*; *"even a single distractor reduces performance"* [S10]. NoLiMa: 10 models
  *"dropping below 50% of their strong short-length baselines at 32K"*; GPT-4o falls *"from an
  almost-perfect baseline of 99.3% to 69.7%"* [S11]. **This undercuts "just use long context" as much as
  it undercuts naive RAG.**
- **No chunking strategy dominates.** Contextual chunking beats traditional only marginally (NDCG@5
  0.317 vs 0.312) at *"2x"*–*"4x longer"* processing; late chunking wins on NFCorpus (0.380 vs 0.374)
  but **loses on MSMarco (0.503 vs 0.630)** [S6].
- **Seven documented failure points**: Missing Content · Missed Top-Ranked · Not in Context · Not
  Extracted · Wrong Format · Incorrect Specificity · Incomplete. The paper's own framing is itself a
  finding: *"validation of a RAG system is only feasible during operation"* and *"the robustness of a
  RAG system evolves rather than [being] designed in at the start"* [S8].
- **The LC-vs-RAG contest, reported honestly rather than resolved.** Four sources disagree: RAG wins via
  a chunk-count sweet spot [S3]; retrieval+small context ≈ big context, cheaper [S2]; *"LC generally
  outperforms RAG in question-answering... RAG has advantages in dialogue-based and general question
  queries"* [S4]; *"when resourced sufficiently, LC consistently outperforms RAG... However, RAG's
  significantly lower cost remains a distinct advantage"* with a hybrid Self-Route as the practical
  answer [S5]. **Universal agreement: RAG is cheaper. Disagreement: whether that costs quality —
  depends on task type and retrieval quality, not a fixed rule.**

**COST.** **No single clean multiplier exists** across the four head-to-head papers without blending
baselines — reported as a real gap, not filled with an invented number. Reranking is a known latency
adder whose magnitude could not be sourced at primary level.

**CHEAPER FIRST.** BM25 + off-the-shelf embeddings as the floor — hybrid lexical+dense captures ~49% of
Anthropic's full reduction (5.7%→2.9%) for a fraction of the pipeline. Add contextual annotation only if
the embedding retriever is proven the bottleneck; add a reranker only if correct chunks are retrieved
but ranked too low (FP2). **Diagnose which of the seven failure points is occurring before buying the
next-most-expensive fix.**

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Anthropic, *Contextual Retrieval* `[read directly]` · S2 Xu et al. (NVIDIA), *Retrieval meets Long Context LLMs*, arXiv:2310.03025 `[via WebSearch snippet]` · S3 Yu et al., *In Defense of RAG in the Era of Long-Context LLMs*, arXiv:2409.01666 `[read directly]` · S4 Li et al., *Long Context vs. RAG for LLMs*, arXiv:2501.01880 `[read directly]` · S5 Li et al., *RAG or Long-Context LLMs? A Comprehensive Study and Hybrid Approach*, EMNLP 2024 industry, arXiv:2407.16833 `[read directly]` · S6 *Reconstructing Context: Advanced Chunking Strategies*, arXiv:2504.19754 `[read directly]` · S7 Weller et al. (Google DeepMind), *On the Theoretical Limitations of Embedding-Based Retrieval*, arXiv:2508.21038 `[read directly]` · S8 Barnett et al., *Seven Failure Points When Engineering a RAG System*, IEEE/ACM AI Engineering 2024, arXiv:2401.05856 `[read directly]` · S9 Hsieh et al., *RULER*, arXiv:2404.06654 `[read directly]` · S10 Chroma, *Context Rot*, trychroma.com/research/context-rot `[read directly]` · S11 Modarressi et al., *NoLiMa*, ICML 2025, arXiv:2502.05167 `[via WebSearch snippet]` · S12 Anthropic, *Effective context engineering for AI agents* `[read directly]`

---

## 14. Inter-Agent Communication

**No primer coverage.**

**Definition.** Formal protocols and message contracts — schemas, IDs, lifecycle states, transport — so
independently-implemented agents can discover capabilities and exchange task requests without sharing a
process, memory, or filesystem. `platform-dependent` — the specs revise (MCP's 2026-07-28 revision
dropped session state outright), so the platform source wins over this entry.

**WHEN — narrower than "multi-agent system."** Two or more agents that are (a) **implemented/deployed
independently** (different vendor, team, or trust boundary) and (b) must delegate **across a network
boundary** where a shared filesystem or in-process call is unavailable. A coordinator and its own
subagents in one container **do not need this**.

**WHY.** MCP is genuinely formal and RFC-2119-graded, but narrower than "AI agent standard": it covers
tool/resource/prompt exposure, not agent-to-agent delegation; JSON-RPC 2.0 base; the 2026-07-28 revision
**dropped session state entirely** (session-ID handshake retired, correlation now per-request), and
`ttlMs`/`cacheScope` became mandated on list results [S1, S2]. A2A mandates real lifecycle structure:
server-generated Task IDs, named states (`SUBMITTED`/`WORKING`/`INPUT_REQUIRED`/`AUTH_REQUIRED` +
terminals), required message fields, capability-gated push notifications, and Agent Card discovery [S3].

**WHY NOT — the headline.**
- **No primary source measures whether a formal protocol beats plain function calls at small scale.**
  Every source located is either a **specification** (defines the contract; does not measure whether
  using it beats not using it) or a **governance/adoption announcement** (who signed on, not what it
  bought them). **On the evidence, this is a genuinely-specified but empirically-unevidenced pattern.**
- **MCP's security section mandates application-level consent, not protocol enforcement**: *"Hosts must
  obtain explicit user consent before invoking any tool"* and *"descriptions of tool behavior such as
  annotations should be considered untrusted"* — but explicitly, *"While MCP itself **cannot enforce
  these security principles at the protocol level**, implementors SHOULD..."* [S1]. **This is the
  clearest documented gap between what practitioners assume MCP guarantees and what it specifies.**
- **A2A does NOT mandate TTL/expiry** — *"Agents MAY implement context expiration or cleanup policies
  and SHOULD document any such policies."* No required window exists. This contradicts an
  enterprise-message-bus mental model [S3]. A2A also defines the **envelope, not an authorization model**
  for what an agent may delegate.
- **A named production counter-voice argues against the architecture this layer serves.** Cognition:
  subagents with partial context make *"conflicting assumptions not prescribed upfront"*; recommendation
  is *"single-threaded linear agents for most use cases"* [S6].
- **CORRECTED MISATTRIBUTION — record this.** A widely-repeated *"10-15x more tokens"* figure attributed
  to Cognition's *Don't Build Multi-Agents* **does not appear in that post; it states no token multiplier
  at all** (verified by direct fetch). The real sourced 4×/15× figures are **Anthropic's**, from the
  multi-agent research-system post, misattributed in secondary write-ups [S6, S7]. Our primer cites
  4×/15× correctly to Anthropic — **do not "correct" it toward the phantom figure.**

**COST.** **No source measures protocol overhead.** The only measured figure nearby is `~4× single-agent
/ ~15× multi-agent vs a single chat turn` [S7] — that is about **running multiple agents at all**, not
the wire protocol, and must not be presented as protocol cost.

**CHEAPER FIRST.** Inside one operator's own deployment: plain function calls / in-process delegation,
or a shared filesystem plus a lightweight message convention. Anthropic's own multiagent product does
exactly this — shared container and filesystem, typed thread events, **no JSON-RPC, no Agent Card, no
A2A** — because those agents are not independent implementations crossing a trust boundary [S8]. Reach
for MCP only to expose tools to a client you do not control; A2A only to interoperate with another
organization's agent.

**EVIDENCE GRADE: no-primary-source** (for efficacy). The specifications themselves are
`vendor-guidance`/standards-grade and verified.

**Sources.** S1 MCP, *Specification (2025-06-18)* `[read directly]` · S2 MCP blog, *The 2026-07-28 Specification* `[read directly]` · S3 A2A Protocol, *Specification*, a2a-protocol.org `[read directly]` · S4 Google Developers Blog, A2A/MCP relationship `[read directly]` · S5 Linux Foundation A2A press release — org list verified; the *"150 organizations"* figure `[from memory — VERIFY]` · S6 Cognition AI, *Don't Build Multi-Agents* `[read directly]` · S7 Anthropic, *How we built our multi-agent research system* `[read directly]` · S8 bundled `claude-api` skill, `shared/managed-agents-multiagent.md` `[read directly]` · S9 OWASP LLM06:2025 `[read directly]`

---

## 15. Resource-Aware Optimization

**Extends primer §10 — the four-token-field money model is authoritative there.** Adds the exact caching
multipliers from the vendor and the adversarial inversion. `platform-dependent` — the cache-read/write
multipliers below are current vendor pricing and are revisable; the live platform source wins.

**WHEN.** Task difficulty is **heterogeneous** and a cheap signal can classify it before committing to
the expensive model; a **prefix repeats** across calls (caching has nothing to save otherwise); and the
cost of a misroute is **bounded and acceptable** — an assumption the counter-evidence shows is not
always safe.

**WHY.** Cascades/routers: see pattern 2 (FrugalGPT, RouteLLM). **Caching, sourced exactly from the
vendor**: cache reads cost **0.1× base input price**; 5-minute writes **1.25×**; **1-hour writes 2×**
[S3]. This is the precise mechanism behind the primer's `cache_read`-dominance claim.

**WHY NOT.**
- **The adversarial inversion** [S4] — see pattern 2's WHY NOT. Under attack the entire cost band flips
  sign: **+148.9% cost, −84.6% accuracy, +81.4% jailbreak success**, transferring black-box.
- **Cascade termination rests on a signal documented as unreliable**: confidence estimates are
  miscalibrated and prompt-sensitive, and models are **most overconfident exactly where they are wrong**
  — the precise case early termination must catch [`[from memory — VERIFY]`, directionally consistent
  with the overconfidence literature but not independently verified].
- **Degrades when** input is adversarial or merely out-of-distribution relative to the router's training
  data (RouteLLM's transfer claim is about swapping model *pairs*, not OOD *queries*); when the
  cheap-tier confidence signal is trusted without verification; or when savings are measured only under
  benign traffic.

**COST.** `0.1× per cached-and-hit token vs no caching`; writes `1.25×` (5m) / `2×` (1h) — **caching only
pays once a prefix is reused within the TTL** [S3]. Routing: `over 2× vs always-strong-model` [S2];
`up to 98% vs GPT-4 alone` [S1]. Adversarial: `+148.9% vs the same cascade benign` [S4].

**CHEAPER FIRST.** **Prompt caching before any trained router** — no training data, no classifier, and
**no documented adversarial-inversion failure mode**, capturing most of the saving for the common
repeated-prefix agentic workload. Reach for a cascade only once caching is exhausted and query
difficulty is genuinely heterogeneous enough to justify the added attack surface.

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Chen, Zaharia & Zou, *FrugalGPT*, arXiv:2305.05176 `[read directly]` · S2 Ong et al., *RouteLLM*, arXiv:2406.18665 `[read directly]` — a secondary *"50x"* figure is **not in the paper**; its verified number is "over 2 times" · S3 Anthropic, *Prompt Caching*, platform docs `[read directly]` · S4 Sun, Chen & Li, *When Efficiency Backfires*, arXiv:2605.17288 (preprint) `[read directly]`

---

## 16. Reasoning Techniques

**Extends primer §3/§4 — self-consistency, debate economics, and verification-vs-generation are
authoritative there.** Adds CoT's own boundary conditions, ToT's cost, and inference-time-scaling limits.

**WHEN.** The problem has a large or combinatorial search space that a single forward pass does not
cover. **Not** when the bottleneck is missing information rather than insufficient reasoning steps —
see the ceiling below.

**WHY NOT — the new material, and it is substantial.**
- **CoT actively hurts on identifiable task shapes.** Drawing on cognitive-psychology tasks where
  deliberation makes *humans* worse: *"state-of-the-art models exhibit significant performance drop-offs
  with CoT (up to 36.3% absolute accuracy for OpenAI o1-preview compared to GPT-4o)"* on three of six
  tested tasks [S3]. **A falsifiable, task-shape-based prediction of when CoT hurts — not a vague
  caveat.**
- **A CoT trace is not a trustworthy audit log.** Silently biasing inputs (e.g. reordering options so the
  answer is always "(A)") causes accuracy to drop *"by as much as 36%"* while **the model's stated
  reasoning never mentions the bias it is actually following**; *"CoT explanations can be plausible yet
  misleading, which risks increasing our trust in LLMs without guaranteeing their safety"* [S4].
  **Direct implication: do not treat a reviewer agent's stated reasoning as evidence that the stated
  reasoning caused its verdict.**
- **CoT gains do not generalize as learned algorithms.** Improvements occur *"only... when those prompts
  are exceedingly specific to their problem class"* and *"quickly deteriorate as the size n of the
  query-specified stack grows past the size of stacks shown in the examples"*; gains *"do not stem from
  the model learning general algorithmic procedures"* [S5].
- **ToT's authors state its own limits**: *"Deliberate search such as ToT might not be necessary for many
  existing tasks that GPT-4 already excels at,"* and it *"requires significantly more computations"* —
  reserve it *"on tasks requiring deliberate reasoning, on which CoT struggles"* [S2].
- **Inverse scaling in test-time compute (TMLR, peer-reviewed).** Longer reasoning *reduces* accuracy on
  constructed tasks. Five failure modes: *"Claude models become increasingly distracted by irrelevant
  information"*; o-series *"overfit to problem framings"*; *"models shift from reasonable priors to
  spurious correlations"*; difficulty *"maintaining focus on complex deductive tasks"*; and the
  safety-relevant one — *"extended reasoning may amplify concerning behaviors, with Claude Sonnet 4
  showing increased expressions of self-preservation."* [S6] **"More thinking budget" is not a safe
  default knob.**
- **Overthinking / inverted-U**: *"models exhibit 'overthinking,' where extended reasoning is associated
  with abandoning previously correct answers"*; *"optimal thinking length varies across problem
  difficulty, suggesting that uniform compute allocation is suboptimal"* [S7].
- **A hard information-theoretic ceiling.** *"Compute-only test-time scaling, as a post-processing
  procedure of a fixed model, cannot introduce new information about the ground-truth answer,"* and
  longer reasoning *"encourages more attempts, many of which are incorrect,"* with *"patterns consistent
  with confirmation bias"* [S8]. **For a fact-lookup-shaped problem, add retrieval or tools — not
  thinking budget.**

**COST.** ToT vs **single CoT completion**: paper's own range **5–100× more generated tokens**; its own
same-success-tier table gives ≈**1.6× the cost of best-of-100 CoT** for 74% vs 49% on Game of 24 [S2].
Self-consistency vs **one greedy decode**: linear in K; the headline GSM8K result used **K=40 ≈ 40×**.
Debate vs **single-agent self-consistency**: `3–40×` (primer §3). Extended thinking vs **thinking off**:
**not a fixed multiplier** — billed 1:1 as output against the chosen budget.

**CHEAPER FIRST.** The evidence implies an escalation order: (1) one well-specified CoT prompt; (2)
self-consistency at **small K** before jumping to 40; (3) ToT only for genuinely combinatorial tasks its
authors say CoT struggles on; (4) debate last; (5) for extended thinking, start near the documented
minimum and raise only if quality misses the bar.

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Wang et al., *Self-Consistency*, ICLR 2023 (primer source) · S2 Yao et al., *Tree of Thoughts* `[read directly]` · S3 Liu, K. et al., *Mind Your Step (by Step)*, ICML 2025, arXiv:2410.21333 `[read directly]` · S4 Turpin et al., *Language Models Don't Always Say What They Think*, NeurIPS 2023, arXiv:2305.04388 `[read directly]` · S5 Stechly, Valmeekam & Kambhampati, *Chain of Thoughtlessness?*, NeurIPS 2024, arXiv:2405.04776 `[read directly]` · S6 Gema, Hägele et al. (Anthropic + Fellows), *Inverse Scaling in Test-Time Compute*, TMLR Dec 2025, arXiv:2507.14417 `[read directly]` · S7 *When More Thinking Hurts*, arXiv:2604.10739 (preprint) `[read directly]` — specific "2K vs 8K" thresholds **not confirmed** · S8 Zhao, Ng & Ng, *Test-Time Scaling in Reasoning Models Is Not Effective for Knowledge-Intensive Tasks Yet*, COLM 2026, arXiv:2509.06861 `[read directly]` · S9 Anthropic extended-thinking docs `[read directly]`

---

## 17. Evaluation & Monitoring

**Extends primer §8/§11 — attribution limits and self-preference are authoritative there.** Adds the
numeric backbone for judge bias and the production catch-rate evidence.

**LANE — defers to primer §9.** The review ladder is settled policy. This entry equips the agent to
audit an eval design; it is not grounds to re-propose a different review cadence for this runtime
without new review-outcome-ledger data.

**WHY.** The canonical validity claim: *"strong LLM judges like GPT-4 can match both controlled and
crowdsourced human preferences well, achieving over 80% agreement, the same level of agreement between
humans"* [S1]. **This is a SINGLE-TURN number. The same paper is also the source of the biases below and
must never be cited for the headline without them.**

**WHY NOT — with measured effect sizes.**
- **Position bias.** Judging identical answer pairs with order swapped (a perfect judge scores 100%):
  **GPT-4 self-consistent in 65.0%** of cases; **Claude-v1 in only 23.8%** (75.0% first-position bias)
  [S1]. Order manipulation alone let *"Vicuna-13B beat ChatGPT on 66 over 80 tested queries with ChatGPT
  as an evaluator"* [S2]. Cross-model robustness (1.0 = order-invariant): ChatGPT 0.566, GPT-4-Turbo
  0.818, GPT-4o 0.776, Claude-3.5 0.832 — and it drops *"below 0.5"* at three-to-four candidates [S3].
- **Verbosity bias, and it is not uniform.** Padding with duplicated content-free list items: **GPT-4
  failure rate 8.7%**; **Claude-v1 and GPT-3.5 failure rate 91.3%** [S1]. A mitigation tuned to one
  judge family will not transfer.
- **Self-enhancement, quantified.** GPT-4 favored its own answers at a **10pp higher win rate than human
  judges**; **Claude-v1 at 25pp** [S1]. **This is the closest available numeric backbone for the
  runtime's own same-family discount** — earlier than, and distinct from, Panickssery et al.
- **THE PRODUCTION RESULT — an LLM-judge gate that caught almost nothing.** A deployed bilingual
  multi-turn transaction agent: on one 100-round batch the judge gate **flagged 0 of 23 human-confirmed
  defects (0% recall)**; on another, **22% pattern recall (2 of 9)**. It emitted suspected-bug notes on
  **125 of 220 rounds yet triggered 0 of 220 gate failures** — it noticed, but the rubric never converted
  suspicion into a fail. **113 of 114 confirm-gate/state defects were mis-scored as "brand voice"**, and
  **50% of confirmed defect patterns fell into dimensions the rubric had no name for** [S7].
  **Treating MT-Bench's 80%+ single-turn agreement as if it transfers to trajectory judging is exactly
  the blended-baseline error this file exists to prevent.**
- **Benchmarks themselves mis-score agents**: *"SWE-bench Verified uses insufficient test cases while
  TAU-bench counts empty responses as successful, leading to under- or overestimation... by up to 100%
  in relative terms"*; a corrective checklist *"reduces the performance overestimation by 33%"* [S5].
- **Industry does not actually do formal agent eval.** 306 practitioners, 20 case studies, 26 domains:
  **75% evaluate agents with no formal benchmark**; 74.2% use human-in-the-loop; 51.6% use LLM-as-judge
  — **but every team combining a judge also kept a human check; none relied on the judge alone** [S6].
- **The cheap mitigations don't fix it**: top models *"detect errors made by LLMs at very low recall,"*
  and *"self-consistency and majority vote do not improve error-detection performance"* [S8 `[from
  memory — VERIFY]`].
- Agent eval is structurally harder: multi-turn state, non-determinism (*"a task that passed on one eval
  run might fail on the next"* → pass@k/pass^k), trajectory-vs-outcome, and partial credit [S4].

**COST.** **No clean multiplier vs a "no formal eval" baseline exists** in any primary source located —
reported as a gap.

**CHEAPER FIRST.** Targeted human review of sampled real transcripts plus production A/B testing —
per the 306-practitioner survey this is the **majority practice, arguably the pragmatic floor rather
than a compromise**, especially for multi-turn agents where judge-based gating silently passed the
overwhelming majority of real defects while still costing judge tokens on every transaction.

**EVIDENCE GRADE: primary-measured.**

**Sources.** S1 Zheng et al., *Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena*, NeurIPS 2023 D&B, arXiv:2306.05685 `[read directly, bias tables]` · S2 Wang et al., *Large Language Models are not Fair Evaluators*, ACL 2024, arXiv:2305.17926 `[read directly]` · S3 Ye, Wang, Huang et al., *Justice or Prejudice?*, arXiv:2410.02736 `[read directly]` · S4 Anthropic, *Demystifying Evals for AI Agents* `[read directly]` · S5 Zhu et al., *Establishing Best Practices for Building Rigorous Agentic Benchmarks*, NeurIPS 2025, arXiv:2507.02825 `[read directly, search-summary level]` · S6 Pan, Arabzadeh et al., *Measuring Agents in Production*, arXiv:2512.04123 `[read directly]` · S7 Zhang, Wang & Lei, *Catching One in Five: LLM-as-Judge Blind Spots in Production Multi-Turn Transaction Agents*, arXiv:2606.10315 (preprint) `[read directly]` · S8 Kamoi et al., *Evaluating LLMs at Detecting Errors in LLM Responses*, COLM 2024, arXiv:2404.03602 `[from memory — VERIFY]`

---

## 18. Guardrails & Safety

**No primer coverage.** `platform-dependent` — the OWASP LLM Top 10 has a 2026 edition superseding the
2025 list quoted below, and vendor guardrail products change; the platform/standards source wins.

**LANE — `trust-architect` owns agentic security.** Primer §9 is explicit: *"Agentic security is
trust-architect's lane... Do not re-propose a dedicated agentic-security specialist."* **The seam:**
this agent judges a guardrail as **DESIGN** (is the mechanism structurally sound, is it a probabilistic
filter doing a structural job); trust-architect judges it as **security CONTROL**. Filed once,
cross-referenced, never duplicated.

**WHEN.** Any agent that (a) ingests content from outside the operator's control — including **tool
output that itself came from an external system** (the indirect-injection surface) — or (b) can take a
real-world action or emit sensitive output.

**WHERE — two genuinely different layers, and the why-not hinges on not confusing them.**
Input/output filtering is **probabilistic**; sandboxing and least-privilege tool scoping are
**structural infrastructure** — what the process can physically do, independent of any classifier.

**WHY.** OWASP Top 10 for LLM Applications **2025**: LLM01 Prompt Injection · LLM02 Sensitive Information
Disclosure · LLM03 Supply Chain · LLM04 Data and Model Poisoning · LLM05 Improper Output Handling ·
LLM06 Excessive Agency · LLM07 System Prompt Leakage · LLM08 Vector and Embedding Weaknesses · LLM09
Misinformation · LLM10 Unbounded Consumption [S1]. **A 2026 edition exists and supersedes this list; its
entry-level list could not be extracted — treat the above as last-confirmed, not necessarily current.**
Indirect injection's founding paper demonstrated practical viability *"against both real-world systems,
such as Bing's GPT-4 powered Chat and code-completion engines"* [S2]. Structural defenses: *"Minimal
initial scope set... containing only low-risk discovery/read operations"* with step-up elevation, and
*"Execute MCP server commands in a sandboxed environment with minimal default privileges"* [S3]; OWASP's
agent cheat sheet: *"Grant agents the minimum tools required"* and *"per-tool permission scoping"* [S4].

**WHY NOT.**
- **OWASP states its own #1 risk is not solved by the techniques teams reach for first**: *"While
  techniques like Retrieval Augmented Generation (RAG) and fine-tuning aim to make LLM outputs more
  relevant and accurate, research shows that they do not fully mitigate prompt injection
  vulnerabilities."* [S1]
- **Measured guardrail bypass, up to total.** Six defense systems including Azure Prompt Shield and Meta
  Prompt Guard: character-injection and adversarial-ML evasion *"can be used to evade detection while
  maintaining adversarial utility achieving in some instances up to 100% evasion success"* [S5].
- **The mechanism for why filtering is structurally insufficient**: *"competing objectives"* and
  *"mismatched generalization"*, concluding **safety-capability parity** — *"safety mechanisms should be
  as sophisticated as the underlying model"*; scaling the filter without scaling its sophistication does
  not close the gap [S6].
- **No guardrail approach dominates** — the field's own SoK exists precisely because none has been shown
  sufficient [S7].
- **The structural tradeoff, stated precisely:** tightening a probabilistic filter to close the bypass
  rates above **necessarily raises its false-positive rate on legitimate traffic**, because it cannot
  distinguish "crafted to look legitimate" from "genuinely legitimate and merely resembles the pattern."
  **A correctly-scoped permission boundary does not share this tradeoff** — it blocks nothing that was
  never in scope, and fails closed. An agent that cannot physically call a destructive tool cannot be
  talked into calling it, regardless of how the injection succeeds.

**COST.** **No primary source gives a filtered-vs-unfiltered cost multiplier.** The 100% evasion figure
is a **bypass rate, not a cost band** — presenting it as one would misrepresent what was measured.

**CHEAPER FIRST.** **Least-privilege tool scoping and sandboxing before — or instead of, for
irreversible tools — ever-more-sophisticated content filtering.** A minimal read-only initial scope with
step-up elevation is cheap, structural rather than probabilistic, and closes the gap OWASP names
**without needing to solve prompt-injection detection at all** for the tools it scopes away [S3].

**EVIDENCE GRADE: primary-measured** (for the failure modes and the structural alternative).

**Sources.** S1 OWASP GenAI Security Project, *OWASP Top 10 for LLM Applications 2025*, official PDF `[read directly]` · S2 Greshake, Abdelnabi, Mishra, Endres, Holz & Fritz, *Not what you've signed up for*, arXiv:2302.12173 `[read directly]` · S3 MCP, *Security Best Practices* `[read directly]` · S4 OWASP, *AI Agent Security Cheat Sheet* `[read directly]` · S5 Hackett, Birch, Trawicki, Suri & Garraghan, *Bypassing LLM Guardrails*, LLMSec 2025, arXiv:2504.11168 `[read directly]` · S6 Wei, Haghtalab & Steinhardt, *Jailbroken: How Does LLM Safety Training Fail?*, NeurIPS 2023, arXiv:2307.02483 `[read directly]` · S7 Wang, Ji et al., *SoK: Evaluating Jailbreak Guardrails*, arXiv:2506.10597 `[read directly, abstract only]` · S8 Shavit et al., *Practices for Governing Agentic AI Systems*, OpenAI `[read directly]` · S9 NIST AI 600-1 `[UNVERIFIED at quote level]`

---

## 19. Prioritization

**No primer coverage.**

**LANE — `launch-director` owns ranking.** The agent definition is explicit: this agent's audit is
*"never used to rank other work — ranking against the app's one goal is `launch-director`'s lane."*
**The seam: this agent may audit whether a ranking MECHANISM is sound; it never performs the ranking.**

**Definition.** Scoring and ordering candidate work by value × effort × urgency × risk, revised as
conditions change.

**WHY — and this is the headline: there is essentially no supporting evidence.**
**No primary study was found that measures an LLM ranking a real work queue by a
value×effort×urgency×risk formula and beating a simple heuristic or a human.** What exists is adjacent
and weaker: a tool-description paper that **defers its own evaluation** to *"a future case study"* [S3];
and a vulnerability-triage evaluation (4 LLMs × 12 prompting techniques, 384 real vulnerabilities) whose
best sub-task result was F1=0.79 but whose agreement with expert judgment was **Cohen's κ 0.06–0.10
("none to slight")**, concluding *"LLMs cannot yet replace expert judgment"* — and which **does not
compare against CVSS or any heuristic baseline at all** [S2].

**WHY NOT.**
- **LLM rankings are internally inconsistent, independent of accuracy.** Testing pairwise judgments for
  ranking people for scarce resources on two independent consistency measures: *"No model
  Pareto-dominates across both dimensions"* — the model with the best run-to-run stability had the worst
  internal circular-triad consistency, and vice versa. *"Real-world LLM data exhibits approximately
  constant inconsistency rates as problem size increases."* Their explicit warning: choosing a model on
  a single consistency diagnostic *"can be actively misleading"* [S1].
- **Unstable under mere reordering of identical inputs** — position bias makes raw LLM ranking
  untrustworthy without post-hoc statistical correction [S8 `[from memory — VERIFY]`].
- **The three biases that would corrupt exactly this ranking** (position, verbosity, self-preference —
  measured effect sizes in pattern 17) predict: swayed by which item is listed first, over-ranking
  verbose tickets over terse-but-important ones, and — where the same model both proposes and ranks work
  — systematically over-ranking its own proposals. *No paper tested a value×effort×urgency×risk backlog
  specifically; this application is reasoned inference from measured bias mechanisms, flagged as such.*
- **The formula itself is unvalidated.** RICE (Intercom, 2016) and WSJF (SAFe) are **product-management
  heuristics with no peer-reviewed validation found**, regardless of whether a human or an LLM applies
  them. Layering an LLM on top adds documented biases **on top of an already-unvalidated formula**.

**COST.** **Not computable** — no source gives a multiplier for "LLM ranks the backlog" vs "a formula
ranks the backlog." The dominant cost is not compute but **the risk of an inconsistent or biased ranking
silently misdirecting effort** — documented in kind, not in a comparable unit.

**CHEAPER FIRST.** A **deterministic weighted-sum formula**, computed identically every time and
re-sorted mechanically when an input changes — no position bias, no verbosity bias, no self-preference,
fully reproducible and auditable. Reserve the LLM for estimating a formula *input* from unstructured
text (e.g. inferring risk from an incident description) rather than owning the final ranking end-to-end.

**EVIDENCE GRADE: no-primary-source** for the pattern's core claim. **State this plainly rather than
softening it — this pattern is substantially practitioner folklore.**

**Sources.** S1 Pokharel, Farabi, Fowler & Das, *Can LLMs Rank? A Tale of Triads and Triage*, arXiv:2606.30412 (preprint) `[read directly]` · S2 Al Haddad, Ikram, Ahmed & Lee, *Prompting the Priorities*, arXiv:2510.18508 `[read directly]` · S3 Sami et al., *Prioritizing Software Requirements Using LLMs*, arXiv:2405.01564 `[from memory — VERIFY]` — cited for its **absence** of a completed evaluation · S4–S7 judge-bias sources: see pattern 17 · S8 Ma, Cheng, Zhu & Xiong, *Large Language Models are Not Stable Recommender Systems*, arXiv:2312.15746 `[from memory — VERIFY]` · S9 RICE (McBride, Intercom 2016) and WSJF (SAFe) — practitioner frameworks, not peer-reviewed

---

## 20. Exploration & Discovery

**No primer coverage.**

**LANE — `sentinel` owns discovery sweeps.** This agent may audit whether an exploration LOOP is well
designed; running discovery sweeps is sentinel's scheduled lane (CLAUDE.md §13).

**Honest framing first.** The evidence is **thin and split across unrelated sub-fields** (game-world,
codebase, hypothesis-space) that share a label more than a mechanism. Treat this as an **umbrella over
at least two distinct evidenced mechanisms, not one unified pattern.**

**WHEN.** The space is large and the query specific enough that single-shot retrieval measurably
underperforms multi-step interaction; or the task requires **finding what you don't know to look for**
rather than retrieving a known answer.

**WHERE.** Single-agent control loop — this is a **loop-shape** pattern, not an orchestration one.

**WHY.** **Codebase exploration is a real, measured, distinct capability.** 848 issues across 10
languages: *"Sparse retrievers (BM25, TF–IDF) and the lightweight dense retriever remain close to Random
on most metrics, while every agentic explorer is substantially higher."* Agentic explorers reach ~**64%
file-hit-rate vs ~8–14%** for sparse retrievers; nDCG@500 **0.88 vs 0.13**. *"Repository exploration is
not well captured by one-shot lexical or embedding retrieval alone."* [S1] Open-ended hypothesis
exploration: MCTS + Bayesian surprise discovered *"5-29% more hypotheses deemed surprising"*, best on 17
of 21 datasets, with **human-grounded** validation — *"two-thirds of discoveries... are surprising to
domain experts"*, surprise metric **67% correlated with human surprisal** (95% CI [0.63, 0.71], 1,620
hypotheses) [S2]. **One paper, one author cluster — promising, not established.**

**WHY NOT.**
- **A simpler non-agentic pipeline beat agentic exploration outright, at a fraction of the cost.** A
  fixed three-phase pipeline (localize → repair → validate) with **no LLM-driven action planning**
  achieved *"both the highest performance (32.00%, 96 correct fixes) and low cost ($0.70) compared with
  all existing open-source software agents"*, framed as an explicit challenge: *"Do we really have to
  employ complex autonomous software agents?"* [S4] **The honest synthesis: open-ended agentic
  exploration beats naive single-shot retrieval, but loses to a well-engineered staged pipeline. The
  comparison that matters is exploration-vs-staged-pipeline, not exploration-vs-nothing.**
- **The advantage collapses at fine granularity.** File-level recall is strong but **line-level recall
  averages only ~15–19%**, F1 0.19–0.24 — *"the limiting term is usually line-level recall"* [S1].
  **Scope any claimed benefit to file/region-level discovery, never fine-grained localization.**
- **Autonomous research mostly fails.** Four end-to-end attempts with a 6-agent pipeline: *"three
  attempts failed during implementation or evaluation. One completed the pipeline"* — **25%**, with six
  named failure modes including *"overexcitement that declares success despite obvious failures"* [S5].
  *Small-N: treat 25% as illustrative, the failure taxonomy as the durable part.*
- **Automation reduces visibility into what is actually being discovered** [S6 `[read directly,
  partial — thesis only, no numbers extractable]`].
- **Novelty alone is likely insufficient without a directing signal** — surfaced in search but **never
  fetched; explicitly UNVERIFIED and flagged for a future pass** [S7].

**COST.** **No clean exploration-vs-retrieval multiplier exists.** Exploration's cost is iteration count,
not an agent-count multiplier. The Agentless `$0.70` figure compares a non-agentic pipeline to *full
agents*, not an exploration loop to retrieval — **do not manufacture a multiplier that was not
measured.**

**CHEAPER FIRST.** For codebases: a **well-engineered staged pipeline** (localize → repair → validate),
verified to beat full agentic exploration on cost and, at publication, accuracy. For hypothesis
generation: a **directed search with an explicit reward or surprise signal** rather than undirected
"explore everything." For well-specified lookups: **plain retrieval** — the agentic premium is earned
only when retrieval is independently shown near-random on the task.

**EVIDENCE GRADE: primary-measured** per sub-domain; **practitioner-consensus** for the umbrella pattern
as a single thing.

**Sources.** S1 *SWE-Explore: Benchmarking How Coding Agents Explore Repositories*, arXiv:2606.07297 (preprint) `[read directly]` · S2 Agarwal, Majumder, Adamson et al., *AutoDiscovery: Open-ended Scientific Discovery via Bayesian Surprise*, NeurIPS 2025, arXiv:2507.00310 `[read directly]` · S3 Wang, Xie et al., *Voyager*, arXiv:2305.16291 `[read directly]` — **Minecraft-specific; its 3.3×/2.3×/15.3× numbers do NOT transfer to code or document corpora** · S4 *Agentless: Demystifying LLM-based Software Engineering Agents*, arXiv:2407.01489 `[read directly]` · S5 *Why LLMs Aren't Scientists Yet*, arXiv:2601.03315 `[read directly]` · S6 Luo, Kasirzadeh & Shah, *The More You Automate, the Less You See*, arXiv:2509.08713 `[read directly, partial]` · S7 *Discovery under Hypothesis Redundancy*, arXiv:2606.14386 **`[NOT fetched — do not treat as verified]`**

---

## Could not source at primary level (consolidated)

Every item below is a real gap in the evidence base or in this research pass — **not** something to fill
with a plausible number later. A §15 claim resting on any of these must say so.

**Missing head-to-head comparisons (the most consequential class):**
- Prompt chaining vs. a single-call baseline, with an accuracy delta. The compounding case is
  mechanistic, not a demonstrated regression.
- A formal inter-agent protocol (MCP/A2A) vs. plain function calls / shared filesystem at small scale —
  latency, defect rate, or engineering cost, either arm. **Not found anywhere.**
- An LLM value×effort×urgency×risk ranking vs. a deterministic RICE/WSJF formula or a human, scored on
  the same backlog. **This is the central gap for pattern 19 and it is absent.**
- An exploration-loop vs. single-shot-retrieval token-cost multiplier.
- A full eval/golden-set/judge pipeline vs. a "no formal eval" baseline, in cost terms.
- A genuinely **online**, continuously self-improving production agent loop. All credible evidence is
  offline optimization against a fixed benchmark, later frozen and shipped.
- A study measuring **agent retry non-determinism** directly (rerun on identical input N times, report
  divergence rate). Pattern 11's claim on this is structural reasoning, not a measured finding.
- A study measuring an agent's self-reported "percent complete" against ground-truth completion.

**Numbers that exist but could not be pinned:**
- MemGPT's and A-MEM's headline benchmark results (architecture verified, magnitude not).
- MAST's category-level roll-ups (two extractions disagree; per-mode figures are reliable).
- Self-Refine per-task deltas; self-consistency's exact K=40/56.5%→74.4% pairing; ToT's Creative
  Writing / Mini Crossword numbers; overthinking's "2K vs 8K" thresholds.
- ADaPT's token/call-count multiplier vs ReAct; its abstract's "27% on WebShop" vs the table's 12.0pp.
- Skeleton-of-Thought's exact speedup ("considerable" in the abstract; a secondary "1.9× / ten LLMs"
  conflicts with the abstract's "12 LLMs").
- Reranker latency figures (blog-tier only); the verbosity-bias +17.3%/+12.9% pair.
- Numeric effect sizes from the TextGrad critique and the self-evolving-risk paper (degraded PDF).
- Blackboard/shared-memory contention and staleness **rates** (names confirmed, magnitudes not).
- The Tool Search Tool's own discovery-step recall as libraries grow past what was tested.
- A measured cost for approval-gate fatigue in agentic systems specifically.

**Sources that exist but could not be opened (cite title/venue only, never a number):**
- *Capable language models can outgrow the benefits of collaboration*, Nature MI 2026 — auth-blocked.
  On-point for "when does multi-agent stop helping"; deserves a follow-up fetch.
- Parasuraman & Riley 1997; Skitka, Mosier & Burdick 1999; Parasuraman, Molloy & Singh 1993 — paywalled
  or scanned-image. Citations triangulated 3+ ways; **wording is paraphrase, not quotation.**
- Nygard's *Release It!*; Garcia-Molina & Salem's *Sagas* (1987).
- NIST AI 600-1 — existence and scope confirmed via secondary summaries only.
- The **OWASP GenAI LLM Top 10 2026 edition's entry list** — confirmed to exist and supersede the 2025
  list; entries not extractable. **The 2025 list in pattern 18 is last-confirmed, not necessarily
  current.** `platform-dependent` — re-check before relying on it.
- OWASP Agentic AI Threats & Mitigations ("Overwhelming HITL").
- *Discovery under Hypothesis Redundancy*, arXiv:2606.14386.

**Claims actively EXCLUDED as unsupported (recorded so they are not silently reintroduced):**
- A vivid "April 30, 2026" router-misclassification fraud incident — reads as an illustrative vendor
  example, not a citable postmortem. **Excluded, not reported as fact.**
- The *"10-15x more tokens"* figure attributed to Cognition's *Don't Build Multi-Agents* — **verified
  absent from that post.** The real 4×/15× figures are Anthropic's. See pattern 14.
- A *"50x"* RouteLLM saving — the paper's own number is "over 2 times."
- Galileo AI's "87% of downstream decisions poisoned within four hours" — no primary report located.
- Composio's 33%→74% function-calling figure — Medium-tier only.
- Embedding-model negation-failure ("a blue shirt with no logos") — no fetchable primary source.
- Vendor "N FTEs rubber-stamping approvals" estimates — cite no measured study.
