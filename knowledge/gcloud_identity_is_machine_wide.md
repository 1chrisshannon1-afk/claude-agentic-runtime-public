# gcloud's ambient identity is machine-wide, shared by every live session (#5310)

## The fact

`gcloud`'s "active account" (`gcloud config get-value account`, the identity every subsequent
`gcloud`/`gsutil`/`bq` call implicitly uses) and the on-disk Application Default Credentials (ADC)
file at `~/.config/gcloud/application_default_credentials.json` are **not per-session, per-terminal,
or per-agent state** — they are ONE piece of state per machine, read and written by every concurrently
running `gcloud` invocation regardless of which shell, session, or agent issued it. There is no
`gcloud`-native equivalent of a per-process credential scope for the *ambient* identity: `gcloud
config set account <x>` and `gcloud config configurations activate <x>` both rewrite a file under
`~/.config/gcloud/` that every other process on the machine reads next time it shells out to `gcloud`
with no explicit override.

This is the exact same hazard shape as the shared git working tree this runtime's gate chain already
protects (`~/.claude/CLAUDE.md` §2: "Assume other agents are editing the tree — right now";
`docs/subsystems/gate-chain.md`'s gate 1 `block_branch_ops`): one shared, mutable resource, many
concurrent readers/writers, no isolation unless every writer deliberately scopes its own mutation.
`git checkout`ing a shared branch out from under a peer session and `gcloud config set account`ing a
shared identity out from under a peer session are the same class of bug with a different resource
name.

## Why this matters operationally

An agent that runs any of the following silently re-identifies **every other live session's next
gcloud/ADC-consuming call** on this machine, with no notification, no isolation, and no way for the
affected peer session to detect the change happened:

- `gcloud config set account <val>` / `gcloud config set core/account <val>` (same property, two
  spellings)
- `gcloud config configurations activate <name>`
- `gcloud auth activate-service-account ...` — gcloud's own `--help` documents this as
  *unconditionally* activating the account ("similar to running gcloud config set account
  [ACCOUNT_NAME]") — there is no flag that suppresses this
- `gcloud auth application-default login ...` — overwrites the shared ADC file directly
- `gcloud auth login ...` without `--no-activate`
- `gcloud config unset account <val>` / `gcloud config unset core/account <val>` — reaches the
  identical mutation `config set account` performs, by **deletion** instead of assignment: removing
  the active `account` property re-identifies every peer session's next call exactly as reassigning
  it would (`gcloud config unset --help`: "By default, unsets the property in your active
  configuration only" — the same active-configuration scope `set` mutates)
- `gcloud auth revoke [ACCOUNTS...] [--all]` — with no account given, gcloud's own `--help`: "revokes
  credentials for the currently active account, effectively logging out of that account" (the same
  re-identification as `config set account`, reached by deleting the credential instead of
  reassigning it); with an explicit account or `--all`, it still deletes that account's cached
  credential from the shared, machine-wide credential store outright, with no scoping flag limiting
  the removal to the caller's own session
- `gcloud auth application-default revoke` — deletes the shared ADC file outright (gcloud's own
  `--help`: "deletes the local credential file"), the same well-known machine-wide path
  `auth application-default login` is blocked for overwriting, now reached by deletion
- any shell-level `>`/`>>`/`cp`/`mv`/`tee` write to
  `~/.config/gcloud/application_default_credentials.json` directly, bypassing gcloud's own CLI
  entirely

A peer session mid-way through a GCP operation (a deploy, a Secret Manager read, a Cloud Run
invocation) that suddenly starts authenticating as a different principal is exactly the kind of bug
that is nearly impossible to diagnose after the fact — the peer session sees permission errors, stale
project context, or worse, succeeds against the *wrong* project/account, with no local signal that its
identity changed underneath it mid-session.

## The mechanical fix (#5310)

`~/.claude/hooks/block_gcloud_identity.py`, wired as **gate 1c** in the `PreToolUse:Bash` dispatcher
chain (`~/.claude/hooks/pretooluse_bash.py`; see `docs/subsystems/gate-chain.md`'s "Gate 1c" section
for the full spec), blocks every command in the list above and allows the sanctioned **per-invocation**
scoping forms instead:

```
gcloud --account=<value> <cmd>
gcloud <cmd> --account=<value>
gcloud --impersonate-service-account=<value> <cmd>
CLOUDSDK_CORE_ACCOUNT=<value> gcloud <cmd>
gcloud auth login --no-activate
gcloud auth list                    # read-only
gcloud config get-value account     # read-only
```

Every one of these leaves the machine's ambient/active identity untouched — the override applies
only to that one invocation (`--account=`/`--impersonate-service-account=`) or that one process
(`CLOUDSDK_CORE_ACCOUNT=` as an env prefix). This is the same pattern the runtime already asks
agents to use for `git`: never mutate shared branch/stash state, always act through your own
scoped, path-limited operation.

## For any agent that needs to act as a specific GCP identity

**Never** run `gcloud config set account`, `gcloud config configurations activate`, `gcloud config
configurations create` (it activates by default — pass `--no-activate` if you genuinely only need
to create one, never activate it), `gcloud auth activate-service-account`, `gcloud auth
application-default login`, or `gcloud auth login ... --update-adc` (this overwrites the shared ADC
file regardless of `--no-activate`) to "switch into" an identity for a task, even temporarily, even
if you plan to switch back afterward — the window between your mutation and your restoration is
exactly when a peer session's own `gcloud` call can silently pick up your temporary identity, and a
crash/interruption in that window leaves the wrong identity active machine-wide with no automatic
recovery. **None of this changes under an `alpha`/`beta` release-track prefix** — `gcloud alpha
auth login` / `gcloud beta config set account ...` mutate the identical machine-wide state as their
non-prefixed form; the gate strips the track prefix before matching, and this rule does too.

**Always** use a per-command or per-process override instead:

- One-off command: `gcloud --account=<value> <subcommand...>`
- A short script/session of commands: `CLOUDSDK_CORE_ACCOUNT=<value> gcloud <subcommand...>` (repeat
  the env prefix on each invocation, or export it only within a subshell/script you fully control —
  never in the parent shell an operator or another agent might reuse)
- Acting as a service account for a specific operation: `gcloud --impersonate-service-account=<sa>
  <subcommand...>` (requires the caller's own identity to already hold
  `roles/iam.serviceAccountTokenCreator` on that service account — this is itself a scoped,
  audit-logged impersonation, not a credential swap)

## Known scope gap (deliberate, not silent)

#5310's own checklist item 1 additionally names "any write to
`~/.config/gcloud/application_default_credentials.json` / **shell-profile credential exports**."
The gate covers the ADC-file-write half; it does **not** cover the shell-profile half — a
`GOOGLE_APPLICATION_CREDENTIALS` export appended to `~/.zshrc` (or any other shell profile)
survives every new shell the operator or an agent opens, exactly like the ADC file itself, and
`GOOGLE_APPLICATION_CREDENTIALS` **takes precedence over** the ADC file when both are present. This
was one of the three actual incident mutations behind #5310. It is not covered here because
detecting an arbitrary write to an arbitrary shell-profile file (`~/.zshrc`, `~/.bash_profile`,
`~/.profile`, ...) is a materially different, much broader detection surface than a write to one
well-known JSON path — the false-positive risk (any shell-profile edit at all, for any reason,
mentioning `GOOGLE_APPLICATION_CREDENTIALS`) needs its own scoped design, not a quick addition here.
Tracked as a real, open gap — not solved by this module.

## Scheduler / Cloud Run / Cloud Functions `describe` — the masked `--format` convention (the scheduler/IaC section)

A SEPARATE hazard, also fixed in `block_gcloud_identity.py` (#5890), but not an
identity mutation: `gcloud scheduler jobs describe <job>` (and `run services describe`, `run jobs
describe`, `run revisions describe`, `run jobs executions describe`, `run jobs executions tasks
describe`, `functions describe`) prints the resource's FULL representation to stdout by default —
and stdout is tool output, which reaches the model. For a Scheduler job whose HTTP target carries an
auth header (e.g. `X-Scheduler-Key: <secret>`), the header VALUE — the secret itself, not just its
existence — lands in tool output with no redaction. The identical shape applies to a Cloud Run
revision's plaintext env vars and a Cloud Functions OIDC/service-account token config. No gate in
this chain stopped this before #5890 landed; identity-mutation and secret-dump are different hazard
classes sharing the same module because they share the same gcloud-tokenizing infrastructure and the
same gate slot (1c) in `pretooluse_bash.py`'s dispatcher — see that module's own docstring, not a
statement that they are the same kind of bug.

**Always describe a cloud resource that might carry an auth header, an env var, or a token/secret
config with an explicit, MASKED field projection** — never gcloud's bare default output:

```
gcloud scheduler jobs describe my-job --format='table(name,schedule,state)'
gcloud run services describe my-svc --format='json(metadata.name,status.url)'
gcloud functions describe my-fn --format='yaml(status,httpsTrigger.securityLevel)'
```

**Round 2 (trust-architect review, #5890 fix round, 2026-09-24): the safety check
is now a fail-closed per-resource-family ALLOWLIST of known-safe LEAF fields, not a substring
blocklist.** The original design flagged a projected field only if its name matched an
unsafe-looking substring (`header`, `env`, `secret`, `token`, ...) — which cannot see that a PARENT
key's entire subtree is unsafe even though the parent's OWN name looks benign:
`--format='yaml(httpTarget)'` named a field with no unsafe-looking substring, yet gcloud prints the
whole `httpTarget` subtree, headers included. `--format='yaml(spec)'` on a Cloud Run service is the
identical shape for its env vars. The fix inverts the check: a **safe** format is a field-PROJECTION
(`yaml(...)`, `json(...)`, `table(...)`, `value(...)`, `csv(...)`) whose field list is non-empty and
**every field is an EXACT, case-insensitive match against that resource family's own allowlist**
(`_SAFE_LEAF_FIELDS` in `block_gcloud_identity.py`, one entry per family: `scheduler-job`,
`run-service`, `run-job`, `run-revision`, `run-execution`, `run-worker-pool`, `function`) — there is
no longer any path
for a field to pass merely by failing to LOOK unsafe. A `.`/`*` wildcard field, an empty field, or a
field naming a parent key not itself on the allowlist are all denied outright. A bare
`--format=yaml`/`--format=json`/`--format=text` (no field list — dumps the whole resource) or no
`--format` at all are BOTH denied for `describe` (gcloud's own default `describe` output is
equivalent to a full dump). `list` is narrower in one respect only: its own default output is
already a summary table, so no `--format` at all is fine there — but an EXPLICIT `--format` on
`list` is checked against the identical per-family allowlist as `describe`, not merely for being a
bare full-dump kind.

Also denied on every covered `describe`/`list` verb: **`--flags-file`** (a flags file expands in
place and can itself set `--format` to something unsafe with no `--format` token visible in the
command this gate ever sees) and **2+ `--format` tokens** (gcloud applies the LAST value — the last-
repeated-flag-wins rule comes from argparse's own default behavior for a flag with no
`action="append"`, verified against the SDK's own arg-parser wiring, NOT from `gcloud topic formats`'
help text, which says nothing about repeated-flag precedence; a single value can also itself
concatenate more than one projection, e.g. `--format='table(name) json()'` — so 2+ tokens are denied
outright rather than trusting a parse of just one of them).

**Fix round (2026-09-24, same day): two routes around `--log-http` closed.** `--log-http` **when it
resolves TRUTHY** is denied on every gcloud verb this module evaluates, not only the
scheduler/run/functions family. **CORRECTION (round 8): this is NOT "any spelling" — a bare
`--log-http`, or `--log-http=true`/`=yes`/`=1`, are denied, but the mitigation spellings
`--log-http=false`/`=no`/`=0` and `--no-log-http` (added round 4, P3-2, to stop denying the
opt-out form itself) are explicitly ALLOWED, and remain so; "any spelling is denied" was never
accurate once that fix round landed, and this doc's own P3-2 entry below already says so
correctly — this paragraph was simply never updated to match.** `CLOUDSDK_CORE_LOG_HTTP` set
**anywhere** in the command (and resolving truthy — see the `_env_var_assignment_or_removal_is_active`
entries below for the exact, round-7/8-corrected rule) is ALSO denied — not only a leading
env-prefix on the SAME shell segment as the gcloud call, which is all round 2 originally caught. A
command that sets the variable in a DIFFERENT segment first (`export CLOUDSDK_CORE_LOG_HTTP=1;
gcloud ...`, `env CLOUDSDK_CORE_LOG_HTTP=1 gcloud ...`, `set -a; CLOUDSDK_CORE_LOG_HTTP=1; set +a;
gcloud ...`) reaches the identical property (`properties.py` reads `CLOUDSDK_<SECTION>_<NAME>` from
the process environment, not from argv position) with no per-segment argv shape for the original
check to see — this is now caught by a raw-text substring match across the WHOLE command, mirroring
the module's own inline-escape-var tripwire. Separately, **`gcloud config set
log_http`/`core/log_http`** is now also denied — the PERSISTENT, machine-wide route to the identical
leak: unlike the per-invocation `--log-http` flag, this writes the property into the active named
configuration, so every subsequent gcloud call on this machine (every live session's, not just the
one that ran the command) that doesn't itself override it starts logging the full, unmasked HTTP
response to stderr — including a masked `describe`/`list` this gate otherwise allows. **Known
remaining gap:** a direct write of `log_http`/`core/log_http` into
`~/.config/gcloud/configurations/config_<name>` bypassing the `gcloud` CLI entirely has no argv shape
for this module to inspect — the same class of gap as the shell-profile-export gap documented above
for `GOOGLE_APPLICATION_CREDENTIALS`. `config-set-log-http` has its own dedicated deny-message branch
(round 3 fix round, item 1) distinct from every identity-mutation reason above — it is a persistent,
machine-wide RESPONSE-LEAK hazard, not an account/ADC identity change, and reads as such rather than
reusing the "re-identifies every peer session" phrasing the account-mutation reasons use.

**Known deliberate-attacker gaps (round 3 fix round, item 4 — documented, not silent, alongside the
two gaps already named above):**
- **Runtime-built env var name.** `CLOUDSDK_CORE_LOG_$(echo HTTP)=1 gcloud ...` (or any command-
  substitution/indirect-expansion/`eval` shape that only resolves to the literal string
  `CLOUDSDK_CORE_LOG_HTTP` at shell-execution time) never appears as that literal substring in the
  command TEXT the gate inspects, so the raw-text `CLOUDSDK_CORE_LOG_HTTP` check cannot see it.
- **`source`-ing a file that sets the property.** `source ./env.sh; gcloud ...` where `env.sh` sets
  `CLOUDSDK_CORE_LOG_HTTP` (or `CLOUDSDK_CORE_ACCOUNT`, or any other identity-relevant var) is
  invisible to this module — it does no file I/O by contract (a pure decision function, matching
  every sibling gate), so a sourced file's own content is never read or inspected.
- **`CLOUDSDK_CONFIG` redirection.** Pointing `CLOUDSDK_CONFIG` at an alternate configuration
  directory (`CLOUDSDK_CONFIG=/tmp/altconfig gcloud ...`) sidesteps this module's entire "one shared,
  machine-wide config directory" threat model for whatever properties live there — every `config
  set`/`unset` check here reasons about property NAMES only, never about WHICH on-disk directory
  gcloud actually targets, and nothing in this module inspects `CLOUDSDK_CONFIG` itself.

None of these three are chased in this module: each needs either executing/parsing arbitrary shell
(which would break the "no I/O, no subprocess, pure decision function" contract every sibling gate in
this chain shares) or a genuinely different detection strategy (sandboxing gcloud's real file I/O
rather than inferring it from argv text). Documented so a future audit reads "this hazard class is
covered" as "covered for the argv-visible shapes this module can see," not "closed."

**Round 4 fix round (two blockers found by a cold review, closed the same day):**

- **B1 — a group-level flag before the verb no longer hides the command path.** `run services`/
  `run jobs`/`run revisions` each declare `--region`/`--platform`/`--cluster`/`--cluster-location`/
  `--context`/`--kubeconfig` at the GROUP level (verified against the SDK's own source,
  `googlecloudsdk/command_lib/run/flags.py`'s `AddPlatformAndLocationFlags`/`AddRegionArg`, and the
  real installed CLI), so gcloud genuinely accepts them BEFORE the verb:
  `gcloud run services --region us-central1 describe svc`. The module's single-reading flag walk
  treated any unrecognized flag as taking no value, so `us-central1` landed where `describe` should
  have, and the path never matched any covered verb group — a real bypass. Fixed by computing EVERY
  distinct path reading for an unrecognized flag when the command's family could be `run` (both
  "flag takes no value" and "flag consumes the next token"), and blocking if EITHER reading matches a
  covered verb group. `scheduler`/`functions` have no group-level flags at all (confirmed live) and
  are unaffected.
- **B2 — a gcloud call hidden behind a wrapper, shell keyword, or quoted command substitution is no
  longer invisible.** The prior "is this gcloud" check walked past a FIXED, enumerated set of wrapper
  tokens (`env`/`sudo`/`command`/`exec`) from the front of argv — so `time gcloud ...`,
  `timeout 60 gcloud ...`, `nohup gcloud ...`, `xargs ... gcloud ...`, a shell keyword left as a
  segment's own leading token by the segmenter (`do gcloud ...`, `then gcloud ...`), `bash -c
  'gcloud ...'`, `eval 'gcloud ...'`, a heredoc body fed to a shell interpreter (directly or via a
  pipe: `cat <<'EOF' | bash`), and a `$(...)`/backtick command substitution living INSIDE a
  double-quoted token all evaluated to "not gcloud" and passed straight through, including for an
  identity-mutation verb like `config set account`. Fixed with ONE shared helper that scans EVERY
  token in a segment's argv for the first one that IS a gcloud program token (rather than walking a
  fixed prefix), used by both the "is this gcloud" check and the "does this segment mention gcloud"
  check — no wrapper enumeration needed, at the cost of a rare, accepted false positive
  (`echo gcloud config set account x` — the word is merely `echo`'s own argument, never executed, but
  is now treated as a real invocation and denied; the module's own docstring names this tradeoff
  directly). A `bash -c`/`eval` argument, a heredoc body, and a `$(...)`/backtick span (quote-aware
  now, so a literal `)` inside a quoted `--format` value like `value(name)` no longer truncates the
  extraction) are all recursively re-evaluated by the SAME decision logic, depth-capped at 6 levels.
  The `CLOUDSDK_CORE_LOG_HTTP`/`CLOUDSDK_CORE_FORMAT` raw-text tripwires were widened the same way —
  `export CLOUDSDK_CORE_LOG_HTTP=1; bash -c 'gcloud run services list'` now denies.
- **P2-1 (non-blocking) — new verb-group coverage.** `run worker-pools describe|list` and `run
  worker-pools revisions describe|list` share their own `run-worker-pool` family (their default
  printers build on the same env-var-rendering util `run-service`/`run-revision` already need masking
  for). `run configurations describe` defaults to a bare `yaml` full dump with no group-level flags
  in the way; it reuses the `run-service` family (a Configuration is a Service's own template
  history, same `spec.template` container/env shape) — `run configurations list`'s own default is
  already a safe summary table, so it needed no new entry. `functions deploy` returns the full,
  newly-deployed Function object to gcloud's default printer with no `AddFormat` call narrowing it —
  denied the same way `describe` is, reusing the `function` family.
- **P3-1 (defensive; unverified as exploitable on SDK 574.0.0) — `gcloud config set
  format`/`core/format` and `CLOUDSDK_CORE_FORMAT`.** Its own `--help` text says it overrides the
  default output format for every command that doesn't pass its own `--format`. Setting
  `CLOUDSDK_CORE_FORMAT=json` on the installed SDK had no observed effect on a bare `list`, but if a
  future SDK version honors it, every bare `list` this gate allows (on the assumption its own default
  table output is safe) would silently become a full-dump default machine-wide. Denied defensively
  now, mirroring `config-set-log-http`/`CLOUDSDK_CORE_LOG_HTTP` exactly (`config-set-format` /
  `format-env-override`).
- **P3-2 (over-blocking, fixed) — the mitigation forms are no longer denied.** `--log-http=false`/
  `=no`/`=0`/`--no-log-http` (gcloud's own boolean-flag semantics, LAST-flag-wins) and
  `unset CLOUDSDK_CORE_LOG_HTTP` / `env -u CLOUDSDK_CORE_LOG_HTTP gcloud ...` (and the identical
  mitigation forms for `CLOUDSDK_CORE_FORMAT`) now correctly ALLOW. Two known, deliberately-unfixed
  over-blocks remain unchanged from before this round: a correctly-masked multi-line command
  continued with a backslash-newline is still denied as untokenizable, and a `value(ID)`-style label
  projection (gcloud's own valid syntax for referencing a positional resource ID inside a projection)
  is still denied outright — both documented over-blocks, not silent ones.

**Round 5 (trust-architect cold review, same-day) found 4 blockers in the round-4 fix; round 6
closes all of them, plus 4 non-blocking findings from the same review.**

- **B1 — the round-4 path-variant walk had no bound, and could take ~10 minutes of CPU on one
  command.** Every unrecognized flag DOUBLED the branching frontier with no cap on path length, no
  memoization, and no ceiling on the number of distinct readings enumerated — measured: a `run`
  command with 22 unrecognized `--flag value` pairs took ~10s; a blocked describe padded with ~30
  copies of `--no-log-http` took ~1.85s and climbing. Fixed with three always-active, small, fixed
  bounds: (1) a PATH-LENGTH CAP (`_MAX_PATH_ELEMENTS = 6` — no covered verb group is longer than 5
  elements, so a branch that reaches 6 elements can never newly start matching a group it wasn't
  already matching at a shorter prefix); (2) STATE MEMOIZATION on `(index, path)` so two branch
  orders reaching the identical state are never re-explored; (3) a VARIANT-COUNT CEILING
  (`_MAX_PATH_VARIANTS = 64`) — past it, the walk stops and reports a sentinel meaning "too ambiguous
  to enumerate further," which the caller treats as a BLOCK (`run-path-too-ambiguous`) only when the
  command's own argv contains, as a literal token, one of the `run` describe/list family's own
  second-path-element keywords (`services`/`jobs`/`revisions`/`worker-pools`/`configurations`) —
  refined mid-round from an earlier "starts with `run`" check, which was too broad and denied a
  legitimate `gcloud run deploy` padded with many unrecognized flags even though `deploy` can never
  match any covered family under any reading.

  **ROUND 7 CORRECTION (B1-r6): the round-6 fix above was itself incomplete and denied ORDINARY
  Cloud Run commands.** The "argv contains a literal covered keyword" check was necessary but not
  sufficient — a real command like `gcloud run services update api --region us-central1 --memory
  1Gi --cpu 2 ...` (13+ real, documented flags) DOES contain the literal token `services`, so the
  round-6 variant walk still branched on every one of its unrecognized flags even though the PATH
  itself (`services`, then `update`) had already diverged from every covered group at index 1
  (`update` is never `describe`/`list`) — pushing the variant count past the 64-variant ceiling and
  denying a command that could never have been a describe/list under any reading. Confirmed
  affected: `run services update`, `run jobs update`, `run services update-traffic`, `run
  worker-pools update` (all denied starting around 11 real flags), plus `run jobs execute` and `run
  services list` with 12+ flags — even a MASKED `run services describe` padded with extra unknown
  flags denied under this bug, which should never happen once the format is already masked. Fixed
  by adding a FOURTH bound to the walk: a branch now finishes IMMEDIATELY the instant its path is no
  longer a plausible PREFIX of any covered `run` describe/list group
  (`_is_plausible_run_group_prefix`), not merely once it hits the length cap or runs out of input —
  `run services update` diverges at 2 elements and produces exactly one completed branch regardless
  of how many real flags follow. `run deploy`/`run jobs execute`/`run services
  update`/`update-traffic`/etc. padded with unrecognized flags are therefore ALL allowed and fast
  regardless of flag count now (not merely `deploy`, which the round-6 doc's own claim here
  incorrectly implied was the only safe case); a `run
  services`/`jobs`/`revisions`/`worker-pools`/`configurations` command whose PATH could still
  plausibly resolve to a describe/list, and that becomes too ambiguous to soundly enumerate, is
  denied outright, never silently allowed and never a multi-second/-minute hang. The deny message
  for `run-path-too-ambiguous` now recommends the real, working recovery: re-spell every flag as
  `--flag=value` instead of `--flag value` (this removes the space-separated-value ambiguity that
  the branching walk exists to resolve, so an `=`-spelled command never branches at all).
- **B2 — a "set the var, run gcloud, clean up" pattern (ordinary debugging) was silently allowed.**
  The round-4 mitigation-form fix resolved `CLOUDSDK_CORE_LOG_HTTP`/`CLOUDSDK_CORE_FORMAT` by
  LAST-occurrence-in-text-wins, intended to get `unset VAR; VAR=1; gcloud ...` right — but it also
  allowed the mirror-image `export VAR=1; gcloud ...; unset VAR`, since the trailing `unset` reads as
  the textually-last event even though the gcloud call in the middle genuinely ran with the var set.
  Fixed: the var is now treated as ACTIVE (deny) if ANY truthy assignment or unrecognized mention
  appears ANYWHERE in the command, and SAFE (allow) only when every recognized occurrence is itself a
  removal (`unset`/`env -u`) or a falsy assignment — no more attempt at inferring execution order,
  matching this round's "simple, conservative, bounded" directive.
- **B3 — common shell-interpreter idioms were unrecognized: `bash -lc`, clustered short options,
  additional interpreters, and here-strings.** Only an EXACT `-c`/`--command` token was recognized,
  so `bash -lc '...'` (the single most common agent idiom for this shape — login shell + command) and
  any other clustered short-option form (`-ec`, `-euxc`, ...) were invisible; `bash -c -- '...'`
  extracted the literal string `--` instead of the real command; the interpreter set covered only
  `bash`/`sh`/`zsh`; and a here-string (`bash <<< '...'`) was not recognized as an invocation at all.
  Fixed: any short-option cluster matching `^-[A-Za-z]*c[A-Za-z]*$` is now treated as carrying `-c`,
  with the command string taken as the next non-option argument (skipping `--` and `-o
  OPTNAME`/`+o OPTNAME`); the interpreter set widened to add `dash`/`ksh`/`mksh`/`fish`/`csh`/`tcsh`;
  and a here-string is recognized in BOTH its space-separated (`bash <<< '...'`) and no-space
  (`bash <<<'...'`, which `shlex` glues into one combined token with no special `<<<` handling) forms.
- **B4 — this doc, the module's own DENY REASON STRINGS list, and `gate-chain.md` were stale for
  round 4's `config-set-format`/`format-env-override`/`run-worker-pool` additions, and `gate-chain.md`
  contained a FALSE claim that a `### Gate 1b` heading exists in this doc's neighbor.** Fixed: this
  doc's family list now names `run-worker-pool` (above); the module's own docstring DENY REASON
  STRINGS list includes `config-set-format`/`format-env-override`; and `gate-chain.md`'s own
  corrected-note section is fixed to state the real heading structure (Gate 1 at its own heading, Gate
  1c at its own heading, Gate 2 at its own heading — no `Gate 1b` heading exists in that file at all;
  `block_head_overwrite.py` is documented as a SEPARATE gate elsewhere in that doc under its own
  name, never as a `### Gate 1b` subsection of this gate's entry).

**Non-blocking findings closed the same round:**

- **P2-1 — the `$(...)`/backtick scanner ignored single-quoted regions and non-interpreter-fed
  literal heredoc bodies, over-blocking real idioms.** `printf '...$(gcloud ...)...'`, `grep
  '$(gcloud run services describe' docs/`, and — most importantly — this runtime's OWN
  `gh issue comment --body "$(cat <<'EOF' ... EOF)"` completion-comment idiom and `git commit -F -
  <<'EOF' ... EOF` commit-message idiom were all denied whenever their literal text happened to
  contain a backtick-quoted or `$(...)`-shaped mention of a covered command, even though bash never
  expands `$(...)`/backticks inside a single-quoted string, and a heredoc body fed to `cat`/a redirect
  target (never a shell interpreter) is inert file content, not executed text. Fixed by pre-computing
  every single-quoted span and every literal (quoted-delimiter) heredoc body NOT fed to an interpreter
  before scanning, and skipping both — scanning still proceeds normally through double-quoted regions
  and unquoted-delimiter heredoc bodies (bash DOES expand inside both).
- **P2-2 — an earlier argument merely ENDING in `/gcloud` as a path/flag-value could hide a REAL
  gcloud invocation later in the same command.** `docker run -v ~/.config/gcloud:/root/.config/gcloud
  IMAGE gcloud run services describe s` and `sudo --preserve-env=/x/gcloud gcloud config set account
  x` both matched the Docker volume-mount argument or the sudo flag value as "the" gcloud invocation
  (the FIRST token ending in `/gcloud`) and silently missed the REAL, dangerous invocation later in
  the same argv. Fixed: every argv slice starting at a gcloud-shaped token is now evaluated (capped at
  16 slices per segment), and the command is blocked if ANY slice is dangerous.
- **P2-3 — the per-family deny-message hint failed to resolve for a command blocked only via a
  wrapped or nested shape**, silently falling back to the generic `scheduler-job` example, which then
  denied AGAIN when followed on a `run`/`functions` command (round 3 already fixed this for
  TOP-LEVEL multi-segment commands; round 5 found it was never extended to nested text at all — `do
  gcloud run jobs --region r describe j` and `bash -c 'gcloud run services describe s'` both resolved
  no family). Fixed by mirroring the same nested-text recursion the main decision function uses (`bash
  -c`/`eval`/here-string/`$(...)`/backtick/heredoc-fed-to-an-interpreter), depth-capped identically.
- **P2-4 — deliberate-attacker gaps, documented, some newly discovered this round.** All of the
  following remain unrecognized as gcloud invocations by this module (fail-open for these specific
  shapes, never fail-closed) — a genuinely determined attacker with shell access has other options
  this module was never designed to close (see the module's own docstring and the "gate targets
  accidental leaks, not a determined attacker" framing):
  - `echo '...gcloud...' | bash`, `bash < <(...)`, `source <(...)` — process substitution / piped
    text fed to a shell has no argv shape this module inspects.
  - `ssh host '...gcloud...'` — the remote command string is opaque to this module; it has no notion
    of SSH's own argument semantics.
  - `python3 -c "import subprocess; subprocess.run(['gcloud', ...])"` — an interpreted language
    invoking gcloud via its own subprocess API has no shell-level argv shape at all.
  - A shell function wrapping gcloud (`f(){ gcloud "$@"; }; f run services describe s`) — this module
    does no shell-execution-semantics tracking, so a function definition and its later call are
    invisible as a gcloud invocation.
  - A program path held in a variable (`G=/opt/homebrew/bin/gcloud; $G run services describe s`) —
    variable expansion is a shell-execution-time operation this module (a pure text/argv analyzer)
    cannot resolve.
  - **Newly found this round:** `bash -c "$(cat <<'EOF' ...gcloud... EOF)"` — a quoted-delimiter
    heredoc fed to `cat` (not an interpreter, so P2-1's own fix correctly treats its body as inert)
    whose OUTPUT is then itself fed as the STRING ARGUMENT to `bash -c` via command substitution. This
    is a genuine, pre-existing gap (confirmed present before round 6 too, not introduced by this
    round's P2-1 fix) in how deeply this module's nested-substitution recursion chases a
    substitution's own OUTPUT once that output is fed onward to a second, different consumer — closing
    it would require this module to know what a heredoc's rendered TEXT will be and then re-inspect
    that rendered text as if it were itself a nested `-c` body, which is a materially different (and
    more expensive) analysis than the argv/text-shape matching this module does everywhere else.
  - **Newly found round 7 (grouped with the `source`/file-content-invisible gap documented earlier in
    this section — both are "this module cannot see what a FILE on disk will contain"):** a script
    WRITTEN and then RUN in one command, `cat <<'EOF' > /tmp/s.sh\ngcloud run services describe
    s\nEOF\nbash /tmp/s.sh` — the heredoc body here is written to a FILE (`cat > /tmp/s.sh`, not fed
    to an interpreter directly), so it is correctly treated as inert by P2-1's own logic; the
    SEPARATE `bash /tmp/s.sh` segment that actually executes the file has no notion that
    `/tmp/s.sh`'s content is the gcloud-mentioning text written two lines earlier — this module does
    no filesystem I/O at all (by contract, the same reason the `source ./env.sh` gap is unfixed), so
    it cannot know what any file on disk contains, whether written earlier in the SAME command or
    pre-existing.
  - **Newly found round 8:**
    - `$(which gcloud) config set account x` — the program path is resolved by a NESTED command
      substitution whose own OUTPUT becomes the program to invoke; this module's `_gcloud_token`
      matching is purely textual (does it end in `/gcloud`, or is it the literal `gcloud`), and
      `$(which gcloud)` is neither, so the segment's own program token is never recognized as gcloud
      at all -- the same class of gap as a variable-held program path, one level more indirect.
    - `gcloud auth login --no-activate --activate` -- gcloud's own LAST-flag-wins semantics mean the
      trailing `--activate` overrides the earlier `--no-activate`, so this genuinely DOES activate
      (mutate the ambient identity) despite carrying the scoping flag this module's `auth login` check
      looks for; the check only tests PRESENCE of `--no-activate` anywhere in argv
      (`_has_no_activate`), not which of two conflicting boolean flags wins under gcloud's own
      last-repeated-flag-wins rule.
    - `X="$(case a in a) gcloud config set account x;; esac)"` -- a `case` statement's own syntax
      (`a)`/`;;`/`esac`) is not `_lib._split_segments`'s control-operator vocabulary, so the gcloud
      invocation living inside a `case` arm's body, itself inside a `$(...)` substitution, is
      genuinely present in the extracted substitution TEXT but the case-statement keywords around it
      are inert noise this module's segment walk was never designed to parse — this specific shape
      happens to still be caught today (the substitution extractor finds the `$(...)` span and
      recurses into its full text, which still contains `gcloud config set account x` as a literal,
      tokenizable segment), but is tracked here because a case arm's own body could in principle be
      SPLIT across control-flow syntax this module has no model of, in a way that might not always
      recurse cleanly.
    - `source /dev/stdin <<'EOF'\ngcloud config set account x\nEOF` -- `source`-ing `/dev/stdin` fed
      by a heredoc is functionally identical to directly executing the heredoc body as a script, but
      `source`'s own argument (`/dev/stdin`) gives no textual hint that the heredoc immediately
      following it is what will actually be read and executed -- the SAME "this module cannot see
      what a file/stream will contain" limitation as the `source ./env.sh` and write-then-run-script
      gaps above, reached through a different plumbing path (a heredoc feeding a special device file
      instead of a real file on disk).
    - `watch 'gcloud config set account x'` -- `watch` repeatedly re-executes its own single-quoted
      argument as a shell command on an interval; this module's wrapper/keyword scan
      (`_find_gcloud_argv`) finds `gcloud` as a token INSIDE the single-quoted argument string (since
      shlex already strips the outer quotes before this module ever sees the tokens), so `watch
      'gcloud run services describe s'` (an already-covered, denied shape) is NOT the gap -- the gap
      is specifically `watch 'gcloud config set account x'`: an identity-mutation verb wrapped in
      `watch`, which this module's own test suite never separately exercised for the IDENTITY-
      MUTATION family (only for describe/list) until this audit found it; confirmed still a real gap.
    - **Pre-existing, chain-wide (#5907, not newly introduced by any round here): a correctly-masked
      multi-line command continued with a trailing backslash-newline is over-blocked.** `gcloud
      scheduler jobs describe j \` (backslash-newline) `--format='table(name,schedule,state)'` is
      denied as `untokenizable-segment-with-gcloud` even though the command is genuinely safe (a real
      masked describe) -- `_lib._split_segments` has no notion of backslash-newline LINE CONTINUATION
      (a real shell feature that joins the two physical lines into one logical command before any
      further parsing), so the embedded literal newline inside the segment confuses the tokenizer.
      This is a known, already-documented over-block (see the P3-2 entry above, "two known,
      deliberately-unfixed over-blocks remain") restated here explicitly in the gap list for
      visibility, not a new finding -- it is a FALSE POSITIVE (denies something safe), the opposite
      direction from every other item in this list (which are all FALSE NEGATIVES, allowing something
      dangerous), included here because the round-8 review's own audit re-confirmed it is still
      present and still unfixed.
- **P3-1 — the `--log-http=false` advice was never real advice.** `--log-http` is registered with
  `actions.StoreBooleanProperty` (`nargs=0` on the installed SDK, 574.0.0) — a strict zero-argument
  boolean flag. Passing `=value` to it is a genuine argparse error ("ignored explicit argument"),
  confirmed against the live installed CLI, not merely an unusual spelling gcloud happens to accept.
  The `config-set-log-http` deny message (and this module's own `--log-http=false` handling) is
  fixed to recommend `--no-log-http` (the real, argparse-accepted paired flag every
  `StoreBooleanProperty` registration gets) instead. `_FALSE_FLAG_VALUES` (`false`/`no`/`0`) is kept
  for a DIFFERENT, still-correct purpose: scoring the `CLOUDSDK_CORE_LOG_HTTP`/`CLOUDSDK_CORE_FORMAT`
  ENV VAR forms, which properties.py reads as plain string properties (not through argparse), where
  these spellings genuinely are accepted as falsy.
- **P3-2 — the heredoc extractor was quadratic on an adversarial input.** 3,000 `<<`-shaped
  substrings on one line took ~14s; the real driver was that the scanner re-examined text INSIDE an
  already-consumed heredoc's own body for more `<<`-shaped candidates (a large, legitimate
  commit-message-style heredoc whose OWN body text happened to contain the literal characters "<<"
  many times triggered the identical cost). Fixed with two changes: the scan now jumps PAST a real
  heredoc's body once found (removing the spurious in-body re-scanning entirely, the actual
  linear-time fix), plus a hard ceiling (`_MAX_HEREDOC_OPENERS_SCANNED = 32`) on the number of
  DISTINCT heredocs examined, past which the function fails closed for the remainder — bounding a
  genuinely pathological input (thousands of distinct real heredoc openers, not merely `<<`-shaped
  text inside one) to a small, fixed cost.
- **P3-3 — two docstrings described behavior the code did not actually have.** The nested-decision
  function's own docstring claimed an internal error degrades to `(False, "")` for the offending
  nested text specifically — false: that function has no top-level try/except of its own, so an
  error in its recursive call propagates all the way up through `decision()`'s OUTER try/except,
  which fails OPEN for the WHOLE command, not just one nested text. A second docstring claimed the
  nested-decision function calls the program-token-aware "mentions gcloud" check — false: it uses the
  cheaper whole-word text-match check directly, for exactly the reason its own inline comment already
  gave (the program-token-aware check would always evaluate False for the nested shapes that function
  exists to catch). Both docstrings corrected to match the actual code.

**Round 6 (warm continuation of the same reviewer, cold-reviewing round 6's own fix) found ONE
blocker caused by round 6's own B1 fix, plus 6 non-blocking findings; round 7 closes all of them.**

- **B1-r6 — see the corrected B1 entry above; round 6's own variant-count-ceiling fix denied
  ORDINARY, non-describe/list `run` commands.** Fixed by finishing a branch the instant its path is
  no longer a plausible prefix of any covered group, not merely at the length cap.
- **P2-a — the P2-1 fix (round 6) was incomplete for its OWN worked example.** The `$(...)` depth
  walk's quote-tracking (separate from the OUTER scan's own skip-span check) had no notion of
  `_quoted_heredoc_skip_spans` at all, so a `$(cat <<'EOF' ... EOF)` substitution whose heredoc BODY
  contained an apostrophe in ordinary prose ("It's fixed: ...") had that apostrophe misread as
  opening a real shell quote inside the depth walk, which then never closed before the
  substitution's own `)` — denying this runtime's own `gh issue comment --body "$(cat <<'EOF'
  ...EOF)"` completion-comment idiom whenever the comment text happened to contain an apostrophe.
  Fixed by computing `_quoted_heredoc_skip_spans` once and letting BOTH the outer scan and the inner
  `$(...)` depth walk jump over those spans without touching quote state.
- **P2-b — `_env_var_assignment_or_removal_is_active` (round 6) contradicted its own docstring in
  BOTH directions.** (1) A falsy assignment (`VAR=0`) was never recorded into either of the
  function's two tracking collections, so a command whose ONLY occurrence of the var was a safe
  falsy assignment (`CLOUDSDK_CORE_LOG_HTTP=0 gcloud projects list`) fell into the "nothing
  recognized" branch and was wrongly denied. (2) The function's "did I recognize ANYTHING at all in
  this whole command" gate meant a removal ANYWHERE (e.g. a trailing `unset`) made an UNRELATED,
  unrecognized bare mention elsewhere (`export VAR` with no `=`, `read VAR <<< 1`, `:
  ${VAR:=1}`) resolve safe, attacker-shaped: the var's real value from that unrecognized shape was
  never actually determined, yet the command was allowed. Fixed by tracking every occurrence of the
  variable name PER-POSITION: each occurrence's span is checked against three separately-recognized
  shape classes (truthy assignment, falsy assignment, removal); an occurrence not covered by any of
  the three is unrecognized and counts as truthy. Truthy (deny) iff ANY occurrence is truthy or
  unrecognized; safe (allow) only when EVERY occurrence is a removal or falsy assignment.
- **P3-a — `_find_all_gcloud_argv_slices` (round 6, P2-2) silently evaluated only its first 16
  slices when a command had more gcloud-shaped tokens than that**, contradicting this module's own
  "bounded rules fail closed, never silently allow past the bound" directive: 20 Docker `-v
  /hN/gcloud:/cN/gcloud` volume mounts before a REAL `gcloud run services describe s` (or `gcloud
  config set account x`) both silently ALLOWED, since the real invocation sat at slice 17+ and was
  never reached. Fixed: the function now also reports whether its scan was truncated by the cap
  before finishing, and the caller denies outright (`untokenizable-segment-with-gcloud`) whenever it
  was, rather than evaluating a partial slice list as if it were complete.
- **P3-b — a false `<<`-shaped opener with no matching close, not fed to an interpreter, ended the
  WHOLE heredoc scan** (two separate `break` statements in `_extract_shell_heredoc_bodies`), so any
  LATER, genuinely dangerous heredoc anywhere after it in the command was never examined at all.
  Repro: `echo $((1<<b))` (the `1<<b` arithmetic shift is not a real heredoc opener) followed on the
  next line by a real `cat <<'EOF' | bash\ngcloud run services describe s\nEOF` was silently
  ALLOWED — the scan stopped dead at the harmless false opener. Fixed by resuming the scan right
  after each false-opener match (`pos = m.end(); continue`) instead of ending it outright, exactly
  like an unrelated non-opener match already did. **This closes a real, correctness-affecting gap,
  and it also means round 6's own opener-count cap (`_MAX_HEREDOC_OPENERS_SCANNED = 32`) is now
  reachable in a case it accidentally never hit before** — a command with MANY (32+) false
  `<<`-shaped candidates in a row (e.g. `echo a<<b0 a<<b1 ... a<<b2999`) now correctly counts each
  one as an opener candidate and fails closed once the cap trips, rather than the pre-fix `break`
  accidentally keeping this specific shape fast by exiting after the very first candidate. This is a
  genuine, intentional behavior change from round 6, not a regression: the round-6 "fast" result was
  itself an accident of the bug this round fixes, not a deliberate perf design.
- **P3-c — `_in_any_span`'s own callers re-tested every character position inside an already-known
  skip span, one at a time.** Total scan cost was `O(len(text) * len(spans))`; a `git commit` naming
  2,000 single-quoted paths, in a command that also mentioned this module's own filename, took over
  a second from this alone. Fixed with a new `_span_end_if_in_any` that returns a covering span's
  own END, letting both the outer scan and the inner `$(...)` depth walk JUMP straight past it
  instead of re-testing every position — turning the scan into `O(len(text) + len(spans))`.
- **P3-d — the `pretooluse_bash.py` docstring's own deny-reason-strings list (a file not otherwise
  touched since round 5) never named `run-path-too-ambiguous`**, even though the module, this
  knowledge doc, and `gate-chain.md` all already did. Fixed.
- **P3-e — the round-6 fix round's own new performance tests asserted wall-clock time (`< 2.0s`),
  which can fail on a loaded machine for reasons unrelated to the code.** Replaced with assertions
  on deterministic variant/iteration COUNTS wherever a countable proxy existed (all five cases did) —
  e.g. asserting `_gcloud_command_path_variants` returns exactly the expected small number of
  readings, or that `_extract_shell_heredoc_bodies` finds zero real bodies in an adversarial input,
  rather than timing the call.

**Round 8 (cold trust-architect review of round 7, found 2 blockers, both fail-opens on plausible
agent commands; closed same day, plus 5 cheap P3 items):**

- **B1-r7 (BLOCKER, a REGRESSION from round 7's own B1-r6 fix) — `_is_plausible_run_group_prefix`
  ran BEFORE the alpha/beta release-track prefix was ever stripped from the path it checks.** The
  round-7 branching walk builds `path` directly from `argv[1:]` with NO track stripping anywhere in
  that walk (stripping only ever happened on the SEPARATE `base_path` reading) — so for `gcloud beta
  run services --region us-central1 describe svc`, the plausibility check was called with `path =
  ("beta",)` on the very first token, judged implausible immediately (no covered group starts with
  `"beta"` — they all start with the literal `"run"`), and the branch finished before `run`/
  `services`/`describe` were ever consumed. `gcloud alpha/beta run services/jobs --region ...
  describe/list ...` all silently ALLOWED a real unmasked secret dump — a genuine regression from
  round 6, which stripped the track prefix in its own (different) single-reading walk and had no such
  gap. Fixed by stripping a single leading `alpha`/`beta` element from `path` INSIDE
  `_is_plausible_run_group_prefix` itself, before running the positional check — making the
  function's own contract self-sufficient rather than relying on an external precondition its actual
  caller never honored. `_MAX_PATH_ELEMENTS` (6) still comfortably fits a track-prefixed path (5
  elements for the longest group, plus the stripped track token itself).
- **B2 (BLOCKER) — `_single_quoted_spans` scanned raw text with no notion of heredoc bodies and no
  backslash-escape handling, and let an unterminated span run to end-of-text.** A prose apostrophe
  inside ANY heredoc body (quoted-delimiter or not) — `cat > /tmp/notes.md <<'EOF'\nIt's the deploy
  note\nEOF\n...` — was misread as opening a REAL single-quoted span; with no matching close before
  the text ended, that false span extended to cover EVERYTHING after it, including every later real
  `"$(gcloud ...)"` substitution or backtick, which `_extract_command_substitutions` then skipped
  entirely as "inside a quote." Six distinct repro shapes across different heredoc/segment layouts
  all silently ALLOWED a real identity mutation or unmasked describe that followed an earlier,
  completely unrelated heredoc containing an apostrophe — including the live dispatcher itself, not
  merely a hypothetical. Fixed with three changes: (a) a new `_all_heredoc_body_spans` helper (ANY
  delimiter kind, not just the quoted-and-not-interpreter-fed subset `_quoted_heredoc_skip_spans`
  already covered) that `_single_quoted_spans` now jumps over WHOLESALE before ever considering a
  character a quote opener — a heredoc body is never real shell-quoted text regardless of delimiter
  kind, so no apostrophe inside one can ever be a real quote; (b) a backslash OUTSIDE any quote now
  escapes the next character, matching real bash (`echo don\'t` no longer misreads the escaped
  apostrophe); (c) an unterminated single-quote span now makes the WHOLE function return `[]` (fail
  CLOSED by skipping NOTHING) instead of extending the span to end-of-text (fail OPEN by skipping
  EVERYTHING after it) — a real, deliberate reversal of the round-6/7 direction for exactly this
  case, since the prior "extend to end-of-text" choice was the wrong direction for a security scanner
  even though it read as a reasonable default in isolation.
- **P3 (cheap, closed the same pass):**
  - The `untokenizable-segment-with-gcloud` deny message claimed every cause was an unbalanced-quote
    problem and told the reader to "rewrite as a single line with balanced quotes" — wrong advice for
    the OTHER four causes that share this one reason string (the slice cap, the heredoc-opener cap,
    the nesting-depth cap, and a genuine unmatched-`$(`/backtick opener). Fixed with a message that
    names all five causes and their own correct remediation.
  - Two stale comments corrected: `decision()`'s own inline comment describing
    `_env_var_assignment_or_removal_is_active` as "LAST-occurrence-wins" (the round-6 semantics,
    REPLACED in round 7's own P2-b fix — the comment was never updated to match); and
    `_gcloud_segments`' docstring describing `_mentions_gcloud` as walking past a fixed
    `env`/`sudo`/`command`/`exec` wrapper list (the round-3 mechanism, REPLACED in round 4's B2 fix
    by scanning every token for the first gcloud-shaped one, with no fixed list at all).
  - The P3-c "O(len(text) + len(spans))" complexity claim from round 7 was itself FALSE — the
    round-7 `_span_end_if_in_any` implementation still did a plain linear scan over `spans` on EVERY
    call, including every call for a position NOT inside any span (the common case), so the real cost
    was still O(len(text) * len(spans)), identical to the round-6 bug it was meant to fix. Fixed for
    real this time with `bisect.bisect_right` over spans SORTED BY START (sorted exactly ONCE per
    scan, in a new `_sorted_spans_with_starts` helper, never re-sorted per call) — genuinely
    O(len(text) * log(len(spans))) now. The "spans never overlap ... by construction" docstring
    claim (a separate, narrower claim than the complexity one) was also tightened: it is true, but
    only BECAUSE `_single_quoted_spans` (per the B2 fix above) now explicitly skips heredoc bodies
    before ever considering a quote character — a dependency the prior wording asserted as a
    self-evident structural given rather than spelling out.
  - Two test fixes: the fail-closed-for-whole-command test asserted only `isinstance(block, bool)`/
    `isinstance(reason, str)` (vacuous — passes regardless of the actual verdict) and monkeypatched a
    target (`_lib._split_segments`) that is guarded by a LOCAL try/except at every call site inside
    this module, so raising there never actually reached the fail-open path its own name/comment
    claimed to test. Fixed to monkeypatch `_gcloud_segments` itself (called with no wrapping
    try/except at its own call site) and assert the exact expected result,
    `(False, "decision-error")`. A source-text lock-in test (asserting a literal substring appears in
    `inspect.getsource(...)`) was dropped — it pinned an implementation detail rather than observable
    behavior. A new count-based (not wall-clock) test for the P3-c complexity claim was added,
    verified to go RED on both round 6 and round 7's actual implementations.

None of the B1/B2 fixes touch gate 1 (`block_branch_ops.py`)'s OWN identical wrapper/keyword blind
spot — confirmed live, tracked separately on #5907, not fixed here. Also out of
scope for #5907 (deliberately, same tracking issue): a case-insensitive program name (`GCLOUD` on a
case-insensitive filesystem volume), a quote-split program name (`gcl''oud`), `bash_gate.sh`'s own
case-sensitive fast-path pattern match, and CLAUDE.md §7's own wording about gates 1/1c failing
closed "on their own error" (both actually fail OPEN on their own errors — the dispatcher's fail-open
default applies to both, matching the documented contract every sibling gate in this chain shares).

**Deny reason strings** this hazard class returns (for anyone reading `~/.claude/.enforcement/log.jsonl`
directly): `describe-unmasked-format`, `list-unmasked-format`, `describe-multiple-format`,
`list-multiple-format`, `describe-flags-file`, `list-flags-file`, `log-http-leaks-response`,
`config-set-log-http`, `config-set-format` (round 4), `format-env-override` (round 4),
`untokenizable-segment-with-gcloud` (now also reachable from nested/ambiguous command-substitution,
heredoc extraction, or an `_find_all_gcloud_argv_slices`/`_extract_shell_heredoc_bodies` cap being hit
before the scan could finish, round 4/7), `run-path-too-ambiguous` (round 6, B1; corrected round 7,
B1-r6 — a `run services`/`jobs`/`revisions`/`worker-pools`/`configurations` command whose PATH could
STILL plausibly resolve to a describe/list and whose unrecognized-flag count made every remaining
path reading too expensive to soundly enumerate; this reason is NEVER returned for a `run` command
whose path has already diverged from every covered group — true for EVERY non-describe/list verb,
`deploy`/`update`/`update-traffic`/`execute`/`create`/etc., regardless of flag count, not merely
`deploy` as an earlier version of this doc incorrectly implied before B1-r6 closed the gap between
those two claims).

**The suggested safe `--format` hint is now per-resource-family**, not one shared example. A single
shared hint (`table(name,schedule,state)`) only ever passed this gate's own check for `scheduler-job`
— `name`/`schedule`/`state` are not top-level fields on any OTHER family's allowlist — so an agent
that followed the pre-fix-round deny message's advice on a `run`/`functions` verb was denied again by
the very message meant to unblock it. Each family now has its own working example (see
`_SAFE_FORMAT_HINTS` in `block_gcloud_identity.py`), and the deny message for a `describe`/`list`
denial names the hint for that command's OWN family.

This is the general rule for ANY scheduler/IaC gcloud work an agent does, not just the verbs the
gate currently enforces: **describing a cloud resource that carries an auth header or env secrets is
a masked-format call, named only allowlisted leaf fields (never a parent key, and never the default
output)** — see the scheduler/IaC section above for the safe `--format` convention. The gate covers
`scheduler jobs describe` / `run services describe` / `run jobs describe` / `run revisions describe`
/ `run jobs executions describe` / `run jobs executions tasks describe` / `run worker-pools
describe` / `run worker-pools revisions describe` / `run configurations describe` / `functions
describe` / `functions deploy` (round 4 adds the `worker-pools`/`configurations`/`deploy` entries;
plus their `list` counterparts where one exists, `--log-http`/`CLOUDSDK_CORE_LOG_HTTP` and
`--format`-property overrides via `CLOUDSDK_CORE_FORMAT` on every verb, and `config set
log_http`/`format`) specifically; a resource type outside that list has no MECHANICAL gate yet, so
the same discipline must be applied BY HAND until the gate's verb coverage widens.

## Related

- `~/.claude/hooks/block_branch_ops.py` — the git analogue: blocks `checkout`/`switch`/`stash`/
  `reset`/`rebase`/`restore`/`clean`/branch-delete for the identical "shared mutable resource, many
  concurrent agents" reason.
- `~/.claude/docs/subsystems/gate-chain.md` — the full gate-chain spec, including gate 1c's own
  section.
- `~/.claude/CLAUDE.md` §2 — "Assume other agents are editing the tree — right now," the general
  operating principle this gate is one more instance of, extended from the git working tree to the
  machine's gcloud identity.
