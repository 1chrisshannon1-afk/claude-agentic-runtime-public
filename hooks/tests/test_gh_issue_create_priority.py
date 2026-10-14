"""Tests for gh_issue.sh `create --priority` (#5827, master
plan WS1 Phase D — the issue-CREATION quality gate + promotion budget,
observer-first).

THE FEATURE: `create` gains `--priority P0|P1|P2|P3`, which — given
`--project`/`--owner` — sets the project's "Priority" field on the newly
created issue via the SAME one-query `_resolve_project_and_field` resolver
`--triage`/`transition` already use (see test_gh_issue_transition_field_
query.py's own docstring for the GraphQL-cost rationale this reuses).

OBSERVER-FIRST (Phase D's own words): "Nothing is ever dropped or refused
for budget reasons." A `create` missing `--priority` or any of the three
label classes (type/area:/difficulty:) logs `create-missing-triage` (this
script's own stderr WARNING line, plus a best-effort JSONL line to
~/.claude/.enforcement/log.jsonl -- see test_missing_triage_still_logs_and_
never_refuses's temp-HOME redirection) and STILL FILES. `--priority P9` (an
invalid VALUE, not an absent flag) is the one thing that DOES refuse --
that is a caller error (a mistyped flag value), not a budget refusal, and is
paired here with its own recovery test per CLAUDE.md §6's "deny test paired
with a recovery test" convention.

EVERY new issue lands in `Backlog` when --project is given but --triage is
not (Phase D: "Backlog IS the parked state... every new issue... lands in
Backlog").

Harness shape borrowed from test_gh_issue_transition_field_query.py (same
`_GRAPHQL_HELPER`/`_GH_STUB`/`_project_fixture`/`_make_env` pattern) --
duplicated locally rather than cross-imported, matching this test suite's
existing one-file-per-concern convention (see test_gh_issue_dispose.py /
test_gh_issue_create_dupe_search_failure.py, which do the same).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT = os.environ.get(
    "GH_ISSUE_SCRIPT", str(Path.home() / ".claude" / "scripts" / "gh_issue.sh")
)

_GRAPHQL_HELPER = r"""
import json, os, re, sys

def _load(path):
    with open(path) as f:
        return json.load(f)

args = sys.argv[1:]
kv = {}
i = 0
while i < len(args):
    if args[i] in ("-f", "-F") and i + 1 < len(args):
        k, _, v = args[i + 1].partition("=")
        kv[k] = v
        i += 2
    else:
        i += 1
query = kv.get("query", "")

fields_by_project = _load(os.environ["FAKE_PROJECT_FIELDS_JSON"])

# FAKE_FIELDS_SWITCH_AFTER / FAKE_PROJECT_FIELDS_JSON_2 (fix-round 3,
# finding 12): opt-in only -- unset in every other test, so this changes
# nothing for them. When set, the FIRST N resolver queries see the primary
# fixture and every query after that sees the second one. This is the only
# way to reach _write_status_field's own post-create _RESOLVE_ERR branch:
# an EXPLICIT --triage is validated pre-create by _validate_triage_status,
# which calls the SAME resolver, so a board that fails the resolver from
# the start is always caught BEFORE the issue is filed and never reaches
# the post-create write at all.
_switch_after = os.environ.get("FAKE_FIELDS_SWITCH_AFTER")
if _switch_after:
    _counter = os.environ["FAKE_RESOLVER_CALL_COUNTER"]
    try:
        _n = int(open(_counter).read().strip() or "0")
    except (OSError, ValueError):
        _n = 0
    if "repositoryOwner" in query and "projectV2" in query:
        _n += 1
        with open(_counter, "w") as fh:
            fh.write(str(_n))
    if _n > int(_switch_after):
        fields_by_project = _load(os.environ["FAKE_PROJECT_FIELDS_JSON_2"])

if "repositoryOwner" in query and "projectV2" in query:
    owner = kv.get("owner", "")
    number = kv.get("number", "")
    field_name = kv.get("field", "")
    proj = fields_by_project.get(str(number))
    if proj is None or owner != os.environ.get("FAKE_OWNER", owner):
        print(json.dumps({"data": {"repositoryOwner": {"projectV2": None}}}))
        sys.exit(0)
    matches = [f for f in proj["fields"] if f["name"] == field_name]
    field_obj = None
    if matches:
        f = matches[0]
        field_obj = {"__typename": f["typename"], "id": f["id"], "name": f["name"]}
        if f["typename"] == "ProjectV2SingleSelectField":
            field_obj["options"] = f.get("options", [])
    nodes = [{"__typename": f["typename"], "name": f["name"]} for f in proj["fields"]]
    print(json.dumps({
        "data": {
            "repositoryOwner": {
                "projectV2": {
                    "id": proj["id"],
                    "field": field_obj,
                    "fields": {"totalCount": len(proj["fields"]), "nodes": nodes},
                }
            }
        }
    }))
    sys.exit(0)

if "projectItems" in query:
    node_id = kv.get("id", "")
    items = _load(os.environ["FAKE_PROJECT_ITEMS_JSON"])
    nodes = items.get(node_id, [])
    print(json.dumps({"data": {"node": {"projectItems": {"nodes": nodes}}}}))
    sys.exit(0)

print(f"fake gh graphql helper: unhandled query: {query!r} kv={kv!r}", file=sys.stderr)
sys.exit(1)
"""

_GH_STUB = r"""#!/bin/bash
echo "$@" >> "$GH_LOG"
if [ "$1" = "project" ] && [ "$2" = "view" ]; then
  echo "gh_stub: FORBIDDEN call: gh project view" >&2
  exit 1
fi
if [ "$1" = "project" ] && [ "$2" = "field-list" ]; then
  echo "gh_stub: FORBIDDEN call: gh project field-list" >&2
  exit 1
fi
if [ "$1" = "api" ] && [ "$2" = "graphql" ]; then
  "$FAKE_GH_PYTHON" "$FAKE_GRAPHQL_HELPER" "$@"
  exit $?
fi
if [ "$1" = "issue" ] && [ "$2" = "comment" ]; then
  exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "view" ]; then
  echo "{\"id\": \"$FAKE_ISSUE_NODE_ID\", \"url\": \"https://github.com/o/r/issues/$FAKE_ISSUE_NUM\"}"
  exit 0
fi
if [ "$1" = "issue" ] && [ "$2" = "create" ]; then
  echo "https://github.com/o/r/issues/$FAKE_ISSUE_NUM"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "item-add" ]; then
  echo "{\"id\": \"$FAKE_ADD_ITEM_ID\"}"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "item-edit" ]; then
  if [ -n "${FAKE_ITEM_EDIT_FAIL:-}" ]; then
    if [ -z "${FAKE_ITEM_EDIT_FAIL_FIELD_ID:-}" ] || printf '%s\n' "$@" | grep -qF -- "$FAKE_ITEM_EDIT_FAIL_FIELD_ID"; then
      echo "gh_stub: forced item-edit failure" >&2
      exit 1
    fi
  fi
  exit 0
fi
echo "gh_stub: unhandled args: $*" >&2
exit 1
"""

DEFAULT_PROJECT = "1"
DEFAULT_OWNER = "acme"
DEFAULT_ITEM_ID = "PVTI_existing_item"


def _project_fixture(
    *,
    project_id: str = "PVT_x1",
    status_options: list[str] | None = None,
    priority_options: list[str] | None = None,
    extra_field_count: int = 0,
) -> dict:
    fields = []
    if status_options is not None:
        fields.append(
            {
                "name": "Status",
                "id": "FIELD_status",
                "typename": "ProjectV2SingleSelectField",
                "options": [{"id": f"OPT_{o}", "name": o} for o in status_options],
            }
        )
    if priority_options is not None:
        fields.append(
            {
                "name": "Priority",
                "id": "FIELD_priority",
                "typename": "ProjectV2SingleSelectField",
                "options": [{"id": f"POPT_{o}", "name": o} for o in priority_options],
            }
        )
    fields.append({"name": "Title", "id": "FIELD_title", "typename": "ProjectV2Field"})
    # extra_field_count (fix-round 2, B2): pads the board's field list past
    # 100 so `fields(first: 100) { totalCount ... }` reports a genuine
    # totalCount > 100, exercising _resolve_project_and_field's own
    # ambiguity-check-cannot-page refusal (the >100-fields case) via the
    # SAME fake-gh/fake-GraphQL harness every other test in this file uses
    # -- no separate stub needed.
    for i in range(extra_field_count):
        fields.append({"name": f"Extra{i}", "id": f"FIELD_extra{i}", "typename": "ProjectV2Field"})
    return {"id": project_id, "fields": fields}


def _make_env(
    tmp_path: Path,
    *,
    project_fixture: dict,
    project_number: str = DEFAULT_PROJECT,
    owner: str = DEFAULT_OWNER,
    item_already_on_board: bool = False,
    item_edit_fail: bool = False,
    item_edit_fail_field_id: str | None = None,
    project_fixture_2: dict | None = None,
    fields_switch_after: int | None = None,
    fake_home: bool = True,
) -> dict:
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    gh = bindir / "gh"
    gh.write_text(_GH_STUB)
    gh.chmod(0o755)

    helper = tmp_path / "graphql_helper.py"
    helper.write_text(_GRAPHQL_HELPER)

    fields_by_project = {project_number: project_fixture}
    fields_json = tmp_path / "project_fields.json"
    fields_json.write_text(json.dumps(fields_by_project))

    issue_node_id = "ISSUE_NODE_1"
    items_json = tmp_path / "project_items.json"
    items_map = {}
    if item_already_on_board:
        items_map[issue_node_id] = [
            {"id": DEFAULT_ITEM_ID, "project": {"id": project_fixture["id"]}}
        ]
    else:
        items_map[issue_node_id] = []
    items_json.write_text(json.dumps(items_map))

    log = tmp_path / "gh.log"
    log.write_text("")

    env = dict(os.environ)
    env["PATH"] = f"{bindir}:{env['PATH']}"
    env["GH_LOG"] = str(log)
    env["FAKE_GH_PYTHON"] = sys.executable
    env["FAKE_GRAPHQL_HELPER"] = str(helper)
    env["FAKE_PROJECT_FIELDS_JSON"] = str(fields_json)
    if fields_switch_after is not None:
        assert project_fixture_2 is not None, (
            "fields_switch_after needs project_fixture_2"
        )
        fields_json_2 = tmp_path / "project_fields_2.json"
        fields_json_2.write_text(json.dumps({project_number: project_fixture_2}))
        counter = tmp_path / "resolver_calls.txt"
        counter.write_text("0")
        env["FAKE_PROJECT_FIELDS_JSON_2"] = str(fields_json_2)
        env["FAKE_FIELDS_SWITCH_AFTER"] = str(fields_switch_after)
        env["FAKE_RESOLVER_CALL_COUNTER"] = str(counter)
    else:
        for k in (
            "FAKE_PROJECT_FIELDS_JSON_2",
            "FAKE_FIELDS_SWITCH_AFTER",
            "FAKE_RESOLVER_CALL_COUNTER",
        ):
            env.pop(k, None)
    env["FAKE_PROJECT_ITEMS_JSON"] = str(items_json)
    env["FAKE_OWNER"] = owner
    env["FAKE_ISSUE_NODE_ID"] = issue_node_id
    env["FAKE_ISSUE_NUM"] = "1"
    env["FAKE_ADD_ITEM_ID"] = "PVTI_newly_added"
    if item_edit_fail:
        env["FAKE_ITEM_EDIT_FAIL"] = "1"
        if item_edit_fail_field_id:
            env["FAKE_ITEM_EDIT_FAIL_FIELD_ID"] = item_edit_fail_field_id
        else:
            env.pop("FAKE_ITEM_EDIT_FAIL_FIELD_ID", None)
    else:
        env.pop("FAKE_ITEM_EDIT_FAIL", None)
        env.pop("FAKE_ITEM_EDIT_FAIL_FIELD_ID", None)
    if fake_home:
        # Redirect ~/.claude/.enforcement/log.jsonl to a throwaway HOME so
        # the observer-window WARN line's best-effort JSONL write never
        # touches the REAL ~/.claude/.enforcement/ ledger (task constraint:
        # "never the real ~/.claude/.enforcement/").
        fake_home_dir = tmp_path / "fakehome"
        (fake_home_dir / ".claude").mkdir(parents=True, exist_ok=True)
        env["HOME"] = str(fake_home_dir)
    return env


def _run(tmp_path: Path, args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", SCRIPT, *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def _log_lines(env: dict) -> list[str]:
    return Path(env["GH_LOG"]).read_text().splitlines()


def _create_args(
    tmp_path: Path,
    *,
    title: str = "A brand new distinct finding",
    priority: str | None = None,
    triage: str | None = None,
    project: str | None = DEFAULT_PROJECT,
    owner: str | None = DEFAULT_OWNER,
    labels: list[str] | None = None,
    force_new: bool = True,
) -> list[str]:
    body = tmp_path / "body.md"
    body.write_text("body text")
    args = ["create", "--title", title, "--body-file", str(body)]
    if force_new:
        args.append("--force-new")
    if priority is not None:
        args += ["--priority", priority]
    if triage is not None:
        args += ["--triage", triage]
    if project is not None:
        args += ["--project", project]
    if owner is not None:
        args += ["--owner", owner]
    for label in labels or []:
        args += ["--label", label]
    return args


# ---------------------------------------------------------------------------
# (1) Happy path: --priority writes the Priority field via the ONE-query
# resolver, never calling gh project view / field-list.
# ---------------------------------------------------------------------------


def test_priority_write_succeeds_via_single_graphql_query(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project field-list") for line in log), log
    assert not any(line.startswith("project view") for line in log), log
    assert any(line.startswith("project item-edit") for line in log), log
    assert "set project #1 field 'Priority' = 'P2'" in proc.stderr


def test_priority_write_adds_issue_to_board_when_not_already_on_it(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    env = _make_env(tmp_path, project_fixture=fixture, item_already_on_board=False)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P1",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("project item-add") for line in log), log


def test_priority_and_triage_both_write_in_one_create_call(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog", "Ready #1"],
        priority_options=["P0", "P1", "P2", "P3"],
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    args = _create_args(
        tmp_path,
        priority="P0",
        labels=["bug", "area: backend", "difficulty: easy"],
    )
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 0, proc.stderr
    assert "field 'Status' = 'Ready #1'" in proc.stderr
    assert "field 'Priority' = 'P0'" in proc.stderr


# ---------------------------------------------------------------------------
# (2) Invalid --priority VALUE refuses BEFORE creating anything -- a caller
# error, paired with a recovery test (CLAUDE.md §6).
# ---------------------------------------------------------------------------


def test_invalid_priority_value_refuses_and_creates_nothing(tmp_path):
    fixture = _project_fixture(priority_options=["P0", "P1", "P2", "P3"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority="P9"),
        env,
    )
    assert proc.returncode != 0
    assert "not one of the valid priority values" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("issue create") for line in log), log


def test_invalid_priority_value_paired_recovery_with_valid_value(tmp_path):
    """PAIRED RECOVERY (CLAUDE.md §6): the identical call with a VALID
    priority value succeeds and creates the issue."""
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("issue create") for line in log), log


def test_invalid_priority_refused_even_without_project(tmp_path):
    # An invalid value is ALWAYS a caller error, regardless of whether a
    # board write was even going to happen.
    fixture = _project_fixture(priority_options=["P0", "P1", "P2", "P3"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority="bogus", project=None, owner=None),
        env,
    )
    assert proc.returncode != 0
    assert "not one of the valid priority values" in proc.stderr


# ---------------------------------------------------------------------------
# (3) Observer-first WARN: missing --priority or a label class logs
# `create-missing-triage` and STILL FILES -- nothing is ever refused for it.
# ---------------------------------------------------------------------------


def test_missing_priority_still_files_and_warns(tmp_path):
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" in proc.stderr
    assert "priority" in proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("issue create") for line in log), "must still file despite missing --priority"


def test_missing_all_labels_still_files_and_warns(tmp_path):
    fixture = _project_fixture(status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority="P2", labels=[]),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" in proc.stderr
    assert "type-label" in proc.stderr
    assert "area-label" in proc.stderr
    assert "difficulty-label" in proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("issue create") for line in log)


def test_fully_compliant_create_logs_no_warning(tmp_path):
    fixture = _project_fixture(status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" not in proc.stderr


def test_missing_triage_writes_enforcement_log_line(tmp_path):
    """Layer 1's own best-effort JSONL write (distinct from Layer 2's
    issue_create_observer.py hook) lands in the FAKE HOME's
    .enforcement/log.jsonl -- never the real one (see _make_env's
    fake_home redirection). Fix-round 1 (A3): the write is DEFERRED until
    the real issue number is known, and the row carries it as "issue" --
    board-steward's 30-event audit must be able to join this row back to
    the issue it describes."""
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority=None, labels=[]),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    log_path = Path(env["HOME"]) / ".claude" / ".enforcement" / "log.jsonl"
    assert log_path.exists(), "expected a best-effort enforcement log write"
    lines = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["hook"] == "gh_issue_sh"
    assert lines[0]["decision"] == "create-missing-triage"
    assert set(lines[0]["missing"]) == {
        "priority",
        "type-label",
        "area-label",
        "difficulty-label",
    }
    assert lines[0]["issue"] == int(env["FAKE_ISSUE_NUM"])


def test_missing_triage_on_exec_gh_fast_path_logs_issue_null(tmp_path):
    """A3: the exec-gh FAST PATH (no --triage, no --priority at all -- so no
    number is ever parsed) must still log create-missing-triage when labels
    are absent, with "issue": null and an explanatory note -- never a
    fabricated/guessed number, and never silently skipped just because this
    path never captures one."""
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path, priority=None, project=None, owner=None, labels=[]
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    log_path = Path(env["HOME"]) / ".claude" / ".enforcement" / "log.jsonl"
    assert log_path.exists()
    lines = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["decision"] == "create-missing-triage"
    assert lines[0]["issue"] is None
    assert "note" in lines[0] and lines[0]["note"]


# ---------------------------------------------------------------------------
# (4) Every new issue lands in Backlog by default when --project is given
# but --triage is not.
# ---------------------------------------------------------------------------


def test_create_with_project_but_no_triage_defaults_to_backlog(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "Ready #1"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "field 'Status' = 'Backlog'" in proc.stderr


def test_defaulted_backlog_on_board_without_that_option_still_files(tmp_path):
    """A1 (fix-round 1): a DEFAULTED --triage (Backlog, because --project
    was given but --triage was not) is SOFT -- on a board whose Status
    field has no literal "Backlog" option, the pre-fix code `_die`d BEFORE
    creation (rc 1, nothing filed), violating Phase D's own "nothing is
    ever dropped or refused". Post-fix: files successfully (rc 0), warns,
    and leaves Status unset rather than refusing."""
    # No "Backlog" in this board's Status options at all.
    fixture = _project_fixture(status_options=["Triage", "In Progress"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "WARNING" in proc.stderr
    assert "Backlog" in proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("issue create") for line in log), "must still file despite the invalid defaulted Backlog"
    # The write was never attempted against a nonexistent option.
    assert not any(line.startswith("project item-edit") for line in log), log


def test_explicit_triage_on_board_without_that_option_still_refuses(tmp_path):
    """PAIRED RECOVERY-of-the-inverse (A1): an EXPLICIT --triage naming an
    invalid option stays HARD -- refuses, creates nothing, exactly as
    before this fix. Proves the soft/hard split actually distinguishes the
    two cases rather than softening everything."""
    fixture = _project_fixture(status_options=["Triage", "In Progress"])
    env = _make_env(tmp_path, project_fixture=fixture)
    args = _create_args(
        tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"]
    )
    args += ["--triage", "Backlog"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode != 0
    assert "not a valid option" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("issue create") for line in log), "an EXPLICIT bad --triage must still refuse"


def test_create_without_project_never_defaults_triage(tmp_path):
    # No --project at all -> no board write is even possible; the old,
    # backward-compatible exec-gh fast path stays in force (no Status write
    # attempted, no crash on an unset PROJECT/OWNER).
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority=None, project=None, owner=None, labels=[]),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "field 'Status'" not in proc.stderr


def test_explicit_triage_overrides_backlog_default(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "Ready #1"])
    env = _make_env(tmp_path, project_fixture=fixture)
    args = _create_args(tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"])
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 0, proc.stderr
    assert "field 'Status' = 'Ready #1'" in proc.stderr
    assert "field 'Status' = 'Backlog'" not in proc.stderr


# ---------------------------------------------------------------------------
# (5) --priority write failure fails loud (mirrors _do_transition's own
# item-edit-failure contract).
# ---------------------------------------------------------------------------


def test_priority_item_edit_failure_fails_loud(tmp_path):
    """Fix-round 1 (A2): a post-create Priority write failure is a NAMED
    PARTIAL (exit 3), never a bare 1 that reads as "nothing happened" --
    the issue ALREADY EXISTS by this point. The issue number appears on
    stdout (never buried only in stderr) so a caller can find it either
    way."""
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    # Scope the forced item-edit failure to the Priority field's own id
    # (FIELD_priority, per _project_fixture) so the Backlog-default Status
    # write succeeds first and the failure is unambiguously attributable to
    # the Priority write this test targets.
    env = _make_env(
        tmp_path,
        project_fixture=fixture,
        item_edit_fail=True,
        item_edit_fail_field_id="FIELD_priority",
    )
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "Priority NOT set" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_priority_field_not_found_fails_loud(tmp_path):
    """A2: same PARTIAL contract (exit 3, issue number on stdout) when the
    Priority field itself doesn't exist on the board."""
    # No priority_options given -> no "Priority" field on the fixture at all.
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "not found" in proc.stderr
    assert "Priority NOT set" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_priority_without_project_files_and_warns_never_fails(tmp_path):
    """A2 primary fix: --priority WITHOUT --project used to create the
    issue and then exit 1 (reading as total failure when the issue already
    existed) -- and, with GH_PROJECT_OWNER set, fired a real GraphQL call
    with an EMPTY project number before dying. Post-fix: rc 0, the issue
    URL is on stdout, a WARNING names the issue number, and ZERO `api
    graphql` calls are made for the Priority resolution (there is nothing
    to resolve without a project)."""
    fixture = _project_fixture(priority_options=["P0", "P1", "P2", "P3"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority="P2", project=None, owner=None, labels=[]),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert f"issues/{env['FAKE_ISSUE_NUM']}" in proc.stdout
    assert "WARNING" in proc.stderr
    assert "--priority given without --project" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("api graphql") for line in log), (
        "no GraphQL call may be made resolving a Priority write with no --project",
        log,
    )


def test_priority_without_project_paired_recovery_with_project(tmp_path):
    """PAIRED RECOVERY: the identical call WITH --project succeeds and
    actually writes the Priority field."""
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    assert "field 'Priority' = 'P2'" in proc.stderr


# ---------------------------------------------------------------------------
# Fix-round 2 (B1, B2, finding 3): after the issue exists, NOTHING may exit
# 1 -- exit 1 means "nothing was filed, safe to retry"; any post-create
# failure is a PARTIAL (exit 3, issue number on stdout, a message naming
# what did not get set).
# ---------------------------------------------------------------------------


def test_b1_defaulted_backlog_item_edit_failure_is_soft_never_partial(tmp_path):
    """B1: a DEFAULTED --triage (Backlog) whose item-edit write fails is
    SOFT -- exit 0, warns, issue stays filed with no Status set. Mirrors
    A1's own soft/hard split extended to the post-create write."""
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(
        tmp_path,
        project_fixture=fixture,
        item_edit_fail=True,
        item_edit_fail_field_id="FIELD_status",
    )
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "WARNING" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stderr


def test_b1_explicit_triage_item_edit_failure_is_partial_never_exit_1(tmp_path):
    """B1 primary fix: an EXPLICIT --triage whose item-edit write fails is a
    named PARTIAL (exit 3) -- NEVER a bare exit 1, which would read as
    "nothing happened" and drive a retry that files a duplicate. This is
    the exact HEAD-vs-pending regression the reviewer proved by execution:
    pre-fix, this cell returned rc=1 with the issue already filed."""
    fixture = _project_fixture(status_options=["Backlog", "Ready #1"])
    env = _make_env(
        tmp_path,
        project_fixture=fixture,
        item_edit_fail=True,
        item_edit_fail_field_id="FIELD_status",
    )
    args = _create_args(
        tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"]
    )
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "Status NOT set" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_b1_explicit_triage_item_add_failure_is_partial(tmp_path):
    """The second of the three post-create rc=1 paths the reviewer named:
    item-add (the issue is not yet on the board and adding it fails)."""
    fixture = _project_fixture(status_options=["Backlog", "Ready #1"])
    env = _make_env(
        tmp_path, project_fixture=fixture, item_already_on_board=False
    )

    # Force item-add to fail by pointing FAKE_ADD_ITEM_ID at nothing --
    # simplest: monkeypatch the stub via env override isn't available here,
    # so instead make item-add fail structurally: an item NOT already on
    # the board, with add_json missing "id" -- achieved by leaving
    # FAKE_ADD_ITEM_ID unset (empty), which the real _GH_STUB always
    # returns verbatim as {"id": ""} => jq -r '.id // empty' => "".
    env["FAKE_ADD_ITEM_ID"] = ""
    args = _create_args(
        tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"]
    )
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "could not be added" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_b1_explicit_triage_issue_view_failure_is_partial(tmp_path):
    """The third of the three post-create rc=1 paths: `gh issue view`
    itself fails to resolve the issue's node id."""
    fixture = _project_fixture(status_options=["Backlog", "Ready #1"])
    env = _make_env(tmp_path, project_fixture=fixture)
    # FAKE_ISSUE_NODE_ID empty -> the stub's `gh issue view` response has an
    # empty "id", which the script reads as issue_node_id="" -> fails.
    env["FAKE_ISSUE_NODE_ID"] = ""
    args = _create_args(
        tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"]
    )
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "could not resolve issue" in proc.stderr
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_b1_standalone_transition_keeps_exit_1_contract(tmp_path):
    """PAIRED CONTRAST (B1): the STANDALONE `transition` subcommand keeps
    its exit-1 contract unchanged -- nothing has been filed by `transition`
    itself, so exit 1 on a failed item-edit is CORRECT there, unlike the
    post-create path inside `create`."""
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(
        tmp_path,
        project_fixture=fixture,
        item_edit_fail=True,
        item_edit_fail_field_id="FIELD_status",
    )
    proc = _run(
        tmp_path,
        [
            "transition",
            env["FAKE_ISSUE_NUM"],
            "--status",
            "Backlog",
            "--project",
            DEFAULT_PROJECT,
            "--owner",
            DEFAULT_OWNER,
        ],
        env,
    )
    assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
    assert "board update FAILED" in proc.stderr
    # Never a PARTIAL marker on this path -- transition has no PARTIAL concept.
    assert "PARTIAL" not in proc.stdout


def test_b2_over_100_fields_is_partial_never_bare_exit_1_priority(tmp_path):
    """B2: the >100-fields ambiguity refusal, reached from the POST-CREATE
    Priority write, must route through the PARTIAL contract -- not `_die`
    from inside the resolver, bypassing it. `totalCount: 151` (150 extra
    padding fields + the base Priority/Title fields)."""
    fixture = _project_fixture(
        priority_options=["P0", "P1", "P2", "P3"], extra_field_count=150
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority="P2",
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "more than the 100" in proc.stderr
    assert "PARTIAL" in proc.stdout
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout


def test_b2_over_100_fields_explicit_triage_refuses_pre_create_not_partial(tmp_path):
    """B2's mirror on the Status side is caught EARLIER than the Priority
    case: an EXPLICIT --triage's own PRE-CREATE validation
    (_validate_triage_status, routed through _triage_fail -- hard for an
    explicit value) already calls the resolver and refuses BEFORE creating
    anything when the board has >100 fields -- so this never reaches the
    post-create write / PARTIAL path at all. This is CORRECT and DIFFERENT
    from the Priority case (which has no pre-create validation step, since
    --priority's only pre-create check is the fixed P0-P3 value domain, not
    a live board lookup). Asserts BOTH angles itself -- the exit code and
    the "nothing was filed" fact, read from the gh call log -- since a
    refusal that still filed the issue would be the actual defect here.
    (fix-round 3, finding 13: a second test asserting the identical facts
    with a weaker `!= 0` exit assertion was folded into this one.)"""
    fixture = _project_fixture(
        status_options=["Backlog", "Ready #1"], extra_field_count=150
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    args = _create_args(
        tmp_path, priority=None, labels=["bug", "area: backend", "difficulty: easy"]
    )
    args += ["--triage", "Ready #1"]
    proc = _run(tmp_path, args, env)
    assert proc.returncode == 1, (proc.returncode, proc.stdout, proc.stderr)
    assert "more than the 100" in proc.stderr
    assert "PARTIAL" not in proc.stdout
    log = _log_lines(env)
    assert not any(line.startswith("issue create") for line in log), (
        "explicit --triage validation refuses BEFORE filing -- nothing should be created",
        log,
    )


def test_b2_over_100_fields_defaulted_backlog_is_soft(tmp_path):
    """B2 + A1 interaction: a DEFAULTED Backlog hitting the >100-fields
    refusal is SOFT (exit 0), exactly like any other defaulted-write
    failure -- the severity split is orthogonal to WHICH resolver failure
    triggered it. This is caught by _validate_triage_status's own
    PRE-CREATE call to the resolver (routed through _triage_fail's soft
    branch, since TRIAGE_WAS_DEFAULTED is set), never reaching
    _write_status_field at all -- unlike the Priority case (B2's other
    test, test_b1_over_100_fields_is_partial_never_bare_exit_1_priority),
    which has no pre-create validation step and so genuinely exercises the
    POST-CREATE path."""
    fixture = _project_fixture(status_options=["Backlog"], extra_field_count=150)
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "WARNING" in proc.stderr
    assert "more than the 100" in proc.stderr


def test_finding3_unparseable_issue_number_is_partial(tmp_path):
    """Finding 3: the "could not parse an issue number" branch is PARTIAL
    (exit 3), never exit 1 -- its own message already says "the issue was
    filed", so exit 1 there was self-contradictory. The number is unknown,
    so the raw gh output is printed instead of a fabricated number."""
    fixture = _project_fixture(status_options=["Backlog"])
    env = _make_env(tmp_path, project_fixture=fixture)

    # Make the fake gh's `issue create` print something with NO parseable
    # issue URL, so created_url/created_num never resolve.
    bindir = tmp_path / "bin"
    gh = bindir / "gh"
    original = gh.read_text()
    stub = original.replace(
        'if [ "$1" = "issue" ] && [ "$2" = "create" ]; then\n'
        '  echo "https://github.com/o/r/issues/$FAKE_ISSUE_NUM"\n'
        "  exit 0\n"
        "fi",
        'if [ "$1" = "issue" ] && [ "$2" = "create" ]; then\n'
        '  echo "some unparseable garbage with no issue URL at all"\n'
        "  exit 0\n"
        "fi",
    )
    assert stub != original, "gh stub's issue-create branch text moved -- update the .replace() target"
    gh.write_text(stub)

    proc = _run(
        tmp_path,
        _create_args(
            tmp_path,
            priority=None,
            labels=["bug", "area: backend", "difficulty: easy"],
        ),
        env,
    )
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "PARTIAL" in proc.stdout
    assert "#<unknown>" in proc.stdout
    assert "unparseable" in proc.stderr


# ---------------------------------------------------------------------------
# (B3, fix-round 3) `create --triage <status>` with NO --project must stay a
# COMMENT-ONLY success — exit 0, a comment posted, the COMMENT-ONLY warning
# on stderr, and ZERO GraphQL calls. Before the fix, _write_status_field was
# called without a $PROJECT guard, so this documented call shape regressed
# from rc 0 to PARTIAL 3, lost its comment, and (whenever $GH_PROJECT_OWNER
# was set, i.e. the standard setup) fired a REAL GraphQL query with an EMPTY
# project number -- the exact defect _write_priority_field's own first guard
# exists to prevent on the adjacent path.
#
# Spec source: scripts/gh_issue.sh's own header, which documents
# "'transition' call with no --project -- same COMMENT-ONLY warning", and
# HEAD's _do_transition, which is what this call shape resolved to before
# the Status write was split out into _write_status_field.
# ---------------------------------------------------------------------------
def test_b3_triage_without_project_is_comment_only_and_exits_zero(tmp_path):
    fixture = _project_fixture()
    env = _make_env(tmp_path, project_fixture=fixture)
    env.pop("GH_PROJECT_OWNER", None)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, triage="Backlog", project=None, owner=None),
        env,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "PARTIAL" not in proc.stdout, proc.stdout
    assert "COMMENT-ONLY" in proc.stderr, proc.stderr
    lines = _log_lines(env)
    assert any(line.startswith("issue comment") for line in lines), lines
    assert not any(line.startswith("api graphql") for line in lines), lines


def test_b3_triage_without_project_but_with_owner_env_still_comment_only(tmp_path):
    """The same shape under the DOCUMENTED standard setup ($GH_PROJECT_OWNER
    exported, as daily_sweep.txt and oversight_install.md both prescribe).
    This is the worse half of B3: with $OWNER non-empty the pre-fix
    [ -n "$OWNER" ] guard PASSED, so execution reached the resolver and
    fired a GraphQL query with an empty project number."""
    fixture = _project_fixture()
    env = _make_env(tmp_path, project_fixture=fixture)
    env["GH_PROJECT_OWNER"] = DEFAULT_OWNER
    proc = _run(
        tmp_path,
        _create_args(tmp_path, triage="Backlog", project=None, owner=None),
        env,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "PARTIAL" not in proc.stdout, proc.stdout
    assert "COMMENT-ONLY" in proc.stderr, proc.stderr
    lines = _log_lines(env)
    assert any(line.startswith("issue comment") for line in lines), lines
    assert not any(line.startswith("api graphql") for line in lines), lines


def test_b3_paired_recovery_triage_with_project_still_writes_the_field(tmp_path):
    """Paired recovery for the two tests above: the comment-only fallback must
    not have broken the real path. WITH --project the Status field is written
    for real, and NO comment is posted (the field write is the record --
    _write_status_field's documented no-duplicate-comment behavior)."""
    fixture = _project_fixture(status_options=["Backlog", "Ready #1", "Done"])
    env = _make_env(tmp_path, project_fixture=fixture, item_already_on_board=True)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, triage="Backlog"),
        env,
    )
    assert proc.returncode == 0, (proc.returncode, proc.stdout, proc.stderr)
    assert "COMMENT-ONLY" not in proc.stderr, proc.stderr
    lines = _log_lines(env)
    assert any(line.startswith("project item-edit") for line in lines), lines
    assert not any(line.startswith("issue comment") for line in lines), lines


# ---------------------------------------------------------------------------
# (finding 12, fix-round 3) `_write_status_field`'s OWN post-create
# `_RESOLVE_ERR` branch. Every other >100-fields Status test is caught
# PRE-create by `_validate_triage_status`, which calls the same resolver, so
# none of them reaches the post-create write. Reaching it needs a board that
# passes the pre-create query and FAILS the post-create one -- hence the
# fixture switch. The point is not the >100-fields case itself (already
# covered pre-create) but that the post-create branch routes through
# `_status_write_fail`, so an EXPLICIT --triage lands on PARTIAL 3 with the
# issue filed and its number on stdout, never a bare exit 1.
# ---------------------------------------------------------------------------
def test_finding12_status_post_create_resolver_failure_is_partial(tmp_path):
    ok = _project_fixture(status_options=["Backlog", "Ready #1"])
    broken = _project_fixture(
        status_options=["Backlog", "Ready #1"], extra_field_count=150
    )
    # switch_after=1: the pre-create validation query sees the good board,
    # every later resolver query sees the >100-field one.
    env = _make_env(
        tmp_path,
        project_fixture=ok,
        project_fixture_2=broken,
        fields_switch_after=1,
        item_already_on_board=True,
    )
    proc = _run(tmp_path, _create_args(tmp_path, triage="Ready #1"), env)
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "PARTIAL" in proc.stdout, proc.stdout
    assert "Status NOT set" in proc.stdout, proc.stdout
    assert f"#{env['FAKE_ISSUE_NUM']}" in proc.stdout, proc.stdout
    assert "more than the 100" in proc.stderr, proc.stderr
    log = _log_lines(env)
    # The issue WAS filed -- that is the whole point of PARTIAL over exit 1.
    assert any(line.startswith("issue create") for line in log), log
    # A SECOND discriminator, independent of the message text above: an
    # item-edit FAILURE also yields rc 3 + "Status NOT set" + a filed issue
    # WITHOUT ever reaching the _RESOLVE_ERR branch, so it would satisfy
    # every other assertion here for the wrong reason. It is excluded by
    # the stderr assertion, and independently by this one -- that candidate
    # attempts the edit, whereas a resolver failure never gets that far.
    assert not any(line.startswith("project item-edit") for line in log), log


# ---------------------------------------------------------------------------
# (2026-09-21) The ambiguity guard tested a DIFFERENT value than it compared.
# Every one of the five sites read:
#
#     if [[ "${n:-0}" =~ ^[0-9]+$ ]] && [ "$n" -gt 1 ]
#
# The regex tests the DEFAULTED `${n:-0}` (which passes for an empty n), then
# the comparison uses the RAW `$n`. On an empty value bash errors with
# `[: : integer expression expected`, the `&&` sees a non-zero status, and the
# guard body is SKIPPED. Fixed by comparing `${n:-0}` too, so the guard tests
# what it compares.
#
# CONTROL FLOW IS UNCHANGED by that fix -- stated explicitly because an
# earlier version of this comment called it a closed fail-open, and that was
# WRONG. An empty count arises only when `_resolve_project_and_field` failed,
# and every call site already routes that failure to a terminal handler ABOVE
# this guard (`_die` at :510, `_triage_fail` at :619, `_priority_partial` at
# :724, `_status_write_fail` at :850). Verified by execution: pre-fix and
# post-fix produce identical rc, stdout, stderr (minus the noise line), and
# gh call log. This is a latent-trap and log-noise fix -- it matters because a
# future edit that moves one of those upstream checks would silently re-arm
# the skip, and the guard would then not fire while appearing to.
#
# A genuinely reachable wrong-field write DOES exist nearby and is NOT this:
# GraphQL may return `data` + `errors` together with `fields: null`, which
# `// 0` turns into a confident `0` while `proj_id`/`field_json` both resolve,
# so the guard evaluates cleanly and does not fire on a board that really has
# two same-named fields. That is identical pre-fix and post-fix -- a
# pre-existing defect tracked separately, never closed by this change.
#
# This asserts the OBSERVABLE half: no `integer expression expected` noise on
# a board-unresolvable run. That message is the tell that the guard was
# skipped rather than evaluated, and it lands in unattended job logs.
# ---------------------------------------------------------------------------
def test_ambiguity_guard_does_not_emit_integer_expression_errors(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1", "P2", "P3"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    # The trigger is a FAILING `gh api graphql`, not a succeeding one: the
    # resolver's `total_count`/`field_match_count` assignments capture the
    # empty output of a failed call, and the guard then compares that raw
    # empty value. The shared stub SUCCEEDS at `gh api`, so swap in one that
    # fails -- a board the resolver cannot reach at all, which is exactly the
    # unattended-job shape (bad token, network, deleted project).
    gh = tmp_path / "bin" / "gh"
    gh.write_text(
        "#!/bin/bash\n"
        'if [ "$1" = "issue" ] && [ "$2" = "create" ]; then\n'
        '  echo "https://github.com/o/r/issues/$FAKE_ISSUE_NUM"; exit 0\n'
        "fi\n"
        'if [ "$1" = "issue" ] && [ "$2" = "list" ]; then echo "[]"; exit 0; fi\n'
        "exit 1\n"
    )
    gh.chmod(0o755)
    proc = _run(
        tmp_path,
        _create_args(tmp_path, priority="P2"),
        env,
    )
    assert "integer expression expected" not in proc.stderr, proc.stderr
    # The real contract is unaffected: the issue is still filed and the
    # board-write failure is still a PARTIAL 3, never a bare exit 1.
    assert proc.returncode == 3, (proc.returncode, proc.stdout, proc.stderr)
    assert "PARTIAL" in proc.stdout, proc.stdout
