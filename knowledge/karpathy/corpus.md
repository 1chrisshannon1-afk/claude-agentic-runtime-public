# Karpathy corpus (distilled, cited — research-scout dispatch 2026-08-31)

```
bounded: false
repos_examined: 4
rounds_used: 10
```

(Repos examined = repos for which `/license` was actually queried: `karpathy/autoresearch`,
`karpathy/nanochat`, `karpathy/nanoGPT`, `karpathy/micrograd`. Rounds = WebSearch/`gh api
search/*` calls only, per the primer's definition.)

---

# Software 2.0 (2017 essay)

**Source:** Andrej Karpathy, "Software 2.0," *Medium*, published November 2017. Primary URL: https://karpathy.medium.com/software-2-0-a64152b37c35 (fetch blocked by Medium's bot wall during this sweep — HTTP 403 — so direct quotes below are drawn from secondary coverage that itself quotes the essay; the URL is verified live and is the correct primary citation. Treat any unquoted paraphrase here as UNVERIFIED against the primary text until a session can read it directly.)

**Core thesis.** Most software ("Software 1.0") is explicit source code — instructions written by humans, encoding a programmer's understanding directly into logic. "Software 2.0" is code written not by a human but by an optimization process (gradient descent) against a dataset and an objective. The artifact a Software-2.0 "programmer" produces is not a program text but a **dataset and a loss function**; the weights of the trained network are the compiled binary. Reported framing from secondary sources, treated as paraphrase rather than verbatim: "datasets are the new source code, model weights are the new binaries, gradient descent is the new compiler." The essay recasts neural-network training as a *programming methodology*, not merely a modeling technique.

**What it predicts.** A shift in where engineering effort concentrates: away from hand-writing control flow and toward (a) curating and cleaning training data, (b) specifying the objective/loss precisely, and (c) building the infrastructure to evaluate, version, and roll back trained artifacts the way 1.0 shops version code (the essay explicitly draws the analogy to CI/CD, code review, and version control needing 2.0-native equivalents — dataset diffing, training-run provenance, evaluation harnesses as the "test suite"). Software 2.0 gradually subsumes 1.0 in domains where the mapping from input to correct output is easy to *specify by example* but hard to *write down as explicit logic* — perception, ranking, pattern-recognition-heavy tasks lead.

**Where it applies / doesn't (his stated caveats).** It applies where (1) a large, correctly-labeled dataset can be assembled or generated, (2) the task tolerates statistical/probabilistic correctness rather than requiring provably exact behavior, and (3) the cost of an occasional wrong output is bounded (recoverable), not catastrophic-and-silent. It is a poor fit for logic that must be exact, auditable, and provably correct by construction (financial ledger arithmetic, cryptographic protocols, anything needing a formal correctness guarantee) — those stay 1.0. **This boundary condition is the single most load-bearing part of the essay for any downstream architect** — it is not a blanket "ML replaces code" claim, and treating it as one is a documented misreading the essay itself heads off.

**Confidence note.** Thesis, prediction, and boundary-condition claims are corroborated across multiple independent secondary sources (Seth Weidman's response essay, the MindStudio retrospective, the "frenxt" retrospective, paper-notes summaries) that converge on the same reading. Nothing here is a verbatim quote unless explicitly marked.

---

# HydraNet (Tesla)

**Source:** Karpathy's Tesla AI talks — Tesla Autonomy Day (Apr 2019), PyTorch DevCon 2019, CVPR 2020/2021 workshop talks, and Tesla AI Day (Aug 19, 2021). These talks are the primary source; this sweep could not fetch a transcript directly (the most detailed secondary retrospective, Lance Martin's "Tesla's arc of AI progress," returned HTTP 403). Findings are sourced from WebSearch snippets of that retrospective plus corroborating coverage (thinkautonomous.ai, towardsdatascience's AI Day 2021 review) — **UNVERIFIED against the primary talk audio/transcript**; re-verify any specific number before treating it as load-bearing.

**The architecture.** HydraNet (named for the multi-headed Hydra) is Tesla's multi-task perception design: one shared convolutional/transformer **backbone** extracts general visual features once per frame, then many **task-specific heads** (object detection, lane lines, traffic lights, depth, etc.) branch off that shared trunk, each producing its own output. A single expensive feature-extraction pass is amortized across dozens of downstream tasks rather than running a separate full network per task.

**Why it was chosen.** (1) **Compute amortization** — N independent networks for N tasks is N× the inference cost on the car's fixed onboard compute budget; a shared backbone with N cheap heads is close to 1× the backbone cost. (2) **Training/iteration decoupling** — heads can be fine-tuned individually from **cached features** (the backbone's output is cached once, then reused to train/evaluate many heads without re-running the expensive backbone forward pass), letting different teams iterate on their own head without a full end-to-end retrain per change. Full backbone retraining happens periodically, not per-head-change.

**Cost/consistency trade-offs.** Upside: inference cost and engineering-org parallelism. Trade-off: a shared backbone couples every head's quality to the backbone's feature quality — a backbone deficiency propagates to all heads simultaneously — and the infrequent full retrain means backbone improvements lag head-level iteration, creating a periodic "catch up the backbone" cycle. This is the classic multi-task-learning tension (shared representation efficiency vs. per-task specialization) applied at production scale under a hard latency/compute ceiling.

---

# BEV vector space (Tesla)

**Source:** Same talk lineage — Tesla AI Day (Aug 19, 2021) is the primary source for the mature architecture; earlier CVPR 2020 talks describe an intermediate "pseudo-lidar" approach BEV superseded. Sourced via WebSearch snippets of secondary coverage — **UNVERIFIED against the primary talk**, same caveat as HydraNet.

**The mechanism.** Tesla's pipeline takes 8 cameras' worth of raw 2D video, rectifies it, runs each through a shared visual backbone, and then — instead of running per-camera object detection and later fusing 8 independent detection sets — a transformer-based fusion step lifts and combines the per-camera FEATURES into **one canonical bird's-eye-view (BEV) vector space**: a single, metric, top-down representation of the scene that all downstream planning/control consumes. Multi-camera BEV features are cached alongside vehicle kinematics into a feature/video queue so temporal context (motion, occlusion reasoning) is available without re-running the backbone every frame.

**Why per-camera 2D reasoning failed.** When you detect objects independently *within* each 2D camera image and only afterward project/stitch per-camera detections into a shared top-down space, small per-pixel depth errors compound into noisy, inconsistent results — the same physical lane line detected slightly differently by two overlapping cameras doesn't line up. An intermediate fix (CVPR 2020 era) built a pseudo-lidar point cloud per camera — better, but still fusing after per-camera detection. The AI-Day-2021 fix moved fusion **before** detection: features (not detections) are fused across cameras into the shared BEV space by a learned transformer, and detection/planning heads operate directly on that single unified representation — there is only ever one scene representation, never N per-camera ones to reconcile.

**Why this matters beyond driving.** This is the general "**fuse early, in a canonical shared representation, rather than fuse late across independently-reasoned-about views**" pattern — recurring anywhere multiple partial/noisy observations of one underlying ground truth must combine before a decision is made on top of them.

---

# DenseCap (Stanford PhD)

**Source:** Justin Johnson, Andrej Karpathy, Li Fei-Fei, "DenseCap: Fully Convolutional Localization Networks for Dense Captioning," arXiv:1511.07571 (Nov 24, 2015; CVPR 2016). Primary URL: https://arxiv.org/abs/1511.07571 — **fetched directly and successfully in this sweep.** Part of Karpathy's Stanford PhD thesis, "Connecting Images and Natural Language" (2016).

**The task.** Dense captioning generalizes two previously-distinct tasks into one: it generalizes **object detection** when a region's description collapses to a single word, and generalizes **image captioning** when a single predicted region covers the whole image. Given an image: jointly localize *and* describe, in natural language, every salient region — many region-caption pairs per image.

**The architecture (FCLN — Fully Convolutional Localization Network).** Three components chained into a single, end-to-end trainable, single-forward-pass model: (1) a convolutional network for feature extraction; (2) a novel **dense localization layer** proposing candidate regions directly from convolutional features — **no external region-proposal step**; (3) a recurrent language model generating a caption per localized region. A full image processes in one forward pass (~240ms for 720×600) and trains end-to-end with one round of optimization — no multi-stage pipeline of independently trained components.

**Output structure.** Per image: a set of **(region, caption, confidence)** triples. Evaluated on Visual Genome — ~94,000 images, ~4.1 million region-grounded captions — outperforming baselines built from separately-trained detection + captioning pipelines.

**Why architecturally notable beyond the task.** An early, concrete instance of "collapse a multi-stage pipeline of independently-optimized components into one jointly-trained, end-to-end model with a single richer output structure" — localization and description were separate systems glued together; DenseCap trains them jointly against one loss and emits one structured output per region.

---

# AutoResearch (karpathy/autoresearch, 2026)

**Source:** the GitHub repository's README.md and `program.md`, **fetched directly via `gh api` in this sweep (primary source).** Metadata: created 2026-03-06, last pushed 2026-03-26, 95,002 stars at sweep time. Description: "AI agents running research on single-GPU nanochat training automatically."

**License — FLAGGED DISCREPANCY (directly verified).** The README's footer states "License: MIT," but the GitHub `/license` endpoint (`gh api repos/karpathy/autoresearch/license`) returns **404 Not Found**, and a root-contents listing confirms **no LICENSE file exists**. **LEARN-FROM ceiling only, never COPY** — a bare README license claim with no backing LICENSE file is exactly the ambiguous case the license-ceiling rule exists for. (Contrast: `nanochat`, `nanoGPT`, `micrograd` all cleanly return `MIT` from the same endpoint with real LICENSE files.)

**The actual mechanism, as documented.** AutoResearch gives a coding agent ("Claude/Codex or whatever") a small, real, single-GPU LLM-training setup and lets it experiment **overnight, autonomously, unattended**. Deliberately three files:
- `prepare.py` — fixed constants, one-time data prep, the evaluation harness. **Never modified by the agent** — the immutable ground-truth measurement layer.
- `train.py` — the **only** file the agent edits: model, optimizer, training loop. Everything in it is fair game.
- `program.md` — the **charter file**, edited by the human (not the agent): operating instructions, constraints, loop protocol. Karpathy's framing: "you're not touching any of the Python files like you normally would as a researcher. Instead, you are programming the `program.md` Markdown files."

**Bounded experiments.** Every training run has a **fixed 5-minute wall-clock budget** (excluding startup) — deliberate, not incidental: experiments are directly comparable (the budget, not the platform, is the constant), yielding ~12 experiments/hour, ~100 overnight.

**Metric evaluation.** One scoring metric: `val_bpb` (validation bits-per-byte), chosen for vocabulary-size independence so architectural changes stay comparable. `evaluate_bpb` in `prepare.py` is called out as "ground truth" and off-limits — **the agent cannot edit the yardstick it is measured against.**

**Git keep/revert loop (the actual safety mechanism).** `program.md` specifies deterministically: (1) inspect git branch/commit state, (2) hack on `train.py` with one experimental idea, (3) `git commit`, (4) run training with output to a log, (5) grep the log for the metric, (6) empty grep = crash — read the traceback, attempt a fix, give up after a few tries, (7) log the result to an **untracked** `results.tsv` (never committed), (8) if `val_bpb` improved, keep the commit; if equal or worse, `git reset` back. All work on a dedicated `autoresearch/<tag>` branch, never `master`.

**What makes the loop safe (structural, not instructional).** Four compounding constraints bound the blast radius of a fully unattended loop: (a) **a single mutable file**; (b) **a fixed, small time budget per attempt** — no bad idea runs away with unbounded compute; (c) **an immutable, agent-inaccessible scoring function** — the goalposts cannot move; (d) **git as the undo mechanism** — every experiment is a commit, a worse result is mechanically reverted, a bad idea never accumulates. `program.md` also states a **"simplicity criterion"**: a marginal improvement that adds meaningful complexity is discouraged in favor of equal-or-better results from *deleting* code — anti-gold-plating baked into the charter.

**What makes it unsafe / the honest limit.** `program.md` explicitly instructs "**NEVER STOP**... do NOT pause to ask the human if you should continue... The loop runs until the human interrupts you, period." A genuinely unattended, indefinite loop by design — the safety case rests entirely on the narrowness of what the agent can touch and the cheapness/reversibility of each attempt, not on any judgment or approval gate. Explicitly **not** general-purpose: one file, one metric, one hardware target. It generalizes only to problems sharing this shape — a single mutable surface, a cheap fast feedback signal, an immutable external scorer — never to open-ended agentic work against a large multi-file production codebase with no equivalently cheap ground-truth metric.

---

# Vibe coding → agentic engineering (2026)

**Sources:** (1) the original "vibe coding" tweet, Feb 6, 2025 (X/Twitter `@karpathy`) — direct fetch returned HTTP 402 (paywall); the definition is reconstructed from consistent, widely-corroborated secondary quotation (vibecodinghistory.com, coderabbit.ai, frenxt.com) — high-confidence but **not literally re-verified against the tweet**. (2) The "agentic engineering" reframing — Karpathy's blog, `karpathy.bearblog.dev/sequoia-ascent-2026/`, published **Apr 30, 2026** — **fetched directly in this sweep; a genuine primary-source read.**

**Vibe coding, as originally stated (Feb 2025).** Reported verbatim across sources: "fully give in to the vibes, embrace exponentials, and forget that the code even exists," and "I just see stuff, say stuff, run stuff, and copy-paste stuff, and it mostly works." He later described the tweet as "a shower of thoughts throwaway tweet," meant for throwaway weekend/prototype projects — not production software — an intent later widespread use drifted from.

**Agentic engineering (Apr 2026 post, quoted directly from the fetched page).**
- Vibe coding: **"raises the floor. It lets almost anyone create software by describing what they want."**
- Agentic engineering: **"raises the ceiling. It is the professional discipline of coordinating fallible agents while preserving correctness, security, taste, and maintainability."**

Serious teams need agentic engineering — professionals who "design specs, supervise plans, inspect diffs, write tests, create evaluation loops, manage permissions."

**The human-orchestrates/agents-execute claim (direct quote):** **"The unit of programming changed from typing lines of code to delegating larger 'macro actions': Implement this feature. Refactor this subsystem. Research this library."** The human stays "in charge of aesthetics, judgment, taste, and oversight"; hiring should test whether a candidate can "decompose work for agents" and "preserve quality while moving fast."

**Reading the two together.** Vibe coding was never retracted — it was scope-narrowed: right for low-stakes throwaway work, while agentic engineering is the superset professional discipline for anything that ships and gets maintained. The distinguishing test is not "are you using an agent" (both modes do) but whether disciplined human supervision — specs, plan review, diff inspection, tests, eval loops, permission scoping — stands between the agent's output and what ships.

---

# Minimal-implementation pedagogy (micrograd, nanoGPT, nanochat, Zero-to-Hero, Eureka Labs)

**Sources (all fetched directly, primary):** `micrograd`, `nanoGPT`, `nanochat` READMEs (all three MIT, verified via `/license`); `karpathy/LLM101n` README (Eureka Labs' course repo, archived pending course development; its license unchecked this sweep). Zero-to-Hero (the YouTube lecture series) was not independently fetched — treat Zero-to-Hero-specific claims as UNVERIFIED.

**The philosophy, stated consistently across every repo.** Each artifact deliberately minimizes lines of code and dependencies in service of full inspectability — the code itself *is* the explanation.

- **micrograd:** "A tiny Autograd engine... about 100 and 50 lines of code respectively... Potentially useful for educational purposes." Scalar-valued deliberately — "we chop up each neuron into all of its individual tiny adds and multiplies" — trading performance entirely for every operation being individually inspectable.
- **nanoGPT:** a rewrite of the more didactic minGPT that **"prioritizes teeth over education"** — minimalism serving *usability and hackability* (a real GPT-2-reproducing trainer): "`train.py` is a ~300-line boilerplate training loop and `model.py` a ~300-line GPT model definition... That's it." "Because the code is so simple, it is very easy to hack to your needs."
- **nanochat:** the full still-minimal pipeline, tokenization → inference, whose stated principle takes the pattern one step further — **"nanochat is written and configured around one single dial of complexity — the depth of the transformer,"** with every other hyperparameter computed from that one dial: minimal *interface*, not just minimal code.
- **LLM101n / Eureka Labs:** epigraph — Feynman's "What I cannot create, I do not understand." A linear syllabus building a full LLM from a bigram model up, "from scratch in Python, C and CUDA," each chapter independently buildable before the next composes on it.

**The 2026 extension (bearblog post, primary).** He describes **"microGPT"** as "a complete GPT training and inference implementation in a single dependency-free Python file," noting even *coding agents* struggle to simplify it further — the artifact becomes **"small enough for both humans and agents to inspect."** The same minimal-canonical-implementation principle that served human pedagogy is now framed as a *requirement for an agent to safely reason about and modify code* — which is exactly why AutoResearch scopes its agent to one small editable file.

**The unifying claim.** One clean, minimal, canonical implementation is **the unit of understanding** — not a comprehensive framework with flags for every variant, but the smallest version that still does the real thing end-to-end, on the theory that a learner (human or agent) understands a mechanism by holding the entire implementation in their head at once.

---

# Applicability Index

One line per section, mapped generically onto four consuming-architecture shapes. Each names the mechanism, not a product.

**Software 2.0 (dataset-as-source-code)**
- (a) Estimating-SaaS vision/data pipeline: the boundary condition is the load-bearing part — perception/extraction stages are legitimately 2.0-shaped (dataset+eval), but pricing/business-rule logic that must be exact and auditable stays 1.0; conflating the two is the named failure mode.
- (b) Ops-automation playbook loops: a playbook's *triggering/classification* step is 2.0-shaped; the *action* it takes stays 1.0-exact and reviewable.
- (c) Advisory-LLM/deterministic-rails trading system: the canonical worked example of the boundary itself — advisory stays 2.0, execution/risk rails stay 1.0, never the reverse.
- (d) Multi-agent dev runtime: agent judgment is 2.0-shaped and probabilistic; the gates around it are 1.0-exact by design — the gate architecture is an implicit bet on this split.

**HydraNet (shared backbone / many heads)**
- (a) One shared feature-extraction pass over a photo feeding many independent downstream scorers, rather than re-analyzing per trade.
- (b) One shared context-gathering/normalization pass feeding many playbook heads, instead of each re-fetching raw state.
- (c) One shared market-feature layer feeding multiple signal heads — with the same coupling risk (a shared-feature defect propagates to every signal at once).
- (d) The oversight roster's shared grounding-read (dossier/primer) feeding many agent "heads" is the same pattern — a stale shared dossier degrades every consumer at once, the direct analogue of a backbone defect.

**BEV vector space (fuse early into one canonical space)**
- (a) Fuse multiple photos of one room into one canonical measured representation *before* line-item generation — the per-photo-then-reconcile shape is exactly the failure mode this replaced.
- (b) Fuse multiple signal sources into one canonical state representation before a playbook decides.
- (c) Fuse multiple feeds/venues into one canonical market-state representation before any strategy reasons over it.
- (d) Fuse multiple agents' partial findings into one canonical shared state before a decision/report — how a fan-out sweep's findings should consolidate before being acted on.

**DenseCap (joint localization + description, single structured output)**
- (a) A vision step emitting `(region, item-description, confidence)` triples in one pass rather than a "where" detector and a "what" classifier bolted together.
- (b) A detector emitting `(affected-resource, diagnosis, confidence)` jointly.
- (c) A signal emitting `(instrument, rationale, confidence)` jointly — confidence-scored structured joint output is the transferable piece.
- (d) A review/audit agent emitting `(finding-location, description, severity/confidence)` per finding — close to what findings ledgers already do; DenseCap is the earliest documented instance of that output shape.

**AutoResearch (charter file + bounded experiments + immutable metric + git keep/revert)**
- (a) An unattended tuning loop for a scoring/calibration parameter is safe under this shape ONLY with an immutable, agent-inaccessible ground-truth evaluator and a cheap fast per-attempt cost.
- (b) Close to a direct template for a self-tuning playbook-parameter loop — one mutable surface, fixed evaluation window, immutable success metric, keep/revert via version control.
- (c) Maps to unattended strategy-parameter search ONLY inside a walk-forward-safe immutable-backtest-metric sandbox with hard bounds per attempt; the repo's "NEVER STOP" posture is the part needing the most scrutiny near money.
- (d) **The most directly transplantable mechanism in the corpus** — structurally identical to a nightly bounded finishing-loop (bounded items, isolation, non-destructive revert, never-push, stop-on-strikes); independent convergent prior art for that design, worth citing when justifying or extending it. The delta worth porting: a MEASURED keep condition (metric-gated keep/revert on a frozen instrument), which the review-gated loop lacks.

**Vibe coding → agentic engineering**
- (a)/(b) Throwaway one-off scripts are vibe-shaped; anything on a shipped path needs the full discipline (spec, plan review, diff inspection, tests, eval loop).
- (c) The sharpest-stakes instance — nothing money-adjacent is ever vibe-coded; "agent is fallible, human stays accountable for spec/quality/security" reads as a mission statement for deterministic rails.
- (d) A direct description of a plan-review + commit-review cadence — Opus review at plan and commit boundaries is the mechanized version of "supervise plans, inspect diffs, write tests, create evaluation loops, manage permissions."

**Minimal-implementation pedagogy (one clean canonical implementation)**
- (a) One golden minimal reference implementation of a core calculation, small enough to fully audit, beats a comprehensive configurable version as ground truth.
- (b) One small canonical reference playbook per pattern-class beats a mega-playbook.
- (c) A minimal fully-auditable reference strategy/backtest is the trust anchor other strategies validate against.
- (d) The explicit rationale (his own 2026 words) for keeping agent-edited files small and single-purpose — directly relevant to partition-by-file-before-dispatch and to why AutoResearch scopes its agent to one file.

---

**Evidence-quality notes for future refreshes:** Software 2.0's primary text and the vibe-coding tweet were not directly readable (Medium 403 / X 402); both sections rest on convergent secondary quotation, flagged inline. HydraNet/BEV rest on secondary coverage of the primary Tesla talks (publicly recorded — re-verify numbers via transcript access before any becomes load-bearing). DenseCap (arXiv), AutoResearch (repo content), and the Apr-2026 bearblog post were direct primary-source reads — highest confidence. The AutoResearch license discrepancy (README "MIT" vs `/license` 404) is a directly-verified fact; preserve it verbatim — it is exactly the case a future COPY-grade sweep would get wrong by trusting the README.
