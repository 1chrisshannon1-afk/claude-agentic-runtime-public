#!/usr/bin/env python3
"""bundle_parity — REPORT-ONLY check: does everything a runtime agent/primer/
skill/command reads or names actually SHIP with the bundle?

Part of `runtime_bundle_repo_agnostic_plan.md` WS5.6 (H9/H10/H12/H13/H14) —
the plan that makes every runtime agent repo-agnostic and shippable via the
`claude-agentic-runtime` mirror. This module is the drift guard the plan's
own §0 assertion 1 and assertion 6 point at: "everything an agent reads
either ships or has a seed" should be a command, not a judgment call re-run
by hand every time someone adds a primer or a template.

Mirrors `hooks/model_pin_parity.py`'s shape on purpose (same report-only
design constraints reviewed and accepted for that module):
  * NEVER blocks anything -- no `emit_stop_block`, no `emit_pretooluse_deny`.
    `check()` never raises; every rule below degrades to a single
    `rule-error` line on its own I/O failure rather than crashing the whole
    report.
  * stdlib only. `CLAUDE_DIR` (env) overrides the runtime root, exactly like
    `scripts/repo_manifest.py`'s own `_claude_dir()`.
  * `--json` prints `{"findings": [...], "summary": {...}}`; the default
    text mode prints one line per finding (`rule<TAB>subject<TAB>detail`)
    then a summary line. Exit 0 when clean, 1 when there is at least one
    REAL finding (including `rule-error` lines, so a caller parsing exit
    code alone still sees "something needs a look"). `deferred` and
    `dangling` lines (see `_INFORMATIONAL_TAGS`) are printed and
    JSON-summarized exactly like every other line, but never counted
    toward the finding total or the exit code -- a known, already-tracked
    gap (`deferred`) or a reference to something that does not exist
    anywhere on disk (`dangling`, so there is nothing to "ship" a finding
    about) would otherwise make this check PERMANENTLY red, and a
    permanently-red check is a dead check: nobody could ever tell a real
    regression apart from it.

WIRING: `schedules/prompts/daily_sweep.txt`'s fixed self-check leg (C),
`commands/sweep.md`'s fixed pre-steps, and
`hooks/runtime_mirror_sync.py --check` (fail-open: an exception inside this
module's own `check()` is caught by the caller and never changes
`--check`'s own exit semantics -- see that module's own call site).
Deliberately NOT wired into `pre_commit_ratchet.py` (that hook is
unwaivable; a checker that reads other repos' filesystems does not belong
there, per the plan's own WS5.6 note).

RULES (bundle set = every `agents/*.md` file minus `trading-strategist.md`,
the one agent explicitly out of scope per the plan's §0):

  (a) primer-shipped     -- every `knowledge/<x>_primer.md` a bundle agent's
                             text names is in `.mirror/config.json`'s
                             `include` AND tracked (`git ls-files`) at HEAD.
  (b) template-present   -- every bundle agent that reads its own dossier
                             (`oversight/<a>.md` in its text, minus the
                             `_has_no_dossier_opt_out` carve-out reused
                             directly from `scripts/repo_manifest.py`) has a
                             non-empty `templates/oversight/<a>.md` with >= 3
                             `## ` headings, no forbidden_patterns hit, and
                             every `__TOKEN__` placeholder it uses listed in
                             `templates/oversight/PLACEHOLDERS.md`.
  (c) doc-present        -- `docs/agents/<a>.md` exists for every bundle
                             agent.
  (d) referenced-paths-shipped -- every `skills/<s>`, `tools/<t>`,
                             `scripts/<x>` path literal named by a bundle
                             agent, primer, skill, or command is in
                             `include` (a parent-dir include entry counts)
                             AND tracked at HEAD. A path covered by
                             `DEFERRED_PATHS` (a known, tracked,
                             not-yet-in-scope gap, e.g. `skills/
                             live-testing` -- #5242) is reported as its own
                             `deferred` line instead, and a path that does
                             not exist ANYWHERE on disk (mirrors rule (g))
                             is reported as `dangling` instead -- neither
                             counts as a `referenced-paths-shipped` finding.
  (e) twin-collision     -- for each repo in `knowledge/repo_registry.json`
                             (vacuous when empty), a `<root>/.claude/
                             agents/<name>.md` or `<root>/.claude/skills/
                             <name>/` sharing a name with a runtime agent or
                             skill is flagged, scanning
                             `<root>/.claude/worktrees/*/.claude/
                             {agents,skills}` too. Collision-only.
  (f) mirror-readme-count -- when the mirror clone exists locally, its
                             README's stated agent count equals the bundle
                             set size + 1 (trading-strategist). Fail-open
                             when there is no clone.
  (g) knowledge-referenced-ships -- every `knowledge/<path>` literal named
                             from a bundle agent, primer, skill, command,
                             hook `.py`, or `schedules/prompts/*.txt` is
                             either in `include` (+ tracked at HEAD) or has
                             a `templates/knowledge/<basename>` seed.
                             `knowledge/repo_registry.json` and
                             `knowledge/wheel_repos.json` (both generated,
                             machine-local) are ignored. A referenced path
                             that does not exist ANYWHERE on disk is a
                             DIFFERENT defect (a dangling reference) and is
                             reported under its own `dangling` line instead.

This module owns exactly two files:
  ~/.claude/hooks/bundle_parity.py            (this file)
  ~/.claude/hooks/tests/test_bundle_parity.py  (written separately)
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _claude_dir() -> str:
    """The runtime root -- `CLAUDE_DIR` env override, else `~/.claude`.
    Mirrors `scripts/repo_manifest.py`'s own `_claude_dir()` verbatim (same
    env var, same default), so a caller that sets `CLAUDE_DIR` for one gets
    consistent behavior from the other."""
    raw = os.environ.get("CLAUDE_DIR")
    if raw:
        return os.path.expanduser(raw)
    return os.path.expanduser("~/.claude")


# Bundle-scoped skill sources for rule (d)/(g): `skills/live-testing/` is
# explicitly OUT OF SCOPE for this whole plan (§0: "OUT of scope ...
# `live-testing/` (§8)") and its own SKILL.md intentionally references
# product-repo-relative scripts (`./scripts/prime_browser_pool.sh`,
# `scripts/playwright_pool.py`) that are not runtime paths at all --
# scanning it here would manufacture false findings for a subsystem this
# plan deliberately does not touch.
_EXCLUDED_SKILL_DIRS = frozenset({"live-testing"})

# The two primers `trading-strategist` alone reads (§0: "OUT of scope ...
# `trading-strategist` and its two primers") -- excluded from every source
# scan the same way `trading-strategist.md` itself is excluded from the
# bundle agent set, so their own references to product-repo-local trading
# scripts (`scripts/ag_brief.py`, etc.) never manufacture a finding for a
# subsystem this plan deliberately does not touch.
_EXCLUDED_PRIMERS = frozenset(
    {"agricultural_futures_primer.md", "trading_strategist_equities_primer.md"}
)

# Rule (d) referenced paths that are DELIBERATELY not yet shippable -- a
# tracked, named follow-up, not an oversight. `browser-ops.md` (a bundle
# agent) references `skills/live-testing/SKILL.md`, but `live-testing/`
# portability is its own separate plan (§5/§8, follow-up #5242) and is
# explicitly not part of this plan's scope. Without this table, that
# reference makes rule (d) PERMANENTLY red until #5242 lands -- a
# permanently-red check is a dead check, since nobody can ever tell a new
# regression apart from this known, already-tracked gap. Keyed by PREFIX
# (checked via `path == key or path.startswith(key + "/")`, mirroring
# `_included`'s own parent-dir semantics) so a whole deferred subsystem's
# directory covers every file under it, not just one exact path.
DEFERRED_PATHS: dict[str, str] = {
    "skills/live-testing": "#5242 live-testing portability",
}


def _deferred_reason(path: str) -> str | None:
    """The `DEFERRED_PATHS` reason covering `path`, or None. Prefix match,
    same semantics as `_included`'s parent-dir rule."""
    for prefix, reason in DEFERRED_PATHS.items():
        if path == prefix or path.startswith(prefix + "/"):
            return reason
    return None


# Rule tags that are INFORMATIONAL, not findings: still present in the
# returned/JSON `findings` array and in text-mode output, and
# JSON-summarized exactly like every other line, but never counted toward
# the finding TOTAL or the exit code. `deferred` (a known, tracked,
# out-of-scope-for-now reference) and `dangling` (a referenced path that
# does not exist anywhere on disk -- a different defect class than "exists
# but unshipped") are the two members: a permanently-red check on either is
# a dead check, since real regressions could never be told apart from
# these known, already-understood shapes.
_INFORMATIONAL_TAGS = frozenset({"deferred", "dangling"})

_PLACEHOLDER_RE = re.compile(r"__[A-Z][A-Z0-9_]*__")
_HEADING_RE = re.compile(r"^##\s+\S", re.MULTILINE)
_NO_DOSSIER_HELPER = None  # lazily imported; see _has_no_dossier_opt_out()


def _has_no_dossier_opt_out(agent_text: str, agent_name: str) -> bool:
    """Reuse `scripts/repo_manifest.py`'s own opt-out predicate rather than
    duplicating it (plan directive, rule (b)). Degrades to "no opt-out"
    (i.e. the dossier IS required) if the import ever fails -- fail toward
    reporting a real finding, never toward silently skipping a check."""
    global _NO_DOSSIER_HELPER
    if _NO_DOSSIER_HELPER is None:
        try:
            import repo_manifest as _rm

            _NO_DOSSIER_HELPER = _rm._has_no_dossier_opt_out
        except Exception:
            _NO_DOSSIER_HELPER = False
    if _NO_DOSSIER_HELPER is False:
        return False
    try:
        return bool(_NO_DOSSIER_HELPER(agent_text, agent_name))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Small, shared, fail-open filesystem/git helpers
# ---------------------------------------------------------------------------


def _read_text(path: str) -> str | None:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return None


def _bundle_agent_names(claude_dir: str) -> list[str]:
    """Every `agents/<name>.md` stem, minus `trading-strategist` -- the
    bundle set every rule below is scoped to. Sorted for stable output."""
    agents_dir = os.path.join(claude_dir, "agents")
    try:
        files = sorted(
            f
            for f in os.listdir(agents_dir)
            if f.endswith(".md") and not f.startswith(".")
        )
    except OSError:
        return []
    return [f[: -len(".md")] for f in files if f[: -len(".md")] != "trading-strategist"]


def _load_mirror_config(claude_dir: str) -> dict | None:
    path = os.path.join(claude_dir, ".mirror", "config.json")
    text = _read_text(path)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _git_ls_files(claude_dir: str, *paths: str) -> set[str]:
    """Every path `git ls-files` reports at HEAD, restricted to `paths`
    (each may be a directory or a file pathspec). Returns an empty set on
    any git/subprocess failure -- callers treat "not found" identically to
    "git could not tell us", which is the fail-open posture every other
    rule here already takes."""
    if not paths:
        return set()
    try:
        proc = subprocess.run(
            ["git", "-C", claude_dir, "ls-files", "--", *paths],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return set()
    if proc.returncode != 0:
        return set()
    return {line for line in proc.stdout.splitlines() if line}


def _included(rel_path: str, include: Iterable[str]) -> bool:
    """True when `rel_path` is covered by `include` -- either an exact
    entry, or a parent-directory entry (`"knowledge"` covers
    a nested example under the knowledge tree). Pure string comparison;
    never touches disk."""
    rel_path = rel_path.strip("/")
    for entry in include:
        if not isinstance(entry, str):
            continue
        entry = entry.strip("/")
        if not entry:
            continue
        if rel_path == entry or rel_path.startswith(entry + "/"):
            return True
    return False


def _tracked(claude_dir: str, rel_path: str) -> bool:
    return bool(_git_ls_files(claude_dir, rel_path))


# For a referenced path that resolves to a DIRECTORY (e.g. `skills/foo`,
# never a specific file), `_tracked()` alone is directory-granular: `git
# ls-files -- skills/foo` returns True the moment ANY file under that
# directory is tracked, even if the directory's own real entrypoint is not.
# A `skills/foo` directory whose `README.md` is tracked but whose
# `SKILL.md` is NOT is exactly the ship-a-broken-skill failure mode this
# rule exists to catch -- and `_tracked('skills/foo')` alone reports it
# fine. Map a directory-shaped reference to its real required entrypoint
# filename here; a prefix with no entry falls back to directory-granular
# tracking (unchanged behavior for anything not enumerated).
_DIR_ENTRYPOINT_BY_PREFIX: tuple[tuple[str, str], ...] = (
    ("skills/", "SKILL.md"),
)


def _tracked_entrypoint(claude_dir: str, rel_path: str) -> bool:
    """Like `_tracked`, but for a directory-shaped reference, also requires
    the directory's own real entrypoint file (per
    `_DIR_ENTRYPOINT_BY_PREFIX`) to itself be tracked -- not merely that
    the directory has SOME tracked descendant."""
    if not _tracked(claude_dir, rel_path):
        return False
    if os.path.isdir(os.path.join(claude_dir, rel_path)):
        for prefix, entrypoint in _DIR_ENTRYPOINT_BY_PREFIX:
            if rel_path == prefix.rstrip("/") or rel_path.startswith(prefix):
                entry_rel = rel_path.rstrip("/") + "/" + entrypoint
                if not _tracked(claude_dir, entry_rel):
                    return False
                break
    return True


# ---------------------------------------------------------------------------
# Reference extraction -- shared by (a), (d), (g)
# ---------------------------------------------------------------------------

_BACKTICK_SPAN_RE = re.compile(r"`([^`\n]+)`")
# Triple-backtick fenced blocks (```...```), non-greedy, DOTALL so the body
# can span multiple lines -- a path cited inside a fenced code/example block
# is otherwise invisible to `_extract_runtime_tool_paths` (only inline
# single-backtick spans were scanned), a real false-negative: a fenced
# reference to a nonexistent path went undetected as `dangling`.
_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_PRIMER_REF_RE = re.compile(r"knowledge/([A-Za-z0-9_]+_primer\.md)")
# `skills/<x>`, `tools/<x>`, `scripts/<x>` -- one or more further path
# segments required after the prefix, so a bare directory mention like
# "`.claude/skills/`" (no basename) never matches.
_RUNTIME_TOOL_PATH_RE = re.compile(r"\b(skills|tools|scripts)/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*")
_KNOWLEDGE_PATH_RE = re.compile(r"knowledge/[A-Za-z0-9_./-]+")
_TRAILING_PUNCT_RE = re.compile(r"[).,:;'\"]+$")


def _bundle_source_files(claude_dir: str) -> dict[str, str]:
    """rel_path -> text, for every source file rule (a)/(d)/(g) scan:
    bundle agents, primers, skills (minus the excluded ones), commands.
    Read failures drop that one file rather than aborting the scan."""
    out: dict[str, str] = {}

    for name in _bundle_agent_names(claude_dir):
        rel = f"agents/{name}.md"
        text = _read_text(os.path.join(claude_dir, rel))
        if text is not None:
            out[rel] = text

    knowledge_dir = os.path.join(claude_dir, "knowledge")
    try:
        primer_files = sorted(
            f
            for f in os.listdir(knowledge_dir)
            if f.endswith("_primer.md") and f not in _EXCLUDED_PRIMERS
        )
    except OSError:
        primer_files = []
    for fname in primer_files:
        rel = f"knowledge/{fname}"
        text = _read_text(os.path.join(knowledge_dir, fname))
        if text is not None:
            out[rel] = text

    skills_dir = os.path.join(claude_dir, "skills")
    try:
        skill_names = sorted(os.listdir(skills_dir))
    except OSError:
        skill_names = []
    for name in skill_names:
        if name in _EXCLUDED_SKILL_DIRS or name.startswith("."):
            continue
        rel = f"skills/{name}/SKILL.md"
        text = _read_text(os.path.join(claude_dir, rel))
        if text is not None:
            out[rel] = text

    commands_dir = os.path.join(claude_dir, "commands")
    try:
        command_files = sorted(f for f in os.listdir(commands_dir) if f.endswith(".md"))
    except OSError:
        command_files = []
    for fname in command_files:
        rel = f"commands/{fname}"
        text = _read_text(os.path.join(commands_dir, fname))
        if text is not None:
            out[rel] = text

    return out


def _knowledge_source_files(claude_dir: str) -> dict[str, str]:
    """rule (g) additionally scans hook `.py` files and
    `schedules/prompts/*.txt`, on top of every `_bundle_source_files` file
    (agents/primers/skills/commands) -- the plan's own rule text."""
    out = dict(_bundle_source_files(claude_dir))

    hooks_dir = os.path.join(claude_dir, "hooks")
    try:
        hook_files = sorted(f for f in os.listdir(hooks_dir) if f.endswith(".py"))
    except OSError:
        hook_files = []
    for fname in hook_files:
        rel = f"hooks/{fname}"
        text = _read_text(os.path.join(hooks_dir, fname))
        if text is not None:
            out[rel] = text

    prompts_dir = os.path.join(claude_dir, "schedules", "prompts")
    try:
        prompt_files = sorted(f for f in os.listdir(prompts_dir) if f.endswith(".txt"))
    except OSError:
        prompt_files = []
    for fname in prompt_files:
        rel = f"schedules/prompts/{fname}"
        text = _read_text(os.path.join(prompts_dir, fname))
        if text is not None:
            out[rel] = text

    return out


# ---------------------------------------------------------------------------
# (a) primer-shipped
# ---------------------------------------------------------------------------


def check_primer_shipped(claude_dir: str, include: list[str]) -> list[str]:
    out: list[str] = []
    try:
        sources = _bundle_source_files(claude_dir)
        primers: set[str] = set()
        for rel, text in sources.items():
            if not rel.startswith("agents/"):
                continue
            for m in _PRIMER_REF_RE.finditer(text):
                primers.add(f"knowledge/{m.group(1)}")
        for primer_rel in sorted(primers):
            if not _included(primer_rel, include):
                out.append(
                    f"primer-shipped\t{primer_rel}\tnot in .mirror/config.json include"
                )
            elif not _tracked(claude_dir, primer_rel):
                out.append(f"primer-shipped\t{primer_rel}\tnot tracked (git ls-files) at HEAD")
    except Exception as exc:
        out.append(f"rule-error\tprimer-shipped\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (b) template-present
# ---------------------------------------------------------------------------


def _load_placeholder_tokens(claude_dir: str) -> set[str]:
    path = os.path.join(claude_dir, "templates", "oversight", "PLACEHOLDERS.md")
    text = _read_text(path)
    if text is None:
        return set()
    return set(_PLACEHOLDER_RE.findall(text))


def _forbidden_regexes(claude_dir: str) -> list[re.Pattern]:
    cfg = _load_mirror_config(claude_dir)
    if not cfg:
        return []
    patterns = cfg.get("forbidden_patterns")
    if not isinstance(patterns, list):
        return []
    out: list[re.Pattern] = []
    for p in patterns:
        if not isinstance(p, str):
            continue
        try:
            out.append(re.compile(p, re.IGNORECASE))
        except re.error:
            continue
    return out


def check_template_present(claude_dir: str) -> list[str]:
    out: list[str] = []
    try:
        forbidden = _forbidden_regexes(claude_dir)
        placeholder_table = _load_placeholder_tokens(claude_dir)
        for name in _bundle_agent_names(claude_dir):
            agent_text = _read_text(os.path.join(claude_dir, "agents", f"{name}.md"))
            if agent_text is None:
                continue
            if f"oversight/{name}.md" not in agent_text:
                continue
            if _has_no_dossier_opt_out(agent_text, name):
                continue
            tpl_path = os.path.join(claude_dir, "templates", "oversight", f"{name}.md")
            tpl_rel = f"templates/oversight/{name}.md"
            tpl_text = _read_text(tpl_path)
            if tpl_text is None:
                out.append(f"template-present\t{name}\tmissing: {tpl_rel}")
                continue
            if not tpl_text.strip():
                out.append(f"template-present\t{name}\tempty: {tpl_rel}")
                continue
            heading_count = len(_HEADING_RE.findall(tpl_text))
            if heading_count < 3:
                out.append(
                    f"template-present\t{name}\tonly {heading_count} '## ' heading(s) "
                    f"(need >= 3): {tpl_rel}"
                )
            for pat in forbidden:
                m = pat.search(tpl_text)
                if m:
                    out.append(
                        f"template-present\t{name}\tforbidden_patterns hit "
                        f"'{pat.pattern}' in {tpl_rel}"
                    )
            used_tokens = set(_PLACEHOLDER_RE.findall(tpl_text))
            missing_tokens = sorted(used_tokens - placeholder_table)
            for tok in missing_tokens:
                out.append(
                    f"template-present\t{name}\tplaceholder {tok} not listed in "
                    "templates/oversight/PLACEHOLDERS.md"
                )
    except Exception as exc:
        out.append(f"rule-error\ttemplate-present\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (c) doc-present
# ---------------------------------------------------------------------------


def check_doc_present(claude_dir: str) -> list[str]:
    out: list[str] = []
    try:
        for name in _bundle_agent_names(claude_dir):
            doc_path = os.path.join(claude_dir, "docs", "agents", f"{name}.md")
            if not os.path.isfile(doc_path):
                out.append(f"doc-present\t{name}\tmissing: docs/agents/{name}.md")
    except Exception as exc:
        out.append(f"rule-error\tdoc-present\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (d) referenced-paths-shipped
# ---------------------------------------------------------------------------


def _extract_runtime_tool_paths(text: str) -> set[str]:
    """Backtick-quoted `skills/<x>` / `tools/<x>` / `scripts/<x>` path
    literals, excluding any span that also names a product-repo root
    (`<repo>/.claude/...` or `repo_tooling/...`) -- those are a DIFFERENT
    repo's paths, not this runtime's, and must never be checked against
    this runtime's own `include`/`git ls-files`. A span may carry a
    `~/.claude/` or bare `.claude/` prefix, which is stripped before
    returning, so `~/.claude/tools/gtm/exit_contract.py` and
    `tools/gtm/exit_contract.py` normalize to the same key.

    Scans BOTH inline single-backtick spans and the body of triple-backtick
    fenced blocks -- a path cited only inside a fenced example (not an
    inline span) was previously invisible to this extraction, a real
    false-negative for rule (d)'s dangling-reference check."""
    out: set[str] = set()
    spans: list[str] = list(_BACKTICK_SPAN_RE.findall(text))
    spans.extend(_FENCE_RE.findall(text))
    for span in spans:
        if "<repo>" in span or "repo_tooling" in span:
            continue
        for m in _RUNTIME_TOOL_PATH_RE.finditer(span):
            out.add(m.group(0))
    return out


def check_referenced_paths_shipped(claude_dir: str, include: list[str]) -> list[str]:
    out: list[str] = []
    try:
        sources = _bundle_source_files(claude_dir)
        referenced: dict[str, set[str]] = {}
        for rel, text in sources.items():
            for path in _extract_runtime_tool_paths(text):
                referenced.setdefault(path, set()).add(rel)
        for path in sorted(referenced):
            citers = ", ".join(sorted(referenced[path]))
            deferred_reason = _deferred_reason(path)
            if deferred_reason is not None:
                out.append(f"deferred\t{path}\t{deferred_reason} (referenced by: {citers})")
                continue
            if not os.path.exists(os.path.join(claude_dir, path)):
                out.append(
                    f"dangling\t{path}\treferenced but does not exist on disk "
                    f"(referenced by: {citers})"
                )
                continue
            if not _included(path, include):
                out.append(
                    f"referenced-paths-shipped\t{path}\tnot in .mirror/config.json "
                    f"include (referenced by: {citers})"
                )
            elif not _tracked_entrypoint(claude_dir, path):
                out.append(
                    f"referenced-paths-shipped\t{path}\tnot tracked (git ls-files) at "
                    f"HEAD (referenced by: {citers})"
                )
    except Exception as exc:
        out.append(f"rule-error\treferenced-paths-shipped\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (e) twin-collision
# ---------------------------------------------------------------------------


def _load_repo_registry_roots(claude_dir: str) -> dict[str, str]:
    path = os.path.join(claude_dir, "knowledge", "repo_registry.json")
    text = _read_text(path)
    if text is None:
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    repos = data.get("repos") if isinstance(data, dict) else None
    if not isinstance(repos, dict):
        return {}
    out: dict[str, str] = {}
    for slug, entry in repos.items():
        if not isinstance(entry, dict):
            continue
        root = entry.get("root")
        if isinstance(root, str) and root:
            out[slug] = os.path.expanduser(root)
    return out


def _runtime_skill_names(claude_dir: str) -> set[str]:
    skills_dir = os.path.join(claude_dir, "skills")
    try:
        return {
            d
            for d in os.listdir(skills_dir)
            if os.path.isdir(os.path.join(skills_dir, d)) and not d.startswith(".")
        }
    except OSError:
        return set()


def _collision_hits(
    agents_root: str, skills_root: str, runtime_agents: set[str], runtime_skills: set[str]
) -> list[tuple[str, str]]:
    """(kind, name) pairs found under one `.claude/agents`+`.claude/skills`
    pair that collide with a runtime name. `kind` is `"agents"` or
    `"skills"`."""
    hits: list[tuple[str, str]] = []
    try:
        for f in os.listdir(agents_root):
            if f.endswith(".md") and not f.startswith("."):
                name = f[: -len(".md")]
                if name in runtime_agents:
                    hits.append(("agents", name))
    except OSError:
        pass
    try:
        for d in os.listdir(skills_root):
            if os.path.isdir(os.path.join(skills_root, d)) and not d.startswith("."):
                if d in runtime_skills:
                    hits.append(("skills", d))
    except OSError:
        pass
    return hits


def check_twin_collision(claude_dir: str) -> list[str]:
    out: list[str] = []
    try:
        runtime_agents = set(_bundle_agent_names(claude_dir))
        # trading-strategist itself is still a real runtime agent file (just
        # excluded from the bundle set) -- a project twin of IT would shadow
        # a real runtime agent too, so it belongs in the collision name set
        # even though it's excluded from every other rule above.
        runtime_agents.add("trading-strategist")
        runtime_skills = _runtime_skill_names(claude_dir)

        roots = _load_repo_registry_roots(claude_dir)
        if not roots:
            out.append("twin-check\t(none)\tno repos registered")
            return out

        for slug, root in sorted(roots.items()):
            candidates = [(root, os.path.join(root, ".claude"))]
            worktrees_dir = os.path.join(root, ".claude", "worktrees")
            try:
                for wt in sorted(os.listdir(worktrees_dir)):
                    wt_claude = os.path.join(worktrees_dir, wt, ".claude")
                    if os.path.isdir(wt_claude):
                        candidates.append((f"{root} (worktree {wt})", wt_claude))
            except OSError:
                pass

            for label, claude_subdir in candidates:
                agents_root = os.path.join(claude_subdir, "agents")
                skills_root = os.path.join(claude_subdir, "skills")
                for kind, name in _collision_hits(
                    agents_root, skills_root, runtime_agents, runtime_skills
                ):
                    if kind == "agents":
                        out.append(
                            f"twin-collision\t{slug}:{name}\tproject agent REPLACES "
                            f"runtime agent (project > user precedence) — "
                            f"{label} .claude/agents/{name}.md"
                        )
                    else:
                        out.append(
                            f"twin-collision\t{slug}:{name}\trepo-local skill is DEAD "
                            f"(user-level skill wins, Personal > Project) — "
                            f"{label} .claude/skills/{name}/"
                        )
    except Exception as exc:
        out.append(f"rule-error\ttwin-collision\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (f) mirror-readme-count
# ---------------------------------------------------------------------------

# Anchored to a genuine agent-DEFINITION-count claim, never any incidental
# "N agent-hours"/"N agent-driven..." mention -- an earlier unanchored
# `(\d+)\s+agent` regex collected every such phrase into a set and passed
# the moment ANY of them happened to equal the expected count, a real
# false-negative the moment the README gained a second "N agent..." phrase
# unrelated to the definition count (e.g. an effort estimate). "agent" or
# "agents" immediately followed by a hyphenated qualifier (agent-hours,
# agent-driven, agent-based, ...) is excluded; a bare "N agent(s)" mention
# (optionally followed by "definition(s)") still counts, matching both the
# real README's "20 agent definitions" phrasing and this module's own test
# fixture's "3 agents." phrasing.
_AGENT_COUNT_RE = re.compile(
    r"(\d+)\s+agents?\b(?!-)",
    re.IGNORECASE,
)


def check_mirror_readme_count(claude_dir: str) -> list[str]:
    out: list[str] = []
    try:
        cfg = _load_mirror_config(claude_dir)
        if not cfg:
            return out
        clone_dir = cfg.get("clone_dir")
        if not isinstance(clone_dir, str) or not clone_dir:
            return out
        clone_path = os.path.expanduser(clone_dir)
        readme_path = os.path.join(clone_path, "README.md")
        if not os.path.isdir(clone_path):
            return out  # fail-open: no clone locally, nothing to compare
        text = _read_text(readme_path)
        if text is None:
            return out
        expected = len(_bundle_agent_names(claude_dir)) + 1  # + trading-strategist
        matches = {int(m) for m in _AGENT_COUNT_RE.findall(text)}
        if expected not in matches:
            found = ", ".join(str(n) for n in sorted(matches)) or "(none)"
            out.append(
                f"mirror-readme-count\t{readme_path}\texpected {expected}, "
                f"found agent-count mention(s): {found}"
            )
    except Exception as exc:
        out.append(f"rule-error\tmirror-readme-count\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# (g) knowledge-referenced-ships
# ---------------------------------------------------------------------------

_IGNORED_KNOWLEDGE_BASENAMES = frozenset({"repo_registry.json", "wheel_repos.json"})


def _extract_knowledge_paths(text: str) -> set[str]:
    out: set[str] = set()
    for m in _KNOWLEDGE_PATH_RE.finditer(text):
        path = _TRAILING_PUNCT_RE.sub("", m.group(0))
        if path.endswith("/"):
            path = path.rstrip("/")
        if path == "knowledge" or "/" not in path:
            continue
        out.add(path)
    return out


def check_knowledge_referenced_ships(claude_dir: str, include: list[str]) -> list[str]:
    out: list[str] = []
    try:
        sources = _knowledge_source_files(claude_dir)
        referenced: dict[str, set[str]] = {}
        for rel, text in sources.items():
            for path in _extract_knowledge_paths(text):
                referenced.setdefault(path, set()).add(rel)

        for path in sorted(referenced):
            basename = os.path.basename(path)
            if basename in _IGNORED_KNOWLEDGE_BASENAMES:
                continue
            citers = ", ".join(sorted(referenced[path]))
            abs_path = os.path.join(claude_dir, path)
            exists_on_disk = os.path.exists(abs_path)
            if not exists_on_disk:
                out.append(
                    f"dangling\t{path}\treferenced but does not exist on disk "
                    f"(referenced by: {citers})"
                )
                continue
            if _included(path, include) and _tracked(claude_dir, path):
                continue
            seed_path = os.path.join(claude_dir, "templates", "knowledge", basename)
            if os.path.isfile(seed_path):
                continue
            out.append(
                f"knowledge-referenced-ships\t{path}\tneither shipped (include + "
                f"tracked) nor seeded (templates/knowledge/{basename}) "
                f"(referenced by: {citers})"
            )
    except Exception as exc:
        out.append(f"rule-error\tknowledge-referenced-ships\t{exc.__class__.__name__}: {exc}")
    return out


# ---------------------------------------------------------------------------
# check() / main()
# ---------------------------------------------------------------------------


def check(claude_dir: str | None = None) -> list[str]:
    """Run every rule and return the concatenated finding lines. Never
    raises -- each rule's own try/except already turns a crash into a
    `rule-error` line; this function adds no further exception handling
    because none of the calls below can themselves raise given that
    contract, but the whole thing is still wrapped defensively so a future
    rule that forgets its own try/except degrades to one `rule-error`
    line instead of taking the whole report down."""
    resolved = claude_dir or _claude_dir()
    out: list[str] = []
    cfg = _load_mirror_config(resolved)
    include = cfg.get("include", []) if isinstance(cfg, dict) else []
    if not isinstance(include, list):
        include = []

    try:
        out.extend(check_primer_shipped(resolved, include))
    except Exception as exc:
        out.append(f"rule-error\tprimer-shipped\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_template_present(resolved))
    except Exception as exc:
        out.append(f"rule-error\ttemplate-present\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_doc_present(resolved))
    except Exception as exc:
        out.append(f"rule-error\tdoc-present\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_referenced_paths_shipped(resolved, include))
    except Exception as exc:
        out.append(f"rule-error\treferenced-paths-shipped\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_twin_collision(resolved))
    except Exception as exc:
        out.append(f"rule-error\ttwin-collision\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_mirror_readme_count(resolved))
    except Exception as exc:
        out.append(f"rule-error\tmirror-readme-count\t{exc.__class__.__name__}: {exc}")
    try:
        out.extend(check_knowledge_referenced_ships(resolved, include))
    except Exception as exc:
        out.append(f"rule-error\tknowledge-referenced-ships\t{exc.__class__.__name__}: {exc}")

    return out


def _line_tag(line: str) -> str:
    return line.split("\t", 1)[0] if line else "(unparseable)"


def _summarize(findings: list[str]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for line in findings:
        rule = _line_tag(line)
        summary[rule] = summary.get(rule, 0) + 1
    return summary


def _is_informational(line: str) -> bool:
    """True for a `deferred`/`dangling` line (see `_INFORMATIONAL_TAGS`):
    reported and JSON-summarized like every other line, but excluded from
    the finding COUNT and the exit code -- a known, already-tracked gap
    (deferred) or a different defect class entirely (dangling: the
    reference itself doesn't exist, so there is nothing to ship) must never
    make this check permanently red, or a real regression could never be
    told apart from it."""
    return _line_tag(line) in _INFORMATIONAL_TAGS


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    as_json = "--json" in argv
    findings = check()
    summary = _summarize(findings)
    # `deferred`/`dangling` lines stay IN `findings` (JSON and text mode
    # both) so a caller scanning them can see why a path was skipped --
    # only the finding COUNT and the exit-code decision exclude them.
    real_findings = [f for f in findings if not _is_informational(f)]
    if as_json:
        print(json.dumps({"findings": findings, "summary": summary}, indent=2))
    else:
        for line in findings:
            print(line)
        if summary:
            for rule in sorted(summary):
                print(f"  {rule}: {summary[rule]}")
        print(f"bundle_parity: {len(real_findings)} finding(s)")
    return 1 if real_findings else 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
