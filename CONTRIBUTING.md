# Contributing

Thanks for looking at this. It is a free project maintained by one person: read
[`SUPPORT.md`](SUPPORT.md) for what to expect (no response-time guarantee; pull requests are welcome,
test additions most of all). This page covers how to build and test a change, the two rules every
change follows, and how to report a gate that blocks something it should not.

Orientation, in the order that helps most: [`README.md`](README.md) (what is here),
[`ARCHITECTURE.md`](ARCHITECTURE.md) (how the pieces fit), [`GLOSSARY.md`](GLOSSARY.md) (the project's
own words: gate, pathspec commit, dossier, ...), [`docs/README.md`](docs/README.md) (index of every
doc) and [`docs/subsystems/gate-chain.md`](docs/subsystems/gate-chain.md), the reference for the part
most changes touch. `CSA_` is the prefix of this runtime's environment variables, a historical
acronym kept for compatibility.

## The two rules every change follows

1. **Tests assert the intended behaviour, not the current behaviour.** Write a test from the
   documented contract (the module's docstring, its page under `docs/`, the verdict the gate is
   documented to give), never by running the code and copying what it prints. If the code disagrees
   with the contract, fix the code; a test that snapshots a bug locks the bug in. A bug fix comes with
   a regression test, and you should have seen that test fail without your fix before you say it is
   done: revert the fix in a scratch copy of the one file, confirm the test goes red, restore it, and
   confirm it goes green. A test that asserts a refusal needs a partner that asserts the way back (a
   gate that denies X is paired with a test that the allowed shape still passes).
2. **Docs travel with the change.** If a change alters behaviour, a flag, an environment variable, an
   output format or a gate's verdict, update the doc that describes it in the same pull request: the
   module docstring, the matching page in `docs/subsystems/`, the `--help` text, any README table that
   quotes the number. A pull request that changes behaviour and leaves its docs stale is unfinished.

Do not make a failing check pass by silencing it (`# noqa`, `--no-verify`, a skip with no stated
reason, an assertion loosened to match output). Fix the cause, or open an issue.

## What you need

- `git`, `bash`, `tar`
- Python 3.9 or newer. 3.9 is the supported floor (`requires-python` in `pyproject.toml`, ruff
  `target-version = "py39"`), so do not use syntax or library calls newer than that.
- Node.js 20 or newer, for the single `workflows/tests/*.mjs` test.
- For lint: `ruff` 0.15.18 and `shellcheck`. `pre-commit` is optional (see below).
- The Python test packages (`pytest>=8`, `pytest-cov`, `jsonschema`, `detect-secrets==1.5.0`) are
  declared in `pyproject.toml` under `[project.optional-dependencies]` (`test`; `ruff` is in `lint`).
  `scripts/ci_layout.sh` installs them into its own virtual environment, so you do not install them
  yourself. `pyproject.toml` is not a package definition: `packages = []`, and nothing runs
  `pip install .`.

## Running the tests the hermetic way: `scripts/ci_layout.sh`

The runtime is a *deployed shape*. Hooks find each other through `$HOME/.claude`
(`hooks/_lib.py` sets `CLAUDE_DIR` there, `settings.json` wires every hook by that path, `bash_gate.sh`
runs `$HOME/.claude/hooks/pretooluse_bash.py`), and many test files read `Path.home() / ".claude"` on
purpose. Run from a clone anywhere else, hundreds of tests would fail with
`~/.claude/scripts/<x>.sh: No such file`, which says nothing about your change. So the suite refuses to
start there: `hooks/tests/conftest.py` aborts the session (exit 2) with a pointer to
`scripts/ci_layout.sh` (details under "Why the test suite refuses to run from a foreign checkout" below).

`scripts/ci_layout.sh` builds the shape the tests were written against, the same way every time, without
touching your real `~/.claude`:

```
<layout root>/                  a dedicated directory; the parent of --home
  .ci-layout-root               marker: the siblings below are the script's to manage
  home/                         $HOME for the run, outside /tmp and /private/tmp
    .ci-layout                  marker: this directory is the script's to rewrite
    .claude/                    `git archive HEAD` of your checkout, extracted with tar
      projects/                 created empty (it exists on every real install)
      live-testing/allowlist.json         seeded from allowlist.example.json, if absent
      knowledge/protected_boards.json     seeded from its .example.json, if absent; the
                                          example ships with an empty `boards` list, so nothing
                                          is protected until you list boards
  venv/                         pytest, pytest-cov, ruff, jsonschema, detect-secrets
  pytest-tmp/                   pytest --basetemp: a sibling of home, not under it
```

Typical loop. Only **committed** content reaches the layout (it is built from `git archive HEAD`;
uncommitted tracked changes are reported, not copied), so commit first:

```bash
git commit -m "fix(scope): summary" -- path/one path/two
bash scripts/ci_layout.sh --refresh --run      # re-extract HEAD, then run the whole battery
```

The first build creates the virtual environment and needs network access for `pip`. A later build for
a different commit is refused unless you pass `--refresh`; the same commit is simply reused.

| Flag | What it does |
|---|---|
| `--home DIR` | Layout home. It must be named `home`, inside a directory of its own. Default `~/.cache/ci-layout/home`. |
| `--python PATH` | Interpreter for the virtual environment (default `python3`, must be 3.9 or newer). A venv is tied to one Python version: test another one with a second `--home`, for example `--home ~/.cache/ci-layout-py39/home --python python3.9`. |
| `--refresh` | Delete and re-extract the layout's `.claude` from `HEAD`. Only done after the `.ci-layout` marker is proven present. |
| `--run` | After building, run the full battery inside the layout and exit non-zero on any failure or on a location that ran zero tests. |
| `--skip-install` | Create or install nothing (no venv, no `pip`). A debug aid; `--run` then needs an existing venv. |
| `--system-deps` | Allow ONE privileged step: installing `jsonschema` for `/usr/bin/python3`, because `scripts/codex_review.sh` hardcodes that interpreter. Without `--system-deps`, or `CI=true` in the environment, nothing is escalated; a shell that exports `CI=true` gets the system install without asking. When nothing is escalated, the script prints the exact command, prefixed `ACTION NEEDED`, and carries on (the codex-review tests then fail with `validator-unavailable` until you run it). |
| `--min-hooks N`, `--min-gtm N`, `--min-node N` | With `--run`: the number of tests each location must actually execute (see `--help` for the defaults). A location that executes fewer, or zero, fails. If your change removes tests on purpose, say why in the pull request rather than lowering a floor silently. |

`--run` runs, from the layout, in this order: `pytest hooks/tests -m "not live_machine"`,
`pytest tools/gtm/tests`, `pytest live-testing/tests` (when that directory exists), every
`hooks/tests/*.sh`, and `node --test` on `workflows/tests/test_issue_wheel_triage.mjs`. Results land
beside the layout (`junit-*.xml`, `sh-*.log`, `node-test.log` in the layout root).

Why each part of the layout exists (so you can tell a layout problem from a code problem):

- **`$HOME` outside `/tmp`.** `agentarch_metric_check.py` treats `/tmp` as an always-safe root; a
  `/tmp` home would silently change what it flags.
- **`--basetemp` is a sibling of home.** Not under `/tmp` (same reason), and not under `$HOME`:
  `repo_manifest.py` stores registry roots relative to `$HOME`, so a `tmp_path` under it breaks
  `test_register_preserves_root_sharing_alias`.
- **`jsonschema` for `/usr/bin/python3`.** See `--system-deps` above.
- **`TZ=UTC`.** CI runners run in UTC; your machine's zone must not decide a time-based assertion.
- **A scrubbed environment, stdin from `/dev/null`.** Inside the layout `CSA_*`, `CLAUDE_*`,
  `PYTEST_*`, `PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV` and `CONDA_*` are unset, and there is no
  `.enforce` marker and no state directory, so the hooks run in log-only mode and your shell cannot
  leak into an assertion.

To run a single test file inside the layout, enter it the way the build prints it ("Enter it exactly
like this"; the paths are filled in for you). In a subshell, so your own shell keeps its `HOME`:

```bash
( cd <layout root>/home/.claude \
  && export HOME=<layout root>/home TZ=UTC PATH=<layout root>/venv/bin:"$PATH" \
  && export PYTEST_ADDOPTS="--basetemp=<layout root>/pytest-tmp -p no:cacheprovider" \
  && python -m pytest hooks/tests/test_lib.py -q -m "not live_machine" </dev/null )
```

The `live_machine` marker tags slow smoke tests that read the telemetry of the machine they run on;
they are deselected by default and skip themselves when those sources are absent. You do not need them.

### The safety rails

A wrong `--home` could extract `HEAD` over a live runtime and destroy uncommitted work, so the script
refuses (exit 3) instead: when the layout home or its parent is, contains, or lies inside a real
`~/.claude` (checked by resolved path and by file identity, so a case variant or a firmlink does not
get past it); when it overlaps the checkout being archived; when it is under `/tmp` or `/private/tmp`;
when the current directory is inside a real `~/.claude`; when the home, a `.claude`, a marker, `venv/`
or `pytest-tmp/` is a symlink; when the home exists, is not empty and has no `.ci-layout` marker; and
when the layout root holds a `venv/`, a `pytest-tmp/` or earlier result files but no `.ci-layout-root`
marker (pip would install into that venv, and pytest wipes its `--basetemp` on every run). If you have
a directory from an older run that you know is yours, create the marker file yourself. Exit codes:
`0` ok, `1` failure, `2` usage error, `3` a rail refused.

## Why the test suite refuses to run from a foreign checkout

`hooks/tests/conftest.py` aborts the whole session, exit code 2, with a pointer to `scripts/ci_layout.sh`
when `realpath(<checkout>)` is not `realpath($HOME/.claude)`. The abort exists because a run from the
wrong place fails with noise that reads as product bugs; it has already led to a misdiagnosis.

If you really mean to run there (running the mutation battery,
`hooks/tests/precommit_review_mutation_battery.py`, or a second working tree of this repository), the
opt-out is exactly:

```bash
CSA_TESTS_ALLOW_FOREIGN_ROOT=1 python3 -m pytest hooks/tests/test_lib.py -q
```

It removes the abort, not the coupling: expect deployed-shape failures, and do not report them. Do not
use it to get a green run for a pull request; use `scripts/ci_layout.sh`.

## Running the tests inside a live runtime: `hooks/run_tests.sh`

If your checkout *is* your `~/.claude`, `bash hooks/run_tests.sh` (from any directory) runs four
locations in order and stops at the first failure: `hooks/tests` (with a per-module coverage table
when `pytest-cov` is importable), `tools/gtm/tests`, every `hooks/tests/test_*.sh`, and the node test.
Unlike `ci_layout.sh --run`, it does not run `live-testing/tests`. A location that runs zero tests, or a
node test that passes fewer than its floor, is a failure. It needs `bash`, a `python3` with `pytest`,
and `node`; there is no GNU `timeout` dependency and no network. The environment variables it reads,
all optional:

| Variable | Effect |
|---|---|
| `PYTHON` | Interpreter to use (default `python3`). |
| `RUN_TESTS_LIVE_MACHINE=1` | Include the slow `live_machine` smoke tests (default: deselected). |
| `RUN_TESTS_SKIP_NODE=1` | Skip the node location when `node` is not installed (otherwise a missing `node` is a failure). |
| `PYTEST_ADDOPTS` | The standard pytest variable, applied to both pytest locations. Use it to move pytest's temp directories: by default they live under the system temp directory (`/tmp` on Linux), which `agentarch_metric_check.py` treats as an always-safe root, so its tests assert something different there. Point it at a dedicated directory outside `/tmp` and outside `$HOME`, for example `PYTEST_ADDOPTS="--basetemp=/var/tmp/csa-pytest-tmp" bash hooks/run_tests.sh`. pytest **clears** that directory on every run, so never use one that holds anything else. |

Known failure with the default temp directory: when pytest's temp dir is under `/tmp`,
`test_split_redirect_target_denies_pathspec_outside_repo` (in `hooks/tests/test_precommit_review_gate.py`)
fails; it passes with `--basetemp` outside `/tmp`, which is what `ci_layout.sh` does. Fixing the test is
a tracked follow-up; please do not report it as a regression.

For a pull request, use `scripts/ci_layout.sh`; it is the isolated one.

## Static checks

A GitHub Actions workflow that runs these on every pull request is planned (see "Known gaps" in
[`CHANGELOG.md`](CHANGELOG.md)). Until it lands, run them yourself and say so in the pull request.

- **Lint.** `ruff check .` must report nothing. The configuration is in `pyproject.toml`: ruff's
  default rule set spelled out (`E4`, `E7`, `E9`, `F`), `target-version = "py39"`, `line-length = 100`.
  Fix findings by hand and read any autofix before you commit it. A wider rule set is a planned,
  measured follow-up, not something to sneak in with a feature.
- **Format.** `ruff format --check` must be clean. Formatting the whole tree is deferred to one
  dedicated commit, so the files that pass would change are listed in `[tool.ruff.format] exclude`
  (generated, never hand-edited; the regeneration recipe is in `pyproject.toml`). Format *new* files;
  leave the listed ones alone in a feature pull request so blame stays readable.
- **Peer-held paths.** `[tool.ruff] extend-exclude` names the few files another in-flight change holds;
  they are skipped by lint until that change lands. They are listed in `CHANGELOG.md` under "Known gaps".
- **Shell.** `shellcheck -S warning` over every shell script (`scripts/legacy/`, which is not shipped
  here, and `scripts/codex_review.sh`, held by the same in-flight change, are skipped):

  ```bash
  find . -name '*.sh' -not -path './.git/*' -not -path './scripts/legacy/*' \
    -not -path './scripts/codex_review.sh' -print0 | xargs -0 shellcheck -S warning
  ```

- **Guard wiring.** `python3 scripts/check_guard_wiring.py` checks, against the checkout it lives in,
  that every hook `settings.json` wires points at a file that exists, that the live-testing allowlist
  parses and carries its required keys, and that every hook module able to emit a `PreToolUse` deny is
  reachable from something `settings.json` wires. It prints how many guard modules it examined and
  exits non-zero on any problem (or if it examined none).
- **Agent roster.** If you add or change an agent definition under `agents/`, regenerate the roster
  with `python3 scripts/gen_agent_index.py` (it reads the agent frontmatter,
  `knowledge/model_policy.json` and `knowledge/agent_meta.json`, and fails when they disagree);
  `--check` reports a stale `docs/agents/README.md` without writing anything.
- **pre-commit, for your own clone.** `.pre-commit-config.yaml` pins ruff 0.15.18 and shellcheck
  0.11.0 (the `shellcheck-py` package at `v0.11.0.1`), and adds `check-json` and `end-of-file-fixer`.
  Use those versions locally so your results match. Install it in the clone you prepare a pull
  request from (`pipx install pre-commit`, then `pre-commit install`). Do not install it in a live
  `~/.claude`: the runtime's own commit gates are the `PreToolUse` hook chain, not the pre-commit
  framework.

## Making a change

- **One logical change per commit and per pull request.** Smaller is easier to review and to revert.
- **Path-scoped commits.** Name the paths you mean, every time:

  ```bash
  git add path/new_file.py                          # new files only; tracked edits need no add
  git commit -m "fix(gate): summary" -- hooks/the_gate.py hooks/tests/test_the_gate.py
  ```

  Never `git add -A`, `git add .` or `git commit -a`: they sweep up files you did not author. This
  repository's own gate chain blocks those shapes when it is installed and enforcing, which is exactly
  why contributors are asked to work the same way. Run `git status` before you push and leave out
  anything you did not write.
- **Commit subjects** read `type(scope): summary`, 72 characters or fewer; types are `feat`, `fix`,
  `docs`, `style`, `refactor`, `test`, `chore`. A short body saying what changed and why helps.
- **A change to a gate or hook includes its tests in the same pull request.** Every gate has its own
  test file under `hooks/tests/`; follow its neighbours. Cover the deny and the matching allow. Whether
  a gate fails open or fails closed on its own error is part of its contract, so if your change moves
  that line, say so in the pull request and update `docs/subsystems/gate-chain.md`.
- **Hooks run on every tool call of everyone who installs them.** Gates fail open on their own errors
  by design, but a syntax or import error in a shared module such as `hooks/_lib.py` stops all of
  them. Run the module's tests and `python3 -m py_compile` on what you touched before you push.
- **Tests never touch the real `~/.claude`.** Use the `sandbox` fixture from `hooks/tests/conftest.py`
  (a throwaway `~/.claude` under `tmp_path`); it also clears the `CSA_*` variables the suite controls
  (the `clean_env` fixture), so a stray one in your shell cannot change an assertion.
- **argparse help strings:** a literal `%` must be written `%%`. Python 3.14 rejects the unescaped form
  when the argument is added, which crashes `--help`.
- **No real identifiers in code, tests, fixtures or docs.** Use placeholders (`example.com`,
  `/Users/x/`, `<your-repo>`); no credentials, tokens, personal data, customer names or internal
  hostnames, even in a test.

By opening a pull request you agree that your contribution is licensed under the repository's
[MIT licence](LICENSE).

## Reporting a gate false positive

A *false positive* is a gate denying a command or dispatch that its documented rules say is allowed.
Open a GitHub issue with:

1. **The gate and the reason.** The deny reason it printed (for example `missing-pathspec`,
   `bulk-pathspec`, `unreviewed-commit`, `pin-tier-mismatch`) and the module it belongs to
   (`hooks/precommit_review_gate.py`, `hooks/model_pin_gate.py`, ...).
2. **The exact command or dispatch** that was denied, and the sentence in the docs that says it should
   have been allowed.
3. **The mode.** Enforcing (a `~/.claude/.enforce` file, `CSA_ENFORCE=1`, or a `.claude/.csa-enforce`
   marker file at the root of the repository the command ran in) or log-only, where the Bash and Task
   gates only record a `would-block` row and allow the command. (`CSA_DISABLE_HOOKS=1` switches the
   hooks off entirely and overrides all of these.) See
   [`docs/subsystems/gate-chain.md`](docs/subsystems/gate-chain.md).
4. **The decision rows** from `~/.claude/.enforcement/log.jsonl` (one JSON object per decision). They
   can contain parts of the command, so read them and trim anything private before you paste.
5. **Your environment:** OS, `python3 --version`, `git --version`, and the commit of this repository.

The most useful report is a failing test: a case in the gate's own test file under `hooks/tests/` that
asserts the verdict you expected, and fails today. If you can also fix it, send the test and the fix
together. The gate's escape hatch for getting unblocked meanwhile is documented in `gate-chain.md`;
please do not remove a hook from `settings.json` wholesale.

The reverse, a gate **letting through** something it should block, is a *false negative*. When an agent
or injected content could trigger it, report it privately as a security issue: see
[`SECURITY.md`](SECURITY.md).

By taking part you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
