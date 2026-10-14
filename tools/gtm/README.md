# `tools/gtm/` — company-pack and logging foundation

This directory holds the runtime, company-agnostic GTM tooling from the GTM
Autonomous Department plan (`~/.claude/plans/gtm_autonomous_department_plan.md`),
Phase 1 part A: **P1 — Homes, packs, logging foundation** (§14), the
`company.json` schema (§3.1–§3.3), and mechanical logging (§11 items 2–3).

Everything here is Python stdlib only, no network calls, and every tool
takes `--company <slug>` (or a positional `<slug>`) rather than hardcoding
any one company's paths.

## The five tools

### `company.py` — resolve and validate a company pack

A "company pack" is `<home>/.claude/gtm/company.json`. Its presence — not
any registry flag — is what makes a registered repo a GTM company (§3.1).
`<home>` is resolved from ONE OF TWO registries, checked in this order:

1. **`~/.claude/knowledge/gtm_company_registry.json`** — a GTM-only,
   machine-local registry (shape: `{"schema_version": 1, "companies":
   {"<slug>": {"root": "<abs or ~ path>"}}}`), written and removed only via
   `company.py register`/`unregister` (below). This exists because
   `scripts/repo_manifest.py` is frozen (parked uncommitted work elsewhere)
   and its own `register` subcommand refuses a home with no GitHub remote
   — which every local-only company home (Brightline, Maplewood,
   Opswell) is.
2. **`~/.claude/knowledge/repo_registry.json`**'s `<slug>.root` (entries
   created by `scripts/repo_manifest.py register`) — for slugs NOT already
   in the GTM registry. CSA and Agency keep resolving here, unaffected.

**A slug present in BOTH registries is INVALID** (`resolve_home` raises;
`validate --all` reports it as `INVALID <slug>: registered in BOTH ...`)
— this tool never silently prefers one registry over the other for the
same slug, since that would hide a real configuration mistake.

```
python3 company.py resolve <slug>              # print the home path
python3 company.py validate <slug>|--all       # print OK / INVALID <reason> per pack
python3 company.py index                       # write ~/.claude/.gtm_state/identity_index.json
python3 company.py gitignore <slug>            # print the generated .gitignore block
python3 company.py backup-set <slug>           # print every path backup_state.py should archive
python3 company.py register <slug> --root <path>  # register a company home in gtm_company_registry.json
python3 company.py unregister <slug>           # remove a company from gtm_company_registry.json
```

`register` is atomic and refuses: a home whose `.claude/gtm/company.json`
is missing or fails `validate_company`; a slug already registered in
`repo_registry.json` at all (ALWAYS refused there, even at the SAME
root — that registry is `scripts/repo_manifest.py`'s own, and this tool
never writes to it); or a slug already registered in
`gtm_company_registry.json` to a **different** root (re-registering the
SAME root in `gtm_company_registry.json` specifically IS idempotent —
this is the ONLY case that re-validates and re-writes rather than
refusing). `unregister` refuses a slug not registered in
`gtm_company_registry.json` (it never touches `repo_registry.json`).

Validation is hand-written stdlib Python (`validate_company()` — no
`jsonschema` dependency); `company_schema.json` next to this file documents
every key for humans and is not itself read by the validator. Checks
include: unknown/missing top-level keys; `pack.slug` matching the registry
key it was resolved by; every `paths.*` value being home-relative (no
leading `/`/`~`, no `..`); `co_managing_systems` entries (§20.9/§20.13);
shared `credential_ref`/identity values across packs (§3.3); a wildcard
anywhere in a standing approval's `rows` (§6.4); secret-shaped content in
`company.json` or `<home>/.claude/gtm/mcp.json` (widened secret-key-name
and secret-value-pattern scan, plan `mcp.json` note in §3.2).

`generate_gitignore()` builds the `.gitignore` block for a pack's
ignored-class paths (§3.2) directly from that pack's own `paths.*` values
— never a hardcoded literal — using `dir/**` + `!dir/**/` + `!dir/**/*.md`
negation forms wherever a directory's `.md` docs must stay tracked.
`paths.metrics` is never ignored (§3.2: tracked config).

`backup_set()` returns every ignored-class path plus `.claude/gtm/state/`,
ignored mission records (when `paths.mission_records == "ignored"`), and
this company's own runtime cross-company state
(`~/.claude/.gtm_state/tickets/<slug>/`,
`~/.claude/.gtm_state/leases/<slug>.lock`) — the target set for
`backup_state.py`. Approval/cancel records under `.gtm_state/` are NOT yet
separable per-company on disk and are therefore NOT included; a company's
backup/restore is missing that piece until the on-disk layout changes.

### `activity_log.py` — the semantic (manual) activity log

The ONLY way manual entries enter a company's activity log. Generalizes
Brightline's original `tracking/activity_log/log_action.py`.

```
python3 activity_log.py add --company <slug> --system ... --action ... --object ... --why ... --actor ... [--undo ...] ...
python3 activity_log.py render --company <slug>              # regenerate ACTIVITY_LOG.md + owner mirrors
python3 activity_log.py check --company <slug>                # validate both JSONL files + hash chain
python3 activity_log.py backfill-changelog --company <slug> <path>
python3 activity_log.py audit --company <slug> [--days N] [--since ISO] [--include-local]
python3 activity_log.py explain --company <slug> --cluster <id> --why ... --object ... --undo ...
```

Paths come from the pack's `paths.activity_log_dir` (default
`.claude/gtm/state/activity_log`). `SYSTEMS` is the union of the pack's
`scope.channels_in_scope`, the original Brightline system list, and a fixed
added set including `gtm_browser` (the harvester's registered fallback
system name — see `harvest_tool_trail.py` below) and the generic
`gbp`/`facebook`/`website_wordpress` systems the default host→system
mapping can produce.

**Hash chain:** every new line carries `prev_hash` = sha256 of the
previous line's raw bytes. A legacy prefix with no `prev_hash` key is
accepted; `check` verifies the chain from the first chained line onward
and reports a break.

**`TOOL_TRAIL.jsonl.ids` sidecar (minor 17/#20):** `check` also verifies
this membership-index file (written next to `TOOL_TRAIL.jsonl`, same
`activity_log_dir`) is not DRIFTED from the trail — see the dedicated
sidecar subsection under `harvest_tool_trail.py` below for its format and
what "drifted" means; `check` fails (non-zero exit, `TOOL_TRAIL.jsonl:
sidecar drifted: ...` on stderr) when it is. Clearing a drift failure: run
a harvest (which self-heals a drifted sidecar by rebuilding it from a real
scan of the trail) or simply delete the `.ids` file — the harvester
rebuilds it from scratch on its next run either way. A trail with NO
sidecar at all (never harvested through the sidecar-aware tooling) is not
itself a drift and does not fail `check`.

**`check` blocks on a concurrent flush, and never initializes a fresh
home:** `check` takes the SAME activity-log lock `add` and every harvest
flush already take, for its whole read+verify pass — so a `check` run
against a company mid-harvest-flush WAITS for that flush to finish rather
than reading the trail while it is legitimately ahead of its sidecar
(which would otherwise report a false "sidecar drifted"). The one
exception: when the lock file's parent directory doesn't exist yet (a home
that has never logged anything, or a mistyped slug/layout), `check` skips
the lock entirely rather than creating that directory as a side effect of
a purely read-only verification — there is nothing to race when nothing
has ever been written.

**Agent-actor rule (§11.3):** `audit` counts only agent-actor entries as
explaining a mutating trail cluster (`is_agent_actor()`) — an actor counts
as an agent only if it matches a known shape: `<seat>:<agent_id>` where the
agent id looks like `a[0-9a-f]{8,}`, exactly `main-session` or `agent`, or
anything starting with `main-session`. Everything starting with `owner` or
`outside:`, and anything starting with `unknown`, is non-agent — this
covers the real Brightline shapes `"owner (via main session)"` and
`"unknown (backfill)"`.

`audit` also reports **`gtm-offserver`** rows unconditionally (a mutating
trail record flagged `offserver: true` by the harvester — see below) —
independent of whether its cluster is otherwise explained, since the point
is that the action ran outside the governed `playwright-gtm`
server/ticket system at all (plan §7.1, "detect-after").

**Mirrors:** written to `paths.mirror_dir` (or env `TS_ACTIVITY_MIRROR_DIR`
for tests) only when the pack sets one. Both a markdown mirror
(`<mirror_basename>.md`) and a self-contained HTML mirror
(`<mirror_basename>.html`, ported from the Brightline original's
`render_owner_html` — header totals, actor table, entries table with
client-side filter boxes that degrade gracefully with JS disabled,
"Features not yet used" built from `feature_inventory_dir`) are written.
`mirror_basename` and `mirror_title` are optional pack keys — default
`<TitleCasedLegalName>_Activity_Log` / `<display_names[0] or legal_name>
Activity Log`; Brightline's migrated pack pins both to its exact
pre-migration values (`Brightline_Activity_Log` /
`Brightline Activity Log`) so the operator's existing bookmark/file
reference keeps working. A mirror-write failure warns to stderr but never
fails the logging operation that triggered it (`render_all()`).

### `harvest_tool_trail.py` — the mechanical tool trail

Scans Claude Code transcript JSONL files and appends every relevant tool
call to the attributed company's `TOOL_TRAIL.jsonl`. Idempotent by
`tool_use_id` (checked across every company's trail plus the unattributed
sink, so a re-run or a changed identity index never duplicates).

**The `.ids` sidecar (minor 17/#20)** — `TOOL_TRAIL.jsonl.ids`, written next
to the trail file — is a membership index that makes idempotency checks
fast (`O(existing id count)`) instead of re-parsing the entire (potentially
many-MB) trail JSONL on every harvest run. Format: a first JSON header
line `{"size": <trail byte size>, "lines": <trail line count>}` recording
the trail's shape at the time the sidecar was last synced, followed by one
`tool_use_id` per line (sorted). A pre-#20 sidecar with no header line at
all is still readable (its first line is treated as an id, not a header)
and gets a header added the next time it's rebuilt.

Nit correction: the "fast, no-rescan" case is a matching *byte size*
(checked first, a single O(1) `stat()` call) — a line-count read of the
trail still happens whenever that size matches (to also confirm the line
count agrees, since two different files can share a byte size) or when a
real rescan is unavoidable (drift, or the sidecar's first build). The
`O(existing id count)` framing above describes the membership-index READ
itself (the id set is `O(existing id count)` regardless), not a claim
that no trail bytes are ever read on that path — an earlier draft of this
doc, and of `_trail_stats`'s own docstring, overstated that saving.

**Drift detection and self-healing:** the sidecar is trusted only when its
header's `(size, lines)` matches the trail file's CURRENT stats; on any
mismatch — a lagging sidecar, a crash between the JSONL append and the
sidecar update, or an out-of-band edit to `TOOL_TRAIL.jsonl` that bypassed
this tooling entirely — the harvester silently falls back to a full scan
of the trail and rebuilds the sidecar from scratch, exactly as it does for
a genuinely missing sidecar. This self-healing means a drift is invisible
during normal harvesting; `activity_log.py check` (see above) is the
independent surface that actually REPORTS a drift when one is found,
rather than silently curing it. Known blind spot: drift detection compares
`(size, lines)` only, never content — an out-of-band overwrite that
happens to produce the exact same byte size and line count as before is
indistinguishable from "unchanged" and is trusted anyway.

```
python3 harvest_tool_trail.py                     # default globs (see below)
python3 harvest_tool_trail.py <path> [<path>...]  # explicit transcript files
```

**Default globs** cover only registered homes' project dirs (derived the
way Claude Code itself names them: the absolute home path with every `/`,
`_`, `.`, and space replaced by `-`) plus the Brightline legacy
working-directory project dir — never a blanket scan of every project on
the machine.

Also included: any project dir for a **subfolder or worktree** of a
registered home — e.g. `<home>/.claude/worktrees/<name>` or
`<home>/repo_tooling/demo_video`, whose derived directory name extends the
home's own with `-<sub-component>` — matched with a separator-bounded
prefix check (exact name, or the home's derived name followed by `-` and
at least one more character), never a bare `str.startswith`, which would
also match an unrelated sibling directory that merely shares the same
prefix characters (e.g. `...-Repo` bare-matching `...-RepoOther`).

Because that prefix match is still directory-NAME-level and therefore
admits some false positives (name derivation is lossy — `/`, `_`, `.`, and
space all collapse to the same `-`, so no name-only rule can fully
distinguish a real subfolder from a same-prefix sibling), every
glob-matched candidate is then narrowed against its own recorded `cwd`
field: kept only when `cwd` is under one of this run's registered homes
(or the Brightline legacy dir), or when the transcript carries no readable
`cwd` at all (fails open, rather than silently excluding a transcript this
tooling can't inspect).

**Capture scope:** only **mutating** browser calls are captured at all, via
either of two paths: (a) any playwright MCP server, when the call's
URL/host or account id is in the cross-company identity index
(`~/.claude/.gtm_state/identity_index.json`, written by
`company.py index`); or (b) any mutating call on the `playwright-gtm`
server specifically, regardless of host. A non-mutating call (navigate,
snapshot, hover, ...) is never captured. `cwd`-based attribution is used
only as rung 2, and only for the `playwright-gtm` server — there is no
"cwd alone" fallback for any other server.

**Attribution precedence (§11.3, narrowed):**
1. an identity-index host or account id appearing in the call (any server)
2. `playwright-gtm` server + the transcript record's `cwd` under a
   registered home that has a loadable GTM pack (a home registered — e.g.
   in `repo_registry.json` — for other tooling, with no
   `.claude/gtm/company.json` at all, is not a GTM company and is never a
   rung-2 attribution target; §3.1)

A mutating call that IS eligible for capture (matched path (a) or (b))
but whose attribution still cannot resolve to exactly one company is
appended to `~/.claude/.gtm_state/unattributed_trail.jsonl` instead of any
company's trail — never silently dropped, never guessed.

**Exit codes / reroute:** `main()` exits non-zero when a call gets
attributed to a company slug (via the identity index or rung 2) that turns
out to have NO resolvable trail path — a stale `identity_index.json`, an
unregistered/duplicate slug, or a `load_pack`/trail-path failure for an
otherwise-registered, otherwise-packed company. That record is never
dropped; it is rerouted to the unattributed sink and a warning names the
slug and count. The exit code reflects only a genuinely NEW reroute this
run (an unattended run re-scanning the same transcripts a second time,
with the record already recorded from the first run's reroute, exits 0) —
never merely "an unresolvable company was seen". Once a record lands in
the unattributed sink this way, it stays there permanently: idempotency is
global (by `tool_use_id`, across every trail including the sink), so
fixing the underlying configuration afterward does not move or re-attribute
an already-rerouted record on a later run.

**`gtm-offserver`:** a mutating call on a non-`playwright-gtm` server that
DID match an identity host (capture path (a)) is still attributed and
captured, but flagged `offserver: true` in its trail record — this is the
"browser off-server bypass" the plan calls detect-after (§7.1). `activity_log.py audit` reports these rows unconditionally.

**Host → system mapping (`host_system_for_url`):** a company's own pack
key `host_systems: {host: system}` (checked first, in insertion order),
then `DEFAULT_HOST_SYSTEMS` (the common platforms: `ads.google.com` →
`google_ads`, `analytics.google.com` → `ga4`, `tagmanager.google.com` →
`gtm`, `business.google.com` → `gbp`, `facebook.com`/
`business.facebook.com` → `facebook`, `instagram.com` → `instagram`,
`yelp.com` → `yelp`, `angi.com`/`homeadvisor.com` → `angi`,
`thumbtack.com` → `thumbtack`, `houzz.com` → `houzz`, `nextdoor.com` →
`nextdoor`, `bbb.org` → `bbb`, `businessconnect.apple.com` →
`apple_business`, `bingplaces.com` → `bing_places`,
`search.google.com`/search-console → `search_console`,
`localservices.google.com` and `ads.google.com/localservices` → `lsa`),
then a pack-domain + `/wp-admin`/`/wp-login.php` path special case →
`website_wordpress`, else the registered fallback system `gtm_browser`
(never an unregistered literal — `gtm_browser` is a real member of
`activity_log.py`'s `SYSTEMS`).

**`host_systems` is HOST-LEVEL ONLY by default (#27 caveat):** a plain
`{host: system}` entry cannot tell two brands apart when they share a
host — e.g. two sibling brands of the same company both using
`business.google.com` (GBP) and `facebook.com`. For that, a `host_systems`
key MAY instead be `<host>/<path-prefix>` (e.g.
`"business.google.com/9000000000000000001"`, a GBP location id, or
`"facebook.com/100000000000001"`, a Facebook Page id) — despite the name
"path-prefix", this is NOT a prefix match: the id is matched when it
appears at a token boundary (not immediately preceded or followed by
another alphanumeric character) ANYWHERE in the URL's path or query
string, checked BEFORE any plain host-only entry for the same host, so
the more specific per-brand mapping always wins; a plain host-only entry,
if also present, is the fallback when no brand-specific id appears in the
URL at all. If both brands' ids happen to appear in the same URL (e.g. a
`ref=` query parameter carrying the other brand's id), the FIRST matching
`host_systems` entry in dict insertion order wins — prefer putting the id
that appears in the URL's path over one that could appear only in a query
string, when a pack can predict which case is more common for its own
traffic.

**Concurrency:** every trail append is taken under the same flock
`activity_log.py` uses for that company's `ACTIVITY_LOG.jsonl` (both files
live in `activity_log_dir`) — this spans the read-last-line-then-append
sequence, so two concurrent harvesters (or a harvester racing an
`activity_log.py add`) can never both compute `prev_hash` from the same
"last line" and fork the chain.

### `backup_state.py` — backup/restore a company's ignored-class state

```
python3 backup_state.py --company <slug> [--dest-root DIR]
python3 backup_state.py --restore <tgz> --to <dir> [--runtime-state-to DIR] [--company <slug>]
```

The backup set is exactly `company.py backup-set <slug>`'s output, tarred
to `<dest-root>/<slug>/<YYYY-MM-DD>.tgz` (default dest root
`~/Backups/gtm`, overridable via `--dest-root` or env
`GTM_BACKUP_DEST_ROOT`), keeping the newest 8.

**Restore safety:** every archive member is validated BEFORE any member is
extracted (all-or-nothing — a crafted archive can never get partial
trust). Rejected: absolute or home-relative (`~`) member paths, any `..`
path component, a symlink/hardlink whose target resolves outside the
restore directory, and device/special files (char/block device, FIFO). The
outside-target check uses `Path.is_relative_to()` (a real path-component
comparison), never a bare string-prefix check — a sibling directory that
merely shares the restore directory's path as a string prefix (e.g.
`restore_evil/` vs `restore/`) is correctly judged NOT inside it.
`UnsafeArchiveMember` is raised on any violation.

**Runtime cross-company state (`--runtime-state-to`, minor 18/#22):** a
company's backup set includes two paths that live OUTSIDE its home, under
the runtime's shared `~/.claude/.gtm_state/` tree —
`tickets/<slug>/` and `leases/<slug>.lock`. These are archived under a
`_gtm_state/<slug>/...` prefix (never under a bare filename, and never
mixed into the home-relative members), and restore refuses to place them
anywhere but an explicit `--runtime-state-to <dir>` — an archive
containing any such member with no `--runtime-state-to` given raises
`RuntimeStateRestoreRefused` and extracts NOTHING (all-or-nothing, same
discipline as the member-safety checks above). The `_gtm_state/<slug>/`
prefix is STRIPPED on restore, so `--runtime-state-to
~/.claude/.gtm_state` reproduces each file's ORIGINAL path directly
(`~/.claude/.gtm_state/tickets/<slug>/...`,
`~/.claude/.gtm_state/leases/<slug>.lock`) — never nested under an extra
`_gtm_state/<slug>/` layer that never existed on disk before the backup.

**⚠️ Restoring into the live `.gtm_state` directory OVERWRITES current
tickets and lease files in place.** `--runtime-state-to
~/.claude/.gtm_state` (or any directory that IS the machine's real,
in-use `.gtm_state` tree) replaces whatever tickets/leases are there right
now with the backup's snapshot — including a lease file, which can WEDGE
a run if it restores a stale/held lease over a currently-clear one. Prefer
restoring to a scratch directory first and inspecting/copying selectively,
unless you specifically intend to roll runtime state back to the backup's
point in time.

**`slug` auto-detection:** the slug used to strip the `_gtm_state/<slug>/`
prefix defaults to the one auto-detected from the archive's own
runtime-state members (every member in one company's own backup shares
the same slug segment). `--company <slug>` only CONFIRMS or PINS the
slug to use — it does not, and cannot, fix a mismatch: whichever of
`--company` or auto-detection supplied the effective slug, it must equal
the slug of EVERY runtime-state member actually present in the archive,
or the restore is refused outright (`RuntimeStateRestoreRefused`) and
nothing is extracted (all-or-nothing, same discipline as the
member-safety checks above). Two ways this refusal fires: the effective
slug matches NONE of the members (e.g. `--company` names the wrong
company entirely), or the archive is a MIXED-slug archive (most members
share one slug but at least one carries a different slug) — nit fix #10:
the refusal applies to a partial mismatch too, not only a total one, and
applies identically whether the slug came from `--company` or from
auto-detection. Neither an explicit `--company` nor auto-detection can
ever be used to attribute an archive's runtime-state members to a slug
other than the one they were actually backed up under — do not pass
`--company` expecting it to relabel or repair a mixed-slug archive.

### `exit_contract.py` — mission convergence evaluator

Decides mechanically whether a GTM mission's current round has converged, by reading the dissent
ledger (`gtm_reviewed.jsonl` under the repo manifest's `gtm.missions_dir`; schema in
`MISSION_SCHEMA.md`) instead of trusting an agent's claim of consensus. Its three assertions are
named `GTM-CONV-01` to `GTM-CONV-03`; the module docstring defines each one.

## Design contracts: `CONTRACTS.md` and `contracts/` (design contracts; partially implemented)

`CONTRACTS.md` and the files under `contracts/`, including `contracts/requests/` (the change requests
between contract files), are **design contracts; partially implemented**. They are the interface
specification written for the GTM department's next build wave: file shapes, record fields, commands
and exit codes. Nothing in this directory's code reads them (the tools above take their behaviour from
their own code and from `company_schema.json`), and only part of what they specify exists. Agent
definitions and knowledge-base pages cite sections of them as the intended shape of pieces that are
not built yet (for example `contracts/08_seats_wps.md` §8.5). They are not frozen:
`contracts/OPEN_FINDINGS.md` records points that were still open. Where a contract and the shipped
code disagree, the code is what runs today; report the disagreement as an issue.

## Running the tests

Same convention as the existing `tools/gtm/tests/test_gtm_exit_contract.py`:

```
cd ~/.claude && python3 -m pytest tools/gtm/tests/ -q
```

Every test builds its own tmp `CLAUDE_DIR` + registry + pack (via the
`CLAUDE_DIR` env override every tool in this directory respects) — none of
them read or write the real `~/.claude`, a real company home, or
`~/Desktop`. `test_mirror_parity.py` is the one exception with a live
dependency: it imports the real Brightline
`tracking/activity_log/log_action.py` **read-only** (never modifies it) to
prove the ported mirror renderers are byte-identical; it self-skips if that
file is absent from the machine.

## Pack keys this directory reads

See `company_schema.json` for the full, authoritative list. Keys
introduced or widened by this Phase 1 work specifically:
`paths.build_dir`, `mirror_basename`, `mirror_title`, `host_systems`,
`co_managing_systems[].interface`. Plan citations: §3.1–§3.3 (pack schema
and layering), §3.2 (tracked vs. ignored classes, `.gitignore`
generation, backup set), §6.4 (standing-approval row ids, never a
wildcard), §7.1 (G-A default-deny and the off-server detect-after
posture), §7.6 (the identity index), §11 items 2–3 (activity log + tool
trail), §20.9/§20.13 (`co_managing_systems`, identity+interface keying).
