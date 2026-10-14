"""sync_agent_rules — validate the operating contract against the agent defs.

Read-only consistency validator. The operating contract (`~/.claude/CLAUDE.md`)
and the agent definitions (`~/.claude/agents/*.md`) must stay mutually
consistent: every agent the contract names must exist, every agent must be
anchored to the contract, and no agent may restate a contract fact (its Opus
review roster, its `CSA_*` switch names, its `scripts/*.sh` helper paths) with a
value that has DRIFTED from the contract.

This module never rewrites the docs. It emits problems only. main() is SHAPED
like a `Stop` hook (reads a Stop event, would emit a block via
`_lib.emit_stop_block` only when enforcing() and never when disabled()) — but as
of this writing it is NOT registered in `settings.json`'s `Stop` hooks array, so
it never fires automatically off a live Stop event; today it only ever runs via
manual/ad hoc invocation (e.g. a CLI check, `< /dev/null` for stdin). Re-verify
against `settings.json` before describing it as wired. Deny/block is via JSON,
never via exit code — main() always exits 0 so a validator hiccup can never
wedge the agent.

PORTED FROM: ~/.claude/CLAUDE.md (the contract IS the spec here). The checks
below encode the contract's own invariants:
  * §1  "Use the defined agents in ~/.claude/agents/ as written" -> every agent
        the contract references by role name must exist as an agent def.
  * §10 "An Opus plan-reviewer ... An Opus code-reviewer ..." -> those two
        agents' frontmatter model must be `opus`.
  * §7  the CSA_* switch names (CSA_DISABLE_HOOKS / CSA_ENFORCE / CSA_SKIP_REVIEW)
        are declared by the contract; an agent naming a CSA_* var the contract
        does not = drift.
  * §7/§8/§9 the scripts/*.sh helper paths are declared by the contract; an
        agent naming a scripts/*.sh path the contract does not = drift.
  * every real agent def is anchored with "operate under ~/.claude/CLAUDE.md";
        an agent missing that anchor has silently detached from the contract.
  * §1/§2 "Use the defined agents in ~/.claude/agents/ as written" +
        "harness-native worktree isolation is sanctioned" -> a worktree's own
        .claude/agents/<name>.md must never silently REPLACE (last-write-wins
        name resolution) a runtime agent of the same name for a session
        running inside it (AUDIT FINDING 3, 2026-09-03, #4744) —
        find_worktree_agent_twins() scans every registered repo's
        .claude/worktrees/*/.claude/agents/*.md for exactly this collision.

Shared-lib API used: read_event, cwd, disabled, enforcing, emit_stop_block, log.
"""

from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402  (import after sys.path shim, mirrors sibling modules)

HOOK_NAME = "sync_agent_rules"

# The contract file and the agent-def directory, relative to ~/.claude.
CONTRACT_REL = "CLAUDE.md"
AGENTS_REL = "agents"

# The repo registry every registered product repo is listed in — the SAME
# file model_pin_parity.py's registered_repo_agent_names() and
# agentarch_metric_check.py's ${REPO:<slug>} resolution already trust as the
# single source for "which repos does this runtime know about" (CLAUDE.md's
# own preamble: "${REPO:<slug>} (resolved against knowledge/repo_registry.json)").
# Computed from the real HOME (mirroring model_pin_parity.py's own
# DEFAULT_REPO_REGISTRY_PATH), not _lib.CLAUDE_DIR — callers that need a
# sandboxed registry pass registry_path explicitly rather than relying on a
# module-level constant to follow a monkeypatched _lib at call time.
DEFAULT_REPO_REGISTRY_PATH = os.path.join(
    os.path.expanduser("~"), ".claude", "knowledge", "repo_registry.json"
)

# The role names the contract calls out in backticks. These are the agents the
# contract explicitly depends on existing; if the contract's prose adds another,
# extend this via _referenced_agents() (which also scrapes the live text).
CONTRACT_REVIEW_AGENTS = ("plan-reviewer", "code-reviewer")

# Agents the contract asserts run on Opus (§10 review cadence). Frontmatter model
# for these MUST be "opus" or the roster has drifted from the contract.
# The two §10 review boundaries PLUS the oversight system's sanctioned Opus
# reviewers (#4400, CLAUDE.md §13, 2026-08-23): launch-director (bounded weekly
# ranked judgment), test-architect and trust-architect (review-boundary agents;
# trust-architect substitutes as reviewer-of-record on trust-surface commits),
# agentic-systems-architect (#4436, 2026-08-25: a bounded
# monthly audit of the runtime's own agentic-system design — unit size and
# convergence, consensus/verification economics, grounding quality, platform-
# capability drift), and code-quality-architect (added 2026-08-30, CLAUDE.md
# §10/§13: a bounded monthly audit of code structure/coupling/complexity/debt
# trend, dispatch-only, never a commit-boundary reviewer), and
# admin-portal-architect (added 2026-09-10, operator-directed: admin-console /
# back-office visibility and operability audits — per-page
# WORKS/DEGRADED/DEAD/STUB verdicts, root-cause clusters, operator-visibility
# gaps; dispatch-only, never a commit-boundary reviewer, same cost shape as
# code-quality-architect), and observability-architect (added 2026-09-15,
# operator-directed: logging/observability architecture audits — structured-
# logger adoption, correlation-id coverage, error classification, severity-
# string validity, alert-to-signal traceability, dead telemetry; dispatch-
# only, never a commit-boundary reviewer, same cost shape as
# code-quality-architect/admin-portal-architect), and devops-architect (added
# 2026-09-16, operator-directed: delivery & infrastructure architecture audits
# — IaC declared-vs-running drift, container/image supply chain, environment
# parity, release/rollback engineering, runtime service config judged for
# safety not cost, plus the five DORA delivery metrics and the pipeline's
# named constraint; dispatch-only, never a commit-boundary reviewer, same cost
# shape as code-quality-architect/admin-portal-architect/observability-
# architect; CI pipeline internals stay git-ops's lane), and the eight GTM
# bench seats — conversion-architect, brand-architect, content-strategist,
# seo-architect, paid-acquisition-strategist, pricing-economist,
# video-producer, and market-analyst (added 2026-09-19, operator-directed,
# upgraded from sonnet after the sonnet specialists missed defects the Opus
# director caught on a real mission: a claimed-nonexistent conversion event
# that actually existed, a 4x budget error, and a missing cross-connect
# guardrail), and four more GTM bench seats — local-presence-architect,
# social-media-strategist, measurement-architect, revenue-ops-architect —
# added 2026-09-28 per the GTM department plan §4.2 (operator-directed
# build-out of the missing marketing seats; findings-only, opus like the
# rest of the bench), and the venture department's two opus seats —
# venture-director (a department orchestrator like marketing-director) and
# capital-and-exit-strategist — added 2026-09-28 per the venture plan §4.1
# (operator: "i need other agents to help me build a team for otherapp ...
# i need help with exits and deals")
# here REQUIRES the matching CLAUDE.md roster entry — the two must move together.
OPUS_AGENTS = (
    "plan-reviewer",
    "code-reviewer",
    "launch-director",
    "test-architect",
    "trust-architect",
    "agentic-systems-architect",
    "code-quality-architect",
    "marketing-director",
    "admin-portal-architect",
    "observability-architect",
    "devops-architect",
    "conversion-architect",
    "brand-architect",
    "content-strategist",
    "seo-architect",
    "paid-acquisition-strategist",
    "pricing-economist",
    "video-producer",
    "market-analyst",
    "local-presence-architect",
    "social-media-strategist",
    "measurement-architect",
    "revenue-ops-architect",
    "venture-director",
    "capital-and-exit-strategist",
)

# The seat(s) permanently pinned "fable" (2x Opus 5 pricing). RETIRED by
# OPERATOR DIRECTIVE, 2026-09-24 ("change all models pinned to fable to be
# pinned to opus (5.5)"): the standing fable pins this tuple once carried —
# `marketing-director` (operator directive, 2026-09-19, "all planners on
# fable") and `plan-reviewer` (operator ruling 2026-09-20, ExampleApp
# OPERATOR_DECISIONS.md card [87]) — are both retired. Both seats are now
# pinned "opus" in `agent_pins` and in their own frontmatter, and remain in
# OPUS_AGENTS above unchanged. Card [87] (which restored plan-reviewer's
# standing pin against THE ISSUE WHEEL's unattended dispatch) stays on
# record, but is no longer load-bearing at the opus tier: opus-on-the-wheel
# was itself B1's own 2026-09-19 remedy, and `launch-director` already runs
# its weekly report on opus, unattended, with no override at all --
# `model_policy.json`'s `session_rules.no_unattended_opus_loops` never
# barred a sanctioned Opus agent from running unattended; the override
# card [87] granted was needed only for the fable tier plan-reviewer
# briefly carried, which sits above what that rule already permits.
#
# This tuple stays EMPTY, not deleted: it is the mechanism, not a roster of
# names. Nothing here forecloses a future standing fable pin — a new one
# still requires its own operator ruling on a specific named seat (never by
# analogy to a past grant) plus a matching CLAUDE.md citation and
# `agent_pins` entry, exactly as before. Absent such a ruling, fable is
# reachable ONLY via the single-use operator-grant path
# (`scripts/grant_model_exception.sh`, run by the operator directly — see
# `model_pin_gate.py`'s own docstring). Every member added here in the
# future must ALSO be in OPUS_AGENTS above (fable is opus-tier-and-above,
# never a replacement classification) — this remains a NARROWING subset,
# not a parallel roster, and both tuples must move together on any future
# change to a member seat's tier (mirrors OPUS_AGENTS' own "must move
# together" rule with CLAUDE.md).
FABLE_AGENTS: tuple[str, ...] = ()

# The canonical anchor every agent def carries tying it to the contract.
CONTRACT_ANCHOR = "~/.claude/CLAUDE.md"

# A backticked token that looks like an agent role name: lowercase words joined
# by single hyphens (plan-reviewer, code-reviewer, browser-ops, git-ops, ...).
_ROLE_RE = re.compile(r"`([a-z][a-z]+(?:-[a-z]+)+)`")

# CSA_* switch tokens and scripts/*.sh helper paths, wherever they appear.
_CSA_RE = re.compile(r"CSA_[A-Z][A-Z_]*")
# Anchored to RUNTIME helpers only. The bare `scripts/(\w+\.sh)` form had no
# path boundary, so it matched the `scripts/` segment inside ANY longer path
# and stripped the prefix: `repo_tooling/scripts/local_ci.sh` -- a legitimate
# PRODUCT-repo path -- came back as `local_ci.sh`, which the RUNTIME contract
# naturally does not name, so every agent correctly citing product tooling was
# flagged `script-path-drift`. Three agents (ci-monitor, git-ops, test-runner)
# tripped it, keeping the suite red (#5848).
#
# Implemented as a NEGATIVE lookbehind on the preceding path segment, NOT as
# an allowlist of delimiters. An allowlist was tried first and leaked: it
# missed `**scripts/x.sh**`, `./scripts/x.sh`, `CMD=scripts/x.sh` and
# `run,scripts/x.sh` -- i.e. it turned a false POSITIVE into false NEGATIVES,
# which is the strictly worse direction for a drift check. Rejecting a
# foreign prefix needs no guess about which characters may precede a path.
#
# The class also carries `$`, `{`, `}` and `>` so the CONTRACT'S OWN mandated
# citation forms are rejected as foreign: CLAUDE.md's preamble requires a
# product path be written `${REPO:<slug>}/...`, and `<repo>/...` is its
# placeholder idiom -- both would otherwise read as runtime helpers the
# moment an agent follows the rule.
#
# `*` is deliberately NOT in the class. Adding it would reject
# `*repo*/scripts/x.sh` but also break `**scripts/x.sh**`, since `*` is
# markdown emphasis rather than a path separator. That leaves `*repo*/` as a
# latent over-flag -- the safe direction (a loud red test, never a silent
# miss), and not an idiom anything actually uses.
#
# Permits: `scripts/x.sh`, `./scripts/x.sh`, `~/.claude/scripts/x.sh`,
#          `.claude/scripts/x.sh`, and every markdown-decorated form.
# Rejects: `repo_tooling/scripts/x.sh`, `modules/a/scripts/x.sh`,
#          `foo.claude/scripts/x.sh`, `${REPO}/scripts/x.sh`,
#          `<repo>/scripts/x.sh`, `$REPO/scripts/x.sh`.
_SCRIPT_RE = re.compile(
    r"(?<![A-Za-z0-9_.~/${}>-])(?:[.~]?/)?(?:\.claude/)?scripts/([a-z0-9_]+\.sh)"
)
# Pool-slot BROWSER tools (the numbered/labeled `playwright-NN`/`-adhoc`/
# `-auth` MCP servers) are DEFERRED — their schemas load only via
# ToolSearch. An agent granted them without ToolSearch can call none of
# them (#4452: every roster browser lane stopped on exactly this,
# silently). Requires a literal hyphen right after "playwright" so the
# BARE, unpooled `mcp__playwright__...` server (see _BARE_UNPOOLED_SERVER_RE
# below) never matches here — that server loads its tools EAGERLY, it is
# not one of the deferred pool-slot servers, so granting it alone must
# never trip this check. Scoped to playwright servers on purpose: that is
# the only deferred family the roster grants today; widen when a second
# one appears.
_DEFERRED_TOOL_RE = re.compile(r"mcp__playwright-[A-Za-z0-9-]+__")
_TOOLSEARCH_RE = re.compile(r"(^|,)\s*ToolSearch\s*(,|$)")
# With no origin-enforcing hook on the numbered pool (2026-07-24 override), an
# agent's browser grant IS its boundary (CLAUDE.md §12). A pooled browser
# agent may not hold: a wildcard on any playwright server (it sweeps in the
# JS-eval tools), `browser_evaluate` / `browser_run_code_unsafe` (arbitrary
# in-page JS; the latter echoes its source, cookies included), or the unleased
# `playwright-adhoc` server (an escape hatch from slot discipline).
_UNSAFE_BROWSER_GRANT_RE = re.compile(
    r"mcp__playwright[A-Za-z0-9-]*__\*"
    r"|mcp__playwright[A-Za-z0-9-]*__browser_(evaluate|run_code_unsafe)\b"
    r"|mcp__playwright-adhoc__"
)
# The BARE, unpooled `mcp__playwright__...` server (the global ~/.claude.json
# `playwright` MCP entry) is a DIFFERENT server from the numbered pool slots
# (`mcp__playwright-01__...` .. `mcp__playwright-12__...`, plus `-auth`/
# `-adhoc`): it carries no isolation/origin flags and is never a leasable
# pool slot — it lives in `~/.claude.json`, which `browser_pool.py` never
# generates or prunes (CLAUDE.md §12), so a grant of it has no lease/reap/cap
# discipline behind it regardless of which individual
# tool within it is granted. The slot forms always have a hyphenated suffix
# between "playwright" and the closing "__" (`playwright-01__`); the bare form
# has nothing there (`playwright__`), which is exactly what this matches — a
# slot grant like `mcp__playwright-07__browser_navigate` never contains the
# literal substring `playwright__`, so this cannot false-positive on one.
_BARE_UNPOOLED_SERVER_RE = re.compile(r"mcp__playwright__")


class Problem:
    """One consistency defect. `kind` is a stable machine code; `detail` is prose."""

    __slots__ = ("kind", "detail")

    def __init__(self, kind: str, detail: str):
        self.kind = kind
        self.detail = detail

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Problem) and self.kind == other.kind and self.detail == other.detail
        )

    def __hash__(self) -> int:
        return hash((self.kind, self.detail))

    def __repr__(self) -> str:  # pragma: no cover - debugging aid only
        return f"Problem({self.kind!r}, {self.detail!r})"

    def format(self) -> str:
        return f"[{self.kind}] {self.detail}"


# ---------------------------------------------------------------------------
# Frontmatter parsing — tolerant of malformed files; never raises.
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict:
    """Extract the leading `---`-delimited YAML frontmatter as a flat dict.

    Only the simple `key: value` lines agent defs actually use are parsed (no
    nested YAML). Returns {} when there is no well-formed frontmatter block.
    Never raises.
    """
    if not text:
        return {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    fields: dict = {}
    for line in lines[1:]:
        if line.strip() == "---":
            return fields
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key and not key.startswith("#"):
            fields[key] = value.strip()
    # No closing `---` -> malformed frontmatter block.
    return {}


def _agent_stem(filename: str) -> str:
    """The role name a file defines: its basename without the .md suffix."""
    base = os.path.basename(filename)
    return base[:-3] if base.endswith(".md") else base


def _referenced_agents(contract_text: str) -> set[str]:
    """Agent role names the contract references, as a set.

    Union of the explicit review-agent list and any backticked hyphenated token
    in the contract prose that names one of the known agent roster roles. We do
    NOT treat every hyphenated backtick as an agent (the contract also backticks
    things like `stash pop`); we intersect the scraped tokens with the actual
    agent files at the call site, and always include the review agents the
    contract's §10 hard-depends on.
    """
    found = set(CONTRACT_REVIEW_AGENTS)
    for m in _ROLE_RE.finditer(contract_text or ""):
        found.add(m.group(1))
    return found


# ---------------------------------------------------------------------------
# The PURE decision function — takes text, returns problems. No IO.
# ---------------------------------------------------------------------------


def check_consistency(contract_text: str, agents: list[tuple[str, str]]) -> list[Problem]:
    """Return the consistency problems between the contract and the agent defs.

    `agents` is a list of (filename, text) pairs. Pure: no file/network/git IO,
    deterministic, order-stable. An empty return means the contract and agents
    are mutually consistent.

    Checks (all read-only — this never proposes a rewrite):
      1. referenced-agent-missing — a role the contract names has no agent file.
      2. malformed-frontmatter    — an agent file has no parseable `name:`.
      3. name-mismatch            — frontmatter name != filename stem.
      4. missing-contract-anchor  — agent does not reference ~/.claude/CLAUDE.md.
      5. model-drift              — a contract-declared Opus agent isn't `opus`
                                     (or, for the FABLE_AGENTS subset, isn't
                                     `fable`).
      6. env-var-drift            — agent names a CSA_* var the contract doesn't.
      7. script-path-drift        — agent names a scripts/*.sh the contract doesn't.
      8. worker-model-drift       — a non-review agent has no model pin, or is
                                     pinned to opus (§10: opus is reserved for the
                                     two review boundaries, never a worker default).
      9. deferred-tools-without-toolsearch — agent is granted deferred MCP
                                     pool-slot tools (mcp__playwright…) but not
                                     ToolSearch, so it can load none of them (#4452).
     10. browser-grant-not-least-privilege — a playwright-granted agent holds a
                                     server wildcard, browser_evaluate /
                                     browser_run_code_unsafe, the unleased
                                     playwright-adhoc server, or the bare
                                     unpooled `mcp__playwright__` server (no
                                     slot suffix — never a leasable pool slot,
                                     it lives in ~/.claude.json, which
                                     browser_pool.py never generates or
                                     prunes) (CLAUDE.md §12: with no origin
                                     hook, the grant is the boundary).
    """
    problems: list[Problem] = []

    contract_text = contract_text or ""
    contract_csa = set(_CSA_RE.findall(contract_text))
    contract_scripts = set(_SCRIPT_RE.findall(contract_text))

    # Build the set of role names that actually have a def file.
    existing_roles = {_agent_stem(fn) for fn, _ in agents}

    # (1) Every agent the contract references by role name must exist. We only
    # flag references that look like real roster roles: the hard-required review
    # agents, plus any scraped token that matches *some* existing agent-name
    # shape but is missing — i.e. a token the contract clearly means as an agent.
    referenced = _referenced_agents(contract_text)
    for role in sorted(referenced):
        must_exist = role in CONTRACT_REVIEW_AGENTS
        if role in existing_roles:
            continue
        if must_exist:
            problems.append(
                Problem(
                    "referenced-agent-missing",
                    f"contract references review agent '{role}' but "
                    f"agents/{role}.md does not exist",
                )
            )

    # Per-agent checks. Sort by filename for stable output.
    for filename, text in sorted(agents, key=lambda p: p[0]):
        stem = _agent_stem(filename)
        text = text or ""
        fm = parse_frontmatter(text)
        name = fm.get("name", "")

        # (2) malformed / missing frontmatter name.
        if not name:
            problems.append(
                Problem(
                    "malformed-frontmatter",
                    f"agent '{filename}' has no parseable frontmatter 'name'",
                )
            )
        # (3) name must equal filename stem.
        elif name != stem:
            problems.append(
                Problem(
                    "name-mismatch",
                    f"agent '{filename}' declares name '{name}' but filename stem is '{stem}'",
                )
            )

        # (4) contract anchor — every agent must tie back to the contract.
        if CONTRACT_ANCHOR not in text:
            problems.append(
                Problem(
                    "missing-contract-anchor",
                    f"agent '{filename}' does not reference the contract ({CONTRACT_ANCHOR})",
                )
            )

        # (5) model drift for the contract-declared Opus agents. FABLE_AGENTS
        # is a NARROWING subset of OPUS_AGENTS (operator directive,
        # 2026-09-19, permanent): each FABLE_AGENTS seat must be pinned literally
        # "fable", not "opus" — every other OPUS_AGENTS member is unchanged.
        if stem in OPUS_AGENTS:
            model = fm.get("model", "")
            required = "fable" if stem in FABLE_AGENTS else "opus"
            if model != required:
                problems.append(
                    Problem(
                        "model-drift",
                        f"contract declares '{stem}' a{'n' if required == 'opus' else ''} "
                        f"{required.capitalize()} agent but its frontmatter model is "
                        f"'{model or '<unset>'}'",
                    )
                )
        else:
            # (8) every non-review agent must declare an explicit, non-opus,
            # non-fable model. Unset silently inherits the dispatching
            # session's model (the exact mechanism a 2026-08-01 credit-burn
            # audit traced two weeks of accidental opus[1m]/xhigh spend
            # through); an explicit "opus" pin on a worker contradicts §10
            # ("opus reserved for the two review boundaries... never the
            # standing default"). "fable" (2x Opus 5 pricing) is
            # opus-tier-and-above, never a way to dodge this check — a worker
            # mutated to `model: fable` must be flagged exactly like a bare
            # `model: opus` worker would be (trust-architect finding H2,
            # 2026-09-19 fix round: this elif was blind to "fable" and let a
            # worker pinned fable produce zero sync problems).
            model = fm.get("model", "")
            if not model:
                problems.append(
                    Problem(
                        "worker-model-drift",
                        f"agent '{filename}' has no model pin — it will silently "
                        f"inherit the dispatching session's model instead of a "
                        f"fixed cheap default",
                    )
                )
            elif model in ("opus", "fable"):
                problems.append(
                    Problem(
                        "worker-model-drift",
                        f"agent '{filename}' is pinned to '{model}' but is not one of "
                        f"the contract's sanctioned Opus reviewers ({', '.join(OPUS_AGENTS)})",
                    )
                )

        # (6) env-var drift — a CSA_* the contract does not define.
        for var in sorted(set(_CSA_RE.findall(text))):
            if var not in contract_csa:
                problems.append(
                    Problem(
                        "env-var-drift",
                        f"agent '{filename}' names env var '{var}' which the "
                        f"contract does not define",
                    )
                )

        # (7) script-path drift — a scripts/*.sh the contract does not name.
        for script in sorted(set(_SCRIPT_RE.findall(text))):
            if script not in contract_scripts:
                problems.append(
                    Problem(
                        "script-path-drift",
                        f"agent '{filename}' references helper 'scripts/{script}' "
                        f"which the contract does not name",
                    )
                )

        # (9) deferred-tool grant without ToolSearch — the tools: line is a
        # permission grant, and a grant the agent cannot load is a false
        # capability claim the roster would otherwise carry silently.
        tools_line = fm.get("tools", "")
        if _DEFERRED_TOOL_RE.search(tools_line) and not _TOOLSEARCH_RE.search(tools_line):
            problems.append(
                Problem(
                    "deferred-tools-without-toolsearch",
                    f"agent '{filename}' is granted deferred MCP pool-slot tools "
                    f"(mcp__playwright…) but not ToolSearch — it can load none of "
                    f"them (#4452)",
                )
            )

        # (10) least-privilege browser grant — the companion of (9): (9) asks
        # "can it load what it was granted"; (10) asks "was it granted only
        # what a pooled browser agent may hold". A bare `mcp__playwright__`
        # grant is flagged here too — it names a different, unpooled MCP
        # server (no isolation/origin flags; never a leasable pool slot, it
        # lives in ~/.claude.json, which browser_pool.py never generates or
        # prunes), independent of which specific tool within it is granted.
        # The gate checks both the (narrowed, hyphen-required) deferred-slot
        # regex AND the bare-unpooled regex directly — (9)'s deferred check is
        # deliberately narrower than this gate (the bare server loads eagerly,
        # so it never trips (9)), but (10) must still inspect a bare-only
        # grant with no numbered slot present at all.
        if _DEFERRED_TOOL_RE.search(tools_line) or _BARE_UNPOOLED_SERVER_RE.search(tools_line):
            bad = sorted({m.group(0) for m in _UNSAFE_BROWSER_GRANT_RE.finditer(tools_line)})
            reasons: list[str] = []
            if bad:
                reasons.append(
                    f"wildcard / JS-eval / adhoc: {', '.join(bad[:4])}"
                    f"{' …' if len(bad) > 4 else ''}"
                )
            if _BARE_UNPOOLED_SERVER_RE.search(tools_line):
                reasons.append(
                    "bare-unpooled-server: mcp__playwright__ is the global, "
                    "unslotted MCP server — never a leasable pool slot; it "
                    "lives in ~/.claude.json, which browser_pool.py never "
                    "generates or prunes — use a numbered "
                    "mcp__playwright-NN__ slot instead"
                )
            if reasons:
                problems.append(
                    Problem(
                        "browser-grant-not-least-privilege",
                        f"agent '{filename}' holds a browser grant the contract forbids "
                        f"for a pooled agent ({'; '.join(reasons)})",
                    )
                )

    return problems


# ---------------------------------------------------------------------------
# IO layer — read the contract + agent files. Best-effort; never raises.
# ---------------------------------------------------------------------------


def _read_text(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return ""


def load_docs(claude_dir: str) -> tuple[str, list[tuple[str, str]]]:
    """Read the contract text and every agents/*.md under `claude_dir`.

    Returns (contract_text, [(basename, text), ...]). Missing contract -> "".
    Missing / unreadable agents dir -> []. Never raises.
    """
    contract_text = _read_text(os.path.join(claude_dir, CONTRACT_REL))
    agents: list[tuple[str, str]] = []
    agents_dir = os.path.join(claude_dir, AGENTS_REL)
    try:
        entries = sorted(os.listdir(agents_dir))
    except Exception:
        entries = []
    for entry in entries:
        if not entry.endswith(".md"):
            continue
        full = os.path.join(agents_dir, entry)
        if not os.path.isfile(full):
            continue
        agents.append((entry, _read_text(full)))
    return contract_text, agents


# ---------------------------------------------------------------------------
# Worktree-twin detection (AUDIT FINDING 3, 2026-09-03 agentic-systems-
# architect audit; #4744).
#
# A worktree — sub-agent OR interactive session, per CLAUDE.md §2's
# sanctioned harness-native isolation — is created at
# <repo>/.claude/worktrees/<name>/, a FULL nested checkout of the repo
# including its own .claude/agents/ directory. Claude Code resolves
# sub-agents by name with last-write-wins REPLACEMENT: a
# .claude/worktrees/<name>/.claude/agents/<agent>.md whose stem collides
# with a name in the RUNTIME roster (~/.claude/agents/*.md) silently
# REPLACES the runtime definition for any session running inside that
# worktree — and the replacement never loads the operating contract (it is
# not anchored to CLAUDE.md the way a real runtime agent def is required to
# be). The nightly finishing loop runs every weeknight *inside* exactly this
# kind of worktree (CLAUDE.md's "loop" job, isolation: "worktree"), so this
# is not a dormant risk — it fires whenever a stale worktree checkout still
# carries an agents/ dir from before a runtime-name migration/cleanup.
#
# No existing checker scans worktrees (a TRACKED, KNOWN gap — #4744,
# 430 shadow files measured on 2026-09-03, up from 287 a week earlier).
# This is DETECTION ONLY: it reports; it never deletes a worktree file
# (worktree removal is operator-scoped per CLAUDE.md §2's ExitWorktree
# rules — discard_changes is forbidden outright, and a dirty worktree's
# twin must not be silently reaped by a validator).
# ---------------------------------------------------------------------------


def _load_repo_registry(registry_path: str) -> dict[str, str]:
    """repo slug -> expanded, absolute root path, from repo_registry.json.

    The SAME registry model_pin_parity.py's registered_repo_agent_names()
    already trusts. Never raises; a missing/unparseable registry, or a repo
    entry with no real `root` string, degrades to skipping that entry
    rather than crashing the whole read.
    """
    out: dict[str, str] = {}
    try:
        with open(registry_path, encoding="utf-8") as fh:
            data = json.load(fh)
        repos = data.get("repos")
        if not isinstance(repos, dict):
            return {}
        for slug, entry in repos.items():
            if not isinstance(entry, dict):
                continue
            root = entry.get("root")
            if isinstance(root, str) and root:
                out[slug] = os.path.expanduser(root)
    except Exception:
        return {}
    return out


def _list_worktree_agent_files(repo_root: str) -> list[tuple[str, str, str]]:
    """Every `.md` file under `<repo_root>/.claude/worktrees/*/.claude/agents/`.

    Returns a list of (worktree_name, agent_stem, absolute_path) tuples.
    A missing worktrees dir, an unreadable entry, or any IO error degrades
    to skipping that entry — never raises, mirroring load_docs().
    """
    found: list[tuple[str, str, str]] = []
    worktrees_dir = os.path.join(repo_root, ".claude", "worktrees")
    try:
        worktree_names = sorted(os.listdir(worktrees_dir))
    except Exception:
        return []
    for wt_name in worktree_names:
        agents_dir = os.path.join(worktrees_dir, wt_name, ".claude", "agents")
        try:
            entries = sorted(os.listdir(agents_dir))
        except Exception:
            continue
        for entry in entries:
            if not entry.endswith(".md"):
                continue
            full = os.path.join(agents_dir, entry)
            if not os.path.isfile(full):
                continue
            found.append((wt_name, _agent_stem(entry), full))
    return found


def find_worktree_agent_twins(
    runtime_agent_names: set[str],
    registry_path: str = DEFAULT_REPO_REGISTRY_PATH,
) -> list[Problem]:
    """Scan every registered repo's `.claude/worktrees/*/.claude/agents/*.md`
    for a filename stem that COLLIDES with a name in the runtime roster.

    Each collision is its own `worktree-agent-twin` Problem naming the
    worktree path and the runtime agent it shadows — the exact shape AUDIT
    FINDING 3 asked for. A non-colliding worktree agent name (a genuine
    product-domain specialist that has never lived in ~/.claude/agents/) is
    NOT flagged — the defect is specifically the last-write-wins REPLACEMENT
    of a runtime definition, not a worktree carrying its own agents dir at
    all. Pure detection: never deletes, never touches the worktree.

    Never raises: a missing/unparseable registry, an unlisted repo, or a
    repo root that does not exist all degrade to contributing nothing.
    """
    problems: list[Problem] = []
    for slug, root in sorted(_load_repo_registry(registry_path).items()):
        for wt_name, stem, full_path in _list_worktree_agent_files(root):
            if stem in runtime_agent_names:
                problems.append(
                    Problem(
                        "worktree-agent-twin",
                        f"'{full_path}' (repo '{slug}', worktree '{wt_name}') "
                        f"shadows runtime agent '{stem}' (agents/{stem}.md) — "
                        f"last-write-wins name resolution means a session "
                        f"running inside this worktree silently REPLACES the "
                        f"runtime definition with this one, which never loads "
                        f"the operating contract",
                    )
                )
    return problems


def _block_reason(problems: list[Problem]) -> str:
    """Human-readable Stop-block reason enumerating the problems."""
    header = (
        f"sync_agent_rules: {len(problems)} contract/agent consistency "
        f"problem(s) — the operating contract and agents/*.md have drifted:"
    )
    body = "\n".join(f"  - {p.format()}" for p in problems)
    return f"{header}\n{body}"


# ---------------------------------------------------------------------------
# Thin main() — read event, decide, emit/log, exit 0. Deny via JSON only.
# ---------------------------------------------------------------------------


def main() -> int:
    """Read the Stop event, run the validator, emit/log, and ALWAYS exit 0.

    LOG-ONLY unless enforcing(): the block object is emitted only when
    enforcement is on for the firing cwd. disabled() (CSA_DISABLE_HOOKS=1) is the
    master-off — no decision, no log, immediate clean exit. A validator failure
    never blocks via exit code.
    """
    try:
        if _lib.disabled():
            return 0

        ev = _lib.read_event()
        where = _lib.cwd(ev)

        # Determine the runtime dir to validate. The contract + agents live in
        # ~/.claude regardless of where the hook fired, so validate against the
        # sandbox/real CLAUDE_DIR rather than the firing cwd.
        contract_text, agents = load_docs(_lib.CLAUDE_DIR)
        problems = check_consistency(contract_text, agents)

        # AUDIT FINDING 3 (2026-09-03, #4744): also scan every registered
        # repo's .claude/worktrees/*/.claude/agents/*.md for a same-named
        # twin of a runtime agent — a class no existing checker covers.
        # Registry path is derived from the same sandbox/real CLAUDE_DIR the
        # contract+agents load above already uses, so a sandboxed test's
        # monkeypatched _lib.CLAUDE_DIR is honored here too.
        runtime_names = {_agent_stem(fn) for fn, _ in agents}
        registry_path = os.path.join(_lib.CLAUDE_DIR, "knowledge", "repo_registry.json")
        problems = problems + find_worktree_agent_twins(runtime_names, registry_path)

        if not problems:
            _lib.log(HOOK_NAME, "clean", agents=len(agents))
            return 0

        kinds = sorted({p.kind for p in problems})
        enforce = _lib.enforcing(where)
        if enforce:
            _lib.log(
                HOOK_NAME,
                "block",
                problems=len(problems),
                kinds=kinds,
            )
            _lib.emit_stop_block(_block_reason(problems))
        else:
            # LOG-ONLY: record the drift but do not surface a block.
            _lib.log(
                HOOK_NAME,
                "would-block",
                problems=len(problems),
                kinds=kinds,
            )
        return 0
    except Exception:
        # Degrade OPEN: a crashing validator must never wedge the agent.
        try:
            _lib.log(HOOK_NAME, "error")
        except Exception:
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover - entrypoint
    sys.exit(main())
