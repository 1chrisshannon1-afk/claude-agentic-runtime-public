"""Parity test for `agents/*.md` `description:` frontmatter lines.

Built for the 2026-09-28 rewrite that gave every runtime agent a mechanically-triggerable
description (operator directive: "i want agents to be called on or initiated mechanically
when/where reasonable and possible"), shaped as:

    Use when <concrete trigger situations>. <the lane in one clause>. Not for <the
    confused lane> (use <other agent>).

Four rules, all mechanical:

1. Every `agents/*.md` `description:` starts with "Use when" -- EXCEPT the three seats
   the operator's standing rules name for proactive dispatch (plan-reviewer: any plan before
   implementation, CLAUDE.md §10; agentic-systems-architect: any new or changed agent or agentic
   loop design, operator rule 2026-09-28; auth/tenancy/billing/secrets/webhooks/agent-tool-
   grant changes), whose descriptions instead start with "Use proactively":
   `plan-reviewer`, `agentic-systems-architect`, `trust-architect`.
2. Every description is <= 300 characters (an unnecessary dispatch costs ~400K tokens;
   precision over recall).
3. The TOTAL characters across every description is <= 14,000 (the whole roster's
   descriptions live in the dispatcher's context on every session).
4. "Use proactively" appears in a description ONLY for those three seats -- nowhere else.

This test reads the real frontmatter (via PyYAML, falling back to a manual scan only if
PyYAML is unavailable) rather than re-deriving the rule from prose, so it fails loudly if a
future edit reintroduces a bad opener, blows the length budget, or widens "Use proactively"
past its three sanctioned seats.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover - PyYAML is a standing runtime dependency
    yaml = None

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"

MAX_DESC_CHARS = 300
MAX_TOTAL_CHARS = 14000

# The only three seats sanctioned for "Use proactively" framing (plan-reviewer and trust-architect
# from CLAUDE.md §10; agentic-systems-architect from the operator's 2026-09-28 standing rule):
#   - plan-reviewer: any plan before implementation
#   - agentic-systems-architect: any new or changed agent definition or agentic loop
#   - trust-architect: auth, tenancy, billing, secrets, webhooks, agent tool grants
PROACTIVE_ALLOWED = {"plan-reviewer", "agentic-systems-architect", "trust-architect"}


def _extract_frontmatter(text: str) -> str:
    """Return the raw YAML frontmatter block (between the first two '---' lines)."""
    lines = text.split("\n")
    assert lines and lines[0].strip() == "---", "agent file must open with a '---' frontmatter fence"
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    assert end_idx is not None, "agent file frontmatter never closes with '---'"
    return "\n".join(lines[1:end_idx])


def _description_from_frontmatter(fm_text: str) -> str:
    """Return the `description:` field's value, via PyYAML when available.

    Falls back to a manual single-line scan (handles a bare or double-quoted value) only
    if PyYAML cannot be imported -- every agent file in this roster carries a single-line
    description (verified when this test was authored), so the fallback never needs to
    handle a YAML block scalar.
    """
    if yaml is not None:
        data = yaml.safe_load(fm_text)
        assert isinstance(data, dict) and "description" in data, "no description: field"
        return str(data["description"])

    for line in fm_text.split("\n"):
        if line.startswith("description:"):
            value = line[len("description:"):].strip()
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("''", "'")
            return value
    raise AssertionError("no description: field found in frontmatter")


def _agent_files() -> list[Path]:
    files = sorted(AGENTS_DIR.glob("*.md"))
    assert files, f"no agent files found under {AGENTS_DIR}"
    return files


def _agent_descriptions() -> dict[str, str]:
    result = {}
    for path in _agent_files():
        fm = _extract_frontmatter(path.read_text())
        result[path.stem] = _description_from_frontmatter(fm)
    return result


@pytest.fixture(scope="module")
def descriptions() -> dict[str, str]:
    return _agent_descriptions()


def test_every_agent_file_has_a_description(descriptions: dict[str, str]) -> None:
    assert len(descriptions) == len(_agent_files()), "every agent file must yield exactly one description"
    for name, desc in descriptions.items():
        assert desc.strip(), f"{name}: description is empty"


def test_descriptions_start_with_use_when_or_use_proactively(descriptions: dict[str, str]) -> None:
    bad = {}
    for name, desc in descriptions.items():
        if name in PROACTIVE_ALLOWED:
            if not desc.startswith("Use proactively"):
                bad[name] = desc[:60]
        else:
            if not desc.startswith("Use when"):
                bad[name] = desc[:60]
    assert not bad, f"descriptions with the wrong opener (name -> first 60 chars): {bad}"


def test_no_description_exceeds_300_characters(descriptions: dict[str, str]) -> None:
    over = {name: len(desc) for name, desc in descriptions.items() if len(desc) > MAX_DESC_CHARS}
    assert not over, f"descriptions over {MAX_DESC_CHARS} chars: {over}"


def test_total_description_characters_within_budget(descriptions: dict[str, str]) -> None:
    total = sum(len(desc) for desc in descriptions.values())
    assert total <= MAX_TOTAL_CHARS, (
        f"total description characters {total} exceeds the {MAX_TOTAL_CHARS}-char budget "
        f"across {len(descriptions)} agents"
    )


def test_use_proactively_appears_only_in_the_three_allowed_seats(descriptions: dict[str, str]) -> None:
    actual_proactive = {name for name, desc in descriptions.items() if "Use proactively" in desc}
    assert actual_proactive == PROACTIVE_ALLOWED, (
        f"'Use proactively' seat mismatch: found {sorted(actual_proactive)}, "
        f"expected exactly {sorted(PROACTIVE_ALLOWED)}"
    )


def test_descriptions_do_not_use_bare_everyday_trigger_words(descriptions: dict[str, str]) -> None:
    """Guard against over-broad bare-word triggers the task explicitly called out.

    A bare occurrence of these words as a STANDALONE trigger phrase is what's forbidden
    (e.g. "Use when a sale happens" would false-trigger on ordinary CSA/OtherCompanyB product
    vocabulary). This check is deliberately narrow: it flags the exact single-word forms
    the task named, matched as whole words, since those are the ones proven to be ordinary
    product vocabulary in these repos ("estimate", "job", "sale" all mean something mundane
    in ExampleApp AI / OtherCompanyB / trading-repo contexts). It does not flag a phrase
    like "sell the company" or "hire an employee", which are the sanctioned, precise forms.
    """
    forbidden_bare_words = {"sale", "sales", "hire", "buyer", "estimate", "job"}
    offenders = {}
    for name, desc in descriptions.items():
        # Strip the sanctioned precise phrases before scanning for bare occurrences, so a
        # description that correctly uses "sell the company" isn't flagged for containing
        # a word this test cares about only in its bare/standalone form.
        # Words inside the "Not for ..." clause are disambiguation (they steer the
        # model AWAY from this seat), so they are not triggers.
        scrubbed = re.split(r"\bNot for\b", desc, maxsplit=1)[0]
        for phrase in (
            "sell the company",
            "sell a company",
            "selling a company",
            "selling the company",
            "co-founder",
            "find a co-founder",
            "hire an employee",
            "hire staff",
            "job post",
            "post a job",
            "company buyer",
            "an acquirer",
        ):
            scrubbed = re.sub(re.escape(phrase), "", scrubbed, flags=re.IGNORECASE)
        words = set(re.findall(r"[a-zA-Z]+", scrubbed.lower()))
        hit = words & forbidden_bare_words
        if hit:
            offenders[name] = sorted(hit)
    assert not offenders, (
        f"descriptions using a forbidden bare everyday trigger word (never as a lone "
        f"trigger -- use a precise phrase instead): {offenders}"
    )
