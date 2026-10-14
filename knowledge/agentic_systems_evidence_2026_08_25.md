# Agentic-systems design claims: what primary sources actually show (2026-08-25)

Research note, not a primer yet. Standard applied: peer-reviewed papers, official vendor engineering
guidance, competition rules/results, and systematic meta-analyses. Blogs and vendor marketing were
found, flagged, and excluded. Gathered to evaluate the claim "agentic systems with a feedback loop,
consensus, and fact storage typically win collegiate competitions," and to seed the bibliography of a
possible `agentic-systems-architect` oversight agent.

## Verdict on the bundled claim

**Not supported as stated by any primary source.** Each leg has real support *in isolation, for the
right task type*; the conjunction as a competition-winning recipe is stated nowhere, and the best
meta-analysis of a real multi-team competition explicitly declines to attribute the win to any
architectural pattern.

| Leg | Evidence | Caveat that matters here |
|---|---|---|
| Feedback loops | Reflexion (NeurIPS 2023): HumanEval 80%→91%. Self-Refine (NeurIPS 2023): ~20pp avg. CRITIC (ICLR 2024). | **Only when grounded in an external checkable signal** (tests, tool output, retrieved facts). Huang et al. (ICLR 2024): ungrounded self-critique does not help and can **degrade** results. |
| Consensus / voting / debate | Self-consistency (ICLR 2023): GSM8K +17.9pp. Multi-agent debate (ICML 2024): GSM8K 77→85. | Non-monotonic with scale (Chen et al. 2024: rises then **falls** with more calls). "Stop Overvaluing Multi-Agent Debate" (2025): debate **often fails to beat single-agent self-consistency** at far more compute. Cost 3–40× base. |
| Fact storage / memory | RAG (NeurIPS 2020) is foundational; Google's whitepaper treats data stores as a core tool type. | Two documented failure modes: **lost-in-the-middle** (TACL 2023 — accuracy is U-shaped by position even when the right fact is retrieved) and **staleness** (a retriever cannot prefer a current fact over an outdated one of equal similarity). **Absent from every winning-architecture record reviewed.** |
| Verification vs. generation | Process supervision beats outcome supervision (Lightman et al., ICLR 2024). | "When To Solve, When To Verify" (2025): generative verification needs up to **~8× the compute** of self-consistency just to match it; compute-optimal favours generation at most budgets. Not a strict hierarchy; budget-dependent. |
| Decomposition / unit size | Least-to-Most (ICLR 2023): SCAN 16%→99%. **ADaPT (NAACL 2024): +27–33pp** on ALFWorld/WebShop/TextCraft. | ADaPT's gain comes from **adaptive** decomposition — split only when a unit fails to execute — not maximal upfront splitting. (This is exactly the "plateau = split" rule, not a numeric file cap.) |

## What competitions actually show

- **ICPC World Finals 2025** (OpenAI 12/12, Gemini 10/12): Gemini = multiple agents + test execution +
  iteration (feedback + ensemble). OpenAI = GPT-5 then a second model as **sequential fallback**, not
  voting. **No fact store described by either.**
- **DARPA AIxCC** (USENIX Security 2026 SoK): feedback loops common; explicit **voting used by 2 of 7
  finalists**; verification-style feedback (multi-PoV validation, post-patch fuzzing) correlated with
  higher patch accuracy; the champion won through **"sustained availability across all phases"**;
  the SoK states attribution to any single technique "is inherently difficult." No knowledge store.
- **AIMO** (Kaggle): self-consistency + code-execution feedback; later entropy-weighted voting and a
  learned selector beating majority vote. No memory component.

## What the three vendors' own guidance says

All three converge on **start single-agent; add agents only for a specific structural reason**
(parallelizable work, context limits, tool count, workflow branching). **None names consensus or
voting as a default pattern.**
- Anthropic, *Building Effective Agents*: "building the right system for your needs… add multi-step
  agentic systems only when simpler solutions fall short." Evaluator-optimizer is gated on *clear
  evaluation criteria*. *Multi-agent research system*: ~4× the tokens of a single chat for agentic
  work, **~15× for a full multi-agent configuration** (not a per-added-agent multiplier).
- OpenAI, *A Practical Guide to Building Agents*: "maximize a single agent's capabilities first."
  Two orchestration patterns (Manager, Decentralized); guardrails are layered output verification.
- Google, *Agents* whitepaper: the orchestration loop is **definitional**; data stores are a core
  tool type; self-consistency is one named CoT sub-technique.

## The structural caveat

"Stop Comparing LLM Agents Without Disclosing the Harness" (2026): the harness — context
construction, tool orchestration, verification scaffolding — **often dominates model choice**, with
documented ranking reversals. Cross-system architecture claims are unreliable unless harnesses are
matched. Corollary for this runtime: our own ledgers are better evidence about our own harness than
any external result.

## Curated primer bibliography (17)

1. Anthropic, *Building Effective Agents* — the "start simple" doctrine to measure creep against.
2. Anthropic, *How we built our multi-agent research system* — 90.2% (self-reported) and 4×/15× cost.
3. OpenAI, *A Practical Guide to Building Agents* — against premature multi-agent split.
4. Google, *Agents* whitepaper — model + tools + orchestration + data stores.
5. Huang et al., *LLMs Cannot Self-Correct Reasoning Yet* (ICLR 2024) — counter-evidence to ungrounded reflection.
6. Shinn et al., *Reflexion* (NeurIPS 2023) — the canonical grounded feedback-loop result.
7. *Stop Overvaluing Multi-Agent Debate* (2025) — counter-evidence to consensus-by-default.
8. Chen et al., *Are More LLM Calls All You Need?* (2024) — consensus is non-monotonic.
9. *When To Solve, When To Verify* (2025) — compute-optimal verification vs. consensus.
10. Lightman et al., *Let's Verify Step by Step* (ICLR 2024) — process > outcome supervision.
11. Liu et al., *Lost in the Middle* (TACL 2023) — the fact-store failure mode any KB must design for.
12. Prasad et al., *ADaPT* (NAACL 2024) — adaptive decomposition, with numbers.
13. Zhang et al., *SoK: DARPA AIxCC* (USENIX Security 2026) — the one real competition meta-analysis.
14. *Stop Comparing LLM Agents Without Disclosing the Harness* (2026) — the harness confound.
15. METR, *Measuring AI Ability to Complete Long Software Tasks* (2025) — external capability trendline.
16. Anthropic, bundled `claude-api` skill — `shared/prompt-caching.md` (added 2026-08-27; a platform doc
    extracted at session start under a version-keyed temporary path — cite by skill + doc, never by
    path). Prefix-match caching, render order, fork/prefix reuse, silent invalidators. Primer §10.
17. Panickssery, Bowman & Feng, *LLM Evaluators Recognize and Favor Their Own Generations* (2024;
    added 2026-08-27) — self-recognition causally drives self-preference in LLM judges. Primer §11.
    [from memory — see the Flagged list below; verify venue + identifier before citing]

## Feedback-loop, delivery-flow, and agentic-factory doctrine (added 2026-08-29)

Second research pass, same primary-source standard, gathered to upgrade the agentic-systems-
architect agent from "audits ML-agent architecture literature" to "is a domain expert in feedback-
loop engineering and agentic-factory design, able to prescribe concrete redesigns." Four parallel
research agents (WebSearch/WebFetch, not memory) verified 18 further sources; most of the highest-
stakes claims were confirmed by directly fetching and reading the primary text (Wiener's own 1948
pages, Boyd's briefings as reproduced in Richards 2020, both DORA reports' own PDFs, the DevOps
Handbook's publisher-hosted excerpt, Google's SRE book, the 2002 flow-state chapter, and Anthropic's
and Stripe's own current engineering posts) rather than search-snippet paraphrase. Full claim-level
detail with quotes and page numbers is in this session's research transcript; this section carries
the caveats that matter before any of these citations are used in a report.

**Confirmed at primary-text level (highest confidence):** Wiener's *Cybernetics* (1948) closed-loop
chain, negative feedback, and gain/oscillation math (read directly, pp.128–139); Boyd's OODA loop
as tempo-and-orientation, not raw speed (Richards 2020, read directly, reproducing Boyd's own 1996
sketch); the 2019 and 2024 DORA *Accelerate State of DevOps* reports' own performance-cluster
tables and headline multipliers (both PDFs fetched and text-extracted directly); *The DevOps
Handbook*'s formal statement of The Three Ways (publisher-hosted excerpt PDF, quoted verbatim);
Google's SRE book on alert fatigue (sre.google, read directly); Nakamura & Csikszentmihalyi's 2002
restatement of the three flow-state preconditions (chapter PDF, read directly); Anthropic's
*When to use multi-agent systems (and when not to)* (2026) and *Subagents in the SDK* docs (fetched
directly); Stripe's *Minions* engineering post (fetched directly, not a third-party recap).

**Caveats that must travel with specific claims, not just live in this note:**
- The widely-repeated "**208× more frequent deployments / 106× faster lead time / 2,604× faster
  recovery / 7× lower change failure rate**" statistic, commonly attributed to the 2019 DORA
  report, does **not** appear anywhere in that report's actual text (its "How Do We Compare?"
  section and Appendix A give only bucketed ranges, never point multipliers). **Cite the 2024
  report's own verified headline instead — 127×/182×/8×/2293× — never the 208× figure.**
- Ohno's exact wording on "stopping is cheaper than a downstream defect" could not be pulled from a
  readable copy of *Toyota Production System* itself (the located PDF was bot-gated). The
  jidoka/andon mechanism, its Toyoda-loom origin, and its stop-the-line economics are solidly
  triple-corroborated (Wikipedia's Autonomation article, Toyota's own corporate description, and —
  the strongest leg — Spear & Bowen's peer-reviewed HBR study of real Toyota plants). Cite Ohno's
  book by title for the CONCEPT; do not present any specific sentence as an Ohno verbatim quote.
- Goldratt's most-quoted lines ("an hour lost at the bottleneck..."; "an hour saved at a
  non-bottleneck is a mirage") are consistently attested across many independent Theory-of-
  Constraints secondary sources but were not verified against a page-numbered scan of the 1984
  novel itself. Treat as a well-established paraphrase of the book's teaching, not a page-checked
  verbatim quote.
- Reinertsen's specific principle labels (B1, B3, B4, B8/B9, Q1–Q3) came from a third-party
  book-notes page, not the book's own text — the labels are reported-by-summary; the substantive
  batch-size/cost-of-delay claim is well corroborated independently (multiple reviews of the same
  book plus the parallel Toyota heijunka/lot-size-reduction literature).
- Two Anthropic posts state two DIFFERENT, non-contradictory token-overhead multipliers for
  multi-agent work: the 2025 multi-agent research post says multi-agent is "~15× the tokens of a
  single chat"; the 2026 "when to use multi-agent systems" post says multi-agent is "3–10× a
  single-agent approach." These measure different baselines (chat vs. single-agent) at different
  times — **always state which baseline a cited figure uses; never blend them into one number.**
  This is the same discipline primer §1 already applies to its own 4×/15× figures.
- The application of Goodhart's Law specifically to "a gameable feedback-loop correction signal in
  an agentic-review pipeline" is this research pass's own synthesis, not a claim stated that way in
  any primary source — the underlying law (Goodhart 1975; Strathern's 1997 restatement) is solidly
  verified; this specific framing of it is not independently citable beyond that general principle.
- Bacchelli & Bird's *Expectations, Outcomes, and Challenges of Modern Code Review* (ICSE 2013) is
  real, peer-reviewed, and about code review at Microsoft — but no specific finding within it about
  "review latency causes larger batch sizes / big-bang merges" could be confirmed. That mechanism
  is better and more safely grounded in *Continuous Delivery*'s own explicit "integration hell"
  thesis (Humble & Farley, verified directly); do not attribute the batching-mechanism claim to
  Bacchelli & Bird.
- Control-theory vocabulary (open-loop/closed-loop, gain/damping/overshoot, hysteresis, the Smith
  Predictor's dead-time treatment) is genuinely textbook-standard, confirmed via convergent
  search-engine corroboration across named, real, correctly-cited textbooks (Nise; Ogata;
  Åström & Murray; Lipták's handbook; Smith 1957) — but not via a direct page-by-page read of those
  texts the way Wiener and the DORA reports were verified. Treat as solid but lighter-weight
  sourcing than the directly-read primary texts above.

New bibliography entries 18–35 (control theory, Lean/TPS/Theory of Constraints, DORA/DevOps
delivery-flow research, flow-state psychology, and current Anthropic/Stripe agentic-factory
guidance) are listed in the primer's own Sources section — this note does not duplicate the list,
per the primer's own "never hand-maintain a second copy" discipline (§12).

## Flagged: could not source at primary level

- "80% of enterprise RAG projects fail" — vendor blog only; do not cite.
- SWE-bench leakage ~32% — reported in secondary summaries of 2025 papers; unverified from full text.
- RAG 14-failure-mode taxonomy — hosted on a non-standard preprint server; downgrade.
- Venue status of *More Agents Is All You Need* and *Stop Overvaluing MAD* — preprints at fetch time.
- Entry 17 (Panickssery et al.) was added from memory on 2026-08-27 without a fetch — the title and
  authors are held with high confidence, the venue (believed NeurIPS 2024) and arXiv identifier are
  NOT; verify both before the primer cites it in any report. Entry 16 is a bundled platform doc and
  needs no external verification, only a fresh read each run.
- "208× more frequent deployments / 106× faster lead time / 2,604× faster recovery / 7× lower
  change failure rate," commonly attributed to the 2019 DORA report — does not appear anywhere in
  that report's own text (added 2026-08-29); do not cite. Cite the 2024 report's own verified
  127×/182×/8×/2293× headline instead.
- "Review latency causes larger batch sizes / big-bang merges" attributed specifically to
  Bacchelli & Bird (ICSE 2013) — the paper is real but no such specific finding within it could be
  confirmed (added 2026-08-29); cite *Continuous Delivery*'s "integration hell" thesis for this
  mechanism instead.
