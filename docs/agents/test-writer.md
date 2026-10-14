# test-writer

`test-writer` is the runtime's dedicated test-authoring sub-agent: it writes unit, integration,
and E2E tests that assert *intended* behavior pulled from a spec source, never tests that merely
snapshot whatever the code currently does. It exists to enforce `~/.claude/CLAUDE.md` §6 as a
structural guarantee rather than a hope — a "lock-in test" (one that encodes current, possibly
wrong, behavior) is treated as a regression, and this agent's entire design is built around not
producing one.

## Model & tools

- **Model:** `sonnet` (`agents/test-writer.md` frontmatter, `model:`)
- **Tools:** `Read, Edit, Write, Bash, Glob, Grep` (`agents/test-writer.md` frontmatter, `tools:`)

Identical tool grant to `implement` — this is the other of the two dev-workflow agents allowed to
create/modify files. Its `Bash` grant is for running the test suite it just wrote and for the two
mandatory tool checks described below (the test-quality scanner and `verify_fix`), not for git or
formatting.

## When it's dispatched

Per its own definition: "**Test-writer follows `implement`:** every code change gets paired tests in
the same commit/PR — in parallel when covering already-committed code, else immediately after
implement" (`agents/test-writer.md`, "## Coverage and pairing"). So it is dispatched either right
after `implement` finishes a change (the common case), or independently when a session is
backfilling coverage for code that already exists. `~/.claude/CLAUDE.md` §5 makes this a hard
requirement, not a nicety: "Code change → paired tests in the same commit/PR (§6, and test-writer
follows implement)."

## What it does

It is handed the target code, the spec source, and the project's test locations by the
orchestrator. Its core discipline: **read the spec first** — "contract/schema, README, docstring,
route helper, or user story — NOT the just-written implementation" — and author assertions from
that, not from what the code happens to output. If the implementation contradicts the spec, it does
not encode the wrong behavior into a passing test; it reports the mismatch so the code gets fixed.
If it ever wrote an assertion by running the code and snapshotting the result, its own definition
calls that out by name as a lock-in test to be rewritten (`agents/test-writer.md`, "## Assert
INTENDED behavior, not current behavior (the core rule)").

Two pairings are non-negotiable (`agents/test-writer.md`, "## Required pairings (non-negotiable)"):
- A test asserting a **redirect/gate** (sign-in wall, get-started flow, license wall) must be paired
  with a test proving the user can leave that page and reach the originally intended state.
- A test asserting an **auth/permission failure** must be paired with a test asserting recovery.
- A lone redirect assertion or a bare 403 with no recovery test is explicitly forbidden.

It covers happy path and error cases, writes contract tests for new/changed API routes (methods,
status codes, request/response shapes), and is told to extend one comprehensive file per component
rather than scattering small overlapping files (`agents/test-writer.md`, "## Coverage and pairing").
Because "extend the existing file" is exactly the shape that collides with another agent doing the
same, the card carries the same two multi-agent rules as `implement`: **stay in your partition**
(edit only the assigned test files; report rather than reach outside them) and **contested file →
yield** (a test file mid-edit by another agent gets set aside, not forced through — progress other
work and poll). A new test file or suite also carries its own same-change doc obligation: it must be
registered in the repo's harness index in that same change, using the index named by the repo
grounding dossier or, failing that, the repo's own `CLAUDE.md`/docs hierarchy; if neither names one,
the agent must not invent a path — it reports the registration as a required doc update naming the
suite it added (`agents/test-writer.md`, "## Coverage and pairing").

Unit tests must be fully isolated (no network, no real DB, no shared mutable state); it must not
mock the project's own services/controllers, only genuine third-party boundaries, and where the
project forbids mocking a dependency, a missing key must make the test **fail**, never skip. Like
`implement`, it must never suppress a test to get it green — no `# noqa`, `type: ignore`, or
xfail-to-hide (`agents/test-writer.md`, "## Isolation and honesty").

## Prove it before you report it — two mandatory tool checks

This is the part of the agent that changed most recently, and it is the part most worth knowing.
Falsifiability here is **no longer a prose self-report — it is a tool verdict**
(`agents/test-writer.md`, "## Assert INTENDED behavior, not current behavior (the core rule)").
Two mechanical checks run before the agent writes its report; neither is optional and neither may
be replaced by the agent's own narration, and both run from the root of the repo being worked in
(`agents/test-writer.md`, "## Prove it before you report it (MANDATORY — both checks, every time)").
Where the invocations live is itself grounded: the repo's `.claude/oversight/dev-runtime.md`
test-quality digest, if it carries one, names that repo's exact commands and wins over the default
paths below — and the agent must confirm the file exists before claiming to have run it. That
override is scoped to paths and test commands only: it never overrides the absolute-interpreter
requirement for `--python` below, even when the dossier's own sanctioned snippet shows a relative
shorthand — the agent resolves that shorthand to an absolute path before running it.

### 1. Scanner self-check — its own output, graded

```
python3 repo_tooling/test_quality/scan.py delta -- <every test file written or edited>
```

(`agents/test-writer.md`, "### 1. Scanner self-check — your own output, graded". The path is
ExampleApp's; `repo_tooling/test_quality/scan.py` confirmed present there 2026-08-31.)

`delta` reports only what the pending change itself introduces and **always exits 0 by design**, so
the exit code is meaningless — the printed output is the result. A clean run prints *nothing at
all*, which makes silence structurally ambiguous: a path the tool never scored looks byte-for-byte
identical to one it scored and found clean. A violation line may itself carry a trailing
`[outside the snapshot roots -- reported here, never recorded in the ledger]` tag when the file sits
outside the scanner's tracked roots — the finding is still real and still must be fixed; the tag only
means it won't trend in the ledger later, never "not a real finding." The agent therefore may not read an empty delta as
"clean" until it has confirmed, per path, that the input was actually scored — that the file
exists, that it matches the scanner's Python test-file pattern (`test_*.py` / `*_test.py`, no
excluded path segment such as `node_modules`, `__pycache__`, `.claude`, `worktrees`, `.venv`,
`site-packages`), and that it resolves under the repo root of the `scan.py` actually invoked (the
live failure mode: working in a `.claude/worktrees/` checkout while invoking the main tree's
scanner, where every file scores a byte-identical "clean"). Its report names which paths it
confirmed were scanned, never just "delta clean".

Non-Python test files — `.test.ts`, `.test.tsx`, `.spec.ts`, `.spec.tsx`, Playwright specs — are
deliberately out of scope, so **a frontend-only change gets no mechanical self-check at all**; that
must be reported as N/A with the reason, followed by an actual hand-check against the A–C list:

- **A — vacuous:** no assertion at all; `assert True`, or a lone `assert x is not None` /
  `isinstance` / `len(x) >= 0` as the only assertion; a commented-out `# assert`.
- **B — weakened:** `status_code in (...)` instead of the one status the spec names; `xfail`
  without `strict=True`; `pytest.mark.skip` with no `reason=`.
- **C — lock-in shape:** equality against a long magic literal; an assertion against a loaded
  golden/baseline artifact with no citation of the spec, issue, or standard section that makes that
  golden correct; `@patch` aimed at the module under test rather than a true external boundary.

Crucially, **a Category A–C violation in its own output is a defect it must FIX before reporting,
not a finding it hands back** — the agent does not return test files that the repo's own lock-in
detector flags. And the scanner is the mechanical **floor, not the ceiling**: a clean delta does not
license a lock-in test, because the spec rule at the top of the definition still governs.

### 2. Falsifiability — a `verify_fix` verdict, not a claim

```
python3 repo_tooling/scripts/verify_fix.py \
    --python "<ABSOLUTE path to the dossier's interpreter>" \
    --test "pytest <the new tests>" \
    --paths <the production files this change touches>
```

`--python` is mandatory, not decorative: it defaults to `sys.executable`, so under a scheduled
job's PATH it becomes an interpreter that has pytest but not the repo's dependencies — the suite
dies on `ImportError` and the run reports `CLAIM_FALSE`, i.e. a correct change reported as a false
claim, unattended. A *relative* `.venv/...` path cannot substitute: the sandbox is a
tracked-files-only `git clone --shared` and `.venv` is gitignored, so it resolves to nothing.

(`agents/test-writer.md`, "### 2. Falsifiability — a verify_fix verdict, not a claim".
`repo_tooling/scripts/verify_fix.py` confirmed present in ExampleApp 2026-08-31.)

It clones the repo into a throwaway sandbox at `--base` (default `HEAD`), reverts the in-scope
production files **in the sandbox**, and re-runs the tests there — the revert never touches the
shared tree, which is what makes this safe under §2's multi-agent rules. `--paths` must name the
agent's own files (omitting it judges every file changed vs base, wrong in a tree where other
agents have in-flight edits).

The report must carry the **literal verdict string**:

| Verdict (exit) | Meaning | What the agent must do |
|---|---|---|
| `PROVEN` (0) | Green with the fix, RED without it, every changed line ran | Report it — the only clean result |
| `PARTIAL` (1) | Falsifiable overall, but a changed file is unguarded or a changed line never ran | Name them; close them and re-run, or declare UNVERIFIED for exactly those files. Never reported as done |
| `FALSE_ALLCLEAR` (2) | Tests pass identically with the fix REVERTED — the test cannot fail | **HARD STOP** — the exact failure this step exists to catch; rewrite the test |
| `CLAIM_FALSE` (3) | Tests do not pass even with the fix applied | Rule out a wrong interpreter FIRST (an `ImportError` on a repo dep, or exit 127, is environmental, not a bad fix); only a real assertion failure makes this a **HARD STOP** |
| `ERROR` (4) | The harness itself could not run | Not a verdict: report UNVERIFIED with the harness's verbatim error |
| `NOTHING_TO_FALSIFY` (5) | No production files were in scope — nothing was reverted | Not a pass: fix `--paths`, or (tests-only work) break the asserted behavior in a scratch copy and confirm RED |
| `STALE_BUNDLE` (6) | A leg flagged its compiled input as out of sync with its source | Re-run with the right `--setup` recompile (and `--carry`) |

If `verify_fix` cannot be run at all — absent in the repo, or no runnable test command exists — the
agent reports **UNVERIFIED with the reason** and does the revert-and-rerun by hand, never in the
shared tree and always in a REAL scratch copy (`cp -R`, never `cp -al`, which shares inodes and
mutates the shared tree). The revert itself is content-level — `git show <base>:<path> > <path>` or
`git apply -R <the diff>` — never `git checkout`/`git restore` against the working tree: the
state-verb guard strips a leading `git -C <dir>` before it inspects the subcommand, so pointing that
same blocked verb at a scratch copy doesn't evade it. The governing line: *an honest UNVERIFIED
always beats a green you have not falsified.*

Both verdicts are part of the deliverable — the scanner self-check result (clean with the confirmed
paths / N/A for non-Python files / the exact path checked and why the scanner could not run) and
the literal `verify_fix` verdict. The report also carries **Grounding** (the dossier was read, or was
missing and what the agent fell back to) and **Flags raised** (code contradicting the spec, a
lock-in test found in already-existing test files, or a schema/signature surprise) — both mandated
elsewhere in the card (the spec-contradiction and missing-dossier rules). **A report missing either
verdict is incomplete**
(`agents/test-writer.md`, "## Report").

## Grounding / inputs

Reads `<repo>/.claude/oversight/dev-runtime.md` first if present — here it's specifically the
repo's "test commands, placement, and spec docs", and (per the section above) any test-quality
digest naming this repo's exact scanner/verify_fix invocations. Missing dossier → report that fact
and fall back to the repo's own `CLAUDE.md`/config, "never invent a command, path, or spec doc"
(`agents/test-writer.md`, the "**Repo grounding.**" paragraph). Same shared mechanism as every
other agent in this slice.

## Boundaries — what it will NOT do

- **No formatting, no git.** "Never run a formatter by hand (it clobbers concurrent in-flight
  edits). Your edits are dispatched work and may never trigger a PostToolUse format hook, and not
  every repo has one — list the files you wrote in your report so the orchestrator can have
  formatting applied. Do not commit/push or run any git write op; never checkout/switch/stash/reset.
  Report results; the orchestrator handles git." (`agents/test-writer.md`, "## Not yours") — this
  runtime has no Edit/Write-triggered format hook of its own; a product repo may or may not, and
  dispatched sub-agent work bypasses PostToolUse regardless, so the agent's own list of files
  written is what lets the orchestrator get formatting applied.
- **No guessing on an unclear spec.** "If the spec is unclear, report the ambiguity to the
  orchestrator and leave that test unwritten — do not guess." (`agents/test-writer.md`, "## Assert
  INTENDED behavior, not current behavior (the core rule)")
- **No lock-in tests, ever** — this is the agent's defining constraint, not an incidental rule, and
  it is now backed by a scanner run against the agent's own output.
- **No shipping a scanner violation as a "finding"** — a Category A–C hit in its own new tests is
  fixed, not reported.
- **No unfalsified green.** It may not report work complete on `FALSE_ALLCLEAR`, `CLAIM_FALSE`, or
  a bare `PARTIAL`.
- **No mocking the project's own code**, and no silently skipping a test over a missing required
  key when the project mandates real test credentials.

## How it fits with other agents

Sits directly downstream of `implement` in the standard change pipeline, and can run in parallel
with it when backfilling tests for already-committed code (rather than strictly sequenced). Its
output — plus `implement`'s — is what `test-runner` subsequently verifies, and what
`code-reviewer` inspects before a commit: `~/.claude/CLAUDE.md` §5/§10 explicitly call out that the
reviewer "flags lock-in tests (assert-current) and missing doc/help updates," which is the same
failure mode `test-writer` is designed to prevent at authoring time. The scanner it self-checks
against is the same deterministic sensor `test-architect` reads at the monthly audit — test-writer
runs `delta` on its own pending output, test-architect interprets the ledger's snapshot deltas
across the whole suite (`agents/test-architect.md`, "## Read FIRST" item 4) — so the two meet the
same rule set at two different scales. It never commits its own work; that's `git-ops` (or the
reviewing orchestrator, per the gate-3b seam described in `git-ops`'s own doc).

## Example invocation

After `implement` lands a fix so that an expired license correctly blocks a paid feature, the
orchestrator dispatches `test-writer` with the licensing spec, the changed file, and the test
directory — expecting back a test that asserts the block AND a paired recovery test (renewing the
license restores access), not just a lone "returns 403" assertion — plus a scanner self-check
naming the paths confirmed scanned and a literal `PROVEN` verdict from `verify_fix`. A returned
`FALSE_ALLCLEAR` would mean the new test passes even with the licensing fix reverted, and the work
is not done.
