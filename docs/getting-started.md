# Getting started with this runtime bundle

This is a **product-agnostic operating layer** for Claude Code agents — the dev-workflow roster,
the git safety gates, the review ladder, the standing oversight roster, THE ISSUE WHEEL, and the
GTM department. It defines *how* agents work; it never carries product code or product facts. See
the top-level [`README.md`](../README.md) for the full map of what's in here — this doc is the
"clone it and stand it up against my own repo" path.

## 1. Put the runtime in place

The hooks are wired by the path `~/.claude/hooks/...`, so the runtime has to be reachable at `~/.claude`. Claude Code
also reads `CLAUDE.md`, `agents/` and `settings.json` from there in every session. The hooks create and write
machine-local state directories under `~/.claude` (`.review_state/`, `.file_claims/`, `.agent_budget/`,
`.enforcement/`, `.model_exceptions/`); this repository's `.gitignore` already ignores them. Pick the case that matches
your machine; both set `RUNTIME`, which every later step uses. `<repository-url>` is this repository's own HTTPS clone
URL (the Code button on its GitHub page); the README's Install section prints the full command.

**A. `~/.claude` does not exist yet** (a machine that has never run Claude Code). Clone into place:

```
git clone <repository-url> ~/.claude
export RUNTIME=~/.claude
```

The `settings.json` in the clone already wires the hooks, so skip to *Before you turn enforcement on* below.

**B. `~/.claude` already exists** (any machine that has run Claude Code; `git clone` into a non-empty directory
fails). Clone beside it and merge by hand:

```
git clone <repository-url> ~/.claude-runtime
export RUNTIME=~/.claude-runtime CLAUDE_DIR=~/.claude-runtime
```

`CLAUDE_DIR` tells a script which directory is the runtime; without it they use `$HOME/.claude`. The scripts that
read it include `init_repo.sh`, `repo_manifest.py`, `lane.sh`, `disk_janitor.sh`, `agent_router.py`,
`agent_obligations.py` and `bundle_parity.py`. The gates (`bash_gate.sh`, `pretooluse_bash.py`, `pretooluse_task.py`,
`model_pin_gate.py`) never read it: they always use `$HOME/.claude`. Here it makes `init_repo.sh` and
`repo_manifest.py` find their templates in the clone. Keep it set for steps 2 to 8 in this shell, and
**`unset CLAUDE_DIR` before you start Claude Code**: a session that inherits it points `lane.sh`, `disk_janitor.sh`
and the router hooks (if you wired them) at the clone instead of your real `~/.claude`.

An installer script that does the merge is planned for the next release; today it is manual:

1. Copy in the files the gates need. `--ignore-existing` keeps every file you already have; diff any same-named file
   against `$RUNTIME` yourself before deciding to take the new one.

   ```
   mkdir -p ~/.claude/knowledge
   rsync -a --ignore-existing "$RUNTIME/hooks/" ~/.claude/hooks/
   rsync -a --ignore-existing "$RUNTIME/agents/" ~/.claude/agents/
   cp -n "$RUNTIME/knowledge/model_policy.json" ~/.claude/knowledge/
   ```

   The agents' primers and reference corpora live in `$RUNTIME/knowledge/`; copy that directory across the same way
   if you want the agents grounded rather than only pin-checked.

2. Merge the hook wiring into `~/.claude/settings.json`. Add these entries to the matching arrays under `hooks`
   (create an array that is missing). Do not replace your file. `$RUNTIME/settings.json` carries the full wiring.

   ```json
   {
     "hooks": {
       "PreToolUse": [
         {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/bash_gate.sh"}]},
         {"matcher": "Task", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/pretooluse_task.py"}]},
         {"matcher": "Workflow", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/workflow_model_gate.py"}]}
       ],
       "PostToolUse": [
         {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/post_bash_gate.sh"}]},
         {"matcher": "Task", "hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/agent_budget.py release_hook"}]}
       ],
       "PostToolUseFailure": [
         {"matcher": "Bash", "hooks": [{"type": "command", "command": "bash ~/.claude/hooks/post_bash_gate.sh"}]}
       ],
       "SubagentStop": [
         {"hooks": [{"type": "command", "command": "python3 ~/.claude/hooks/agent_budget.py release_hook"}]}
       ]
     }
   }
   ```

   The Bash `PostToolUse` and `PostToolUseFailure` entries release the file claims a commit took; without them a
   claim lingers until its timeout. The `Task` and `SubagentStop` entries record each dispatch's completion in the
   spend ledger (`~/.claude/.agent_budget/spend.jsonl`) and release its pacer lease when `CSA_PACER=1`.

3. Copy the permission rules. A `git push` is gated by `permissions.ask`, not by the hooks. From
   `$RUNTIME/settings.json` copy at least `Bash(git push:*)` and `Bash(git push)` from `permissions.ask`, and from
   `permissions.deny` the force-push entries and the token-printing ones (`gh auth token`,
   `gcloud auth print-access-token`, `gcloud auth application-default print-access-token`,
   `gcloud secrets versions access`).

4. Check the wiring. The first command confirms the JSON is valid. The second prints nothing: gates are log-only
   until you enable enforcement (if `~/.claude/.enforce` already exists on your machine it prints the deny too). The
   third prints a JSON `deny` whose reason contains `state-verb:stash`.

   ```
   python3 -m json.tool ~/.claude/settings.json > /dev/null && echo settings.json is valid JSON
   echo '{"tool_name":"Bash","tool_input":{"command":"git stash"},"cwd":"'"$PWD"'"}' | bash ~/.claude/hooks/bash_gate.sh
   echo '{"tool_name":"Bash","tool_input":{"command":"git stash"},"cwd":"'"$PWD"'"}' | CSA_ENFORCE=1 bash ~/.claude/hooks/bash_gate.sh
   ```

**Not wired by default, on purpose.** `hooks/settings_drift_guard.py` (a `SessionStart` hook) restores `model` and
`effortLevel` to their committed values and removes an uncommitted `modelSettings` block, which overrides a model you
change deliberately. The agent router is three hooks: `agent_router.py` (`UserPromptSubmit`), `agent_router_path.sh`
(`PostToolUse` on `Write|Edit|MultiEdit`) and `agent_obligations.py` (`Stop`), which blocks the stop once per
obligation even in log-only mode. Wire any of them only when you want them.

**Before you turn enforcement on, seed the Playwright allowlist.** The browser guard (`hooks/block_prod_mutations.py`,
wired on `mcp__playwright.*`) reads `~/.claude/live-testing/allowlist.json`, and the repository ships only
`live-testing/allowlist.example.json`. Under enforcement with no `allowlist.json` the guard denies every browser
interaction (click, type, fill form, evaluate); navigation and snapshots still pass. Copy the example, then edit it to
name the hosts you actually test against (in case B, also copy `live-testing/browser_pool.py` if you wire the
Playwright hooks):

```
mkdir -p ~/.claude/live-testing
cp -n "$RUNTIME/live-testing/allowlist.example.json" ~/.claude/live-testing/allowlist.json
```

**Turn enforcement on** when you are ready, in either case. Any one of these does it: an empty `~/.claude/.enforce`
(every session on the machine), `CSA_ENFORCE=1` in one session's environment, or an empty
`<repo>/.claude/.csa-enforce` for one repository (the hooks use the first directory at or above the working directory
that has a `.git`). `CSA_DISABLE_HOOKS=1` turns every hook off. Under enforcement the model-pin gate denies a dispatch
that names no `model` when there is no agent file to take a pin from (the built-in `Explore`, `Plan`,
`general-purpose`, or an agent type you have not defined), and a dispatch of an agent file with no `model:` line; the
README's "Status and caveats" explains why.

**Run the gate-chain suites** before trusting any of it. They need `pytest`. On Homebrew Python `python3 -m pip
install pytest` fails with an `externally-managed-environment` error, so use a virtual environment and run pytest
with its interpreter (in case B, `hooks/tests/` came across with `hooks/`):

```
python3 -m venv ~/.cache/rt-venv && ~/.cache/rt-venv/bin/pip install pytest
cd ~/.claude && ~/.cache/rt-venv/bin/python -m pytest hooks/tests/test_block_branch_ops.py hooks/tests/test_check_staged_scope.py hooks/tests/test_precommit_review_gate.py hooks/tests/test_file_claims.py -q
```

On Linux, prefix the second command with `PYTEST_ADDOPTS=--basetemp=/var/tmp/rt-pytest`. pytest's default temp
directory there is under `/tmp`, and `test_split_redirect_target_denies_pathspec_outside_repo` uses `/tmp/e.log` as its
"outside the repo" path, so it fails when the repository it builds is itself under `/tmp` (seen on macOS with a base
temp under `/tmp`). pytest empties that directory on every run, so give it one of its own.

The suite aborts when the test files do not live under `$HOME/.claude`: the check is on where `hooks/tests/` is, not on
your current directory, because the hooks resolve each other through that path. The abort message points to
`scripts/ci_layout.sh`, which stages a checkout the way the planned CI will. `CONTRIBUTING.md` covers running the full
suite that way.

## 2. Run `init_repo.sh` against your product repo

```
"$RUNTIME/scripts/init_repo.sh" <path-to-your-repo>
```

This is idempotent — safe to run again later; it never overwrites a file you've started editing.
On a fresh repo it:

- creates `<repo>/.claude/oversight/` and copies in one dossier skeleton per bundle agent (a
  `## `-headed outline with placeholder tokens, not real content — see step 4);
- copies `templates/oversight/manifest.example.json` to `<repo>/.claude/oversight/manifest.json`;
- sets `worktree.baseRef: "head"` in `<repo>/.claude/settings.json` (load-bearing for every
  worktree-isolated sub-agent and for THE ISSUE WHEEL, the nightly issue-triage workflow defined in
  [`GLOSSARY.md`](../GLOSSARY.md) — without it, an isolated build branches from
  the remote default branch instead of your own HEAD and silently loses your session's commits);
- writes `<repo>/.claude/oversight/.bundle_version`, recording which commit of this runtime the
  templates it just copied came from (see step 8);
- seeds three small per-machine files into `$RUNTIME/knowledge/` if they aren't already there
  (see step 7 — this is the one step that writes *into the runtime*, not into your repo);
- runs `repo_manifest.py validate` and `doctor` against your repo and prints both. `validate`
  reporting two `INVALID` lines here is expected and fine — they name the two manifest fields that
  still need real values (see step 3), not a broken install.

## 3. Fill `manifest.json`

`<repo>/.claude/oversight/manifest.json` is the one machine-readable answer to "where is X in this
repo" — every field's meaning is documented inline in
[`templates/oversight/manifest.example.json`](../templates/oversight/manifest.example.json)'s own
key names and the generic example values next to them (`product.slug`, `github.repo`,
`oversight.tracking_issue`, `gtm.missions_dir`, `wheel.venv_python`, `security.auth_cookie_names`,
and so on). Edit it directly — there's no separate schema doc to cross-reference, and
`repo_manifest.py` has no `set` command.

**Two fields must point at something real before `validate` passes.** On a fresh repo they are the
only two `INVALID` lines, because the example values name paths your repo does not have yet. Both
paths are relative to the repo root.

- `gtm.missions_dir` — the directory where `/gtm` missions write their JSON files. It must already
  exist. The example value is `docs/gtm_missions`:

  ```
  mkdir -p <path-to-your-repo>/docs/gtm_missions
  ```

  Or edit the field to name a directory you already have.

- `wheel.venv_python` — the Python interpreter THE ISSUE WHEEL uses to run your repo's tests. The
  path must exist. The example value is `.venv/bin/python`:

  ```
  python3 -m venv <path-to-your-repo>/.venv
  ```

  Add `.venv/` to the repo's `.gitignore`, and install your project's own test dependencies into it
  before the wheel relies on it. Or edit the field to point at the interpreter of a virtual
  environment you already have. If you will not run the wheel, set it to `null`: `validate` accepts
  that.

Once both resolve, run:

```
python3 "$RUNTIME/scripts/repo_manifest.py" validate --repo <path-to-your-repo>
```

`OK` means every required key is present, the `product.slug` shape is valid, and every
repo-relative path field actually exists on disk. Anything else is one `INVALID <key>: <reason>`
line per problem — fix the named field and re-run. (`repo_manifest.py get gtm.missions_dir --repo
<path-to-your-repo>` prints the absolute path a field resolves to.)

## 4. Fill the dossiers `doctor` names

```
python3 "$RUNTIME/scripts/repo_manifest.py" doctor --repo <path-to-your-repo>
```

`doctor` reports every gap between what a bundle agent expects to read and what your repo actually
has: a missing dossier file, a placeholder token (`__LIKE_THIS__`) still sitting unfilled in a
dossier that's otherwise done, a dossier that just restates a value `manifest.json` already owns
(say `manifest.json`'s key instead — that's the whole point of having one owner per fact), or a
template that's changed upstream since your `.bundle_version` was recorded (see step 8). `OK: 0
findings` is the target — every template ships fillable, so an empty `doctor` run is always
reachable, never a moving target.

[`templates/oversight/PLACEHOLDERS.md`](../templates/oversight/PLACEHOLDERS.md) is the full table
of every placeholder token used across the templates, what it means, and a worked example value —
read it side by side with whichever dossier you're filling in.

An agent whose dossier you haven't gotten to yet doesn't error — it reads what's there, notices the
placeholders or the missing file, and **declares itself DEGRADED for this repo's facts** rather
than improvising. That's deliberate: a degraded agent is safe to dispatch at any point in this
process, it just won't know your app's specifics yet.

## 5. The 15-minute minimum viable GTM path

You don't need every dossier filled to run your first mission. The GTM department's entry point,
`/gtm "<goal>"`, needs exactly three things to produce something real:

1. `manifest.json` — at minimum `product`, `github`, and `gtm.missions_dir` filled in.
2. `<repo>/.claude/oversight/marketing-director.md` filled in — the department orchestrator's
   grounding.
3. `<repo>/.claude/oversight/market-analyst.md` and `content-strategist.md` filled in — one
   fact-gathering seat, one production seat.

Every other specialist seat (`brand-architect`, `conversion-architect`, `seo-architect`,
`paid-acquisition-strategist`, `pricing-economist`) runs **DEGRADED and says so explicitly** in its
own output when its dossier isn't filled yet — the mission still runs, it just doesn't get that
seat's app-specific judgment. Fill the rest whenever you're ready for the full roster.

Once those three are real: `/gtm "<your goal>"` (see
[`skills/gtm/SKILL.md`](../skills/gtm/SKILL.md) for the full mission lifecycle — clarify → plan →
produce → converge → present). If `manifest.json`'s `operator_input` is left `null`, the director
writes its questions to a numbered `OPERATOR_QUEUE.md` in your `gtm.missions_dir` instead of a
richer operator-input surface — either way, nothing is silently skipped.

## 6. What a mission produces

Every `/gtm` mission writes one JSON file to `<gtm.missions_dir>/<mission_id>.json`. The exact
schema — what fields exist, what each phase is required to fill in, how the dissent ledger and its
mechanical convergence evaluator work — is
[`tools/gtm/MISSION_SCHEMA.md`](../tools/gtm/MISSION_SCHEMA.md). Read that before parsing mission
output programmatically, or before writing a second consumer of it.

## 6a. `marketing_kb_state/` — your repo's own GTM state, alongside the doctrine corpus

`knowledge/marketing_kb/` (ships with the bundle) is **doctrine only** — portable frameworks,
anti-patterns, and playbooks with zero facts about any one app. The GTM seats that read it
(`brand-architect`, `seo-architect`, `paid-acquisition-strategist`, `content-strategist`, …) also
need real, current facts about *your* app — its actual token values, its actual SEO pipeline
state, its actual ad-account history — and that state is never something this corpus can ship,
because it's true for exactly one repo and goes stale the moment the app changes.

That state lives at `<repo>/.claude/oversight/marketing_kb_state/` — repo-local, never exported to
this runtime or its mirror, same standing as any other `.claude/oversight/<agent>.md` dossier. A
seat's dossier names which state file (if any) it reads as a Read-FIRST pointer, e.g.
`.claude/oversight/brand-architect.md` pointing at
`.claude/oversight/marketing_kb_state/<yourrepo>-as-is-state.md`. There's no fixed file list or
schema — author whatever state docs your repo's seats actually need, each carrying its own as-of
date so staleness is visible rather than assumed away.

**A missing state file is not an error** — a seat with no Read-FIRST state file, or one whose
target doesn't exist, declares itself DEGRADED for that app's facts and says so rather than
improvising them, exactly like a missing oversight dossier. `init_repo.sh` does not create this
directory or any file in it; it is genuinely optional and genuinely repo-authored.

## 7. The three files `init_repo.sh` seeds into `$RUNTIME/knowledge/`, and why

Step 2's seeding step copies three files from `templates/knowledge/` into `$RUNTIME/knowledge/`
**only if each is absent** — these are per-**machine** state, not per-repo, so they live at the
runtime root, not under your repo's `.claude/`:

- `oversight_install.md` — the per-install half of the oversight system's job table (which
  scheduled jobs actually exist on *this* machine, their labels, cadences, and current load
  state). The portable half — the heartbeat contract, kill-switch, and mechanics that never need
  per-machine editing — ships with the bundle itself as
  [`docs/subsystems/oversight-install.md`](subsystems/oversight-install.md); read that for how any
  of it actually works, and edit the seeded file for what you've actually installed here.
- `agentarch_recommendations.jsonl` and `research_ledger.jsonl` — empty ledgers that
  `agentic-systems-architect` and `research-scout` (among others) append real findings to over
  time. They ship empty by design: the *content* is this machine's own findings, never anyone
  else's, so there's nothing meaningful to pre-populate.

Because seeding only fires when the target is absent, re-running `init_repo.sh` — even against a
different repo on the same machine — never overwrites a machine's real, already-populated copies
of these three files.

If you installed by the merge-by-hand route (step 1, case B), the files are seeded into
`~/.claude-runtime/knowledge/`, but the agents you copied into `~/.claude/agents/` read
`~/.claude/knowledge/`. Copy the three across once, without overwriting: `cp -n
"$RUNTIME/knowledge/oversight_install.md" "$RUNTIME/knowledge/agentarch_recommendations.jsonl"
"$RUNTIME/knowledge/research_ledger.jsonl" ~/.claude/knowledge/`.

## 8. Keeping templates in sync

Templates can change upstream (a new placeholder token, a restructured section) after you've
already filled in your repo's dossiers. Two ways to check:

```
"$RUNTIME/scripts/init_repo.sh" --diff <path-to-your-repo>
```

prints a unified diff, per changed template, of the upstream version against your repo's own
filled-in dossier — since the commit recorded in your `.bundle_version`. This is preview-only; it
never writes anything or attempts a merge. Decide by hand whether to fold anything in.

`doctor` (step 4) also flags this on its own — a `template-outdated:<file>` line means `--diff`
has something to show you for that file. Run `init_repo.sh --update-version` once you've reconciled
everything, to move your recorded baseline forward and quiet the flag until the next real change.

## 9. What is deliberately NOT in this bundle

This runtime is intentionally narrower than "everything one product's Claude Code setup ever
needed":

- **Product-domain agents** — a trade/domain specialist whose grounding is a product-specific
  knowledge corpus (pricing rules, an engine's own accuracy harness, anything that can't be made
  generic) stays in that product's own repo. This bundle ships the *discipline* every agent
  operates under, never a specific product's domain expertise.
- **Your live-testing policy** — the bundle ships the browser-pool tool (`live-testing/browser_pool.py`),
  the Playwright guard hook (`hooks/block_prod_mutations.py`) and a generic seed
  (`live-testing/allowlist.example.json`), but never a real allowlist: your origins, tenants and test
  recipients are per machine (copy the seed to `live-testing/allowlist.json` and tailor it, as
  `live-testing/README.md` explains). Nothing here assumes you have a staging environment.
- **The estimate-engine loop** (or any single product's own accuracy-scoring/self-correction loop)
  — that's product-specific machinery built around one product's own domain problem, not a
  portable pattern this bundle tries to generalize.

If your own repo needs any of these, build them there, following the same shape this bundle uses
for everything else: portable discipline in the agent/primer, your repo's own facts in a dossier or
manifest field, never the reverse.
