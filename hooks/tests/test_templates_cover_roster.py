"""Live-tree guard: the dossier templates shipped in `templates/oversight/` cover
every dossier `scripts/repo_manifest.py doctor` requires, and every placeholder a
template uses is registered in `templates/oversight/PLACEHOLDERS.md`.

WHY THIS EXISTS. `scripts/init_repo.sh` copies every `templates/oversight/*.md` (except
`PLACEHOLDERS.md`) into a new repo as that repo's dossier skeletons; `doctor` then reports
`<agent>\\tmissing-dossier` for any agent whose own text names an `oversight/<agent>.md`
dossier it does not have. When three agents (devops-architect, observability-architect,
video-producer) shipped without a template, a fresh install's `doctor` could never reach
`OK: 0 findings`, whatever the user did. `hooks/bundle_parity.py` rule (b) detects the same gap,
but it is a report-only checker that nothing asserts on, and its own tests use fixtures; this
file is the assertion against the REAL tree.

ROSTER DERIVATION (documented choice). The roster is NOT re-implemented here. The test runs
`scripts/repo_manifest.py doctor` itself (its public CLI) against an empty repo directory and
collects every `<name>\\tmissing-dossier` finding. With no dossier present, that list is exactly
the set of dossiers `doctor` requires: every `agents/*.md` whose text names its own
`oversight/<name>.md` dossier minus the sanctioned "No per-agent ... dossier is expected"
opt-out, minus the out-of-scope `trading-strategist`, plus `dev-runtime` when any agent
references `oversight/dev-runtime.md`. Deriving it from doctor's own output means the test
cannot drift from what doctor really checks.

PLACEHOLDER REGISTRY. A token is `__[A-Z][A-Z0-9_]*__`, the same pattern as
`repo_manifest.PLACEHOLDER_RE` (what `doctor` counts as `placeholder-left`) and
`bundle_parity._PLACEHOLDER_RE`. Every token used by any `templates/oversight/*.md` must appear
somewhere in `PLACEHOLDERS.md`.

The helper functions take the runtime directory as a parameter, so the negative controls below
run the exact detectors against a throwaway runtime and prove each one goes RED on a gap.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

import pytest

# hooks/tests/<this file> -> the runtime root is two levels up. In the deployed shape this is
# ~/.claude; in any scratch layout it is that layout's root.
RUNTIME_DIR = Path(__file__).resolve().parents[2]
DOCTOR_SCRIPT = RUNTIME_DIR / "scripts" / "repo_manifest.py"

# `init_repo.sh` copies every `templates/oversight/*.md` except this one.
REGISTRY_FILE = "PLACEHOLDERS.md"
PLACEHOLDER_RE = re.compile(r"__[A-Z][A-Z0-9_]*__")

# The real roster is ~30 dossiers; a floor well below that still catches a derivation that
# silently returned nothing (which would make the coverage assertion pass vacuously).
MIN_REAL_ROSTER = 10


def _templates_dir(claude_dir: Path) -> Path:
    return claude_dir / "templates" / "oversight"


def required_dossiers(claude_dir: Path, scratch: Path) -> List[str]:
    """Names of the dossiers `doctor` requires for `claude_dir`'s agents, derived by running
    `doctor` against an empty repo directory and collecting its `missing-dossier` findings."""
    assert DOCTOR_SCRIPT.is_file(), f"cannot derive the roster: {DOCTOR_SCRIPT} is missing"
    repo = scratch / "empty-repo"
    repo.mkdir(exist_ok=True)
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(claude_dir)
    proc = subprocess.run(
        [sys.executable, "-I", str(DOCTOR_SCRIPT), "doctor", "--repo", str(repo)],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        stdin=subprocess.DEVNULL,
    )
    # doctor exits 0 (clean) or 1 (findings). Anything else, or a traceback, is a crash and
    # must fail loudly rather than yield an empty roster.
    assert proc.returncode in (0, 1) and "Traceback" not in proc.stderr, (
        f"doctor crashed (rc={proc.returncode}): {proc.stderr[-400:]}"
    )
    suffix = "\tmissing-dossier"
    return sorted(
        {line[: -len(suffix)] for line in proc.stdout.splitlines() if line.endswith(suffix)}
    )


def shipped_templates(claude_dir: Path) -> Set[str]:
    """Names (file stems) of the non-empty dossier templates `init_repo.sh` would copy."""
    tdir = _templates_dir(claude_dir)
    if not tdir.is_dir():
        return set()
    return {
        p.stem
        for p in tdir.glob("*.md")
        if p.name != REGISTRY_FILE
        and p.stat().st_size > 0
        and p.read_text(encoding="utf-8").strip()
    }


def missing_templates(claude_dir: Path, scratch: Path) -> List[str]:
    """Dossiers `doctor` requires that no non-empty `templates/oversight/<name>.md` provides."""
    shipped = shipped_templates(claude_dir)
    return [name for name in required_dossiers(claude_dir, scratch) if name not in shipped]


def registered_tokens(claude_dir: Path) -> Set[str]:
    registry = _templates_dir(claude_dir) / REGISTRY_FILE
    if not registry.is_file():
        return set()
    return set(PLACEHOLDER_RE.findall(registry.read_text(encoding="utf-8")))


def unregistered_placeholders(claude_dir: Path) -> Dict[str, List[str]]:
    """template file name -> tokens it uses that `PLACEHOLDERS.md` does not list."""
    registry = registered_tokens(claude_dir)
    out: Dict[str, List[str]] = {}
    tdir = _templates_dir(claude_dir)
    for path in sorted(tdir.glob("*.md")) if tdir.is_dir() else []:
        if path.name == REGISTRY_FILE:
            continue
        unknown = sorted(set(PLACEHOLDER_RE.findall(path.read_text(encoding="utf-8"))) - registry)
        if unknown:
            out[path.name] = unknown
    return out


# ---------------------------------------------------------------------------
# The real tree
# ---------------------------------------------------------------------------


def test_roster_derivation_is_not_vacuous(tmp_path: Path) -> None:
    """If doctor's output were unparseable the coverage test below would pass on an empty
    roster. The real roster is large and always includes the shared `dev-runtime` dossier."""
    roster = required_dossiers(RUNTIME_DIR, tmp_path)
    assert len(roster) >= MIN_REAL_ROSTER, f"roster suspiciously small: {roster}"
    assert "dev-runtime" in roster, f"doctor no longer requires dev-runtime? roster={roster}"


def test_every_dossier_doctor_requires_has_a_template(tmp_path: Path) -> None:
    """INTENDED behavior: a fresh `init_repo.sh` install gets a skeleton for every dossier
    `doctor` will ask for, so `doctor` can reach `OK: 0 findings` once placeholders are filled."""
    missing = missing_templates(RUNTIME_DIR, tmp_path)
    assert not missing, (
        "doctor requires a dossier with no shipped template (add templates/oversight/<name>.md "
        f"and register its tokens in PLACEHOLDERS.md): {missing}"
    )


def test_registry_file_exists_and_lists_tokens() -> None:
    assert len(registered_tokens(RUNTIME_DIR)) > 20, "PLACEHOLDERS.md missing or lists no tokens"


_REAL_TEMPLATES = sorted(
    p.name for p in _templates_dir(RUNTIME_DIR).glob("*.md") if p.name != REGISTRY_FILE
)


def test_templates_directory_is_not_empty() -> None:
    """Guards the parametrized test below against collecting zero cases."""
    assert len(_REAL_TEMPLATES) >= MIN_REAL_ROSTER


@pytest.mark.parametrize("template_name", _REAL_TEMPLATES)
def test_template_placeholders_are_all_registered(template_name: str) -> None:
    """Every `__TOKEN__` a template uses is listed in PLACEHOLDERS.md (a template that
    introduces a new token without registering it is a defect in the same change)."""
    unknown = unregistered_placeholders(RUNTIME_DIR).get(template_name, [])
    assert not unknown, f"{template_name} uses tokens missing from PLACEHOLDERS.md: {unknown}"


# ---------------------------------------------------------------------------
# Negative controls: the detectors above must go RED on a gap, and GREEN when it is closed.
# ---------------------------------------------------------------------------


def _fake_runtime(root: Path, agents: Dict[str, str], templates: Dict[str, str]) -> Path:
    cdir = root / "fake_claude_dir"
    (cdir / "agents").mkdir(parents=True)
    (_templates_dir(cdir)).mkdir(parents=True)
    for name, body in agents.items():
        (cdir / "agents" / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: x\nmodel: sonnet\ntools: Read\n---\n\n{body}\n",
            encoding="utf-8",
        )
    for fname, body in templates.items():
        (_templates_dir(cdir) / fname).write_text(body, encoding="utf-8")
    return cdir


_DOSSIER_REF = "Read the repo-local dossier `.claude/oversight/{name}.md` before judging."


def test_detector_flags_an_agent_with_no_template(tmp_path: Path) -> None:
    cdir = _fake_runtime(
        tmp_path,
        agents={"alpha": _DOSSIER_REF.format(name="alpha")},
        templates={REGISTRY_FILE: "| `__A__` | a |\n"},
    )
    assert missing_templates(cdir, tmp_path) == ["alpha"]


def test_detector_clears_once_the_template_exists(tmp_path: Path) -> None:
    """Pair of the control above: closing the gap makes the same detector pass."""
    cdir = _fake_runtime(
        tmp_path,
        agents={"alpha": _DOSSIER_REF.format(name="alpha")},
        templates={REGISTRY_FILE: "| `__A__` | a |\n", "alpha.md": "# alpha\n\n## s\n__A__\n"},
    )
    assert missing_templates(cdir, tmp_path) == []


def test_detector_treats_an_empty_template_as_missing(tmp_path: Path) -> None:
    cdir = _fake_runtime(
        tmp_path,
        agents={"alpha": _DOSSIER_REF.format(name="alpha")},
        templates={REGISTRY_FILE: "| `__A__` | a |\n", "alpha.md": "  \n"},
    )
    assert missing_templates(cdir, tmp_path) == ["alpha"]


def test_roster_honors_doctor_opt_out_and_out_of_scope_agent(tmp_path: Path) -> None:
    """The roster must mirror doctor: an agent carrying the sanctioned no-dossier sentence and
    the out-of-scope `trading-strategist` never require a template; a dev-runtime reference does."""
    cdir = _fake_runtime(
        tmp_path,
        agents={
            "alpha": _DOSSIER_REF.format(name="alpha")
            + " Also read `.claude/oversight/dev-runtime.md`.",
            "beta": "No per-agent `.claude/oversight/beta.md` dossier is expected in any repo.",
            "trading-strategist": _DOSSIER_REF.format(name="trading-strategist"),
        },
        templates={REGISTRY_FILE: "| `__A__` | a |\n"},
    )
    assert required_dossiers(cdir, tmp_path) == ["alpha", "dev-runtime"]


def test_detector_flags_an_unregistered_placeholder(tmp_path: Path) -> None:
    cdir = _fake_runtime(
        tmp_path,
        agents={},
        templates={
            REGISTRY_FILE: "| `__KNOWN__` | a known token |\n",
            "alpha.md": "# alpha\n\n## s\n__KNOWN__ and __NOT_REGISTERED__\n",
            "beta.md": "# beta\n\n## s\n__KNOWN__\n",
        },
    )
    assert unregistered_placeholders(cdir) == {"alpha.md": ["__NOT_REGISTERED__"]}
