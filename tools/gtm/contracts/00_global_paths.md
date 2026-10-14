# GTM Wave-2 interface contracts — §0 Global rules, §1 Paths, environment, test isolation

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md).

**What this is.** The one interface document that every Wave-2 work package (WP) builds from without
talking to the others. If two WPs touch the same file, record, command, or env var, its exact shape
is here. Implementers code to this document, write their own tests against the example records in
it, and never invent a field, path, flag, or exit code that is not listed here.

**Source of truth.** `~/.claude/plans/gtm_autonomous_department_plan.md` (v15). Its §20 (operator
rulings 2026-09-27, incl. §20.9 v15 and §20.13–§20.17) supersedes every earlier section it conflicts
with. §17 (probe results) is binding fact. This document fixes shapes and adds no policy of its
own, except the items **listed in this paragraph** — every one a narrowing that only withholds
(the former loosening (viii) is withdrawn, below). The first is
the interim OtherApp `website_static` deny of §0.1 "§20.9c and §20.9a", a narrowing of what plan
§20.9c allows. §20.9c stands as ruled; the interim lasts only until the reviewed carve-out design
named there lands **and** the §0.1 "Follow-up" (2) site/paths question is answered (both, as §0.1
states), not until the operator re-confirms a ruling already given. The derived
narrowings are this file's reading of §20.9c's "never … developing (application code,
infrastructure)", each **DECIDED HERE** with its reason in §0.1 "The `marketing_paths` guardrail"
and indexed in 08_seats_wps.md Appendix B (`requests/00_global_paths.md` R35): (i) tracking,
pixel and consent snippets are out of scope for `website_static` (they go to the measurement
rows, plan §6.3); (ii) the never-list of build/config/infrastructure files (`.gitignore`,
`*.toml`, `*.yml`/`*.yaml`, `.htaccess`, `_headers`, `_redirects`, `*.lock`, `Makefile`,
`Dockerfile`, `tsconfig*.json`, `.pre-commit-config.yaml`, `**/.github/**`) has no pack override;
(iii) a displayed price may change only inside a declared price-display file and only to the
value, billing period and tier label of its named slot in the ruled source, and the ruled source
itself is write-protected from GTM scope and GTM seats (§0.1, plan §20.9c "Changing an actual price
… never a GTM edit"). **Other policy-level DECIDED-HERE items (listed so the "no policy of its own"
claim stays checkable; `requests/00_global_paths.md` R41, R42, R43). Items (iv)–(viii) are
narrowings that only withhold:**
(iv) `autonomy --card` is withdrawn, so leaving shadow needs met criteria or a signed operator
marker (§1.4); (v) in the GTM scope of a pack with `regulated` ∋ `hipaa`, every read target
outside the company home, the trust-architect-allowlisted OtherCompany folders, the **narrowed**
runtime read roots (never `R/projects/` as a whole, never another session's transcripts) and the
calling session's own scratchpad is denied (§1.2 "OtherCompany read scope"), and a missing or
unparseable `phi_denylist.json` fails closed for **every** GTM scope and GTM seat, hipaa pack or not
(§1.2, plan §20.3 prevention-first); (vi) Desktop-level (and other operator-named) Open
Dental-derived files are enumerated by name, classified by trust-architect and denylisted **before
the first GTM session of any company** — the launchers refuse to start until that has run, and
every GTM scope and GTM seat is default-deny outside its allowed roots while it has not (§1.2
"Top-level PHI classification is a precondition", plan §20.3, which bans Open Dental exports for all
GTM sessions, not only OtherCompany scope); (vii) every `revert --approval` of a revert child that
step 1 neither executes nor holds is a **signed** approval: a non-money child uses the amount-less
approval request signed over its `after_digest` in every pause state, never a card (§1.4 "The card
route", plan §20.8 "`revert --approval <card id>` (§6.8) means 'a signed approval for that revert
action'", read literally rather than as money-only); (viii) an unattributable
`S/lead_spool/_unknown/` file is treated as possibly prospective-patient data and purged on the
plan §20.4/§20.13 30-day window like a hipaa slug's spool, with an urgent replay notice from 24
hours onward (§1.2). **No loosening remains (wave1c):** the former loosening (viii) ("`_unknown`
never purged by age", reasoned from plan §5/§6.8) is withdrawn, because plan §20 is headed
"SUPERSEDE any conflicting text above" and §20.4 covers OtherCompany forms — a contract that adds no
policy of its own cannot rank §5/§6.8 above it (`requests/00_global_paths.md` R43).
The Agency arm for sub-agents
(§0.4) is **not** a policy item: it is scoped to GTM work only, exactly as §20.9a binds it; nor is
its "Agency session files" clause, which applies §20.9's "never reads through anything from Agency"
to the transcripts and scratchpads Agency's sessions leave outside `A`. Every choice the plan left open is marked **DECIDED HERE** with its reason and indexed in
08_seats_wps.md Appendix B. Every place the plan contradicts itself or the committed code is listed in 08_seats_wps.md Appendix C.

**Already built, never redefined here** (read their real code): `tools/gtm/company.py`,
`company_schema.json`, `activity_log.py`, `harvest_tool_trail.py`, `backup_state.py`, `README.md`.
**The baseline (what "committed" means in this file).** Commit `44b9bf5` **plus** the follow-up
that is still **uncommitted** in the `~/.claude` working tree (it adds
`knowledge/gtm_company_registry.json` handling, `company.py register|unregister`, and
`_repo_registry_repos()`). That working tree is still moving (its size changed during review), so
this file quotes **no** line counts or line numbers for committed code: every reference names the
function and quotes the statement it means (e.g. `harvest_tool_trail._read_transcript_cwd`'s
`return Path(cwd).resolve()`), which survives edits above it. Where `44b9bf5` and the working tree
differ, the working tree wins until the sha below is recorded. **Coordinator gate:** the follow-up
is committed and its sha is recorded in `../CONTRACTS.md` before any WP starts, WPs build on that
sha, and that sha — not a +/− count — is the baseline citation (`requests/00_global_paths.md` R33).

**Requests not yet applied elsewhere.** Where another contract file still carries text that a
request in `requests/00_global_paths.md` replaces (e.g. 04_hooks.md rule k's retired `operator_ack`,
R10), this file's text wins for every §0–§1 shape until the coordinator applies the request; the
coordinator runs the retired-spelling test (R11) and confirms each open request applied before the
WP that depends on it starts.

---

## 0. Global rules (every WP)

### 0.1 The Agency boundary (binding; plan §20.9, §20.9a and §20.9c, all operator rulings of 2026-09-27)

The OtherApp repo (`~/Desktop/OtherApp`) and the OtherApp SaaS runtime are a **separate application**.
The only thing it shares with this work is the Claude Code runtime itself. Therefore **no WP**:

- reads, lists, greps, globs, imports, executes, or links to any path inside the OtherApp repo;
- reuses any Agency agent, skill, script, API, MCP shim, browser state, or `oauth-google-<slug>` secret;
- writes anything into the OtherApp repo (the old §20.11 "OtherApp repo" edits are **struck**);
- reads, files, comments on, labels, closes or edits any issue, PR, release, file or other object in
  the **Agency GitHub repo** (`<org>/Agency`, any org; plan §20.9a "never … files against
  `~/Desktop/OtherApp` or its GitHub repo") — by browser, `gh` (`-R`/`--repo <org>/Agency`, `gh api
  repos/<org>/Agency/…`, `gh issue|pr … <url>`), `curl`/`git` against `github.com/<org>/Agency…`, or
  any other means. G-B rule i must deny every one of those spellings (requested of 04_hooks.md §4.2,
  `requests/00_global_paths.md` R14, with B1 tests); no GTM or department seat, WP, research agent or finding
  filer ever targets that repo — a finding about OtherApp's product goes to the operator, never to
  that tracker;
- follows the old §20.2 instruction to list `companies/othercompany/` inside Agency (**struck** by
  §20.9 v15; OtherCompany facts come only from the operator, public sources, and
  `~/Desktop/OtherCompany Files/` under the §20.2 list-first procedure — see WP-M). Plan §20.3's
  PHI ban is wider than that one folder ("any export, report or file derived from [Open Dental],
  and any folder holding such files"), so Open Dental-derived files **anywhere else** (e.g. at the
  top level of `~/Desktop`) are enumerated by name only, classified by trust-architect and
  denylisted before the **first GTM session of any company** starts (§1.2 `phi1-listing
  --top-level` and "Top-level PHI classification is a precondition": the launchers refuse, and the
  hooks default-deny every GTM scope and GTM seat, until it has run); a GTM scope with
  `regulated` ∋ `hipaa` is additionally default-deny outside its allowed roots (§1.2 "OtherCompany
  read scope").

OtherApp's GTM home is `~/Desktop/OtherApp_GTM/` (a new local repo), never the OtherApp repo. Agency
appears in Wave-2 code only as **deny patterns and exclusions**, including (the list is
illustrative, not exhaustive — any new Agency reference must be one of these two kinds): G-B rule (i)
(Bash, 04_hooks.md §4.2, incl. its `oauth-google-` token and the `<org>/Agency` `gh`/URL forms), G-B
rule (d2) (`gcloud secrets versions access` of `oauth-google-*` in GTM scope, plan §20.9), the
`agency-boundary` rule of the path gate (Read/Grep/Glob/Edit/Write/WebFetch, 04_hooks.md §4.4), G-A
rule 3b (browser navigation to the Agency GitHub repo, 04_hooks.md §4.1), the Agency/OtherApp app
hosts entered in `phi_denylist.json` with `applies_to: ["othercompany"]` (plan §20.3, 03_schemas.md
§3.20), the exclusion inside `company.gtm_slugs()` (below), the `register` refusals below, the
Agency project-dir skip (below), the "Agency session files" arm for agent reads of Agency
transcripts and scratchpads (§0.4), and the `co_managing_systems` outside-actor record in packs (§20.9,
03_schemas.md §3.23).
**Which sessions the mechanical denies reach** is stated in §0.4 ("The Agency boundary outside GTM
scope"): GTM scope, every `gtm_seat_types()` member (GTM **and** department seats — the Agency
arm is the one place "GTM seat" is widened, §0.4 "GTM seat"), and every sub-agent dispatched with a GTM dispatch tag, whose
cwd is outside Agency, are hook-enforced (the sub-agent arm depends on probe q); every other
session and sub-agent started outside Agency is bound by prose and code review only (accepted
residual, reason stated there — §20.9a binds GTM work, not the whole machine), with the oracle
below as the test-time backstop.

**The one path-compare implementation (DECIDED HERE; A1 `gtm_env`, imported by `company.py`,
`gtm_lists.py`, the oracle fixture, the path gate, G-B and `refuse_real_state`).** Every
Agency-root and root compare in this contract set calls these `gtm_env` functions, never a local
copy:
- `gtm_env.norm_text(s: str) -> str` = `canon_aliases(os.path.normpath(s).casefold())` — no
  `~` expansion, no stat. `strip_firmlink(t)`: when `t == "/system/volumes/data"` → `"/"`; when `t`
  starts with `"/system/volumes/data/"` → `t[len("/system/volumes/data"):]`; else `t`. Reason: on
  macOS `/Users` is a **firmlink** of `/System/Volumes/Data/Users` (`/usr/share/firmlinks`;
  `os.path.islink("/Users")` is False and `os.path.realpath("/System/Volumes/Data/Users")` returns
  that path unchanged), so `/System/Volumes/Data/Users/<u>/Desktop/OtherApp` names the Agency tree
  while passing every plain-text compare, every symlink walk and `realpath`.
  **`canon_aliases(t)` — the one kernel-alias canonicalizer (DECIDED (wave1c): one loop over every
  known alias class — the firmlink strip alone left three same-class aliases open; widened wave1d,
  finding 00-BLOCKER, to fail closed on the `/.vol` volfs alias, a fourth same-class alias the
  wave1c loop missed).** Checked on
  this machine: `os.path.normpath('//Users/x/Desktop/OtherApp')` keeps the double leading slash
  (POSIX) and `//Users/x/Desktop` is a directory; `/.nofollow/<path>` names `<path>`
  (`os.path.samefile('/.nofollow/Users/x/Desktop', '/Users/x/Desktop')` is
  True, `os.path.realpath` leaves the prefix unchanged, `os.path.islink('/.nofollow')` is False);
  `/.resolve/1/<path>` is a directory too; and `/.nofollow/System/Volumes/Data/Users` is a
  directory (prefixes stack). **`/.vol/<dev>/<ino>/…` is a fourth kernel alias root of the same
  class, checked on this machine: `os.path.isdir('/.vol/' + str(os.stat('/Users').st_dev) + '/' +
  str(os.stat('/Users').st_ino))` is True, `os.path.samefile(that, '/Users')` is True,
  `os.path.islink('/.vol')` is False, and `os.path.realpath` leaves the `/.vol/<dev>/<ino>` prefix
  unchanged** — so a home spelled `/.vol/<dev of /Users>/<ino of Desktop/OtherApp>` would pass every
  plain-text compare, the symlink walk (never a link) and `realpath`, identically to the
  `.nofollow`/`.resolve` cases above. Unlike those two, `/.vol/<dev>/<ino>` carries **no** textually
  recoverable path — the device/inode pair names an arbitrary filesystem object with no static
  string substitution back to `/Users/...`, so it cannot be stripped to its real path the way
  `.nofollow`/`.resolve`/the firmlink prefix are; the only fail-closed option is to refuse the
  whole alias class outright rather than attempt to resolve it. So, on the casefolded text, repeat
  until one pass changes nothing:
  (a) collapse any leading run of `/` to a single `/`; (b) strip a leading `/.nofollow` component
  (`t == "/.nofollow"` → `"/"`; `t.startswith("/.nofollow/")` → `t[len("/.nofollow"):]`); (c) strip
  a leading `/.resolve/<digits>` (regex `^/\.resolve/\d+(?=/|$)`, an empty remainder → `"/"`); (d)
  `strip_firmlink`; **(e) `/.vol` match (checked before the loop can make any further progress on
  this branch): if `t == "/.vol"` or `t.startswith("/.vol/")`, `canon_aliases` returns the sentinel
  text `gtm_env.VOLFS_SENTINEL` (a module constant, an unrepresentable string such as
  `"\x00agency-alias-vol\x00"` that can never occur in a real filesystem path — NUL is illegal in a
  POSIX path component — so it can never collide with, or be spoofed by, a legitimate home) instead
  of continuing the loop** — this is a terminal arm, not a strip-and-continue one, because there is
  no reduced text left to re-loop on. Because it runs on casefolded text, every casing of each prefix is covered.
  **Every consumer that compares `norm_text`/`norm` output against `norm(A)` (`is_under`,
  `is_ancestor`, or a direct equality) must therefore treat the sentinel as an unconditional Agency
  match** — `is_under`/`is_ancestor` never need their own `/.vol` awareness: a caller that receives
  `VOLFS_SENTINEL` from `norm`/`norm_text` and does not special-case it will simply find
  `is_under(VOLFS_SENTINEL, norm(A))` False (the sentinel does not start with `norm(A)` as text), so
  **every one of `gtm_slugs()`'s exclusion, `register`'s walk step "Before touching `C`" and checks
  (a)/(d), the oracle's recording compare, `test_mode`'s `HOME` pre-check, `refuse_real_state`, the
  §0.4 `agency-boundary` compares (04_hooks.md `canon` step (2b) and `path_is_or_under`, applied
  wave1e, `requests/00_global_paths.md` R44) and `claude_dir()`'s refusal (both branches, §1.1) adds one
  explicit line, before its `is_under`/`is_ancestor` calls: `if candidate == gtm_env.VOLFS_SENTINEL:
  refuse (that site's own Agency-match reason)`** — for `register`'s walk this is
  `kernel_path_alias` (the same reason the `.nofollow`/`.resolve` component check above already
  raises, since `/.vol` is unresolvable exactly the way those two are unclimbable), for
  `gtm_slugs()`/`resolve_home()`/`_entry_root_path()`/`test_mode`/`refuse_real_state`/the
  `agency-boundary` hook rule this is the same `agency_home`-class refusal each site already raises
  for an ordinary Agency match (never a silent pass-through). Every consumer of `norm_text`/`norm`
  gets the sentinel by construction (all listed above go through `norm_text`/`norm`); none keeps a
  local copy of the alias list. Unit tests (A1), each RED without its arm:
  `norm_text("//users/u/desktop/agency") == "/users/u/desktop/agency"` (arm a);
  `norm_text("/.nofollow/users/u/desktop/agency")` (arm b); `norm_text("/.resolve/1/users/u/desktop/agency")`
  (arm c); the stacked `norm_text("//.nofollow/.resolve/1/system/volumes/data/users/u/desktop/agency")`
  (RED when the loop runs one pass only); `norm_text("/.nofollowx/a")` is unchanged (component
  boundary); **and `norm_text("/.vol/1/2/anything") == gtm_env.VOLFS_SENTINEL` (arm e), plus
  `norm_text("/.volx/a")` is unchanged (component boundary, mirroring the `.nofollowx` case).**
  Oracle/register/`gtm_slugs()` tests (coordinator, Appendix C item 14, each RED when the `/.vol`
  arm or its consumer-side check is removed): with `dev`/`ino` taken from `os.stat()` of a tmp
  Agency-rooted directory, `register x --root /.vol/<dev>/<ino>` → stderr `error: agency_home:
  kernel_path_alias`, exit 1, empty oracle record; a GTM-registry entry `{"foo": {"root":
  "/.vol/<dev>/<ino>"}}` for the same tmp Agency directory → `gtm_slugs()` excludes it and
  `resolve_home("foo")`/`load_pack("foo")` raise `CompanyError` naming `agency_home:
  kernel_path_alias`; the oracle positive control `open("/.vol/<dev>/<ino>/x")` for a tmp Agency
  path records a touch (proving the sentinel is not silently treated as "no match" anywhere the
  no-Agency-touch oracle itself watches).
- `gtm_env.norm(s: str, *, test: bool) -> str` = `norm_text(expand(s))`, where `expand` =
  `real_expand` (below) when `test` is False and `os.path.expanduser` when True. Callers pass the
  `test` flag from `gtm_env.test_mode(environ)[0]` computed once per call; `test_mode` itself uses
  only `norm_text` (never `norm`), so the definitions do not loop.
- `gtm_env.is_under(a: str, b: str) -> bool` = `a == b or a.startswith(b.rstrip(os.sep) + os.sep)`
  on two already-`norm`ed strings ("equal to or under").
- `gtm_env.is_ancestor(a: str, b: str) -> bool` = `a != b and b.startswith(a.rstrip(os.sep) +
  os.sep)` on two already-`norm`ed strings ("`a` is a strict ancestor of `b`"). It is the **one**
  ancestor test: `gtm_slugs()`'s ancestor arm and `register`'s check (d) both call it, so a home of
  `/` (whose `rstrip` is empty) is an ancestor of every absolute path in both places. Unit tests:
  `is_ancestor("/", "/users/u/desktop/agency")` is True; `is_ancestor("/users/u/desktop",
  "/users/u/desktop/agencyx")` is True and `is_ancestor("/users/u/desktop/agency",
  "/users/u/desktop/agencyx")` is False (separator boundary).
- **The `~user` form is refused, never expanded (DECIDED HERE).** `os.path.expanduser` expands
  `~<user>/…` against that user's passwd home, while `real_expand` (§1.1) expands only `~` and
  `~/…`; a hand-edited registry root such as `~x/Desktop/OtherApp` would therefore pass the
  text compare as un-expanded relative text and then be resolved into the real Agency tree by
  `resolve_home()`. So every root or path string this contract set reads from a registry, a pack or
  a CLI argument that starts with `~` must be exactly `~` or start with `~/`; anything else (`~x`,
  `~x/…`, `~+`) is refused **before** any expansion or file-system call:
  `gtm_env.real_expand` raises `gtm_env.TildeUserForm(ValueError)`; `gtm_slugs()` input rule (5),
  `resolve_home()`/`_entry_root_path()`, `register`/`cmd_register` (stderr `error: agency_home:
  tilde_user_form`, exit 1) and R36's `validate_company` (`paths.*`, `marketing_paths`) raise or
  report `CompanyError("… 'root' uses the ~user form")`; `gtm_lists.py phi-denylist add --path`
  exits 3 `path_tilde_user`; `refuse_real_state` treats a real-registry root in that form as a
  match (refuse; fail closed). Coordinator test (08_seats_wps.md Appendix C item 14,
  `requests/00_global_paths.md` R41): outside test mode (`gtm_env.test_mode` monkeypatched to
  `(False, [])`, `real_home()` monkeypatched to a tmp dir holding `Desktop/OtherApp`), a registry root
  `~<the real user name>/Desktop/OtherApp` → `gtm_slugs()` raises `CompanyError` naming the slug and
  the no-Agency-touch oracle records nothing; RED when the refusal is removed (checked:
  `os.path.expanduser('~x/Desktop/OtherApp')` returns `/Users/x/Desktop/OtherApp`).
- `gtm_env.agency_root(environ: Mapping[str, str] = os.environ) -> Path` = `A` below;
  `real_agency_root()` as in §1.1. The exact signatures of every `gtm_env` export are the one table
  in §1.1 "`gtm_env` exports".
Below, `norm(s)` means `gtm_env.norm(s, test=<the caller's test flag>)`. Unit tests (A1): for each
of `gtm_slugs()` exclusion, `register` (`registry_path_in_agency`) and the oracle positive control
`open("/System/Volumes/Data" + A + "/x")`, the firmlink form is caught; each goes RED when
`strip_firmlink` is removed. The same three sites are tested with the `//`, `/.nofollow` and
`/.resolve/1` forms (RED when the matching `canon_aliases` arm is removed): registry roots
`"/" + A`, `"/.nofollow" + A` and `"/.resolve/1" + A` are each excluded by `gtm_slugs()`;
**`register x --root /.nofollow<tmp HOME>/Desktop/OtherApp` → `kernel_path_alias`, not
`registry_path_in_agency` (corrected wave1d, finding 00-MAJOR): the walk's component check "Before
touching `C`, if `norm(C)` is equal to or under `norm(A)` … else, if `P == "/"` and `c.casefold()`
is `.nofollow`/`.resolve`/`.vol` → refuse `kernel_path_alias`" runs component-by-component in
order, and `.nofollow` is the walk's very first component after the leading `/` — so the
`.nofollow`/`.resolve`/`.vol` arm fires immediately, before `C` has accumulated enough of the path
to ever equal-or-be-under `norm(A)`. The argument-text check (a) (`os.path.abspath(s)` compared
whole, unwalked) is a SEPARATE, later check on the raw argument, not the walk's own per-component
refusal that `register` actually raises first — since `register`'s refusals are checked in the
walk's own order and the walk's per-component refusal fires before check (a) is ever reached for
this input, the walk's `kernel_path_alias` is what `register` reports, under the oracle** with an
empty record; and the oracle positive controls `open("/" + A + "/x")`,
`open("/.nofollow" + A + "/x")` and `open("/.resolve/1" + A + "/x")` each record a touch.

**Registered GTM company (binding definition).** Every place this document says "registered pack",
"every pack", "siblings" or "all companies" means the slugs returned by
**`company.gtm_slugs() -> list[str]`** (sorted ascending, no duplicates; `company.py list` prints
them one per line in that order) — never `company.registered_slugs()`, which unions **every**
`knowledge/repo_registry.json` slug except a by-name denylist (corrected (wave1c): on the baseline
working tree `registered_slugs()` returns `['exampleapp']`, because it reads the repo
registry through `_gtm_eligible_repo_registry_repos()`, which drops
`_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS = frozenset({"agency"})`; only the unfiltered
`_repo_registry_repos()` returns `['agency', 'exampleapp']`). **Fate of the by-name
denylist (DECIDED (wave1c): kept as a second layer — it costs nothing and still holds if the text
compare is ever wrong):** `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS` and
`_gtm_eligible_repo_registry_repos()` stay; `gtm_slugs()` reads allowlisted repo slugs through
`_gtm_eligible_repo_registry_repos()` (so `agency` is dropped by name even if someone allowlists
it) **and** applies the text exclusion below; `resolve_home()` keeps reading through it too and
adds the same text exclusion (below, "`resolve_home()` is bound to the exclusion").
`_register_gtm_company_locked`'s collision check and the duplicate checks of (4), `validate --all`
and `cmd_index` keep the **unfiltered** `_repo_registry_repos()` (a collision or duplicate must see
every slug, `agency` included; they read keys and root **text** only, never resolving a root under
`A`, "Existing registry roots" below). **Callers that switch from `registered_slugs()` to
`gtm_slugs()`** (Appendix C item 14): `_all_packs`, `build_identity_index`,
`build_account_id_index`, `cmd_validate`'s `--all` slug list and
`harvest_tool_trail._registered_homes`. `registered_slugs()` itself stays, unchanged, with no
Wave-2 caller. `gtm_slugs()` = the companies in `knowledge/gtm_company_registry.json` ∪ the
repo-registry slugs named in that file's explicit allowlist key `"repo_registry_slugs":
["exampleapp"]`, minus any slug whose **registry-string** home path is equal to or under
the Agency root **or is an ancestor of it**. **The comparison is text-only and exact (I14):**
`norm` is `gtm_env.norm` above — `expand` = `gtm_env.real_expand` (`~` against the passwd home,
§1.1) **outside test mode** and `os.path.expanduser` in test mode, the same split as `A` below, so
a `HOME` that is a symlink of the passwd home (not test mode, §1.1) still expands
`~/Desktop/OtherApp` to `A`'s text, and the firmlink prefix is stripped; `gtm_slugs()`, `register`'s
checks and `validate --all` all use this `norm`. A slug is excluded iff `is_under(norm(home),
norm(A))` **or** `is_ancestor(norm(home), norm(A))` (an ancestor of `A`, e.g.
a hand-edited root `~/Desktop` or `~`: `company.backup_set()` archives `home/<paths.data_dir>`, so
with home `~/Desktop` and `data_dir: "Agency"` a backup would tar the Agency tree), each compared
against `norm(A)` **and** `norm(str(real_agency_root()))` (the registry stores `~/Desktop/OtherApp`
with a tilde; APFS is case-insensitive, hence `casefold`). No stat. An ancestor is reported by
`validate --all` as `INVALID <slug>: agency_home: ancestor_of_agency` (below). Unit cases
(coordinator, Appendix C item 14): `real_home()` monkeypatched to a tmp dir, `HOME` a symlink to
it, a registry entry `~/Desktop/OtherApp` → excluded (RED when `expand` is `os.path.expanduser`
outside test mode); a registry root `~/Desktop` → excluded and reported `ancestor_of_agency` (RED
when the ancestor arm is removed); a root `/System/Volumes/Data<tmp HOME>/Desktop/OtherApp/x` →
excluded (RED without the firmlink strip). CROSS (`requests/00_global_paths.md` R36):
`company.validate_company` refuses any `paths.*` value that is absolute, starts with `~`, contains
a `..` segment, or whose `norm(os.path.join(H, value))` is equal to or under `A` or
`real_agency_root()`.
**The Agency root `A` (defined once here; DECIDED HERE).** Outside test mode (§1.1) `A =
str(Path(gtm_env.real_home()) / "Desktop" / "Agency")` — from the passwd home, never from `HOME`,
matching §1.1's rule that production roots never come from `HOME` or `CLAUDE_DIR`. In test mode
`A = str(Path(environ.get("HOME") or real_home()) / "Desktop" / "Agency")` — `HOME` read from the
**given** mapping (never `os.environ` or `Path.home()` when a mapping is passed), with the same
empty-counts-as-unset rule `test_mode` uses — so the tests' tmp-`HOME` construction keeps working
and an in-process caller is judged on the mapping it passes (the `refuse_real_state` rule, §1.1).
Test mode itself is `gtm_env.test_mode(environ)[0]` on that same mapping.
`gtm_env.real_agency_root() -> Path` = `Path(real_home()) / "Desktop" / "Agency"` always (§1.1).
`agency_root()` (04_hooks.md §4) is `gtm_env.agency_root(os.environ)` and returns `Path(A)`; every
Agency-root comparison in this document uses the same `gtm_env.norm`/`is_under`. Where a check must hold in test mode **and** keep
the real Agency tree unstat'd (§1.1 consequence 3, the oracle below), it compares against **both**
`A` and `real_agency_root()`.
It never stats, opens or lists a path before that exclusion. Tests include `~/Desktop/OtherApp`,
`~/Desktop/OtherApp/`, `~/desktop/agency`, `str(Path.home()/"Desktop"/"Agency"/"sub")` computed **at
test time** under the tmp `HOME` (a literal `/Users/<u>/…` would not be under the test's `A`) — all
excluded — and `~/Desktop/OtherAppX` (not excluded: separator boundary).

**Registry inputs of `gtm_slugs()` (exact; DECIDED HERE).** (1) `knowledge/gtm_company_registry.json`
missing → no GTM-registry slugs **for lookups only** (`gtm_slugs()`, `resolve_home()`; committed
`_gtm_registry_companies` behaviour); present but unreadable → `CompanyError`. (2) Key
`repo_registry_slugs` absent (or not a list of strings) → no repo-registry slug is admitted, so
`gtm_slugs()` returns only GTM-registry slugs (the file does not exist on disk today, so
08_seats_wps.md Appendix C item 14 creates it with the key). **That state is never silent, and a
missing file is the same state for every writer and for `validate --all` (DECIDED HERE):** when
`gtm_company_registry.json` is **missing**, or exists with the key absent or not a list of strings,
`validate --all` prints `INVALID <registry path>: repo_registry_slugs_missing` on stdout and exits
1 (whatever else it reports). `<registry path>` = exactly `str(company.gtm_registry_path())`, the
absolute path resolved from `claude_dir()`, never a `~` form or a bare file name. **This line is a
stated grammar exception:** every other `validate --all` line is `INVALID <slug>: <reason>`; this
one alone carries an absolute path (it starts with `/`, which no slug can), so a consumer that
parses the output tests for a leading `/` first. **The one precheck (the API gtm_lists and the
index writer share):** `company.require_repo_registry_slugs() -> None` (new, public; Appendix C
item 14) raises `CompanyError("repo_registry_slugs_missing")` when the file is missing, or its
key is absent or not a list of strings (a present-but-unreadable file raises `CompanyError` as in
(1)), and returns `None` otherwise; it reads only `gtm_company_registry.json` and writes nothing. **The index refusal lives inside the one writer,
not in a CLI:** `company.write_identity_index()` (which writes both `identity_index.json` and
`account_id_index.json`) calls `require_repo_registry_slugs()` first, **before writing
anything**, so `company.py index` refuses **without rewriting**
`identity_index.json`/`account_id_index.json`; `company.py index` maps it to stderr `error:
repo_registry_slugs_missing`, exit 1. `gtm_lists.py` (§1.2 "Every add") calls
`require_repo_registry_slugs()` itself **before** its atomic replace of the list file (exit 3
`repo_registry_slugs_missing`, nothing written), then replaces the list file, then calls
`write_identity_index()`, which reads the **new** list from disk through `_other_businesses()` —
so neither ordering constraint needs a second index builder. Rewriting the indexes without CSA would silently drop
CSA's identifiers and `credential_refs` from every sibling isolation check (validate's
shared-credential and shared-identifier refusals, the identity/account indexes G-A reads, harvest
attribution; plan §3.3/§20.2), which would fail open because of a config edit — or because the
file was deleted or not restored, which is why a **missing** file refuses too. Coordinator tests
(Appendix C item 14): key removed → `validate --all` exits 1 with that line, `company.py index`
exits 1, and both index files are byte-identical before and after (RED when the refusal is
removed); **file deleted** → the same three results (RED when a missing file is treated as "no
slugs" by `write_identity_index()`); file deleted → `gtm_slugs()` and `resolve_home()` still
treat it as no GTM-registry slugs (no raise). **Test retrofit, stated in full (DECIDED (wave1c);
Appendix C item 14 scope, `requests/00_global_paths.md` R43).** Once the allowlist exists and
`write_identity_index()` refuses on a missing file, a committed fixture that registers its test
company **only** through `repo_registry.json` loses that company from `gtm_slugs()` (so from
`_all_packs` sibling checks, both indexes, `validate --all` and `_registered_homes`), and every
direct `company.write_identity_index()` call raises. The same coordinator change therefore gives
each such file a `gtm_company_registry.json` carrying `"repo_registry_slugs": [<its test slugs>]`
(or moves the slug into the GTM registry), through one helper,
`gtm_fixtures.write_gtm_registry(claude_dir: Path, *, repo_registry_slugs: list[str], companies:
dict | None = None) -> Path` (Appendix C item 28). Known sites (grep of the baseline, re-derive
before editing): direct `write_identity_index()` callers `test_host_systems.py`,
`test_host_systems_validation.py`, `test_company_pack.py`, `test_flush_many_scalability.py`,
`test_harvest_tool_trail.py` (two sites), `test_lock_scope_not_blocking.py`,
`test_harvest_multiprocess.py`, `test_nap_never_triggers_capture.py`; `validate --all`
subprocess tests in `test_company_pack.py` and `test_gtm_company_registry.py`; and
`test_corrupt_registry_error_handling.py`. The coordinator runs the whole `tools/gtm/tests/` suite
before and after; any further test that goes red **only** because a repo-registry-only company
left `gtm_slugs()` is fixed the same way — never by weakening a refusal. **Why the opt-in design
is now acceptable, reversing company.py's own comment above `_GTM_NEVER_PROBED_REPO_REGISTRY_SLUGS`**
(which rejected opt-in because "14+ files register a test-local company purely via a
repo_registry.json entry"): that comment weighed a retrofit against a one-entry Agency problem, and
Agency is now held by the text exclusion plus the by-name layer. The allowlist exists for a
different reason — fail-closed membership: without it, any repo later added to
`repo_registry.json` for other runtime tooling becomes a GTM company automatically (its pack
probed, its transcripts globbed, its identifiers entered into every sibling index). The retrofit
is one bounded, mechanical fixture change in the same commit, and a missing allowlist is refused
loudly (`repo_registry_slugs_missing`), never silently. The coordinator updates that company.py
comment in the same change so the code no longer argues against itself. WP-M test: key removed →
`gtm_lists.py other-business add --label L --value V` exits 3 `repo_registry_slugs_missing`, and
`other_businesses.json`, `identity_index.json` and `account_id_index.json` are byte-identical
before and after (RED when the precheck is moved after the list replace). (3) `knowledge/repo_registry.json` missing → the allowlisted repo slugs
are dropped (no raise from `gtm_slugs()` itself); present but unreadable → `CompanyError`. This
matches the baseline: `resolve_home()`, `registered_slugs()` and `backup_set()` read the repo
registry through `_repo_registry_repos()`, which treats a **missing** `repo_registry.json` as empty
and raises `CompanyError` only for a present-but-unreadable one (`load_registry()` itself still
raises on a missing file, but no baseline caller reaches it without that existence check). Test
trees still always create the file (§1.5 item 1) — a determinism rule, not a workaround. (4) A slug in **both** registries is
excluded from `gtm_slugs()` (the committed `registered_slugs()`/`resolve_home()` treat it as a
configuration error; `validate --all` reports it). (5) A `companies` entry in the GTM registry, or a
`repos` entry for an allowlisted slug in the repo registry, that is not a JSON object, or whose
`root` is absent, not a string, or empty, **or starts with `~` without being exactly `~` or
starting with `~/`** (the `~user` form, refused before any expansion, §0.1 "The one path-compare
implementation"), **or not absolute after `os.path.expanduser`** (a
hand-edited relative root such as `Desktop/OtherApp` would pass the text compare and then resolve
against the cwd, possibly into Agency) → `CompanyError` naming the slug (never skipped, because
skipping would silently drop a company from every sibling check). The committed `resolve_home()`
and `_entry_root_path()` accept a relative root today (`Path(root).expanduser().resolve()` resolves
it against the cwd), so the Appendix C item 14 coordinator change makes **both** raise
`CompanyError(f"… entry for {slug!r} has a non-absolute 'root'")` for a root that is not absolute
after `os.path.expanduser`, before any `resolve()` — so every `--company` consumer that calls
`resolve_home(slug)` directly gets the same refusal (`requests/00_global_paths.md` R36).
**`resolve_home()` is bound to the exclusion (DECIDED (wave1c); widened wave1d, finding 00-MAJOR;
`requests/00_global_paths.md` R43).** Only enumeration used to exclude an Agency-rooted entry, while every `--company <slug>`
consumer (act.py, `gtm_lists`, `activity_log`, `backup_state --company`, `load_pack`, `pack_path`)
calls `resolve_home(slug)` directly, which runs `Path(root).expanduser().resolve()` and then reads
`<root>/.claude/gtm/company.json`; a GTM-registry entry `{"foo": {"root": "~/Desktop/OtherApp"}}`
(which §1.2 admits no gate yet stops a GTM session writing) resolved straight into Agency.
**A bare `norm(root)`-vs-`norm(A)` text compare is not enough here (DECIDED (wave1d), because
unlike `register`'s argument this `root` string is never independently walked): `canon_aliases`
only canonicalizes the fixed, enumerable kernel-alias classes (`.nofollow`, `.resolve/<n>`, the
firmlink prefix, `.vol` per the fix above) — it has no way to catch a *symlink* spelling of a real
path, because a symlink's target is arbitrary and only discoverable by actually walking the
filesystem. A macOS example: `/Volumes/Macintosh HD` is a real symlink to `/` on a machine where
the boot volume is named "Macintosh HD" (`os.path.islink('/Volumes/Macintosh HD')` is True,
`os.path.realpath('/Volumes/Macintosh HD')` is `/`), so a registry root
`/Volumes/Macintosh HD/Users/<u>/Desktop/OtherApp` is textually nothing like `norm(A)` and would pass
a bare `norm(root)` compare while being the identical filesystem object. So the Appendix C item 14 change makes `resolve_home()` **and** `_entry_root_path()`, after the (5) checks
and **before** any `expanduser().resolve()`, run `register`'s own component walk (§0.1 "The walk",
above — the same `s`-splitting, symlink-following, `.nofollow`/`.resolve`/`.vol`-refusing,
40-symlink-capped procedure `register` runs on its `--root` argument, called here on `root` after
its `~`/`~user` handling per the (5) checks) to obtain the walked text `F`, and apply the same
`checks (a)–(d)` (§0.1 "The checks") to **both** `F` and the argument text — raising
`CompanyError(f"… entry for {slug!r} agency_home: <reason>")` for whichever `<reason>` the walk or
the checks produce (`registry_path_in_agency`, `symlink_into_agency`, `symlink_limit`,
`agency_project_dir`, `ancestor_of_agency`, `kernel_path_alias` — the full `register` reason set,
never only the two `is_under`/`is_ancestor` reasons a bare text compare could produce), `test` from
`gtm_env.test_mode(os.environ)[0]`. This is strictly stronger than, and replaces, the plain
`is_under(norm(root), n)`/`is_ancestor(norm(root), n)` text compare this paragraph specified before
wave1d (that compare still runs too, as the walk's own step (a)/(d) checks apply it to `F`; nothing
that passed before now fails, because every textual match `norm` caught is also a walk match — the
walk is a superset). Only `resolve_home()`/`_entry_root_path()` pay the walk's cost (one `register`
call per `--company` resolution); `gtm_slugs()`'s own enumeration exclusion (used far more often,
once per registered slug on every listing) keeps the cheaper text-only `norm` compare, accepting
the "Accepted residual" already stated below (a home later replaced by an unwalked symlink is
caught by `resolve_home()`/`register`/the path gate, not by `gtm_slugs()`'s listing).
`resolve_home()` is **not** narrowed to `gtm_slugs()` membership (DECIDED (wave1c): the Agency risk
is closed by this compare plus the by-name layer, while a membership check would additionally turn
every committed test fixture that registers a company only through `repo_registry.json` — most of
the 18 `tools/gtm/tests/` files that write one, e.g. `test_activity_log.py`, `test_backup_state.py`
— red for no Agency gain). Coordinator test (wave1d addition): a registry root
`/Volumes/Macintosh HD` + a tmp-Agency-relative suffix, built by creating a tmp symlink named
`Macintosh HD` under a tmp `Volumes`-alike directory pointing at the tmp Agency parent (the real
`/Volumes/Macintosh HD` cannot be created by a test; the walk logic is exercised through a
monkeypatched `real_agency_root()`/tmp-home symlink of the same shape) → `resolve_home("foo")` and
`load_pack("foo")` each raise `CompanyError` naming `agency_home: symlink_into_agency`, empty
oracle record; RED when the walk call is replaced back by the bare `norm(root)` compare. Coordinator test,
under the no-Agency-touch oracle with an empty record asserted: GTM registry `foo` →
`~/Desktop/OtherApp` (tmp `HOME`) → `resolve_home("foo")` and `load_pack("foo")` each raise
`CompanyError` naming `agency_home: registry_path_in_agency`; `foo` → `~/Desktop` →
`ancestor_of_agency`; `foo` → `/.nofollow<tmp HOME>/Desktop/OtherApp` → `kernel_path_alias`
(corrected (wave1e): `resolve_home()` now runs `register`'s walk, whose per-component
`.nofollow`/`.resolve`/`.vol` refusal fires on the first component, before `C` can equal or be under
`norm(A)` — the same ordering §0.1 states for `register --root`); `foo` → `/.vol/<dev>/<ino of tmp
A>` → `kernel_path_alias`; each RED when the check is removed or moved after the `resolve()`.
**`validate --all` for case (5):** it does not stop; it prints `INVALID <slug>: bad_registry_entry:
<CompanyError text>` for that slug, continues with the others, and exits 1. Coordinator tests: a
relative root `Desktop/OtherApp` → `resolve_home` raises before any stat (under the oracle) and
`validate --all` prints that line and exits 1; each RED when the absolute check is removed. **Accepted residual (stated):** `gtm_slugs()` compares registry text only and
does not re-run `register`'s symlink walk, so a registered home directory that is later **replaced
by a symlink into Agency** is not caught by `gtm_slugs()`; the path gate's `agency-boundary` rule
(04_hooks.md §4.4, which `canon`s the target side) and the no-Agency-touch oracle are the backstops,
and `validate --all` re-runs `register`'s (a)–(d) text/symlink walk of below on every registered home
and reports `agency_home` (never stat'ing under `A`). **`validate --all` output for excluded
entries (exact):** because `gtm_slugs()` drops them, `validate --all` reads both raw registries
(`_gtm_registry_companies()` and `_repo_registry_repos()`) and considers every GTM-registry
`companies` slug plus every repo-registry slug named in `repo_registry_slugs` (a repo-registry entry
**not** allowlisted, such as today's `agency`, is not a GTM company and is never reported); for each
one excluded by the Agency-root rule above or by (7) it prints on stdout, in the committed `INVALID <slug>:
<reason>` form, exactly `INVALID <slug>: agency_home: <reason>` (`<reason>` from the `register` set
below) or `INVALID <slug>: bad_slug`, and exits 1. Coordinator tests: one per line, plus a
non-allowlisted repo-registry `agency` entry → no line, exit unaffected. (6) Whenever `gtm_slugs()` reads `repo_registry.json` at all — to admit an
allowlisted slug **or** to run the duplicate check of (4), which it does whether or not
`repo_registry_slugs` is present — an unreadable file raises `CompanyError`; only a **missing** file
counts as "no repo-registry slugs". (7) A slug that fails the §0.3 slug grammar is excluded from
`gtm_slugs()` and reported by `validate --all` (`bad_slug`); `register` refuses it (below).
Coordinator tests (Appendix C item 14): one per case (5)–(7) (case (5) includes a relative root
`Desktop/OtherApp`), plus an unreadable `repo_registry.json` with `repo_registry_slugs` absent →
`CompanyError`.

**`register` refuses a home that leads into Agency (DECIDED HERE; coordinator, 08_seats_wps.md
Appendix C item 14).** `company.py register` refuses exit 1 `agency_home` when any of (a)–(d)
holds. **Order (binding):** (1) the two slug refusals (end of this paragraph); (2)
`tilde_user_form` on the **raw** argument (a leading `~` that is neither `~` nor `~/…`, §0.1 "The
one path-compare implementation"); (3) expansion, `s = gtm_env.real_expand_raw(arg)` outside test
mode and `os.path.expanduser(arg)` in test mode — **tilde expansion only, no `normpath`** in either
mode (DECIDED (wave1c): `real_expand` also `normpath`s, which would collapse `..` as text before the
walk and make production differ from test mode; `real_expand_raw` is the same `~`/`~/…` expansion
against `real_home()` with the same `TildeUserForm` refusal and no `normpath`, §1.1), so `register`
and `gtm_slugs()` still expand `~` the same way while only the walk interprets `..`; (4) the
character set on `s`; (5) the walk on `s`;
(6) the checks (a)–(d). Every check below runs **before** any `resolve()`, `exists()`,
`open()` or other file-system call the committed `register_gtm_company`/`cmd_register` make (today
they `Path(root).expanduser().resolve()` and `.exists()` first, which stats every component of an
Agency-bound path; the coordinator change moves the refusals ahead of both), and **the committed
code is then given the walk's final text path `F`, never the original argument** (its `resolve()`
of `F` is a no-op, because `F` holds no symlink, `.` or `..`), and `cmd_register`'s success line
prints `F` (`registered <slug> -> <F> (in <registry path>)`) — never a second `resolve()` of the
original argument, which the committed `cmd_register` does today for its message.
- **Character set.** The expanded `s` must contain only characters in
  `[A-Za-z0-9/_. -]`; any other character → stderr `error: bad_home_chars: <arg>`, exit 1. Reason:
  `project_dir_name_text`'s `[/_. ]` mapping is backed by four verified characters only (UNVERIFIED
  for the rest), so a home such as `~/Desktop/OtherApp(old)` could map to a project dir that check
  (c) misjudges; refusing the unverified characters makes (c) exact.
- **The walk (never `abspath`/`normpath` first).** `abspath` collapses `..` as text, while the
  kernel applies `..` after symlinks (`/tmp/link/../Agency` with `link → ~/Desktop/sub` is really
  `~/Desktop/OtherApp`). So, with `s` from step (3): if `s` is not absolute, prefix
  `os.getcwd()` (text). Split `s` on `/` into components (empty ones dropped); keep a real prefix
  `P = "/"` and a link count `n = 0`. Take components in order: `.` → skip; `..` → `P =
  os.path.dirname(P)` (text: `P` is already symlink-free, so its text parent is its real parent);
  otherwise `C = os.path.join(P, c)`. **Before touching `C`**, if `norm(C)` is equal to or under
  `norm(A)` or `norm(str(gtm_env.real_agency_root()))` → refuse (`symlink_into_agency` when `n > 0`,
  else `registry_path_in_agency`) with no call on `C`. Else, if `P == "/"` and `c.casefold()` is
  `.nofollow`, `.resolve` **or `.vol`** → refuse `kernel_path_alias` with no call on `C` (DECIDED
  (wave1c; widened wave1d, finding 00-BLOCKER, to add `.vol`):
  these kernel alias roots are not symlinks — `islink('/.nofollow')` and `islink('/.vol')` are both
  False — so the walk would
  otherwise pass straight through them; the `norm` compare above already catches an alias of `A`
  for `.nofollow`/`.resolve` (both textually strip to the real path via `canon_aliases`), **but not
  for `.vol`: a `/.vol/<dev>/<ino>` component is opaque device/inode addressing with no static text
  reduction to compare against `norm(A)` at all, so this component-level refusal is the only place
  in the walk that ever sees it — the `norm(C)`-equal-to-`norm(A)` check just above can never fire
  for a `/.vol` path, because `norm(C)` for such a `C` is `canon_aliases`'s `VOLFS_SENTINEL`, not a
  text form comparable to `norm(A)` by prefix** — and
  no legitimate home is spelled through any of the three). Else, if `os.path.islink(C)`: `n += 1` (`n >
  40` → refuse `symlink_limit`; never "accept after the limit"), `t = os.readlink(C)`, and the
  remaining components become `t`'s components followed by the rest — with `P` reset to `/` when
  `t` is absolute, `P` unchanged (the link's parent) when relative. Else `P = C`. A missing
  component is not a link and is kept as text (the committed code's `exists()` then refuses it).
  When the components run out, `F = P`.
- **The checks, each on `F` and on the argument text** (`os.path.abspath(s)`, `s` from step (3)):
  (a) `norm(·)` equal to or under `norm(A)` (`registry_path_in_agency`, or `symlink_into_agency`
  when only `F` matches); (b) is the walk's own refusal above; (c)
  `project_dirs.is_agency_project_dir(project_dirs.project_dir_name_text(·))` is true
  (`agency_project_dir`: a home such as `~/Desktop/OtherApp_GTM`, `~/Desktop/OtherApp Marketing` or
  `~/Desktop/OtherApp.old` maps to a project dir that the Agency project-dir skip below would
  silently drop, so all its transcripts would be ignored); (d) `norm(A).startswith(norm(·) +
  os.sep)` (`ancestor_of_agency`: a home such as `~/Desktop`, or a symlink `~/x → ~/Desktop`, would
  put `H/Agency` inside every walk of `H`, and its project-dir prefix `-Users-…-Desktop` would
  prefix-match Agency's project dirs). (d) is `gtm_env.is_ancestor(norm(·), norm(A))` (and the
  same against `norm(str(real_agency_root()))`) — the one helper `gtm_slugs()` also uses, so
  `register x --root /` (walk result `F = "/"`) is refused `ancestor_of_agency` (a hand-written
  `norm(·) + os.sep` prefix would test for `//` and miss it). (`tilde_user_form` is step (2)
  above, on the raw argument, before any expansion.)
- **Existing registry roots are never resolved when under Agency.** Before any `_entry_root_path`
  call (the committed `_register_gtm_company_locked` resolves existing entries only for its two
  slug-collision checks, e.g. `register agency --root <ok path>`; it has no duplicate-home scan,
  and none is added here), every existing root string of either
  registry is compared text-only with `norm` against `A`: one equal to or under `A` is never passed
  to `_entry_root_path`/`resolve()` (it is treated as a distinct, non-colliding home), and when it
  belongs to the slug being registered, `register` refuses `agency_home: registry_path_in_agency`.
Output: stderr exactly `error: agency_home: <reason>` with `<reason>` ∈ {`registry_path_in_agency`,
`symlink_into_agency`, `symlink_limit`, `agency_project_dir`, `ancestor_of_agency`,
`tilde_user_form`, `kernel_path_alias`}, exit 1 (the
CLI's generic `error: <exc>` form is not used for this refusal). **Slug refusals, also before any
file-system call:** the reserved slug `runtime` → stderr `error: reserved_slug: runtime`, exit 1; a
slug failing the §0.3 grammar (`system_names.SLUG_RE`, the one constant `company.py` imports, §0.3)
→ stderr `error: bad_slug: <slug>`, exit 1 (the coordinator change maps the committed
`register_gtm_company` SLUG_RE refusal to this exact line instead of its generic `error: refusing
to register … slug must match …` text). Tests, each run under the
no-Agency-touch oracle below with an **empty record** asserted: a tmp home that is a symlink to
`<tmp HOME>/Desktop/OtherApp/x` → `symlink_into_agency`; a chain of two symlinks whose second target
is under Agency → `symlink_into_agency`; 41 chained symlinks → `symlink_limit`; `<tmp>/link/../Agency`
with `link → <tmp HOME>/Desktop/sub` → `symlink_into_agency` (RED when the walk `abspath`s first);
a home that is a symlink to `<tmp HOME>/Desktop` → `ancestor_of_agency` (RED when (d) is checked on
the argument text only); `<tmp HOME>/Desktop/OtherApp_GTM` → `agency_project_dir`; `<tmp
HOME>/Desktop` → `ancestor_of_agency`; `register agency --root <tmp ok path>` with a repo-registry
`agency` entry under `A` → `registry_path_in_agency` (RED when the existing root is resolved);
`<tmp HOME>/Desktop/OtherApp(old)` → `bad_home_chars`; `<tmp HOME>/Desktop/OtherAppX` (project dir
`…-Desktop-OtherAppX`, no `-` boundary) is accepted and the committed code receives the walked `F`;
`runtime`, `a_b` and `1abc` are refused with the exact stderr lines above; `register x --root /`
→ `ancestor_of_agency` (RED when (d) is written as `norm(·) + os.sep` instead of `is_ancestor`);
`register x --root ~<user>/Desktop/sub` → `tilde_user_form`;
**`register x --root /.nofollow<tmp HOME>/Desktop/OtherApp` → `kernel_path_alias`, not
`registry_path_in_agency` (corrected wave1d, finding 00-MAJOR — see §0.1 "Unit tests (A1)" above for
the reason: the walk's per-component alias check fires on `.nofollow` as the first component,
before `C` ever accumulates enough path to match Agency by the `norm(C)`-under-`norm(A)` check) and**
`register x --root /.nofollow<tmp HOME>/Desktop/sub` → `kernel_path_alias` (RED when the
component refusal is removed); **`register x --root /.vol/<dev of a tmp Agency-rooted dir>/<its
ino>` → `kernel_path_alias` (RED when the `.vol` arm of the component check is removed);** **outside test mode** (`gtm_env.test_mode` monkeypatched to
`(False, [])`, `real_home()` monkeypatched to the tmp home) `<tmp>/link/../Agency` with `link →
<tmp HOME>/Desktop/sub` → `symlink_into_agency` (RED when step (3) uses `real_expand`, whose
`normpath` collapses `..` before the walk); each goes RED when its check is removed or moved after
the committed `resolve()`.

**`runtime` is a reserved slug** (the
runtime-wide notice directory, 07_notices_schedules.md §7.1): `gtm_slugs()` never returns it and `company.py register`
refuses it (08_seats_wps.md Appendix C item 14). Adding `gtm_slugs()`, **adding** the new
`company.py list` subcommand (it does not exist in the baseline) on top of it, and switching
`_all_packs()`, `validate --all`, the identity/account indexes and
`harvest_tool_trail._registered_homes()` to it is a coordinator
follow-up that lands **before B1/A1** (08_seats_wps.md Appendix C item 14); every Wave-2 consumer calls
`gtm_slugs()` only.

**No-Agency-touch test oracle (exact; coordinator + every WP that enumerates packs or scans
`R/projects/`).** A shared fixture (in `tools/gtm/tests/gtm_fixtures.py`, 08_seats_wps.md Appendix C
item 28) defines `class AgencyTouched(BaseException)` — **not** an `OSError`/`Exception` subclass, so
neither `Path.exists`/`is_dir` (which swallow `OSError`) nor a fail-open hook's `except Exception`
can absorb it — and patches **all** of the following (patching `builtins.open` alone does not reach
`Path.read_text`/`Path.open`, which call `io.open` — verified on Python 3.13; and patching only the
read/metadata calls lets `os.mkdir`, `os.utime` and `os.system` run uncaught — verified on the
machine's Python 3.13.14):
- **reads and metadata:** `builtins.open`, `io.open`, `os.open`, `os.stat`, `os.lstat`, `os.access`,
  `os.readlink`, `os.chdir`, `os.scandir`, `os.listdir`, `os.statvfs`, `os.pathconf`,
  `os.getxattr`, `os.listxattr`, `os.path.realpath`, `pathlib.Path.stat`, `pathlib.Path.lstat`,
  `pathlib.Path.resolve`, `pathlib.Path.iterdir`;
- **mutations:** `os.mkdir`, `os.makedirs`, `os.rmdir`, `os.remove`, `os.unlink`, `os.rename`,
  `os.replace`, `os.symlink`, `os.link`, `os.chmod`, `os.chown`, `os.lchown`, `os.utime`,
  `os.truncate`, `os.setxattr`, `os.removexattr` (a two-path call such as `rename`/`link`/`symlink`
  tests **both** paths);
- **process spawning:** `subprocess.Popen.__init__` (which `subprocess.run`, `check_output` and
  `call` go through), `os.system`, `os.posix_spawn`, `os.posix_spawnp`, every `os.exec*` variant
  (`execv`, `execve`, `execvp`, `execvpe`, `execl`, `execle`, `execlp`, `execlpe`), every
  `os.spawn*` variant (`spawnv`, `spawnve`, `spawnvp`, `spawnvpe`, `spawnl`, `spawnle`, `spawnlp`,
  `spawnlpe`), `pty.spawn`, and `os.fork` (recorded **unconditionally** — no consumer on the list
  below forks, and a fork escapes every other wrapper).
Each file wrapper converts its path argument with `os.fsdecode(os.fspath(p))` (an `int` fd is passed
through), then makes it absolute with `os.path.abspath` (so a relative Agency path, e.g.
`Desktop/OtherApp` with cwd `<tmp HOME>`, is caught), and **records** the call when that text,
`norm`-ed, is equal to or under `norm(A)` **or** `norm(str(gtm_env.real_agency_root()))` (§0.1 "The
Agency root": the tmp-`HOME` `A` alone could never see a touch of the real Agency tree, §1.1
consequence 3), or is under `R/projects/` with a **first path component after `R/projects/`** for
which `project_dirs.is_agency_project_dir(name)` is true. Recording = **append the call to a
recorded list and raise `AgencyTouched`**. Each spawn wrapper tests the `cwd` argument (`abspath`-ed;
`None` = the current cwd) and **every argv element** — a string command (`shell=True`, `os.system`)
is `shlex.split` first — in each of these forms: the element after `os.path.expanduser` (so
`subprocess.run("ls ~/Desktop/OtherApp", shell=True)` is caught), every suffix after an `=` (so
`--root=<A>` is caught), and every substring starting at a `/` (so `-C<A>` and `x:<A>/y` are
caught), each `abspath`-ed only when it contains `/` or equals `.`/`..` (so `git -C <A> log`,
`find <A>`, `ls <A>` and `rg x <A>` are caught while a bare word such as `ls` is not). A path built
inside the child process (e.g. `bash -c 'cd ~/Desk''top/Agency'`) is out of the oracle's reach and
remains a code-review item, as are `DirEntry` methods (below) and **every `dir_fd`-relative
call** (`os.open(name, dir_fd=fd)`, `os.stat(name, dir_fd=fd)`, `os.scandir(fd)`, `os.fwalk`):
the wrappers `abspath` a relative name against the process cwd, not against the directory `fd`
names, so such a call is judged on the wrong path (a false negative). Consumers on the list below
do not use `dir_fd` forms; a reviewer rejects one that does unless it also compares the text path
it was built from. The test then runs each consumer
inside `try/except AgencyTouched: pass` and asserts **the recorded list is empty** (the assertion
is on the record, never on "nothing raised"). Consumers run: `validate --all`, `company.py list`,
`company.py register` (refusal paths above), G-W, G-B rule d1, `gtm_hooklib.identity_hosts_other_than`,
`checks.run_all` siblings, harvest attribution, **`harvest_tool_trail.main([])` (the weekly
default-glob harvest, via `default_globs_for_homes` → `_matching_project_dirs`)**,
`transcript_index.refresh(full=True)`, the 02_act.md §2.11 trail harvest and card-authorship scan,
`secret_sink` scans, and `ai_budget` attribution (04_hooks.md §4.6). **The in-process
`harvest_tool_trail.main([])` run first monkeypatches the committed import-time constant
each pack's `legacy_workdirs` (read by `harvest_tool_trail._legacy_workdirs`; the old hardcoded legacy-dir constant was removed 2026-09-28) to a path under the tmp tree** (§1.1 "Committed
import-time exceptions"); otherwise `_project_dir_name` `resolve()`s a real `~/Desktop` path
computed at import. It is the only load-bearing one: `DEFAULT_GLOBS_TEMPLATE` is defined but
referenced nowhere in `harvest_tool_trail.py`, so it needs no monkeypatch. The fixture tree
contains a registered repo-registry `agency` entry whose root is `<tmp HOME>/Desktop/OtherApp` (a real
directory holding a pack), an `R/projects/<P_A>` and `R/projects/<P_A>--claude-worktrees-x`
directory each holding a transcript, **and the second-residual input** (below): a transcript in a
**non-Agency** project dir — one in `R/projects/<project_dir_name_text(<tmp HOME>)>` (a session
started in `~`) and one in a GTM home's project dir — whose recorded `cwd` and at least one
`tool_input` path (`file_path`, `path`, a Bash `command` argument) lie under `A`. **Binding rule
for every consumer that reads transcripts (DECIDED HERE):** a path taken from transcript text
(`cwd`, any `tool_input` path, a path inside a Bash command) is compared with `A` and
`real_agency_root()` by the text `gtm_env.norm`/`is_under` compare **before** any `resolve()`,
`realpath`, `stat`, `exists`, `open` or other file-system call on it; a path equal to or under
either root is treated as "not under any GTM home" and never touched. **The committed
transcript-derived resolves, each fixed by the Appendix C item 14 coordinator change
(`requests/00_global_paths.md` R36, corrected by R41; anchored by function and quoted statement,
never by line number — header "The baseline"):** (i) `harvest_tool_trail._read_transcript_cwd`
runs `return Path(cwd).resolve()` on the recorded `cwd`; the text compare goes **there**, before
that statement, and a `cwd` equal to or under either root returns a module sentinel
`AGENCY_CWD` meaning "not under any home" — distinct from `None` ("unreadable, fail open, keep") —
which `resolve_transcript_paths`'s nested `_keep` (`cwd = _read_transcript_cwd(p)`; the path the
weekly `main([])` actually runs; it calls `_read_transcript_cwd` directly and never calls
`_transcript_cwd_is_under_home`) and the thin `_transcript_cwd_is_under_home` wrapper both treat
as **drop**; (ii) `attribute_company`'s playwright-gtm rung runs `cwd_path =
Path(cwd).resolve()`: the text compare goes before it, and a `cwd` equal to or under either root
attributes no company from that rung; (iii) the Write/Edit/NotebookEdit attribution loop runs
`Path(file_path).resolve().relative_to(home)`: the text
compare of `file_path` goes before it (a relative `file_path` is first joined, as text, to the
record's recorded `cwd`, never to the harvester's own cwd), and a path equal to or under either
root returns no attribution (no touch, no record). **Positive controls (each must go RED):** the same fixture run
against a deliberately wrong consumer — `lambda: Path(A, ".claude/gtm/company.json").read_text()`;
`[p.is_dir() for p in R_projects.iterdir()]`; `subprocess.run(["ls", A])`;
`subprocess.run(["git", "status"], cwd=A)`; `os.chdir(<tmp HOME>);
open("Desktop/OtherApp/.claude/gtm/company.json")`; `os.mkdir(A + "/x")`; `os.system("ls " + A)`;
`subprocess.run("ls ~/Desktop/OtherApp", shell=True)` (with the tmp `HOME`);
`subprocess.run(["git", "-C" + A, "status"])`; `open("/System/Volumes/Data" + A + "/x")` (the
firmlink form); and `Path(<the non-Agency transcript's recorded cwd>).resolve()` (a consumer that
resolves a transcript-derived path) — records a touch and fails the emptiness assertion,
proving the oracle can fail for each class it claims to cover. `harvest_tool_trail.main([])` run
over the second-residual transcripts with the text compare removed from `_read_transcript_cwd`
must also record a touch (RED control for site (i); removing it from `_transcript_cwd_is_under_home`
alone would falsify nothing, because `main([])` never calls that wrapper). The fixture also holds a
third second-residual transcript whose recorded `cwd` is **under a GTM home** and whose `Write`
`tool_input.file_path` is under `A`: `main([])` must record no touch and write no attribution for
it, and it goes RED when site (iii)'s guard is removed (the earlier fixture, whose `cwd` and path
are both under `A`, is dropped before attribution and so cannot exercise (iii)). A
`playwright-gtm` record with `cwd` under `A` in a GTM home's transcript goes RED when site (ii)'s
guard is removed.

**Agency Claude-session transcripts are skipped too (F9; DECIDED HERE).** `~/.claude/projects/`
holds Agency's own session transcripts (its project directories, counted by name only). They are
the shared runtime's files, but reading them would read Agency's work product, which §20.9 ("never
reads through anything from Agency") and the operator's directive forbid. The **Agency project-dir
prefix** is `P_A = project_dirs.project_dir_name_text(A)`, the pure-text helper in the
coordinator-owned `tools/gtm/project_dirs.py` (02_act.md §2.1, IMP-15; `harvest_tool_trail`
re-exports it): `project_dir_name_text(path_str: str) -> str = _PROJECT_DIR_NAME_UNSAFE_RE.sub("-",
os.path.normpath(os.path.expanduser(path_str)))` (lands with 08_seats_wps.md Appendix C item 14).
`project_dirs.project_dir_name(home)` (the public spelling every contract file uses, 02_act.md §2.1;
`harvest_tool_trail._project_dir_name` survives only as its alias) is **not** used for `A`: it calls
`home.resolve()`, i.e. `os.path.realpath`, which `lstat`s every component of `~/Desktop/OtherApp`. GTM
homes use `project_dirs.project_dir_name` (their dirs may be stat'd). **The one Agency filter** is
`project_dirs.is_agency_project_dir(name: str) -> bool` (same module, same change; pure text):
true iff `name.casefold() == P_A.casefold()` or `name.casefold().startswith(P_A.casefold() + "-")`
(Agency worktree/subfolder dirs). It is **casefolded**; the shared separator-bounded prefix helper
— `project_dirs.matches_project_dir_prefix`, the public name 02_act.md §2.1 gives it, which today
exists only as `harvest_tool_trail`'s private `_matches_project_dir_prefix` until the Appendix C
item 33 relocation — is case-sensitive and is **never** used for the Agency filter. Every
consumer that scans `R/projects/` — `transcript_index.refresh`, every 02_act.md §2.11 trail harvest,
the card-authorship scan, `secret_sink` scans, `ai_budget` attribution, **and the weekly full
harvest (`harvest_tool_trail.main([])` → `default_globs_for_homes` → `_matching_project_dirs`)** —
filters by name **before** descending: one `os.scandir(R/projects)`, then `entry.name` is tested with
`is_agency_project_dir` **before any** `DirEntry.is_dir()`/`stat()`/`Path` call on that entry (the
skipped entries are never opened, listed or stat'd; `DirEntry` methods are not interceptable by the
oracle above, so this ordering is also a code-review item). The committed `_matching_project_dirs`
(`projects_root.iterdir()` then `p.is_dir()` on every entry) violates this today; rewriting it to the
scandir-name-filter-first form is part of the 08_seats_wps.md Appendix C item 14 coordinator change
(`requests/00_global_paths.md` R16), and the rewrite also changes its root from the committed
`Path.home() / ".claude" / "projects"` to `company.claude_dir() / "projects"` (= `R/projects`,
the root every other consumer here scans; `requests/00_global_paths.md` R42). **The name filter
binds GTM tool consumers only.** An agent's own `Read`/`Grep`/`Glob` or Bash operand naming an
Agency project dir, an Agency session's temp dir, or a search root above them is a separate arm:
§0.4 "Agency session files" (R42). Consequence stated plainly: an Agency Claude session that acts on a GTM
company's accounts (a §20.9 boundary violation, tracked on Agency issue #5081) is **not** detected
from transcripts; the platform change-history reconcile (03_schemas.md §3.23) still sees its writes as
`outside:unknown`. Whether to detect it from transcripts is an operator decision (08_seats_wps.md Appendix C item
22), never a default. **Second accepted residual (stated; CROSS 03_schemas.md §3.16 scope):** the
name filter sees only project dirs named after Agency. Agency work done in a session whose project
dir is **not** `P_A`-prefixed — one started in `~` or `~/Desktop` that then works in
`~/Desktop/OtherApp` — lands in that session's own dir, and consumers that scan every non-Agency dir
(`transcript_index.refresh(full=True)`, the card-authorship scan, `secret_sink`) can read those
transcripts. It is accepted rather than closed by narrowing those consumers to GTM-home prefixes,
because the card-authorship and secret scans exist to catch agent writes and leaks from sessions
started anywhere. Binding on those consumers: they keep only the fields their own contract names
(agent ids and paths, Edit targets, secret-match locations), and never copy transcript text from a
dir that is not a GTM home's (or the OtherCompanyB legacy dir) into any GTM record.

**§20.9c and §20.9a (F8; the first policy item of the header's list — interim, until the reviewed
carve-out design below lands and the "Follow-up" (2) question is answered).** The facts, stated as the plan records them: §20.9a (verbatim, 2026-09-27) forbids any GTM
step from opening, listing, grepping or filing against `~/Desktop/OtherApp` or its GitHub repo.
§20.9c (verbatim, 2026-09-27) is headed "amends §20.9a for the GTM team", says in its body that
"§20.9a still binds everything that is not a marketing edit", and its quote ("Public website is built
from the agency repo … should be allowed to make changes to both applications and their marketing
stuff") answers the open question §20.9b left. So the plan **does** record which ruling amends which:
read under CONTRACTS.md precedence item 1, §20.9c's marketing-only scope reaches the OtherApp/Agency
repo. No later operator directive narrowing §20.9c is recorded anywhere in the tree (this section's
earlier heading cited "operator directive this session"; that directive is §20.9a itself, which
§20.9c amends), so this contract does not claim one.

**Interim deny (DECIDED HERE; a narrowing only).** §20.9c stands as ruled; the operator already
answered it ("Yes, you understand it correctly … allowed to do marketing type things, for both
companies and repos", plan §20.9c verbatim), and nothing here re-asks that question. What §20.9c adds for Agency beyond
§20.9a is exactly one thing: a `website_static` commit that lands OtherApp marketing-surface edits
in the OtherApp repo. Until the carve-out design below lands, that one thing is withheld: no pack's
`marketing_paths` may name a path equal to or under the Agency root. **The exact compare
(`company.validate_company`, never stat'd):** a `marketing_paths` glob is refused `agency_boundary`
when it is absolute, starts with `~`, or has a `..` segment (split on `/`); otherwise its **literal
prefix** `L` = the glob's leading `/`-separated segments up to (not including) the first segment
containing any of `*?[`, joined with `/` (empty when the first segment is a wildcard, which Appendix
C item 13 already refuses), and the glob is refused when `is_under(norm(os.path.join(H, L)),
norm(A))` or the same against `norm(str(real_agency_root()))`, where `H` is the pack's home. Until
touchpoint (i) of the follow-up below lands, the
`website_static` target repo is **always** `H`'s own git toplevel (02_act.md §2.4 makes every
patch relative to it), so Agency is reachable only if `H` itself is under Agency, which `register`
(below) and `gtm_slugs()` already refuse; `act.py` still refuses a `website_static` action whose
target repo is equal to or under the Agency root with `agency_boundary` (02_act.md §2.8 checks 1/9)
as defence in depth. A1/coordinator tests: `../Agency/x/**`, `/Users/u/Desktop/OtherApp/**`,
`~/Desktop/OtherApp/**` and, for a home `<tmp HOME>/Desktop/CSA`, `../Agency/**` are each refused
(RED when the absolute/`~`/`..` refusal or the joined compare is removed); `site/**` is accepted.
G-B rule i and the path gate's `agency-boundary` rule keep denying Agency in GTM scope
with **no** carve-out; and such a change goes to Agency's own development sessions (§20.9b's
fallback). Reason: implementing §20.9c for Agency means carving one commit path out of the two
gates that hold the §20.9a boundary, which is an engineering design that needs its own review;
withholding it until then grants nothing and loses nothing the operator cannot still get through
Agency's own sessions. Everything else in §20.9c (the CSA repo's marketing scope, the guardrail
below) applies as written.

**Follow-up, split by who decides.** (1) **Engineering — a design item, never an operator card**
(CSA `CLAUDE.md`: a security/architecture call a specialist agent exists to make is not carded):
the whole carve-out design, which must change **every** touchpoint that today makes a OtherApp
`website_static` edit impossible, not only the two gates — otherwise the interim would become
permanent with nobody deciding it (OtherApp's `H` is `~/Desktop/OtherApp_GTM/`, which holds no
site). The design lists and changes exactly these five: (i) **a `website_static` target-repo model
distinct from `H`** — a pack key (e.g. `website_repo_root`) naming the external repo root,
validated text-only by `company.validate_company` (never stat'd before the Agency compare; used by
this pack only), with every `website_static` patch and commit made relative to it instead of `H`'s
git toplevel (02_act.md §2.4); (ii) **`act.py` checks 1/9 `agency_boundary`** (02_act.md §2.8)
admitting exactly that root and exactly the pack's listed marketing paths under it; (iii)
**`validate_company`'s `marketing_paths` compare against `A`** ("Interim deny" above) relaxed for
that pack only, and only for globs whose literal prefix lies under the declared external root;
(iv) **the G-B rule i and path-gate `agency-boundary` carve-out**, limited to Read of the listed
paths plus `git -C <A> add|commit -- <listed paths>` from that pack's GTM scope, nothing else — no
other Agency read, list, grep or GitHub path; (v) **oracle positive controls** proving nothing
else under `A` is touched (a Read of an unlisted path under `A`, a `git -C <A> log`, a `grep -r` of
`A` each still denied and recorded). The coordinator files it as **one tracked issue with
trust-architect as reviewer-of-record, due before P1b**, whose acceptance criteria name all five
(`requests/00_global_paths.md` R26, rescoped by R41). (2) **Operator-only — one card, one question:** "Which
OtherApp site and which repo paths may the GTM team edit?" (plan §20.9c "when the operator names the
site"). §20.9c is implemented for Agency as its own reviewed change once (1) has landed and (2) is
answered; until both hold, the interim above holds.

**Scope of the gate (coordinator, 08_seats_wps.md Appendix C item 15; `requests/00_global_paths.md`
R15, narrowed by R24, re-scoped by R26).** This matters only for OtherApp `website_static` actions,
which first become possible at P1b. It does **not** hold any other Wave-2 WP (CSA and OtherCompanyB
work never touches OtherApp). Before P1b enables any OtherApp `website_static` row, the coordinator
confirms (a) the design issue of (1) is filed and **all five** of its touchpoints (i)–(v) have
landed with a clean trust-architect review (an issue that changes only the two gates does not
satisfy (a)), (b) the one-question card of (2) is posted on the **OtherApp home's** `operator_input`
surface (the path named by `~/Desktop/OtherApp_GTM/.claude/oversight/manifest.json`, plan §20.8
"the company's surface"; OtherApp must not depend on the CSA org's continuity, plan §20.11) and
answered before the row is enabled — that home is created at P1b, which is also the first moment
the question matters, so no interim CSA posting exists; if the card must be asked before the home
exists, it is posted to CSA's `OPERATOR_DECISIONS.md` `## Open` and **moved** (verbatim, with any
answer) to the OtherApp surface in the P1b change that creates the home — and (c) the interim is recorded in the plan as a
**new** §20.x entry (e.g. §20.18) that cites the issue and the card. §20.9c's verbatim text is
**never** edited to say something the operator has not ruled.

**The `marketing_paths` guardrail (plan §20.9c; every GTM home repo that is not Agency — today the
CSA repo).** A `website_static` action may only land a commit whose paths all match the pack's
`marketing_paths` (02_act.md §2.8 check 9, 02_act.md §2.4 `complete --commit`). Pack values are
**content-only** globs (08_seats_wps.md Appendix C item 13's validation); CSA's value is Appendix
C item 13's content-only list — **not** `marketing/website/**`, which covers `build.mjs` (the
mandatory AI-provenance publish gate), `deploy.mjs`, the tracking/consent scripts and
`partials/{tracking-inline,gtm-noscript,head,form}.html`. Two rules bind even **inside**
`marketing_paths`, because §20.9c allows marketing edits but forbids "developing" (application
code, infrastructure), and tracking/pixel/consent/lead-form changes need the measurement lane (plan
§6.3) and, for OtherCompany, trust-architect (plan §20.5 items 3 and 6):
- **Code, build, infrastructure and tracking — one definition, no pack override.** The single
  definition is `gtmlib.checks.MARKETING_PATH_NEVER`, its matching rule, and the tracking-content
  rule (`tracking_change_not_static`) of **08_seats_wps.md Appendix C item 13**, applied by
  02_act.md §2.8 check 9 at `propose` **and** at `complete --commit`, whatever the pack says. This
  section restates no pattern. **No pack key re-admits a never-listed path:** the former
  `marketing_code_paths` escape is withdrawn (`requests/00_global_paths.md` R25 supersedes R24's
  text for it); a change the rule refuses goes to that application's own development sessions, and a
  tracking, pixel or consent change goes to the measurement/tracking rows (App C item 13). Three
  decisions this section adds, requested **into** App C item 13 by R25 so the one definition carries
  them — the coordinator applies R25 before A1 builds check 9, so no second list ever exists: (i) the
  never-list also covers `.gitignore` (an edit could un-ignore the generated AI images), `*.toml`,
  `*.yml`, `*.yaml`, `.htaccess`, `_headers`, `_redirects`, `*.lock`, `Makefile`, `Dockerfile`,
  `tsconfig*.json`, `.pre-commit-config.yaml` and `**/.github/**`; (ii) the tracking-content rule
  is applied to **added and removed** lines (removing a tag snippet is a tracking change too) and
  also matches `javascript:`; (iii) `*.svg` stays content but is subject to the tracking-content rule
  (an SVG `<script` or `on*=` is refused). Tracking snippets are **out of scope** for `website_static`.
  **These are derived narrowings, not plan text (DECIDED HERE; header items (i)–(ii), 08_seats_wps.md
  Appendix B via R35):** §20.9c permits marketing edits and forbids "developing (application code,
  infrastructure)" without listing files; this contract reads the listed config/build/CI files as
  infrastructure (each can change what is built, served or ignored — e.g. `.gitignore` could
  un-ignore the AI-generated images, `_headers`/`.htaccess` change what every page serves) and
  tracking snippets as measurement-lane changes (plan §6.3; trust-architect for OtherCompany, plan
  §20.5 items 3 and 6). The reading only withholds; anything withheld still reaches the operator
  through the application's own development sessions or the measurement rows.
- **A displayed price is corrected only to the ruled source, bound by slot identity (DECIDED HERE;
  plan §20.9c "correcting displayed prices … so they match that company's ruled source of truth";
  "Changing an actual price … is a pricing decision (operator) — never a GTM edit").** A check on
  a flat set of allowed values cannot do this: swapping tiers (`$49 Basic`/`$99 Pro` → `$99 Basic`/
  `$49 Pro`) keeps every value in the set, and a quota such as `3` could pass as a price. So every
  displayed price is tied to a **named slot** in the ruled source.
  - **The source.** Pack key `pricing_source_ref` = exactly `{"path": "<repo-relative path of a JSON
    file in the same repo>", "reviewed_commit": "<40 lowercase hex>", "slots": {"<slot_id>":
    {"pointer": "<RFC 6901 JSON pointer>", "period": "month"|"year"|"one_time", "label":
    "<non-empty display label, e.g. \"Basic\">"}, …}}` (at least one slot; `slot_id` matches
    `^[a-z0-9][a-z0-9_]{0,63}$`; a slot is **amount + billing period + tier label**, because a
    price is not just a number: `$49/mo` → `$49/yr`, or moving the "Basic"/"Pro" label text while
    the slot elements stay, re-prices a tier while every amount still equals the source — the
    same class as the tier swap below). `V(slot)` = the value at that slot's
    pointer, which must be exactly one JSON number (never `bool`, object or array), parsed with
    `json.loads(…, parse_float=Decimal)`, ints as `Decimal`. act.py reads the file with `git -C <H
    toplevel> show <rev>:<path>` — at `propose`, `<rev>` = `HEAD`; at `complete --commit <sha>`,
    `<rev>` = `<sha>^1` (the state before the commit) — **never** from the working tree and never from
    the patch. `company.validate_company` refuses a `pricing_source_ref.path` that matches any
    `marketing_paths` glob, and act.py refuses a patch or commit touching that path
    (`price_source_in_patch`), so one change can never move the source and the price together.
  - **The ruled source is out of GTM's reach (DECIDED HERE; plan §20.9c "Changing an actual price
    … is a pricing decision (operator) — never a GTM edit").** `price_source_in_patch` stops one
    change moving source and display together, but a GTM session could otherwise move the source
    in an **earlier** commit (e.g. a `paths.*`-editable entry or the pack-scoped weekly commit,
    plan §3.2) and then "correct" the display to it. So: (1) **Write protection.** Pack key
    `pricing_source_origin` = a list of repo-relative paths of the documents the source is derived
    from (CSA: `["_Config_Project/docs/domain/opex_and_pricing.html"]`; may be empty). In GTM scope
    (`gtm_scope` non-None) and for every GTM seat (any scope), the path gate and G-W deny Write/Edit,
    and G-B rule c (write and removal class) and rule n (a GTM-scope `git commit`/`git apply`
    pathspec) deny shell and git writes, on every registered pack's `pricing_source_ref.path` and
    every `pricing_source_origin` entry (`pricing-source-write`), unconditionally (§0.4) and
    whatever any `paths.*` entry or `marketing_paths` glob says; `company.validate_company` refuses a
    pack whose `paths.*` editable entries or `marketing_paths` cover either. (2) **Review binding
    at act.py — the check chosen is the review record, not transcript attribution.** At `propose`
    and `complete --commit`, act.py computes `c = git -C <H toplevel> log -1 --format=%H <rev> --
    <path> <every pricing_source_origin entry>` and refuses `price_source_recent_change` (state
    unchanged) unless `c == pricing_source_ref.reviewed_commit` of the **committed** pack
    (`load_pack_safe`, HEAD; a GTM session cannot write the pack, 04_hooks.md §4.3
    `pack-edit-in-gtm-session`). So every source change needs a reviewed pack change (a
    non-GTM development session, trust-architect reviewer-of-record for a pricing-source commit)
    that records the new commit before any display may be corrected to it. Transcript attribution
    was **not** chosen: it cannot see in-process writes or sessions whose transcript is missing (the
    same blind spots §1.4 lists for the card scan), and it would fail open on them; a pinned sha
    fails closed. B1 tests: a GTM-scope `Edit` of `opex_and_pricing.prices.json` and of
    `opex_and_pricing.html` and a GTM-seat `Write` of either are denied `pricing-source-write`, and
    a GTM-scope `sed -i` of the source is denied by rule c (each RED when its arm is removed). A1
    tests: a source changed by a later commit than `reviewed_commit` → a correct-to-source patch
    refuses `price_source_recent_change` at `propose` and at `complete --commit` (RED when the check
    is removed); the same with `reviewed_commit` updated by a pack commit → allowed.
  - **Declared price-display files.** Pack key `price_display_paths` = a list of exact repo-relative
    file paths (no globs), each matching a `marketing_paths` glob and ending in `.html`, `.htm`,
    `.njk`, `.hbs` or `.md` (`company.validate_company` refuses anything else). In such a file every
    displayed price is the text of an element whose start tag carries `data-price-slot="<slot_id>"`,
    inside a tier container carrying `data-price-tier` (e.g. `<div data-price-tier><h3>Basic</h3>
    <span data-price-slot="basic_monthly">$49</span>/mo</div>`).
  - **No proposal field carries the ref.** The binding is pack → committed source; nothing an agent
    writes into the proposal is trusted for it. The proposal's `why` keeps its shape `{plan_ref,
    metric_id}` (03_schemas.md §3.2) and is not read by this rule.
  - **Decoding (one function, `gtmlib.checks.decoded_text(image: str, ext: str, *, attrs: bool)
    -> str`).** **HTML-family** = exactly the extensions `.html`, `.htm`, `.xhtml`, `.njk`, `.hbs`,
    `.md` and `.svg` (casefolded). An HTML-family image is parsed with the stdlib
    `html.parser.HTMLParser(convert_charrefs=True)` (`.md` included: its inline HTML is tags, the
    rest is data), which decodes numeric and named entities (`&#36;`, `&#x24;`, `&dollar;`,
    `&euro;`, `&pound;`) in data **and** attribute values. The decoded text is the concatenation, in
    document order, of every data chunk — plus, **only when `attrs=True`**, every attribute value
    except `data-price-slot` itself — joined with **no** separator (so `<span>$</span>` +
    `<span>59</span>` becomes `$59`); a line break inside data is kept. **Which form each rule uses
    (binding):** the slot amount (Rule A (1)) and the tier-container text (Rule A (4)/(5)) use
    `attrs=False` (data only), because attribute values such as `class="monthly-toggle col-2"` or
    `href="/pricing/yearly"` would otherwise add spurious amounts or period tokens; the outside-slot
    price-token compare (Rule A, last paragraph) and Rule B (1) use `attrs=True`, so a price hidden in
    an attribute (`content="$59"`) is still a change. A file that is not HTML-family is taken as raw
    text passed through `html.unescape` (the `attrs` flag does not apply).
  - **Rule A — a declared price-display file (any file in `price_display_paths` that the patch or
    commit touches).** On the **post-image**: (1) every `data-price-slot` element's decoded text must
    hold exactly one amount `\d[\d,]*(?:\.\d+)?` (commas removed → `Decimal`), and slot elements must
    not nest — else `price_slot_malformed`; (2) its `slot_id` must be a key of
    `pricing_source_ref.slots` — else `price_slot_unknown`; (3) its amount must equal `V(slot_id)` at
    `<rev>` — else `price_not_in_source` (`error.data` = `[{path, slot_id, shown, source}]`); (4)
    the slot's **tier container** — the nearest ancestor element whose start tag carries
    `data-price-tier` (a slot with no such ancestor → `price_slot_malformed`) — must have decoded
    text containing the slot's `label` (casefolded substring, whitespace runs collapsed) — else
    `price_label_mismatch`; (5) the **period tokens** in that container's decoded text — matches of
    `(?i)(?:/\s?mo\b|/\s?month\b|/\s?yr\b|/\s?year\b|\bper\s+(?:month|year)\b|\bmonthly\b|\bannual(?:ly)?\b|\byearly\b)`,
    each mapped to `month` (`/mo`, `/month`, `per month`, `monthly`) or `year` (the rest) — must
    all map to the slot's `period`, and a slot whose `period` is `month` or `year` must have at
    least one; a `one_time` slot must have none — else `price_period_mismatch`. A container
    holding two slots of different periods is refused `price_slot_malformed` (declare one tier
    container per slot). Rules (3)–(5)
    run on every slot of a touched file, not only changed ones, so an edit to a page whose shown
    price has drifted from the source is refused until it is corrected. Separately, the ordered
    sequence of **price tokens** in the decoded text **outside** slot elements — digit runs `\d+`,
    the symbols `$ € £ ¢`, and word-bounded `(?i)\b(?:usd|eur|gbp)\b` (entities already decoded, so
    `&#36;59` and split `<span>` forms are caught) — must be identical in the pre- and post-image;
    any difference → `price_unslotted`. So on a declared price page **any** change in digits,
    entities or currency tokens outside a slot is refused, including a price typed without a slot
    (`<td>59</td>`, no keyword needed).
  - **Rule B — every other touched file under `marketing_paths`.** A **price change** here is refused
    `price_outside_display_paths` (a price may change only inside a declared file, by Rule A).
    **Scope:** Rule B applies to a file whose extension is HTML-family or one of `.txt`, `.json`,
    `.csv` (casefolded) — the **text allowlist**. A **created** file has an empty pre-image and a
    **deleted** file an empty post-image (so adding or removing a page that shows a price is a price
    change). A text-allowlisted image that does not decode as strict UTF-8 is refused
    `price_outside_display_paths` (fail closed: a price in it cannot be read). A file outside the
    text allowlist (images, fonts, PDFs, video) is not judged by Rule B — **accepted residual,
    stated:** a price drawn inside an image is not detected here; the content review lanes see the
    image. The file has a price change iff any of: (1) the **ordered** sequence `AMOUNTS(decoded text of the
    whole image)` differs between pre- and post-image, where `AMOUNTS` = every match, deduplicated by
    span, in text order, of `(?i)(?:[$€£]|\b(?:usd|us\$|eur|gbp)\b)\s?(\d[\d,]*(?:\.\d+)?)`,
    `(?i)(\d[\d,]*(?:\.\d+)?)\s?(?:dollars?|usd|eur|gbp)\b` and the bare two-decimal
    `(?<![\d.])(\d[\d,]*\.\d{2})(?![\d.])`, each normalized to `Decimal` with commas removed (an
    ordered compare, so a tier swap is caught; a copy-only edit on a line that keeps `$49` leaves the
    sequence unchanged); (2) on the diff's `-` and `+` lines, each `html.unescape`d, the multiset of
    numbers `(?<![\d.])(\d[\d,]*(?:\.\d+)?)(?![\d.])` on lines matching the **word-bounded** price
    vocabulary `(?i)(?:\b(?:price|prices|pricing|plan|plans|tier|tiers|cost|costs|monthly|annual|annually)\b|/mo\b|/month\b|/yr\b|/year\b|\bper (?:month|year)\b)`
    differs between `-` and `+` lines (`planning`, `explanation` and `costume` do not match); (2b)
    on the `-` and `+` lines that carry an amount (an `AMOUNTS` match, or a number on a
    price-vocabulary line), the **ordered** sequence of period tokens (the Rule A (5) regex, each
    mapped to `month`/`year`) differs between the `-` side and the `+` side — so `$49/mo` → `$49/yr`
    is a price change even though every number is unchanged; (3) a
    `-` or `+` line, unescaped, matches `(?i)\b(?:dollars?|bucks|euros?|pounds? sterling)\b` (a
    spelled-out amount such as "forty-nine dollars" is never parsed, only flagged).
  - **Routing — no card by default.** `price_unslotted`, `price_slot_malformed`,
    `price_slot_unknown` and `price_outside_display_paths` are fixable by the session (mark the price
    with its slot, declare the page, or leave the digits alone) or belong to the application's own
    development sessions; none is carded. `price_not_in_source`, `price_period_mismatch` and
    `price_label_mismatch` mean the patch shows an amount, period or tier label the source does not
    hold for that slot: the session re-proposes with the source's values.
    `price_source_recent_change` goes to a development session (review the source change and record
    `reviewed_commit` in a pack change); it is never carded. An operator pricing card
    (pricing-economist questions, never reprices) is posted **only** when the session's evidence is
    that the **source itself** is wrong — that, and only that, is the operator's pricing call (CSA
    `CLAUDE.md`: card only what only the operator can answer). A pack with no `pricing_source_ref`,
    or a source that is missing at `<rev>`, unparseable, or has a slot whose pointer does not resolve
    to one JSON number → any Rule A file with a slot, or any Rule A/B price change, refuses
    `price_source_missing`. State is unchanged on every refusal.
  - **Each company's ruled source (DECIDED HERE).** **CSA:** the ruled source is
    `_Config_Project/docs/domain/opex_and_pricing.html` (CSA `CLAUDE.md`: the only cost/pricing
    doc), which is HTML, so CSA needs a **generated JSON projection** of it before any CSA price can
    be corrected: `_Config_Project/docs/domain/opex_and_pricing.prices.json`, produced by a CSA
    script from `data-price-slot`-tagged cells of the HTML, with a CSA test asserting the two agree
    (a data projection, not a second pricing doc). CSA's `pricing_source_origin` is
    `["_Config_Project/docs/domain/opex_and_pricing.html"]`, so both files are write-protected from
    GTM scope and GTM seats ("The ruled source is out of GTM's reach" above). It is a CSA development item filed by the
    coordinator (`requests/00_global_paths.md` R35), never a GTM edit. Until it lands, the CSA pack
    carries **no** `pricing_source_ref`, so every CSA price change refuses `price_source_missing`
    (fail closed; nothing is lost — the correction goes to a CSA development session); it **does**
    carry `pricing_source_origin` from the start, so the ruled HTML is write-protected before the
    projection exists.
    `modules/estimate_product_layer/frontend/src/content/pricingRows.json` is application display
    copy, **never** a ruled source (and is application code, outside `marketing_paths`).
    **OtherCompanyB:** no ruled price list is recorded (prices are per-job estimates) → no
    `pricing_source_ref`. **OtherApp** and **OtherCompany:** none recorded; a ref is added only in a
    reviewed pack change naming a file the operator has ruled to be the source.
Anything refused goes to that application's own development sessions (or, when the source itself is
wrong, the operator). A1 tests (A2 repeats the first four and the price tests at `complete --commit`):
with the pack glob deliberately wide (`marketing/website/**`), a patch editing
`marketing/website/partials/tracking-inline.html` → `non_marketing_path`, and one adding `<script
src="https://x.example/p.js">` to `templates/index.html` → `tracking_change_not_static`, and one
removing a `gtag(` line → `tracking_change_not_static` (each RED when its rule is reverted);
`marketing/website/build.mjs` → `non_marketing_path` with no pack key able to admit it. Price tests,
with slots `basic_monthly` → 49 and `pro_monthly` → 99 at `<rev>` and a declared page `pricing.html`,
each going RED when the named rule is reverted: the tier swap `$49 Basic`/`$99 Pro` → `$99`/`$49`
in the slot elements → `price_not_in_source` (RED when Rule A(3) is reduced to "amount is some
source value"); the same swap in an undeclared file → `price_outside_display_paths` (RED when Rule
B(1) compares a multiset); `<td>59</td>` added to `pricing.html` outside any slot, no keyword →
`price_unslotted`; `&#36;59` and `<span>$</span><span>59</span>` added to an undeclared file →
detected (RED when entity decoding or the no-separator join is removed); "planning 3 steps" →
"planning 5 steps" in an undeclared file → not a price change (RED when Rule B(2) matches by
substring); "forty-nine dollars" added → detected by Rule B(3); `basic_monthly` shown `$59` with
source 49 → `price_not_in_source`, with source 59 committed → allowed, with 59 only in the working
tree → still refused (RED when the source is read from the working tree); a slot id not in
`slots` → `price_slot_unknown`; a patch that also edits the source file → `price_source_in_patch`;
a copy-only edit on a line keeping `$49` in an undeclared file → not a price change; `USD 49`, `49
dollars` and `<td>49.99</td>` in an undeclared file each detected as amounts. Period and label
tests (slot `basic_monthly` = `{pointer, period: "month", label: "Basic"}`), each RED when its check
is removed: `…$49</span>/mo` → `…$49</span>/yr` next to the slot on `pricing.html` →
`price_period_mismatch` (Rule A (5)); the tier headings "Basic"/"Pro" swapped between the two
`data-price-tier` containers while the slot elements stay → `price_label_mismatch` (Rule A (4));
`$49/mo` → `$49/yr` in an undeclared file → `price_outside_display_paths` (RED when Rule B (2b) is
removed); a `month` slot whose container carries no period token → `price_period_mismatch`. The
pack keys `pricing_source_ref` (slot form `{pointer, period, label}` plus `reviewed_commit`; the
former `key` form and the bare-pointer slot form are withdrawn), `pricing_source_origin` and
`price_display_paths`, the refusal codes `price_not_in_source`, `price_period_mismatch`,
`price_label_mismatch`, `price_source_missing`, `price_source_in_patch`,
`price_source_recent_change`, `price_unslotted`, `price_slot_malformed`, `price_slot_unknown` and
`price_outside_display_paths`, the hook reason `pricing-source-write`,
`gtmlib.checks.decoded_text`, and the withdrawal of `marketing_code_paths` are requested of
03_schemas.md, 02_act.md, 04_hooks.md and 08_seats_wps.md (`requests/00_global_paths.md` R25,
amended by R35 and R41).

### 0.2 Language, dependencies, style

- Python 3 (machine has 3.13), `from __future__ import annotations`, **stdlib only, no
  exceptions** (`requests/05_approver.md` R12, applied here). Signature verification: ECDSA P-256 via
  `/usr/bin/openssl` (scrubbed environment), Ed25519 via the stdlib-only
  `tools/gtm/ed25519_verify.py` (05_approver.md §5.5).
  The third-party `cryptography` package is never imported by any GTM tool or hook:
  a user-installable package, or a stub earlier on `sys.path`, could make verification return
  success, which would defeat plan §20.8 (a `$` approval is valid only as a signature the
  operator's Touch ID releases). The former `GTM_VERIFY_BACKEND` override is retired with it (§1.4).
  Coordinator contract-consistency check (with the §1.4 retired-spelling test, same file set): it
  fails when a contract file names the package on a line that contains none of the words
  "retired", "never imported" or "stub" (the A2 test's stub package, 05_approver.md §5.5).
  **It fails on the current tree, substantively:** several 04_hooks.md lines still specify
  verifying inside hooks with that package, which must be never imported (not a wording slip). The coordinator
  applies `requests/05_approver.md` R12 to 04_hooks.md (verification through `/usr/bin/openssl` and
  `tools/gtm/ed25519_verify.py` only) and runs this check green **before B1 starts**
  (`requests/00_global_paths.md` R42).
- No network calls from any tool except connectors (06_connectors.md §6), collectors (07_notices_schedules.md §7.4), `secret_sink.py` (06_connectors.md §6.6),
  and the GSM credential fetch (06_connectors.md §6.3).
- Every **new** file writer (Wave-2 code) writes atomically: write `<name>.tmp.<pid>` in the same
  dir, `os.replace`. **Exception — files whose name is a fresh id or a `<UTCts>` (DECIDED HERE):**
  a file named by a random-suffix id (`tkt_`/`apr_`/`ntc_`/`unt_`, §0.3, **and the `S/lead_spool/`
  files**) or by a `<UTCts>` alone (`actions.broken-<UTCts>.jsonl`, `cancels/<slug>/_all.<UTCts>`,
  `lead_fallback.replayed-<UTCts>.jsonl`) is **created exclusively**, never
  `os.replace`d, because a same-second collision would silently overwrite the earlier record: write
  the tmp file, then `os.link(tmp, final)` and unlink the tmp (or open `final` with
  `O_CREAT|O_EXCL`). On `EEXIST`, a random-suffix name draws a new suffix (at most 5 tries, then exit
  1 `id_collision`); a `<UTCts>`-only name retries with `-<n>` appended (`n` = 2, 3, …, at most 99,
  then exit 1 `id_collision`), per the grammar in §0.3. **Lead-spool names are in the random-suffix
  class:** exactly `<UTCts>_<8 lowercase hex>.json`, matching
  `^(?P<ts>\d{8}T\d{6}Z)_(?P<rnd>[0-9a-f]{8})\.json$`; on `EEXIST` the 8 hex are redrawn (the
  `<UTCts>` is kept), at most 5 tries, then `id_collision`; no `-<n>` suffix is ever added. Replay
  order is `(ts, rnd)`. Committed writers are not retrofitted by any WP: `company.py`'s
  `_atomic_write_json` (register/unregister) already uses a unique `tempfile.mkstemp` name, and its
  `write_identity_index` keeps its fixed `<stem>.json.tmp` (`target.with_suffix(".json.tmp")`, e.g.
  `identity_index.json.tmp`; a known, narrow concurrent-writer race;
  any change to it is a coordinator change, not a WP's).
- Every appended JSONL file is appended under an exclusive `fcntl.flock` on the named lock file.
  `ST/lead_fallback.jsonl` has no lock of its own: it is appended under `ST/actions.lock`. **Lock
  timeout (DECIDED HERE):** every lock in this contract set whose timeout is not stated where it is
  defined waits at most 30 s; a tool that times out exits 12 (a hook fails per its own fail mode).

### 0.3 Timestamps, ids, JSON encodings

- **Machine timestamps** in every new record are UTC ISO-8601 with `Z`, second precision:
  `2026-09-27T15:04:05Z` — exactly `strftime("%Y-%m-%dT%H:%M:%SZ")` of a UTC datetime.
  (`activity_log.py` is untouched: its record `ts` is `now_denver_iso()` — America/Denver ISO with
  an offset and microseconds, whatever the pack's `timezone`; only its human "last updated" header
  uses the pack's `timezone`. Consumers parse the offset and never assume a local date. The
  committed `now_denver_iso()` falls back to a **naive** `datetime.now().isoformat()` when
  `ZoneInfo` is missing or fails, and `isoformat()` drops microseconds when they are 0: parsers use
  `datetime.fromisoformat` (which accepts both precisions), and a naive activity-log `ts` is
  interpreted as America/Denver.)
- **`<UTCts>`** (file-name timestamps: `_all.<UTCts>`, `actions.broken-<UTCts>.jsonl`,
  `lead_fallback.replayed-<UTCts>.jsonl`, and any other `<UTCts>` in this contract set) is exactly
  `strftime("%Y%m%dT%H%M%SZ")` of a UTC datetime (the id form, no colons), parsed with the same
  format as aware UTC. **Collision suffix (DECIDED HERE):** when an exclusive create (§0.2) finds
  the name taken within the same second, the file name carries `<UTCts>-<n>` (`n` = 2–99, no
  leading zero), e.g. `actions.broken-20260927T150405Z-2.jsonl`; parsers accept
  `(?P<ts>\d{8}T\d{6}Z)(?:-(?P<n>[2-9]|[1-9]\d))?` and order by `(ts, n or 1)`. Comparing it with an ISO field (e.g. 04_hooks.md §4.1's `<UTCts> ≥
  created_at`) is done on parsed aware UTC datetimes, never on strings.
  **DECIDED HERE:** UTC everywhere new, because four companies span time zones and records are joined.
- **Company-local time** (quiet hours, cadence, week boundaries) uses the pack's `timezone`.
- **Slug grammar:** `^[a-z][a-z0-9-]{1,31}$` (starts with a letter, 2–32 characters, no
  underscores) — **exactly the committed `company.SLUG_RE`** (and `scripts/repo_manifest.py`'s
  `SLUG_RE`, same pattern), which `register_gtm_company` and `validate_company` already enforce for
  the registry key and `pack.slug`; this contract narrows nothing and widens nothing. **DECIDED
  HERE:** ids below are split on `_`; all four real slugs (`exampleapp`, `other-company`,
  `otherapp`, `othercompany`) comply. The one code definition is `system_names.SLUG_RE`
  (03_schemas.md §3.22); the Appendix C item 14 coordinator change makes `company.py` import it
  instead of defining its own, and adds a coordinator test that
  `scripts/repo_manifest.SLUG_RE.pattern == system_names.SLUG_RE.pattern` (repo_manifest is a
  standalone script and keeps its own copy) (`requests/00_global_paths.md` R41). `act.py`,
  gate-gtm, `register` (`bad_slug`, §0.1), the lead-spool stdlib regex (§1.2) and cancel ingest
  (§1.2) refuse a slug that does not match.
- **Id formats:**

  | Id | Format | Allocated by |
  |---|---|---|
  | action | `act_<slug>_<YYYYMMDD>_<NNNN>` (UTC date, 4-digit per-company-per-day counter) | `gtmlib.store`, under the actions lock |
  | lead | `lead_<slug>_<YYYYMMDD>_<NNNN>` | `gtmlib.leads`, under the actions lock |
  | ticket | `tkt_<slug>_<YYYYMMDDTHHMMSSZ>_<6 hex>` | `gtmlib.tickets` |
  | approval request (= `$` card id) | `apr_<slug>_<YYYYMMDDTHHMMSSZ>_<6 hex>` | `gtmlib.approvals_verify` |
  | notice | `ntc_<slug>_<YYYYMMDDTHHMMSSZ>_<6 hex>` (slug may be the reserved `runtime` for runtime-wide notices, 07_notices_schedules.md §7.1) | any writer (07_notices_schedules.md §7.1) |
  | untrusted item | `unt_<slug>_<YYYYMMDDTHHMMSSZ>_<6 hex>` | `gtmlib.untrusted` |
  | experiment | `exp_<slug>_<NNNN>` | `experiments.py` |
  | cycle / run | `cyc_<slug>_<kind>_<YYYY_MM_DD>[_<HHMM>]` (plan §5); parse **only** with `CYCLE_ID_RE` below; date and HHMM are **company-local** (pack `timezone`). Scheduled runs: the id is computed **once, at job start, before the lease wait**, by `runner_probe.py`, which `run_gtm_job.sh` calls (07_notices_schedules.md §7.2); `inbox` HHMM = the `pack.cadence.inbox_checks` slot **the firing plist was rendered for**, passed to `run_gtm_job.sh` as its `--slot <HHMM>` argument (IMP-21; never computed from the clock, so a late fire can never take a later slot's id); the date, for **every** kind, = `run_date`, the company-local date of the most recent **scheduled occurrence** at or before job start — the kind's `RUN_TIMES` time (for `inbox`, the `--slot` time) on one of the kind's scheduled company-local days (07_notices_schedules.md §7.2, §7.3 `RUN_TIMES`) — so a late fire after company-local midnight, or a coalesced wake-up fire, keeps its occurrence's date and never takes an unscheduled (e.g. weekend) date; `monthly_load`/`daily`/`weekly`/`monthly` carry no HHMM. Plist calendar entries are the pack-timezone slots converted to the machine's timezone at render time (07_notices_schedules.md §7.3), because `StartCalendarInterval` fires in machine-local time. Interactive sessions: kind `interactive`, HHMM mandatory = company-local start minute (07_notices_schedules.md §7.6) | `runner_probe.py` (scheduled, called by `run_gtm_job.sh`) / `gtm_session.sh` (interactive) compute; `cycle.py open --cycle <id>` records |
  | mission run | `gtm_<YYYY_MM_DD>_<mission-slug>` (existing `MISSION_SCHEMA.md` format) | marketing-director |
  | hold | **= the action id** (one hold per action) | — |

  **DECIDED HERE:** random-suffix ids for tickets/notices/requests so independent writers (hooks,
  act.py, the approver) never need a shared counter; sequential ids only where one lock already
  serializes the writer. A random-suffix id's file is created exclusively and redraws its 6-hex
  suffix on `EEXIST` (§0.2), so a same-second 24-bit collision never overwrites a record. **`NNNN` is exactly 4 digits, `0001`–`9999`:** when the next value for a
  company-day would be 10000, the allocating command refuses exit 3 `id_space_exhausted` and writes
  no state (10 000 actions or leads for one company in one UTC day is itself a runaway; the refusal
  plus its `warn` notice is the intended stop). Ids are never widened or truncated.

  **Counter source (action and lead ids; DECIDED HERE).** There is no stored counter. Under the
  actions lock, the next `NNNN` for date `D` = 1 + the maximum `NNNN` captured by the regex
  `act_<slug>_<D>_(\d{4})(?!\d)` (resp. `lead_<slug>_<D>_(\d{4})(?!\d)`, with `<slug>` and `<D>`
  `re.escape`d) over the **raw text** of each source below — file contents, and file **names**
  where noted — (0 when none):
  - `ST/actions.jsonl`, every `ST/actions.broken-*.jsonl`, every `ST/lead_fallback*.jsonl` (contents);
  - `S/tickets/<slug>/*.json`, `S/approval_requests/<slug>/*.json`, `S/approvals/<slug>/*.json`
    (contents);
  - `S/approval_nonces.jsonl` — only lines whose parsed `company` equals `slug` (contents of those
    lines);
  - `S/cancels/<slug>/*` **by file name**, and the flat `S/cancels/act_<slug>_*` hand-made markers
    (§1.2) by file name — a surviving cancel for `_0012` would otherwise cancel a newly issued
    `_0012`;
  - `ST/review_briefs/*.json` **by file name**, `ST/patches/*.patch` by file name, and
    `ST/cycles/*.json` (contents) — the same set the chain-genesis check below scans;
  - `ST/connector_idem/*.jsonl` and `ST/cards_posted.jsonl` (contents) — a connector ledger keys a
    recorded success by action id (06_connectors.md §6.2), so a reissued id would replay that success
    with no platform write.
  Notices (`S/notices/**`) are **not** a source: a notice is display-only and never authorizes or
  replays anything by id. An implementation may pre-filter each source on the substring
  `_<D>_` before applying the regex. **Cost bound (DECIDED HERE):** so allocation does not grow with
  all history, an implementation **may** skip a whole source **file** (never a line of a file it
  reads) whose `st_mtime` is earlier than the start of UTC day `D` minus 48 hours — a file that
  holds a `_<D>_` id was written on or after day `D` began, and `tar` preserves mtimes on
  `backup_state.py --restore`, so a restored file keeps its real write time; the 48-hour skew covers
  clock adjustments and restores that set an mtime slightly early. It may not skip
  `ST/actions.jsonl`, a `ST/actions.broken-*.jsonl` or a `ST/lead_fallback*.jsonl` (append-only logs
  whose mtime is always recent; they are read in full, pre-filtered by substring). File-name
  sources (cancels, briefs, patches) are matched by name and need no read. A1 test: a ticket file
  naming `_0012` whose mtime is set to 49 hours before `D` is skipped, and one at 47 hours is read
  (so the skew, not the mere existence of a filter, is what the test pins); the mtime filter is
  optional, so this test runs only when the implementation enables it.
  An unreadable source file is an error (exit 1 `id_source_unreadable`), never skipped, because
  skipping it could reissue an id it holds. So an id used before a `chain-repair --replay` rotation,
  or referenced by a ticket, approval, nonce, cancel, brief or cycle that survived a restore of an
  older log, is never issued again. A1 tests: rotate a log holding `act_x_<D>_0007`, then `propose` →
  the new id is `_0008`; a ticket file naming `_0012` with no log line → `_0013`; a surviving cancel
  file `S/cancels/x/act_x_<D>_0015` with no log line → `_0016` (RED when the cancels source is
  removed); a connector ledger line for `act_x_<D>_0020` with no log line → `_0021` (RED when the
  connector-ledger source is removed); a next value of 10000 → exit 3 `id_space_exhausted`, log
  unchanged.

  `CYCLE_ID_RE = r"^cyc_(?P<slug>[a-z][a-z0-9-]{1,31})_(?P<kind>monthly_load|monthly|weekly|daily|inbox|interactive)_(?P<date>\d{4}_\d{2}_\d{2})(?:_(?P<hhmm>\d{4}))?$"`
  — the kind alternation is listed longest-first so `monthly_load` never parses as `monthly`.
  **HHMM per kind (binding):** `inbox` and `interactive` require the `hhmm` group; `monthly_load`,
  `monthly`, `weekly` and `daily` forbid it. The regex admits both shapes for every kind, so
  `system_names.cycle_id_ok(cycle_id: str) -> bool` (same module) adds that check, and `cycle.py
  open` and `validate_run.py` refuse a mismatch with exit 3 `bad_cycle_id_hhmm` (no state written).
  Tests (one per kind): `inbox`/`interactive` without HHMM → `bad_cycle_id_hhmm`, with → accepted;
  `monthly_load`/`monthly`/`weekly`/`daily` with HHMM → `bad_cycle_id_hhmm`, without → accepted;
  each RED when `cycle_id_ok`'s kind check is removed. Defined once in
  `tools/gtm/system_names.py` (03_schemas.md §3.22), together with the dispatch-tag regex `TAG_RE` (04_hooks.md §4.6), and
  imported by `cycle.py`, `ai_budget.py`, gate-gtm, `agent_budget.py` (tag parse, 03_schemas.md §3.13),
  `runner_probe.py` (for `run_gtm_job.sh`, 07_notices_schedules.md §7.2), `gtm_session.sh` (via
  `python3 -c` import) and `validate_run.py`.
- **Card ids** match `^[A-Za-z0-9_-]{1,80}$` (the longest `$` card id, `apr_` + a 32-char slug +
  `_<16>_<6>`, is 60 characters). Test with a 32-character slug (a registrable company).
- **Hash-chained JSONL** (`actions.jsonl`, and the existing `ACTIVITY_LOG.jsonl`/`TOOL_TRAIL.jsonl`):
  each line is `json.dumps(obj, ensure_ascii=False, sort_keys=True)`; `prev_hash` = hex sha256 of the
  previous **stripped raw line**'s UTF-8 bytes; the genesis line carries `prev_hash: null`. The
  **append** semantics are exactly `activity_log._append_chained`'s. **Verification of
  `actions.jsonl` is stricter than `activity_log.verify_chain` (I9; DECIDED HERE):** that function
  accepts a missing/empty file and an unchained legacy prefix, which would let a deleted log restart
  history silently. `store.verify_chain` requires line 0 to be a `genesis` event with `seq: 0` and
  `prev_hash: null`, every later line to chain, `seq` contiguous, and no unchained prefix; and it
  compares against the **chain anchor** `S/chain_anchors/<slug>.json`, exactly
  `{"seq": 41, "line_sha256": "<64 lowercase hex, no prefix>", "ts": "2026-09-27T15:04:05Z"}` where
  `seq` is the last line's `seq` and `line_sha256` = hex sha256 of that last line's **stripped raw
  line** UTF-8 bytes — the same bytes, and the same bare-hex form, as the next line's `prev_hash`
  (not the `sha256:`-prefixed digest string of this section). `store.append` rewrites it atomically
  (same lock) after every append. Verification cases, exhaustively (case 0 is checked first):
  0. anchor file **present but not a valid anchor** — unreadable (`OSError` other than
     `FileNotFoundError`), not valid UTF-8 JSON, not a JSON object, a missing or extra key, `seq`
     not an `int` (`bool` excluded) or negative, `line_sha256` not exactly 64 lowercase hex, or
     `ts` not the §0.3 machine-timestamp form → broken (`chain_truncated`) → `PAUSE.chain`. It is
     **never** treated as an absent anchor: that reading would reach case 4 on an empty log and mint
     a new genesis, silently restarting history. Only a `FileNotFoundError` is "absent";
  1. anchor present, and the log missing/empty, its last `seq` below the anchor's, or the line at the
     anchor's `seq` hashing to a different value → broken (`chain_truncated`) → `PAUSE.chain`, never
     a new genesis;
  2. anchor **absent** and `actions.jsonl` **present** (non-empty) → broken (`chain_truncated`) →
     `PAUSE.chain`: the anchor can only be missing if it was deleted, and accepting-and-recreating
     would let "delete the anchor, then truncate the tail" pass unnoticed. Only `chain-repair
     --replay` recreates the anchor;
  3. anchor absent **and** `actions.jsonl` absent/empty while any source of the counter list above
     other than `ST/actions.jsonl` itself references an `act_<slug>_` id → broken too
     (`chain_truncated`). "The actions log" here is `ST/actions.jsonl` only: a surviving
     `ST/actions.broken-*.jsonl` counts as a **reference** (it proves history existed);
  4. anchor absent, log absent/empty, and no such reference → a truly fresh company → new genesis
     (and its anchor);
  5. anchor present and **behind** the log (anchor `seq` < last `seq`, e.g. a crash between the
     append and the anchor rewrite) while the line at the anchor's `seq` hashes to the anchor's
     `line_sha256` and the rest chains → passes. Re-anchoring is a write, so it follows 02_act.md
     §2.2b's signature `store.verify_chain(ctx, *, locked: bool = False) -> tuple[bool, str |
     None]`: with `locked=True` (the caller already holds `store.locked(ctx)` — `store.append` and
     dispatch's locked re-verify) the verifier rewrites the anchor to the last line, atomically,
     before returning; with `locked=False` (a reader such as `status`, which takes no lock) it
     returns `(True, None)` and writes nothing — the next locked caller re-anchors. That is the one
     write `verify_chain` ever makes (`requests/00_global_paths.md` R42 asks 02_act.md §2.2b to say
     "read-only unless `locked=True`, where case 5 re-anchors").
  A1 tests: one per case, and one per case-0 malformation (unreadable, not JSON, missing key,
  extra key, `seq: "41"`, `seq: true`, a 63-hex and an uppercase-hex `line_sha256`), each →
  `chain_truncated` + `PAUSE.chain` with an empty log, RED when that malformation is treated as an
  absent anchor (the test asserts no genesis line is written); case 2 goes RED when the check is
  reverted to "recreate the anchor"; case 5 with `locked=False` leaves the anchor file
  byte-identical (RED when the reader re-anchors), and with `locked=True` rewrites it to the last
  line. The anchor lives under `S` so deleting `ST` does not delete it (G-B rule
  c protects both). `chain-repair --replay` (02_act.md §2.4) — the only sanctioned restart — rewrites the
  anchor to its new genesis line in the same lock. **Backup and restore carry the anchor with the
  log (F-anchor; 08_seats_wps.md Appendix C item 7):** `S/chain_anchors/<slug>.json` is in `company.backup_set()`
  for that company, and a `backup_state.py --restore` of an archive that holds `ST/actions.jsonl`
  must restore the anchor from the **same** archive (via `--runtime-state-to`); a restore that would
  write the log without the matching anchor refuses (exit 3, `anchor_not_in_archive`) instead of
  leaving a newer anchor beside an older log (which would read as `chain_truncated`).
  **The backup captures the log and its anchor at one moment (IMP-08; DECIDED HERE).**
  `backup_state.py --company <slug>` takes `ST/actions.lock` (exclusive `fcntl.flock`, the same
  30 s timeout as act.py, 02_act.md §2.3), reads the bytes of `ST/actions.jsonl` and of
  `S/chain_anchors/<slug>.json` into memory, releases the lock, and writes both members into the
  tar from those snapshots (`tar.addfile` under their normal arcnames,
  `.claude/gtm/state/actions.jsonl` and `_gtm_state/<slug>/chain_anchors/<slug>.json`). Each
  snapshot's `TarInfo` carries `size` = the snapshot's byte length, `mtime` = that file's
  `st_mtime` and `mode` = `0o600`, taken from an `os.fstat` of the same open descriptor the bytes
  were read from, under the lock (the mtime matters: §0.3's counter-source mtime skip reads it after
  a restore). The recursive `tar.add` of the `ST` root (a `backup_set()` entry) and the
  `backup_set()` entry for the anchor skip the two live files so they are archived exactly once —
  through the **one combined `filter=`** of §1.3 "Protection and backup of `ST`", which returns
  `None` for exactly those two arcnames as well as for every backup exclusion. **Pair presence at
  backup time (binding):** log present **and** anchor present → both snapshotted; log present and
  anchor **absent** → exit 3 `anchor_missing` (stderr `error: anchor_missing: <slug>`), **no
  archive written** (such an archive could never pass restore check (5), and the missing anchor is
  itself §0.3 case 2, `chain_truncated`); log absent and anchor absent → neither member is written
  (a fresh company); log absent and anchor present → the anchor alone is snapshotted (the §0.3 case
  1 state is reported by `verify_chain`, not repaired by a backup). An append that lands
  after the lock is released is simply not in this backup; it can never split the pair. Test (the
  coordinator follow-up of 08_seats_wps.md Appendix C item 7): monkeypatch the tar step to run a
  real `store.append` between writing the two members → restore the archive → `store.verify_chain`
  passes and no `PAUSE.chain` is written; the test goes RED when the lock/snapshot is removed.
  Further tests: log present and anchor deleted → `backup_state.py --company x` exits 3
  `anchor_missing` and no archive file exists afterwards (RED when the log is archived alone);
  neither present → exit 0 with neither arcname in the archive; a snapshot member's `mtime` equals
  the source file's `st_mtime` and its mode is `0o600` (RED when `TarInfo` defaults are kept).
  **`backup_state.py` exit codes (IMP-17; DECIDED HERE):** the committed codes stay as they are —
  0 ok, 1 every pre-existing error or refusal (archive not found, unsafe member, runtime-state
  refusal, unknown company; committed tests assert 1), 2 usage — and the new outcomes take the
  common codes: 3 `anchor_not_in_archive` (stderr `error: anchor_not_in_archive: …`), 3
  `anchor_missing` (backup, above), 12 timeout on `ST/actions.lock`. **Check order in
  `backup_state.py --restore` (binding; the committed order is kept, nothing is reordered;
  anchored by function and quoted statement, header "The baseline"):** (0) `--restore` without
  `--to` → exit 2 (`main`: `error: --restore requires --to <dir>`, the first check, before the
  archive is looked up); (1) archive not found → exit 1 (`main`, before
  `restore_archive`); (2) the committed runtime-state refusal (the archive holds `_gtm_state/`
  members but `--runtime-state-to` is absent) → exit 1 `RuntimeStateRestoreRefused`; (3) the
  committed mixed-slug refusal → exit 1 `RuntimeStateRestoreRefused`; then the committed runtime
  prefix strip (`restore_archive`'s `member.name = _strip_runtime_state_prefix(member.name,
  effective_slug)`) rewrites the runtime members' names; (3b) the committed runtime-member hardlink
  refusal (`restore_archive`'s `if member.islnk(): raise UnsafeArchiveMember(…)`) → exit 1; (4)
  unsafe archive member (`_validate_member`, home members then runtime members) → exit 1; (5)
  **new**, after (4) and before any member is extracted: anchor pairing, with `<slug>` =
  `restore_archive`'s `effective_slug` (the `--company` value, else the slug auto-detected from the
  archive's runtime members) — the archive holds the arcname `.claude/gtm/state/actions.jsonl` and
  either `effective_slug` is `None` (no `--company` and no runtime member to detect a slug from,
  so no anchor can be in it) or the archive lacks `_gtm_state/<slug>/chain_anchors/<slug>.json` →
  exit 3 `anchor_not_in_archive`. Check (5) evaluates a set of member names **snapshotted before the
  prefix strip** (captured right after `getmembers()`, ahead of the strip loop), because after the
  strip the runtime arcname no longer carries `_gtm_state/<slug>/`; only its refusal is emitted
  after (4). So `--restore` without `--runtime-state-to` of an archive holding the log exits 1 at
  (2) before (5) is reached; coordinator tests (Appendix C item 7) assert (2) before (5), (3b) before
  (5) and (4) before (5), each RED when the new check is moved ahead of the one it must follow, an
  archive holding both members passes (5) (RED when (5) reads the post-strip names), and an archive
  holding only the home log member, restored without `--company`, exits 3 `anchor_not_in_archive`
  (RED when a `None` `effective_slug` skips check (5)).
- **Canonical JSON** (digests and signatures): `json.dumps(obj, sort_keys=True, separators=(",", ":"),
  ensure_ascii=False).encode("utf-8")`. Written below as `canon(obj)`.
- **Digest strings:** `"sha256:" + hexdigest`.

### 0.4 Enforcement conventions (hooks)

New hooks follow the existing hook contract: exit code is **always 0**; a deny is the JSON
object `_lib.emit_pretooluse_deny(msg)` prints; every deny and would-block is logged with
`_lib.log(...)`. **`CSA_DISABLE_HOOKS=1`** (read from the hook process's own environment) is the one
off switch: the hook returns allow **before any parsing or logging**, exactly as the committed
`pretooluse_task.py` does under `_lib.disabled()`.

**"GTM seat" (binding definition for this whole file; DECIDED (wave1c); plan §7.4, §20.3).** A
**GTM seat** is an `agent_type` in `system_names.GTM_SEATS` (unioned with `model_policy.json`'s
`gtm_seats`, 03_schemas.md §3.22) — the plan §7.4 set of new seats that "exist only for GTM" and
the plan §20.3 "`agent_type ∈ gtm_seats`" set — and **never** a `DEPARTMENT_SEATS` member, the same
reading 04_hooks.md uses. Every "GTM seat" clause in this file means that set: §0.1's
`pricing-source-write` write protection, §1.2's registry-write request (`gtm-registry-write`), the
top-level PHI precondition (`phi-toplevel-unclassified`), the `phi_denylist.json`-unreadable arm
(`phi-denylist-unreadable`), the fail-closed read roots' `H_eff` rule, and header items (iii),
(v) and (vi). A `DEPARTMENT_SEATS` member (marketing-director … market-analyst) is covered by those
clauses **only in GTM scope** (where GTM scope already covers it), because plan §7.4 says outside a
GTM session "existing seats … are allowed … no new denials for existing work". **The one
exception is the Agency arm** (test (2) of "The Agency boundary outside GTM scope" below and §0.1's
reach summary), which keeps `gtm_seat_types()` = `GTM_SEATS` ∪ `DEPARTMENT_SEATS`, because plan
§20.9a binds "every … seat" of GTM work. B1 test: a `content-strategist` `Read` of a CSA-repo file
from a non-GTM CSA session with **no** `phi_toplevel_classification.json` (a valid
`phi_denylist.json` present) is not denied (RED when `DEPARTMENT_SEATS` leak into the PHI arms),
while the same `Read` by `gtm-analyst` is denied `phi-toplevel-unclassified`; with the
classification valid and `phi_denylist.json` deleted, the `content-strategist` `Read` is again not
denied while the `gtm-analyst` one is denied `phi-denylist-unreadable`.

**GTM safety denies do not depend on `_lib.enforcing` (DECIDED HERE).** `_lib.enforcing(cwd)`'s
full precedence (`hooks/_lib.py` `enforcing`): (1) `disabled()` (`CSA_DISABLE_HOOKS=1`) → False;
(2) env `CSA_ENFORCE=1` → True; (3) the global `~/.claude/.enforce` marker exists → True; (4) the
per-repo walk (the first ancestor with a `.git` entry must also hold `.claude/.csa-enforce`) →
True; else False. It is true today only because of step (3); without the marker and without
`CSA_ENFORCE=1` it falls back to the step-(4) walk, which none of the GTM homes
(`~/Desktop/OtherCompanyB/GTM/`, `~/Desktop/OtherApp_GTM/`, `~/Desktop/OtherCompany_GTM/`) is required to
carry. The plan states these rules unconditionally (e.g. §20.3 "fails closed on a match"), so a
machine-wide rollout flag must not turn them into log-only. Therefore:
- **In GTM scope** (`gtm_hooklib.gtm_scope(...)` non-None, 04_hooks.md §4): every GTM rule denies
  unconditionally — G-A (all rules, incl. tickets, hosts, PHI hosts, 3b), G-B (all rules), the path
  gate (incl. `phi-path` and `agency-boundary`), G-W, and gate-gtm (incl. the budget rules).
- **In every session:** the rules that protect GTM state and trust files deny unconditionally —
  G-B rule c (`protected-state-write`), rule k (operator/launchd-only literals), rule l
  (`gtm-identity-forge`, 02_act.md §2.3) and rule m (`gtm-env-override`, the §1.1/§1.4 test-override
  arm; both requested, `requests/00_global_paths.md` R12/R20), and G-W's `machine-written-path` and
  `trust-root` deny classes (04_hooks.md §4.3).
- **The Agency boundary outside GTM scope (DECIDED HERE; plan §20.9a binds "No GTM build step,
  seat, tool, consult, research agent or issue" — GTM work — in "every phase and every agent"; the
  operator's directive "stop going into the agency repo").** Rule i (incl. its `<org>/Agency`
  GitHub forms) and the path gate's `agency-boundary` rule also deny, unconditionally, when the
  call's cwd is **not** equal to or under the Agency root (`is_under(norm(cwd), norm(A))` or the
  same against `real_agency_root()`, text only) **and** the call is GTM work by one of these
  tests: (1) GTM scope; (2) the payload's top-level `agent_type` is in
  `gtm_hooklib.gtm_seat_types()` = the union of the first two sets `system_names.seat_sets()`
  returns (`GTM_SEATS` ∪ `DEPARTMENT_SEATS`, each already unioned with `knowledge/model_policy.json`'s
  `gtm_seats` / `gtm_department_seats` keys, 03_schemas.md §3.22; the one definition, 08_seats_wps.md
  Appendix C item 104) — packs carry no seat key, so no pack contributes to it. `market-analyst` is
  a member (it is in `DEPARTMENT_SEATS`); **`research-scout` is not** (it is a general runtime seat,
  also dispatched for non-GTM prior-art work) and is covered **only** through test (3), a GTM
  dispatch tag; (3) the payload carries a
  non-empty `agent_type` and its `agent_id` is bound to a `S/dispatch_tags.jsonl` row carrying a
  `[gtm company=… run=…]` tag (gate-gtm records the tag at admission, 04_hooks.md §4.6), so a
  catch-all type (`general-purpose`, `Explore`, `Plan`, `claude`) dispatched **for** GTM work is
  covered. The binding key (how a sub-agent's `agent_id` is tied to the admitting `tool_use_id`'s
  row) is **UNVERIFIED** and is added to probe q; until the probe records a working key, test (3)
  is inert and such dispatches are prose-covered like any other non-GTM sub-agent.
  **Scoped to GTM work, deliberately (this revises R37's machine-wide widening; R41):** any other
  sub-agent — `implement`, `explore`, `agentic-systems-architect`, `trust-architect` and the
  catch-all types dispatched without a GTM tag — stays prose-covered, exactly like a top-level
  session, because runtime maintenance from `~/.claude` legitimately reads Agency's shared-runtime
  surfaces by operator direction and runtime `CLAUDE.md` §1 tells sessions to delegate multi-file
  work: `CLAUDE.md` §2's worktree-twin sweep (`find <repo>/.claude/worktrees -path
  '*/.claude/agents/*.md'` over every registered repo), the `bundle_parity.py`/`model_pin_parity.py`
  roster scans, and the operator-gated Phase-2 migration of Agency's 19 product-local agents.
  A machine-wide arm would make those non-delegable and land unannounced on every product
  session, a policy decision plan §20.9a does not make. Agency's own sessions and their
  sub-agents run with a cwd under Agency and are unaffected either way. **Not covered by a hook:**
  a top-level (main) session — its payloads carry no `agent_type` — and every non-GTM sub-agent,
  started outside Agency; that residual is covered by this section, §0.1, each WP's forbidden list
  and the §0.1 oracle as the test-time backstop. **Dependencies:** the arm is inert wherever the
  payload lacks `agent_type` (and, for test (3), `agent_id`) — UNVERIFIED for Bash/Read/Grep/Glob payloads (probe q,
  04_hooks.md §4.4); until probe q passes, sub-agent coverage is prose-only too, and the
  coordinator records the probe result before B1 lands. **Fast path.** The **committed**
  `bash_gate.sh` has no numbered arms and no GTM token at all: one `case "$payload" in` whose single
  forwarding arm matches `*git*`, `*gcloud*`, the `CSA_ALLOW_GIT_STATE_OPS` escape-var literal, and
  the `gh issue close`/`gh issue create`/`gh_issue.sh create`/`gh project`/`--project` shapes;
  everything else exits 0 without python. The numbered arms (2, 2b, 4, …) are what 04_hooks.md §4.7
  specifies B2 **adds**; as specified there, arm 2b forwards only `GTM_DEPT_SEAT_RE` payloads (the 9
  department seats) and arm 4 carries no Agency token. So `requests/00_global_paths.md` R42
  (superseding R41's token list) asks 04_hooks.md §4.7 for: (a) arm 2b's regex widened to every
  `gtm_seat_types()` member (the P2 parity test compares it with that union, not with
  `DEPARTMENT_SEATS`); (b) one new arm, exactly: `shopt -s nocasematch` (bash 3.2 has it; `${x,,}`
  is bash 4 only and `#!/usr/bin/env bash` may resolve to macOS's `/bin/bash` 3.2), then forward
  when the payload carries a non-empty `agent_type` (`[[ $payload =~
  \"agent_type\"[[:space:]]*:[[:space:]]*\"[^\"]+\" ]]`) **and** matches the bare glob `*agency*`
  or `*oauth-google-*`, then `shopt -u nocasematch`. The bare `*agency*` token is deliberate:
  narrower tokens such as `*desktop/agency*` miss `cd ~/Desktop && ls Agency`; it forwards more
  than it must (one python spawn), which is the §4.7 cost rule's accepted direction. A glob that
  never spells the word — `ls ~/Desktop/Agen*` — carries no token; it reaches python only through
  arm 2b (a `gtm_seat_types()` member) or the GTM-scope arm, and python's rule i expands nothing, so rule i's own
  glob-operand clause (04_hooks.md §4.2) must treat a glob operand whose literal prefix is an
  ancestor of `A` and whose pattern can match `Agency` (`fnmatch.fnmatchcase("agency", <segment>)`
  on the casefolded segment) as naming `A`. Python then applies tests (1)–(3). The B1 tests below
  run **end-to-end through `bash_gate.sh`** (not only as unit tests of the python arm), so a
  missing fast-path arm makes them RED. B1 tests: a `gtm-analyst` `Read` of `<A>/x` from a CSA cwd
  outside GTM scope is denied `agency-boundary` (RED when `gtm_seat_types()` omits `GTM_SEATS`),
  and the same call with a cwd under Agency is allowed; a `gtm-analyst` Bash `cd ~/Desktop && ls
  Agency` and `ls ~/Desktop/Agen*` from a CSA cwd are each denied (RED when arm 2b is left at
  `DEPARTMENT_SEATS` or the glob clause is removed); a `research-scout` Bash `cd ~/Desktop && ls
  Agency` from a CSA cwd with **no** GTM tag reaches python through the new arm (RED when the arm
  uses `*desktop/agency*`) and is **not** denied (logged only; research-scout is not a `gtm_seat_types()` member);
  once probe q records the binding key, the same `research-scout` call and a `general-purpose` Bash
  `ls <A>` from a CSA cwd whose `agent_id` is bound to a GTM `dispatch_tags.jsonl` row are denied
  (RED when test (3) is removed); an `implement` `Read` of
  `<A>/x` and a `general-purpose` Bash `ls <A>` from a `~/.claude` cwd with **no** GTM tag are
  **not** denied by this arm (logged only; RED when the arm is widened back to every
  `agent_type`); a payload with no `agent_type` from a CSA cwd is not denied by this arm (logged
  only).
- **Agency session files (DECIDED HERE; plan §20.9 "never reads through anything from Agency",
  §20.3 prevention-first; `requests/00_global_paths.md` R42).** Agency's own sessions leave files
  **outside** `A`, so a compare against `A` alone never sees them: their transcripts in
  `R/projects/<c>` (§0.1 F9) and their scratchpads under `/private/tmp/claude-<uid>/<c>/<session>/`
  (the payload's `scratchpad_dir` form, 04_hooks.md §4.7 "Fixed payload keys"), for every project
  dir name `c` with `project_dirs.is_agency_project_dir(c)`. Plan §20.3 records that those sessions
  do legitimate Open Dental integration work, so both places can hold Open Dental-derived PHI as
  well as Agency's work product. The F9 name filter binds GTM tool consumers only, never an agent's
  own Read/Grep/Glob. So the path gate's `agency-boundary` rule and G-B rule i also deny,
  unconditionally, for exactly the calls the Agency arm above covers (tests (1)–(3), cwd not under
  `A`), with reason `agency-boundary`, by **text compare only** (`gtm_env.norm`/`is_under`, no stat,
  no `realpath`; `T` below ranges over the temp roots `/private/tmp`, `/tmp` and
  `norm_text(tempfile.gettempdir())`):
  (1) **a target in an Agency session's files** — any Read/Grep/Glob/Edit/Write/WebFetch target or
  Bash path operand whose normed path is equal to or under `norm(R) + "/projects/" + c` or
  `norm(T) + "/" + k + "/" + c` for any single component `k` starting with `claude-`, where `c` is
  the next path component and `is_agency_project_dir(c)` holds;
  (2) **a search rooted above them** — any Grep or Glob call, and any Bash **recursive search**
  (`grep`/`egrep`/`fgrep` with `-r`, `-R`, `--recursive`, `--dereference-recursive` or `-d
  recurse`, including inside a short-option cluster; `rg`; `ag`; `find`; `fd`; `tree`; `du`; `ls`
  with `-R`; `tar` in create mode), whose search root (the Grep/Glob `path`, default the payload
  `cwd`; each Bash path operand, default the payload `cwd`) is equal to or an ancestor of
  `norm(R) + "/projects"` or of `norm(T)`, or is exactly `norm(T) + "/" + k` for a `k` starting
  with `claude-` — e.g. `R`, `R/projects`, `/private/tmp`, `/tmp`, `/private/tmp/claude-501`,
  `~`, `/`. A root **below** those (e.g. `R/tools/gtm`, `R/projects/<a GTM home's dir>`, the
  session's own scratchpad) is judged by (1) only.
  **Accepted residual (stated):** for a GTM-tagged catch-all dispatch (test (3)), a Bash recursive
  search whose command carries neither `agency` nor `oauth-google-` reaches python only through
  another §4.7 arm; test (3) is inert until probe q in any case. B1 tests, end-to-end through
  `bash_gate.sh` or the path gate, each RED when its clause is removed: a OtherCompanyB-scope `Read`
  of `R/projects/<P_A>/x.jsonl` is denied (clause (1)); a OtherCompanyB-scope `Read` of
  `/private/tmp/claude-<uid>/<P_A>/s/scratchpad/x` is denied (clause (1), temp form); a
  OtherCompany-scope `Grep` with `path` `~/.claude` and a `gtm-analyst` Bash `grep -r x
  ~/.claude/projects` from a CSA cwd outside GTM scope are denied (clause (2)); a OtherCompanyB-scope
  `Read` of `R/projects/<project_dir_name(H)>/t.jsonl` and a `Grep` rooted at `R/tools/gtm` are
  **not** denied by this arm (RED when clause (2) is widened to every root under `R`).
- Every other GTM rule outside GTM scope (e.g. rule a's write-script block in a non-GTM CSA session,
  08_seats_wps.md Appendix C item 24) keeps the ordinary behaviour: deny only when
  `_lib.enforcing(cwd)` is true, else log the would-block.
**Mechanism (binding on B1/B2; `requests/00_global_paths.md` R20).** The committed dispatchers emit a
deny only under `_lib.enforcing` (`pretooluse_bash._finish`, `pretooluse_task.apply_t1`), so the
split above is carried by a flag, never by a second code path: `pretooluse_bash._Block` gains a
keyword field `unconditional: bool = False` (added to its `__slots__` and `__init__`); every
`_Block` a GTM rule listed above as unconditional creates sets it `True`; **every** GTM `_Block` is
built with the required keyword `git_state=False` (verified: `_Block.__init__` requires it), so
`_finish`'s `CSA_ALLOW_GIT_STATE_OPS` escape-hatch branch never applies to a GTM deny (04_hooks.md
§4.2 says the same); `_finish` emits the deny
when `enforcing(where) or block.unconditional` and logs `enforce=<that value>`. **A flag alone is
not enough, because `resolve_block` returns the FIRST block** (verified, `pretooluse_bash.py`
`resolve_block`) and G-B runs after gates 1, 1b and 1c: with `_lib.enforcing(where)` False, a
compound such as `cp x ~/.claude/.gtm_state/tickets/t/y.json; git stash` gets a log-only gate-1
block, `_finish` allows it, and rule c is never evaluated. So `resolve_block` changes too (B2,
`requests/00_global_paths.md` R38, corrected by R41): when an earlier gate returns a block with
`unconditional` False — **whatever `_lib.enforcing(where)` returns** — `resolve_block` still calls
`_gtm_bash_block(command, where, agent_type)`; if that returns a block with `unconditional` True,
**that** block is returned (it wins; the earlier block is written to the same log row as
`shadowed_block`), else the earlier block is returned as today. **That second call can never lose
the earlier block (binding):** the committed `resolve_block` wraps every gate in one `try: … except
Exception: return None, {}`, so an exception raised by `_gtm_bash_block` there would drop the
earlier block too and turn, say, a gate-1 `git stash` deny into an allow. So the call made after an
earlier block is wrapped in **its own** `try/except Exception`: on an exception it logs one
`gate-fault` row (`_lib.log`, naming `_gtm_bash_block` and the exception type) and returns the
earlier block unchanged; the exception never reaches the outer handler. **G-B's position when no
earlier gate blocked (binding):** gates 1, 1b, 1c, then **G-B**, then gate 2 and the rest (3, 3b,
3c, 4, 5, 5b, 6) — before gate 2, so a G-B deny (rule n on a GTM-scope `git commit` pathspec, for
example) returns before gates 3/3b/4 read the index or take any file claim or commit-mutex token
(gate 4's side effects). An exception inside G-B on that path is handled by G-B's own fail mode
(04_hooks.md §4.2 "Fail mode"), never by the outer handler, so gates 2–6 still run. The enforcing case is not exempt:
with `_lib.enforcing(where)` True, gate 1 returns a `git_state=True` block for `git stash; cp x
~/.claude/.gtm_state/…`, and if the hook process's own environment carries the git-state-ops
escape hatch (`_escape_hatch_active`, the `CSA_ALLOW_GIT_STATE_OPS` variable), `_finish`
escape-allows that block — so without this rule the G-B rule c write in the same compound would be
silently allowed. Because the returned block is the unconditional GTM one (built with
`git_state=False`), the escape hatch never applies to it. B1/B2 falsification tests: (1) in a tmp
`HOME` with no enforce marker anywhere and `CSA_ENFORCE` removed, the compound above is denied with reason
`protected-state-write` (RED under plain first-block-wins); (2) in a tmp `HOME` **with** the global
enforce marker present and the escape variable set in the hook process's own environment (set by
the test harness, never inline in a command), the same compound is still denied
`protected-state-write` (RED when the `_gtm_bash_block` call is limited to `not enforcing`); (3)
with `_gtm_bash_block` monkeypatched to raise, `git stash` is still denied by gate 1 (RED under the
committed outer handler alone); (4) a GTM-scope `git commit -F m -- <a pricing-source path>` denied
by rule n leaves the file-claims ledger and the commit-mutex token untouched (RED when G-B runs
after gate 4). The new GTM hooks
that do not go through `_finish` (G-A, G-W, the path gate, gate-gtm) apply the same test in their
own emit step (`deny if unconditional or _lib.enforcing(where)`). Only `CSA_DISABLE_HOOKS=1`, read
first, overrides it. **GTM sessions never run with hooks disabled:** `gtm_session.sh` and
`run_gtm_job.sh` refuse `CSA_DISABLE_HOOKS` set non-empty and not `0` (exit 64,
07_notices_schedules.md §7.2/§7.6), and act.py refuses every `write`/`lead`/`repair`-policy
command (the two §2.3 exceptions to the GTM-session proof included: the holds job and the
operator-marker `resume`/`autonomy`) with exit 3 `hooks_disabled` when the same value is set
in act.py's own environment, so a process tree whose hooks are off cannot mint write tickets or
execute (`requests/00_global_paths.md` R21). **The refusal never applies to a `read`-policy
command** — in particular `pause`, `cancel` and `card-post` (02_act.md §2.3: `read`-policy, "they
run anywhere"): the first two only stop work and the third only asks a question, and plan §20.7
says "cancelling only prevents an action, so it may come from any channel" — including
`gtm_cancel.sh` from an operator terminal where the operator switched hooks off
(`requests/00_global_paths.md` R41). **A lead is never lost to this refusal (plan §6.8
"never lets a lead sit unlogged"):** when `lead-append` refuses `hooks_disabled`, act.py first
writes the raw input to `S/lead_spool/<slug>/` exactly as on the trust-root-failure path (§1.2:
the same stdlib-only writer, slug taken from `--company` by the stdlib regex, exclusive create,
0600, the same hipaa backup/purge rules) and writes one `warn` notice ("lead spooled: hooks
disabled"); the next trusted `lead-append` replays and deletes it (03_schemas.md §3.14). The exit
stays 3 `hooks_disabled` (with `spooled: "<file name>"` in the result JSON), so no chain write
happens with hooks off. A1 test: `CSA_DISABLE_HOOKS=1 lead-append --file l.json` exits 3, leaves
one spool file with the input's bytes and one `warn` notice, and a later trusted `lead-append`
replays it into the chain (RED when the spool write is removed) (`requests/00_global_paths.md`
R38).
B1 test (`requests/00_global_paths.md` R13): in a tmp `HOME` with **no** `~/.claude/.enforce`, no
`.csa-enforce` anywhere and `CSA_ENFORCE` removed from the hook's environment (precedence step (2)
would otherwise make every arm enforce and the test prove nothing), (a) a GTM-scope `Grep` of a `phi_denylist` path is denied, (b) a non-GTM
`cp x <R>/.gtm_state/tickets/…` is denied (rule c), (c) a non-GTM `Write` of a file under `S` is
denied (G-W `machine-written-path`), (d) a non-GTM rule-a command only logs; each of (a)–(c) goes
RED when its arm is routed back through `_lib.enforcing` (i.e. `unconditional` left `False`). A1
test: `CSA_DISABLE_HOOKS=1` in act.py's environment → `propose` exits 3 `hooks_disabled`;
`CSA_DISABLE_HOOKS=0` → not refused. A1 test (the other direction): with `CSA_DISABLE_HOOKS=1` in
act.py's environment, `cancel <a held action>` succeeds (the hold is cancelled) and `pause --system
gbp` writes its pause file; each goes RED when the `hooks_disabled` refusal is widened to
`read`-policy commands.

---

## 1. Paths, environment, test isolation

### 1.1 Runtime root

`R = company.claude_dir()` — env `CLAUDE_DIR` if set (non-empty), made `Path(v).expanduser().resolve()`
(committed; symlinks resolved, e.g. `/var` → `/private/var`), else `Path.home()/.claude` (**not**
resolved). Test fixtures therefore build under a resolved tmp root (pytest's `tmp_path`, resolved).
**`claude_dir()` refuses an Agency result on BOTH branches (DECIDED (wave1c); widened wave1d —
finding 00-6 partial fix; coordinator, Appendix C item 14, `requests/00_global_paths.md` R43).** The
committed `.resolve()` lstats every component, so `CLAUDE_DIR=~/Desktop/OtherApp` (or any alias form)
would stat and then write under Agency before any `test_mode` or `refuse_real_state` check runs;
G-B rule m (an inline assignment in a command naming `tools/gtm/`) is defence in depth only. **The
`HOME`-fallback branch has the identical exposure and is not merely a defence-in-depth gap: a
process whose `HOME` is set to (or under) Agency — e.g. `HOME=<tmp>/Desktop/OtherApp python3
…/act.py …`, or any launcher/subprocess that inherits a mis-set `HOME` — reaches `Path.home()`
(`pwd.getpwuid(os.getuid()).pw_dir` when `HOME` is unset, else the `HOME` value) and resolves `R`
under Agency with no refusal at all today, because the CLAUDE_DIR branch's checks above never run
for an empty/unset `CLAUDE_DIR`.** So `claude_dir()`, when `CLAUDE_DIR` is non-empty,
first computes `v = os.path.expanduser(value)` (text; the same expansion it applies today) and,
**before** the `.resolve()`, raises `CompanyError(f"CLAUDE_DIR agency_home: <reason>")` when `v` is
not absolute (`claude_dir_not_absolute`; a relative value resolves against the cwd) or when, for
`n` in {`norm_text(str(Path(os.environ.get("HOME") or real_home()) / "Desktop" / "Agency"))`,
`norm_text(str(real_agency_root()))`}, `is_under(norm_text(v), n)` (`registry_path_in_agency`) or
`is_ancestor(norm_text(v), n)` (`ancestor_of_agency`) — text only, no stat (`CLAUDE_DIR` set is
always test mode, so the first `n` is `A`); **before** those compares, `norm_text(v) ==
gtm_env.VOLFS_SENTINEL` raises with reason `kernel_path_alias` (§0.1 arm (e)). **When `CLAUDE_DIR` is
empty/unset (the `else` branch), `claude_dir()` applies a text-only refusal to the real candidate
result before returning it (DECIDED (wave1e), finding wave1d-B1: the wave1d form checked `HOME`
itself against `n`, and `is_ancestor(norm_text(HOME), norm_text(HOME + "/Desktop/OtherApp"))` is true
for every home, so it raised `ancestor_of_agency` on every production call — the candidate, not the
home, is what must stay out of Agency):** `h = os.environ.get("HOME") or real_home()` (text, no
expansion needed — `HOME` is never `~`-prefixed), `c = norm_text(h + "/.claude")` (the text of the
`Path.home()/.claude` the branch returns), and `r = norm_text(str(real_agency_root()))`; `c ==
gtm_env.VOLFS_SENTINEL` raises `kernel_path_alias`, `is_under(c, r)` raises
`registry_path_in_agency` and `is_ancestor(c, r)` raises `ancestor_of_agency`, each as
`CompanyError(f"HOME agency_home: <reason>")`, **before** `Path.home()/.claude` is ever constructed
or returned (no `.resolve()` is reached on this branch — `Path.home()/.claude` is returned
unresolved — so the check is purely textual and stats nothing). Only `real_agency_root()` is the
`n` here: `HOME/Desktop/OtherApp` is by construction never under or an ancestor of `HOME/.claude`, so
comparing against it would prove nothing, and a mis-set `HOME` is exactly the case where the
`HOME`-derived Agency root is not the real one. Every Wave-2 tool
maps either raise to exit 3 `claude_dir_in_agency`; a hook that gets it applies its own §4 fail mode
(04_hooks.md). Oracle test (coordinator, both branches): `CLAUDE_DIR=<tmp A>/x`,
`CLAUDE_DIR=/.nofollow<tmp A>/x`, `CLAUDE_DIR=/.vol/<dev>/<ino of tmp A>/x` and `CLAUDE_DIR=<tmp
HOME>/Desktop` each make `claude_dir()` raise with an empty oracle record (RED when the check is
removed or moved after the `.resolve()`); **and, with `CLAUDE_DIR` unset and `real_home()`
monkeypatched to the tmp home (so `real_agency_root()` is `<tmp A>`)**, `HOME=<tmp A>` (candidate
`<tmp A>/.claude`) makes `claude_dir()` raise `HOME agency_home: registry_path_in_agency` with an
empty oracle record (RED when the HOME-branch check is removed, or when `Path.home()/.claude` is
returned before it runs); **control (RED under the wave1d tautology):** `HOME` equal to
`real_home()` (the monkeypatched tmp home), and separately `HOME` unset, each return `<tmp
home>/.claude` without raising. (The wave1d expectation that `HOME=<tmp HOME>/Desktop` raises is
withdrawn: its candidate `<tmp HOME>/Desktop/.claude` is neither under nor an ancestor of Agency.)
**Every**
new GTM component, hooks included, resolves `R` by calling `company.claude_dir()` at call time
(never at import time). `S = company.gtm_state_dir()` = `R/.gtm_state`. `R` is the **state** root;
it is never the trust root in production (below).

**Import rule (DECIDED HERE).** The **code** root and the **state** root are different things. A
hook in `hooks/` makes `tools/gtm` importable by inserting, at call time,
`str(Path(os.path.abspath(__file__)).parent.parent / "tools" / "gtm")` at `sys.path[0]` — first
removing every existing `sys.path` entry whose `os.path.normpath` equals it, so the entry is at
index 0 after the call whether or not it was already present (an "only when absent" insert would
leave it behind an earlier resolved entry) —
**unresolved** (never `.resolve()`/`realpath`), so a module reached through a symlink imports its
siblings from the tree it was reached through, not from the link's target. It is inserted
at `sys.path[0]` (never appended) so a same-named module in site-packages can never shadow a GTM
module such as `gtm_env` or `approval_sig` (the §0.2 stub concern). Because that also puts
`tools/gtm` ahead of `hooks/`, **no module basename may exist in both** `tools/gtm/` (incl. the
top level of `gtmlib/` and `connectors/` as packages) and `hooks/`: B2 test
`test_no_module_name_collision` lists both directories' `*.py` stems and **package names** and fails
on any overlap (RED when a `hooks/company.py` is added in the test's tmp copy). **A package** is an
immediate subdirectory that contains an `__init__.py`; `tests`, `__pycache__` and the stem
`__init__` are excluded explicitly on both sides (`tools/gtm/tests/` is a package and
`hooks/tests/` is not, so without the exclusion the test would depend on that accident;
`tools/gtm/contracts/` holds no `__init__.py` and is not a package). **Baseline (checked
2026-09-28):** `tools/gtm/` stems `activity_log`, `backup_state`, `company`, `exit_contract`,
`harvest_tool_trail` (plus `__init__`, excluded); no package besides `tests`; no overlap with
`hooks/*.py`. A unit test (B2) builds its own symlinked hook in a tmp dir, imports it in process
and asserts `company.__file__` is under the tmp `tools/gtm` (RED when the rule uses `.resolve()`).
Then it imports `company`, `system_names`, `gtm_env` etc. as top-level modules and uses
`company.claude_dir()` for every state path.

**Scripts are different: Python itself resolves them (checked on this machine, Python 3.13.14).**
A file run as a script (`python3 <path>/X.py`, or a hook entry point run by its command line)
gets `sys.path[0]` = the directory of the script's **realpath**, so a script reached through a
symlink imports its siblings from the **link target's** directory — for a symlinked tmp tree, the
real `~/.claude/tools/gtm` or `~/.claude/hooks`. No in-process import rule can undo that for a
subprocess. **Therefore (binding on B2 and every WP whose tests run tools or hooks from a tmp
tree): the tmp tree COPIES, never symlinks, code.** B2's end-to-end tests copy every `*.py` under
`tools/gtm/` (top level, `gtmlib/`, `connectors/`, recursively, excluding `tests/`) into `<tmp
CLAUDE_DIR>/tools/gtm/` and every `*.py` plus `bash_gate.sh` under `hooks/` (patched or not) into
`<tmp CLAUDE_DIR>/hooks/`, as regular files (`shutil.copy2`, never `os.symlink`/`copytree(...,
symlinks=True)`); trust-root fixtures such as `approver_pubkey.pem` (§1.5 item 5) are real files
committed there. The files are small, and copying removes the whole class (a resolved script path
is then inside the tmp tree). B2 tests: run one tool that imports `company` at module level
(`python3 -v <tmp>/tools/gtm/backup_state.py --help`) and one hook entry point that imports `gtm_hooklib` (the path-gate entry point, 04_hooks.md
§4.4, with a fixture payload on stdin; no hook file is edited for the test) as **subprocesses**
from the tmp tree, and assert from `-v`'s stderr import trace that every file loaded for the
modules `company`, `gtm_env`, `system_names` and `gtm_hooklib` lies under the tmp tree and none
under the real `~/.claude` (RED when the fixture symlinks the modules instead of copying them);
plus a guard test that no path under `<tmp CLAUDE_DIR>/tools/gtm` or `<tmp CLAUDE_DIR>/hooks` is a
symlink.

The rule "never at import
time" binds new code. **Committed import-time exceptions** (not retrofitted by any WP; tests that
depend on them set `HOME` before import, i.e. run them in a subprocess, or monkeypatch the
constant): `harvest_tool_trail.DEFAULT_GLOBS_TEMPLATE` (defined but referenced nowhere, so
harmless), each pack's `legacy_workdirs` (read by `harvest_tool_trail._legacy_workdirs`; the old hardcoded legacy-dir constant was removed 2026-09-28) (load-bearing, §0.1 oracle),
the `hooks/_lib.py` module constants, and **four resolved `sys.path` inserts** that break the
unresolved-import rule above (anchored by statement, header "The baseline"): the module-level
`sys.path.insert(0, str(Path(__file__).resolve().parent))` of `activity_log.py`,
`harvest_tool_trail.py` and `backup_state.py`, and `company._pack_system_set`'s lazy `this_dir =
str(Path(__file__).resolve().parent)` / `sys.path.insert(0, this_dir)` when absent.
**Consequence:** anywhere those modules are reached through a symlink, importing any of them (or
calling `_pack_system_set`) before `company`, `gtm_env` and `system_names` are loaded puts the
link target's directory at `sys.path[0]`, so the next import may load the wrong copy. The
copy-not-symlink rule above removes this from B2's tree; the inserts are still fixed for every
other deployment. **Fix, both parts binding:** (1) the Appendix C item 14 coordinator change (lands
before B2) replaces the four resolved inserts with the unresolved form and the
remove-then-insert-at-0 rule above (`str(Path(os.path.abspath(__file__)).parent)`),
`requests/00_global_paths.md` R41; (2) B2's in-process harness imports `company`, `gtm_env` and
`system_names` **first**, before any hook or any of the three modules, and the in-process
symlinked-hook unit test asserts that ordering (`sys.modules` holds all three, each `__file__`
under the tmp `tools/gtm`, before the first hook import) as well as `company.__file__` after it;
RED when the harness imports `activity_log` first while a resolved insert is still present.
Separately, the committed `harvest_tool_trail._matching_project_dirs` reads
`Path.home() / ".claude" / "projects"` at **call** time and ignores `CLAUDE_DIR` (tests set `HOME`;
there is no constant to monkeypatch); its Appendix C item 14 rewrite (§0.1 F9, R16) switches it to
`company.claude_dir() / "projects"`.

**Real root and test mode (DECIDED HERE; closes the inline-override bypass).** Every env override
in §1.4 can be set inline by any agent's Bash (`CLAUDE_DIR=/tmp/x python3 …/act.py …`), and
`company.claude_dir()` honors `CLAUDE_DIR` (company.py `claude_dir`). So a new standalone,
stdlib-only module **`tools/gtm/gtm_env.py`** (A1; hooks, `approval_sig`, `ai_budget`, connectors
and `gtmlib` import it — `requests/00_global_paths.md` R9/R21) defines:
- `real_home() -> str` = `pwd.getpwuid(os.getuid()).pw_dir`, `real_root() -> Path` =
  `Path(real_home()) / ".claude"`, and `real_agency_root() -> Path` = `Path(real_home()) /
  "Desktop" / "Agency"` — **never** from `HOME` or `CLAUDE_DIR` (§0.1 "The Agency root" uses it
  for `A` outside test mode). `gtm_env` imports only the stdlib, never another `tools/gtm` module,
  because `approval_sig` imports it before the trust check (05_approver.md §5.5 step 0;
  `requests/05_approver.md` R29(a)).
- `same_root(a, b) -> bool` — the one root compare: `os.path.samefile(a, b)` when both exist (the
  stat is safe only because every caller pre-checks by text: `R` comes from `claude_dir()`, which
  refuses an Agency result on **both** its `CLAUDE_DIR` branch (before its `.resolve()`) and its
  `HOME`-fallback branch (before `Path.home()/.claude` is returned) — §1.1 "Runtime root"; `real_root()` is
  `real_home()/.claude`; `test_mode`'s `h` gets the Agency text pre-check below, which
  `canon_aliases` extends to every alias form), else `norm_text(a) ==
  norm_text(b)` (§0.1 "The one path-compare implementation": normpath + casefold + firmlink strip,
  **no** `~` expansion and no test-mode dependence — so `same_root`, `test_mode` and `norm` never
  call each other in a loop; callers pass already-expanded paths). APFS is case-insensitive:
  `CLAUDE_DIR=~/.CLAUDE` names the real root. `norm_text`, `norm`, `is_under` and `agency_root`
  live in this module (§0.1).
- `real_expand(s) -> str` — `~`/`~/…` expanded against `real_home()` (never `HOME`), then
  `os.path.normpath`; used for every root string read from a **real** registry. Any other leading
  `~` (the `~user` form, `~x`, `~+`) raises `gtm_env.TildeUserForm(ValueError)` and is never
  expanded (§0.1 "The one path-compare implementation"). Unit test: `real_expand("~<user>/x")`
  raises; `real_expand("~")` and `real_expand("~/x")` do not. `real_expand` is for **compare-only**
  uses (`norm`, `refuse_real_state`, `phi-denylist add --path`).
- `real_expand_raw(s) -> str` — the same `~`/`~/…` expansion against `real_home()` and the same
  `TildeUserForm` refusal, **without** `os.path.normpath` (DECIDED (wave1c)); used only where `..`
  must reach a kernel-order walk, i.e. `register`'s step (3) outside test mode (§0.1). Unit test:
  `real_expand_raw("~/a/../b") == real_home() + "/a/../b"` while `real_expand` of the same is
  `real_home() + "/b"`.
- `test_mode(environ) -> tuple[bool, list[str]]` → `(True, reasons)` when any of: `CLAUDE_DIR`
  non-empty, `GTM_TEST` non-empty, `GTM_FAKE_NOW` non-empty, or, with `h = environ.get("HOME") or
  real_home()`, `not same_root(h, real_home())` — an `h` for which `is_under(norm_text(h),
  norm_text(str(real_agency_root())))` holds is a mismatch without any stat — (so `HOME=""` counts as unset, and a trailing `/`,
  a case variant or a symlink of the passwd home is **not** a mismatch — otherwise a production
  session would silently fall into test mode and every live connector would refuse
  `test_mode_no_live`); reasons are the variable names, in the order `CLAUDE_DIR`, `GTM_TEST`,
  `GTM_FAKE_NOW`, `HOME`. **An empty-string value counts as unset everywhere** (matching
  `company.claude_dir()`'s `if override:`), including the launcher refusal in §1.4. Unit cases:
  `HOME=""` → not test mode; `HOME=pw_dir + "/"` → not test mode; `HOME` = a case variant of
  `pw_dir` → not test mode; `HOME=<tmp>` → `(True, ["HOME"])`.
- `now(environ) -> datetime` — the one clock (`gtmlib` clock and hooks clock both call it); it
  **always returns an aware UTC datetime**: `datetime.now(timezone.utc)`, or, when honored,
  `datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)`. Company-local times
  are `now(...).astimezone(ZoneInfo(pack["timezone"]))`. `GTM_FAKE_NOW` is honored **only when
  `GTM_TEST=1`** (hence only in test mode) and is parsed only then; otherwise it is ignored (still
  counted for test mode). An unparseable honored value raises **`gtm_env.BadFakeNow(ValueError)`**
  (its message names the value); every tool maps it to exit 2 `usage` with code `bad_fake_now`;
  every hook catches it and calls `datetime.now(timezone.utc)` instead (fail-open for availability
  — a hook never loosens a rule because of it, since only a fake clock could move a window). Unit
  tests: `now({}).tzinfo is not None`; `now({"GTM_TEST": "1", "GTM_FAKE_NOW":
  "2030-01-01T00:00:00Z"}).tzinfo is not None`; `now({"GTM_TEST": "1", "GTM_FAKE_NOW": "x"})` raises
  `BadFakeNow`; `now({"GTM_FAKE_NOW": "x"})` (no `GTM_TEST=1`) returns the real clock.
- `refuse_real_state(R: Path, H: Path | None, environ: Mapping[str, str] = os.environ) -> None` —
  the **one choke point** of consequence 3 below; test mode is judged by `test_mode(environ)` on the
  **given** mapping (act.py and every in-process caller pass the same mapping they gave
  `test_mode`, so the P2 recipes' in-process environ is the one judged); raises
  `gtm_env.RealStateRefused` (every CLI maps it to exit 3 `test_mode_real_state`) and is a no-op
  outside test mode. A1 test: with `os.environ` clean and `environ={"GTM_TEST": "1"}` passed, a
  write to a real-registry home is refused (RED when the function reads `os.environ` instead).

**`gtm_env` exports — the one table (binding; A1; `requests/00_global_paths.md` R42 asks 02_act.md
§2.1 to cite this table instead of restating it).** `gtm_env` exports exactly these names and no
others; the bullets above and §0.1 give their semantics. Every function that takes `environ`
judges test mode with `test_mode(environ)` and reads `HOME` from `environ` (empty = unset, then
`real_home()`), never from `os.environ` or `Path.home()` when a mapping is passed. None of them
stats a path under either Agency root.

| Name | Exact signature | Raises |
|---|---|---|
| `strip_firmlink` | `strip_firmlink(t: str) -> str` | never |
| `canon_aliases` | `canon_aliases(t: str) -> str` — the §0.1 loop (leading `/` run, `/.nofollow`, `/.resolve/<digits>`, firmlink) on casefolded text, plus the terminal `/.vol` arm (e): `t == "/.vol"` or `t.startswith("/.vol/")` returns `VOLFS_SENTINEL` | never |
| `VOLFS_SENTINEL` | `VOLFS_SENTINEL: str` — the unrepresentable sentinel text (contains NUL, e.g. `"\x00agency-alias-vol\x00"`) `canon_aliases`/`norm_text`/`norm` return for any `/.vol` path; every consumer treats it as an unconditional Agency match (§0.1 arm (e)) | — |
| `norm_text` | `norm_text(s: str) -> str` | never |
| `norm` | `norm(s: str, *, test: bool) -> str` | `TildeUserForm` (only when `test` is False, from `real_expand`) |
| `is_under` | `is_under(a: str, b: str) -> bool` | never |
| `is_ancestor` | `is_ancestor(a: str, b: str) -> bool` | never |
| `TildeUserForm` | `class TildeUserForm(ValueError)` | — |
| `real_home` | `real_home() -> str` | `KeyError` only when the uid has no passwd entry (unsupported machine; propagates) |
| `real_root` | `real_root() -> Path` | as `real_home` |
| `real_agency_root` | `real_agency_root() -> Path` | as `real_home` |
| `agency_root` | `agency_root(environ: Mapping[str, str] = os.environ) -> Path` | as `real_home` |
| `phi1_root` | `phi1_root(environ: Mapping[str, str] = os.environ) -> Path` — `Path(real_home()) / "Desktop" / "OtherCompany Files"` outside test mode, `Path(environ.get("HOME") or real_home()) / "Desktop" / "OtherCompany Files"` in test mode (the `A` rule, §0.1) | as `real_home` |
| `same_root` | `same_root(a: str, b: str) -> bool` | never (an `OSError` from `os.path.samefile` falls back to the text compare) |
| `real_expand` | `real_expand(s: str) -> str` | `TildeUserForm` |
| `real_expand_raw` | `real_expand_raw(s: str) -> str` — as `real_expand`, no `normpath` | `TildeUserForm` |
| `test_mode` | `test_mode(environ: Mapping[str, str] = os.environ) -> tuple[bool, list[str]]` | never |
| `now` | `now(environ: Mapping[str, str] = os.environ) -> datetime` (aware UTC) | `BadFakeNow` |
| `BadFakeNow` | `class BadFakeNow(ValueError)` | — |
| `refuse_real_state` | `refuse_real_state(R: Path, H: Path \| None, environ: Mapping[str, str] = os.environ) -> None` | `RealStateRefused` (incl. a present-but-unreadable real registry file) |
| `RealStateRefused` | `class RealStateRefused(Exception)` | — |
| `gtm_tmp_root` | `gtm_tmp_root() -> str` = `os.path.realpath(os.environ.get("TMPDIR") or "/tmp")`, with `"/tmp"` (realpath'd) used instead when that value is not an existing directory — the literal body each entry point's pre-import block carries as `_gtm_tmp_root()` (05_approver.md §5.5 step 0; `requests/05_approver.md` R80 (d)); every isolated-subprocess pycache prefix is created **directly** under it (04_hooks.md §4 "Isolated subprocesses"; DECIDED (wave1e)) | never (no stat beyond `os.path.isdir`; never under an Agency root) |
| `git_show_head` | `git_show_head(root: str \| Path, relpath: str, *, timeout: float = 5.0) -> bytes \| None` — the one hardened committed read (04_hooks.md §4, the paragraph defining `gtm_env.git_show_head`; `requests/04_hooks.md` R30): `/usr/bin/git --no-replace-objects -c core.fsmonitor=false -c core.untrackedCache=false -C <root> show HEAD:./<relpath>` with 05_approver.md §5.5's scrubbed environment | never (`None` on a non-zero exit, a timeout or an `OSError`) |
| `TRUSTED_PYTHON` | `TRUSTED_PYTHON: str` — the literal value is decided in 05_approver.md §5.5 "Interpreter pin" (`"/opt/homebrew/opt/python@3.13/bin/python3.13"` today) and lives here | — |

`gtm_env.__all__` lists exactly the table's names. A1 tests: `set(gtm_env.__all__)` equals the
table's name column and each name resolves on the module (RED when a name is added or dropped on
one side);
`agency_root({"HOME": <tmp>, "GTM_TEST": "1"})` with `os.environ["HOME"]` pointing elsewhere returns
`<tmp>/Desktop/OtherApp` (RED when it reads `Path.home()`).
Consequences, binding on every WP:
1. **Trust root = `real_root()` outside test mode.** `approval_sig.trust_root_ok`, every
   `git -C <root> show HEAD:tools/gtm/approver_pubkey.pem` (05_approver.md §5.5) and the dispatch-time
   trust-root check (02_act.md §2.3) use `real_root()` when not in test mode; outside test mode
   `same_root(R, real_root())` must hold or the command refuses exit 3 `root_mismatch` (distinct
   from 02_act.md's exit 11, which is an `approval_sig.TRUST_KINDS` failure). In test mode they use
   `R` (tests `git init` the tmp `CLAUDE_DIR`, §1.5 item 5).
2. **Test mode never reaches a live platform or secret.** In test mode
   `connector_dispatch.credential_getter`, the GSM fetch (06_connectors.md §6.3), and every live
   connector transport refuse exit 3 `test_mode_no_live` before any network or GSM call; only fixture
   transports (06_connectors.md §6.5) run. Tests are unaffected — they already use fixtures.
3. **Test mode never writes real state.** In test mode, `gtm_env.refuse_real_state(R, H)` refuses
   when `same_root(R, real_root())`, or when a home `H` is given and is equal to or under any `root`
   string listed in `real_root()/knowledge/gtm_company_registry.json` or
   `real_root()/knowledge/repo_registry.json`. Each listed root `r` is compared twice: as text
   (`norm(H)` vs `norm(real_expand(r))`, casefolded) and, only when `real_expand(r)` is **not**
   equal to or under **either** Agency root — `real_agency_root()` **or** the `HOME`-derived test
   `A` (§0.1), each by the text `norm` compare — by `os.path.realpath` (`H` is already resolved by
   `resolve_home`); an Agency root is never stat'd. (Comparing against the tmp `A` alone would let
   the real registry's `~/Desktop/OtherApp`, expanded by `real_expand` to the real path, reach
   `realpath` on every test-mode write — invisible to the oracle, whose `A` is the tmp one.) A1
   test: fake `HOME`, a monkeypatched real registry listing `~/Desktop/OtherApp` with `real_home()` →
   a tmp "real" home, and `os.path.realpath` wrapped to record its calls → it is never called with
   that root; RED when the compare goes back to `A` only. A real registry file that is **missing** lists
   no roots; one that is present but unreadable → refuse. Reading these two real files is the **one
   sanctioned exception** to §1.5 item 3 (read-only, never written). **Every** GTM state writer calls
   it before its first write, and new writers must too: through the shared helpers —
   `gtmlib.store.append` (chain and anchor), the shared atomic-write helper, the pause-file writer,
   `gtmlib.leads`, and the `approvals_verify` nonce-ledger writer — and, for writers that do not use
   those, at their entry point: act.py's `write`/`lead`/`repair`-policy dispatch, `cycle.py`,
   `notices.py` (and `gtm_hooklib.write_notice_file`), `gtm_lists.py`, `metrics.py`,
   `perf_report.py`, `autonomy_ladder.py`, `scoreboard.py`, `outside_actor.py`, `experiments.py`,
   `transcript_index.py`, `mission_record.py`, `backup_state.py --restore`, and every connector's
   idempotency-ledger writer. So a fake root or fake clock whose registry points at a real company
   home cannot append to that home's chain, and a case-variant `CLAUDE_DIR` cannot write real `S`.
4. `gtm_session.sh`/`run_gtm_job.sh` refuse to start in test mode caused by `CLAUDE_DIR`, `GTM_TEST`
   or `GTM_FAKE_NOW` (§1.4); a `HOME` mismatch alone does not stop them (launcher tests run that
   way, §1.5 item 9), but everything they start is then in test mode by (2)/(3).
P2 falsification tests (A1 for 1/3, A2 for the approval path, L for 2): (a) a tmp root holding an
agent-generated key and a validly signed approval, selected with `CLAUDE_DIR=<tmp>` against a
registry pointing at a tmp home, runs `execute` → no connector transport is called (fixture spy
records zero live calls) and exit 3 `test_mode_no_live`; RED when (2) is removed. **Recipe for (b)
and (d)** (so the test proves the `GTM_TEST`/`GTM_FAKE_NOW` arm **alone**, never the `HOME` arm,
and never reaches the real `~/.claude`, §1.5 item 3): `HOME=<tmp>/home` with `CLAUDE_DIR` unset (so
`R = <tmp>/home/.claude`, whose `gtm_company_registry.json` registers slug `x` at the tmp home);
`gtm_env.real_home` monkeypatched → `<tmp>/home` (the `HOME` arm is off); `gtm_env.real_root`
monkeypatched → `<tmp>/real/.claude`, whose registry names that same tmp home; and, before the
command, `assert gtm_env.test_mode(environ) == (True, ["GTM_TEST", "GTM_FAKE_NOW"])`. (b)
`run-holds --company x` in process with that environ plus `GTM_TEST=1
GTM_FAKE_NOW=2030-01-01T00:00:00Z`, the tmp home holding a pending hold → exit 3
`test_mode_real_state` (not 13: `x` resolves in `R`), the hold is not released and the log is
unchanged; RED when (3) is removed; (c) outside test mode, `R ≠ real_root()` (both monkeypatched) →
`root_mismatch`; (d) (G) the same recipe, `autonomy_ladder.py promote` with `GTM_TEST=1
GTM_FAKE_NOW=<8 days later>`, the tmp home holding a demoted system and its breaker pause → exit 3
`test_mode_real_state`, the pause file stays; RED when the `refuse_real_state` call is
removed; (e) (A1) fake `HOME` plus a fake registry naming the tmp "real" home by its **absolute**
path, while the monkeypatched real registry lists it as `~/<rel>` under a monkeypatched
`real_home()` → `test_mode_real_state`; RED when `real_expand` is replaced by `os.path.expanduser`;
(f) (M) a case-variant `CLAUDE_DIR` naming the tmp "real" root → `gtm_lists.py` exits 3
`test_mode_real_state`; RED when `same_root` is replaced by a case-sensitive `normpath` compare.

### 1.2 `~/.claude/.gtm_state/` layout (`S`, gitignored)

```
S/
  identity_index.json              company.py index            (exists; {slug: [values], "other_businesses": [...]})
  account_id_index.json            company.py index            (exists; {slug: [platform ids]})
  other_businesses.json            gtm_lists.py (WP-M), add-only  {"<label>": [values] | "<value>"}  (shape company.py reads)
  phi_denylist.json                gtm_lists.py (WP-M), add-only  03_schemas.md §3.20
  othercompany_listing.json          gtm_lists.py phi1-listing --root      §1.2 "Listing shapes" (names only, never contents; 03_schemas.md §3.20 asked to adopt it, R42)
  phi_toplevel_listing.json        gtm_lists.py phi1-listing --top-level §1.2 "Listing shapes" (immediate child names only; never descends)
  phi_toplevel_classification.json gtm_lists.py phi-classify          §1.2 "Top-level PHI classification is a precondition" (binds the classification to the listing's sha256)
  othercompany_read_allowlist.json   gtm_lists.py phi1-allowlist  03_schemas.md §3.20 (trust-architect-reviewed folders)
  unattributed_trail.jsonl         harvest_tool_trail.py       (exists)
  transcript_index.json            WP-G transcript_index.py    03_schemas.md §3.16
  transcript_index_oi.jsonl        WP-G transcript_index.py    03_schemas.md §3.16   (appended under transcript_index.lock)
  transcript_index.lock            WP-G transcript_index.py    03_schemas.md §3.16   guards the index + _oi file
  agent_results.jsonl              SubagentStop hook (B1, gtm_ticket_release)   08_seats_wps.md §8.1, 04_hooks.md §4.5   maker-checker ground truth: {"ts","agent_id","agent_type","session_id","result_sha256"} (+ agent_results.lock, 5 s)
  isolation_hits.jsonl             G-A, act.py, secret_sink    03_schemas.md §3.21   (+ isolation_hits.lock)
  browser_hosts/<session_id>.json  G-A                         {"<server>": {"host", "ts"}} — one file per session (single writer; atomic replace; no cross-session lock needed, I17)
  dispatch_tags.jsonl              gate-gtm (admission)        04_hooks.md §4.6   (+ dispatch_tags.lock)
  chain_anchors/<slug>.json        gtmlib.store                §0.3   {"seq","line_sha256","ts"} exact form in §0.3
  trust_edit_allow.json            GTMApprover --sign-trust-edit, via the operator's `gtm_approve.sh trust-edit` (Touch ID)   05_approver.md §5.3/§5.4, 04_hooks.md §4.3   single-use, signed, nonce-bound trust-file edit marker (a plain file is never the control)
  trust_edit_allow.lock            G-W                         04_hooks.md §4.3   held while the marker is checked + deleted
  operator_ok/<command>.<slug>.<target>.json   GTMApprover --sign-operator-ok, via the operator's `operator_ok.sh` → `gtm_approve.sh operator-ok` (Touch ID)   §1.4 "Operator authority", 02_act.md §2.3 "Operator marker"   single-use, signed, nonce-bound go-ahead for one `resume`/`autonomy`/`pause` invocation (keyed by target)
  operator_ok.lock                 gtmlib.session (A1)         02_act.md §2.3   held while a marker is validated + deleted
  lists.lock                       gtm_lists.py                §1.2
  PAUSE.trust                      the daily trust check only (`approval_sig.py --trust-check` / `approval_sig.trust_check`; never act.py dispatch)   global: all `$` refused (05_approver.md §5.6 "Who writes PAUSE.trust", 02_act.md §2.9)
  approver_pubkey.pem              GTMApprover --export-pubkey 05_approver.md §5.6   the app's default export (0600); NOT the trust anchor
  approver_fingerprint.json        GTMApprover --export-pubkey 05_approver.md §5.6   export record compared by the daily check (`pubkey_vs_export`); NOT the trust anchor
  approver_selftest.json           GTMApprover --self-test     05_approver.md §5.7
  approver_inbox/show.<request_id> gtm_approve.sh              05_approver.md §5.4 (consumed + deleted by the app)
  approval_nonces.jsonl            gtmlib.approvals_verify     03_schemas.md §3.9   (+ approval_nonces.lock)
  approval_requests/<slug>/<request_id>.json    act.py        03_schemas.md §3.7
  approvals/<slug>/<request_id>.json            GTMApprover   03_schemas.md §3.8
  cancels/<slug>/<action_id>                    any channel   03_schemas.md §3.11   (+ cancels/<slug>/_all.<UTCts>)
  cancels/<action_id>, cancels/_all[.<slug>]    operator by hand (flat, plan §20.7)   §1.2 "Cancels: two accepted layouts"
  notices/<slug>/<notice_id>.json               any writer    07_notices_schedules.md §7.1   (reserved slug dir `runtime` for runtime-wide)
  notices/<slug>/.lock                          any writer    07_notices_schedules.md §7.1   held across the dedupe check + create
  notices/pushed.jsonl                          notices.py, gtm_hooklib.write_notice_file   07_notices_schedules.md §7.1   (+ notices/pushed.lock)
  tickets/<slug>/<ticket_id>.json               act.py, G-A, ticket release   03_schemas.md §3.6
  tickets/<slug>/.lock
  leases/<slug>.lock                            gtm_session.sh (lockf)        07_notices_schedules.md §7.6
  leases/<slug>.json                            gtm_session.sh holder info, written by the locked child only    07_notices_schedules.md §7.6
  reports/                                      perf_report.py --all          03_schemas.md §3.19
  lead_spool/<slug>/<UTCts>_<8 hex>.json        act.py lead-append on a trust-root failure (stdlib-only, 0600; exclusive create, §0.2)   02_act.md §2.3 step 0, 05_approver.md §5.5   raw lead input; replayed and deleted by the next trusted `lead-append` (03_schemas.md §3.14)
  pycache/                                      hook entry points (`pycache_prefix`, 0700)   05_approver.md §5.5 step 0   bytecode cache only
```

**Tracked trust files under `R/tools/gtm/` (not under `S`; `requests/05_approver.md` R22).**
`approver_pubkey.pem` (the committed verification key, read only as `HEAD:tools/gtm/approver_pubkey.pem`),
**`approver_fingerprint.txt` — the one fingerprint anchor** plan §20.8's daily check compares the
HEAD key against (05_approver.md §5.6 "Anchor"; `S/approver_fingerprint.json` is the app's own
export record and is **never** an anchor, because the app writes it into `S`), and
`approver_pubkeys/` (retired keys with `index.json` validity windows, 05_approver.md §5.6 "Rotation
and loss"). All three are written only by the operator's reviewed HIGH-tier commit in the install or
rotation order of 05_approver.md §5.6, are TRUST_PATHS (05_approver.md §5.5), and are recovered from
git, never from a backup.

**Backup and purge of the `S` paths above that are not per-company state (DECIDED HERE).**
- `S/lead_spool/<slug>/` — the spool file lives under the company slug taken from act.py's own
  `--company` argument (validated against the §0.3 grammar with a stdlib regex before any
  `tools/gtm` import; an absent or invalid value → `S/lead_spool/_unknown/`), so it can be
  attributed without parsing lead data (`requests/00_global_paths.md` R28 asks 02_act.md §2.3 and
  05_approver.md §5.5 to use this path). **Non-hipaa packs:** in that company's `backup_set()` (a
  lead must not be lost); never purged by a GTM tool (the next trusted `lead-append` replays and
  deletes it). **Packs with `regulated` ∋ `hipaa`:** excluded from every
  `backup_set()` (the raw input can carry prospective-patient details, plan §20.4/§20.13), and `act.py
  purge-untrusted` deletes files older than its `--older-than-days` (default 30, the §20.4 window),
  writing one `warn` notice per deleted, unreplayed spool file so a lost lead is visible.
  **`_unknown` (DECIDED (wave1c), a narrowing — header item (viii); the former "never purged by
  age" loosening is withdrawn, because plan §20 supersedes §5/§6.8 where they conflict and §20.4
  covers OtherCompany forms):** an unattributable file may hold prospective-patient details, so it
  is treated like a hipaa slug's spool: excluded from every `backup_set()` and every runtime backup
  tgz, and `act.py purge-untrusted` deletes it once older than `--older-than-days` (default 30, the
  §20.4 window), writing one `warn` notice per deleted, unreplayed file. From 24 hours onward every
  daily run (07_notices_schedules.md §7.5) and every `purge-untrusted` writes one **urgent** notice
  per `_unknown` file (runtime-wide, slug `runtime`, 07_notices_schedules.md §7.1; deduplicated per
  file name) asking a session to re-run `act.py lead-append --company <slug> --file <that file>`,
  so a session has about 29 days to replay it. Before the window, a file is deleted only after a
  successful replay of that file into a company chain, or by an explicit `act.py purge-untrusted
  --include-unknown` (itself writing one `warn` notice per deleted file). A1 tests: a
  OtherCompany-fixture spool file older than 30 days is purged with a notice and is absent from the
  backup set (RED when the purge or exclusion is removed); a OtherCompanyB one is kept and backed up;
  a 31-day-old `_unknown` file is purged by `purge-untrusted` with one `warn` notice (RED when it
  survives); a 25-hour-old `_unknown` file survives `purge-untrusted`, raises one urgent notice, is
  deleted by `purge-untrusted --include-unknown`, and a second one is deleted after `lead-append
  --company other-company --file <it>` replays it (`requests/00_global_paths.md` R43 withdraws R41's
  request that 02_act.md §2.4 `purge-untrusted` stop deleting unattributable spool files by age).
- `S/othercompany_listing.json` — **excluded from every `backup_set()` and from every runtime backup
  tgz** (its file names come from the OtherCompany folders and can carry patient names, §1.2 WP-M
  text, plan §20.4/§20.13); it is regenerable at any time by `gtm_lists.py phi1-listing`, so nothing
  is lost. Never purged by a GTM tool (it is replaced whole by the next listing).
- `S/phi_denylist.json` — **machine-level**: in no company's `backup_set()` (its `path` entries
  name files found to hold patient information, plan §20.4 "add the path", so a OtherCompany tgz
  must not carry them either), and **no other copy is kept** (DECIDED HERE: a machine-level backup
  outside the company tgzs was considered and not chosen — it would be a second place holding
  PHI-bearing path names, and the file is re-derivable). Never purged. **Loss is never silent and
  never fails open (DECIDED HERE; plan §20.3 prevention-first):** see "`phi_denylist.json` missing or
  unparseable" below. **Recovery is an agent procedure, not an operator task** (CSA `CLAUDE.md`:
  never assign the operator a task an agent can do): a session re-runs the listings
  (`gtm_lists.py phi1-listing --top-level ~/Desktop` plus any operator-named folder — the P1
  precondition below — and, once OtherCompany is registered, `phi1-listing --root …`), dispatches
  trust-architect on the fresh top-level listing, and re-adds entries with
  `gtm_lists.py phi-classify` (review-bound) and `phi-denylist add` (the seeded Open Dental and
  Agency app hosts, 03_schemas.md §3.20 "Seeding"). While the file is missing the listing commands
  still run (`gtm_lists.py` is not a GTM-scope read); the `--root` walk then prunes nothing by
  denylist, which is acceptable because a listing records names only and is excluded from every
  backup. Only a host value that no public fact or earlier record supplies
  goes to the operator, as 03_schemas.md §3.20 already states.
- `S/othercompany_read_allowlist.json` — machine-level, in no company's `backup_set()`; it is only
  valid against the current listing's sha256 (§1.2 `phi1-allowlist`), which is itself not backed
  up, so a restored copy could never be re-bound; it is regenerated from a fresh trust-architect
  review. Never purged.
- `S/phi_toplevel_listing.json` — excluded exactly like `othercompany_listing.json` (its names come
  from `~/Desktop` and other operator-named folders and can carry patient names); regenerable by
  `gtm_lists.py phi1-listing --top-level`; replaced whole by the next listing, never purged.
- `S/phi_toplevel_classification.json` — machine-level, in no company's `backup_set()` (it binds a
  listing that is itself not backed up, so a restored copy could never match); regenerated by the
  next `phi-classify`; never purged.
  WP-M/A1 tests: `backup_set("othercompany")` and `backup_set("other-company")` contain none of these
  five files and no runtime backup archive built by `backup_state.py` contains
  `othercompany_listing.json` or `phi_toplevel_listing.json` (RED when the exclusion is removed).
- `S/pycache/` — WITHDRAWN (wave1e): no process uses a fixed bytecode prefix any more (R41 (b)); every isolated process gets a fresh `gtm_pyc_` prefix under `gtm_tmp_root()`.
- `S/approver_pubkey.pem`, `S/approver_fingerprint.json`, `S/approver_selftest.json`,
  `S/approver_inbox/`, `S/trust_edit_allow.json`, `S/operator_ok/`, `S/PAUSE.trust` — machine-level,
  in no company's `backup_set()`, never purged by a GTM tool (single-use markers are consumed by their
  checker; `PAUSE.trust` is removed only by the operator, by hand).

`knowledge/gtm_company_registry.json` lives at `R/knowledge/gtm_company_registry.json` (not under
`S`). Its `companies` map is written only by `company.py register|unregister` (existing), which
preserve every other top-level key. Its `repo_registry_slugs` key (§0.1) has **no tool writer**
(the committed `register` refuses repo-registry slugs by design): it is created by the coordinator
by hand in the 08_seats_wps.md Appendix C item 14 change (`["exampleapp"]`) and changed
afterwards only by the operator, by hand. When the file or the key is absent, `gtm_slugs()` returns only
GTM-registry slugs (none when the file is absent), and `validate --all` and `company.py index`
refuse loudly (`repo_registry_slugs_missing`, §0.1 "Registry inputs" (2)). **"Only by the operator"
is prose-only today, stated:** no rule named in this contract set yet denies a GTM session a
Write/Edit or shell write of `R/knowledge/gtm_company_registry.json` or
`R/knowledge/repo_registry.json` (G-W's classes and G-B rule c cover `S` and `R/tools/gtm`).
`requests/00_global_paths.md` R42 asks 04_hooks.md §4.2/§4.3 to add both files to the path gate's
and G-W's Write/Edit deny and to rule c's write-and-removal targets and rule n's pathspec check, in
GTM scope and for every GTM seat, unconditionally (§0.4), with reason `gtm-registry-write`; until
that lands the operator-only rule is enforced by code review and `validate --all`'s refusals only.

**Updating the operator-maintained lists (DECIDED HERE).** Once G-W and G-B are live, nothing can
Write/Edit or shell-redirect into `S`. WP-M therefore owns `tools/gtm/gtm_lists.py`, which writes in
process (atomic, under `S/lists.lock`). Semantics **per subcommand** (no tool path ever loosens a
gate; loosening is the operator's, by hand in an editor):
- **Every add (both denylists below) re-runs `company.write_identity_index()` under the same
  `S/lists.lock`**, because G-A and harvest read `identity_index.json`, not the list files: without
  it a new denylist entry would have no effect until `company.py index` ran. **Adding a value already
  present is a no-op, exit 0** (the result JSON says `"unchanged": true`); the index is still
  re-written. **Order (binding; the one API is §0.1 "Registry inputs" (2)):** (1)
  `company.require_repo_registry_slugs()` — on `CompanyError("repo_registry_slugs_missing")` exit 3
  `repo_registry_slugs_missing`, nothing written, neither the list file nor either index file
  changes; (2) the list file's atomic replace; (3) `company.write_identity_index()`, which reads the
  new list from disk. Any other `CompanyError`/`OSError` at step (3) exits 1 `reindex_failed` with
  the list file already holding the new value (add-only, so the list is never looser than before)
  and the indexes as they were; the next add or `company.py index` brings them level.
- `gtm_lists.py other-business add --label L --value V` — **add-only** (a denylist: an entry only
  makes gates stricter). When label `L` currently holds a **string** (company.py accepts `"<value>"`),
  the add converts it to a list; every written list is sorted and deduplicated.
- `gtm_lists.py phi-denylist add (--path P | --host H [--agency-app] | --host-suffix S | --url U)
  --why W [--applies-to <slug> ...]` and `gtm_lists.py agency-gsm-project add <project id> --why W`
  — **add-only** (denylists). This is the **complete** grammar; 03_schemas.md §3.20's schema is
  the storage it writes. `--path P` is `gtm_env.real_expand`ed (`~` against the passwd home;
  a `~user` form → exit 3 `path_tilde_user`, never expanded)
  and must then be absolute, else exit 3 `path_not_absolute`. `--applies-to` is accepted **only**
  together with `--host … --agency-app` (03_schemas.md §3.20: `applies_to` only on `agency_app:
  true` host entries); with `--host` alone, `--host-suffix`, `--url` or `--path` → exit 3
  `phi_denylist_scope_invalid` (03's refusal code), nothing written. **Storage mapping (exact):**
  `--path` → a string appended to `paths[]` in the expanded, `~`-free form; `--host` →
  `{"host": <lowercased>}` appended to `hosts[]`, plus `"agency_app": true` with `--agency-app` and
  `"applies_to": [<slugs>]` with `--applies-to`; `--host-suffix` → `{"suffix": <lowercased, leading
  `.` added when absent>}` appended to `host_suffixes[]`; `--url` → `add_phi_url` (03_schemas.md
  §3.20; `url_prefixes[]`, normalized there; a non-`https` URL, a query or a fragment is refused
  `phi_denylist_scope_invalid`); `agency-gsm-project add` → the id appended to
  `agency_gsm_projects[]`. **Every** add also appends `{"entry": <the stored value as text>, "why":
  W, "source": "gtm_lists <subcommand>"}` to `notes[]` and sets `updated_at` (§0.3 machine
  timestamp); `why` is never stored anywhere else. An `--applies-to` slug not in
  `company.gtm_slugs()` → exit 13. A
  `--path` entry **wins inside an allowlisted folder** (G-B rule j and the path gate check the
  denylist first), so tightening OtherCompany access never needs an allowlist edit.
- **Listing shapes (DECIDED HERE; 03_schemas.md §3.20 is asked to carry these exact shapes and drop
  its single-`root`, `os.walk` form, `requests/00_global_paths.md` R42).** Both files are written
  atomically under `S/lists.lock`, 0600:
  ```json
  {"schema": "gtm.phi1_listing.v2", "listed_at": "2026-09-27T15:04:05Z",
   "roots": ["/Users/<u>/Desktop/OtherCompany Files"],
   "entries": [{"path": "<abs>", "kind": "dir"}, {"path": "<abs>", "kind": "file", "size": 1234},
               {"path": "<abs>", "kind": "symlink"}, {"path": "<abs>", "kind": "dir", "denylisted": true}]}
  ```
  ```json
  {"schema": "gtm.phi_toplevel_listing.v1", "listed_at": "2026-09-27T15:04:05Z",
   "roots": ["/Users/<u>/Desktop"],
   "entries": [{"path": "<abs>", "kind": "file"}, {"path": "<abs>", "kind": "dir", "covered": true}]}
  ```
  `entries` sorted by `path`; `kind` ∈ `dir`/`file`/`symlink`; `size` only on a `file` entry of
  the `--root` listing, from `entry.stat(follow_symlinks=False).st_size` (never on a symlink);
  `denylisted` and `covered` appear only when true. The listing's sha256 is the hex sha256 of the
  file's bytes as written, which `phi1-listing` prints in its result JSON (`listing_sha256`).
- `gtm_lists.py phi1-listing --root "<OtherCompany Files path>" [--root <dir> ...]` — **replaces**
  `othercompany_listing.json` (a fresh listing; names only). `--root` may be repeated (each root is
  walked the same way; a root equal to, under or an ancestor of `A` or `real_agency_root()` by the
  §0.1 text compare → exit 3 `agency_root`, before any stat). It walks recursively with
  `os.scandir` (never `os.walk`) and **never follows a symlink**: a symlink entry is recorded as
  `{path, kind: "symlink"}` without stat'ing or reading its target (a link could lead into Agency
  or into a denylisted folder). It never descends
  into a folder equal to or under a `phi_denylist.json` `path` entry — containment is the §0.1
  casefolded `norm` text compare, never `realpath` — and records that folder as `{path, kind: "dir",
  denylisted: true}`; its children are neither listed nor stat'd (their file names can carry patient
  names, plan §7.6). WP-M tests: a denylisted folder's children are absent from the listing (RED when
  the pruning is removed); a symlink to a folder holding files is recorded as `kind: "symlink"` and
  its target is never opened (RED when `follow_symlinks` is left on); an `other-business add`
  followed at once by a read of `identity_index.json`'s `other_businesses` sees the value (RED when
  the index re-write is removed); a label holding a string becomes a sorted list; a duplicate add exits 0 with the file unchanged; `--path ~/x` is stored expanded;
  `--path x` → exit 3; `--path P --applies-to othercompany` and `--host h --applies-to othercompany`
  (no `--agency-app`) → exit 3 `phi_denylist_scope_invalid`, file unchanged (RED when
  `--applies-to` is accepted without `--agency-app`); `--host h --agency-app --applies-to
  othercompany` stores `{"host": "h", "agency_app": true, "applies_to": ["othercompany"]}` and one
  `notes[]` entry; `--url https://x.example/p?q=1` stores `https://x.example/p`;
  `agency-gsm-project add p1 --why w` appends `p1` to `agency_gsm_projects`.
- `gtm_lists.py phi1-listing --top-level <dir> [--top-level <dir> ...]` — **replaces**
  `phi_toplevel_listing.json` with the **immediate child names** of each `<dir>` and nothing else
  (plan §20.3: "any export, report or file derived from [Open Dental], and any folder holding such
  files" can sit anywhere, e.g. at the top level of `~/Desktop`; checked 2026-09-28 by name only,
  no file opened: several reporting exports and a credentialing folder sit there — whether any holds PHI is UNVERIFIED). One
  `os.scandir(<dir>)`; for each entry, **before any `DirEntry` method**, the text path
  `os.path.join(<dir>, entry.name)` is compared with `A` and `real_agency_root()` by the §0.1
  `norm`/`is_under`/`is_ancestor` compare, and an entry equal to, under or an ancestor of either is
  **skipped and not recorded** (so `--top-level ~/Desktop` never stats `A`); every other entry is
  recorded as `{path, kind}` with `kind` ∈ `file`/`dir`/`symlink` from `entry.is_symlink()` /
  `entry.is_dir(follow_symlinks=False)` (a symlink's target is never read); it **never descends**
  into any entry and never opens one. Entries equal to or under `phi1_root()` (default-denied to
  every GTM session by 03_schemas.md §3.20's OtherCompany read allowlist) and names already covered
  by a `phi_denylist.json` `path` entry are recorded with `covered: true`. **P1 runs it — before the
  first GTM session of any company, not at P1b** — on `~/Desktop` and on every other folder the
  operator has named as holding Open Dental or OtherCompany material (WP-M's intake question,
  08_seats_wps.md WP-M, asked at P1), then runs `phi-classify` (below). The `--root "<OtherCompany
  Files path>"` listing and `phi1-allowlist` stay at P1b (they only loosen OtherCompany scope).
- `gtm_lists.py phi-classify --listing-sha256 <hex> --review-agent <trust-architect agent_id>` —
  the **review-bound denylist feed** for the top-level listing (the `--root` listing needs none:
  everything under `phi1_root()` outside an allowlisted folder is already default-deny).
  trust-architect is dispatched with the listing path (it Reads the listing only, never a listed
  file) and must end with one ```` ```gtm-result ```` block whose `reviews[]` holds exactly one
  entry `{action_id: "phi1_toplevel:<sha256>", after_digest: "sha256:<sha256>", lane: "hipaa",
  verdict: "pass", lines: [{check: "entry:<absolute path>", result: "pass"|"denylist"|"unknown",
  note}]}` (the 03_schemas.md §3.20 `phi1_listing` review shape with these three values; `verdict:
  "pass"` means the review completed). `gtm_lists.py` verifies it with
  `gtm_result.verify_reviewer(agent_id, {"trust-architect"}, "phi1_toplevel:<sha256>",
  "sha256:<sha256>")` (08_seats_wps.md §8.1) and requires `--listing-sha256` to equal the sha256 of
  the **current** `phi_toplevel_listing.json`'s bytes, else exit 3 `listing_sha_mismatch`; an
  unverifiable review → exit 3 `review_unverified`. Every listed entry not marked `covered` is
  classified by its line; a line naming a path not in the listing is ignored and counted in the
  result JSON's `ignored_lines`. **Two refusals, both checked before anything is written (DECIDED
  (wave1c): a `path` entry applies to every company, wins over every allowlist and is removable only
  by hand, so one incomplete review must never PHI-deny a GTM home — the listing names
  `ExampleApp`, `OtherCompanyB` and later `OtherApp_GTM`/`OtherCompany_GTM` — and recovery must
  stay an agent re-dispatch, never an operator task):** (a) an entry with **no** line → exit 3
  `review_incomplete` (`error.data` names the entries; nothing written; the session re-dispatches
  trust-architect) — never read as `unknown`; (b) an entry whose normed text path (§0.1 `norm`,
  no stat) is equal to or an ancestor of any `company.gtm_slugs()` home's registry root, of `R` or
  of `real_root()` (`is_under`/`is_ancestor`) must carry an explicit `pass` line, else exit 3
  `review_incomplete` naming it, nothing written; when its line was `denylist`, one **urgent**
  runtime notice (slug `runtime`, 07_notices_schedules.md §7.1, deduplicated per listing sha256 and
  path) names the entry so a session re-reviews it. Only explicit `denylist` **and `unknown`**
  lines add entries: each is added to `phi_denylist.json` as a `path` entry through `add_phi_path` (its
  `notes[]` `why`: `"phi-classify <listing sha256> <result>"`, `source`: `"phi-classify
  trust-architect <agent_id>"`) — **add-only**, so a later `pass` never removes an entry (removal
  stays the operator's, by hand); `pass` entries add nothing. Last, under the same lock, it writes
  `S/phi_toplevel_classification.json` atomically, exactly `{"schema":
  "gtm.phi_toplevel_classification.v1", "listing_sha256": "<hex>", "classified_at": "<UTC Z>",
  "review_agent_id": "<id>", "counts": {"pass": n, "denylist": n, "unknown": n}}` — only after
  every denylist add succeeded. Same lock, re-index order and exit codes as `phi-denylist add`.
  WP-M tests, each RED when its refusal is removed: a review omitting the line for the CSA-home
  fixture entry → exit 3 `review_incomplete`, `phi_denylist.json` and the classification file
  byte-identical (or absent) before and after; a `denylist` line on a fixture `Desktop/OtherCompanyB`
  (ancestor of a registered home) → exit 3 `review_incomplete`, nothing written, one urgent notice;
  an explicit `pass` on it plus `denylist` on another entry → that other entry added.
- **Top-level PHI classification is a precondition (DECIDED HERE; header item (vi); plan §20.3
  bans Open Dental exports for all GTM sessions and seats, not only OtherCompany scope).**
  `gtm_hooklib.phi_toplevel_classified() -> bool` is True iff `S/phi_toplevel_listing.json` and
  `S/phi_toplevel_classification.json` are both readable, the latter has exactly the shape above,
  and its `listing_sha256` equals the sha256 of the listing's current bytes (re-listing therefore
  makes the classification stale until `phi-classify` runs again — by design, fail closed).
  (1) **Launchers:** `gtm_session.sh` and `run_gtm_job.sh` refuse to start, exit 64, stderr
  `phi_toplevel_unclassified` when it is False, and exit 64 `phi_denylist_unreadable` when
  `phi_denylist.json` is absent, unreadable or schema-invalid — for **every** company, hipaa pack
  registered or not (07_notices_schedules.md §7.2/§7.6, requested by R42). (2) **Hooks:** while it
  is False, the path gate and G-B rule j deny, unconditionally (§0.4), every GTM-scope and every
  GTM-seat read target (Read/Grep/Glob, Bash path operands with rule j's operand grammar) outside
  the **fail-closed read roots** below, reason `phi-toplevel-unclassified`, in every GTM scope,
  whether or not a hipaa pack is registered — so a GTM seat dispatched outside a launched session,
  or a scope claimed by env var, is covered too. **Accepted residual (stated):** a file placed at a
  listed top level **after** the classification is not in the listing; it is caught only by the
  hipaa default-deny (OtherCompany scope) or by the next re-listing (which stales the
  classification). WP-M/B1 tests, each RED when its clause is removed or scoped back to hipaa packs:
  with **no** hipaa pack registered and no classification file, a OtherCompanyB-scope `Read` of a
  Desktop-level fixture file is denied `phi-toplevel-unclassified` and `gtm_session.sh other-company`
  exits 64 `phi_toplevel_unclassified`; after a verified `phi-classify` of the current listing the
  same `Read` of a `pass` entry is allowed; re-running `phi1-listing --top-level` with a changed
  Desktop makes it denied again (stale sha).
- **The fail-closed read roots (one definition; DECIDED HERE; `requests/00_global_paths.md` R42 asks
  03_schemas.md §3.20 "Hook readers" item (2) to use it instead of its own `H`, `R/tools/gtm`,
  `R/knowledge/marketing_kb` list).** `gtm_hooklib.fail_closed_read_roots(payload, environ) ->
  list[str]` (normed text, no stat) = `H_eff` ∪ the **runtime read roots** ∪ the **own-session
  roots**, where:
  - `H_eff` = the session company's `H` in GTM scope; for a GTM seat called **outside** GTM scope,
    the `H` of the company named in the `[gtm company=<slug> …]` dispatch tag bound to its
    `agent_id` (§0.4 test (3)) when a binding exists and `<slug>` is in `gtm_slugs()`, else **no**
    home;
  - the **runtime read roots** = exactly `R/tools/gtm`, `R/knowledge`, `R/skills/gtm` and the file
    `R/plans/gtm_autonomous_department_plan.md` — never `R` as a whole, never `S` (GTM tools read
    `S` in process, where no hook applies), never `R/projects` as a whole, never `R/.enforcement`
    (it logs command text from every session on the machine, Agency's included);
  - the **own-session roots** = under `R/projects/`: every `R/projects/<c>` where
    `project_dirs.matches_project_dir_prefix(c, project_dirs.project_dir_name(H_eff))` holds (the
    home's dir and its `-` worktree/subfolder dirs; none when `H_eff` is none), plus
    `R/projects/<c0>` where `c0` is the first component after `R/projects/` of the payload's
    `transcript_path` — each only when `project_dirs.is_agency_project_dir(c)` is False; and the
    payload's own `scratchpad_dir` (04_hooks.md §4.7 "Fixed payload keys") when present, has the
    documented form `/private/tmp/claude-<uid>/<c>/<session_id>/scratchpad` with `<session_id>`
    equal to the payload's `session_id` and `is_agency_project_dir(c)` False. Never `/private/tmp`,
    `/tmp` or `tempfile.gettempdir()` as a whole: they are shared by every session on the machine,
    so they hold other sessions' scratchpads, Agency's included. GTM tools keep their own scratch
    under `G/drafts/` (in `H`), so no GTM-owned temp directory is defined.
- **OtherCompany read scope (DECIDED HERE; plan §20.3 prevention-first).** Enumeration can miss a
  folder nobody named, so a GTM scope whose pack has `regulated` ∋ `hipaa` is **default-deny**
  outside its allowed roots: the path gate (Read/Grep/Glob) and G-B rule j (every path operand of a
  Bash command, the same operand grammar as rule j) deny (`phi-scope-outside-allowed`,
  unconditional in GTM scope, §0.4) any target whose `canon` is not equal to or under one of: the
  **fail-closed read roots** above (with `H_eff` = the company home `H`); or a
  `othercompany_read_allowlist.json` folder (still subject to `phi_denylist` `path` entries, which
  win). The runtime root `R` as a whole and the system temp roots are **not** allowed roots: `R/projects/`
  holds every session's transcripts (Agency's own included, §0.1 F9, which §20.9 forbids reading),
  and `/private/tmp` holds every session's scratchpad; plan §20.3 records that Agency's sessions do
  legitimate Open Dental work, so both can hold Open Dental-derived PHI. Default deny therefore no
  longer depends on the one folder name §20.2 used. WP-M/B1 tests (each RED when its clause is
  removed): `phi1-listing --top-level <tmp HOME>/Desktop` with a fixture `Desktop/OtherApp/`
  and `Desktop/sub/deep.pdf` records `Desktop/sub` as `dir` and records nothing under it, and the
  no-Agency-touch oracle records nothing (RED when the name compare runs after `entry.is_dir()`);
  a Desktop-level file classified `denylist` by a verified review is added as a `path` entry and a
  OtherCompany GTM `Read` of it is denied (RED when the entry is removed from the file); an `unknown`
  entry is added too (RED when only `denylist` is added); a OtherCompany GTM `Read` of
  `<tmp HOME>/Documents/x.pdf` (in no listing) is denied `phi-scope-outside-allowed` while a
  OtherCompanyB GTM `Read` of it is not; a `Read` of a file in `H` is allowed; a OtherCompany-scope
  `Grep` whose `path` is `~/.claude` is denied (RED when `R` is an allowed root); a OtherCompany-scope
  `Read` of another session's scratchpad file `/private/tmp/claude-<uid>/<other>/<s2>/scratchpad/x`
  is denied (RED when the temp roots are allowed) while a `Read` of a file in the payload's own
  `scratchpad_dir` is allowed; a OtherCompany-scope `Read` of `R/projects/<c of another, non-GTM
  session>/t.jsonl` is denied (RED when `R/projects` as a whole is allowed).
- **`phi_denylist.json` missing or unparseable (DECIDED HERE; header item (v); supersedes
  03_schemas.md §3.20's "absent file read as empty for other packs").** `gtm_hooklib.phi_denylist()`
  treats a missing, unreadable, unparseable or schema-invalid file as **unreadable** (never as an
  empty list) for **every** GTM scope and GTM seat, whether or not a hipaa pack is registered
  (the launchers already refuse to start while it is, above). Then, unconditionally (§0.4):
  (1) the path gate and G-B rule j deny every GTM-scope and GTM-seat read target outside the
  fail-closed read roots (`phi-denylist-unreadable`) — a Desktop path entry could have named any
  other place; (2) **G-A** restricts `browser_navigate` and every ticketed call exactly as
  03_schemas.md §3.20 "Hook readers" item (1) states (allowed only to the pack's identity
  allowlist and runbook hosts), since the Open Dental hosts cannot be checked; (3) **G-B** mirrors
  G-A for shell network access: a GTM-scope or GTM-seat Bash command naming any network host —
  every token rule j's own host check extracts, each normalized with `gtm_hooklib.host_of`
  (04_hooks.md §4), the one extraction, never a second parser — whose host is not in that same
  G-A allowed set is denied
  `phi-denylist-unreadable`; (4) the connector host guards already fail closed (03_schemas.md
  §3.20). For a GTM seat without a session company, `H_eff` and the G-A host set come from its
  bound dispatch tag's company, else there is no home and no allowed host. The daily run
  (07_notices_schedules.md §7.5) raises one **urgent** runtime notice `phi_denylist_missing`
  (deduplicated) naming the recovery procedure above. Tests (WP-M/B1, each RED when its clause is
  removed or scoped back to hipaa packs): with **no** hipaa pack registered, delete the file → a
  OtherCompanyB-scope `Read` of a Desktop fixture path is denied `phi-denylist-unreadable`, a
  OtherCompanyB-scope `curl https://fixture-opendental.example/x` is denied (clause (3)) while `curl
  https://<a OtherCompanyB pack domain>/` is allowed, and the daily run raises `phi_denylist_missing`;
  a `gtm-analyst` outside GTM scope with **no** dispatch-tag binding may `Read` a file under
  `R/tools/gtm` but not one under `<tmp HOME>/Desktop/OtherCompanyB/GTM` (RED when a tagless seat
  gets any home); with a binding to `other-company` it may read under that home.
- `gtm_lists.py phi1-allowlist --listing-sha256 <hex> --review-agent <trust-architect agent_id>` —
  an **allow**list, so adding a folder **loosens** the PHI gate: it is **never** add-only or merged.
  It **replaces the whole file** with exactly the `pass` folders of one trust-architect review that
  `gtm_result.verify_reviewer` verifies (03_schemas.md §3.20) and that is bound to the **current**
  `othercompany_listing.json`'s sha256 (`--listing-sha256` must equal it, else exit 3
  `listing_sha_mismatch`). No folder is carried over from a previous allowlist file; a folder cleared
  under an older listing is gone unless the new review passes it again. WP-M test: an allowlist
  holding folder F from listing L1, then a verified review of L2 that does not pass F → F is absent
  (RED when the write is changed to a merge).
Exit codes (IMP-17): 0 ok, 1 internal (incl. `reindex_failed`), 2 usage, 3 refused (bad value —
e.g. `path_not_absolute`, `path_tilde_user`, `phi_denylist_scope_invalid`,
`repo_registry_slugs_missing`, `listing_sha_mismatch`, `review_incomplete` — or
`review_unverified`), 12 timeout (30 s)
on `S/lists.lock`, 13 company resolution (an `--applies-to` slug that is not in
`company.gtm_slugs()`). It prints exactly one JSON object on stdout in act.py's envelope (02_act.md
§2.3 "Output (every subcommand)"), with `command` = the `gtm_lists.py` subcommand and `company` =
null unless the subcommand names one.

**DECIDED HERE:** approval requests, approvals, cancels and notices are **per-company subdirectories**
(the plan draws them flat) so a company's backup/restore can include them by name — this closes the
gap `company.py backup_set()`'s docstring records. The nonce ledger stays one global file (every
line carries `company`).

**Cancels: two accepted layouts (DECIDED HERE; plan §20.7 documents the flat hand-made path, which
must never be silently ignored).** Every **writer** (`act.py cancel`, `gtm_cancel.sh`,
GTMApprover, the release re-check) writes the per-company form `S/cancels/<slug>/<action_id>` (and
`S/cancels/<slug>/_all.<UTCts>`). **Ingest** (03_schemas.md §3.11, A2) additionally honors, for
company `X`:
- a flat `S/cancels/<action_id>` whose name matches `^act_(?P<slug>[a-z][a-z0-9-]{1,31})_\d{8}_\d{4}$`
  with `slug == X` — ingested exactly like `S/cancels/X/<action_id>`, recorded as
  `who: "hand_made_file"` whatever its content (an empty file is the expected hand-made form);
- a flat `S/cancels/_all.<slug>` with `slug == X` — like `S/cancels/X/_all.<UTCts>`;
- a flat `S/cancels/_all` (no suffix), or `_all.<anything not a registered slug>` — cancels every
  pending hold of **every** company (cancelling only stops work, so the ambiguous form fails safe);
- any other flat file in `S/cancels/` → a `warn` notice "unrecognized cancel marker <name>" on every
  ingest until the operator removes it (never silently ignored).
**Flat `_all*` markers are keyed by file identity, not name.** Each company records its own
`cancel_all_ingested {marker: "flat:<name>:<st_ino>:<st_mtime_ns>", cancelled}` once per such key
(from one `os.stat` of the marker at ingest), so holds placed after that company ingested a given
marker are unaffected, while re-creating or re-`touch`ing the same name is a **new** marker that
cancels every hold pending at that moment. Flat markers are never deleted by ingest (the per-company
form's lifecycle, 03_schemas.md §3.11, applies to both); `GTM_Operator.html` lists every flat
`_all*` marker present with the line "remove this file when you no longer need it". The exact
hand-made cancel path for each hold, `~/.claude/.gtm_state/cancels/<action_id>` (the plan's flat
form), is shown on `GTM_Operator.html` and in the hold notice's body (07_notices_schedules.md §7.1,
`requests/00_global_paths.md` R17). A2 tests: an empty flat `S/cancels/act_x_<D>_0003` cancels
pending hold `act_x_<D>_0003` with `who: "hand_made_file"` (RED when flat ingest is removed); a flat
`_all` cancels holds in two companies; ingest `_all`, place a new hold, `touch` `_all` again (new
mtime) → the new hold is cancelled (RED when the key is the name alone).

### 1.3 Per-home layout

`H = company.resolve_home(slug)`, `G = H/.claude/gtm`, `ST = G/state`. Paths below marked *(paths.x)*
come from the pack's `paths` block (home-relative) and must always be resolved from it, never assumed.

```
H/.claude/gtm/
  company.json                 tracked   (schema: company_schema.json)
  metrics.json                 tracked   (paths.metrics)            03_schemas.md §3.18
  review_lanes.local.json      tracked, optional                    03_schemas.md §3.5
  connectors.json              tracked, secret-free                 06_connectors.md §6.3   (DECIDED HERE)
  mcp.json                     tracked, secret-free                 07_notices_schedules.md §7.6
  plans/ (paths.plans_dir), feature_inventory/ (paths.feature_inventory_dir), runbooks.local/
  state/                       gitignored (ST)
    actions.jsonl              act.py only, hash-chained            03_schemas.md §3.1
    actions.lock
    lead_fallback.jsonl        act.py lead-append under PAUSE.chain 03_schemas.md §3.14
    lead_fallback.replayed-<UTCts>.jsonl
    actions.broken-<UTCts>.jsonl   chain-repair rotation            02_act.md §2.4
    cycles/<cycle_id>.json     cycle.py                             03_schemas.md §3.12
    collectors/<run_id>/<collector>.json   act.py read-run          07_notices_schedules.md §7.4
    review_briefs/<action_id>.json         act.py status --review-brief   08_seats_wps.md §8.4
    patches/<action_id>.patch              act.py propose --patch (A1; website_static only)   02_act.md §2.4/§2.8, 03_schemas.md §3.2 — the exact reviewed patch; written once at propose, never rewritten (a changed patch is a new action via --supersedes)
    untrusted/<untrusted_id>.{txt,json}    act.py (regulated only)  03_schemas.md §3.15 (quoted text; hipaa inbox-class snapshots and collector output); excluded from backup_set()
    cards_posted.jsonl (+ cards_posted.lock)       act.py card-post         02_act.md §2.6 (card posting record for the authorship scan)
    autonomy_state.json (+ autonomy_state.lock)    act.py breakers, autonomy_ladder.py   03_schemas.md §3.17
    session_spend.jsonl (+ session_spend.lock)   perf_report.py record-session (called by gtm_session.sh)   03_schemas.md §3.19
    outside_actor/<run_id>.json            outside_actor.py reconcile   03_schemas.md §3.23
    connector_idem/<system>.jsonl (+ <system>.lock)   connectors       06_connectors.md §6.2
    reports/                   perf_report.py, scoreboard.py report
    inbox.jsonl (+ inbox.lock)             notices.py write_notice(task=True) / resolve_notice, local_jsonl packs only   07_notices_schedules.md §7.1
    experiments.jsonl (+ experiments.lock) experiments.py
    pending_commit.txt (+ pending_commit.lock)   one line per tracked home file a GTM tool edited: `<UTC ts>\t<home-relative path>\t<writer>`, appended by `act.py card-post` (A1) and `metrics.py render` (F) (plan §3.2; read by the weekly prompt, 07_notices_schedules.md §7.5)
    .isolation_offset          act.py
    PAUSE  PAUSE.<system>  PAUSE.<system>@<brand>  PAUSE.budget  PAUSE.chain   03_schemas.md §3.10
    activity_log/  scoreboard.csv  snapshots/   (defaults; real location = paths.*)
H/.claude/gtm/drafts/          gitignored (08_seats_wps.md Appendix C item 17); session-written proposal/lead JSON and card bodies for `--file` (07_notices_schedules.md §7.6); NOT in backup_set(); hipaa rule below
H/.playwright-mcp/             @playwright/mcp output dir; gitignored; purged (02_act.md §2.4 purge-untrusted)
H/.claude/oversight/manifest.json         operator_input.path (card archive, 02_act.md §2.6)
```

**Protection and backup of `ST` (binding).** Everything under `ST` — `patches/` included — is a
protected path: G-B rule c denies shell writes to it and G-W denies Write/Edit (04_hooks.md
§4.2/§4.3). Those gates are **friction**, not the control: rule c has known shell-write gaps
(split-literal `python3 -c`, heredoc interpreters, `git apply`; §1.4 and 04_hooks.md §4.2 "Known
shell-write reach"). What makes a swapped `website_static` patch fail is the FID-04 binding of
02_act.md §2.4: `after.patch_sha256` and `after.post_image` are fixed at `propose` and bound by the
digest every review signs off on; every later read of `ST/patches/<action_id>.patch` re-hashes it
and refuses `patch_mismatch` (02_act.md §2.4 `propose`, A1 test "a stored patch with one byte
changed after `propose` → `authorize` and `status --review-brief` both refuse `patch_mismatch`"),
and `complete --commit` requires the commit's changed-path set to **equal** `after.paths` (no path
added, none dropped — so a partial commit of a reviewed patch, e.g. one that keeps a claim change
but drops its disclaimer file, is refused) **and** every path's blob to equal
`after.post_image[path]`, else `patch_mismatch` (02_act.md §2.4 `complete`, the one definition),
so a swapped or partial patch cannot complete. It is written
only in-process by the GTM tools listed in the tree above (act.py, `cycle.py`, `perf_report.py`,
`outside_actor.py`, the connectors' idempotency ledgers, `metrics.py`, `autonomy_ladder.py`,
`scoreboard.py`, `experiments.py`, and `notices.py` for `inbox.jsonl`), never by shell, Write or
Edit (G-B rule c, G-W). `company.backup_set()` includes all of `ST` (committed: `home/.claude/gtm/state`) **except
the exclusions below**, so `patches/`, `review_briefs/` and the rest are backed up with the chain.
Every backup exclusion, with its source: `ST/untrusted/**` (plan §20.4 "excluded from backups";
08_seats_wps.md Appendix C item 5), `H/.playwright-mcp/**` and `ST/lead_fallback.replayed-*.jsonl`
(Appendix C item 5), and `G/drafts/**` (session scratch; for hipaa packs it can hold
prospective-patient details) — each excluded explicitly even if a `paths.*` entry would otherwise
sweep it in (`requests/00_global_paths.md` R18). **The exclusion API (DECIDED HERE;
`requests/00_global_paths.md` R42 → 08_seats_wps.md Appendix C item 7).** `company.backup_set()`
returns **root** paths and `backup_state.py`'s `tar.add` recurses into them, so a subpath is
excluded only by a filter: `company.backup_excludes(slug: str, pack: dict) -> list[str]` returns
home-relative patterns — exactly `.claude/gtm/state/untrusted`, `.playwright-mcp`,
`.claude/gtm/state/lead_fallback.replayed-*.jsonl` and `.claude/gtm/drafts` (for every pack; the
hipaa rules add nothing here because the hipaa-only exclusions are `S` paths that are simply not
in `backup_set()`). `backup_state.py` builds **one** `filter=` callable, passed to every
`tar.add`, that returns `None` for a member whose home-relative name `n` satisfies, for some
pattern `p`, `n == p`, `n.startswith(p + "/")` or `fnmatch.fnmatchcase(n, p)`, **and** for the two
IMP-08 snapshot arcnames (§0.3); every other member passes unchanged. A1/coordinator tests: an
archive of a fixture home holds nothing under `.claude/gtm/state/untrusted/` or
`.claude/gtm/drafts/` and no `lead_fallback.replayed-*` file, while `patches/` and
`review_briefs/` are present (RED when the filter is dropped from one `tar.add` call), and the log
appears exactly once.

**`drafts/` for `regulated: ["hipaa"]` packs (DECIDED HERE; plan §20.4, §20.13).** Lead rows, replies
and card bodies written to `drafts/` for `--file` inputs can carry prospective-patient details, and
`purge-untrusted` today removes only `drafts/restore_check/*` (02_act.md §2.4). For a hipaa pack:
(1) `act.py propose --file`, `lead-append --file` and `card-post --file` **delete the input file**
after it is consumed — on success and on every refusal after the file was read — when
`os.path.realpath(file)` is under `os.path.realpath(G / "drafts") + os.sep` (A1; a raw-text prefix
such as `G/drafts/../company.json`, or a symlink in `drafts/` pointing elsewhere, is never deleted).
**`lead-append` deletes its input only once the lead is durably recorded (DECIDED (wave1c); plan
§5/§6.8 "never lets a lead sit unlogged", which §20.4 does not contradict here;
`requests/00_global_paths.md` R43):** durable = a chain line, a `lead_fallback.jsonl` line under
`PAUSE.chain`, or a `S/lead_spool/<slug>/` file. On success those hold it; on `hooks_disabled` the
spool is written first (§0.4). On **any other** refusal after the file was read (exit 12 lock
timeout on `ST/actions.lock`, exit 3 `id_space_exhausted`, and every other post-read refusal),
act.py first writes the raw input bytes to `S/lead_spool/<slug>/` with the same stdlib-only writer
(slug from `--company` by the stdlib regex, `_unknown` otherwise; exclusive create; 0600; the same
hipaa backup exclusion and 30-day purge, §1.2), adds `spooled: "<file name>"` to the result JSON
(the exit code is the refusal's own), and **only then** deletes the draft; if that spool write
fails, the draft is **kept** and one urgent notice names it. `propose --file` and `card-post
--file` keep the rule above. A1 test: a OtherCompany `lead-append --file <G>/drafts/l.json` refused
by a forced `ST/actions.lock` timeout (exit 12) leaves exactly one spool file holding the input's
bytes and no draft (RED when the draft is deleted without spooling). (2) `act.py purge-untrusted` also deletes every file under
`G/drafts/**` whose mtime is older than 24 hours (A1; the 30-day side-store window of §20.4 applies
to `ST/untrusted/`, not to scratch drafts, which have no purpose after their session). Non-hipaa
packs are unchanged. A1 tests: a OtherCompany `lead-append --file <G>/drafts/l.json` leaves no draft
file behind (RED when the delete is removed); `--file <G>/drafts/../company.json` and a
`drafts/` symlink to a file outside `drafts/` are consumed but not deleted (RED when the check is a
raw-text prefix); a 25-hour-old OtherCompany draft is purged, a OtherCompanyB one is not.

### 1.4 Environment variables

| Var | Set by | Read by | Meaning |
|---|---|---|---|
| `CLAUDE_GTM_COMPANY` | `gtm_session.sh` only | every hook, `act.py`, tools | this process tree **claims** to be a GTM session for `<slug>`. A claim, not proof (IMP-03): any Bash caller can set it inline. It selects the company and switches on the GTM-scope gate arms (which only makes gates stricter); wherever it would **admit** a command, act.py also requires `gtmlib.session.prove_gtm_session` (below) |
| `CLAUDE_GTM_SESSION` | `gtm_session.sh` only (the uuid4 from its `--session-id`, which `run_gtm_job.sh` generates; else a fresh uuid4; also passed as `claude --session-id`) | `act.py` (ticket `session_id`), G-A, gate-gtm | the session id hook payloads must carry. **DECIDED HERE** (07_notices_schedules.md §7.2, 07_notices_schedules.md §7.6) |
| `CLAUDE_GTM_RUN` | `run_gtm_job.sh` / `gtm_session.sh --run` | tools (default `--run`), prompts | informational only; no gate trusts it for authorization |
| `CLAUDE_DIR` | tests only | `company.claude_dir()` (all GTM code), `gtm_env.test_mode` | the **only** state-root override; non-empty ⇒ test mode (§1.1): never the trust root, no live connector, no write to a real home |
| `HOME` | tests | `_lib` constants, `Path.home()`, `gtm_env.test_mode` | hook and launcher tests set it to a tmp dir; differing from the passwd home ⇒ test mode (§1.1) |
| `GTM_TEST` | tests only | `gtm_env` | non-empty ⇒ test mode (§1.1); `1` additionally enables `GTM_FAKE_NOW` |
| `GTM_FAKE_NOW` | tests only | `gtm_env.now` (the `gtmlib` clock and the hooks clock) | exactly `%Y-%m-%dT%H:%M:%SZ` (UTC); honored **only** when `GTM_TEST=1`; non-empty ⇒ test mode; unparseable → tools exit 2 `bad_fake_now`, hooks use the real clock (§1.1) |
| `GTM_SECRET_SINK_PORT` | tests only | `secret_sink.py`, capture scripts, **only when `gtm_env.test_mode(environ)[0]` is true** | the production port is the constant `system_names.SECRET_SINK_PORT = 47823` (**DECIDED HERE**); outside test mode the variable is **ignored** (it is on plan §20.10's secret-delivery path: capture scripts POST the captured token to `127.0.0.1:<port>`, so an inline override could steer a secret to a listener other than `secret_sink.py`). G-B rule m denies an inline/`env`/`export` assignment of it in a command naming `tools/gtm/` (`gtm-env-override`, the same arm as `CLAUDE_DIR`/`GTM_TEST`). Test: outside test mode, `GTM_SECRET_SINK_PORT=1` in the environ → the capture script's target port is still 47823 (RED when the env value is honored outside test mode) |
| `GTM_HOLDS_JOB` | `run_gtm_job.sh` holds kind only | `act.py` (02_act.md §2.3 not-GTM-session exception) via `gtmlib.session.prove_holds_job` | `1` **claims** the launchd holds job; admitted only with the process-ancestry proof below (a literal denylist alone is evadable, e.g. `"GTM_HOLDS""_JOB=1"`); G-B rule k still denies the literal in any agent command |
| ~~`GTM_ALLOW_TRUST_EDIT`~~ | **removed (F16)** | — | replaced by the GTMApprover-signed, nonce-bound single-use marker `S/trust_edit_allow.json` (04_hooks.md §4.3, 05_approver.md §5.3/§5.4); a session-wide env var was a standing per-session bypass, which runtime CLAUDE.md §7 forbids. G-B rule k still denies the literal |
| `GTM_BACKUP_DEST_ROOT`, `TS_ACTIVITY_MIRROR_DIR` | existing | `backup_state.dest_root()` (read before its `HOME` default), activity_log's owner mirror | unchanged; tests clear both and pass the destination explicitly (§1.5 item 2) |
| `CSA_DISABLE_HOOKS` | existing | hooks; `gtm_session.sh`, `run_gtm_job.sh`, act.py | hooks: unchanged (`1` = allow before parsing). Non-empty and not `0` ⇒ the GTM launchers refuse to start (exit 64) and act.py refuses write/lead/repair-policy commands (exit 3 `hooks_disabled`), §0.4 |
| `CSA_ENFORCE` | existing | hooks | unchanged semantics: `1` makes `_lib.enforcing` true at its precedence step (2), before the global marker (§0.4); the §0.4 "no enforce marker anywhere" tests clear it |

**`GTM_STATE_DIR` is deliberately NOT supported. DECIDED HERE:** `company.gtm_state_dir()` (committed)
derives `S` from `CLAUDE_DIR`; a second override could split state between two roots.

`gtm_session.sh` and `run_gtm_job.sh` **refuse to start** (exit 64, message on stderr) when any of
`CLAUDE_DIR`, `GTM_TEST`, `GTM_FAKE_NOW` is set to a **non-empty** value (an empty string counts as
unset, §1.1), so production GTM sessions always use the real root; and when `CSA_DISABLE_HOOKS` is
non-empty and not `0` (§0.4), so no GTM session runs with its gates off. This refusal is defense in
depth only: an agent can set the same variables inline on any later Bash call, which is why §1.1's
test mode (not the launcher) is what keeps a fake root or clock away from real platforms, secrets
and state, and why G-B rules l/m deny those inline assignments (`requests/00_global_paths.md` R12/R20).

**GTM-session proof (IMP-03; DECIDED HERE).** The one function is

```python
# tools/gtm/gtmlib/session.py (A1)
def prove_gtm_session(slug: str, environ: Mapping[str, str]) -> tuple[bool, str]
# returns (True, "ok") or (False, reason), reason ∈ {"company_unset", "company_mismatch",
#   "lease_not_held", "lease_unreadable", "session_mismatch", "not_descendant"}
```

It returns `ok` only when `environ.get("CLAUDE_GTM_COMPANY")` equals `slug` (unset or empty →
`company_unset`; another value → `company_mismatch`) **and** all three hold: (a)
`S/leases/<slug>.lock` is held — opened with `os.open(path, os.O_RDONLY)` (never a mode that
creates the file: the proof writes nothing under `S`; a missing file → `lease_not_held`), then a
non-blocking `fcntl.flock(fd, LOCK_EX | LOCK_NB)` on it raises `BlockingIOError` (`/usr/bin/lockf`
locks are flock-compatible, 07_notices_schedules.md §7.6; if the probe acquires the lock it
releases it at once and returns `lease_not_held`); (b) `S/leases/<slug>.json` parses as an object
whose `session_id` is a non-empty string and whose `pid` is an `int` (`bool` excluded) —
`lease_unreadable` otherwise, including a missing file or key — and its `session_id` equals
`environ.get("CLAUDE_GTM_SESSION")` (unset or empty → `session_mismatch`, never a `KeyError`);
(c) its `pid` is `os.getpid()` or an ancestor of it (walk parents
with `ps -o ppid= -p <pid>`, at most 64 hops, stopping at pid 1; `not_descendant` otherwise). The lease
holder's `pid` is the locked child that starts `claude` (07_notices_schedules.md §7.6 step 4a), so
every Bash call of a real GTM session descends from it, while an agent in any other Claude session
that sets the env vars inline does not. **act.py's dispatch (02_act.md §2.3) calls it for every
command whose `chain_policy` is `write`, `lead` or `repair`, and for `resume`**, with exactly
**two** exceptions, matching 02_act.md §2.3: (1) `run-holds --all` for the holds job via
`prove_holds_job` (below); (2) `resume`/`autonomy` with a valid signed operator marker (below).
Separately — **not** an exception — `pause`, `cancel` and `card-post` are `read`-policy commands,
so the proof never applies to them and they run anywhere (02_act.md §2.3 note; `pause --self`
alone still needs the proof, 02_act.md §2.4), and the §0.4 `hooks_disabled` refusal never applies
to them either. Any non-`ok` result → exit 13 `not_gtm_session` with the
reason in the result JSON's `reason` field. A bare `CLAUDE_GTM_COMPANY` check is **never** an
admission test (`requests/00_global_paths.md` R9). Hooks never call it (for them the env var only
tightens scope). G-B additionally denies an inline/`env`/`export` assignment of any `CLAUDE_GTM_*`
variable in a command naming `act.py` (rule l `gtm-identity-forge`, 02_act.md §2.3; defense in depth,
`requests/00_global_paths.md` R12/R20); the
proof does not rely on that rule. A1 tests (P2, moved into 02_act.md §2.3's A1 list by R9): an inline
`CLAUDE_GTM_COMPANY=x CLAUDE_GTM_SESSION=<the lease's id> python3 …/act.py propose …` from a process
that does **not** descend from the lease holder exits 13 `not_descendant`; lease not held → 13
`lease_not_held`; wrong session id → 13 `session_mismatch`; each goes RED when its check is reverted
to the env-only test.

**Holds-job proof (DECIDED HERE).** `gtmlib.session.prove_holds_job(environ) -> tuple[bool, str]`
returns `ok` only when `environ.get("GTM_HOLDS_JOB") == "1"` **and** some ancestor process (≤ 64
hops, `ps -o ppid=,command= -p <pid>`) has a `command` whose first two argv words are a shell
(`/bin/bash` or `bash`) and a path whose `os.path.realpath` equals
`gtm_env.real_root()/system_names.HOLDS_RUNNER_RELPATH` (= `schedules/run_gtm_job.sh`, where the
07_notices_schedules.md §7.3 holds plist runs it), with `holds` among its later words, **and that
ancestor's own ppid is 1** (launchd). **The plist's argv is pinned (binding on WP-K):**
`ProgramArguments = ["/bin/bash", "<real root>/" + system_names.HOLDS_RUNNER_RELPATH, "holds", …]`
exactly — never the script path alone (its shebang would decide the first argv word, e.g. a
Homebrew bash or `/usr/bin/env -S bash`, which the proof rejects, so every real holds run would
exit 13) and never through `env`. Reasons: `not_claimed`, `no_holds_runner_ancestor`,
`runner_not_launchd_child`. In test mode (§1.1) the ppid-1 condition is waived and the runner path is
compared against `R/HOLDS_RUNNER_RELPATH` (test mode can reach no live platform and write no
real state, §1.1 (2)/(3)). **Accepted residual risk:** an agent that double-forks the *real*
`run_gtm_job.sh holds` (so it is reparented to launchd) gets an early holds run; that run is the
same job launchd would start, it refuses test overrides (above), and `run-holds` re-checks
`hold_until` against the real clock, cancels and pauses (03_schemas.md §3.11), so nothing executes
early. A1 test (in process, `gtm_env.test_mode` monkeypatched to `(False, [])`):
`prove_holds_job({"GTM_HOLDS_JOB": "1"})` from pytest (no runner ancestor) →
`(False, "no_holds_runner_ancestor")`, and dispatch of `run-holds --all` exits 13; RED when the
ancestry check is reverted to the env-only test. K test: the rendered `com.oversight.gtm.holds`
plist's `ProgramArguments` **starts with** exactly `["/bin/bash", "<real root>/" +
system_names.HOLDS_RUNNER_RELPATH, "holds"]` (the full argv prefix `prove_holds_job` expects, not
just the path); RED when either side hard-codes another location or the plist drops the explicit
`/bin/bash`.

**Operator authority is never read from the environment (IMP-03; DECIDED HERE).** `CLAUDECODE`
unset, `sys.stdin.isatty()` and every env var in the table above can be produced by any agent's
Bash (`env -u CLAUDECODE`, `unset`, inline `VAR=…`, `script -q /dev/null …`,
`python3 -c 'import pty; pty.spawn(…)'`), and no denylist of spellings closes that. So wherever
this contract set says **operator terminal** (02_act.md §2.3 exception 2, `resume`, `autonomy` and
`pause` in 02_act.md §2.4, 03_schemas.md §3.10 and §3.17), it means exactly: the invocation consumes
a valid single-use **signed operator marker**.

**The marker is signed, not merely present (DECIDED HERE — a security design call, not an
operator question; `requests/00_global_paths.md` R29).** An unsigned marker file can be forged by
any agent that writes under `S` through a route no gate parses (04_hooks.md §4.2 rule c "Known
shell-write reach": split-literal `python3 -c`, heredoc interpreters, `git apply` — accepted gaps
there), and a forged marker could (1) lift an owner pause such as OtherCompanyB's
`PAUSE.website_wordpress@remodeling` (A0022), (2) end shadow early with `autonomy --level
autonomous`, and (3) label a pause `created_by: "operator"`. The signed primitive already exists
for exactly this shape — GTMApprover's `trust_edit_allow` marker (04_hooks.md §4.3, 05_approver.md
§5.3/§5.4) — so the operator marker reuses it:
- **Creation.** Only `tools/gtm/operator_ok.sh <command> <slug> <target>`, run by the operator in
  their own terminal, which execs `scripts/gtm_approve.sh operator-ok <command> <slug> <target>` →
  `GTMApprover --sign-operator-ok`. **Before any LAContext prompt the app shows an in-app
  `NSAlert`** titled with the request (`"Allow ONE <command> of <target> for <slug>?"`) whose
  **default button is Deny** (Return and Escape both deny; Allow needs a deliberate click) — the
  same shape as a `$` approval (plan §20.8: the operator approves from the app's own list, Deny the
  default); only after Allow does it run Touch ID with the reason `"Allow ONE <command> of <target>
  for <slug> within 15 minutes"`. The same alert precedes `--sign-trust-edit`
  (`"Allow ONE edit of <path>?"`). The script still refuses when `CLAUDECODE` is set, but that is
  friction only (`env -u CLAUDECODE` bypasses it); **agents are kept from soliciting these prompts
  by G-B rule g** (`agent-approver-script`, 04_hooks.md §4.2): it already denies running
  `gtm_approve.sh` in **any** mode — the re-show form, `trust-edit` and `operator-ok` — and R41 asks
  it to deny, in the same clause, a direct run of the app binary (a verb whose path, casefolded,
  ends in `gtmapprover.app/contents/macos/gtmapprover`) and `open` with `-a GTMApprover`,
  `-b <the app's bundle id>` or a `GTMApprover.app` operand (any `--args`), so an agent cannot make
  the operator's Mac raise a Touch ID prompt the operator never started (an approval-fatigue hole).
  Rule k is **not** the mechanism here: its literals take effect only as an assignment, interpreter
  code, a write target or an executed program's basename, and an argv argument such as
  `operator-ok` is none of those. Touch ID remains the final control (`requests/00_global_paths.md`
  R39 asks 05_approver.md §5.3/§5.4 for the alert). The app writes
  `S/operator_ok/<command>.<slug>.<target>.json` (keyed by target, so several lifts can be pending),
  e.g. `S/operator_ok/resume.other-company.PAUSE.website_wordpress@remodeling.json`, atomically, 0600:

```json
{"schema": "gtm.operator_ok.v1", "payload_b64": "<canonical payload>", "signature_b64": "…", "alg": "…", "key_fingerprint": "…", "signed_at": "2026-09-27T15:04:05Z"}
```

  where the payload is `canon({"v": 1, "kind": "operator_ok", "command": …, "company": …,
  "target": …, "nonce": "<32 hex>", "expires": "<UTC Z, signing time + 15 min>"})` with exactly
  those keys (the key set differs from a `$` payload's and from `trust_edit`'s, so none can pass as
  another). `command` ∈ `OPERATOR_OK_COMMANDS` (`resume`, `autonomy`, `pause`); `target` = the exact
  pause file name the `resume` removes or the `pause` writes, or `"autonomous"` for `autonomy
  --level autonomous`.
- **Validation (act.py, after its trust check, 05_approver.md §5.5 step 0).** Dispatch derives
  `<target>` from the flags alone (02_act.md §2.3) and looks for exactly that file. Valid only when
  **all** hold: (1) `approval_sig.verify_raw` verifies the signature over the decoded payload bytes
  with the key from `git -C <trust root> show HEAD:tools/gtm/approver_pubkey.pem` (§1.1 consequence
  1; never the working tree; stdlib/openssl only, §0.2); (2) the payload is canonical with exactly
  the keys above and `kind == "operator_ok"`; (3) `command`/`company`/`target` equal the
  invocation's; (4) `now < expires ≤ now + 15 min` (`gtm_env.now`, so `GTM_FAKE_NOW` applies in
  tests; `signed_at` is not signed and is never read); (5) under `S/approval_nonces.lock`,
  `S/approval_nonces.jsonl` holds no line for the nonce, and act.py appends `{"ts", "company":
  <slug>, "request_id": null, "action_id": null, "nonce", "op": "consume", "holder":
  "operator-ok:<command>:<target>"}` (straight from none to `consume`, as for `trust_edit`). It then
  deletes the marker under `S/operator_ok.lock` **before** it changes any state, so one marker
  authorizes one invocation. HEAD with no `approver_pubkey.pem` (approver not installed) → the
  marker route refuses `approver_not_installed` (exit 11, as 05_approver.md §5.5); the card route of
  02_act.md §2.4 `resume --card` still works, so no owner pause is stranded before install. A marker
  that fails any check is **left in place** and the command refuses exactly as it would with no
  marker.
- **The card route is an accepted, plan-sanctioned residual, detect-after (stated).** The argument
  above — an agent-forgeable unsigned file must not grant operator authority — also applies to a
  card answer: its authority is an archived answer in the operator-input file
  (`OPERATOR_DECISIONS.md` for CSA), a tracked markdown file that agents edit by design (they move
  cards to `## Archived`). It is kept **only** where the plan names it: `resume --card` for pause
  lifts (plan §6.1(b)/§6.4, card C7), and the other card-gated commands 02_act.md §2.4/§2.11 list:
  `pause --created-by migration`, `chain-repair`, `record-external --kind
  approval --card <card_id> --action <id>` (an `awaiting_card` action's `authorize <action_id>`
  card, and the `owner_listen` subject), and `record-external --kind owner_executed --card
  <request_id>`. **`revert` is not on that list (DECIDED HERE; header item (vii); a narrowing).**
  Plan §20.8, which supersedes §6.8, says "`revert --approval <card id>` (§6.8) means 'a signed
  approval for that revert action'", and it does not limit that to money; reading it as money-only
  would loosen the superseding text, so this contract reads it literally: **every** `revert --child
  <id> --approval <id>` names a **signed** approval. A money child keeps its full `$` approval
  request. A non-money child that step 1 neither executes nor holds — routes (4) and (5)-`shared`
  of 02_act.md §2.4 `revert`, which today park it in `awaiting_card` when no pause covers it — goes
  to `awaiting_approval` with the **amount-less approval request signed over the child's
  `after_digest`** (03_schemas.md §3.7 case (v), 05_approver.md §5.5 step 3b), the same primitive
  02_act.md §2.4 already uses for a non-money child under a pause, with the child's
  `failing_checks` on its display and a `revert_approval` notice; the signed operator marker is
  **not** reused for it (its payload carries no `after_digest`, and a second primitive for the same
  approval would be a second thing to review). So `OPERATOR_OK_COMMANDS` is unchanged, and step
  2's `--approval <card_id>` form is withdrawn: a card id → exit 3 `revert_approval_mismatch`,
  nothing appended. Stated consequence: before the approver is installed a non-money revert child
  that needs a decision waits in `awaiting_approval` (the operator can still make the change himself
  and record it with `record-external --kind owner_executed`), which only withholds.
  `requests/00_global_paths.md` R42 asks 02_act.md §2.4 `revert` (routes (4)/(5), step 2 (b)),
  §2.5, §2.11, 03_schemas.md §3.7 case (v), 05_approver.md §5.5 step 3b and 07_notices_schedules.md
  §7.1 to match. A2 tests (each RED when the card route is restored): a non-money `shared` revert
  child with no pause → `awaiting_approval` with an amount-less request, never `awaiting_card`;
  `revert --child <it> --approval <an approved card id>` → exit 3 `revert_approval_mismatch`,
  nothing appended; the signed request authorizes it once, and a second step 2 with the same
  request id is refused (nonce consumed). **A card answer never authorizes a `$` action or any
  revert child; only a signed approval does** (plan §20.8 "`record-external` kind (b) never applies
  to `$`"; 02_act.md §2.4 `revert` step 2 and §2.11, 05_approver.md §5.5): `record-external --kind approval` naming an
  effective-`money` action with any subject other than the mirrored `approval <request_id>` form
  refuses exit 3 `card_approval_money_forbidden` with no event, and even the mirrored form never
  decides the request (02_act.md §2.11). The A2 test that pins it (requested of 02_act.md §2.11 by
  `requests/00_global_paths.md` R41): an approved card with subject `authorize <money action id>`
  → `record-external --kind approval` exits 3 `card_approval_money_forbidden`, nothing appended
  (RED when the money check is removed). For these the control is
  **detect-after**, not prevent: 02_act.md §2.6's card-authorship scan checks that no agent wrote
  the answer, from `ST/cards_posted.jsonl` and the session transcripts. Its known blind spots,
  accepted: (a) it skips Agency project dirs by name (§0.1 F9), so an answer written by an Agency
  session is invisible; (b) it sees only writes that some transcript names — an in-process write by
  a script, or a write from a session whose transcript was deleted or never written, is invisible;
  (c) it runs at `require_approved` time, so an answer forged and consumed before the next scan of a
  later session is caught only then. **`autonomy --level autonomous` drops the card route (DECIDED
  HERE):** the plan ties no named lift card to leaving shadow (plan §20.6 "may end early" is an
  operator act, not a card), and shadow is the safe state, so it is allowed only by (i)
  `shadow_exit` criteria met or (ii) a consumed signed operator marker; `autonomy --card` is
  withdrawn (`requests/00_global_paths.md` R39 asks 02_act.md §2.4/§2.3 and 03_schemas.md §3.17 to
  remove it). Before the approver is installed the company simply stays in shadow until its
  criteria are met — nothing is stranded that the plan requires. A1 test: `autonomy --company x
  --level autonomous --card <an approved card>` with criteria unmet and no marker → exit 3
  `shadow_criteria_unmet` (RED when `--card` is re-admitted).
- **Recording.** The chain event records `lifted_via: "operator_ok"` (`resume`) or `decided_by:
  "operator_ok"` (`autonomy`) — the values in 02_act.md §2.2b's event table and 03_schemas.md §3.17
  — and a `pause` created with a marker records `created_by: "operator"`; an `info` notice shows the
  marker's fields on `GTM_Operator.html`, so any use the operator did not make is visible.
- **A pause that names a `lift_card` is never lifted by any marker (binding now, plan §6.4 "lifted
  only by card C7's answer").** For such a pause `resume` requires `--card <lift_card>` passing
  `cards.require_approved` with an **approve** decision (FID-01; the pause's `lift_card` id is the
  subject binding, 03_schemas.md §3.10); a marker for it is refused and left in place
  (`resume_card_required`). So A0022's pauses (`lift_card: "C7"`) are lifted only by C7's approve
  answer, whether or not the marker design has landed.
**Review.** trust-architect is reviewer-of-record for the landing of this design across 02_act.md
§2.3, 04_hooks.md §4.2 rule k, 05_approver.md §5.3/§5.4 and 08_seats_wps.md Appendix B #128 (R29) —
a design item for the coordinator, not an operator card; the former "operator question" wording of
08_seats_wps.md Appendix C item 18 no longer covers these three lifts. Agents also cannot write the
file the ordinary ways (G-W denies Write/Edit under `S`, G-B rule c denies shell writes under `S`,
G-B rule k denies every `RULE_K_LITERALS` member — `operator_ok` included — wherever it can take
effect in an agent command, and G-B rule g denies running `gtm_approve.sh`, the GTMApprover
binary or `open -a GTMApprover`, 04_hooks.md §4.2, `requests/00_global_paths.md` R10/R41), but
those are friction; the signature is the control.
B1 tests (R41, superseding R39's rule-k attribution), each run end-to-end through `bash_gate.sh`
and each RED when **its rule-g clause** is removed: `env -u CLAUDECODE
~/.claude/scripts/gtm_approve.sh operator-ok resume other-company PAUSE.gbp` and
`~/.claude/scripts/gtm_approve.sh trust-edit /x` denied `agent-approver-script` (the existing
`gtm_approve.sh` clause); a direct `~/Applications/GTMApprover.app/Contents/MacOS/GTMApprover
--sign-operator-ok resume other-company PAUSE.gbp` and `open -a GTMApprover --args --sign-trust-edit
/x` denied `agent-approver-script` (the new binary/`open` clause); `grep -rn operator-ok tools/gtm`,
`grep -rn GTMApprover tools/gtm` and `cat ~/.claude/scripts/gtm_approve.sh` allowed. The re-show
form `gtm_approve.sh <request_id>` is **also denied** to agents (rule g, "any mode"): act.py writes
`S/approver_inbox/show.<request_id>` itself (05_approver.md §5.1 step 5), so agents never need the
script; only the operator runs it.
**No env/TTY heuristic survives anywhere**, not even for labelling: `pause` labels `created_by:
"operator"` only from a consumed signed marker (02_act.md §2.4 `pause`). P2 falsification tests (A1,
in 02_act.md §2.3's list; fixture keys and signatures from 05_approver.md's test key, §1.5 item 5):
`env -u CLAUDECODE script -q /dev/null python3 …/act.py resume …` on an operator pause with no
marker is refused; an **unsigned** marker in the former `{command, company, target, created_at}`
form with every field matching is refused and left in place (RED when the signature check is
removed); a marker signed by a key other than HEAD's is refused, also after the working-tree
`approver_pubkey.pem` is swapped to the signer's key; a marker for another command, company or
target, an expired one, and one whose `expires` is more than 15 minutes ahead are refused and left in
place; a valid marker succeeds once and is gone, and a copy restored afterwards (same nonce) is
refused; a valid marker naming the A0022 pause (`lift_card: "C7"`) is refused `resume_card_required`
and left in place (RED when the `lift_card` rule is removed); the same success/refusal pairs for
`autonomy --level autonomous` and for `pause`'s `created_by: "operator"` label. Each goes RED when
its check is reverted.

**Shared literals — every contract file and implementation must agree (DECIDED HERE).** The one
code definition is `tools/gtm/system_names.py` (A1; standalone, so hooks import it):

| Constant | Value | Used by |
|---|---|---|
| `OPERATOR_OK_DIRNAME` | `"operator_ok"` | `gtmlib.session` reads `S/<OPERATOR_OK_DIRNAME>/`; `operator_ok.sh` writes it |
| `OPERATOR_OK_LOCK` | `"operator_ok.lock"` | `gtmlib.session` |
| `OPERATOR_OK_COMMANDS` | `("resume", "autonomy", "pause")` | `gtmlib.session`, `operator_ok.sh` |
| `OPERATOR_OK_EVENT_VALUE` | `"operator_ok"` | `lifted_via` / `decided_by` in 02_act.md §2.2b, 03_schemas.md §3.17 |
| `RULE_K_LITERALS` | `("GTM_ALLOW_TRUST_EDIT", "GTM_HOLDS_JOB", "trust_edit_allow", "operator_ok")` | G-B rule k and the 04_hooks.md §4.7 fast-path tokens. R39's five additions (`operator-ok`, `sign-operator-ok`, `trust-edit`, `sign-trust-edit`, the app binary path) are **withdrawn by R41**: in `gtm_approve.sh operator-ok …` or `GTMApprover --sign-operator-ok` they are argv arguments, a position rule k never judges, so they could not deny what R39 claimed; the unsolicited-Touch-ID path is closed by G-B rule g instead ("Review" above) |
| `SECRET_SINK_PORT` | `47823` | `secret_sink.py` and the capture scripts (§1.4 env table: `GTM_SECRET_SINK_PORT` is honored only in test mode) |
| `SLUG_RE` | `re.compile(r"^[a-z][a-z0-9-]{1,31}$")` | `company.py` (imports it, Appendix C item 14), act.py, gate-gtm, `register`, cancel ingest, `CYCLE_ID_RE` (§0.3) |
| `HOLDS_RUNNER_RELPATH` | `"schedules/run_gtm_job.sh"` | `gtmlib.session.prove_holds_job`; the 07_notices_schedules.md §7.3 holds plist renderer |

Retired spellings (retired: `operator_ack`; retired as a recorded value: `"operator_terminal"`)
must appear in no contract file or code except on a line that contains the word "retired". Tests
(`requests/00_global_paths.md` R10/R11): B1 asserts rule k's literal set **is**
`system_names.RULE_K_LITERALS` and that `system_names.OPERATOR_OK_DIRNAME in RULE_K_LITERALS`
(so the protective deny always covers the directory `gtmlib` reads), and that the set has exactly
the four members above (R39's five are not members, R41); B2 asserts every `RULE_K_LITERALS`
member appears as a `*<literal>*` token in `bash_gate.sh`'s fast-path arm (04_hooks.md §4.7), and
that the fast path forwards `*gtmapprover*` (casefolded) for rule g's binary/`open` clause; the
coordinator's contract-consistency test (`tools/gtm/tests/test_contract_literals.py`) reads an
**exact file set** — the eight numbered contract files in `tools/gtm/contracts/` (`00_global_paths.md`,
`02_act.md`, `03_schemas.md`, `04_hooks.md`, `05_approver.md`, `06_connectors.md`,
`07_notices_schedules.md`, `08_seats_wps.md`) plus
`tools/gtm/CONTRACTS.md` — and fails on any retired spelling found on a line that does not contain
the word "retired" (and, with the same file set, the §0.2 third-party-package check). It never reads
`contracts/OPEN_FINDINGS.md` or `contracts/requests/**`: both are historical records that quote
retired spellings by design (`OPEN_FINDINGS.md` names `S/operator_ack.json` on a line without the
word). The file set is a literal list in the test, not a glob, so a new contract file is added
there on purpose (CROSS: `requests/00_global_paths.md` R11, amended by R30).

### 1.5 Test isolation (every WP's tests)

1. Each test builds a tmp tree: `HOME=<tmp>/home`, `CLAUDE_DIR=<tmp>/home/.claude`, a tmp
   `<CLAUDE_DIR>/knowledge/gtm_company_registry.json` (with a `companies` map and
   `"repo_registry_slugs"` — `["exampleapp"]` when CSA must be enumerated, else `[]`, since an
   absent key makes `validate --all` and `company.py index` refuse, §0.1), a tmp
   `<CLAUDE_DIR>/knowledge/repo_registry.json` — **always**, as a determinism rule (the committed
   `resolve_home()`/`registered_slugs()`/`backup_set()` read it through `_repo_registry_repos()`,
   which treats a **missing** file as empty and raises only for a present-but-unreadable one, §0.1
   "Registry inputs" (3); nothing raises on a missing file, but a test tree that sometimes has it and
   sometimes not would exercise two code paths by accident); at minimum `{"schema_version": 1, "repos": {}}`, plus a
   `exampleapp` entry (root = a tmp home) when the `repo_registry_slugs` allowlist is exercised
   and an `agency` entry when the §0.1 no-Agency-touch oracle runs — and one or more tmp homes each
   holding the 08_seats_wps.md Appendix A pack, at `<tmp>/homes/<slug>` under the resolved
   `tmp_path` (never under the real home, so no real-registry root can contain them, §1.1 (3)). `gtm_slugs()`'s behaviour for a missing
   `repo_registry.json`, an absent `repo_registry_slugs` key, and a slug in both registries is fixed
   in §0.1 "Registry inputs"; each case has a coordinator test (Appendix C item 14).
   Use `company.validate_company(slug, pack, siblings={})` to self-check fixtures. Such a tree is in
   **test mode** (§1.1).
2. Clear, then set explicitly: `CLAUDE_DIR`, `HOME`, `CLAUDE_GTM_COMPANY`, `CLAUDE_GTM_SESSION`,
   `CLAUDE_GTM_RUN`, `GTM_TEST`, `GTM_FAKE_NOW`, `GTM_HOLDS_JOB`, `GTM_SECRET_SINK_PORT`,
   `GTM_BACKUP_DEST_ROOT`, `TS_ACTIVITY_MIRROR_DIR`, `CSA_DISABLE_HOOKS`, `CSA_ENFORCE`, and
   `CLAUDECODE` (set in every Claude session; `operator_ok.sh` refuses when it is set, so its tests
   would otherwise pass or fail with the ambient shell). `backup_state.dest_root()` reads
   `GTM_BACKUP_DEST_ROOT` before its `HOME` default and activity_log honors
   `TS_ACTIVITY_MIRROR_DIR` for the owner mirror, and `refuse_real_state` covers neither
   destination, so backup and render tests pass the destination explicitly (`--dest-root <tmp>` /
   the mirror override set to a tmp path), never the ambient value. Hook tests additionally use
   `hooks/tests/conftest.py`'s `sandbox` fixture, which sets `HOME` to `<tmp_path>/home`,
   monkeypatches every `_lib` path constant (`HOME`, `CLAUDE_DIR`, `GLOBAL_ENFORCE_FILE`,
   `ENFORCEMENT_DIR`, `LOG_FILE`, the review/budget/claims/churn paths) into the sandbox,
   `chdir`s to `tmp_path`, and — through its `clean_env` dependency — deletes the `CSA_*` vars.
   Because conftest is not a WP-owned file, each GTM hook test file adds its own autouse fixture
   that **takes `sandbox` as a parameter** (so it always runs after `sandbox` has set `HOME`),
   deletes the other vars above and sets `CLAUDE_DIR` to `<sandbox HOME>/.claude`, so an ambient
   `CLAUDE_DIR` can never redirect a hook test's state root.
3. Never touch the real `~/.claude`, `~/Desktop`, any real company home, `launchctl`, GSM, Keychain,
   a real browser, or the network. Connector tests use recorded fixture responses (06_connectors.md §6.5).
   The one exception: in test mode, writers **read** (never write)
   `real_root()/knowledge/{gtm_company_registry,repo_registry}.json` for §1.1 (3)'s real-state
   refusal, **and `os.path.realpath` the non-Agency roots listed there** (which `lstat`s each
   component, e.g. the real `~/Desktop` and `~/Desktop/ExampleApp`; never an open, list,
   read or write of anything under them, and never a root equal to or under either Agency root,
   §1.1 (3)); a missing file there lists no roots, so tests pass on a machine without them.
4. Tests needing a clock set `GTM_TEST=1 GTM_FAKE_NOW=...` (subprocess) or pass `now=` (in-process).
5. Tests needing git (trust-root checks, 05_approver.md §5.5) `git init` the tmp `CLAUDE_DIR` and commit fixtures.
   With `HOME=<tmp>/home` there is no `~/.gitconfig`, so every such `git` call passes `env=` with
   `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL=/dev/null`, `XDG_CONFIG_HOME` **removed** (an
   ambient `XDG_CONFIG_HOME` or `GIT_CONFIG_GLOBAL` could still load a user config with a tmp
   `HOME`), `GIT_AUTHOR_NAME=gtm-test`, `GIT_AUTHOR_EMAIL=gtm-test@example.invalid`,
   `GIT_COMMITTER_NAME=gtm-test` and `GIT_COMMITTER_EMAIL=gtm-test@example.invalid`, and commits with
   `-c commit.gpgsign=false` (so neither a missing identity nor the machine's system or user git
   config can change the result).
6. Runtime tests run as `cd ~/.claude && python3 -m pytest tools/gtm/tests/ hooks/tests/ -q -m "not live_machine"`
   (`~/.claude/pyproject.toml`'s `[tool.pytest.ini_options]` has no `addopts`; the `live_machine`-marked tests read this machine's real
   telemetry, which item 3 forbids, and are excluded by that flag).
   Select tests by file or test name; a test command line never needs to spell any
   `system_names.RULE_K_LITERALS` member (`GTM_HOLDS_JOB`, `trust_edit_allow`, `operator_ok`, …; G-B
   rule k, 04_hooks.md §4.2) — those literals live inside the test files — nor set `CLAUDE_DIR`,
   `GTM_TEST`, `GTM_FAKE_NOW` or `HOME` inline on a command naming `tools/gtm/` (G-B rule m
   `gtm-env-override`, R12/R20, exempts only `pytest`/`python3 -m pytest` segments; tests set them
   inside the test via `monkeypatch.setenv` or a subprocess `env=`).
7. Every guard gets a falsification test (runtime CLAUDE.md §6): revert the guard line, the test goes RED.
   **Protected files (IMP-04).** Once B2's G-B wiring is registered, rule c denies shell writes to
   and removals of every trust-root path (`gtm_hooklib.trust_root_path()`: `R/tools/gtm/act.py`,
   everything under `R/tools/gtm/gtmlib/`, and the rest of the live `R/tools/gtm/` subtree except
   `tests/`, `connectors/*/tests/`, `contracts/` and top-level `*.md`) — as a `cp`/`mv`/`install`
   destination, an `mv` source, `sed -i`, a redirect — while **reading** one stays allowed
   (`cp <trust-root file> <scratch>/`, the single-file backup; rule c's IMP-04 exception); and once
   G-W is registered, every Write/Edit on a trust-root path needs a GTMApprover-signed single-use
   `trust_edit_allow` marker (04_hooks.md §4.2 rule c, §4.3 "Trust roots"). Both registrations land
   in the same post-Wave-2 coordinator step (08_seats_wps.md Appendix C item 19, which IMP-04 extends
   from G-W to B2's G-B wiring), so Wave-2 implementers are never blocked by them. Before
   registration the usual single-file backup → revert → rerun → restore works. After it, the
   falsification test for a guard in any trust-root file monkeypatches the guard function to its
   reverted behavior in-process and asserts the paired test's assertion fails (an on-disk revert
   would need a signed marker per edit). Never move, edit or restore a trust-root file from Bash.
8. Tests of write-policy act.py commands (subprocess) create the GTM-session proof of §1.4 in the
   tmp tree: the test process holds `fcntl.flock(LOCK_EX)` on `<tmp S>/leases/<slug>.lock` and writes
   `<tmp S>/leases/<slug>.json` with its own `os.getpid()` and the `CLAUDE_GTM_SESSION` it sets (the
   test process is the subprocess's parent, so check (c) holds). Operator-authority tests write
   `<tmp S>/operator_ok/<command>.<slug>.<target>.json` directly from the test (G-W/G-B do not run inside
   pytest), **signed** with the fixture approver key committed in the tmp `CLAUDE_DIR` (item 5;
   05_approver.md's test-key fixture), and set the payload's `expires` (and `GTM_FAKE_NOW`/`now=`)
   when a test needs an expired or fresh marker.
9. **Launcher tests (WP-K: `gtm_session.sh`, `run_gtm_job.sh` — lease, holder info, alarm,
   cycle-id slot computation).** The launchers refuse a non-empty `CLAUDE_DIR`/`GTM_TEST`/
   `GTM_FAKE_NOW` (§1.4), so their tests are the one exception to items 1 and 4: they set **only**
   `HOME=<tmp>/home` and pass `env=` with `CLAUDE_DIR`, `GTM_TEST` and `GTM_FAKE_NOW` **removed**
   (not set to empty — although an empty value also counts as unset, removal is the recipe).
   `company.claude_dir()` then falls back to `Path.home()/".claude"` = `<tmp>/home/.claude`, inside the
   tmp tree, and the `HOME` mismatch alone puts everything the launcher starts in test mode (§1.1),
   so no live platform, secret or real state is reachable. `claude` itself is replaced by a stub
   script first on the tmp `PATH`. Clock-dependent launcher behaviour (cycle-id `run_date`/HHMM
   from `--slot`, scheduled days, company-local midnight, DST) is tested on the helpers the
   launchers call — `runner_probe.py` (WP-D, 07_notices_schedules.md §7.2 D tests; its clock,
   `requests/00_global_paths.md` R34) — run directly under item 4's clock (`now=` in process, or
   `GTM_TEST=1 GTM_FAKE_NOW` on the probe's own subprocess), never through a fake clock in the
   launcher's environment; `gtm_session.sh`'s interactive `run_id` (07_notices_schedules.md §7.6
   step 4(b)) is asserted by shape only (`CYCLE_ID_RE`, kind `interactive`, HHMM present). A launcher test also asserts the refusal: each of the
   three variables set non-empty → exit 64; set to `""` → not refused; `CSA_DISABLE_HOOKS=1` → exit
   64, `CSA_DISABLE_HOOKS=0` → not refused (§0.4).
