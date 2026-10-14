#!/usr/bin/env python3
"""gen_agent_index - generate docs/agents/README.md, the agent roster.

The roster is derived, never hand-written, from three files that ship in the
checkout:

  * ``agents/*.md`` frontmatter: ``name``, ``model``, ``tools`` and
    ``description``. The description and tool list are copied VERBATIM (never
    truncated or re-wrapped), so a regeneration over a redacted copy of the
    tree matches a redacted copy of the generated page byte for byte.
  * ``knowledge/model_policy.json`` ``agent_pins``: the model each agent must
    run on. Read-only: this file is the live model-pin gate's input and is
    never written by this script.
  * ``knowledge/agent_meta.json``: ``{name: {department, trigger,
    dispatched_by}}``. A separate file on purpose, so a malformed edit here can
    never disturb the pin gate. ``dispatched_by`` is a comma-separated list of
    dispatchers: an agent name, or one of ``orchestrator`` (the session you
    talk to), ``scheduled-job`` or ``operator``.

The script is also the parity check for ``agent_meta.json``. It exits 1 (and
writes nothing) when:

  * an agent in ``agents/`` has no ``agent_meta`` entry or no pin;
  * ``agent_meta`` names an agent that is absent from ``agents/`` or from
    ``agent_pins``;
  * an agent's frontmatter ``model`` disagrees with its pin;
  * an ``agent_meta`` entry is malformed (missing or unknown key, empty value,
    unknown dispatcher), or a frontmatter block cannot be parsed.

Modes:

  (default)   validate, then write docs/agents/README.md
  --check     validate, then exit 1 if docs/agents/README.md is stale or absent
  --summary   validate, then print the model split (counts per model and per
              department, and why the strong model is reserved for judgment
              seats); writes nothing

Exit codes: 0 ok, 1 a problem or a stale page, 2 usage error.

Usage:
    python3 scripts/gen_agent_index.py [--repo PATH] [--check | --summary]

Python 3.9+, standard library only.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import stat
import sys
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from itertools import chain
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

PROG = "gen_agent_index"
OUTPUT_REL = Path("docs") / "agents" / "README.md"
AGENTS_REL = Path("agents")
POLICY_REL = Path("knowledge") / "model_policy.json"
META_REL = Path("knowledge") / "agent_meta.json"

META_KEYS = ("department", "trigger", "dispatched_by")

# Dispatchers that are not agents: id -> (diagram label, plain-text label).
DISPATCHERS: Dict[str, Tuple[str, str]] = OrderedDict(
    [
        ("orchestrator", ("Orchestrating session", "orchestrating session")),
        ("scheduled-job", ("Scheduled job", "scheduled job")),
        ("operator", ("Operator (by name or slash command)", "operator")),
    ]
)

# Known departments, in display order: id -> (title, one-line description).
# A department id that is not listed here is still rendered (after these, in
# alphabetical order, with a title derived from the id), so adding an agent in
# a new department never needs a change to this script.
DEPARTMENTS: Dict[str, Tuple[str, str]] = OrderedDict(
    [
        (
            "dev",
            (
                "Development workflow",
                "Builders, test and CI agents, and the two commit-boundary reviewers. "
                "The orchestrating session dispatches these as the work needs them.",
            ),
        ),
        (
            "oversight",
            (
                "Oversight roster",
                "Watchers and auditors that judge the whole body of work rather than one "
                "change. Some run on a schedule and the rest are dispatched by name; they "
                "mostly return findings for the orchestrating session to act on.",
            ),
        ),
        (
            "marketing",
            (
                "Marketing (go-to-market) department",
                "One director agent runs a mission through a fixed lifecycle and dispatches "
                "a bench of specialist seats. The specialists return findings, specs or "
                "drafts; none of them edits product files.",
            ),
        ),
        (
            "venture",
            (
                "Venture department",
                "A director agent runs one company's money missions (recruiting, exit or "
                "raise, outbound) and dispatches its bench. These seats research and draft; "
                "they never send, sign or spend.",
            ),
        ),
        (
            "domain",
            (
                "Domain specialists",
                "Specialists for one product domain. Each is grounded in a repo's own "
                "dossier and primers rather than in runtime-wide doctrine.",
            ),
        ),
    ]
)

# Model tiers in display order (strongest first). Any other model name sorts
# after these, alphabetically.
MODEL_ORDER = ("opus", "sonnet", "haiku")

WHY_SPLIT = (
    "Why the split: seats whose job is to judge other work (the commit-boundary "
    "reviewers, the deep auditors and architects, the department directors) pin to the "
    "strongest model, because a defect they miss ships unnoticed. Seats that execute a "
    "narrow, checked brief (implementers, test writers, git and routine sweeps) pin to a "
    "mid-tier model, because the review gates check their output. Pure pollers and "
    "runners pin to the cheapest."
)

_KEY_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):[ \t]*(.*)$")
_DEPT_ID = re.compile(r"^[a-z][a-z0-9-]*$")


@dataclass(frozen=True)
class Agent:
    name: str
    model: str
    tools: Optional[str]
    description: str


@dataclass(frozen=True)
class Meta:
    department: str
    trigger: str
    dispatched_by: Tuple[str, ...]


# --------------------------------------------------------------------------- #
# Reading sources
# --------------------------------------------------------------------------- #


def _is_clean_line(value: str) -> bool:
    """True for a non-empty single line with no surrounding whitespace.

    ``str.splitlines`` splits on every line boundary (``\\n``, ``\\r``, form
    feed, NEL, U+2028 and so on), so this also catches a ``\\n`` that a quoted
    JSON/YAML scalar decoded into a real newline.
    """
    return bool(value) and value == value.strip() and value.splitlines() == [value]


def _unquote(value: str) -> str:
    """Return the scalar a one-line YAML value denotes (quotes removed)."""
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] == '"':
        try:
            decoded = json.loads(v)
        except ValueError:
            return v[1:-1]
        return decoded if isinstance(decoded, str) else v[1:-1]
    if len(v) >= 2 and v[0] == v[-1] == "'":
        return v[1:-1].replace("''", "'")
    return v


def parse_frontmatter(text: str) -> Tuple[Dict[str, str], Optional[str]]:
    """Parse the leading ``---`` block. Returns (fields, error-or-None)."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return {}, "no frontmatter (the file must start with a --- line)"
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            end = i
            break
    if end is None:
        return {}, "frontmatter is not closed by a --- line"
    fields: Dict[str, str] = {}
    for raw in lines[1:end]:
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[0] in " \t":
            return {}, "multi-line frontmatter values are not supported: %r" % raw.strip()
        match = _KEY_LINE.match(raw.rstrip())
        if not match:
            return {}, "unparseable frontmatter line: %r" % raw.strip()
        fields[match.group(1)] = _unquote(match.group(2))
    return fields, None


def load_agents(repo: Path) -> Tuple[List[Agent], List[str]]:
    errors: List[str] = []
    agents_dir = repo / AGENTS_REL
    if not agents_dir.is_dir():
        return [], ["%s is not a directory" % AGENTS_REL.as_posix()]
    agents: List[Agent] = []
    for path in sorted(agents_dir.glob("*.md")):
        rel = (AGENTS_REL / path.name).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append("%s: cannot read (%s)" % (rel, exc))
            continue
        fields, problem = parse_frontmatter(text)
        if problem:
            errors.append("%s: %s" % (rel, problem))
            continue
        missing = [k for k in ("name", "description", "model") if not fields.get(k)]
        if missing:
            errors.append("%s: frontmatter lacks %s" % (rel, ", ".join(missing)))
            continue
        bad_lines = [
            k
            for k in ("name", "description", "model", "tools")
            if fields.get(k) is not None and fields[k] != "" and not _is_clean_line(fields[k])
        ]
        if bad_lines:
            errors.append(
                "%s: frontmatter %s must be one line with no surrounding whitespace (a "
                "decoded newline would break the roster table)" % (rel, ", ".join(bad_lines))
            )
            continue
        if "tools" in fields and not fields["tools"]:
            errors.append(
                "%s: frontmatter has an empty tools line (list the tools, or remove the "
                "line to grant every tool)" % rel
            )
            continue
        if fields["name"] != path.stem:
            errors.append(
                "%s: frontmatter name %r does not match the file name %r"
                % (rel, fields["name"], path.stem)
            )
            continue
        agents.append(
            Agent(
                name=fields["name"],
                model=fields["model"],
                tools=fields.get("tools"),
                description=fields["description"],
            )
        )
    if not agents and not errors:
        errors.append("no agent files found under %s" % AGENTS_REL.as_posix())
    return agents, errors


def _load_json(repo: Path, rel: Path) -> Tuple[object, Optional[str]]:
    path = repo / rel
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return None, "%s: cannot read (%s)" % (rel.as_posix(), exc)
    try:
        return json.loads(text), None
    except ValueError as exc:
        return None, "%s: not valid JSON (%s)" % (rel.as_posix(), exc)


def load_pins(repo: Path) -> Tuple[Dict[str, str], List[str]]:
    data, problem = _load_json(repo, POLICY_REL)
    if problem:
        return {}, [problem]
    pins = data.get("agent_pins") if isinstance(data, dict) else None
    if not isinstance(pins, dict) or not pins:
        return {}, ["%s: no non-empty agent_pins object" % POLICY_REL.as_posix()]
    bad = sorted(k for k, v in pins.items() if not isinstance(v, str) or not v)
    if bad:
        return {}, [
            "%s: agent_pins entries must map to a model name: %s"
            % (POLICY_REL.as_posix(), ", ".join(bad))
        ]
    return dict(pins), []


def load_meta(repo: Path, agent_names: Sequence[str]) -> Tuple[Dict[str, Meta], List[str]]:
    data, problem = _load_json(repo, META_REL)
    where = META_REL.as_posix()
    if problem:
        return {}, [problem]
    if not isinstance(data, dict) or not data:
        return {}, ["%s: must be a non-empty object keyed by agent name" % where]
    errors: List[str] = []
    meta: Dict[str, Meta] = {}
    known = set(agent_names)
    for name in sorted(data):
        entry = data[name]
        if not isinstance(entry, dict):
            errors.append("%s: %s must be an object" % (where, name))
            continue
        unknown = sorted(set(entry) - set(META_KEYS))
        absent = [k for k in META_KEYS if k not in entry]
        if unknown:
            errors.append("%s: %s has unknown key(s): %s" % (where, name, ", ".join(unknown)))
        if absent:
            errors.append("%s: %s lacks key(s): %s" % (where, name, ", ".join(absent)))
        if unknown or absent:
            continue
        values = {k: entry[k] for k in META_KEYS}
        empty = [k for k, v in values.items() if not isinstance(v, str) or not _is_clean_line(v)]
        if empty:
            errors.append(
                "%s: %s needs a non-empty single-line string with no surrounding "
                "whitespace for: %s" % (where, name, ", ".join(empty))
            )
            continue
        if not _DEPT_ID.match(values["department"]):
            errors.append(
                "%s: %s department %r must be lowercase letters, digits and hyphens"
                % (where, name, values["department"])
            )
            continue
        tokens = tuple(t.strip() for t in values["dispatched_by"].split(","))
        bad_tokens = [t for t in tokens if (t not in DISPATCHERS and t not in known) or t == name]
        if bad_tokens:
            errors.append(
                "%s: %s dispatched_by has an unknown or self-referencing dispatcher "
                "(%s); use an agent name or one of: %s"
                % (where, name, ", ".join(repr(t) for t in bad_tokens), ", ".join(DISPATCHERS))
            )
            continue
        meta[name] = Meta(values["department"], values["trigger"], tokens)
    return meta, errors


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #


def _node_id(name: str) -> str:
    return "a_" + re.sub(r"[^A-Za-z0-9_]", "_", name)


def validate(agents: Sequence[Agent], pins: Dict[str, str], meta_names: Sequence[str]) -> List[str]:
    """Cross-file parity problems (per-file problems are reported by the loaders)."""
    problems: List[str] = []
    agent_names = {a.name for a in agents}
    meta_set = set(meta_names)
    for agent in agents:
        if agent.name not in meta_set:
            problems.append(
                "agent %r has no entry in %s (add department, trigger and dispatched_by)"
                % (agent.name, META_REL.as_posix())
            )
        pin = pins.get(agent.name)
        if pin is None:
            problems.append(
                "agent %r has no entry in %s agent_pins" % (agent.name, POLICY_REL.as_posix())
            )
        elif pin != agent.model:
            problems.append(
                "agent %r: frontmatter model %r disagrees with its pin %r in %s"
                % (agent.name, agent.model, pin, POLICY_REL.as_posix())
            )
    for name in sorted(meta_set):
        if name not in agent_names:
            problems.append(
                "%s names %r, which has no file in %s/"
                % (META_REL.as_posix(), name, AGENTS_REL.as_posix())
            )
        if name not in pins:
            problems.append(
                "%s names %r, which is not in %s agent_pins"
                % (META_REL.as_posix(), name, POLICY_REL.as_posix())
            )
    ids: Dict[str, str] = {}
    for agent in agents:
        other = ids.setdefault(_node_id(agent.name), agent.name)
        if other != agent.name:
            problems.append("agents %r and %r collide as diagram node ids" % (other, agent.name))
    return problems


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _cell(text: str) -> str:
    """Make text safe inside a Markdown table cell (only the pipe needs it)."""
    return text.replace("|", "\\|")


def _plural(n: int, noun: str) -> str:
    return "%d %s%s" % (n, noun, "" if n == 1 else "s")


def _model_rank(model: str) -> Tuple[int, str]:
    return (MODEL_ORDER.index(model), model) if model in MODEL_ORDER else (len(MODEL_ORDER), model)


def _dept_order(depts: Sequence[str]) -> List[str]:
    known = [d for d in DEPARTMENTS if d in depts]
    return known + sorted(d for d in set(depts) if d not in DEPARTMENTS)


def _dept_title(dept: str) -> str:
    if dept in DEPARTMENTS:
        return DEPARTMENTS[dept][0]
    return dept.replace("-", " ").capitalize()


def _group(agents: Sequence[Agent], meta: Dict[str, Meta]) -> "OrderedDict[str, List[Agent]]":
    by_dept: Dict[str, List[Agent]] = {}
    for agent in sorted(agents, key=lambda a: a.name):
        by_dept.setdefault(meta[agent.name].department, []).append(agent)
    return OrderedDict((d, by_dept[d]) for d in _dept_order(list(by_dept)))


def model_counts(agents: Sequence[Agent]) -> List[Tuple[str, int]]:
    """(model, agent count), strongest model first."""
    counts: Dict[str, int] = {}
    for agent in agents:
        counts[agent.model] = counts.get(agent.model, 0) + 1
    return [(m, counts[m]) for m in sorted(counts, key=_model_rank)]


def summary_text(agents: Sequence[Agent], meta: Dict[str, Meta]) -> str:
    """The ``--summary`` output: counts per model and per department, then why."""
    out: List[str] = ["Agents by model (%d total)" % len(agents)]
    counts = model_counts(agents)
    width = max(len(m) for m, _ in counts)
    for model, n in counts:
        out.append("  %s  %d" % (model.ljust(width), n))
    out.append("By department")
    groups = _group(agents, meta)
    title_width = max(len(_dept_title(d)) for d in groups)
    for dept, members in groups.items():
        split = ", ".join("%s %d" % (m, n) for m, n in model_counts(members))
        out.append("  %s  %2d  (%s)" % (_dept_title(dept).ljust(title_width), len(members), split))
    out.append(WHY_SPLIT)
    return "\n".join(out) + "\n"


_DISPATCHER_NOTES = {
    "orchestrator": "the session you are talking to. It dispatches an agent by name whenever "
    "the work calls for one.",
    "scheduled-job": "an unattended job started by the machine's scheduler (see `schedules/`), "
    "which dispatches the agent without a person in the loop.",
    "operator": "the person running the runtime, who starts the agent by name or with a "
    "slash command such as `/gtm`.",
}


def _agent_link(name: str, doc_names: Sequence[str]) -> str:
    return "[`%s`](%s.md)" % (name, name) if name in doc_names else "`%s`" % name


def _dispatch_diagram(groups: "OrderedDict[str, List[Agent]]", meta: Dict[str, Meta]) -> List[str]:
    lines = ["```mermaid", "flowchart LR"]
    used = [d for d in DISPATCHERS if any(d in m.dispatched_by for m in meta.values())]
    for disp in used:
        lines.append('  d_%s["%s"]' % (disp.replace("-", "_"), DISPATCHERS[disp][0]))
    for dept, members in groups.items():
        lines.append('  subgraph dept_%s["%s"]' % (dept.replace("-", "_"), _dept_title(dept)))
        for agent in members:
            lines.append('    %s["%s"]' % (_node_id(agent.name), agent.name))
        lines.append("  end")
    for disp in used:
        for dept, members in groups.items():
            n = sum(1 for a in members if disp in meta[a.name].dispatched_by)
            if n:
                lines.append(
                    '  d_%s -->|"%s"| dept_%s'
                    % (disp.replace("-", "_"), _plural(n, "agent"), dept.replace("-", "_"))
                )
    everyone = sorted(chain.from_iterable(groups.values()), key=lambda a: a.name)
    agent_names = {a.name for a in everyone}
    for agent in everyone:
        for token in meta[agent.name].dispatched_by:
            if token in agent_names:
                lines.append("  %s --> %s" % (_node_id(token), _node_id(agent.name)))
    lines.append("```")
    return lines


def render_readme(agents: Sequence[Agent], meta: Dict[str, Meta], doc_names: Sequence[str]) -> str:
    groups = _group(agents, meta)
    out: List[str] = []
    add = out.append
    add(
        "<!-- GENERATED by scripts/gen_agent_index.py. Do not edit by hand: change "
        "agents/*.md, knowledge/model_policy.json or knowledge/agent_meta.json, then run "
        "`python3 scripts/gen_agent_index.py`. -->"
    )
    add("# Agent roster")
    add("")
    add(
        "This runtime ships %d agents. An agent is one Markdown file in `agents/`: a short "
        "frontmatter block (`name`, `description`, `model`, `tools`) followed by the prompt "
        "the agent runs under. The `tools` line is the mechanical boundary: an agent cannot "
        "call a tool it was not granted, whatever its prompt says." % len(agents)
    )
    add("")
    add("This page is generated and never edited by hand. Its sources are:")
    add("")
    add("- `agents/*.md` frontmatter: name, model, tools and description, copied verbatim;")
    add(
        "- `knowledge/model_policy.json` `agent_pins`: the model each agent is meant to run on. "
        "The generator fails when a file's `model:` disagrees with its pin. At run time the "
        "model-pin gate (`hooks/model_pin_gate.py`) checks sub-agent dispatches against it, but "
        "only while enforcement is on, and it allows a dispatch rather than block work when the "
        "policy file cannot be read. Workflow steps are not covered by that gate; a separate one "
        "(`hooks/workflow_model_gate.py`) only checks that a model is named;"
    )
    add("- `knowledge/agent_meta.json`: each agent's department, trigger and dispatcher.")
    add("")
    add(
        "`python3 scripts/gen_agent_index.py` rewrites the page, `--check` exits non-zero when "
        "it is stale, and `--summary` prints the model split. An agent's name links to its own "
        "page in this directory when one exists."
    )
    add("")
    add("## Model split")
    add("")
    add("| Model | Agents |")
    add("|---|---|")
    for model, n in model_counts(agents):
        add("| `%s` | %d |" % (model, n))
    add("")
    add(WHY_SPLIT)
    add("")
    add("## Dispatch map")
    add("")
    add(
        "Who starts which agent. An arrow from a dispatcher to a department box means the "
        "dispatcher starts the counted number of agents in it; an arrow between two agents "
        "means the first dispatches the second."
    )
    add("")
    out.extend(_dispatch_diagram(groups, meta))
    add("")
    for disp, (_, plain) in DISPATCHERS.items():
        if any(disp in m.dispatched_by for m in meta.values()):
            add("- **%s**: %s" % (plain, _DISPATCHER_NOTES[disp]))
    add("")
    add("## Roster")
    for dept, members in groups.items():
        title = _dept_title(dept)
        add("")
        add("### %s (%d)" % (title, len(members)))
        add("")
        if dept in DEPARTMENTS:
            add(DEPARTMENTS[dept][1])
            add("")
        add("| Agent | Model | Trigger | Dispatched by | Description |")
        add("|---|---|---|---|---|")
        for agent in members:
            m = meta[agent.name]
            dispatched = ", ".join(
                DISPATCHERS[t][1] if t in DISPATCHERS else _agent_link(t, doc_names)
                for t in m.dispatched_by
            )
            add(
                "| %s | `%s` | %s | %s | %s |"
                % (
                    _agent_link(agent.name, doc_names),
                    agent.model,
                    _cell(m.trigger),
                    _cell(dispatched),
                    _cell(agent.description),
                )
            )
    add("")
    add("## Tool grants")
    add("")
    add(
        "The `tools` line of each agent's frontmatter, verbatim. An agent can use only the "
        "tools listed here."
    )
    add("")
    add("| Agent | Tools |")
    add("|---|---|")
    for agent in sorted(agents, key=lambda a: a.name):
        add("| `%s` | %s |" % (agent.name, _cell(agent.tools or "all tools (no `tools:` line)")))
    add("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# Command line
# --------------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gen_agent_index.py",
        description=(
            "Generate docs/agents/README.md from agents/*.md frontmatter, "
            "knowledge/model_policy.json agent_pins and knowledge/agent_meta.json. "
            "Fails when the three disagree."
        ),
    )
    parser.add_argument(
        "--repo",
        default=None,
        help="checkout to read and write (default: the checkout this script lives in)",
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="exit 1 if docs/agents/README.md is stale or missing; write nothing",
    )
    mode.add_argument(
        "--summary",
        action="store_true",
        help="print the model split (counts per model and department); write nothing",
    )
    return parser


def _fail(problems: Sequence[str]) -> int:
    for problem in problems:
        print("%s: ERROR: %s" % (PROG, problem), file=sys.stderr)
    print(
        "%s: %s found; nothing written" % (PROG, _plural(len(problems), "problem")), file=sys.stderr
    )
    return 1


def _doc_names(repo: Path) -> List[str]:
    docs = repo / "docs" / "agents"
    if not docs.is_dir():
        return []
    return sorted(p.stem for p in docs.glob("*.md") if p.name != OUTPUT_REL.name)


def _page_mode(target: Path) -> int:
    """File mode for the written page: an existing regular file's mode, else 0666 & ~umask."""
    try:
        st = os.lstat(str(target))
    except OSError:
        st = None
    if st is not None and stat.S_ISREG(st.st_mode):
        return stat.S_IMODE(st.st_mode)
    umask = os.umask(0)
    os.umask(umask)
    return 0o666 & ~umask


def _write_atomic(target: Path, data: bytes) -> None:
    """Replace ``target`` with ``data`` without ever writing through a pre-existing path.

    The temporary file gets an unpredictable name and is created with O_EXCL
    (``tempfile.mkstemp``), so a symlink planted at a guessable name such as
    ``README.md.tmp-<pid>`` cannot redirect the write onto another file (for
    example the model policy). ``os.replace`` then swaps the finished file in;
    if ``target`` itself is a symlink, the link is replaced, never followed.
    The temporary file is removed on any failure.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    mode = _page_mode(target)
    fd, name = tempfile.mkstemp(prefix="." + target.name + ".", dir=str(target.parent))
    try:
        # Set the mode on the open descriptor, never by path: a path chmod after
        # the file is closed could follow a link swapped in at ``name``.
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(name, str(target))
    except BaseException:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo) if args.repo else Path(__file__).resolve().parent.parent
    if not repo.is_dir():
        print("%s: --repo %s is not a directory" % (PROG, repo), file=sys.stderr)
        return 2

    agents, problems = load_agents(repo)
    pins, pin_problems = load_pins(repo)
    meta, meta_problems = load_meta(repo, [a.name for a in agents])
    problems = problems + pin_problems + meta_problems
    if not problems:
        problems = validate(agents, pins, list(meta))
    if problems:
        return _fail(problems)

    if args.summary:
        sys.stdout.write(summary_text(agents, meta))
        return 0

    expected = render_readme(agents, meta, _doc_names(repo)).encode("utf-8")
    target = repo / OUTPUT_REL
    current: Optional[bytes] = None
    if target.is_file():
        current = target.read_bytes()

    if args.check:
        if current == expected:
            print("%s: %s is up to date" % (PROG, OUTPUT_REL.as_posix()))
            return 0
        if current is None:
            print("%s: %s is missing" % (PROG, OUTPUT_REL.as_posix()), file=sys.stderr)
        else:
            print("%s: %s is stale" % (PROG, OUTPUT_REL.as_posix()), file=sys.stderr)
            diff = difflib.unified_diff(
                current.decode("utf-8", "replace").splitlines(),
                expected.decode("utf-8").splitlines(),
                "current",
                "expected",
                lineterm="",
                n=0,
            )
            for i, line in enumerate(diff):
                if i >= 20:
                    print("... (diff truncated)", file=sys.stderr)
                    break
                print(line[:200], file=sys.stderr)
        print("regenerate with: python3 scripts/gen_agent_index.py", file=sys.stderr)
        return 1

    if current == expected:
        print("%s: %s already up to date" % (PROG, OUTPUT_REL.as_posix()))
        return 0
    try:
        _write_atomic(target, expected)
    except OSError as exc:
        print("%s: cannot write %s: %s" % (PROG, OUTPUT_REL.as_posix(), exc), file=sys.stderr)
        return 1
    print("%s: wrote %s (%s)" % (PROG, OUTPUT_REL.as_posix(), _plural(len(agents), "agent")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
