# agentic-systems-architect — repo-local grounding dossier (__PRODUCT_NAME__)

FACTS ONLY, fully enumerated. Not a tracker, not a plan. Every count carries its own re-derive
command + an as-of date. VERIFIED = read/grepped/run live this pass; UNVERIFIED = not opened this
pass, do not cite as fact. A missing or stale section here means the agent declares itself
DEGRADED for that repo's in-app agentic-system scope and says so explicitly — the runtime-level
audit (this machine's own `agents/`, `hooks/`, `CLAUDE.md`) still runs in full regardless.

## (a) What the in-app agentic system IS — inventory + dispatch topology

*What goes here: every agent definition this repo carries under its own `.claude/agents/*.md`
(this is the repo's OWN in-app agent roster — separate from the runtime roster this file's own
agent belongs to), each one's tools/model pin, and any customer-facing in-app agent that lives in
product code rather than `.claude/`. The auditor needs this to know what dispatch topology exists
before it can judge convergence, verification economics, or grounding quality against it.*
Re-derive shape: `` `ls <your-repo>/.claude/agents/*.md | wc -l` ``, `` `grep -n '^model:' <your-repo>/.claude/agents/*.md` ``.

- __IN_APP_AGENT_ROSTER__ — *list each in-app agent definition, its class (orchestrator /
  fan-out worker / verifier / architect), its `tools:`/`model:` pin, and one line of its stated
  purpose.*
- __IN_APP_ORCHESTRATOR__ — *the one agent (if any) carrying the `Agent` tool itself, i.e. able to
  dispatch its own sub-agents. Note its `model:` pin explicitly — an orchestrator dispatching its
  own sub-agents is exactly the shape a stale/missing pin is most costly on.*
- __FAN_OUT_WORKER_CLASS__ — *any group of agents dispatched in parallel by the orchestrator above
  (e.g. per-domain specialists) — their shared tool grant, their routing map (which worker handles
  which input), and whether each carries its own explicit model pin or silently inherits one.*
- __VERIFIER_AGENT__ — *any agent whose stated job is to re-check another agent's claims against a
  real document rather than trust its output — name its wiring point (which step of which flow
  actually calls it) and whether it is exercised routinely or only occasionally (a dispatch-count
  check, not a prose claim).*
- __CUSTOMER_FACING_AGENT__ — *any agent that talks to paying customers directly (chat/voice
  copilot, etc.) — lives in product code, not `.claude/`; name its module path, tool-registry/
  action-gate mechanism, and default enforcement posture (on/off by default, and why).*
- __DISPATCH_TOPOLOGY_DIAGRAM__ — *the actual wiring, as run, not as implied by naming: which
  slash command or product surface invokes which agent, and which agents that agent in turn
  dispatches. Draw it as a small arrow diagram, not prose — this is the fastest way for the next
  audit to spot a topology drift.*

## (b) The two skills that orchestrate the GC/trade flow

*What goes here: any skill files (`.claude/skills/<name>/SKILL.md`) that orchestrate a
multi-agent review flow — trigger syntax, procedure, and how findings get filed. The auditor needs
this to distinguish a wired flow from an aspirational one.* Re-derive: `` `ls -d <your-repo>/.claude/skills/*/ | wc -l` ``.

- __ORCHESTRATION_SKILLS__ — *for each relevant skill: trigger command, procedure summary, and
  what verification step (if any) it delegates to a separate verifier agent.*
- __NON_DISPATCHING_RUNBOOKS__ — *any operator-invoked diagnostic/runbook skill that the MAIN
  session runs directly and that never itself dispatches an `Agent`-tool sub-agent — name these
  so they are excluded from the dispatch-topology diagram above by design, not by omission.*

## (c) Knowledge surfaces — location + readers

*What goes here: where this app's domain knowledge base lives (corpus, facts, manifests) and
which agents actually read which parts of it — including any "dead-weight" surfaces a pipeline
stage writes but nothing reads back. The auditor needs this for grounding-quality judgments (axis:
is a claim backed by a real, checkable document or by model memory).* Re-derive:
`` `ls <your-knowledge-base-dir>` ``, `` `grep -rln "<manifest-token>" <your-repo>/.claude/agents/*.md` ``.

- __KNOWLEDGE_BASE_ROOT__ — *the top-level path of this app's domain knowledge corpus, if any.*
- __KNOWLEDGE_READERS__ — *which agents Read-FIRST which subdirectory/file of it — and whether
  that wiring is confirmed by grep or only claimed by a heading (a heading can over-claim; verify
  before repeating it as fact).*
- __KNOWLEDGE_CITATION_DISCIPLINE__ — *the stated rule each knowledge-consuming agent follows for
  citing its source (e.g. "cite the document, never recall it from memory") and any verification
  gate designed to confirm that discipline is actually honored, not merely stated.*
- __DEAD_WEIGHT_SURFACES__ — *any pipeline-stage output directory with no confirmed reader
  anywhere in `.claude/` — named honestly, not silently omitted.*

## (d) Standing decisions this auditor must not re-litigate

*What goes here: settled architectural/product decisions (e.g. "engine X is the only engine",
"doc Y is canonical and non-negotiable") that this auditor should treat as closed, with their
citation, so a fresh audit does not waste a pass re-opening them.* See `.claude/oversight/manifest.json`
for the canonical tracker-doc path, if this repo has one.

- __STANDING_DECISION_1__ — *one settled decision + its citation (doc heading, issue number).*
- __STANDING_DECISION_TESTING_ENVIRONMENT__ — *this repo's own where-to-test rule, if it binds any
  repro command this auditor might suggest running — cite it, never re-litigate it.*
- __RULING_GUARD_ALLOWLIST_CEILING__ — *if this repo runs any kind of advisory guard-count
  ceiling with a standing operator ruling on how new entries should be reviewed, the operator
  records that ruling here — italic note only; do not guess the ruling's content.*

## (e) Known gaps — VERIFIED with the grep that shows each

*What goes here: currently-open gaps in the in-app agentic system's wiring (a verifier not
actually wired into its intended review flow, an untracked file, a stale heading claim) — each
with the grep/command that proves it, and its issue number or "UNTRACKED" if none exists yet.*

- __KNOWN_GAP_1__ — *gap + grep proof + issue link or UNTRACKED.*
- __CLOSED_GAP_HISTORY__ — *a gap that was found and fixed since the last pass — keep one worked
  example here as a reminder that a "VERIFIED, zero callers" fact can go stale in days, not as a
  running incident log (drop the rest at the next rewrite).*

## (f) Axis-specific pointers

*What goes here: repo-specific facts that feed the primer's own audit axes — fan-out sizing (how
many workers can one orchestrator dispatch, against what machine-wide ceiling), verification
economics (ratio of generator dispatches to verifier dispatches, measured not assumed), and
grounding quality (does every worker cite a real document rather than recall one).* Re-derive:
`` `grep -c '"agent_type": "<verifier-name>"' ~/.claude/.agent_budget/spend.jsonl` ``.

- __FAN_OUT_SIZING__ — *max parallel workers one orchestrator can dispatch, and the machine-wide
  concurrency ceiling it competes against.*
- __VERIFICATION_ECONOMICS__ — *measured verifier:generator dispatch ratio, with its re-derive
  command.*
- __GROUNDING_QUALITY__ — *the citation discipline each worker is supposed to follow, and the
  mechanism (if any) that checks it.*

## (g) The loop's own measurement surfaces

*What goes here: if this app runs any kind of self-correcting review/fix loop (a scenario ledger,
a cause registry, an exit-contract convergence evaluator, cycle telemetry), list each surface with
its path and re-derive command. The auditor needs this to judge the loop's OWN convergence — this
section is the loop's instrumentation inventory, never its findings.* See `.claude/oversight/manifest.json`
for standing per-loop config this repo has already centralized.

- __LOOP_LEDGER_PATH__ — *the append-only ledger of reviewed rounds/scenarios, if one exists.*
- __LOOP_CAUSE_REGISTRY__ — *the durable cause-key registry a convergence evaluator consults.*
- __LOOP_EXIT_CONTRACT__ — *the offline evaluator module and its named convergence assertions.*
- __LOOP_CYCLE_TELEMETRY__ — *where per-cycle records land (path, system id).*
- __LOOP_SPEND_OR_CHURN_ORACLE__ — *if the runtime's own churn/spend reporting tool measures a
  DIFFERENT ledger than this loop's own round cadence, say so explicitly — naming the distinction
  once here saves the next audit from re-discovering it.*

## How to re-derive every count in this file

*What goes here: the full set of grep/ls/python one-liners this dossier's own facts depend on, so
the next audit can re-run every one of them rather than trusting a frozen number.*

__RE_DERIVE_COMMAND_BLOCK__
