"""Tests for scripts/gen_agent_index.py, the generator of docs/agents/README.md.

Spec (the script's docstring and the grade-A plan's Phase C1):

  * the roster page is derived from ``agents/*.md`` frontmatter, the read-only
    ``knowledge/model_policy.json`` ``agent_pins`` and ``knowledge/agent_meta.json``;
    descriptions and tool lists are copied verbatim;
  * the script is the parity check for ``agent_meta.json``: it exits 1 and
    writes nothing when an agent lacks meta, when meta names an agent that is
    absent from ``agents/`` or from ``agent_pins``, or when a frontmatter model
    disagrees with its pin;
  * ``--check`` fails when the page is stale or missing; ``--summary`` prints the
    model split; output is byte-stable.

Every case builds a scratch checkout under tmp_path and runs the script against
it with ``--repo``, with a throwaway HOME, so the real ~/.claude is never
written. Every "this input is rejected" case is paired with a recovery step
(the same checkout, repaired, succeeds), per the contract's required pairings.

Sandbox rule: no test writes outside pytest's own base temp directory. ``run()``
takes the HOME it hands the subprocess as a required argument and refuses (fails
the test) any HOME that is not under that base directory, so a helper can never
quietly create a directory beside the real checkout. The in-process tests load
the script with bytecode writing off, so they leave no ``__pycache__`` behind.

Falsification hook: ``GEN_AGENT_INDEX_SCRIPT=<path>`` points every test at a
different copy of the script (a scratch mutant). The suite must go red on each
mutant that removes one of the checks above.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Callable, Dict, Iterator, List, Optional, Tuple

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = Path(os.environ.get("GEN_AGENT_INDEX_SCRIPT") or REPO / "scripts" / "gen_agent_index.py")

# name -> (model, tools, description, quote-the-description-in-the-frontmatter)
BASE_AGENTS: Dict[str, Tuple[str, Optional[str], str, bool]] = {
    "builder": (
        "sonnet",
        "Read, Edit, Write, Bash",
        "Use when code needs writing via targeted edits. Never commits.",
        False,
    ),
    "reviewer": (
        "opus",
        "Read, Grep, Glob, Bash",
        'Use when a commit is about to land | checks correctness; "quoted" words stay — intact.',
        True,
    ),
    "director": (
        "opus",
        "Read, Grep, Agent",
        "Use when a weekly verdict is needed: ranks all work, kills gold-plating.",
        False,
    ),
    "poller": ("haiku", "Bash, Read", "Use when a CI run needs polling to completion.", False),
}

# name -> (department, trigger, dispatched_by)
BASE_META: Dict[str, Tuple[str, str, str]] = {
    "builder": ("dev", "A code change on an assigned file partition", "orchestrator"),
    "reviewer": ("dev", "Before every commit", "orchestrator"),
    "director": ("oversight", "Weekly scheduled report", "scheduled-job, operator"),
    "poller": ("oversight", "After a push", "director"),
}

DOCS = ("builder", "director")


class Checkout:
    """A scratch checkout whose sources are held in memory and written on save()."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.agents: Dict[str, Tuple[str, Optional[str], str, bool]] = dict(BASE_AGENTS)
        self.pins: Dict[str, str] = {n: a[0] for n, a in BASE_AGENTS.items()}
        self.pins["general-purpose"] = "sonnet"  # a pin with no agent file is legitimate
        self.meta: Dict[str, Dict[str, object]] = {
            n: {"department": d, "trigger": t, "dispatched_by": b}
            for n, (d, t, b) in BASE_META.items()
        }
        self.extra_files: Dict[str, str] = {}
        self.policy_text: Optional[str] = None
        self.meta_text: Optional[str] = None
        self.docs = list(DOCS)

    @property
    def readme(self) -> Path:
        return self.root / "docs" / "agents" / "README.md"

    @property
    def home(self) -> Path:
        """The throwaway HOME for this checkout: a sibling of the checkout, so inside tmp_path."""
        return self.root.parent / "home"

    def run(self, *args: str, cwd: Optional[Path] = None) -> "subprocess.CompletedProcess[str]":
        return run(self.root, *args, home=self.home, cwd=cwd)

    @staticmethod
    def agent_text(name: str, spec: Tuple[str, Optional[str], str, bool]) -> str:
        model, tools, description, quote = spec
        desc = json.dumps(description, ensure_ascii=False) if quote else description
        tools_line = "" if tools is None else "tools: %s\n" % tools
        return "---\nname: %s\ndescription: %s\nmodel: %s\n%s---\n\nPrompt body.\n" % (
            name,
            desc,
            model,
            tools_line,
        )

    def save(self) -> "Checkout":
        for d in ("agents", "knowledge", "docs/agents"):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        for stale in (self.root / "agents").glob("*.md"):
            stale.unlink()
        for name, spec in self.agents.items():
            (self.root / "agents" / (name + ".md")).write_text(
                self.agent_text(name, spec), encoding="utf-8"
            )
        for rel, text in self.extra_files.items():
            (self.root / rel).write_text(text, encoding="utf-8")
        policy = (
            self.policy_text
            if self.policy_text is not None
            else json.dumps({"version": 1, "agent_pins": self.pins}, indent=2)
        )
        (self.root / "knowledge" / "model_policy.json").write_text(policy, encoding="utf-8")
        meta = (
            self.meta_text
            if self.meta_text is not None
            else json.dumps(self.meta, indent=2, ensure_ascii=False)
        )
        (self.root / "knowledge" / "agent_meta.json").write_text(meta, encoding="utf-8")
        for page in (self.root / "docs" / "agents").glob("*.md"):
            if page.name != "README.md":
                page.unlink()
        for name in self.docs:
            (self.root / "docs" / "agents" / (name + ".md")).write_text("# " + name + "\n")
        return self

    def set_model(self, name: str, model: str) -> None:
        _, tools, desc, quote = self.agents[name]
        self.agents[name] = (model, tools, desc, quote)


@pytest.fixture()
def fx(tmp_path: Path) -> Checkout:
    return Checkout(tmp_path / "repo").save()


_SANDBOX_ROOT: List[Path] = []


@pytest.fixture(autouse=True)
def _sandbox_root(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Record pytest's base temp directory so run() can refuse a HOME outside it."""
    _SANDBOX_ROOT.append(tmp_path_factory.getbasetemp().resolve())
    try:
        yield
    finally:
        _SANDBOX_ROOT.clear()


def run(
    repo: Path, *args: str, home: Path, cwd: Optional[Path] = None
) -> "subprocess.CompletedProcess[str]":
    """Run the script against ``repo`` with ``home`` as HOME and, by default, as cwd.

    ``home`` must be under pytest's base temp directory: the helper creates it, so
    a HOME derived from the real checkout's location would create a directory
    outside the sandbox (``Path(repo).parent / "home"`` did exactly that for the
    real repo).
    """
    assert _SANDBOX_ROOT, "the autouse _sandbox_root fixture did not run"
    resolved = home.resolve()
    assert _SANDBOX_ROOT[0] in resolved.parents, (
        "refusing to create HOME %s outside the pytest sandbox %s" % (resolved, _SANDBOX_ROOT[0])
    )
    home.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("CSA_", "CLAUDE_"))}
    env["HOME"] = str(home)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), *args],
        cwd=str(cwd or home),
        env=env,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=60,
    )


def load_generator() -> ModuleType:
    """Import the script under test in-process without writing bytecode beside it."""
    spec = importlib.util.spec_from_file_location("gen_agent_index_under_test", SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    sys.modules[spec.name] = mod  # dataclasses resolves string annotations through it
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = previous
        del sys.modules[spec.name]
    return mod


def digest(*paths: Path) -> str:
    h = hashlib.sha256()
    for p in paths:
        h.update(p.read_bytes())
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# The page itself
# --------------------------------------------------------------------------- #


def test_generates_a_page_listing_every_agent_grouped_by_department(fx: Checkout) -> None:
    r = fx.run()
    assert r.returncode == 0, r.stderr
    text = fx.readme.read_text(encoding="utf-8")
    for name in BASE_AGENTS:
        assert "`%s`" % name in text
    dev = text.index("### Development workflow (2)")
    oversight = text.index("### Oversight roster (2)")
    assert dev < oversight, "known departments render in their fixed order"
    assert text.startswith("<!-- GENERATED by scripts/gen_agent_index.py")
    assert "```mermaid" in text
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_description_and_tools_are_copied_verbatim(fx: Checkout) -> None:
    fx.run()
    text = fx.readme.read_text(encoding="utf-8")
    # quoted in the frontmatter, unquoted on the page, only the table pipe escaped
    assert (
        'Use when a commit is about to land \\| checks correctness; "quoted" words stay — intact.'
        in text
    )
    # unquoted source with a colon inside is kept whole
    assert "Use when a weekly verdict is needed: ranks all work, kills gold-plating." in text
    for _, tools, _, _ in BASE_AGENTS.values():
        assert "| %s |" % tools in text


def test_description_is_never_truncated_or_rewrapped(fx: Checkout) -> None:
    # a run of double spaces must survive too: re-wrapping would collapse it
    long_desc = "Use when " + " ".join("word%03d" % i for i in range(120)) + "  end."
    fx.agents["builder"] = ("sonnet", "Read", long_desc, False)
    fx.save()
    assert fx.run().returncode == 0
    assert long_desc in fx.readme.read_text(encoding="utf-8")


def test_real_agent_descriptions_appear_verbatim_in_the_committed_page() -> None:
    page = (REPO / "docs" / "agents" / "README.md").read_text(encoding="utf-8")
    checked = 0
    for path in sorted((REPO / "agents").glob("*.md")):
        line = next(
            ln
            for ln in path.read_text(encoding="utf-8").split("\n")
            if ln.startswith("description:")
        )
        desc = line[len("description:") :].strip()
        if len(desc) > 1 and desc[0] == desc[-1] == '"':
            desc = desc[1:-1]
        assert desc.replace("|", "\\|") in page, path.name
        checked += 1
    assert checked > 0


def test_name_links_to_its_page_only_when_the_page_exists(fx: Checkout) -> None:
    fx.run()
    text = fx.readme.read_text(encoding="utf-8")
    assert "[`builder`](builder.md)" in text
    assert "[`director`](director.md)" in text
    assert "(reviewer.md)" not in text and "(poller.md)" not in text
    # recovery: adding the page turns the name into a link on the next run
    fx.docs.append("reviewer")
    fx.save()
    fx.run()
    assert "[`reviewer`](reviewer.md)" in fx.readme.read_text(encoding="utf-8")


def test_an_unlisted_department_still_renders_after_the_known_ones(fx: Checkout) -> None:
    fx.meta["poller"]["department"] = "data-eng"
    fx.save()
    assert fx.run().returncode == 0
    text = fx.readme.read_text(encoding="utf-8")
    assert "### Data eng (1)" in text
    assert text.index("### Oversight roster (1)") < text.index("### Data eng (1)")


def test_agent_to_agent_dispatch_becomes_a_diagram_edge(fx: Checkout) -> None:
    fx.run()
    text = fx.readme.read_text(encoding="utf-8")
    assert "a_director --> a_poller" in text  # poller is dispatched_by director
    assert 'd_scheduled_job -->|"1 agent"| dept_oversight' in text
    assert 'd_orchestrator -->|"2 agents"| dept_dev' in text


def test_a_pin_with_no_agent_file_is_not_an_error(fx: Checkout) -> None:
    assert "general-purpose" in fx.pins and "general-purpose" not in fx.agents
    assert fx.run().returncode == 0


def test_page_describes_the_pin_gate_without_overclaiming(fx: Checkout) -> None:
    # The gate checks sub-agent dispatches only, only while enforcement is on, and allows a
    # dispatch when the policy cannot be read; Workflow steps have a separate, weaker gate.
    fx.run()
    text = fx.readme.read_text(encoding="utf-8")
    assert "gate enforces it" not in text
    assert "only while enforcement is on" in text
    assert "allows a dispatch rather than block work" in text
    assert "Workflow steps are not covered by that gate" in text


def test_sources_are_read_only(fx: Checkout) -> None:
    sources = sorted((fx.root / "agents").glob("*.md")) + [
        fx.root / "knowledge" / "model_policy.json",
        fx.root / "knowledge" / "agent_meta.json",
    ]
    before = digest(*sources)
    for args in ((), ("--check",), ("--summary",)):
        fx.run(*args)
    assert digest(*sources) == before


def test_rerun_leaves_an_unchanged_page_alone(fx: Checkout) -> None:
    assert fx.run().returncode == 0
    first = fx.readme.read_bytes()
    r = fx.run()
    assert r.returncode == 0 and "already up to date" in r.stdout
    assert fx.readme.read_bytes() == first


# --------------------------------------------------------------------------- #
# Parity failures: each must exit 1, name the problem, write nothing, and be
# recoverable once the checkout is repaired.
# --------------------------------------------------------------------------- #


def _break_missing_meta(fx: Checkout) -> None:
    del fx.meta["poller"]


def _fix_missing_meta(fx: Checkout) -> None:
    fx.meta["poller"] = {
        "department": "oversight",
        "trigger": "After a push",
        "dispatched_by": "director",
    }


def _break_meta_for_missing_agent(fx: Checkout) -> None:
    fx.meta["ghost"] = {"department": "dev", "trigger": "x", "dispatched_by": "orchestrator"}
    fx.pins["ghost"] = "sonnet"  # pinned, so only the missing agent file is wrong


def _fix_meta_for_missing_agent(fx: Checkout) -> None:
    del fx.meta["ghost"]


def _break_meta_for_unpinned_agent(fx: Checkout) -> None:
    fx.agents["extra"] = ("sonnet", "Read", "Use when extra.", False)
    fx.meta["extra"] = {"department": "dev", "trigger": "x", "dispatched_by": "orchestrator"}


def _fix_meta_for_unpinned_agent(fx: Checkout) -> None:
    fx.pins["extra"] = "sonnet"


def _break_meta_for_unknown_everything(fx: Checkout) -> None:
    fx.meta["ghost"] = {"department": "dev", "trigger": "x", "dispatched_by": "orchestrator"}


def _break_model_disagrees_with_pin(fx: Checkout) -> None:
    fx.pins["builder"] = "opus"


def _fix_model_disagrees_with_pin(fx: Checkout) -> None:
    fx.pins["builder"] = "sonnet"


def _break_frontmatter_model_changed(fx: Checkout) -> None:
    fx.set_model("reviewer", "sonnet")


def _fix_frontmatter_model_changed(fx: Checkout) -> None:
    fx.set_model("reviewer", "opus")


def _break_agent_without_pin(fx: Checkout) -> None:
    del fx.pins["poller"]


def _fix_agent_without_pin(fx: Checkout) -> None:
    fx.pins["poller"] = "haiku"


def _meta_edit(key: str, value: object) -> Callable[[Checkout], None]:
    def edit(fx: Checkout) -> None:
        fx.meta["builder"][key] = value

    return edit


def _meta_del(key: str) -> Callable[[Checkout], None]:
    def edit(fx: Checkout) -> None:
        del fx.meta["builder"][key]

    return edit


def _fix_builder_meta(fx: Checkout) -> None:
    fx.meta["builder"] = {
        "department": "dev",
        "trigger": "A code change on an assigned file partition",
        "dispatched_by": "orchestrator",
    }


def _break_name_mismatch(fx: Checkout) -> None:
    fx.extra_files["agents/builder.md"] = Checkout.agent_text(
        "builder", BASE_AGENTS["builder"]
    ).replace("name: builder", "name: builderx")


def _break_no_frontmatter(fx: Checkout) -> None:
    fx.extra_files["agents/oops.md"] = "Just a prompt, no frontmatter.\n"


def _fix_remove_oops(fx: Checkout) -> None:
    fx.extra_files.pop("agents/oops.md", None)


def _break_no_model(fx: Checkout) -> None:
    fx.extra_files["agents/builder.md"] = (
        "---\nname: builder\ndescription: Use when x.\ntools: Read\n---\nbody\n"
    )


def _break_meta_json(fx: Checkout) -> None:
    fx.meta_text = "{not json"


def _fix_meta_json(fx: Checkout) -> None:
    fx.meta_text = None


def _break_policy_json(fx: Checkout) -> None:
    fx.policy_text = "[1, 2"


def _break_policy_without_pins(fx: Checkout) -> None:
    fx.policy_text = json.dumps({"version": 1})


def _fix_policy(fx: Checkout) -> None:
    fx.policy_text = None


def _break_empty_agents(fx: Checkout) -> None:
    fx.agents = {}
    fx.meta = {"x": {"department": "dev", "trigger": "t", "dispatched_by": "operator"}}


def _fix_restore_all(fx: Checkout) -> None:
    fresh = Checkout(fx.root)
    fx.agents, fx.pins, fx.meta = fresh.agents, fresh.pins, fresh.meta
    fx.extra_files.clear()


def _break_node_id_collision(fx: Checkout) -> None:
    for name in ("a-b", "a_b"):
        fx.agents[name] = ("sonnet", "Read", "Use when " + name + ".", False)
        fx.pins[name] = "sonnet"
        fx.meta[name] = {"department": "dev", "trigger": "t", "dispatched_by": "operator"}


def _fix_node_id_collision(fx: Checkout) -> None:
    for name in ("a-b", "a_b"):
        del fx.agents[name], fx.pins[name], fx.meta[name]


def _break_description_decodes_to_newline(fx: Checkout) -> None:
    fx.agents["builder"] = ("sonnet", "Read", "Use when a\nb.", True)


def _break_description_has_surrounding_whitespace(fx: Checkout) -> None:
    fx.agents["builder"] = ("sonnet", "Read", " padded.", True)


def _break_description_has_unicode_line_separator(fx: Checkout) -> None:
    fx.agents["builder"] = ("sonnet", "Read", "Use when a\u2028b.", True)


def _break_tools_decode_to_newline(fx: Checkout) -> None:
    fx.extra_files["agents/builder.md"] = Checkout.agent_text(
        "builder", ("sonnet", None, "Use when x.", False)
    ).replace("---\n\nPrompt", 'tools: "Read,\\nBash"\n---\n\nPrompt')


def _break_empty_tools_line(fx: Checkout) -> None:
    fx.extra_files["agents/builder.md"] = Checkout.agent_text(
        "builder", ("sonnet", None, "Use when x.", False)
    ).replace("---\n\nPrompt", "tools:\n---\n\nPrompt")


Case = Tuple[str, Callable[[Checkout], None], Callable[[Checkout], None], List[str]]

FAILURE_CASES: List[Case] = [
    (
        "agent-without-meta",
        _break_missing_meta,
        _fix_missing_meta,
        ["agent 'poller' has no entry in knowledge/agent_meta.json"],
    ),
    (
        "meta-names-agent-with-no-file",
        _break_meta_for_missing_agent,
        _fix_meta_for_missing_agent,
        ["names 'ghost', which has no file in agents/"],
    ),
    (
        "meta-names-agent-missing-from-pins",
        _break_meta_for_unpinned_agent,
        _fix_meta_for_unpinned_agent,
        ["names 'extra', which is not in knowledge/model_policy.json agent_pins"],
    ),
    (
        "meta-names-agent-in-neither-place",
        _break_meta_for_unknown_everything,
        _fix_meta_for_missing_agent,
        [
            "names 'ghost', which has no file in agents/",
            "names 'ghost', which is not in knowledge/model_policy.json agent_pins",
        ],
    ),
    (
        "agent-without-pin",
        _break_agent_without_pin,
        _fix_agent_without_pin,
        ["agent 'poller' has no entry in knowledge/model_policy.json agent_pins"],
    ),
    (
        "pin-disagrees-with-frontmatter",
        _break_model_disagrees_with_pin,
        _fix_model_disagrees_with_pin,
        ["agent 'builder': frontmatter model 'sonnet' disagrees with its pin 'opus'"],
    ),
    (
        "frontmatter-model-edited",
        _break_frontmatter_model_changed,
        _fix_frontmatter_model_changed,
        ["agent 'reviewer': frontmatter model 'sonnet' disagrees with its pin 'opus'"],
    ),
    (
        "meta-lacks-key",
        _meta_del("trigger"),
        _fix_builder_meta,
        ["builder lacks key(s): trigger"],
    ),
    (
        "meta-unknown-key",
        _meta_edit("owner", "me"),
        _fix_builder_meta,
        ["builder has unknown key(s): owner"],
    ),
    (
        "meta-blank-value",
        _meta_edit("trigger", "   "),
        _fix_builder_meta,
        ["builder needs a non-empty single-line string"],
    ),
    (
        "meta-multiline-value",
        _meta_edit("trigger", "line one\nline two"),
        _fix_builder_meta,
        ["builder needs a non-empty single-line string"],
    ),
    (
        "meta-non-string-value",
        _meta_edit("trigger", 7),
        _fix_builder_meta,
        ["builder needs a non-empty single-line string"],
    ),
    (
        "meta-bad-department-id",
        _meta_edit("department", "Dev Team"),
        _fix_builder_meta,
        ["builder department 'Dev Team' must be lowercase"],
    ),
    (
        "meta-unknown-dispatcher",
        _meta_edit("dispatched_by", "cron"),
        _fix_builder_meta,
        ["builder dispatched_by has an unknown or self-referencing dispatcher ('cron')"],
    ),
    (
        "meta-dispatched-by-itself",
        _meta_edit("dispatched_by", "builder"),
        _fix_builder_meta,
        ["builder dispatched_by has an unknown or self-referencing dispatcher ('builder')"],
    ),
    (
        "frontmatter-name-differs-from-file",
        _break_name_mismatch,
        _fix_restore_all,
        ["agents/builder.md: frontmatter name 'builderx' does not match the file name 'builder'"],
    ),
    (
        "agent-file-without-frontmatter",
        _break_no_frontmatter,
        _fix_remove_oops,
        ["agents/oops.md: no frontmatter"],
    ),
    (
        "frontmatter-without-model",
        _break_no_model,
        _fix_restore_all,
        ["agents/builder.md: frontmatter lacks model"],
    ),
    (
        "meta-file-not-json",
        _break_meta_json,
        _fix_meta_json,
        ["knowledge/agent_meta.json: not valid JSON"],
    ),
    (
        "policy-file-not-json",
        _break_policy_json,
        _fix_policy,
        ["knowledge/model_policy.json: not valid JSON"],
    ),
    (
        "policy-without-agent-pins",
        _break_policy_without_pins,
        _fix_policy,
        ["knowledge/model_policy.json: no non-empty agent_pins object"],
    ),
    (
        "no-agent-files",
        _break_empty_agents,
        _fix_restore_all,
        ["no agent files found under agents"],
    ),
    (
        "frontmatter-description-decodes-to-newline",
        _break_description_decodes_to_newline,
        _fix_restore_all,
        ["agents/builder.md: frontmatter description must be one line"],
    ),
    (
        "frontmatter-description-has-surrounding-whitespace",
        _break_description_has_surrounding_whitespace,
        _fix_restore_all,
        ["agents/builder.md: frontmatter description must be one line"],
    ),
    (
        "frontmatter-description-has-unicode-line-separator",
        _break_description_has_unicode_line_separator,
        _fix_restore_all,
        ["agents/builder.md: frontmatter description must be one line"],
    ),
    (
        "frontmatter-tools-decode-to-newline",
        _break_tools_decode_to_newline,
        _fix_restore_all,
        ["agents/builder.md: frontmatter tools must be one line"],
    ),
    (
        "frontmatter-empty-tools-line",
        _break_empty_tools_line,
        _fix_restore_all,
        ["agents/builder.md: frontmatter has an empty tools line"],
    ),
    (
        "meta-carriage-return-value",
        _meta_edit("trigger", "line one\rline two"),
        _fix_builder_meta,
        ["builder needs a non-empty single-line string"],
    ),
    (
        "node-id-collision",
        _break_node_id_collision,
        _fix_node_id_collision,
        ["agents 'a-b' and 'a_b' collide as diagram node ids"],
    ),
]


@pytest.mark.parametrize(
    "label,break_it,fix_it,expected",
    FAILURE_CASES,
    ids=[c[0] for c in FAILURE_CASES],
)
def test_parity_failure_is_rejected_and_recoverable(
    fx: Checkout,
    label: str,
    break_it: Callable[[Checkout], None],
    fix_it: Callable[[Checkout], None],
    expected: List[str],
) -> None:
    break_it(fx)
    fx.save()
    bad = fx.run()
    assert bad.returncode == 1, (bad.stdout, bad.stderr)
    for needle in expected:
        assert needle in bad.stderr, (needle, bad.stderr)
    assert "Traceback" not in bad.stderr
    assert bad.stdout == ""
    assert not fx.readme.exists(), "a rejected checkout must write nothing"
    # --check and --summary reject the same input; neither prints a roster
    assert fx.run("--check").returncode == 1
    summary = fx.run("--summary")
    assert summary.returncode == 1 and summary.stdout == ""

    fix_it(fx)
    fx.save()
    good = fx.run()
    assert good.returncode == 0, good.stderr
    assert fx.readme.exists()


def test_a_rejected_run_leaves_an_existing_page_untouched(fx: Checkout) -> None:
    assert fx.run().returncode == 0
    before = fx.readme.read_bytes()
    fx.pins["builder"] = "opus"
    fx.save()
    assert fx.run().returncode == 1
    assert fx.readme.read_bytes() == before


def test_every_problem_is_reported_in_one_run(fx: Checkout) -> None:
    del fx.meta["poller"]
    fx.pins["builder"] = "opus"
    fx.save()
    r = fx.run()
    assert r.returncode == 1
    assert "agent 'poller' has no entry" in r.stderr
    assert "agent 'builder': frontmatter model" in r.stderr
    assert "2 problems found" in r.stderr


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_output_directory_is_a_clean_error_and_recoverable(fx: Checkout) -> None:
    out_dir = fx.root / "docs" / "agents"
    out_dir.chmod(0o555)
    try:
        r = fx.run()
        assert r.returncode == 1
        assert "cannot write" in r.stderr and "Traceback" not in r.stderr
        assert sorted(p.name for p in out_dir.iterdir()) == sorted(n + ".md" for n in DOCS)
    finally:
        out_dir.chmod(0o755)
    assert fx.run().returncode == 0


def test_a_symlink_planted_at_the_old_temp_name_is_never_written_through(
    fx: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The first implementation wrote to docs/agents/README.md.tmp-<pid>, a name an attacker
    # (a hostile branch, a build step) can predict. A link planted there to the model policy
    # was followed by the write, so the policy was overwritten and the pin gate, which
    # fails open on an unreadable policy, would stop enforcing anything.
    mod = load_generator()
    policy = fx.root / "knowledge" / "model_policy.json"
    before = digest(policy)
    monkeypatch.setattr(os, "getpid", lambda: 4242)
    planted = fx.root / "docs" / "agents" / "README.md.tmp-4242"
    planted.symlink_to(os.path.join("..", "..", "knowledge", "model_policy.json"))

    assert mod.main(["--repo", str(fx.root)]) == 0

    assert digest(policy) == before, "the policy was written through the planted link"
    assert json.loads(policy.read_text(encoding="utf-8"))["agent_pins"] == fx.pins
    assert planted.is_symlink(), "the planted link itself must be left alone"
    assert fx.readme.is_file() and not fx.readme.is_symlink()
    assert fx.readme.read_text(encoding="utf-8").startswith("<!-- GENERATED")
    # recovery: the checkout still validates and regenerates cleanly afterwards
    assert fx.run("--check").returncode == 0


def test_the_temp_file_is_created_exclusively(
    fx: Checkout, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The planted-link test above pins one guessable name. The property that rules out every
    # guessable name is that the temp file is created with O_CREAT | O_EXCL, which refuses to
    # open anything that already exists, link or not.
    mod = load_generator()
    real_open = os.open
    flags_seen: List[int] = []

    def spy(path: str, flags: int, mode: int = 0o777) -> int:
        if Path(path).parent == fx.readme.parent:
            flags_seen.append(flags)
        return real_open(path, flags, mode)

    monkeypatch.setattr(os, "open", spy)
    assert mod.main(["--repo", str(fx.root)]) == 0
    created = [f for f in flags_seen if f & os.O_CREAT]
    assert created, "no file was created in the output directory"
    assert all(f & os.O_EXCL for f in created), "the temp file must be opened with O_EXCL"


def test_a_symlinked_page_is_replaced_not_followed(fx: Checkout) -> None:
    policy = fx.root / "knowledge" / "model_policy.json"
    before = digest(policy)
    fx.readme.symlink_to(os.path.join("..", "..", "knowledge", "model_policy.json"))

    r = fx.run()

    assert r.returncode == 0, r.stderr
    assert digest(policy) == before
    assert fx.readme.is_file() and not fx.readme.is_symlink()
    assert fx.run("--check").returncode == 0


def test_the_page_gets_the_normal_file_mode_and_an_existing_mode_is_kept(fx: Checkout) -> None:
    umask = os.umask(0)
    os.umask(umask)
    assert fx.run().returncode == 0
    # mkstemp creates 0600; a page nobody else can read would be a silent regression
    assert stat.S_IMODE(fx.readme.stat().st_mode) == 0o666 & ~umask

    fx.readme.write_text("stale", encoding="utf-8")
    fx.readme.chmod(0o640)
    assert fx.run().returncode == 0
    assert stat.S_IMODE(fx.readme.stat().st_mode) == 0o640
    assert fx.run("--check").returncode == 0


def test_a_failed_replace_leaves_no_temp_file_and_a_retry_succeeds(
    fx: Checkout, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mod = load_generator()
    real_replace = os.replace

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    assert mod.main(["--repo", str(fx.root)]) == 1
    err = capsys.readouterr().err
    assert "cannot write" in err and "disk full" in err and "Traceback" not in err
    assert sorted(p.name for p in (fx.root / "docs" / "agents").iterdir()) == sorted(
        n + ".md" for n in DOCS
    ), "a failed write must not leave its temp file behind"

    monkeypatch.setattr(os, "replace", real_replace)
    assert mod.main(["--repo", str(fx.root)]) == 0
    assert fx.readme.is_file()


def test_an_agent_without_a_tools_line_is_listed_as_having_every_tool(fx: Checkout) -> None:
    fx.agents["builder"] = ("sonnet", None, "Use when code needs writing.", False)
    fx.save()
    assert "tools:" not in (fx.root / "agents" / "builder.md").read_text(encoding="utf-8")
    assert fx.run().returncode == 0
    text = fx.readme.read_text(encoding="utf-8")
    assert "| `builder` | all tools (no `tools:` line) |" in text
    assert "| `reviewer` | Read, Grep, Glob, Bash |" in text

    # recovery: once the agent names its tools, the row lists them instead
    fx.agents["builder"] = ("sonnet", "Read, Edit", "Use when code needs writing.", False)
    fx.save()
    assert fx.run().returncode == 0
    text = fx.readme.read_text(encoding="utf-8")
    assert "| `builder` | Read, Edit |" in text
    assert "all tools" not in text


# --------------------------------------------------------------------------- #
# --check
# --------------------------------------------------------------------------- #


def test_check_passes_on_a_fresh_page(fx: Checkout) -> None:
    fx.run()
    r = fx.run("--check")
    assert r.returncode == 0, r.stderr
    assert "up to date" in r.stdout


def test_check_fails_on_a_hand_edited_page_and_regeneration_recovers(fx: Checkout) -> None:
    fx.run()
    edited = fx.readme.read_text(encoding="utf-8").replace(
        "# Agent roster", "# Agent roster (edited)"
    )
    fx.readme.write_text(edited, encoding="utf-8")
    r = fx.run("--check")
    assert r.returncode == 1
    assert "is stale" in r.stderr and "gen_agent_index.py" in r.stderr
    assert fx.readme.read_text(encoding="utf-8") == edited, "--check must not rewrite the page"
    assert fx.run().returncode == 0
    assert fx.run("--check").returncode == 0


def test_check_fails_when_an_agent_description_changes_after_generation(fx: Checkout) -> None:
    fx.run()
    fx.agents["builder"] = ("sonnet", "Read, Edit, Write, Bash", "Use when something new.", False)
    fx.save()
    assert fx.run("--check").returncode == 1
    fx.run()
    assert fx.run("--check").returncode == 0


def test_check_fails_when_an_agent_page_is_added_or_removed(fx: Checkout) -> None:
    fx.run()
    fx.docs.append("poller")
    fx.save()
    assert fx.run("--check").returncode == 1, "the link set is part of the page"
    fx.run()
    fx.docs.remove("poller")
    fx.save()
    assert fx.run("--check").returncode == 1


def test_check_fails_and_creates_nothing_when_the_page_is_missing(fx: Checkout) -> None:
    r = fx.run("--check")
    assert r.returncode == 1
    assert "is missing" in r.stderr
    assert not fx.readme.exists()
    assert fx.run().returncode == 0
    assert fx.run("--check").returncode == 0


def test_the_committed_roster_page_is_fresh(tmp_path: Path) -> None:
    r = run(REPO, "--check", home=tmp_path / "home")
    assert r.returncode == 0, r.stderr


# --------------------------------------------------------------------------- #
# --summary
# --------------------------------------------------------------------------- #


def test_summary_prints_counts_per_model_and_per_department(fx: Checkout) -> None:
    r = fx.run("--summary")
    assert r.returncode == 0, r.stderr
    lines = r.stdout.splitlines()
    assert lines[0] == "Agents by model (4 total)"
    assert re.search(r"^\s+opus\s+2$", r.stdout, re.M)
    assert re.search(r"^\s+sonnet\s+1$", r.stdout, re.M)
    assert re.search(r"^\s+haiku\s+1$", r.stdout, re.M)
    assert r.stdout.index("opus") < r.stdout.index("sonnet") < r.stdout.index("haiku"), (
        "strongest model first"
    )
    assert re.search(r"Development workflow\s+2\s+\(opus 1, sonnet 1\)", r.stdout)
    assert re.search(r"Oversight roster\s+2\s+\(opus 1, haiku 1\)", r.stdout)


def test_summary_explains_why_reviewers_pin_strong_and_implementers_do_not(fx: Checkout) -> None:
    out = fx.run("--summary").stdout
    why = next(line for line in out.splitlines() if line.startswith("Why the split:"))
    assert "reviewers" in why and "strongest model" in why
    assert "implementers" in why and "mid-tier" in why


def test_summary_writes_nothing(fx: Checkout) -> None:
    assert fx.run("--summary").returncode == 0
    assert not fx.readme.exists()


def test_check_and_summary_are_mutually_exclusive(fx: Checkout) -> None:
    r = fx.run("--check", "--summary")
    assert r.returncode == 2
    assert "not allowed with" in r.stderr


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


def test_output_is_byte_stable_across_runs(fx: Checkout) -> None:
    fx.run()
    first = fx.readme.read_bytes()
    fx.readme.unlink()
    fx.run()
    assert fx.readme.read_bytes() == first


def test_output_does_not_depend_on_file_creation_order_cwd_or_home(tmp_path: Path) -> None:
    a = Checkout(tmp_path / "a" / "repo").save()
    a.run()
    b = Checkout(tmp_path / "b" / "repo")
    b.agents = dict(reversed(list(BASE_AGENTS.items())))
    b.meta = dict(reversed(list(b.meta.items())))
    b.pins = dict(reversed(list(b.pins.items())))
    b.save()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    b.run(cwd=elsewhere)
    assert a.readme.read_bytes() == b.readme.read_bytes()


class _AscendingListingPath(type(Path())):
    """A Path whose glob() lists names in ascending order, whatever the filesystem does."""

    def glob(self, pattern: str) -> Iterator[Path]:
        return iter(sorted(super().glob(pattern)))


class _DescendingListingPath(type(Path())):
    """A Path whose glob() lists names in descending order."""

    def glob(self, pattern: str) -> Iterator[Path]:
        return iter(sorted(super().glob(pattern), reverse=True))


def test_roster_order_does_not_depend_on_the_directory_listing_order(fx: Checkout) -> None:
    # Filesystems list directories in different orders (APFS hash order, ext4 hash order).
    # Rendering the same checkout under two opposite listings must give the same page.
    mod = load_generator()

    pages = []
    listings = []
    for path_type in (_AscendingListingPath, _DescendingListingPath):
        root = path_type(str(fx.root))
        listings.append([p.name for p in (root / "agents").glob("*.md")])
        agents, problems = mod.load_agents(root)
        assert not problems, problems
        meta, problems = mod.load_meta(root, [a.name for a in agents])
        assert not problems, problems
        pages.append(mod.render_readme(agents, meta, list(DOCS)))
    assert listings[0] == sorted(listings[0]) and listings[1] == sorted(listings[0], reverse=True)
    assert pages[0] == pages[1]


def test_output_carries_no_timestamp_or_path_of_the_checkout(fx: Checkout) -> None:
    fx.run()
    text = fx.readme.read_text(encoding="utf-8")
    assert str(fx.root) not in text
    assert not re.search(r"\b20\d\d-\d\d-\d\d\b", text)


def test_a_deep_copy_of_the_checkout_regenerates_the_same_bytes(fx: Checkout) -> None:
    fx.run()
    twin = copy.deepcopy(fx)
    twin.root = fx.root.parent / "twin"
    twin.save()
    twin.run()
    assert twin.readme.read_bytes() == fx.readme.read_bytes()


# --------------------------------------------------------------------------- #
# Command line and portability
# --------------------------------------------------------------------------- #


def test_help_exits_zero_and_prints_usage(fx: Checkout) -> None:
    r = fx.run("--help")
    assert r.returncode == 0
    assert r.stdout.startswith("usage:")
    for flag in ("--repo", "--check", "--summary"):
        assert flag in r.stdout


def test_a_missing_repo_is_a_usage_error(tmp_path: Path) -> None:
    r = run(tmp_path / "no-such-checkout", home=tmp_path / "home")
    assert r.returncode == 2
    assert "not a directory" in r.stderr


def test_script_parses_as_python_3_9() -> None:
    ast.parse(SCRIPT.read_text(encoding="utf-8"), feature_version=(3, 9))


def test_script_uses_only_the_standard_library() -> None:
    if not hasattr(sys, "stdlib_module_names"):
        pytest.skip("sys.stdlib_module_names needs Python 3.10+")
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert imported <= set(sys.stdlib_module_names), sorted(imported)
