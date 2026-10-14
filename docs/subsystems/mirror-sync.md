# Runtime mirror sync

**Module:** `hooks/runtime_mirror_sync.py` · **Trigger:** `hooks/posttooluse_bash.py` (job 3)
· **Config:** `~/.claude/.mirror/config.json` (untracked — no config means the whole subsystem
is inert)

## What it does

Keeps a GitHub mirror of this runtime's committed content current, automatically: every time a
`git push` leaves this machine from **any** repo (detected by the `PostToolUse:Bash` dispatcher),
a detached background process exports `~/.claude`'s `HEAD` — never the working tree — into a
local clone of the mirror repo, applies a redaction map, verifies nothing forbidden survived,
and commits + pushes the result. The operator's own push is never slowed; the sync runs fully
detached.

This exists so that the runtime repo on GitHub is always current enough that someone can clone
it as their own `~/.claude/` and run the same agentic system.

## The pipeline, in order

1. **Config validation — the authorization is enforced, not assumed.** `validate_config()`
   rejects (→ whole subsystem inert, reason logged) any config whose `clone_dir` doesn't resolve
   under `~/.claude/.mirror/`, whose `remote_url` isn't a well-formed GitHub https/ssh URL,
   whose branch has disallowed characters, or whose manifest entries aren't clean relative
   paths (no `..`, no absolute, no leading `-`). Positionals are passed after `--`, and the
   clone's actual `origin` must equal `remote_url` at push time. The config is untracked and
   locally writable, so nothing in it is trusted until it passes.
2. **Trigger** — `maybe_trigger(ev)` in the dispatcher: is this Bash event a `git push`
   (tokenized with `_lib.git_segments`, so `ENV=` prefixes and `git -C` are handled)? Is config
   valid? Is the push not the mirror's own? Then spawn `--sync` detached. Degrades **open**.
3. **Short-circuit** — runtime `HEAD` unchanged since the last successful sync → no-op.
4. **Export** — `git archive HEAD -- <path>` per manifest entry, extracted over the clone
   (each path is wiped first so upstream deletions propagate; a manifest entry gone from both
   HEAD and the mirror index drops out of the pathspec rather than making `git add` fatal).
   `mirror_managed` paths (`CLAUDE.md`, `README.md`, `LICENSE`, `.gitignore`, `settings.json`,
   `knowledge/repo_registry.json`) are **never** overwritten — those are curated by hand at
   milestones — but they ARE still scanned (step 6), since they publish too.
5. **Redact** — the config's ordered literal replacement pairs, applied to every exported text
   file. Files the gate can't vouch for — binaries, files over 4 MB, non-UTF-8 text, symlinks —
   are **excluded from publish entirely** (removed from the export, logged). A *mirror-managed*
   binary (a hand-curated logo, say) can't be excluded that way — it publishes only via an
   explicit `"<unscannable>"` `forbidden_allow` entry for that exact path. The mirror is a text
   mirror by construction.
6. **Gate — fails closed** — everything that would publish (fresh export + managed files + every
   other path `git ls-files` says the clone tracks) is scanned for the config's forbidden
   regexes, and exported `.py`/`.json` must byte-compile/parse post-redaction. Any hit
   **withholds the push entirely** and writes `.mirror/BLOCKED.md` naming each file and pattern.
   A novel operator-specific string upstream parks the mirror rather than leaking; the next
   session extends the replacement map and re-runs `--sync`. A diff that would delete more than
   half of what was previously published (and more than 20 files) is also refused — a broken
   export looks exactly like that — with `CSA_MIRROR_ALLOW_MASS_DELETE=1` as the deliberate
   override for a real restructuring.
7. **Publish — success verified, never inferred.** The clone's `origin` URL must equal the
   config's `remote_url` and its checked-out branch must equal `branch` *before* anything is
   mutated. Path-scoped `git add`/`commit` over the manifest paths; then anything local ahead of
   `origin/<branch>` is pushed **whether or not this run produced a new diff** — so a failed
   push is retried by the next sync, never erased by a later "no diff" run — and after a push,
   `origin/<branch>` must equal `HEAD` or the run fails without recording state. Concurrent
   syncs serialize on `.mirror/sync.lock` (a held lock means a live sync — the second invocation
   skips). **Every failure is surfaced**: any non-zero outcome writes `.mirror/last_error`
   (cleared on the next success). Everything logs to `.mirror/sync.log`.

## Operations

```sh
python3 ~/.claude/hooks/runtime_mirror_sync.py --status  # STRICTLY read-only state report — see
                                                         # "--status" below; safe on any cadence,
                                                         # even mid-sync, writes nothing ever
python3 ~/.claude/hooks/runtime_mirror_sync.py --check   # health probe: exit 0 only when config
                                                         # is valid, mirror current, nothing
                                                         # blocked (may append one log line)
python3 ~/.claude/hooks/runtime_mirror_sync.py --sync    # run one sync now
python3 ~/.claude/hooks/runtime_mirror_sync.py --dry-run [--config PATH]
                                                         # export + redact + gate into a temp dir,
                                                         # print the report, publish NOTHING, touch
                                                         # no .mirror state — see "--dry-run" below
cat ~/.claude/.mirror/sync.log                           # what happened, when
cat ~/.claude/.mirror/BLOCKED.md                         # why a push was withheld (if it was)
```

## `--dry-run [--config PATH]` — rehearse a sync without publishing (added 2026-10-13)

Runs the same export, redaction and forbidden-pattern gate stages as `--sync` (they are shared
functions, not a copy), into a `tempfile.mkdtemp` that is removed on exit, and prints a report:
forbidden-pattern hits by **file and pattern name only — never the matched text**; replacements that
landed inside a quoted string literal of a `.py`/`.sh`/`.mjs`/`.js`/`.cjs`/`.json` file as
`file:line`, a count and the replacement index (advisory — these never change the verdict); `include`
entries not in the runtime's `git ls-files` (would never export) and entries tracked but absent at
HEAD (the export skips them); files excluded from publish (binary/oversize/non-UTF-8); a `gate:` line
counting the patterns, replacement pairs and allow entries actually in force; and a verdict line —
`DRY-RUN CLEAN` (exit 0), `DRY-RUN BLOCKED: N hit(s)` (exit 1), or `DRY-RUN ERROR: <reason>` (exit 1:
a stage could not run — config rejected, HEAD unresolvable, export/redaction/git failure, the
`include` membership listing unreadable). A failure never reads as clean.

A gate that is not there is an error, not a clean: `forbidden_patterns` missing, empty, or not a list
of strings exits 1 with `DRY-RUN ERROR: no forbidden_patterns configured` (the real `--sync` reads that
key with a default of `[]`, so a misspelled key would otherwise gate nothing); unknown top-level config
keys are listed **by name** so the typo is visible. The report **never prints an exception's repr or
message** — a `UnicodeDecodeError` carries the raw config bytes (replacement values included) and a
`UnicodeEncodeError` the full text being written — only the exception type
(`config unreadable (UnicodeDecodeError)`, `redaction failed for <file> (UnicodeEncodeError)`).

It writes no state (`last_synced_head`, `sync.lock`, `sync.log` are untouched — proven by a
before/after `stat` snapshot of the whole `.mirror/` tree), takes no lock, does not fetch, and **never
writes to the clone**: the temp tree is seeded from the clone's **index** with
`git checkout-index -a --prefix=<temp>/` (no `-u`), because `--sync` first resets the clone's working
tree to the index (`git checkout -- .`) and gates *that*. A dirty working tree (say, a prior blocked
sync's leftovers after an `include` shrink) therefore cannot make the dry run disagree with `--sync`,
and tracked files deleted from the working tree, and gitlinks, are still gated. It scans the clone as
last synced. **Rails**, each with its own test in
`hooks/tests/test_mirror_sync_dry_run.py`: `--dry-run` with `--sync`, `--status` or `--check` is a
usage error (exit 2) decided before anything runs; `--config` is accepted ONLY with `--dry-run` — the
standing push authority stays bound to `.mirror/config.json`, and a candidate config still passes the
unchanged `validate_config()` (its `clone_dir` must resolve under `.mirror/`). This is the
pre-check for any edit to the redaction map or the `include` list: edit a copy, `--dry-run --config
<copy>`, move it into place only when the verdict is clean.

To disable: remove or rename `.mirror/config.json`. To re-point at a different mirror repo:
edit `remote_url`/`clone_dir` in the config and delete `.mirror/last_synced_head`.

## `bundle_parity` — completeness, not content

`--check` also runs `hooks/bundle_parity.py` and prints its finding count (`bundle_parity: N
finding(s)`) — advisory only, never folded into `--check`'s own exit code. The distinction: this
module (`runtime_mirror_sync.py`) keeps the mirror's **content** in sync — it exports, redacts,
and pushes whatever `include` names, on every push. `bundle_parity` keeps the bundle's
**completeness** in sync — it asks whether everything a runtime agent, primer, skill, or command
actually *reads or names* (a primer path, an oversight dossier template, a `skills/`/`tools/`/
`scripts/` literal, a `knowledge/` path) is itself in `include` and tracked, so a clone of the
mirror is not silently missing something its own agents depend on. A perfectly-synced mirror can
still have a nonzero `bundle_parity` count (e.g. a new agent's primer landed in the roster before
its `include` entry did) — that is a real gap for `runtime_bundle_repo_agnostic_plan.md`'s own
acceptance assertions to close, not a mirror-sync fault, which is why it never affects this
command's exit code. Full rule set and design rationale: the module's own docstring
(`hooks/bundle_parity.py`); wired the same way into `schedules/prompts/daily_sweep.txt`'s
self-check leg and `commands/sweep.md`'s fixed pre-steps.

## `--status` — the read-only health probe

`--check` is a boolean gate: exit 0 only when everything is healthy, and it may append a log
line to get there. `--status` is its machine-consumable sibling for a *watcher* — something that
polls on a schedule and needs to relay *which* thing is wrong, not just that something is. It
reports exactly one of four states, leads line 1 with the bare state token (`awk '{print $1}'`
gets it), and returns a distinct exit code per state (`STATUS_EXIT_CODES` in the module —
deliberately not `1` or `2`, since `--check`'s flat "unhealthy" already owns `1` and `main()`'s
usage no-op owns `2`):

| state     | meaning                                                            | exit |
|-----------|---------------------------------------------------------------------|:----:|
| `OK`      | config valid, nothing blocked, mirror is at runtime HEAD             | 0 |
| `BLOCKED` | `.mirror/BLOCKED.md` exists — the gate withheld a push                | 3 |
| `DRIFTED` | nothing blocked, but `last_synced_head` != runtime HEAD               | 4 |
| `INERT`   | config missing / unreadable / rejected — the whole subsystem never runs | 5 |

Precedence is decided in that order, `INERT` first — an inert subsystem never even logs a block
(step 1's rejection means nothing downstream runs at all), and `BLOCKED.md`'s own remediation
("extend the replacement map") would be the wrong instruction when the real problem is an
unparseable config.

**The load-bearing property is that it is strictly read-only** — no copy, commit, push, state
write, log line, or network call, ever. It runs on `config_status()`, which is `load_config()`
minus its `_log()` calls: `load_config()`'s REJECTED path *writes* to `sync.log`, which is exactly
the side effect a status check must not have on every poll — that was the trap a naive
implementation would have fallen into. Every git read goes through `_git_out()`, which swallows
any failure (missing git, unreadable repo, a timeout) into a reported state rather than a
traceback, so a watcher can run it unconditionally. This is what makes it safe to run on any
cadence, repeatedly, concurrently with a real `--sync` in flight.

Verified live, on this machine:

```
$ python3 ~/.claude/hooks/runtime_mirror_sync.py --status
DRIFTED  mirror is 1 commit(s) behind runtime HEAD 514c3a37f7
config:        valid (branch master -> https://github.com/example-org/claude-agentic-runtime.git)
runtime HEAD:  514c3a37f78e411ae45b2fd60c4de51f0fb1a902
last mirrored: fadb5bc9edce2da69e3f0291f240f86b93b64d20
commits behind:   1
blocked:       no
last error:    none
$ echo $?
4
```

`DRIFTED` here is expected, not a fault: mirroring happens on push, push is ask-gated (§4), and
the runtime had moved one commit past the last mirrored push at the moment this was run — it
clears on the next push. The read-only claim is provable, not just asserted: sha256, mtime, and
size of every file under `~/.claude/.mirror/` are identical before and after a `--status` run —
`sync.log` is never appended to and `BLOCKED.md`/`last_error` are never touched.

Tested by `hooks/tests/test_mirror_sync_status.py` — all four states, every precedence pair, the
read-only property (a directory snapshot taken before/after each state), and one test that drives
a real `sync()` into a real gate hit so `BLOCKED.md` parsing is checked against the module's own
writer rather than a hand-built fixture.

## The watcher — closing the invisible-failure gap

Every failure mode above already had an output *file* — `BLOCKED.md`, `last_error`, `sync.log` —
and for most of this module's life nothing ever read them. From the live log:

```sh
grep -c 'sync: FAILED — BLOCKED' ~/.claude/.mirror/sync.log   # 9, as of this writing
grep -c 'sync: pushed mirror'    ~/.claude/.mirror/sync.log   # 2, as of this writing
```

**9 `BLOCKED` sync attempts against 2 successful pushes, lifetime** — the mirror sat quietly
stale between them with nothing surfacing that fact anywhere but a log file nobody was tailing.
One block sat unnoticed for roughly two and a half hours (2h18m by the log's own timestamps:
`12:45:25Z` first blocked → `15:03:26Z` the fix landed and pushed) — see Troubleshooting below for
what that block actually was. Re-derive both counts rather than trusting the frozen numbers above;
they only grow.

`--status` is the reporter built to close this: a distinct, parseable state a watcher can branch
on instead of parsing prose. **As of this writing, nothing yet reads it** — no scheduled job,
oversight dossier, or `/sweep` dimension invokes `--status`. The intended consumer is sentinel's
rotating `health` slot (`com.oversight.csa.daily`'s health/logs/cost rotation — see
`knowledge/oversight_install.md` §2), the same pattern `sentinel_primer.md` §8 already documents
for its own loop-telemetry leg: designed, inert until wired, and activation is the operator's, not
the agent's. Reading `--status` once at the top of the health dimension and filing anything but
`OK` through board-steward's rules (§13) is the step that turns a written-but-unread file into a
caught incident — that wiring has not landed yet.

## Troubleshooting a BLOCKED gate

Worked from a real instance from today, because the failure mode is instructive, not
hypothetical.

`scan_forbidden()` applies every `forbidden_patterns` entry as a **regex**, matched with
`re.IGNORECASE` — not a literal substring match. The config's vendor-token entry (guarding against
the vendor name, `<Token>Provider`, and `<token>_provider.py` leaking) was an unanchored
substring, so it also matched inside `<unrelated-domain>.com` — a legitimate public citation
in `knowledge/test_architect_primer.md` (Vladimir Khorikov, "When to Mock"), nothing to do with
the vendor. The push was withheld three separate times before anyone looked at `BLOCKED.md`.

**The fix:** `<token>(?!<suffix>)` — a negative lookahead, not a word boundary. The tempting fix,
`\b<token>\b`, is wrong, and it's worth recording why: it tests clean against the false
positive, but it **leaks** the two names the pattern exists to catch, because `\b` doesn't fire
between two word characters, and neither `<Token>Provider`'s capital `P` nor
`<token>_provider.py`'s `_` breaks a `\w` run. Verified directly:

| input                          | `\b<token>\b`      | `<token>(?!<suffix>)`  |
|--------------------------------|-----------------------|-----------------------|
| `<unrelated-domain>.com`  | no match — correct    | no match — correct    |
| `<Token>Provider`            | **no match — LEAK**   | match — correct       |
| `<token>_provider.py`        | **no match — LEAK**   | match — correct       |

**The general rule:** when adding or narrowing a forbidden pattern, test it against *both* a real
reference that must still be caught *and* the false positive being fixed. A redaction gate's two
failure modes are not symmetric — a false block is visible and annoying (a withheld push,
`BLOCKED.md` naming exactly what to fix); a leak is silent and permanent (the string is already on
GitHub by the time anyone notices). Optimize for catching the leak, not for a clean pass against
the one example in front of you.

`BLOCKED.md`'s body is fixed and simple — a `Source HEAD:` line, then one `` - `path` matched
`pattern` `` line per hit — reproduced verbatim by `--status`'s `parse_blocked()` rather than
re-derived, so a watcher relays exactly what the gate saw, not a paraphrase of it.

**Why a leak can't hide in bytecode.** The publish surface carries no binaries and no `.pyc`
files: `.gitignore` excludes `**/*.pyc` and `**/__pycache__/`, so `git archive HEAD` — step 1's
committed-content-only source — never even contains them, and the gate's own binary/oversize/
non-UTF-8 exclusion (pipeline step 5, above) is a second, independent backstop for anything else
that isn't scannable text. The replacement map only ever operates on decoded text, so there is no
path by which an unredacted string escapes inside compiled bytecode.

## Authorization scope

Push is normally ask-gated per the operating contract (§4). This module carries a standing,
deliberately narrow operator authorization (2026-08-30): the **only** push it may perform is
`clone_dir → remote_url` as named in its own config. It never pushes `~/.claude` itself, never
pushes a product repo, and never force-pushes.

## For adopters

The exported copy of this module ships with **no config**, so it does nothing until you create
`~/.claude/.mirror/config.json` pointing at your own mirror repo with your own redaction map.
The full schema, by example:

```json
{
  "remote_url": "https://github.com/your-org/your-runtime-mirror.git",
  "clone_dir": "~/.claude/.mirror/your-runtime-mirror",
  "branch": "main",
  "include": ["agents", "hooks", "docs", "knowledge/model_policy.json"],
  "mirror_managed": ["CLAUDE.md", "README.md", "LICENSE", ".gitignore"],
  "replacements": [["YourRealCompany", "ExampleCo"], ["/Users/you", "~"]],
  "forbidden_patterns": ["yourrealcompany", "co-[0-9a-f]{20}"],
  "forbidden_allow": {
    "LICENSE": ["yourrealcompany"],
    "assets/logo.png": ["<unscannable>"]
  }
}
```

`include`/`mirror_managed` entries must be clean relative paths; `clone_dir` must resolve under
`~/.claude/.mirror/`; `remote_url` must be a GitHub https/ssh URL. `forbidden_allow` maps one
exact file to the pattern strings permitted in it — the special entry `"<unscannable>"` exempts a
mirror-managed binary (e.g. a logo) from the no-unscannable-publish rule, deliberately and per
file.
