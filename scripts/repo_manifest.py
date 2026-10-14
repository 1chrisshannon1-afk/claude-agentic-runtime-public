#!/usr/bin/env python3
"""repo_manifest — the one reader for a product repo's `.claude/oversight/manifest.json`.

WHY THIS EXISTS
----------------
`runtime_bundle_repo_agnostic_plan.md` §2/§WS2 (H11): per-repo configuration used
to be split across three places with no single owner -- `knowledge/repo_registry.json`
(one consumer, `agentarch_metric_check.py`), `knowledge/wheel_repos.json` (THE ISSUE
WHEEL's per-slug config), and free-standing prose scattered across oversight dossiers.
This module is the consolidation: `<repo>/.claude/oversight/manifest.json` is the one
machine-readable answer to "where is X in this repo", and this script is the only
program that reads or writes it. `get`/`validate`/`register`/`doctor` are the four
verbs a prompt, hook, or agent ever needs.

DATA CLASSES
------------
`knowledge/repo_registry.json` is MACHINE-LOCAL and `mirror_managed` (the runtime
mirror publishes it EMPTY by design -- one machine's repo layout is not portable
content). `register` below writes only the LOCAL file at `<CLAUDE_DIR>/knowledge/
repo_registry.json`; it never touches, and has no way to touch, whatever the mirror
clone happens to carry.

`knowledge/wheel_repos.json` is genuinely portable runtime config (THE ISSUE WHEEL's
per-slug tuning) generated FROM each repo's manifest.json's own `wheel` block, but
still a real file this script keeps in sync via `register`.

USAGE
-----
    repo_manifest.py get <dotted.key> [--repo PATH] [--raw]
    repo_manifest.py validate [--repo PATH]
    repo_manifest.py register [--repo PATH]
    repo_manifest.py doctor [--repo PATH]

`--repo PATH` overrides the default resolution (`git rev-parse --show-toplevel` from
the caller's cwd). `CLAUDE_DIR` (env) overrides the runtime root (default `~/.claude`).
`get` returns a PATH-TYPED KEY's value (see `_PATH_KEYS`) anchored to the resolved repo
root as an absolute path, since the manifest stores it repo-relative and a repo-relative
value otherwise resolves against the caller's cwd, not the repo; `--raw` prints the
stored (repo-relative) value instead. Doctor rule D1's own restatement check reads these
same keys directly (never through `cmd_get`), so it keeps comparing the raw, repo-relative
value a dossier would actually cite -- this anchoring is unrelated to, and does not
change, D1's behavior.

DOCTOR RULE D1 (`restates-manifest:<key>`) only scans prose: it exempts fenced code
blocks entirely, exempts an inline code span whose content is a runnable command
(starts with a token like `grep`/`git`/`gh`/etc.), exempts an inline code span whose
content is a shell variable ASSIGNMENT restricted to SCREAMING_SNAKE_CASE
(`^[A-Z][A-Z0-9_]*=`, e.g. `` `GH_PROJECT_OWNER=example-org` ``) -- a re-derive
idiom exactly like a command span, just spelled as an assignment instead of an
invocation; this is deliberately narrower than "any identifier followed by `=`" (a
lowercase `tracker=docs/x.html`-shaped span is NOT an assignment idiom in this repo's
prose -- it is exactly the bare-value restatement D1 exists to catch, and every live
assignment-span instance in this repo's dossiers is already SCREAMING_SNAKE, e.g.
`GH_PROJECT_OWNER=...`) -- exempts any `https?://` URL token BEFORE span-splitting even
runs (a bare backticked URL is stripped by the same URL-removal pass, so it never
reaches span validation at all, whether or not it sits inside backticks or a markdown
link target), since a link is a citation to the real value, not a restatement of it,
and applies both of the command/assignment span exemptions to a span whose content
LINE-WRAPS across MULTIPLE embedded newlines (a CommonMark-legal inline span, e.g. a
long `` `gh project list --owner X` `` command wrapped across several source lines,
up to `_SPAN_MAX_NEWLINES` of them and `_SPAN_MAX_CHARS` characters) -- a blank line
still breaks a span, and so does any line inside the span (other than the span's own
first line) that starts, after optional leading whitespace, with a markdown block
marker (`- `, `* `, `+ `, an ordinal list marker, `#`, `>`, or `|`) that isn't part of
the command text -- CommonMark itself doesn't require this, but a genuine runnable
command never legitimately begins a *later* physical line with a bullet/heading/quote
marker, and a candidate span that does is almost always an unclosed backtick that
swallowed real prose, not a real multi-line span; that candidate is rejected as a span
entirely (its opening backtick is a lone backtick, not a span start) and the scan
resumes from the character right after it, so an unclosed backtick can never swallow
unbounded prose bounded only by a distant matching backtick. An unclosed backtick with
no matching close never matches at all. A bare path/value in backticks with no command
token and no assignment shape is still a restatement and still flags. It scans `tracker_doc`,
`operator_input.path`, `operator_input.open_path`, `operator_input.regen_command`,
`gtm.missions_dir`, `github.repo`, `github.project_owner`, `gtm.inbox_label`, and
`oversight.report_dir` (the last compared AFTER `${slug}`/`~` expansion, since that's
what a dossier would restate) -- every manifest string field a dossier could plausibly
copy-paste rather than defer to the manifest for. `product.name` is deliberately
excluded: it legitimately appears in ordinary prose ("ExampleApp AI does X"),
so treating it as a restatement would false-positive on nearly every dossier.

`${slug}` IS A GENERAL EXPANSION MECHANISM, not special to `oversight.report_dir`:
`cmd_get` expands `${slug}` (and `~`) in *any* string value it returns, so a manifest
author can use `${slug}` in any field a caller reads via `get`.

DOCTOR `missing-dossier` (an agent's text names an `oversight/<agent>.md` dossier path
it does not actually have on disk) is opted OUT of by an agent whose own text carries
the sanctioned phrase -- case-insensitive, may line-wrap -- "No per-agent ...
oversight/<agent>.md ... expected" (or "... required"), e.g. design-reviewer's own
"No per-agent `<repo>/.claude/oversight/design-reviewer.md` dossier is expected in any
repo" sentence, which names its own dossier path only to explain why it doesn't have
one. See `_has_no_dossier_opt_out`. `doctor` still checks `dev-runtime.md` separately
whenever an agent references it, regardless of this opt-out.

DOCTOR RULE D2 (`bundle_version\ttemplate-outdated` / `bundle_version\tunreadable`)
validates `.bundle_version`'s content is a plain hex git sha (`^[0-9a-f]{7,40}$`)
BEFORE it is ever passed to `git diff` as a revision -- an unvalidated value there is
attacker-controlled input to a subprocess argument (e.g. a value shaped like an option
flag), so validation happens first and unconditionally, and the revision range is
additionally passed after `--end-of-options` (requires git >= 2.24; this repo's git is
newer, so no version-detection fallback is implemented -- if this script must ever run
against git < 2.24, the sha-shape validation above is still the sole guard and this
comment should be revisited).
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator

SCHEMA_VERSION = 1
SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
GITHUB_REPO_RE = re.compile(r"^[^/\s]+/[^/\s]+$")
PLACEHOLDER_RE = re.compile(r"__[A-Z][A-Z0-9_]*__")


def _claude_dir() -> Path:
    raw = os.environ.get("CLAUDE_DIR")
    if raw:
        return Path(raw).expanduser()
    return Path("~/.claude").expanduser()


def _resolve_repo(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        print("not-a-repo", file=sys.stderr)
        sys.exit(3)
    path = out.stdout.strip()
    if not path:
        print("not-a-repo", file=sys.stderr)
        sys.exit(3)
    return Path(path)


def _manifest_path(repo: Path) -> Path:
    return repo / ".claude" / "oversight" / "manifest.json"


def _load_manifest(repo: Path) -> dict[str, Any]:
    """Load and parse the manifest, or exit 3/4 per the get/validate/doctor contract."""
    mpath = _manifest_path(repo)
    if not mpath.is_file():
        print(f"manifest-missing: {mpath}", file=sys.stderr)
        sys.exit(3)
    try:
        text = mpath.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"manifest-invalid: {exc}", file=sys.stderr)
        sys.exit(4)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"manifest-invalid: {exc}", file=sys.stderr)
        sys.exit(4)
    if not isinstance(data, dict):
        print("manifest-invalid: top-level value is not an object", file=sys.stderr)
        sys.exit(4)
    return data


def _dig(data: dict[str, Any], dotted_key: str) -> Any:
    """Walk a dotted key through nested dicts; raise KeyError on any missing segment."""
    current: Any = data
    for segment in dotted_key.split("."):
        if not isinstance(current, dict) or segment not in current:
            raise KeyError(dotted_key)
        current = current[segment]
    return current


def _expand_manifest_value(value: str, slug: str | None) -> str:
    """Expand `~` and `${slug}` in a manifest string value, exactly as `cmd_get` returns it
    to a caller. `${slug}` is a general expansion mechanism available in ANY string value
    read from the manifest, not special-cased to one key."""
    expanded = os.path.expanduser(value)
    if slug is not None:
        expanded = expanded.replace("${slug}", str(slug))
    return expanded


# Manifest keys whose value is a path stored REPO-RELATIVE (the natural way to author and
# commit them, and how D1 must keep comparing them -- a dossier cites the relative path, not
# an absolute one). `get` anchors these to the resolved repo root before printing, because a
# repo-relative string resolves against the CALLER's cwd otherwise, which is wrong the moment
# a consumer runs from any directory other than the repo root. `oversight.report_dir` is
# EXCLUDED here: it is `~`-anchored (or `${slug}`-templated), already independent of the
# repo's location, so anchoring it to the repo root would be wrong, not merely redundant.
# NOTE -- `wheel.venv_python` is returned ABSOLUTE by `get` (like every other key here), but
# `register` writes it into `wheel_repos.json` REPO-RELATIVE exactly as stored in the
# manifest -- THE ISSUE WHEEL reads that file directly, never through `cmd_get`, so it never
# sees the absolute form this set produces for a `get` caller.
_PATH_KEYS = frozenset(
    {
        "tracker_doc",
        "operator_input.path",
        "operator_input.open_path",
        "gtm.missions_dir",
        "wheel.venv_python",
    }
)


# ---------------------------------------------------------------------------
# get
# ---------------------------------------------------------------------------


def cmd_get(repo: Path, dotted_key: str, raw: bool = False) -> None:
    data = _load_manifest(repo)
    try:
        value = _dig(data, dotted_key)
    except KeyError:
        print(f"key-missing: {dotted_key}", file=sys.stderr)
        sys.exit(3)

    slug = None
    product = data.get("product")
    if isinstance(product, dict):
        slug = product.get("slug")

    if isinstance(value, str):
        expanded = _expand_manifest_value(value, slug)
        if not raw and dotted_key in _PATH_KEYS and expanded and not os.path.isabs(expanded):
            # os.path.normpath (never Path.resolve()) anchors a repo-relative value to the repo
            # root WITHOUT following symlinks -- resolve() would rewrite e.g. `.venv/bin/python`
            # (a symlink to a real interpreter binary, possibly outside the venv entirely, such
            # as the Homebrew-installed system Python) to its resolved target, silently returning
            # an interpreter outside the venv the caller asked for. The documented intent of this
            # anchoring step is only "make a repo-relative value absolute," which normpath alone
            # satisfies.
            expanded = os.path.normpath(str(repo / expanded))
        print(expanded)
    else:
        print(json.dumps(value))


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def _violations(repo: Path, data: dict[str, Any]) -> Iterator[str]:
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        yield f"INVALID schema_version: must be {SCHEMA_VERSION}, got {schema_version!r}"

    product = data.get("product")
    if not isinstance(product, dict):
        yield "INVALID product: missing or not an object"
    else:
        name = product.get("name")
        if not isinstance(name, str) or not name:
            yield "INVALID product.name: required string"
        slug = product.get("slug")
        if not isinstance(slug, str) or not SLUG_RE.match(slug or ""):
            yield "INVALID product.slug: must match ^[a-z][a-z0-9-]{1,31}$"

    github = data.get("github")
    if not isinstance(github, dict):
        yield "INVALID github: missing or not an object"
    else:
        gh_repo = github.get("repo")
        if not isinstance(gh_repo, str) or not GITHUB_REPO_RE.match(gh_repo or ""):
            yield "INVALID github.repo: must match ^[^/\\s]+/[^/\\s]+$"
        if "project_number" in github and github["project_number"] is not None:
            if not isinstance(github["project_number"], int) or isinstance(
                github["project_number"], bool
            ):
                yield "INVALID github.project_number: must be an int"
        if "project_owner" in github and github["project_owner"] is not None:
            if not isinstance(github["project_owner"], str):
                yield "INVALID github.project_owner: must be a string"

    gtm = data.get("gtm")
    if not isinstance(gtm, dict):
        yield "INVALID gtm: missing or not an object"
    else:
        missions_dir = gtm.get("missions_dir")
        if not isinstance(missions_dir, str) or not missions_dir:
            yield "INVALID gtm.missions_dir: required string"
        elif not (repo / missions_dir).is_dir():
            yield f"INVALID gtm.missions_dir: not an existing directory: {missions_dir}"
        inbox_label = gtm.get("inbox_label")
        if not isinstance(inbox_label, str) or not inbox_label:
            yield "INVALID gtm.inbox_label: required string"

    if "tracker_doc" in data and data["tracker_doc"] is not None:
        tracker_doc = data["tracker_doc"]
        if not isinstance(tracker_doc, str):
            yield "INVALID tracker_doc: must be a string or null"
        elif not (repo / tracker_doc).is_file():
            yield f"INVALID tracker_doc: not an existing file: {tracker_doc}"

    if "operator_input" in data and data["operator_input"] is not None:
        oi = data["operator_input"]
        if not isinstance(oi, dict):
            yield "INVALID operator_input: must be an object or null"
        else:
            kind = oi.get("kind")
            if not isinstance(kind, str) or not kind:
                yield "INVALID operator_input.kind: required string"
            path = oi.get("path")
            if not isinstance(path, str) or not path:
                yield "INVALID operator_input.path: required string"
            elif not (repo / path).is_file():
                yield f"INVALID operator_input.path: not an existing file: {path}"
            for optional_key in ("regen_command", "open_path"):
                if optional_key in oi and oi[optional_key] is not None:
                    if not isinstance(oi[optional_key], str):
                        yield f"INVALID operator_input.{optional_key}: must be a string"
                    elif optional_key == "open_path" and not (repo / oi[optional_key]).is_file():
                        yield (
                            f"INVALID operator_input.open_path: not an existing file: "
                            f"{oi[optional_key]}"
                        )

    if "wheel" in data and data["wheel"] is not None:
        wheel = data["wheel"]
        if not isinstance(wheel, dict):
            yield "INVALID wheel: must be an object"
        else:
            venv_python = wheel.get("venv_python")
            if venv_python is not None:
                if not isinstance(venv_python, str):
                    yield "INVALID wheel.venv_python: must be a string"
                elif not (repo / venv_python).exists():
                    yield f"INVALID wheel.venv_python: not an existing path: {venv_python}"

    security = data.get("security")
    if security is not None:
        if not isinstance(security, dict):
            yield "INVALID security: must be an object"
        else:
            for key in ("auth_cookie_names", "extra_risk_keywords"):
                if key in security and security[key] is not None:
                    val = security[key]
                    if not isinstance(val, list) or not all(isinstance(i, str) for i in val):
                        yield f"INVALID security.{key}: must be a list of strings"

    oversight = data.get("oversight")
    if oversight is not None:
        if not isinstance(oversight, dict):
            yield "INVALID oversight: must be an object"
        else:
            if "tracking_issue" in oversight and oversight["tracking_issue"] is not None:
                ti = oversight["tracking_issue"]
                if not isinstance(ti, int) or isinstance(ti, bool):
                    yield "INVALID oversight.tracking_issue: must be an int or null"
            report_dir = oversight.get("report_dir")
            if report_dir is not None and not isinstance(report_dir, str):
                yield "INVALID oversight.report_dir: must be a string"


def cmd_validate(repo: Path) -> None:
    data = _load_manifest(repo)
    violations = list(_violations(repo, data))
    if not violations:
        print("OK")
        sys.exit(0)
    for line in violations:
        print(line)
    sys.exit(2)


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------


def _home_relative(path: Path) -> str:
    home = str(Path.home())
    raw = str(path)
    if raw == home:
        return "~"
    if raw.startswith(home + os.sep):
        return "~" + raw[len(home) :]
    return raw


def _write_json_if_changed(path: Path, data: dict[str, Any]) -> bool:
    """Write `data` as pretty JSON with a trailing newline; return True if content changed.

    Writes atomically: content lands in a same-directory `.tmp` sibling, fsync'd, then
    `os.replace`d over the real path -- so a crash or interrupt mid-write can never leave
    `path` truncated or partially written. Both `repo_registry.json` and `wheel_repos.json`
    (this function's only two callers) are read by unattended jobs that would otherwise be
    reading a corrupt file with no signal that anything went wrong.
    """
    new_text = json.dumps(data, indent=2, sort_keys=False, ensure_ascii=False) + "\n"
    if path.is_file():
        try:
            old_text = path.read_text(encoding="utf-8")
        except OSError:
            old_text = None
        if old_text == new_text:
            return False
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        with open(tmp_path, "w", encoding="utf-8") as fh:
            fh.write(new_text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_path, path)
    finally:
        tmp_path.unlink(missing_ok=True)
    return True


def _register_registry(claude_dir: Path, repo: Path, slug: str) -> None:
    registry_path = claude_dir / "knowledge" / "repo_registry.json"
    if registry_path.is_file():
        try:
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            registry = {"schema_version": 1, "repos": {}}
    else:
        registry = {"schema_version": 1, "repos": {}}
    registry.setdefault("schema_version", 1)
    repos = registry.setdefault("repos", {})

    root_value = _home_relative(repo)

    for other_slug, entry in repos.items():
        if other_slug == slug:
            continue
        if isinstance(entry, dict) and entry.get("root") == root_value:
            print(f"registry-alias: {other_slug} shares this root")

    repos[slug] = {"root": root_value}

    changed = _write_json_if_changed(registry_path, registry)
    print(f"{'updated' if changed else 'unchanged'} {registry_path}")


def _register_wheel(claude_dir: Path, slug: str, wheel_block: Any) -> None:
    wheel_path = claude_dir / "knowledge" / "wheel_repos.json"
    if wheel_path.is_file():
        try:
            wheel_repos = json.loads(wheel_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            wheel_repos = {}
    else:
        wheel_repos = {}
    wheel_repos[slug] = wheel_block

    changed = _write_json_if_changed(wheel_path, wheel_repos)
    print(f"{'updated' if changed else 'unchanged'} {wheel_path}")


def _register_label(github_repo: str, inbox_label: str) -> None:
    gh_path = shutil.which("gh")
    if gh_path is None:
        print("label-skipped: gh not on PATH")
        return
    try:
        list_result = subprocess.run(
            [
                "gh",
                "label",
                "list",
                "--repo",
                github_repo,
                "--json",
                "name",
                "--limit",
                "1000",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"label-skipped: gh label list failed: {exc}")
        return
    if list_result.returncode != 0:
        print(f"label-skipped: gh label list failed: {list_result.stderr.strip()}")
        return
    try:
        existing = json.loads(list_result.stdout or "[]")
        names = {item.get("name") for item in existing if isinstance(item, dict)}
    except json.JSONDecodeError as exc:
        print(f"label-skipped: gh label list returned invalid JSON: {exc}")
        return
    if inbox_label in names:
        print("label-exists")
        return
    try:
        create_result = subprocess.run(
            [
                "gh",
                "label",
                "create",
                inbox_label,
                "--repo",
                github_repo,
                "--color",
                "5319E7",
                "--description",
                "department inbox (runtime bundle)",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"label-skipped: gh label create failed: {exc}")
        return
    if create_result.returncode != 0:
        print(f"label-skipped: gh label create failed: {create_result.stderr.strip()}")
        return
    print("label-created")


def cmd_register(repo: Path, claude_dir: Path) -> None:
    data = _load_manifest(repo)
    violations = list(_violations(repo, data))
    if violations:
        for line in violations:
            print(line)
        sys.exit(2)

    slug = data["product"]["slug"]

    _register_registry(claude_dir, repo, slug)

    wheel_block = data.get("wheel")
    if wheel_block is not None:
        _register_wheel(claude_dir, slug, wheel_block)

    github_repo = data["github"]["repo"]
    inbox_label = data["gtm"]["inbox_label"]
    _register_label(github_repo, inbox_label)


# ---------------------------------------------------------------------------
# doctor
# ---------------------------------------------------------------------------

_DEV_RUNTIME_TOKEN = "oversight/dev-runtime.md"
_SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")


def _has_no_dossier_opt_out(agent_text: str, agent_name: str) -> bool:
    """True when an agent's own text declares -- in the sanctioned phrasing -- that no
    per-agent `<repo>/.claude/oversight/<agent_name>.md` dossier is expected for it (e.g.
    design-reviewer's sole repo-local grounding is a `dev-runtime.md` section, not a
    per-agent dossier). The sanctioned opt-out phrase is a `No per-agent ... oversight/
    <agent>.md ... dossier ... is/are expected` (or `required`) SENTENCE, case-insensitive;
    the gaps allow the phrase to line-wrap across the agent file's prose (as it does in
    practice) while still requiring "dossier" and "is/are expected|required" to land in the
    SAME sentence as the dossier path -- each gap is bounded both by a max length and by a
    negative lookahead that refuses to cross a period-then-whitespace (a genuine sentence
    break), so an unrelated LATER sentence's "... dossier is required" can never satisfy this
    pattern just because some earlier, unrelated sentence in the same paragraph happened to
    mention this agent's dossier path (e.g. "No per-agent overrides are allowed. Read
    `.claude/oversight/sentinel.md` -- it is required." must NOT match: "dossier" never
    appears in that sentence at all, and even if it had, the sentence break after the first
    "allowed." would still stop the gap from reaching it). A literal `.` inside the dossier
    path itself (`.claude/oversight/<agent>.md`) is not a sentence break -- only `.` followed
    by whitespace is -- so the real, path-bearing sentence still matches in full."""
    no_sentence_break = r"(?:(?!\.\s)[\s\S])"
    pattern = re.compile(
        r"no per-agent"
        + no_sentence_break
        + r"{0,60}?oversight/"
        + re.escape(agent_name)
        + r"\.md"
        + no_sentence_break
        + r"{0,60}?dossier"
        + no_sentence_break
        + r"{0,40}?\b(?:is|are)\s+(?:expected|required)",
        re.IGNORECASE,
    )
    return pattern.search(agent_text) is not None


def _agent_dossier_target(agent_text: str, agent_name: str) -> str | None:
    """Return the dossier basename this agent's text says it reads, or None. An agent
    that carries the sanctioned "no dossier expected" opt-out phrase (see
    `_has_no_dossier_opt_out`) never requires this dossier, even though its text also
    names the `oversight/<agent_name>.md` path (to explain why it doesn't have one)."""
    token = f"oversight/{agent_name}.md"
    if token not in agent_text:
        return None
    if _has_no_dossier_opt_out(agent_text, agent_name):
        return None
    return f"{agent_name}.md"


def _find_placeholders(text: str) -> int:
    return len(PLACEHOLDER_RE.findall(text))


def _doctor_dossiers(claude_dir: Path, repo: Path) -> Iterator[str]:
    agents_dir = claude_dir / "agents"
    oversight_dir = repo / ".claude" / "oversight"
    dev_runtime_checked = False

    if not agents_dir.is_dir():
        return

    for agent_path in sorted(agents_dir.glob("*.md")):
        agent_name = agent_path.stem
        if agent_name == "trading-strategist":
            continue
        try:
            agent_text = agent_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        dossier_basename = _agent_dossier_target(agent_text, agent_name)
        if dossier_basename is not None:
            dossier_path = oversight_dir / dossier_basename
            if not dossier_path.is_file():
                yield f"{agent_name}\tmissing-dossier"
            else:
                try:
                    dossier_text = dossier_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    dossier_text = ""
                count = _find_placeholders(dossier_text)
                if count:
                    yield f"{agent_name}\tplaceholder-left:{count}"

        if _DEV_RUNTIME_TOKEN in agent_text and not dev_runtime_checked:
            dev_runtime_checked = True
            dr_path = oversight_dir / "dev-runtime.md"
            if not dr_path.is_file():
                yield "dev-runtime\tmissing-dossier"
            else:
                try:
                    dr_text = dr_path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    dr_text = ""
                count = _find_placeholders(dr_text)
                if count:
                    yield f"dev-runtime\tplaceholder-left:{count}"


_D1_MIN_LEN = 8
_D1_KEYS = (
    "tracker_doc",
    "operator_input.path",
    "operator_input.open_path",
    "operator_input.regen_command",
    "gtm.missions_dir",
    "github.repo",
    "github.project_owner",
    "gtm.inbox_label",
    "oversight.report_dir",
)

_FENCED_BLOCK_RE = re.compile(r"^([ \t]*)(```|~~~)[^\n]*\n.*?\n\1\2[ \t]*$", re.DOTALL | re.MULTILINE)
# A CANDIDATE span is the shortest run between two backticks (DOTALL, non-greedy) -- this
# is deliberately permissive at the regex level; every real constraint on whether a
# candidate is actually treated as a span lives in `_is_valid_multiline_span_candidate`
# below, run as a POST-MATCH validation rather than folded into one giant regex, so the
# scan below stays linear: a rejected candidate's opening backtick is treated as a lone
# backtick (never a span start) and the scan resumes from the character right after it --
# so an unclosed/mismatched backtick can never swallow prose bounded only by some distant,
# unrelated backtick later in the document (the runaway-swallow failure mode this replaces).
_LONE_BACKTICK_CANDIDATE_RE = re.compile(r"`([^`]*)`", re.DOTALL)
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n")
# A line (other than the candidate's own first line) that opens -- after optional leading
# whitespace -- with one of these markdown block starters ends the candidate: a genuine
# runnable command never legitimately begins a LATER physical line with a bullet, heading,
# blockquote, or table-row marker, so a candidate that does is almost always an unclosed
# backtick that swallowed real document structure, not a real multi-line span.
_BLOCK_STARTER_RE = re.compile(r"^[ \t]*(?:[-*+]\s|\d+\.\s|#|>|\|)")
_SPAN_MAX_NEWLINES = 12
_SPAN_MAX_CHARS = 2000
# Excludes a trailing backtick as well as `)`/`]`/`>` -- a backticked URL span
# (`` `https://x.io/a` ``) would otherwise have its URL match consume the closing backtick along
# with the URL itself, leaving an unbalanced opening backtick that then pairs with a LATER,
# unrelated backtick further down the document -- silently hiding real prose between them from D1
# (the exact runaway-swallow failure mode the span guard above exists to prevent, reintroduced one
# layer earlier by this URL-stripping pass, which runs BEFORE span matching).
_URL_RE = re.compile(r"https?://[^\s)\]>`]+")
_ASSIGNMENT_SPAN_RE = re.compile(r"^[A-Z][A-Z0-9_]*=")
_COMMAND_TOKENS = frozenset(
    {
        "grep",
        "rg",
        "gh",
        "git",
        "python3",
        "python",
        "ls",
        "cat",
        "jq",
        "awk",
        "sed",
        "find",
        "wc",
        "open",
        "curl",
        "head",
        "tail",
        "sort",
        "diff",
    }
)


def _is_command_span(span_text: str) -> bool:
    """True when an inline code span's content is a runnable command (its first
    whitespace-separated token is a known command name) or a shell variable
    ASSIGNMENT restricted to SCREAMING_SNAKE_CASE (`^[A-Z][A-Z0-9_]*=`, e.g.
    `` `GH_PROJECT_OWNER=...` `` -- a re-derive idiom exactly like a command span,
    just spelled as an assignment rather than an invocation; a lowercase
    `tracker=docs/x.html`-shaped span is deliberately NOT matched here -- see the
    module docstring), not a bare path/value. `span_text` may contain multiple
    embedded newlines (a CommonMark-legal line-wrapped span, already bounded by
    `_is_valid_multiline_span_candidate` before this is ever called); it is
    treated exactly as CommonMark renders it -- a space -- before token-splitting,
    so a wrapped `` `gh project list --owner X\n--format json` `` still resolves
    its first token as `gh`."""
    joined = span_text.replace("\n", " ")
    if _ASSIGNMENT_SPAN_RE.match(joined):
        return True
    tokens = joined.split()
    if not tokens:
        return False
    return tokens[0] in _COMMAND_TOKENS


def _is_valid_multiline_span_candidate(span_text: str) -> bool:
    """True when a backtick-delimited CANDIDATE (content between two backticks,
    already found by `_LONE_BACKTICK_CANDIDATE_RE`) is actually treated as one
    inline code span, rather than as two unrelated lone backticks with ordinary
    prose in between. A single-line candidate (no embedded newline) is always
    valid -- these constraints exist only to bound how far a MULTI-line candidate
    may legitimately stretch:

      (i)   no blank line inside (`_BLANK_LINE_RE`) -- a blank line always ends a
            CommonMark inline span;
      (ii)  no line inside, other than the candidate's own first line, begins
            (after optional leading indentation) with a markdown block starter
            (`- `, `* `, `+ `, an ordinal list marker, `#`, `>`, or `|`) --
            a genuine runnable command never legitimately opens a later physical
            line with one of these, so a candidate that does is almost always an
            unclosed backtick that swallowed real document structure;
      (iii) at most `_SPAN_MAX_NEWLINES` embedded newlines and at most
            `_SPAN_MAX_CHARS` characters total -- a real wrapped command in this
            repo's dossiers tops out at single digits of wrapped lines (verified:
            test-architect.md's wrapped `grep`, 8 embedded newlines); anything far
            beyond that is far more likely a runaway match than real command text.

    A candidate that fails any of these is NOT a span: its opening backtick is a
    lone backtick, and the caller resumes scanning from the character right after
    it (see `_iter_valid_spans`) -- this is what stops one unbalanced backtick from
    swallowing unbounded prose bounded only by some distant, unrelated backtick."""
    if "\n" not in span_text:
        return True
    if len(span_text) > _SPAN_MAX_CHARS:
        return False
    if span_text.count("\n") > _SPAN_MAX_NEWLINES:
        return False
    if _BLANK_LINE_RE.search(span_text):
        return False
    lines = span_text.split("\n")
    for line in lines[1:]:
        if _BLOCK_STARTER_RE.match(line):
            return False
    return True


def _iter_valid_spans(text: str) -> Iterator[re.Match[str]]:
    """Yield each backtick-delimited match in `text` that is actually a valid
    inline code span per `_is_valid_multiline_span_candidate`, in left-to-right,
    non-overlapping order. A rejected candidate's opening backtick is skipped as a
    lone backtick (not a span start) and the scan resumes from the very next
    character, rather than from the rejected candidate's closing backtick -- so a
    later, unrelated backtick pair can still form its own valid span even when an
    earlier backtick was never actually closed."""
    pos = 0
    length = len(text)
    while pos < length:
        match = _LONE_BACKTICK_CANDIDATE_RE.search(text, pos)
        if match is None:
            return
        if _is_valid_multiline_span_candidate(match.group(1)):
            yield match
            pos = match.end()
        else:
            pos = match.start() + 1


def _prose_segments(text: str) -> Iterator[str]:
    """Yield the parts of `text` that D1 should actually scan: everything except
    fenced code blocks, inline code spans whose content is a runnable command or a
    shell variable assignment (a span may line-wrap across multiple embedded
    newlines, per CommonMark, within the bounds enforced by
    `_is_valid_multiline_span_candidate` -- it is still one span and still exempt
    on the same terms), and any `https?://` URL token (a link is a citation to the
    real value, not a restatement of it -- this also covers a URL inside a
    markdown link target, since the target text is scanned the same as any other
    text once URLs are stripped from it; this stripping happens BEFORE span
    matching, so a bare backticked URL is exempt too, the same as an unbacktracked
    one). A bare path/value in backticks (no command token, no assignment shape)
    is still yielded -- it is still a restatement."""
    text = text.replace("\r\n", "\n")
    text = _URL_RE.sub("", text)
    cursor = 0
    for fence_match in _FENCED_BLOCK_RE.finditer(text):
        prose_before = text[cursor : fence_match.start()]
        yield from _prose_segments_no_fences(prose_before)
        cursor = fence_match.end()
    yield from _prose_segments_no_fences(text[cursor:])


def _prose_segments_no_fences(text: str) -> Iterator[str]:
    """Split fence-free `text` around command inline-code-spans, yielding
    everything else (prose, and bare-value inline spans)."""
    cursor = 0
    for span_match in _iter_valid_spans(text):
        if _is_command_span(span_match.group(1)):
            yield text[cursor : span_match.start()]
            cursor = span_match.end()
    yield text[cursor:]


def _doctor_d1(repo: Path, data: dict[str, Any]) -> Iterator[str]:
    oversight_dir = repo / ".claude" / "oversight"
    if not oversight_dir.is_dir():
        return

    slug = None
    product = data.get("product")
    if isinstance(product, dict):
        slug = product.get("slug")

    values: list[tuple[str, str]] = []
    for dotted_key in _D1_KEYS:
        try:
            value = _dig(data, dotted_key)
        except KeyError:
            continue
        if not isinstance(value, str):
            continue
        if dotted_key == "oversight.report_dir":
            # A dossier restates the EXPANDED path (what it would actually paste), not the
            # raw ${slug}/~ template -- expand the same way cmd_get does before comparing.
            value = _expand_manifest_value(value, slug)
        if len(value) >= _D1_MIN_LEN:
            values.append((dotted_key, value))

    if not values:
        return

    # manifest.json itself is never matched by this glob (*.md vs. .json), so there is no
    # need to explicitly skip it here.
    for dossier_path in sorted(oversight_dir.glob("*.md")):
        try:
            text = dossier_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        scannable = "".join(_prose_segments(text))
        for dotted_key, value in values:
            if value in scannable:
                yield f"{dossier_path.name}\trestates-manifest:{dotted_key}"


def _doctor_d2(claude_dir: Path, repo: Path) -> Iterator[str]:
    bundle_version_path = repo / ".claude" / "oversight" / ".bundle_version"
    templates_dir = claude_dir / "templates" / "oversight"
    if not bundle_version_path.is_file() or not templates_dir.is_dir():
        return
    try:
        recorded_sha = bundle_version_path.read_text(encoding="utf-8").strip()
    except OSError:
        yield "bundle_version\tunreadable"
        return
    if not recorded_sha or not _SHA_RE.fullmatch(recorded_sha):
        # Reject anything that isn't a plain hex sha BEFORE it ever reaches a subprocess
        # argument -- a value like "--output=/tmp/x" placed here is otherwise read by git
        # as an option, not a revision, and can make git write an attacker-chosen file.
        yield "bundle_version\tunreadable"
        return
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(claude_dir),
                "diff",
                "--name-only",
                "--end-of-options",
                f"{recorded_sha}..HEAD",
                "--",
                "templates/oversight/",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        yield "bundle_version\tunreadable"
        return
    if result.returncode != 0:
        yield "bundle_version\tunreadable"
        return
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        yield f"{Path(line).name}\ttemplate-outdated"


def cmd_doctor(repo: Path, claude_dir: Path) -> None:
    findings: list[str] = []

    mpath = _manifest_path(repo)
    data: dict[str, Any] | None = None
    if not mpath.is_file():
        findings.append("manifest\tmissing")
    else:
        try:
            text = mpath.read_text(encoding="utf-8")
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                data = parsed
        except (OSError, json.JSONDecodeError):
            data = None

    findings.extend(_doctor_dossiers(claude_dir, repo))

    if data is not None:
        findings.extend(_doctor_d1(repo, data))

    findings.extend(_doctor_d2(claude_dir, repo))

    for line in findings:
        print(line)
    if findings:
        print(f"{len(findings)} findings")
        sys.exit(1)
    print("OK: 0 findings")
    sys.exit(0)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_USAGE = """\
usage: repo_manifest.py <command> [args]

commands:
  get <dotted.key> [--repo PATH] [--raw]   print a manifest value (or fail: manifest-missing / key-missing)
  validate [--repo PATH]                  check manifest.json against the schema; OK or INVALID lines
  register [--repo PATH]                  upsert repo_registry.json / wheel_repos.json / gh label from the manifest
  doctor [--repo PATH]                    report missing dossiers, placeholders, manifest restatements, stale templates

env:
  CLAUDE_DIR   runtime root (default ~/.claude)

--repo PATH overrides the default resolution (git rev-parse --show-toplevel from cwd).

${slug} is a general expansion available in any manifest string value `get` returns (not
special to one field) -- it expands to product.slug, alongside a leading ~ expanding to
the caller's home directory.

PATH-TYPED KEYS (tracker_doc, operator_input.path, operator_input.open_path,
gtm.missions_dir, wheel.venv_python) are stored repo-relative but returned ABSOLUTE by
`get` -- anchored to the resolved repo root -- since a repo-relative string otherwise
resolves against the CALLER's cwd, which is wrong from any directory but the repo root.
Pass --raw to print the stored (repo-relative) value instead. oversight.report_dir is
NOT in this set: it is already ~-anchored (or ${slug}-templated), so it is unaffected by
--raw and by this anchoring either way. --raw is only accepted by 'get' -- passing it to
validate/register/doctor is a usage error (exit 64), since none of them ever print a
manifest value for --raw to affect.
"""


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(_USAGE, end="")
        return 0 if argv and argv[0] in ("-h", "--help") else 64

    command = argv[0]
    rest = argv[1:]

    repo_override: str | None = None
    raw = False
    positional: list[str] = []
    i = 0
    while i < len(rest):
        arg = rest[i]
        if arg == "--repo":
            if i + 1 >= len(rest):
                print(_USAGE, end="", file=sys.stderr)
                return 64
            repo_override = rest[i + 1]
            i += 2
            continue
        if arg == "--raw":
            raw = True
            i += 1
            continue
        positional.append(arg)
        i += 1

    if raw and command != "get":
        print(f"usage-error: --raw is only valid with 'get', not '{command}'", file=sys.stderr)
        print(_USAGE, end="", file=sys.stderr)
        return 64

    claude_dir = _claude_dir()

    if command == "get":
        if len(positional) != 1:
            print(_USAGE, end="", file=sys.stderr)
            return 64
        repo = _resolve_repo(repo_override)
        cmd_get(repo, positional[0], raw=raw)
        return 0
    if command == "validate":
        repo = _resolve_repo(repo_override)
        cmd_validate(repo)
        return 0
    if command == "register":
        repo = _resolve_repo(repo_override)
        cmd_register(repo, claude_dir)
        return 0
    if command == "doctor":
        repo = _resolve_repo(repo_override)
        cmd_doctor(repo, claude_dir)
        return 0

    print(_USAGE, end="", file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
