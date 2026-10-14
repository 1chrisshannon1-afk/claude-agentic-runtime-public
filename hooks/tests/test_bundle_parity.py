"""Tests for hooks/bundle_parity.py (report-only, fail-open bundle/mirror parity
checker; runtime_bundle_repo_agnostic_plan.md §WS5.6 rules (a)-(g) + §WS5.8(d)).

Written from the plan's CONTRACT, not from the implementation, which is being
built in parallel and may not exist yet at the time these tests are authored
(expected RED until it lands, GREEN after). Every assertion targets the rule
text quoted in the plan:

  (a) agent -> knowledge/<x>_primer.md must be in `.mirror/config.json`'s
      `include` AND tracked at HEAD (`git ls-files`).
  (b) agent that reads `<repo>/.claude/oversight/<a>.md` -> a non-empty
      `templates/oversight/<a>.md` exists with >= 3 `##` headings, no
      forbidden_patterns hit, and every `__PLACEHOLDER__` token it uses is
      registered in `templates/oversight/PLACEHOLDERS.md`. An agent carrying
      the literal opt-out phrase ("No per-agent `.claude/oversight/<name>.md`
      dossier is expected in any repo") never requires a template.
  (c) `docs/agents/<a>.md` must exist for every bundle agent.
  (d) every skills/<s>, tools/<t>, scripts/<x> path referenced by a bundle
      agent/primer/skill/command must be in `include` AND tracked at HEAD.
      Two carve-outs, both from the module's own `DEFERRED_PATHS`/dangling
      handling (added alongside the parallel implementation, tested here
      from that contract): a referenced path listed in `DEFERRED_PATHS`
      (e.g. `skills/live-testing`, deliberately out-of-scope per the plan's
      §0) yields its own `deferred` line -- informational, excluded from
      `findings` and from the exit-code decision, counted only in
      `summary["deferred"]`; a referenced path that does not exist ANYWHERE
      on disk (e.g. `scripts/ghost.py`) yields its own `dangling` line --
      also informational and never a `referenced-paths-shipped` finding,
      since "not shipped" and "does not exist at all" are different defects
      (mirrors rule (g)'s own existing dangling-vs-ships split, but for (d)
      the dangling line is explicitly uncounted rather than counted).
  (e) twin check (NAME-COLLISION scoped): for each registered repo, a
      `<root>/.claude/agents/<name>.md` (REPLACES direction) or
      `<root>/.claude/skills/<name>/` (DEAD-code direction) whose name
      collides with a runtime agent/skill name is flagged, naming the
      direction; scans `<root>/.claude/worktrees/*/.claude/{agents,skills}`
      too; a non-colliding repo-local skill is clean; an empty registry
      reports "no repos registered" -- itself emitted as a genuine finding
      line (`twin-check\t(none)\tno repos registered`), not a silent pass,
      so a fixture with an empty registry always exits 1 on that line alone
      even when every other rule is clean.
  (f) mirror-clone README agent count vs. `ls agents/*.md | wc -l`; fail-open
      (no finding) when no local clone exists.
  (g) every `knowledge/<path>` referenced from a bundle agent/primer/skill/
      command ships (in include + tracked) or has a `templates/knowledge/
      <path>` seed; a reference to a genuinely nonexistent knowledge path is
      a `dangling` line, never a `knowledge-referenced-ships` finding.

  Bundle set = all agents/*.md minus trading-strategist (the plan's own
  definition) -- trading-strategist must never appear in any finding.
  Exit code: 0 clean / 1 with findings. Every rule wraps its own body in a
  broad exception handler that turns a genuine crash into a single
  `rule-error\t<rule>\t<detail>` line rather than raising out; malformed
  input that is guarded by a narrower, more targeted check upstream (e.g. a
  `.mirror/config.json` that fails to parse) degrades silently to an empty
  default (e.g. `include: []`) instead, which is a DIFFERENT but equally
  fail-open path -- both are asserted below, and neither ever produces a
  Python traceback or a nondeterministic exit code.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path.home() / ".claude" / "hooks" / "bundle_parity.py"


def _skip_if_absent():
    if not SCRIPT.exists():
        pytest.skip(f"bundle_parity.py not yet present at {SCRIPT} (expected RED)")


# ---------------------------------------------------------------------------
# fixture builder: a scratch CLAUDE_DIR that is its own git repo with one
# commit, holding the minimal fixture set the task spec enumerates.
# ---------------------------------------------------------------------------


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_scratch_claude_dir(tmp_path: Path) -> Path:
    cdir = tmp_path / "scratch_claude_dir"
    cdir.mkdir()
    _git("init", "-q", cwd=cdir)
    _git("config", "user.email", "t@example.com", cwd=cdir)
    _git("config", "user.name", "t", cwd=cdir)

    # agents/x.md -- references a primer, a dossier, a skill, and a plain
    # knowledge reference.
    (cdir / "agents").mkdir()
    (cdir / "agents" / "x.md").write_text(
        "---\nname: x\ndescription: x agent\nmodel: sonnet\ntools: Read\n---\n\n"
        "Read `~/.claude/knowledge/x_primer.md` for your discipline.\n"
        "Read the repo-local dossier `.claude/oversight/x.md` before judging.\n"
        "Use the `skills/foo` skill when appropriate.\n"
        "See also `knowledge/ref.md` for background.\n"
    )
    # agents/y.md -- opt-out phrase, never requires a template.
    (cdir / "agents" / "y.md").write_text(
        "---\nname: y\ndescription: y agent\nmodel: sonnet\ntools: Read\n---\n\n"
        "Read `.claude/oversight/y.md` for this repo's grounding facts.\n\n"
        "No per-agent `.claude/oversight/y.md` dossier is expected in any repo.\n"
    )
    # agents/trading-strategist.md -- must be excluded from the bundle set.
    (cdir / "agents" / "trading-strategist.md").write_text(
        "---\nname: trading-strategist\ndescription: excluded\nmodel: sonnet\n"
        "tools: Read\n---\n\n"
        "Read `.claude/oversight/trading-strategist.md` and "
        "`knowledge/trading_strategist_equities_primer.md`. Never bundled.\n"
    )

    # knowledge/
    (cdir / "knowledge").mkdir()
    (cdir / "knowledge" / "x_primer.md").write_text("# x primer\n\nDiscipline.\n")
    (cdir / "knowledge" / "ref.md").write_text("# ref\n\nBackground.\n")
    (cdir / "knowledge" / "repo_registry.json").write_text(
        json.dumps({"schema_version": 1, "repos": {}})
    )
    (cdir / "knowledge" / "wheel_repos.json").write_text(json.dumps({"_comment": "x"}))

    # templates/oversight/x.md -- 3 headings, one placeholder token.
    (cdir / "templates" / "oversight").mkdir(parents=True)
    (cdir / "templates" / "oversight" / "x.md").write_text(
        "# x -- repo-local grounding dossier\n\n"
        "## (a) First\n\n__TOK__\n\n"
        "## (b) Second\n\nBody.\n\n"
        "## (c) Third\n\nBody.\n"
    )
    (cdir / "templates" / "oversight" / "PLACEHOLDERS.md").write_text(
        "# Template placeholder tokens\n\n"
        "| token | meaning | example |\n"
        "|---|---|---|\n"
        "| `__TOK__` | a test token | `value` |\n"
    )
    (cdir / "templates" / "knowledge").mkdir(parents=True)
    (cdir / "templates" / "knowledge" / "seed.jsonl").write_text("")

    # docs/agents/
    (cdir / "docs" / "agents").mkdir(parents=True)
    (cdir / "docs" / "agents" / "x.md").write_text("# x\n\nDocs for x.\n")
    (cdir / "docs" / "agents" / "y.md").write_text("# y\n\nDocs for y.\n")

    # skills/foo/SKILL.md
    (cdir / "skills" / "foo").mkdir(parents=True)
    (cdir / "skills" / "foo" / "SKILL.md").write_text(
        "---\nname: foo\ndescription: test skill\n---\n\nBody.\n"
    )

    # .mirror/config.json -- include covers everything except what a RED
    # case deliberately drops; clone_dir points at a tmp dir with a README.
    mirror_clone = tmp_path / "mirror_clone_dir"
    mirror_clone.mkdir()
    (mirror_clone / "README.md").write_text("This bundle ships 3 agents.\n")

    (cdir / ".mirror").mkdir()
    (cdir / ".mirror" / "config.json").write_text(
        json.dumps(
            {
                "remote_url": "https://example.invalid/repo.git",
                "clone_dir": str(mirror_clone),
                "branch": "master",
                "include": [
                    "agents",
                    "knowledge/x_primer.md",
                    "knowledge/ref.md",
                    "skills/foo",
                    "templates",
                    "docs",
                ],
                "mirror_managed": ["CLAUDE.md", "README.md"],
                "replacements": [],
                "forbidden_patterns": ["forbidden-token-should-never-appear"],
                "forbidden_allow": {},
            }
        )
    )

    _git("add", "-A", cwd=cdir)
    _git("commit", "-q", "-m", "seed", cwd=cdir)
    return cdir


def _run(cdir: Path, *extra_args: str, timeout: int = 30):
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(cdir)
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--json", *extra_args],
        cwd=str(cdir),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _findings(proc) -> list[str]:
    """Parse --json output into its findings list, tolerating either a bare
    list or an object carrying a `findings` key -- the exact shape is an
    implementation detail this suite does not lock in beyond "a list of
    strings is retrievable"."""
    payload = json.loads(proc.stdout)
    if isinstance(payload, list):
        return payload
    assert isinstance(payload, dict) and "findings" in payload, (
        f"--json output has neither list nor 'findings' key: {payload!r}"
    )
    return payload["findings"]


def _payload(proc) -> dict:
    """Parse --json output into its full object (findings + summary), for
    tests that need to inspect `summary` counts directly rather than only
    the findings list `_findings()` returns."""
    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict) and "findings" in payload and "summary" in payload, (
        f"--json output missing findings/summary keys: {payload!r}"
    )
    return payload


def _commit_all(cdir: Path, message: str = "update") -> None:
    _git("add", "-A", cwd=cdir)
    _git("commit", "-q", "-m", message, cwd=cdir)


# ---------------------------------------------------------------------------
# exit codes + trading-strategist exclusion (cross-cutting, checked in every
# scenario below via the shared _findings/_run helpers)
# ---------------------------------------------------------------------------


def test_clean_fixture_exits_0_with_no_findings(tmp_path):
    """The base fixture alone is not enough to reach a genuinely EMPTY
    findings list: rule (e)'s own vacuous-registry line
    (`twin-check\t(none)\tno repos registered`) is itself a reported
    finding, so an empty `repo_registry.json` always yields exit 1 on that
    line alone (see test_rule_e_empty_registry_reports_no_repos_registered
    below for that behavior in isolation). Registering one real,
    non-colliding repo satisfies rule (e) with nothing to report, making
    "fully clean" reachable."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product0", name="product0")
    proc = _run(cdir)
    assert proc.returncode == 0
    assert _findings(proc) == []


def test_trading_strategist_never_appears_in_any_finding(tmp_path):
    """trading-strategist.md deliberately references a nonexistent dossier,
    a nonexistent primer, and is absent from docs/agents/ and templates/
    oversight/ -- every one of those would be a finding for a bundled agent,
    but the plan excludes trading-strategist from the bundle set entirely."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    proc = _run(cdir)
    for finding in _findings(proc):
        assert "trading-strategist" not in finding, finding


# ---------------------------------------------------------------------------
# (a) primer must be in include + tracked at HEAD
# ---------------------------------------------------------------------------


def test_rule_a_primer_dropped_from_include_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"] = [p for p in config["include"] if p != "knowledge/x_primer.md"]
    config_path.write_text(json.dumps(config))
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("primer-shipped" in f and "x_primer.md" in f for f in findings), findings


def test_rule_a_recovers_once_primer_restored_to_include(tmp_path):
    """Pairs with the drop-from-include case: restore the include entry and
    the primer-shipped finding disappears."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"] = [p for p in config["include"] if p != "knowledge/x_primer.md"]
    config_path.write_text(json.dumps(config))
    _commit_all(cdir)
    bad = _run(cdir)
    assert bad.returncode == 1

    config["include"].append("knowledge/x_primer.md")
    config_path.write_text(json.dumps(config))
    _commit_all(cdir, "restore include")
    good = _run(cdir)
    # NOT a bare exit-0 assertion: the base fixture's empty repo_registry.json
    # always contributes its own vacuous twin-check finding (rule (e)),
    # unrelated to rule (a) -- see test_clean_fixture_exits_0_with_no_findings
    # for the genuinely-clean case with a repo registered.
    assert not any("primer-shipped" in f for f in _findings(good))


# ---------------------------------------------------------------------------
# (b) template existence / heading count / placeholder registration /
#     opt-out exemption
# ---------------------------------------------------------------------------


def test_rule_b_missing_template_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "templates" / "oversight" / "x.md").unlink()
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("x.md" in f for f in findings if "template" in f.lower()), findings


def test_rule_b_template_with_fewer_than_3_headings_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "templates" / "oversight" / "x.md").write_text(
        "# x -- repo-local grounding dossier\n\n## (a) Only one\n\nBody.\n"
    )
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any(
        "x.md" in f and ("heading" in f.lower() or "template" in f.lower())
        for f in findings
    ), findings


def test_rule_b_undocumented_placeholder_token_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "templates" / "oversight" / "x.md").write_text(
        "# x -- repo-local grounding dossier\n\n"
        "## (a) First\n\n__NEW__\n\n"
        "## (b) Second\n\nBody.\n\n"
        "## (c) Third\n\nBody.\n"
    )
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("__NEW__" in f for f in findings), findings


def test_rule_b_placeholder_recovers_once_registered(tmp_path):
    """Pairs with the undocumented-token case: register __NEW__ in
    PLACEHOLDERS.md and the finding disappears."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "templates" / "oversight" / "x.md").write_text(
        "# x -- repo-local grounding dossier\n\n"
        "## (a) First\n\n__NEW__\n\n"
        "## (b) Second\n\nBody.\n\n"
        "## (c) Third\n\nBody.\n"
    )
    _commit_all(cdir)
    bad = _run(cdir)
    assert any("__NEW__" in f for f in _findings(bad))

    placeholders = cdir / "templates" / "oversight" / "PLACEHOLDERS.md"
    placeholders.write_text(
        placeholders.read_text() + "| `__NEW__` | a new token | `value` |\n"
    )
    _commit_all(cdir, "register __NEW__")
    good = _run(cdir)
    assert not any("__NEW__" in f for f in _findings(good))


def test_rule_b_opt_out_agent_never_requires_a_template(tmp_path):
    """agents/y.md carries the literal opt-out phrase and has NO
    templates/oversight/y.md on disk at all -- must never surface as a
    missing-template finding."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    assert not (cdir / "templates" / "oversight" / "y.md").exists()
    proc = _run(cdir)
    findings = _findings(proc)
    assert not any(
        "y.md" in f and ("template" in f.lower() or "missing" in f.lower())
        for f in findings
    ), findings


# ---------------------------------------------------------------------------
# (c) docs/agents/<a>.md must exist for every bundle agent
# ---------------------------------------------------------------------------


def test_rule_c_missing_docs_agent_page_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "docs" / "agents" / "x.md").unlink()
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("docs/agents/x.md" in f or ("x.md" in f and "docs" in f.lower()) for f in findings), findings


def test_rule_c_recovers_once_docs_agent_page_restored(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "docs" / "agents" / "x.md").unlink()
    _commit_all(cdir)
    bad = _run(cdir)
    assert bad.returncode == 1

    (cdir / "docs" / "agents" / "x.md").write_text("# x\n\nDocs for x.\n")
    _commit_all(cdir, "restore docs page")
    good = _run(cdir)
    # NOT a bare exit-0 assertion: the base fixture's empty repo_registry.json
    # always contributes its own vacuous twin-check finding (rule (e)),
    # unrelated to rule (c) -- see test_clean_fixture_exits_0_with_no_findings
    # for the genuinely-clean case with a repo registered.
    assert not any("doc-present" in f and "x" in f for f in _findings(good))


# ---------------------------------------------------------------------------
# (d) skills/tools/scripts referenced must be in include AND tracked at HEAD
# ---------------------------------------------------------------------------


def test_rule_d_untracked_skill_is_a_finding(tmp_path):
    """skills/foo/SKILL.md exists on disk but is never committed -- `git
    ls-files` at HEAD does not see it, so it must be flagged even though the
    file is physically present. NOTE: deliberately does not use
    `_commit_all` for the untrack step -- `_commit_all` runs `git add -A`
    first, which would re-stage the still-present worktree file right back,
    making the untrack commit an empty no-op that git refuses."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    # Remove and recreate uncommitted, to prove HEAD (not the worktree) is
    # what's being checked.
    skill_dir = cdir / "skills" / "bar"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: bar\ndescription: x\n---\nBody.\n")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nAlso use `skills/bar`.\n"
    )
    _commit_all(cdir)
    # Now make it untracked-at-HEAD by removing the commit's effect: delete
    # from the index only (keep the worktree file), then commit ONLY that
    # index change -- not `_commit_all`, which would re-add the file.
    _git("rm", "--cached", "-r", "-q", "skills/bar", cwd=cdir)
    _git("commit", "-q", "-m", "untrack bar", cwd=cdir)
    assert skill_dir.exists()  # still present in the worktree

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("skills/bar" in f for f in findings), findings


def test_rule_d_recovers_once_skill_is_committed(tmp_path):
    """NOTE: the untrack step commits directly (never via `_commit_all`,
    which `git add -A`s first and would re-stage the still-present file,
    making the untrack commit an empty no-op that git refuses)."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    skill_dir = cdir / "skills" / "bar"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\nname: bar\ndescription: x\n---\nBody.\n")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nAlso use `skills/bar`.\n"
    )
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"].append("skills/bar")
    config_path.write_text(json.dumps(config))
    _commit_all(cdir, "untracked bar reference")
    _git("rm", "--cached", "-r", "-q", "skills/bar", cwd=cdir)
    _git("commit", "-q", "-m", "untrack bar", cwd=cdir)
    bad = _run(cdir)
    assert bad.returncode == 1
    assert any("skills/bar" in f for f in _findings(bad))

    _commit_all(cdir, "commit bar for real")
    good = _run(cdir)
    assert not any("skills/bar" in f for f in _findings(good))


# ---------------------------------------------------------------------------
# (d) DEFERRED_PATHS carve-out: a referenced path the module explicitly
# defers (e.g. `skills/live-testing`, out of this whole plan's scope per
# §0) yields its own informational `deferred` line -- excluded from
# `findings` and from the exit-code decision, counted only in
# `summary["deferred"]`.
# ---------------------------------------------------------------------------


def test_rule_d_deferred_path_yields_deferred_line_not_a_finding(tmp_path):
    """A reference to a DEFERRED_PATHS-listed path (skills/live-testing) is
    neither shipped (not in include, not tracked) nor a real defect -- it
    surfaces as its own `deferred` line (still present in the raw
    `findings` JSON array and JSON-summarized), but contributes ZERO to the
    real finding count and never flips the exit code on its own: the
    `deferred` line is informational, filtered out of `real_findings`
    before the exit-code/count decision, not absent from `findings` itself.
    The base fixture is otherwise clean modulo rule (e)'s own vacuous
    empty-registry line (see test_clean_fixture_exits_0_with_no_findings
    for why a real repo must be registered to reach a genuinely empty
    overall findings list) -- so this test registers one non-colliding
    repo, exactly like that test, to isolate the deferred-path behavior
    from rule (e)'s unrelated noise."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product_d1", name="product_d1")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nSee also `skills/live-testing`.\n"
    )
    _commit_all(cdir)

    proc = _run(cdir)
    payload = _payload(proc)
    assert proc.returncode == 0
    assert any(f.startswith("deferred\tskills/live-testing\t") for f in payload["findings"])
    # every OTHER (non-informational) finding is absent -- the deferred line
    # is the only thing present, and it alone never flips exit code/count.
    non_informational = [
        f
        for f in payload["findings"]
        if not f.startswith("deferred\t") and not f.startswith("dangling\t")
    ]
    assert non_informational == []
    assert payload["summary"].get("deferred") == 1


def _raw_text_lines(cdir: Path) -> list[str]:
    """Re-run in default (non-JSON) text mode to confirm the `deferred` line
    itself is actually printed with the documented `rule<TAB>subject<TAB>
    detail` shape, not merely present in the JSON summary count."""
    env = dict(os.environ)
    env["CLAUDE_DIR"] = str(cdir)
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        cwd=str(cdir),
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return proc.stdout.splitlines()


def test_rule_d_deferred_path_line_has_documented_shape_in_text_mode(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product_d2", name="product_d2")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nSee also `skills/live-testing`.\n"
    )
    _commit_all(cdir)

    lines = _raw_text_lines(cdir)
    matches = [line for line in lines if line.startswith("deferred\tskills/live-testing\t")]
    assert matches, lines


def test_rule_d_deferred_path_recovers_once_removed_from_reference(tmp_path):
    """Pairs with the deferred-path case: remove the deferred reference
    entirely and the `deferred` line (and its summary count) disappear."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product_d3", name="product_d3")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nSee also `skills/live-testing`.\n"
    )
    _commit_all(cdir)
    bad = _payload(_run(cdir))
    assert bad["summary"].get("deferred") == 1

    original = (cdir / "agents" / "x.md").read_text().replace(
        "\nSee also `skills/live-testing`.\n", ""
    )
    (cdir / "agents" / "x.md").write_text(original)
    _commit_all(cdir, "remove deferred reference")
    good = _payload(_run(cdir))
    assert good.get("summary", {}).get("deferred", 0) == 0
    assert good["findings"] == []


# ---------------------------------------------------------------------------
# (d) dangling carve-out: a referenced skills/tools/scripts path that does
# not exist ANYWHERE on disk is a DIFFERENT defect from "exists but
# unshipped" -- it yields its own informational `dangling` line (still
# present in the raw `findings` JSON array, per `_INFORMATIONAL_TAGS`),
# never a `referenced-paths-shipped` finding, and is excluded from the
# real-finding COUNT and the exit-code decision (`main()`'s `real_findings`
# filter), same informational treatment as rule (d)'s `deferred` lines
# above and rule (g)'s own pre-existing dangling handling.
# ---------------------------------------------------------------------------


def test_rule_d_nonexistent_path_is_dangling_not_referenced_paths_shipped(tmp_path):
    """`dangling` stays IN the JSON `findings` array (and text mode),
    summary-counted, but is excluded from `real_findings`/the exit-code
    decision -- so a fixture with only a dangling reference (plus one
    registered, non-colliding repo to neutralize rule (e)'s unrelated
    vacuous line) still exits 0."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product_d4", name="product_d4")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nRun `scripts/ghost.py` for setup.\n"
    )
    _commit_all(cdir)

    proc = _run(cdir)
    payload = _payload(proc)
    assert proc.returncode == 0
    assert any(f.startswith("dangling\tscripts/ghost.py\t") for f in payload["findings"])
    non_informational = [
        f
        for f in payload["findings"]
        if not f.startswith("deferred\t") and not f.startswith("dangling\t")
    ]
    assert non_informational == []
    assert payload["summary"].get("dangling") == 1
    lines = _raw_text_lines(cdir)
    matches = [line for line in lines if line.startswith("dangling\tscripts/ghost.py\t")]
    assert matches, lines
    assert not any(
        line.startswith("referenced-paths-shipped\tscripts/ghost.py\t") for line in lines
    ), lines


def test_rule_d_dangling_path_recovers_once_created_included_and_committed(tmp_path):
    """Pairs with the dangling case: create the file, add it to include, and
    commit it -- the dangling line disappears and no
    referenced-paths-shipped finding ever appears in its place."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    _seed_registered_repo(tmp_path, cdir, "product_d5", name="product_d5")
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text() + "\nRun `scripts/ghost.py` for setup.\n"
    )
    _commit_all(cdir)
    bad = _payload(_run(cdir))
    assert bad["summary"].get("dangling") == 1

    (cdir / "scripts").mkdir(exist_ok=True)
    (cdir / "scripts" / "ghost.py").write_text("#!/usr/bin/env python3\nprint('hi')\n")
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"].append("scripts/ghost.py")
    config_path.write_text(json.dumps(config))
    _commit_all(cdir, "create + ship scripts/ghost.py")

    good = _payload(_run(cdir))
    assert good.get("summary", {}).get("dangling", 0) == 0
    assert not any("ghost.py" in f for f in good["findings"])


# ---------------------------------------------------------------------------
# (e) twin check -- name-collision scoped, direction-naming, worktrees,
#     empty registry, non-colliding repo-local skill is clean.
# ---------------------------------------------------------------------------


def _seed_registered_repo(tmp_path: Path, cdir: Path, slug: str, name: str = "product") -> Path:
    repo_root = tmp_path / name
    repo_root.mkdir()
    _git("init", "-q", cwd=repo_root)
    _git("config", "user.email", "t@example.com", cwd=repo_root)
    _git("config", "user.name", "t", cwd=repo_root)
    (repo_root / "README.md").write_text("seed\n")
    _git("add", "-A", cwd=repo_root)
    _git("commit", "-q", "-m", "seed", cwd=repo_root)

    registry_path = cdir / "knowledge" / "repo_registry.json"
    registry = json.loads(registry_path.read_text())
    registry.setdefault("repos", {})[slug] = {"root": str(repo_root)}
    registry_path.write_text(json.dumps(registry))
    _commit_all(cdir, f"register {slug}")
    return repo_root


def test_rule_e_repo_local_agent_twin_is_flagged_replaces_direction(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    repo_root = _seed_registered_repo(tmp_path, cdir, "product")
    twin_agents = repo_root / ".claude" / "agents"
    twin_agents.mkdir(parents=True)
    (twin_agents / "x.md").write_text(
        "---\nname: x\ndescription: shadow twin\nmodel: sonnet\ntools: Read\n---\nBody.\n"
    )
    _git("add", "-A", cwd=repo_root)
    _git("commit", "-q", "-m", "add twin", cwd=repo_root)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    matches = [f for f in findings if "x" in f and "agents" in f.lower()]
    assert matches, findings
    assert any("replace" in f.lower() for f in matches), matches


def test_rule_e_repo_local_skill_twin_is_flagged_dead_direction(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    repo_root = _seed_registered_repo(tmp_path, cdir, "product2", name="product2")
    twin_skills = repo_root / ".claude" / "skills" / "foo"
    twin_skills.mkdir(parents=True)
    (twin_skills / "SKILL.md").write_text("---\nname: foo\ndescription: x\n---\nBody.\n")
    _git("add", "-A", cwd=repo_root)
    _git("commit", "-q", "-m", "add twin skill", cwd=repo_root)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    matches = [f for f in findings if "foo" in f and "skill" in f.lower()]
    assert matches, findings
    assert any("dead" in f.lower() for f in matches), matches


def test_rule_e_non_colliding_repo_local_skill_is_clean(tmp_path):
    """A repo-local skills/bar/ with no same-named runtime skill must never
    be flagged -- the rule is collision-only."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    repo_root = _seed_registered_repo(tmp_path, cdir, "product3", name="product3")
    non_colliding = repo_root / ".claude" / "skills" / "bar"
    non_colliding.mkdir(parents=True)
    (non_colliding / "SKILL.md").write_text("---\nname: bar\ndescription: x\n---\nBody.\n")
    _git("add", "-A", cwd=repo_root)
    _git("commit", "-q", "-m", "add non-colliding skill", cwd=repo_root)

    proc = _run(cdir)
    findings = _findings(proc)
    assert not any("bar" in f for f in findings), findings


def test_rule_e_empty_registry_reports_no_repos_registered(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    # registry is already empty ({"schema_version": 1, "repos": {}}) per the
    # fixture builder -- assert the summary states it explicitly, vacuously.
    proc = _run(cdir, "--verbose")
    combined = proc.stdout + proc.stderr
    assert "no repos registered" in combined.lower()


def test_rule_e_worktree_twin_is_also_flagged(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    repo_root = _seed_registered_repo(tmp_path, cdir, "product4", name="product4")
    worktree_agents = repo_root / ".claude" / "worktrees" / "w1" / ".claude" / "agents"
    worktree_agents.mkdir(parents=True)
    (worktree_agents / "x.md").write_text(
        "---\nname: x\ndescription: stale worktree twin\nmodel: sonnet\ntools: Read\n---\nBody.\n"
    )
    # Worktree contents need not be committed to the main repo for this rule
    # to see them -- it scans the filesystem path directly per the plan text
    # ("scans <root>/.claude/worktrees/*/.claude/{agents,skills} too").

    proc = _run(cdir)
    findings = _findings(proc)
    assert any("worktree" in f.lower() and "x" in f for f in findings), findings


# ---------------------------------------------------------------------------
# (f) mirror-clone README agent count vs. real agent count; fail-open when
#     no local clone exists.
# ---------------------------------------------------------------------------


def test_rule_f_readme_count_matches_agent_count_is_clean(tmp_path):
    """The fixture's clone README says '3 agents' and there are exactly 3
    agent files (x, y, trading-strategist) -- clean."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    proc = _run(cdir)
    findings = _findings(proc)
    assert not any("readme" in f.lower() and "agent" in f.lower() for f in findings), findings


def test_rule_f_wrong_readme_count_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config = json.loads((cdir / ".mirror" / "config.json").read_text())
    clone_dir = Path(config["clone_dir"])
    (clone_dir / "README.md").write_text("This bundle ships 20 agents.\n")

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("readme" in f.lower() and "agent" in f.lower() for f in findings), findings


def test_rule_f_no_clone_dir_is_fail_open_no_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["clone_dir"] = str(Path(config["clone_dir"]).parent / "does_not_exist_at_all")
    config_path.write_text(json.dumps(config))
    _commit_all(cdir)

    proc = _run(cdir)
    # NOT a bare exit-0 assertion: the base fixture's empty repo_registry.json
    # always contributes its own vacuous twin-check finding (rule (e)),
    # unrelated to rule (f) -- the load-bearing assertion here is that a
    # missing clone_dir never produces a readme-count finding of its own.
    assert not any("readme" in f.lower() for f in _findings(proc))


# ---------------------------------------------------------------------------
# (g) knowledge/ reference completeness -- ships (include+tracked) or has a
#     templates/knowledge/<path> seed; a nonexistent reference is `dangling`,
#     never a knowledge-referenced-ships finding.
# ---------------------------------------------------------------------------


def test_rule_g_reference_removed_from_include_is_a_finding(tmp_path):
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"] = [p for p in config["include"] if p != "knowledge/ref.md"]
    config_path.write_text(json.dumps(config))
    _commit_all(cdir)

    proc = _run(cdir)
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("knowledge/ref.md" in f for f in findings), findings
    # never mislabeled as dangling -- the file genuinely exists, just unshipped
    assert not any("dangling" in f and "knowledge/ref.md" in f for f in findings), findings


def test_rule_g_recovers_via_templates_knowledge_seed(tmp_path):
    """Pairs with the removed-from-include case: providing a
    templates/knowledge/ref.md seed satisfies the rule without re-adding
    ref.md to include."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config = json.loads(config_path.read_text())
    config["include"] = [p for p in config["include"] if p != "knowledge/ref.md"]
    config_path.write_text(json.dumps(config))
    _commit_all(cdir)
    bad = _run(cdir)
    assert any("knowledge/ref.md" in f for f in _findings(bad))

    (cdir / "templates" / "knowledge" / "ref.md").write_text("# seed\n")
    _commit_all(cdir, "seed ref.md")
    good = _run(cdir)
    assert not any(
        "knowledge/ref.md" in f and "seed" not in f.lower() for f in _findings(good)
    ) or good.returncode == 0


def test_rule_g_reference_to_nonexistent_knowledge_path_is_dangling_not_ships(tmp_path):
    """`dangling` lines stay IN the JSON `findings` array (and text mode),
    summary-counted, but are excluded from `real_findings`/the exit-code
    decision (`_is_informational`). The load-bearing assertion is that the
    line is tagged `dangling`, never `knowledge-referenced-ships`, for this
    path."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    (cdir / "agents" / "x.md").write_text(
        (cdir / "agents" / "x.md").read_text()
        + "\nSee also `knowledge/ghost.md` for more.\n"
    )
    _commit_all(cdir)

    proc = _run(cdir)
    combined_findings = _findings(proc)
    dangling_hits = [f for f in combined_findings if "ghost.md" in f]
    assert dangling_hits, combined_findings
    assert all("dangling" in f for f in dangling_hits), dangling_hits
    assert not any(
        "knowledge-referenced-ships" in f and "ghost.md" in f for f in combined_findings
    ), combined_findings


# ---------------------------------------------------------------------------
# I/O error handling: every rule wraps its own body in a broad exception
# handler that turns a crash into a single `rule-error\t<rule>\t<detail>`
# line rather than raising out -- the module's own stated design
# constraint (docstring: "check() never raises; every rule below degrades
# to a single rule-error line on its own I/O failure rather than crashing
# the whole report"). Malformed input degrades in one of two equally
# fail-open ways depending on WHERE it's caught: `_load_mirror_config`
# itself never raises (invalid JSON -> None -> include=[]), so a malformed
# `.mirror/config.json` is absorbed silently rather than producing a
# `rule-error` line -- proven directly below. The broader
# `try/except Exception` in every `check_*` function (and the wrapping
# `try/except` around each in `check()`) is what actually PRODUCES a
# `rule-error` line, and is proven never to crash even under a genuinely
# malformed registry.
# ---------------------------------------------------------------------------


def test_malformed_mirror_config_degrades_to_empty_include_never_crashes(tmp_path):
    """A malformed `.mirror/config.json` (`_load_mirror_config` returns None
    on a JSON parse failure) must never crash the run and must never emit a
    traceback -- it degrades to an empty `include` list, so every rule that
    consults `include` behaves exactly as it would with `include: []`
    (proven here by rule (a): the primer reference is unshippable with an
    empty include, so primer-shipped fires -- the SAME finding shape as the
    explicit drop-from-include case in rule (a)'s own tests, confirming the
    degradation is real fail-open behavior, not a crash)."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    config_path = cdir / ".mirror" / "config.json"
    config_path.write_text("{ not valid json at all")
    _commit_all(cdir)

    proc = _run(cdir)
    assert "Traceback (most recent call last)" not in proc.stderr
    assert proc.returncode == 1
    findings = _findings(proc)
    assert any("primer-shipped" in f and "x_primer.md" in f for f in findings), findings


def test_malformed_repo_registry_yields_no_traceback_and_deterministic_exit(tmp_path):
    """A `knowledge/repo_registry.json` whose `repos` value is the wrong
    shape (a list instead of an object) is guarded explicitly inside
    `_load_repo_registry_roots` (`isinstance(repos, dict)`), so it degrades
    to the same "no repos registered" vacuous line as a genuinely empty
    registry -- never a crash, never a traceback, and the exit code stays
    deterministic (0 or 1, never a nonzero-from-uncaught-exception)."""
    _skip_if_absent()
    cdir = _init_scratch_claude_dir(tmp_path)
    registry_path = cdir / "knowledge" / "repo_registry.json"
    registry_path.write_text(json.dumps({"schema_version": 1, "repos": ["not", "a", "dict"]}))
    _commit_all(cdir)

    proc = _run(cdir)
    assert "Traceback (most recent call last)" not in proc.stderr
    assert proc.returncode in (0, 1)
    findings = _findings(proc)
    assert any("no repos registered" in f.lower() for f in findings), findings


def test_never_touches_the_real_home_claude_dir(tmp_path):
    """Sanity/isolation proof: running against the scratch CLAUDE_DIR must
    never write into the real ~/.claude tree. We assert this by recording
    the real tree's mtime-independent file list is unaffected -- simplest
    reliable proxy is that the real .mirror/config.json (if present) is
    byte-identical before and after a scratch run."""
    _skip_if_absent()
    real_mirror_config = Path.home() / ".claude" / ".mirror" / "config.json"
    if not real_mirror_config.exists():
        pytest.skip("no real ~/.claude/.mirror/config.json on this machine")
    before = real_mirror_config.read_bytes()
    cdir = _init_scratch_claude_dir(tmp_path)
    _run(cdir)
    after = real_mirror_config.read_bytes()
    assert before == after
