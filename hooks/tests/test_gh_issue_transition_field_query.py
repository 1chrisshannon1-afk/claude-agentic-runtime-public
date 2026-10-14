"""Tests for gh_issue.sh `transition`'s field-resolution GraphQL cost fix
(#5827, 2026-09-20).

THE DEFECT: `_do_transition` (and `create --triage`'s `_validate_triage_status`)
resolved the target project field's id/type/options via `gh project view` +
`gh project field-list` -- the latter fetches EVERY field on the board and
EVERY option of every single-select field just to find the id of the ONE
named field the caller asked for. Measured live, 2026-09-20 (one call each,
GraphQL rateLimit read before/after): `gh project field-list` alone cost
~101 points (19 fields, every option returned); `gh project view` cost 1;
the rest of the write path (issue view, the item-id GraphQL lookup,
item-edit) together cost ~3-4 more. So every `transition --project` call
cost ~105-113 GraphQL points, against a 5,000/hour budget shared by every
session on this machine.

THE FIX: `_resolve_project_and_field` replaces `gh project view` + `gh
project field-list` with ONE GraphQL query --
`repositoryOwner(login:$owner){ ... on ProjectV2Owner { projectV2(number:
$number) { id field(name:$field){...} fields(first:100){totalCount
nodes{...}} } } }` -- passing $owner/$number/$field as GraphQL variables
(-f/-F), never interpolated into the query text. Measured live, same
session: this query costs ~1 point total (the ambiguous-field-name
duplicate check, preserved from f028962, rides in the SAME query via a
names-only `fields(first:100)` selection, also ~1 point -- GitHub's
GraphQL cost model is driven by selection complexity/depth, not raw field
count; the old 101 came from requesting every SINGLE-SELECT FIELD'S OPTIONS
list, which this fix only ever requests for the ONE targeted field).

Spec asserted here (not whatever the code happened to do before/after):
  1. `transition --project` makes ZERO `gh project field-list` calls and
     ZERO `gh project view` calls.
  2. The new query passes owner/number/field as GraphQL VARIABLES
     (-f owner=... -F number=... -f field=...), never embedded as literal
     text inside the query string itself.
  3. Missing field / missing option / null project / a GraphQL `errors`
     response all still fail closed: non-zero exit, `gh project item-edit`
     is NEVER called, and the existing message-prefix contract is
     preserved ("transition: ... — board update FAILED for #$num").
  4. The happy path resolves the SAME field-id/project-id/option-id triple
     the old field-list-based code would have derived from an equivalent
     payload, and passes them to `gh project item-edit` unchanged.
  5. `--field Priority` (a second single-select field, exercised by
     priority_backfill.py) works identically to `--field Status`.
  6. The ambiguous (duplicate-named) field guard, added deliberately in
     f028962 (2026-08-03) as a real safety fix -- GitHub's ProjectV2 schema
     does not enforce unique field names -- still fires and still refuses
     before any write.

SCRIPT honors GH_ISSUE_SCRIPT (same convention as
test_gh_issue_create_dupe_search_failure.py) so this suite can be pointed
at a pre-fix scratch copy to prove test (a) actually goes RED without the
fix (falsifiability, runtime CLAUDE.md §6) -- see the module docstring note
in the accompanying session report for the exact invocation used.

Same harness shape as test_gh_issue_dispose.py / test_priority_backfill.py:
a fake `gh` on PATH, written in Python (via FAKE_GH_PYTHON) for the `api
graphql` branch since answering a GraphQL query by parsing its own `-f`/`-F`
variables and query text is squarely JSON/string-shape logic, and bash for
the simpler branches. Every call is logged to $GH_LOG so a test can assert
on the exact argv of every gh invocation, including the full query text
passed to `api graphql`.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = os.environ.get(
    "GH_ISSUE_SCRIPT", str(Path.home() / ".claude" / "scripts" / "gh_issue.sh")
)

# --------------------------------------------------------------------------
# Fake `gh` — a Python helper answers `api graphql` (both the field-resolution
# query this fix introduces AND the pre-existing item-id-lookup query
# `_do_transition` already made before this fix and still makes), while a
# thin bash wrapper handles every other subcommand and appends every
# invocation's raw argv to $GH_LOG (one line per call) so tests can assert on
# exactly what was called, including catching an accidental `project
# view`/`project field-list` call this fix is supposed to eliminate.
# --------------------------------------------------------------------------

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
# {"<project_number>": {"id": "PVT_x", "fields": [{"name":..., "id":...,
#   "typename": "ProjectV2SingleSelectField"|"ProjectV2Field"|..., "options": [...]}]}}

# --- the NEW field-resolution query (this fix): has `repositoryOwner` and
# `projectV2` in its text, and both `field(name:` and `fields(first:` -- the
# ambiguity-check selection rides in the SAME query.
if "repositoryOwner" in query and "projectV2" in query:
    owner = kv.get("owner", "")
    number = kv.get("number", "")
    field_name = kv.get("field", "")
    fail_mode = os.environ.get("FAKE_GRAPHQL_FIELD_QUERY_FAIL")
    if fail_mode == "errors":
        print(json.dumps({"data": {"repositoryOwner": {"projectV2": None}}, "errors": [{"message": "boom"}]}))
        sys.exit(1)
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

# --- the PRE-EXISTING item-id lookup query (unchanged by this fix): has
# `projectItems` in its text.
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
  echo "gh_stub: FORBIDDEN call: gh project view (must not be called after the #5827 fix)" >&2
  exit 1
fi
if [ "$1" = "project" ] && [ "$2" = "field-list" ]; then
  echo "gh_stub: FORBIDDEN call: gh project field-list (must not be called after the #5827 fix)" >&2
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
if [ "$1" = "project" ] && [ "$2" = "item-add" ]; then
  echo "{\"id\": \"$FAKE_ADD_ITEM_ID\"}"
  exit 0
fi
if [ "$1" = "project" ] && [ "$2" = "item-edit" ]; then
  if [ -n "${FAKE_ITEM_EDIT_FAIL:-}" ]; then
    echo "gh_stub: forced item-edit failure" >&2
    exit 1
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
    extra_fields: list[dict] | None = None,
    duplicate_status_field: bool = False,
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
        if duplicate_status_field:
            fields.append(
                {
                    "name": "Status",
                    "id": "FIELD_status_dup",
                    "typename": "ProjectV2SingleSelectField",
                    "options": [{"id": f"OPT2_{o}", "name": o} for o in status_options],
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
    if extra_fields:
        fields.extend(extra_fields)
    return {"id": project_id, "fields": fields}


def _make_env(
    tmp_path: Path,
    *,
    project_fixture: dict,
    project_number: str = DEFAULT_PROJECT,
    owner: str = DEFAULT_OWNER,
    item_already_on_board: bool = True,
    item_edit_fail: bool = False,
    field_query_fail_mode: str | None = None,
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
    env["FAKE_GH_PYTHON"] = os.environ.get("FAKE_GH_PYTHON") or _python_exe()
    env["FAKE_GRAPHQL_HELPER"] = str(helper)
    env["FAKE_PROJECT_FIELDS_JSON"] = str(fields_json)
    env["FAKE_PROJECT_ITEMS_JSON"] = str(items_json)
    env["FAKE_OWNER"] = owner
    env["FAKE_ISSUE_NODE_ID"] = issue_node_id
    env["FAKE_ISSUE_NUM"] = "1"
    env["FAKE_ADD_ITEM_ID"] = "PVTI_newly_added"
    if item_edit_fail:
        env["FAKE_ITEM_EDIT_FAIL"] = "1"
    else:
        env.pop("FAKE_ITEM_EDIT_FAIL", None)
    if field_query_fail_mode:
        env["FAKE_GRAPHQL_FIELD_QUERY_FAIL"] = field_query_fail_mode
    else:
        env.pop("FAKE_GRAPHQL_FIELD_QUERY_FAIL", None)
    return env


def _python_exe() -> str:
    import sys

    return sys.executable


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


# gh subcommand argv[0]/argv[1] pairs this stub ever logs a fresh call for —
# used to regroup a multi-line query string (the `-f query='...'` GraphQL
# argument is itself multi-line, so a naive splitlines() breaks ONE logged
# `gh api graphql ...` invocation across several "lines", each of which then
# fails a `startswith("api graphql")` check on its own).
_CALL_PREFIXES = (
    "issue comment", "issue view", "issue create", "issue list", "issue close",
    "api graphql", "project view", "project field-list", "project item-edit",
    "project item-add", "project item-list", "repo view",
)


def _log_calls(env: dict) -> list[str]:
    """Returns one string per logged `gh` invocation, with the invocation's
    full multi-line argv (including a multi-line `-f query=...` value)
    joined back into a single entry — unlike _log_lines, which naively
    splits on every newline the query text itself contains."""
    raw = Path(env["GH_LOG"]).read_text().splitlines()
    calls: list[str] = []
    for line in raw:
        if line.startswith(_CALL_PREFIXES):
            calls.append(line)
        elif calls:
            calls[-1] += "\n" + line
        # a stray line before any recognized call start is dropped — never
        # observed in practice, but never silently merged into nothing
    return calls


def _transition_args(
    *,
    num: str = "1",
    status: str = "In progress",
    project: str = DEFAULT_PROJECT,
    owner: str = DEFAULT_OWNER,
    field: str | None = None,
) -> list[str]:
    args = ["transition", num, "--status", status, "--project", project, "--owner", owner]
    if field is not None:
        args += ["--field", field]
    return args


# --------------------------------------------------------------------------
# (a) ZERO `gh project field-list` / `gh project view` calls
# --------------------------------------------------------------------------


def test_transition_never_calls_field_list_or_project_view(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress", "Done"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(), env)
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project field-list") for line in log), log
    assert not any(line.startswith("project view") for line in log), log
    # positive control: the replacement GraphQL call DID happen
    assert any(line.startswith("api graphql") for line in log), log


def test_create_triage_never_calls_field_list_or_project_view(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress", "Done"])
    env = _make_env(tmp_path, project_fixture=fixture)
    body = tmp_path / "body.md"
    body.write_text("body text")
    proc = subprocess.run(
        [
            "bash", SCRIPT, "create", "--title", "A brand new distinct finding",
            "--body-file", str(body), "--force-new",
            "--triage", "In progress", "--project", DEFAULT_PROJECT, "--owner", DEFAULT_OWNER,
        ],
        capture_output=True, text=True, env=_with_create_stub(env), timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project field-list") for line in log), log
    assert not any(line.startswith("project view") for line in log), log


def _with_create_stub(env: dict) -> dict:
    """`create` needs `gh issue create` to succeed and print a parseable URL
    -- extend the fake gh stub in place for the one test that exercises
    `create --triage` (the other tests only ever call `transition`
    directly)."""
    bindir = Path(env["PATH"].split(":")[0])
    gh = bindir / "gh"
    original = gh.read_text()
    stub = original.replace(
        'echo "gh_stub: unhandled args: $*" >&2\nexit 1\n',
        (
            'if [ "$1" = "issue" ] && [ "$2" = "create" ]; then\n'
            '  echo "https://github.com/o/r/issues/1"\n'
            "  exit 0\n"
            "fi\n"
            'echo "gh_stub: unhandled args: $*" >&2\n'
            "exit 1\n"
        ),
    )
    # (reviewer item 7): a reformatted _GH_STUB whose fallback block no longer
    # matches this literal byte-for-byte would make .replace() a silent no-op
    # -- the "issue create" branch would never actually be inserted, and this
    # test would then fail downstream with a confusing "unhandled args"
    # error instead of a clear signal that the patch target moved. Assert the
    # substitution actually happened.
    assert stub != original, "_GH_STUB's fallback block text moved -- update the .replace() target"
    gh.write_text(stub)
    return env


# --------------------------------------------------------------------------
# (b) variables passed via -F/-f, never embedded literally in the query text
# --------------------------------------------------------------------------


def test_field_query_uses_graphql_variables_not_literal_interpolation(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress", "Done"])
    env = _make_env(tmp_path, project_fixture=fixture, owner="acme-corp-test-owner")
    proc = _run(
        tmp_path,
        _transition_args(owner="acme-corp-test-owner", status="In progress"),
        env,
    )
    assert proc.returncode == 0, proc.stderr
    calls = _log_calls(env)
    graphql_calls = [c for c in calls if c.startswith("api graphql") and "repositoryOwner" in c]
    assert len(graphql_calls) == 1, calls
    call = graphql_calls[0]
    # the owner/number/field VALUES must appear only as -f/-F arguments,
    # never baked into the literal query text -- isolate just the `-f
    # query='...'` token's value by cutting the call string at the NEXT
    # standalone -f/-F flag after `query=` (each is preceded by a space and
    # the flag name, which the query text itself, all inside a single-quoted
    # heredoc-free string in the script, never produces).
    query_token_start = call.index("query=")
    query_text = call[query_token_start:]
    for marker in (" -f owner=", " -f field=", " -F number="):
        idx = query_text.find(marker)
        if idx != -1:
            query_text = query_text[:idx]
    assert "acme-corp-test-owner" not in query_text, (
        f"owner value leaked into the literal query text: {query_text!r}"
    )
    # the project NUMBER must appear only via the `$number` GraphQL variable
    # reference, never as the literal passed value "1" -- check specifically
    # for "1" appearing as a field/option NAME-shaped token the way a
    # literal-interpolation bug would produce (e.g. `projectV2(number: 1)`),
    # not as an accidental substring of the query's own static text (e.g.
    # `first: 100`, which legitimately contains "1").
    import re as _re

    assert not _re.search(r"number:\s*1\b", query_text), (
        f"project number leaked into the literal query text as a literal value: {query_text!r}"
    )
    assert "number: $number" in query_text  # the variable reference IS present
    assert "In progress" not in query_text, (
        f"field/status value leaked into the literal query text: {query_text!r}"
    )
    assert "-f owner=acme-corp-test-owner" in call
    assert "-F number=1" in call
    assert "-f field=Status" in call


# --------------------------------------------------------------------------
# (c) fail-closed: missing field / missing option / null project / GraphQL
#     errors -> non-zero, item-edit never called, prefix preserved
# --------------------------------------------------------------------------


def test_missing_field_dies_with_preserved_prefix_and_never_edits(tmp_path):
    fixture = _project_fixture(status_options=None)  # no "Status" field at all
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(field="Status"), env)
    assert proc.returncode != 0
    assert "transition: field 'Status' not found on project #1" in proc.stderr
    assert "board update FAILED for #1" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_missing_option_dies_with_preserved_prefix_and_never_edits(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "Done"])  # no "In progress"
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(status="In progress"), env)
    assert proc.returncode != 0
    assert "'In progress' is not a valid option for field 'Status' on project #1" in proc.stderr
    assert "board update FAILED for #1" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_null_project_dies_with_preserved_prefix_and_never_edits(tmp_path):
    # Fix-round note (reviewer item 5): this ALSO passes unmodified against a
    # pre-fix HEAD script (a null `gh project view` similarly dies with "could
    # not resolve project" text) -- the message match here is COINCIDENTAL
    # between old and new mechanisms, not evidence this test exercises the
    # #5827 fix specifically. It is still a genuine, valuable fail-closed
    # regression guard (a null project must never reach item-edit on EITHER
    # mechanism) -- just not one of the tests that falsifies THIS fix; see
    # test_transition_never_calls_field_list_or_project_view and the
    # totalCount>100 tests below for fix-specific RED-at-HEAD evidence.
    fixture = _project_fixture(status_options=["Backlog", "In progress"])
    env = _make_env(tmp_path, project_fixture=fixture, project_number="1")
    proc = _run(tmp_path, _transition_args(project="999"), env)  # 999 not in fixture map
    assert proc.returncode != 0
    assert "could not resolve project #999" in proc.stderr
    assert "board update FAILED for #1" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_graphql_errors_response_dies_and_never_edits(tmp_path):
    # Fix-round note (reviewer item 5): same caveat as the null-project test
    # above -- a GraphQL `errors` response causing a die is a fail-closed
    # guard worth keeping green, but it is not itself evidence that THIS
    # fix's mechanism (vs. the old one) is what's under test; it happens to
    # pass at HEAD too, coincidentally, since HEAD's `gh project view` can
    # equally fail and produce the same "could not resolve project" text.
    fixture = _project_fixture(status_options=["Backlog", "In progress"])
    env = _make_env(tmp_path, project_fixture=fixture, field_query_fail_mode="errors")
    proc = _run(tmp_path, _transition_args(), env)
    assert proc.returncode != 0
    assert "could not resolve project #1" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_ambiguous_duplicate_named_field_refused(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog", "In progress"], duplicate_status_field=True
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(field="Status"), env)
    assert proc.returncode != 0
    assert "multiple fields named 'Status'" in proc.stderr
    assert "ambiguous, refusing to guess" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


# --------------------------------------------------------------------------
# Fix-round blocker regression (2026-09-20): a project with >100 fields makes
# the names-only ambiguity-check page incomplete. `_resolve_project_and_field`
# must refuse OUTRIGHT rather than silently falling through to a write --
# the original cut set a non-numeric SENTINEL string for field_match_count
# and relied on both callers' `[[ =~ ^[0-9]+$ ]] && [ -gt 1 ]` guards to catch
# it; the sentinel fails that regex, so `&&` short-circuited and execution
# fell straight through to `gh project item-edit` on a project with two
# same-named fields past the 100-node page boundary -- a SILENT wrong-field
# write on exactly the surface this whole change protects. The fix dies
# directly inside the resolver the instant totalCount > 100 is observed, so
# there is no caller-side guard left to get wrong.
# --------------------------------------------------------------------------


def _project_fixture_with_total_count(total_count: int, *, matching_field: dict) -> dict:
    """A fixture whose FIELDS list is short (cheap to build/transmit in the
    fake harness) but whose reported `fields.totalCount` is the given large
    number -- exactly what `fields(first:100)` returns for a real >100-field
    board (GitHub pages `nodes` at 100 but always reports the true
    `totalCount`). `matching_field` is included in the (short) nodes list so
    a caller could observe it if the >100 refusal did NOT fire -- proving the
    refusal is what prevents the write, not merely an absence of the field."""
    return {
        "id": "PVT_huge_board",
        "id_totalCount_override": total_count,
        "fields": [matching_field],
    }


def _patch_helper_for_total_count_override(tmp_path: Path) -> None:
    """The stock _GRAPHQL_HELPER computes totalCount as len(fields) -- extend
    it, for this test module only, to honor an explicit
    `id_totalCount_override` key on the fixture, so a >100 totalCount can be
    simulated without actually constructing 101+ field dicts."""
    helper_path = tmp_path / "graphql_helper_totalcount.py"
    patched = _GRAPHQL_HELPER.replace(
        '"fields": {"totalCount": len(proj["fields"]), "nodes": nodes},',
        '"fields": {"totalCount": proj.get("id_totalCount_override", len(proj["fields"])), "nodes": nodes},',
    )
    assert patched != _GRAPHQL_HELPER, "_GRAPHQL_HELPER's totalCount line moved -- update the patch target"
    helper_path.write_text(patched)


def test_transition_refuses_when_project_has_over_100_fields(tmp_path):
    matching_field = {"name": "Status", "id": "FIELD_status", "typename": "ProjectV2SingleSelectField", "options": [{"id": "OPT_Done", "name": "Done"}]}
    fixture = _project_fixture_with_total_count(150, matching_field=matching_field)
    env = _make_env(tmp_path, project_fixture=fixture)
    _patch_helper_for_total_count_override(tmp_path)
    env["FAKE_GRAPHQL_HELPER"] = str(tmp_path / "graphql_helper_totalcount.py")
    proc = _run(tmp_path, _transition_args(field="Status", status="Done"), env)
    assert proc.returncode != 0
    assert "150 fields" in proc.stderr
    assert "more than the 100" in proc.stderr
    assert "refusing to guess" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_create_triage_refuses_when_project_has_over_100_fields(tmp_path):
    matching_field = {"name": "Status", "id": "FIELD_status", "typename": "ProjectV2SingleSelectField", "options": [{"id": "OPT_Done", "name": "Done"}]}
    fixture = _project_fixture_with_total_count(150, matching_field=matching_field)
    env = _make_env(tmp_path, project_fixture=fixture)
    _patch_helper_for_total_count_override(tmp_path)
    env["FAKE_GRAPHQL_HELPER"] = str(tmp_path / "graphql_helper_totalcount.py")
    body = tmp_path / "body.md"
    body.write_text("body text")
    env = _with_create_stub(env)
    proc = subprocess.run(
        [
            "bash", SCRIPT, "create", "--title", "A brand new distinct finding about the 100-field board",
            "--body-file", str(body), "--force-new",
            "--triage", "Done", "--project", DEFAULT_PROJECT, "--owner", DEFAULT_OWNER,
        ],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert proc.returncode != 0
    assert "150 fields" in proc.stderr
    assert "more than the 100" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("issue create") for line in log), (
        "nothing may be created when the >100-field ambiguity check cannot complete"
    )


# --------------------------------------------------------------------------
# Iteration-field and multi-select-field types both reach the existing
# unsupported-type `_die` arm unchanged -- cheap regression coverage that the
# new resolver's __typename plumbing doesn't accidentally widen what this
# script is willing to write to.
# --------------------------------------------------------------------------


def test_iteration_field_type_is_unsupported_and_refused(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"],
        extra_fields=[{"name": "Sprint", "id": "FIELD_sprint", "typename": "ProjectV2IterationField"}],
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(field="Sprint", status="Iteration 3"), env)
    assert proc.returncode != 0
    assert "unsupported type 'ProjectV2IterationField'" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


def test_multi_select_field_type_is_unsupported_and_refused(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"],
        extra_fields=[{"name": "Tags", "id": "FIELD_tags", "typename": "ProjectV2MultiSelectField"}],
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(field="Tags", status="urgent"), env)
    assert proc.returncode != 0
    assert "unsupported type 'ProjectV2MultiSelectField'" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


# --------------------------------------------------------------------------
# (d) happy path: item-edit receives the SAME ids the field-list-based
#     resolution would have derived
# --------------------------------------------------------------------------


def test_happy_path_item_edit_receives_correct_field_and_option_ids(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress", "Done"])
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(status="In progress"), env)
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    edit_lines = [line for line in log if line.startswith("project item-edit")]
    assert len(edit_lines) == 1, log
    line = edit_lines[0]
    assert f"--id {DEFAULT_ITEM_ID}" in line
    assert "--field-id FIELD_status" in line
    assert f"--project-id {fixture['id']}" in line
    assert "--single-select-option-id OPT_In progress" in line


def test_happy_path_adds_issue_to_board_when_not_already_on_it(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress"])
    env = _make_env(tmp_path, project_fixture=fixture, item_already_on_board=False)
    proc = _run(tmp_path, _transition_args(status="In progress"), env)
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    assert any(line.startswith("project item-add") for line in log), log
    edit_lines = [line for line in log if line.startswith("project item-edit")]
    assert len(edit_lines) == 1
    assert "--id PVTI_newly_added" in edit_lines[0]


def test_item_edit_failure_still_fails_loud(tmp_path):
    fixture = _project_fixture(status_options=["Backlog", "In progress"])
    env = _make_env(tmp_path, project_fixture=fixture, item_edit_fail=True)
    proc = _run(tmp_path, _transition_args(status="In progress"), env)
    assert proc.returncode != 0
    assert "gh project item-edit failed for #1" in proc.stderr


# --------------------------------------------------------------------------
# (e) --field Priority works as before
# --------------------------------------------------------------------------


def test_field_priority_works_identically_to_status(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog", "In progress"], priority_options=["P0", "P1", "P2"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(status="P1", field="Priority"), env)
    assert proc.returncode == 0, proc.stderr
    calls = _log_calls(env)
    graphql_calls = [c for c in calls if c.startswith("api graphql") and "repositoryOwner" in c]
    assert any("-f field=Priority" in c for c in graphql_calls)
    log = _log_lines(env)
    edit_lines = [line for line in log if line.startswith("project item-edit")]
    assert len(edit_lines) == 1
    assert "--field-id FIELD_priority" in edit_lines[0]
    assert "--single-select-option-id POPT_P1" in edit_lines[0]


def test_field_priority_missing_option_fails_closed(tmp_path):
    fixture = _project_fixture(
        status_options=["Backlog"], priority_options=["P0", "P1"]
    )
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(status="P9", field="Priority"), env)
    assert proc.returncode != 0
    assert "'P9' is not a valid option for field 'Priority'" in proc.stderr
    log = _log_lines(env)
    assert not any(line.startswith("project item-edit") for line in log), log


# --------------------------------------------------------------------------
# ProjectV2Field (free-text) branch still works — regression guard, not new
# spec: exercises the non-single-select path through the new resolver.
# --------------------------------------------------------------------------


def test_plain_text_field_type_still_writes_via_text_flag(tmp_path):
    fixture = _project_fixture(status_options=["Backlog"])  # includes a "Title" ProjectV2Field
    env = _make_env(tmp_path, project_fixture=fixture)
    proc = _run(tmp_path, _transition_args(field="Title", status="New title text"), env)
    assert proc.returncode == 0, proc.stderr
    log = _log_lines(env)
    edit_lines = [line for line in log if line.startswith("project item-edit")]
    assert len(edit_lines) == 1
    assert "--text New title text" in edit_lines[0]
