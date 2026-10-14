# GTM Wave-2 interface contracts — §5 Approver protocol

> Part of the split GTM Wave-2 contract set. Index, file list and precedence: [`../CONTRACTS.md`](../CONTRACTS.md).
> References into another contract file carry that file name (e.g. `03_schemas.md §3.4.4`). A bare `§N` is either
> a section of this file or, exactly as in the original single document, a section of the plan
> (`~/.claude/plans/gtm_autonomous_department_plan.md`; always so for §10 and above, and wherever the text says "plan §…").
> Open review findings for this file: [`OPEN_FINDINGS.md`](OPEN_FINDINGS.md).
> Cross-file changes this section depends on are listed in [`requests/05_approver.md`](requests/05_approver.md)
> (R1–R8 first round, R9–R24 revision 2, R25–R30 revision 3, R31–R50 revision 4, R51 revision 5,
> R52–R65 revision 6, R66–R74 revision 7, R75–R82 revision 8).

## 5. Approver protocol (WP-C ↔ WP-A2 ↔ WP-D)

**Names used here.** For Python callers `R` = env `CLAUDE_DIR` if set, else `~/.claude`
(00_global_paths.md §1.5); `S` = `R/.gtm_state` (= `company.gtm_state_dir()`, 00_global_paths.md
§1.1). **The Swift app and the three shell scripts (`gtm_approve.sh`, `gtm_cancel.sh`,
`tools/gtm/approver/build.sh`) never take a production root from `HOME` or `CLAUDE_DIR`
(00_global_paths.md §1.1: "production roots never come from HOME or CLAUDE_DIR"; DECIDED HERE).**
Their real root is `<passwd home>/.claude`: the scripts read the passwd home with
`/usr/bin/dscl . -read "/Users/$(/usr/bin/id -un)" NFSHomeDirectory` (the value after
`NFSHomeDirectory: `), the app with `getpwuid(getuid())->pw_dir`, exactly as `gtm_env.real_root()`.
- **Scripts.** `CLAUDE_DIR` empty or unset → `R` = the real root. `CLAUDE_DIR` non-empty and naming
  the real root → `R` = the real root. "Naming the real root" is the bash equivalent of
  00_global_paths.md §1.1 `gtm_env.same_root` (`os.path.samefile` when both exist, else
  `gtm_env.norm_text` equality): when both `cd "$CLAUDE_DIR"` and `cd <real root>` succeed, the two
  are the same root iff `/usr/bin/stat -L -f '%d:%i'` prints the same device:inode for both
  (samefile; `-L` stats the symlink's **target**, as `os.path.samefile` does — without it a symlink
  to the root is judged by the link's own inode and reports "different"); when either `cd` fails,
  iff their `norm_text` forms are equal, where the bash `norm_text` is an exact port of
  00_global_paths.md §0.1 `gtm_env.norm_text`: (1) `posixpath.normpath` — split on `/`, drop empty
  and `.` components, let `..` pop the previous component (never above the root), keep exactly two
  leading slashes when the input starts with exactly two (Python's rule) and collapse three or more
  to one, and an empty result is `.`; (2) ASCII casefolding (`/usr/bin/tr '[:upper:]' '[:lower:]'`),
  which equals Python's `casefold` only on ASCII, so **a `CLAUDE_DIR` containing any non-ASCII byte
  is refused exit 2 `usage` before any compare**; (3) the firmlink strip — `/system/volumes/data`
  alone → `/`, a `/system/volumes/data/` prefix removed (the text is already casefolded). No symlink
  resolution and no `~` expansion. A C parity test runs the bash function and `gtm_env.same_root`
  over the same case list (identical path, trailing `/`, case variant, symlink to the root, a
  missing path, an unrelated dir, a path with a `.` component, a missing path with a `..`
  component, a `/System/Volumes/Data`-prefixed form of the real root, a leading `//`) and requires
  equal answers (RED when `-L` is dropped: the symlink case differs).
  **Under `GTM_TEST=1`, `CLAUDE_DIR` must be non-empty and must not name the real root** (the bash
  analogue of 00_global_paths.md §1.1 consequence 3, `refuse_real_state`: test mode never writes
  real state); `GTM_TEST=1` with `CLAUDE_DIR` empty, unset or naming the real root → **exit 2
  `usage`**, nothing written (not exit 5: the operator's own real-root invocation is never a
  mismatch). **`GTM_TEST` values (both scripts and `build.sh`):** empty or unset = not a test run;
  exactly `1` = a test run; any other value → exit 2 `usage` before anything else, nothing written
  (so a typo such as `GTM_TEST=true` never silently selects production). C test: `GTM_TEST=yes`
  with a tmp `CLAUDE_DIR` makes each script exit 2 `usage` with nothing written under either root.
  `CLAUDE_DIR` non-empty and naming anything else → a test run **only** when `GTM_TEST=1`
  is also set, and then `R = $(cd "$CLAUDE_DIR" && pwd -P)` (the physical path, so the scripts agree
  with `company.claude_dir()`'s set branch, `Path(CLAUDE_DIR).expanduser().resolve()`; a
  `CLAUDE_DIR` that cannot be entered → exit 2 `usage`); otherwise **exit 5**, stderr
  `root_mismatch`, no stdout, nothing written. **Exit 5 means `root_mismatch` and nothing else, in both scripts and in every
  app CLI mode (§5.3)**; it is never a pass-through of any other condition (the Python side keeps
  02_act.md's exit 3 `root_mismatch`, a different process family). Agents cannot run these scripts
  or the app binary at all (G-B rule g, R36, R51, R57), and `GTM_TEST` is never set in the
  operator's shell, so an exported or `launchctl setenv` `CLAUDE_DIR` can never redirect his
  cancels or re-shows.
- **App.** A production build ignores `CLAUDE_DIR` for `R`; when `CLAUDE_DIR` is non-empty and does
  not name the real root it shows a visible error state in the menu bar ("GTM approver: CLAUDE_DIR
  points elsewhere — not watching") and watches nothing, signs nothing and writes nothing until
  restarted without it. **Every CLI mode of a production build (§5.3 table) does the same check
  first and exits 5 `root_mismatch` (stderr), writing nothing and asking for no Touch ID**, so no
  production binary ever writes a marker or key file for a foreign root. Only the **test build**
  (compiled with `-D GTM_TEST_BUILD`, installed only at `R/test_fixtures/GTMApprover.app`, §5.3)
  takes `R` from `CLAUDE_DIR` (resolved as `company.claude_dir()`'s set branch resolves it). **The
  test build refuses the real root:** when `CLAUDE_DIR` is empty or unset, or its `R` is the same root
  as `<passwd home>/.claude` (the scripts' same-root rule above), every CLI mode exits 5
  `root_mismatch` (stderr) before any `LAContext`, Keychain or file call, and the menu-bar mode
  shows "GTM approver (test build): refusing the real root" and watches, signs and writes nothing —
  so a test build can never write a real `operator_ok`, `show.*` or cancel marker.
- Tests (C/D): `CLAUDE_DIR=/tmp/x gtm_cancel.sh all <fixture slug>` (no `GTM_TEST`) exits 5
  `root_mismatch` and writes nothing under `/tmp/x` or the real `S`; the same for `gtm_approve.sh`
  and `build.sh`; with `GTM_TEST=1` and `CLAUDE_DIR=/tmp/x` (a path through the macOS `/tmp →
  /private/tmp` symlink) the scripts resolve `S = /private/tmp/x/.gtm_state`, equal to
  `company.gtm_state_dir()` for that `CLAUDE_DIR` (RED when the scripts use `$CLAUDE_DIR`
  unresolved); `CLAUDE_DIR=<real root with a trailing / or a case variant>` is not a mismatch. A
  production-build app started with `CLAUDE_DIR=/tmp/x` shows the error state and creates no file
  under either root, and the same binary run as `--sign-operator-ok resume <fixture slug> autonomous`,
  `--sign-trust-edit <path>`, `--export-pubkey` and `--generate-key` with `CLAUDE_DIR=/tmp/x` each
  exit 5 with no LAContext call and no file written under either root. **Real-root refusal in test
  mode (C, each RED when the refusal is removed):** `GTM_TEST=1` with `CLAUDE_DIR` unset, and
  `GTM_TEST=1` with `CLAUDE_DIR=<real root>`, each make `gtm_approve.sh <valid request id>`,
  `gtm_cancel.sh all <fixture slug>` and `build.sh --test` exit 2 `usage`; the test build started
  with either environment exits 5 in every CLI mode; and all of these pass the **test-footprint
  oracle** below.
  **Test-footprint oracle (every test in this file that asserts "nothing written under the real
  root" uses exactly this; DECIDED (wave1c): a per-run marker, never a whole-directory mtime compare
  — the session running the test appends to its own transcript under `~/.claude/projects/`, and
  every live session keeps writing `~/.claude/.enforcement/log.jsonl`, `~/.claude/.agent_budget/`,
  `~/.claude/.file_claims/` and `schedules/heartbeats/`, so a whole-root or whole-directory compare
  can never pass).** Each test run draws one marker `m` = 16 random lowercase hex and uses a fixture
  slug `gtmt-<first 8 hex of m>` (slug grammar, 00 §0.3), ids built from that slug (`apr_<fixture
  slug>_…`, `act_<fixture slug>_…`) and, where the test sends a hook payload, a `session_id`,
  `tool_use_id` and agent id each containing `m`. The oracle passes iff (i) no line appended to the
  real `~/.claude/.enforcement/log.jsonl` or to any file under the real `~/.claude/.agent_budget/`
  during the run (read from each file's byte size recorded before the run to its end; a file absent
  before is read whole) contains `m` or the fixture slug; and (ii) no path under the real `S` or the
  real `tools/gtm/` has `m` or the fixture slug in its name; and (iii) **(DECIDED (wave1e), finding
  wave1d-M6)** no **fixed-name** real file the GTM approver code writes carries `m` or the fixture
  slug in its content. **Every oracle-governed test uses the fixture slug for every slug argument,
  id and marker target — never a real slug such as `other-company`** (a regressed refusal would then
  write `S/cancels/other-company/…`, a path (ii) cannot tell from a live session's). **(ii) alone is
  not sufficient** (the wave1d text said "(ii) alone is both necessary and sufficient"; that was
  false): a file whose name the test does not choose — `S/trust_edit_allow.json` (fixed name,
  replaced by every `--sign-trust-edit`) — can be overwritten by a leak with no `m` in any path. So
  (iii): after the run, if the real `S/trust_edit_allow.json` exists, its `payload_b64` is decoded
  and the payload's `path` must not contain `m` or the fixture slug (every trust-edit test signs a
  path under a tmp directory whose name contains `m`); a file that does not parse fails (iii) only
  when its sha256 differs from the one recorded before the run (a live writer only ever writes a
  parseable marker). `S/operator_ok/<command>.<slug>.<target>.json` needs no content check: with the
  fixture slug its name carries the slug and (ii) catches it. The list of fixed-name files is exactly
  `S/trust_edit_allow.json` today; a new fixed-name file any approver code writes is added here in
  the same change. **(Dropped wave1d, kept dropped: a clause comparing the mtime of
  `S/approver_inbox/`, `S/cancels/<fixture slug>/`, `S/operator_ok/` and `S/trust_edit_allow.json`
  — real, unrelated GTM sessions write those continuously, so an mtime compare fails on false
  positives, exactly the whole-directory-mtime failure mode this oracle's preamble rules out for
  `.enforcement/`/`.agent_budget/`/`.file_claims/`/`schedules/heartbeats/`.)** The
  whole-directory form is never used.

So every test runs against a tmp `CLAUDE_DIR`, never the real `~/.claude` (00_global_paths.md
§1.5). **Trust root `T`** (00_global_paths.md §1.1 "Real root and test mode", consequence 1):
`T = gtm_env.real_root()` outside test mode, and `T = R` only in test mode. Outside test mode a
caller for which `gtm_env.same_root(R, real_root())` is false is refused exit 3 `root_mismatch`
before any step below runs (a `HOME` with a trailing `/`, a case variant or a symlink of the passwd
home is **not** test mode and **not** a mismatch, 00 §1.1). **Python and the scripts judge a
`CLAUDE_DIR` that names the real root differently (stated; 00 §1.1 `test_mode`).** For Python,
any non-empty `CLAUDE_DIR` is test mode, so `CLAUDE_DIR=<real root>/` (or a case variant) gives
`T = R` = the real root **in test mode**, and `gtm_env.refuse_real_state` refuses every write:
act.py and the `approval_sig.py` CLI exit 3 `test_mode_real_state` (00 §1.1's code for
`gtm_env.RealStateRefused`), and a read-only mode (`--trust-result`) runs. For the three scripts
and the app the same value names the real root and is production (header "Scripts"/"App"). What
the operator sees: `gtm_cancel.sh` and `gtm_approve.sh` work exactly as with `CLAUDE_DIR` unset,
while a GTM Python command in that shell refuses `test_mode_real_state` until he unsets it. A2
test: with `CLAUDE_DIR=<fixture real root>/` (`real_home()` monkeypatched), act.py `pause` exits 3
`test_mode_real_state` and writes nothing (the scripts' side is the existing parity test of the
header's same-root rule; no test runs a script against the real root). In test mode `T = R` is the **resolved** path: `approval_sig.claude_dir()`
equals `company.claude_dir()` when `CLAUDE_DIR` is set (company's set branch is
`Path(CLAUDE_DIR).expanduser().resolve()`), so with `CLAUDE_DIR=/tmp/x` on this Mac `T =
/private/tmp/x`. (company's **unset** branch returns `Path.home() / ".claude"` unresolved; the two
are then compared with `gtm_env.same_root`, never `==`, API below.) Every comparison of a path against `T` (the
code-root check of §5.5 step 0 included) therefore uses `gtm_env.same_root` or `os.path.realpath`
on both sides, never `normpath`. The test harness passes `CLAUDE_DIR` **unresolved** (e.g.
`/tmp/x`, or a `$TMPDIR` path under `/var/folders`), so these rules are exercised by every tmp-tree
test. Every `HEAD:` read, the working-tree walk of §5.5 steps 1–2 and every key
lookup use `T`, never `R`; state (`S`) stays under `R`. So a tmp `CLAUDE_DIR` holding an
agent-generated key selects test mode, and test mode never reaches a connector (00 §1.1 consequence
2; its P2 test (a) is also an A2 test of this section). **Enable flag:** the tier-table row flag and the
request's display flag are both named `commits_on_enable` (03_schemas.md §3.4.1, the name 03 uses
in every row; `display.commits_on_enable`, 03_schemas.md §3.7). One name everywhere; if 03 ever
renames it, this file changes in the same commit.

**Formats (every Swift and Python implementer uses exactly these).** Hex is always lowercase. A key
fingerprint is `"sha256:" + <64 lowercase hex>`. Every timestamp this section writes or compares
(`expires`, `signed_at`, `valid_from`, `valid_until`, `S/approver_fingerprint.json`
`exported_at`, heartbeat `started_at`/`finished_at`/`app_started_at`, `S/PAUSE.trust` `ts`, the nonce-ledger line `ts` written by this section's
`reserve`/`consume`/`release`/`quarantine`, the cancel-marker `ts` written by `gtm_cancel.sh` and the
app's menu, and `S/trust_tree_seen.json` `ts`) is UTC `%Y-%m-%dT%H:%M:%SZ` (whole seconds, `Z`), the
form `heartbeat_audit._UTC_TS_RE` accepts. **Every time comparison in this file** (`expires > now`,
the retired-key rule's `consume ts < valid_until`, `reserved_after_expiry`'s reserve `ts` against
`expires`, heartbeat staleness, …) **parses both sides** with `datetime.strptime(v,
"%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)` (the 00_global_paths.md §0.3 / `gtm_env.now`
form) into aware UTC datetimes and compares those, never the strings (00 §0.3). An unparsable value
fails closed: it is the refusal the comparison guards (`key_retired`, `reserved_after_expiry`,
`approval_expired`, `malformed_record` for a record field), never a pass. `MINT_MARGIN = WRITE_TICKET_TTL + 5 min` (= 35 min;
`WRITE_TICKET_TTL` = 30 min, 03_schemas.md §3.6) is the one named mint threshold (§5.5 step 5).
**Swift canonical JSON (DECIDED (wave1c)).** The app builds and signs three payloads itself
(`trust_edit`, `operator_ok`, self-test); their bytes must equal Python's `canon` (00_global_paths.md
§0.3: `json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, UTF-8). The app
emits them with a hand-written encoder (or `JSONSerialization` with `[.sortedKeys,
.withoutEscapingSlashes]`, only while the parity test below passes): keys sorted by Unicode code
point (every key here is ASCII); separators `,` and `:` with no whitespace; `/` never escaped;
string escapes exactly Python's — `\"`, `\\`, `\n`, `\r`, `\t`, `\b`, `\f`, any other code point
below U+0020 as `\u00xx` (lowercase hex), everything else, non-ASCII included, as raw UTF-8; `v` the
integer `1`; `self_test` the literal `true`; every other value a string. **Every consumer refuses
non-canonical bytes before its key-set check:** `verify_signature` (3a: `non_canonical`, then
`bad_keys`), `approval_sig.py --verify-trust-edit` and `approval_sig.py --self-test` (reason
`non_canonical`, exit 7), and the operator-marker validation of 00_global_paths.md §1.4 (2)
(canonical first, then the key set; R83). C↔A2 parity test (RED when the encoder escapes `/` or
orders keys otherwise): for a test-build trust-edit marker whose path has several `/`, an
operator-ok marker and a self-test file, the decoded signed bytes `b` satisfy `b ==
canon(json.loads(b))`, and the trust-edit marker is refused by `verify_signature` with `bad_keys`,
never `non_canonical`.

### 5.1 Flow

1. `authorize` (A2 `approvals_verify.create_request`) writes the request (03_schemas.md §3.7) and a
   `money_card` notice (push) — or, when `urgency == "urgent"`, a `runaway_spend` notice (severity
   `urgent`, push), also in shadow (02_act.md §2.6 rule 6). **Operator-executed actions
   (`display.operator_executes: true`, §5.5 step 3b "Operator-executed actions"):** that notice and
   the mirrored human card begin, verbatim, "You make this change yourself after approving — agents
   cannot make it on <system>." and then carry the prepared change exactly as §5.8's card does
   (account, `object_ref`, the new value and unit or the change in `after_full`, click path and
   snapshot paths), ending "Approve in GTMApprover first; the daily run checks the platform and
   closes this request once the change is visible." — for a regulated pack only the fields the rule
   below allows, with the object, values, click path and snapshot paths on the home-surface card
   only (§5.8). **Regulated packs (`regulated ∋ hipaa`,
   plan §20.4):** the notice body and the macOS notification carry only `company_display`, `system`
   and the amount (or "no amount"); never `after`, metrics or any text derived from an untrusted
   input. For such a pack **every string value of `money_brief`** (03_schemas.md §3.2: title and
   `object` via `object_display`, `metrics_summary`, `best_practice_source`, `expected_effect`,
   `risk`, `reversal`), and every untrusted-input string in `after_full`, is stored in `display` as
   the 03_schemas.md §3.15 side-store form `{"digest": "sha256:<hex>", "pointer":
   ".claude/gtm/state/untrusted/<unt_id>.txt"}`, never as text. **How the app shows them (DECIDED
   HERE, option (a)):** in the NSAlert body only, the app resolves each pointer read-only against the
   company's home `H`, found by a Swift port of the 00_global_paths.md §0.1 **`company.gtm_slugs()`
   admission** ("Registry inputs of `gtm_slugs()`", cases (1)–(7)) followed by that entry's root —
   **not** a port of `company.resolve_home`, which admits every repo-registry slug and has no
   `repo_registry_slugs` allowlist — with exactly these inputs and refusals, **in this order, the
   first refusal winning** (the token is the `<reason>` rendered below):
   (a) **grammar first:** the request's slug must match the 00_global_paths.md §0.3 slug grammar
   `^[a-z][a-z0-9-]{1,31}$` (= `system_names.SLUG_RE`), else `bad_slug` — checked before either
   registry is read, so a bad slug is `bad_slug` whether or not it is registered;
   (a1) **registry files:** `R/knowledge/gtm_company_registry.json` missing → no GTM-registry
   slugs; `R/knowledge/repo_registry.json` missing → no repo-registry slugs (00 §0.1 cases (1),
   (3)); either file present but unreadable, not valid JSON, or valid JSON that is not an object,
   or whose `companies` (respectively `repos`) value is present but not an object →
   `registry_unreadable` (00 §0.1 case (6): the repo registry is read whenever it exists, for the
   duplicate check, whether or not `repo_registry_slugs` is present);
   (a2) **admission:** the slug is admitted when it is a key of the GTM registry's `companies`, or a
   key of the repo registry's `repos` **and** a member of the GTM registry's `repo_registry_slugs`;
   `repo_registry_slugs` absent, or not a list of strings, admits **no** repo-registry slug (00
   §0.1 case (2)); a repo-registry slug not so admitted, and a slug in neither registry, →
   `not_registered`; a slug that is a key of **both** `companies` and `repos` → `registry_conflict`
   (00 §0.1 case (4); checked before admission, so it wins over `not_registered`);
   (b) the entry must be a JSON object whose `root` is a non-empty string, else
   `registry_entry_invalid`; a `root` starting with `~` that is not exactly `~` and does not start
   with `~/` (the `~user` form, `~x`, `~+`; 00 §0.1 "The `~user` form is refused") → **`tilde_user_form`**,
   before any expansion; otherwise `~` is expanded against the **passwd home** (`getpwuid`, as
   `gtm_env.real_expand`), never `HOME`, and a root that is not absolute after expansion →
   `registry_entry_invalid`;
   (c) **Agency-root exclusion, text only, before any stat or open (plan §20.9a, 00 §0.1):** the
   compare is an **exact Swift port** of 00_global_paths.md §0.1 `gtm_env.norm_text`, `is_under`
   and `is_ancestor` — `norm_text(s)` = `strip_firmlink(posixpath.normpath(s).casefold())` with Python's normpath rules
   (empty and `.` components dropped, `..` pops, exactly two leading slashes kept, three or more
   collapsed), Unicode `casefold` (Swift `lowercased()` is **not** a substitute for non-ASCII text:
   a root containing any non-ASCII scalar is refused `registry_entry_invalid`, so ASCII folding is
   exact) and the firmlink strip (`/system/volumes/data` → `/`, a `/system/volumes/data/` prefix
   removed); `is_under(a, b)` = `a == b || a.hasPrefix(b` without trailing `/` `+ "/")`;
   `is_ancestor(a, b)` = `a != b && b.hasPrefix(a` with **every** trailing `/` stripped `+ "/")` —
   the exact port of 00 §0.1's one ancestor test (`b.startswith(a.rstrip(os.sep) + os.sep)`), so a
   root of `/` (stripped to empty) is an ancestor of every absolute path. **Never** the hand-written
   form `hasPrefix(a + "/")`, which 00 §0.1 names as the variant that misses `/` (it tests for a
   `//` prefix). A C parity test runs the Swift functions and the Python ones over one shared case
   list (a `.`, a `..`, a `//` and a `///` prefix, a case variant, a `/System/Volumes/Data` prefix in
   two casings, and for `is_ancestor` the roots `/` and `//` against `A`, `/users/u/desktop`
   against `/users/u/desktop/agencyx` → true and `/users/u/desktop/agency` against
   `/users/u/desktop/agencyx` → false) and requires equal output; a second C test, RED under the
   hand-written form, renders a fixture registry root `/` as `(text unavailable: agency_home)`. With
   `A` = `<passwd home>/Desktop/OtherApp`, the expanded root is refused `agency_home` when
   `is_under(norm_text(root), norm_text(A))` (**equal to or under**) **or**
   `is_ancestor(norm_text(root), norm_text(A))` (**an ancestor** of `A`, e.g. a hand-edited root
   `~/Desktop` or `/`: the 00 §0.1 `gtm_slugs()` ancestor arm) — no `stat`, `open`, `realpath` or
   directory listing of that root ever runs. Both arms are checked against `A` **and**
   `real_agency_root()` (`<passwd home>/Desktop/OtherApp`); in the **test build** `~` and `A` follow
   00 §0.1's test-mode split (`HOME`-derived), and the passwd-home `A` is checked as well, both text
   only (00 §1.1 consequence 3's "both Agency roots" rule);
   (c2) **PHI-folder exclusion, text only (plan §20.3; 03_schemas.md §3.20):** the app reads
   `S/phi_denylist.json` and refuses **`phi_home`** when `norm_text(root)`, or `norm_text(root +
   "/" + pointer)`, is equal to or under (`is_under`) the `norm_text` of any `paths` entry — the
   same text-only compare as (c), no `stat` or `open` of the root. The file missing, unreadable,
   not valid JSON, or with `paths` not a list of absolute strings → `phi_denylist_unreadable` (fail
   closed; pointers exist only for regulated packs, 03 §3.20 "never fails open"). C test (RED when
   the check is removed): a fixture `phi_denylist.json` whose `paths` holds the fixture home's own
   root renders `(text unavailable: phi_home)` and the fs recorder shows no `stat`, `open`,
   `openat` or `realpath` call on any path equal to or under that entry; the file absent renders
   `(text unavailable: phi_denylist_unreadable)`;
   (d) only then `H = realpath(root)` (company.py returns `Path(root).expanduser().resolve()`),
   and a realpath for which either arm of (c), or (c2), holds (same compares, both Agency roots) is
   refused `agency_home` (respectively `phi_home`) without opening anything under it (the 00 §0.1
   accepted residual: `realpath` itself follows the symlink).
   (e) **Pointer grammar:** the `pointer` string must match exactly
   `^\.claude/gtm/state/untrusted/unt_[a-z][a-z0-9-]{1,31}_\d{8}T\d{6}Z_[0-9a-f]{6}\.txt$`
   (the 00 §0.3 untrusted-item id with the §0.3 slug grammar; no `..`, no other directory), else
   `bad_pointer`, before anything is opened.
   (f) **Open by descent, never by path:** the app opens `H` with `open(H, O_RDONLY | O_DIRECTORY)`
   and then each component of the pointer (`.claude`, `gtm`, `state`, `untrusted`, the file) with
   `openat(dirfd, component, O_NOFOLLOW | O_RDONLY)` (`| O_DIRECTORY` for every directory
   component), so a symlink at **any** component — e.g. `H/.claude/gtm/state/untrusted` linked into
   the Agency tree — fails with `ELOOP` and is refused `bad_pointer`; the final descriptor must be a
   regular file (`fstat`). It then requires `"sha256:" + sha256(bytes)` to equal the pointer's
   `digest` (so the rendered text is still bound through `display_sha256`). Any failure (home
   unresolved, file purged, digest differs, any refusal above) renders `"(text unavailable:
   <reason>)"` for that field; Approve stays available, because the binding fields (`object_ref`,
   the values, `unit`, `account_id`) are never pointers and are always shown. Resolved text is **never** shown in the macOS
   notification, the menu-bar list, `GTM_Operator.html` or any log, and never cached (read at
   render, dropped when the alert closes). Test (C): a OtherCompany-fixture request, whose company is
   registered **only** in the fixture `gtm_company_registry.json` (not in `repo_registry.json`),
   shows the fixture's human-readable `risk` and `reversal` text in the alert body (RED when the
   port reads `repo_registry.json` only), and none of that text appears in the notification
   payload, the menu-bar item title or any file the app writes. Test (C): a fixture whose GTM
   registry entry's root is `~/Desktop/OtherApp/x` (expanded against the test build's tmp `HOME`)
   renders `(text unavailable: agency_home)`, and the test build's file-access recorder
   (§5.3 `GTM_TEST_BUILD` seams) shows no `stat`, `open` or `realpath` call on any path equal to or
   under that `A`; a slug present in both fixture registries renders `(text unavailable:
   registry_conflict)`. Tests (C, each RED when its rule is removed; the fs recorder must show no
   `stat`, `open`, `openat` or `realpath` call on any path equal to or under either fixture Agency
   root): a registry root `/System/Volumes/Data<tmp HOME>/Desktop/OtherApp/x` → `(text unavailable:
   agency_home)` (RED without the firmlink strip); a registry root `~/Desktop` (an ancestor of `A`)
   → `agency_home` (RED without the ancestor arm); a pointer `.claude/gtm/state/untrusted/../../../x`
   → `bad_pointer`; a fixture home whose `.claude/gtm/state/untrusted` is a symlink to a directory
   under the fixture `A` holding a file with the right name and digest → `bad_pointer` (RED when only
   the last component carries `O_NOFOLLOW`). Tests (C, one per refusal token, each RED when its
   rule or its position in the order is changed): a slug `9x` that is also unregistered →
   `bad_slug` (grammar first); a 33-character slug → `bad_slug`; a GTM registry whose top level is a
   JSON list → `registry_unreadable`; a repo-registry-only slug with `repo_registry_slugs` absent,
   and again with it set to the string `"exampleapp"`, → `not_registered`; a slug in both
   registries whose repo entry is not allowlisted → `registry_conflict`; a root
   `~x/Desktop/x` → `tilde_user_form` with no `getpwnam` call and no fs-recorder entry; a
   root `Desktop/x` → `registry_entry_invalid`; and a C test that the app's compiled slug pattern
   string equals `system_names.SLUG_RE.pattern` (RED when either drifts).
   After 30 days `purge-untrusted` redacts `display`/`display_b64` of
   such a pack's **terminal** requests (`approved` and consumed, `denied`, `expired`, `superseded`),
   keeping `payload_b64` and the approval record, so consumed records still pass `verify_signature`,
   which never reads `display` (R16).
2. **GTMApprover** watches `S/approval_requests/*/` and `S/notices/*/` (DispatchSource/FSEvents +
   a 30 s poll). A request is *pending* iff `status == "pending"`, no file exists at
   `S/approvals/<slug>/<request_id>.json`, and the decoded payload's `expires > now`. A request past
   `expires` is shown greyed as expired and offers nothing. A new pending request raises an NSAlert
   (Approve / **Deny = default button**) and a macOS notification. Dismissing leaves it in the
   menu-bar list.
3. **What the app shows, and what it checks before it offers Approve (every check must pass; a
   failure shows "Cannot approve: <reason>" and offers Deny only).** The app decodes `payload_b64`
   and `display_b64` (R10) and renders **only** from those decoded bytes; it never re-serializes JSON
   and ignores the plain `display` object (that copy exists for `GTM_Operator.html`).
   - `sha256(decoded display bytes)` equals the payload's `display_sha256` (R10);
   - the payload's key set is exactly the 12 keys of §5.5 step 3a, and each value has the 03_schemas.md
     §3.7 type;
   - `payload.company` equals the request's directory slug and `request.company`;
     `payload.card_id == request.request_id ==` the file name stem; `payload.action_id ==
     request.action_id`;
   - every field present in both the payload and the decoded display (`system`, `account_id`,
     `new_absolute_value`, `unit`) is equal;
   - `payload.expires > now`;
   - **enable** (`display.commits_on_enable: true`, set by A2 as `tiers.is_enable_action(ctx,
     action, row)`, the one 03_schemas.md §3.2 "Enable actions" predicate — §5.5 step 3b "Enable
     binding"; 03_schemas.md §3.7 — never from `money_brief`):
     `display.current_value` equals the payload's `new_absolute_value`;
   - **still undecided (re-read, not remembered):** the request file's `status` is `pending` and no
     file exists at `S/approvals/<slug>/<request_id>.json`. The app re-reads both **immediately
     before `evaluatePolicy`** and **again immediately before `link()`** (step "Publication"
     below). A request that became `denied`, `superseded` or `expired`, or gained a decision
     record, while its alert was open is never signed: the app shows "no longer pending:
     <status>" and publishes nothing. Test (C): a request set to `superseded` while its alert is
     open, then Approve → no `evaluatePolicy` call and no record; the same with the request set to
     `denied` between `evaluatePolicy` and `link()` → no record (the signature is discarded).

   Shown: **first, above the title**, `display.shared_warning` when that key is present
   (03_schemas.md §3.7: present only on a money action with non-empty `check1.shared_hits`, absent
   otherwise), as "This change touches a shared or other-company system" (03_schemas.md §3.7's
   heading text verbatim; one text in both files) followed by each hit's
   `where`, `value`, `relationship` and `ruling_ref`. `shared_hits` holds only values declared in
   the pack's `shared_identifiers` (03_schemas.md §3.4.3); an **undeclared** other-company
   identifier is NEVER-class, refused at check 1 (plan §6.3, §20.6), and never produces a request,
   so the app never shows one (03 R42; it is inside `display`, so
   `display_sha256` and 3b's `build_display` recompute bind it); then the title and `object` from `money_brief` (labelled "description"); `display.object_ref`,
   the action's structured target taken verbatim from the action's `target_ref` and verified
   `id_fields` (R10), labelled "object"; **`account_id` on its own labelled line ("account")**, in
   the alert and in the menu-bar item (plan §2: the operator's other businesses share his
   identities, so the account is the isolation fact he must see; it is never assumed to be inside
   `object_ref`); current and new value with unit; and `display.after_full`, the untruncated
   `canon(after)` text in a scrollable view (R10; for a regulated pack, untrusted-input text in it is
   a pointer, resolved in the alert body only, step 1). `after_summary` (≤ 400 chars) is only a
   heading, never the only view of the change. **Operator-executed actions**
   (`display.operator_executes: true`, §5.5 step 3b): the alert body's **first** line, above
   `shared_warning`, is "You make this change yourself after approving — agents cannot make it on
   <system>. After you approve, make it in <system> (account <account_id>); the daily run checks the
   platform and closes this request once the change is visible.", and the alert shows the prepared
   change (click path and snapshot paths from `display`) below `after_full`.

   **Approve** → one fresh presence check per signature: a new `LAContext` with
   `touchIDAuthenticationAllowableReuseDuration = 0`, `evaluatePolicy(.deviceOwnerAuthentication,
   localizedReason: …)` (Touch ID **or the login password**, as plan §20.8 intends; UI automation
   cannot satisfy either), and that evaluated context is passed as `kSecUseAuthenticationContext`
   to the key lookup and so to `SecKeyCreateSignature`, so the operator sees exactly one prompt and
   it names the amount. The reason string is built from payload values only (plus
   `display.company_display` and `display.object_ref`), **in a fixed field order so that a system
   dialog that truncates the string cuts only the tail:** amount (or digest), then `account_id`,
   then company, then system, then `object_ref`. `<ref80>` = `display.object_ref` cut to its first
   80 characters plus `…` when longer (the full value stays in the alert body). **When
   `display.operator_executes` is true**, the chosen variant below is prefixed, verbatim, with
   `"You make this change yourself after approving — "` (so the one prompt the operator sees says
   that agents will not execute it):
   - amount: `"Approve <new_absolute_value> <unit> — account <account_id> — <company_display> (<company>) <system> <ref80>"`;
   - amount-less (`new_absolute_value` null, 03_schemas.md §3.7; §5.5 step 3b null rule):
     `"Approve change (no amount), digest <after_digest[7:19]> — account <account_id> — <company_display> (<company>) <system> <ref80>"`;
   - enable: `"Enable and commit <new_absolute_value> <unit> — account <account_id> — <company_display> (<company>) <system> <ref80>"`;
   - **pause / stop** (`display.resulting_status == "paused"`; `display.resulting_status` is the
     matched tier row's **authored** `resulting_status` (03_schemas.md §3.4.1), copied verbatim by
     A2's `build_display` and bound by `display_sha256` (03 §3.7 display key table), absent for
     `_nomatch` — **never** derived from verb tokens, the action's name or `money_brief`
     (DECIDED (wave1e), finding wave1d-B3: the wave1d text chose this variant from
     `display.change_kind`, a verb-token scan, so a `remove_end_date`-shaped row that resumes or
     uncaps spend would have been shown as "Remove (stop spend)"); a pause is signed as the
     resulting value, amount 0, plan §20.13, while the platform budget itself stays unchanged,
     §5.8): `"Pause (stop spend), sign <new_absolute_value> <unit> — account <account_id> —
     <company_display> (<company>) <system> <ref80>"`; shown as `Pause (stop spend)` with the signed
     value beside it;
   - **remove** (`display.resulting_status == "removed"`, the same field):
     `"Remove (stop spend), sign <new_absolute_value> <unit> — account <account_id> — <company_display>
     (<company>) <system> <ref80>"`; with a null amount the `sign …` phrase is replaced by the
     amount-less digest phrase;
   - **any other `display.resulting_status`** (`active`, `unbounded`, `unchanged`, or absent) never
     selects either variant above and no reason string, alert heading or menu-bar label contains
     `stop spend`: the action takes the enable, amount or amount-less variant by its own facts
     (`display.commits_on_enable`, `new_absolute_value`). `display.change_kind` and
     `tiers.change_kind` are **withdrawn** (`requests/05_approver.md` R76 (b) withdrawn wave1e; 03 §3.7
     now carries `resulting_status` instead). **A2 test (RED when the variant is chosen from verb
     tokens or `change_kind`):** a tier row `meta.remove_end_date` authored `resulting_status:
     "unbounded"`, `commits_on_enable: false`, a `$` amount → the reason string starts `"Approve "`
     and no rendered string contains `stop spend`; the same row with `commits_on_enable: true`
     (and a configured ceiling) → the enable variant, again without `stop spend`; a row
     `google_ads.campaign_remove` (`resulting_status: "removed"`) → `"Remove (stop spend), sign
     0.00 …"`; a row `google_ads.campaign_pause` (`"paused"`) → `"Pause (stop spend), sign 0.00 …"`;
   - AI-spend **zero cap** (`system == "gtm_ai"` and `new_absolute_value == "0.00"`; a signed
     `"0.00"` is a zero cap — budget state from the first dispatch, lead capture only —
     07_notices_schedules.md §7.2 "A signed `"0.00"` is a zero cap", which supersedes the earlier
     "no cap" reading; requests/07_notices_schedules.md R33): `"Approve $0.00 / week — ZERO CAP:
     every GTM AI dispatch stops except lead capture — account <account_id> — <company_display>
     (<company>) gtm_ai"`. The alert and the menu-bar list show the new value as `$0.00 / week —
     ZERO CAP: every GTM AI dispatch stops except lead capture`, never `NO CAP`.
   - AI-spend **report-only** (`system == "gtm_ai"`, `new_absolute_value` null and `unit ==
     "report_only"`, null case (iv) of §5.5 step 3b; 07 §7.2, requests/07_notices_schedules.md R34):
     `"Approve NO CAP — report only, unlimited AI spend — account <account_id> — <company_display>
     (<company>) gtm_ai"`; shown as `NO CAP — report only, unlimited AI spend`, never `$0.00` or
     `0.00 USD/week`.
   **Selection order (one total order; the first variant whose condition holds is used):**
   report-only, then ZERO CAP, then enable (`display.commits_on_enable`), then pause
   (`display.resulting_status == "paused"`), then remove (`display.resulting_status == "removed"`),
   then amount-less, then amount. (So a `gtm_ai` `"0.00"` request is ZERO CAP, never the amount
   variant; an enable with an amount is the enable variant; an amount-less remove is the remove
   variant with the digest phrase.)
   Tests (C), each RED when the two `gtm_ai` texts are swapped: a zero-cap request's dialog text
   and reason string contain `ZERO CAP` and not `NO CAP`; a report-only request's contain `NO CAP —
   report only` and no `0.00`. Tests (C) for every overlapping pair, each RED when the pair's order
   is inverted: report-only vs amount-less (a report-only request's reason starts `Approve NO CAP`);
   ZERO CAP vs amount (a `gtm_ai` `"0.00"` request's reason contains `ZERO CAP` and does not start
   `Approve 0.00`); enable vs amount (an enable request's reason starts `Enable and commit`); pause vs
   amount (a campaign pause request's reason contains `Pause` within its first 120 characters and
   does not start `Approve`); remove vs amount-less (an amount-less remove request's reason starts
   `Remove (stop spend)` and carries the digest).
   Tests (C): for every variant above, the reason string contains the payload's `account_id`; and
   the amount phrase (`<new_absolute_value> <unit>`, the digest, `ZERO CAP`, `NO CAP`, `Pause` or `Remove`) and the `account_id`
   both lie within the first 120 characters (the first 170 when the operator-executed prefix is
   present), for a fixture whose `company_display` and `object_ref` are each 200 characters long.
   Tests (C, each RED when the prefix is removed): an `operator_executes: true` enable request's
   reason string and alert body both begin `You make this change yourself after approving —`; the
   same request with `operator_executes: false` begins `Enable and commit`.
   **One clock read.** The app captures `now` **once**, immediately after `evaluatePolicy`
   succeeds, truncates it to whole seconds, and derives every time it writes for that decision from
   that one value (`signed_at` of a `$` record; `signed_at` and `expires = now + 15 min` of a
   trust-edit or operator marker, §5.3).
   Then sign the **decoded `payload_b64` bytes verbatim** and publish the 03_schemas.md §3.8 record.
   **Deny** → publish the denial record (no Touch ID; a denial only prevents).

   **Publication is create-exclusive (a decision is final).** `S/approvals/<slug>/` is created with
   mode 0700. The app writes a temp file (0600) in that directory, then `link()`s it to
   `<request_id>.json` and unlinks the temp. `EEXIST` means an earlier decision stands: the app
   discards its own, shows "already decided: <decision>", and never overwrites. Reconsidering needs
   a new request. This also covers a double click and an alert/menu race. An approval record that
   stands can still be **revoked** before its nonce is consumed, but **only through the operator's
   two cancel channels** — the menu-bar **Revoke** (§5.2) and `gtm_cancel.sh` (§5.4) — never by a
   card answer (step 5), an agent cancel, or an empty/hand-made marker (step 5 "Cancelling a `$`
   request"); the record file itself is never rewritten, the revocation lives in the request's
   `status`.
4. act.py verifies per §5.5 at every stage in the step-5 table.
5. **Answers on the mirrored human `$` card never decide anything (plan §20.8: "`record-external`
   kind (b) never applies to `$` … archive entries in OPERATOR_DECISIONS.md are for humans only";
   plan §20.6: stopping spend is a `$` decision only the operator makes; DECIDED in 02_act.md §2.11
   and adopted here verbatim, requests/02_act.md item 87).** The session mirrors each request as a
   human card under the same id (03_schemas.md §3.7). An answer there is read by `act.py
   record-external --kind approval --card <request_id>` with the 02_act.md §2.6 decision grammar.
   **Every answer first requires the card's posted subject to equal `approval <request_id>`**; any
   other subject (or none) → exit 3 `card_subject_mismatch` and nothing changes. An unanswered card
   → exit 3 `card_unanswered`. Then, for **every** answer — `approve`, `deny` and `unclear` alike —
   act.py does exactly two things and nothing else, and exits 0:
   - writes `S/approver_inbox/show.<request_id>` (0600; the app re-shows the alert and deletes the
     marker). `S/approver_inbox/` is created mode 0700 by whichever writer comes first (act.py here,
     `gtm_approve.sh` in §5.4, both via `mkdir` with mode 0700 and no error on `EEXIST`). R60 asks
     00's `S` layout to list act.py (`record-external --kind approval`) as a writer of
     `approver_inbox/show.*` beside `gtm_approve.sh`;
   - writes one notice through the 07_notices_schedules.md §7.1 in-process writer: slug = the
     request's company, kind `info`, severity `info`, `push: false` (the app's re-shown alert is the
     operator-facing signal), title exactly `"Approve or deny <request_id> in GTMApprover on the
     Mac (Touch ID)"`, body exactly `"A card answer cannot approve or deny a $ request. Approve or
     deny <request_id> in GTMApprover on the Mac (Touch ID). To cancel it without deciding, run
     gtm_cancel.sh <action_id> <slug> in your terminal, or let it expire at <expires>."` (for a
     regulated pack the same text: it carries only ids and a timestamp, §5.1 step 1 rule),
     `dedupe_key = "approval_reshow:<request_id>"` (R79 asks 07 to reserve the prefix for
     in-process writers), `created_by: "act"`.
   It appends **no** event, publishes **no** decision record (there is no `decided_via: "card"`
   record form anywhere in this file; a denial record is only ever the app's, `decided_via:
   "app"`, 03_schemas.md §3.8), writes **no** cancel marker, and leaves the request's `status`, the
   action's state and the nonce ledger unchanged, **whatever the answer says and whether or not the
   request is already signed or its nonce reserved or consumed**. So an agent-archived or
   mis-archived "No" can neither kill a pending urgent runaway-spend stop before the operator
   presses Approve, nor undo one he signed; a "Yes" never approves. Denial of a `$` request happens
   **only** in GTMApprover (Deny is its default button) and reaches the chain only as an app denial
   record (`approval_denied`, at `authorize`/`run-holds`, 02_act.md §2.11); cancelling without
   deciding happens only through the operator's cancel channels below. The earlier card-deny
   branches (`card_deny_after_approval`, `card_deny_after_quarantine`, `card_deny_after_consume` and
   their notices) are removed; 05 writes no `card_deny:` notice and no `who: "card_deny"` marker
   (R75/R76/R79 ask 02, 03 §3.7/§3.11 and 07 to drop what they carry for them).
   A2 tests (each RED when a deciding branch is restored): a mirrored card answered "Yes" and one
   answered "No" on an undecided request both leave the request `pending`, the action
   `awaiting_approval`, no record at `S/approvals/<slug>/<request_id>.json`, and exactly one
   `show.<request_id>` marker and one open `approval_reshow:<request_id>` notice; **an
   agent-archived "No" on an `urgency: urgent` request** (a campaign pause, amount `"0.00"`) leaves
   it pending and appends no `approval_denied`, and the app then signs it and `execute` records the
   pause on the platform fixture; the app approves, then a card "No" before any ticket →
   `ticket --write` mints and `execute` runs, no cancel marker exists, and the next G-A-admitted
   call of an already minted ticket is still allowed; a card "No" after a success consume and after
   a quarantine → the request, the action and the ledger are byte-identical before and after; a
   card "No" posted with subject `authorize <action_id>` → `card_subject_mismatch`, no marker, no
   notice.
   **Cancelling a `$` request.** Plan §20.7's "cancelling only prevents, so it may come from any
   channel" is read, for a `$` request **the operator has signed**, as scoped to the operator's own
   cancel channels: the menu-bar **Revoke** (§5.2, `who: "approver_menu"`) and `gtm_cancel.sh
   <action_id> <slug>` (§5.4, `who: "operator_script"`). This reading is a **stated, unratified
   deviation from the letter of plan §20.7** (Deviation register, §5.9, entry V1). An **unsigned**
   `$` request keeps plan §20.7 as written: any cancel channel, an agent's `act.py cancel`
   included, cancels it (02_act.md §2.4 `cancel`; the agent cancel is listed in the weekly report,
   plan §20.7), and the operator's own channel for it is `gtm_cancel.sh`.
   When act.py ingests a cancel marker (03_schemas.md §3.11) for an action whose request is
   `pending`, it classifies (DECIDED (wave1c): every cell has one outcome) **`who`** as *operator*
   (`operator_script`, `approver_menu`) or *agent-class* (`agent`, `card_deny`, `hand_made_file`,
   `system:responded_by`, **and any other value** — unknown, misspelled or absent), and the
   **record state** at `S/approvals/<slug>/<request_id>.json` as *none* (no file), *denial*
   (`decision == "denied"`, published by the app and not yet ingested at `authorize`/`run-holds`),
   *approved-unconsumed* (`decision == "approved"` and the payload nonce has no `consume` line in
   `S/approval_nonces.jsonl`, reserved or not; a record file that does not parse counts here, so an
   operator cancel still prevents), or *approved-consumed* (a `consume` line exists: while the
   request is still `pending` this is the quarantine of §5.5 step 5, since a success consume sets
   `approved`). Outcomes: operator × approved-unconsumed → revoke (first bullet); any × none →
   cancel (second bullet); agent-class × approved-unconsumed → no change (third bullet); any ×
   denial and any × approved-consumed → no change (fourth bullet):
   - **`who` ∈ {`operator_script`, `approver_menu`} and the request has an approval record whose
     nonce is not consumed (revocation)** → act.py sets the request `status: "denied"` and the
     action `cancelled`, appends `approval_revoked {request_id, who}`, and from then on `verify`
     refuses the request at every stage (§5.5 step 3b, `request_denied`); an in-flight write ticket
     is stopped by G-A rule 6b on the same marker. It **always** writes one notice (07 §7.1 record):
     slug = the request's company, kind `agent_cancel`, severity `urgent` when the request's
     `urgency == "urgent"`, else `warn`, `push: true`, title exactly `"Approval <request_id> was
     revoked via <who>"`, body exactly `"Your Touch-ID approval of <request_id> (<new_absolute_value>
     <unit>, or "no amount", account <account_id>) was revoked by a cancel marker that says it came
     from <who>. If you did not do this, the change will not happen: ask for a new request and
     approve it again, and check who can write S/cancels/."` (regulated pack: the same text — ids,
     amount and account only), `dedupe_key = "approval_revoked:<request_id>"` (07 §7.1 already
     reserves the prefix, R65), `created_by: "act"`. **Why always (stated):** `who` is the marker's
     own content, so a marker written by an agent that evaded G-B rule c (a `python -c` with a
     built-up path, §5.6 "What stays detect-after") can claim either operator channel; the pushed
     notice is what makes such a forged revoke of an operator-signed urgent stop visible at once
     rather than only on `GTM_Operator.html`. When the nonce was **reserved** (a ticket in flight),
     the later `complete` still records what actually happened on the platform (step-5 table,
     `complete` row) and writes a second notice: kind `cancel_too_late`, severity `urgent`, `push:
     true`, title exactly `"Approval <request_id> was revoked after the change began — it may be
     live"`, body exactly `"The change for <request_id> on <system> (account <account_id>) ended
     <completed|failed> after you revoked it. Check <system>; if the change is live and you do not
     want it, run act.py revert."`, `dedupe_key = "revoked_late:<request_id>"` (R79 reserves it),
     `created_by: "act"`;
   - **any `who` and the request has no decision record (an unsigned request)** → act.py sets the
     action `cancelled` (02_act.md §2.5 table) **and** the request `status: "denied"` (so the app
     stops offering Approve for a cancelled action), appends `request_cancelled {request_id, who}`
     and writes the same pushed notice with title `"Request <request_id> was cancelled via <who>"`
     and `dedupe_key = "approval_revoked:<request_id>"` (so an agent's cancel of an unsigned urgent
     stop is never silent either; R75 asks 02 for the event and the request-status write);
   - **agent-class `who` (`agent`, `card_deny`, `hand_made_file`, `system:responded_by`, or any
     other value) and the request has an approval record with an unconsumed nonce** (an `act.py
     cancel`, the stdlib fallback cancel, an empty or hand-made file, a marker with an unknown
     `who`) → **never** cancels it: the marker is recorded (`who`)
     and deleted, the request and action are unchanged, and G-A rule 6b does not stop the action's
     ticket for it (04_hooks.md `ticket_cancelled`, applied wave1e: the same operator/agent-class split,
     keyed on the pre-lock rule-7a `signed_required`). `act.py cancel` (`who: "agent"`) of such an action is refused
     exit 3 `approval_stands` with nothing written, in the normal path **and** in the stdlib
     fallback (§5.5 step 0 "`cancel`"). An empty/hand-made file therefore cancels holds and unsigned
     actions (as 03 §3.11 already allows), never a signed, unconsumed `$` approval (R76 asks 03 to
     state that exclusion).
   - **any `who` and the record is a denial, or approved with its nonce consumed (quarantined)** →
     the marker is recorded (`who`) and deleted exactly as in the third bullet; the request, the
     action and the nonce ledger are unchanged, no event is appended and no notice is written. A
     denial is ingested as usual at the next `authorize`/`run-holds` (the action ends `denied`); a
     quarantined request's spent nonce already refuses every stage (`nonce_replay`) and its urgent
     quarantine notice (§5.5 step 5) already tells the operator to re-approve.
   A2 tests (each RED when its rule is reverted): app approves, then `gtm_cancel.sh <action_id>
   <slug>` → `ticket --write` and `execute` both exit 7 `request_denied`, an `approval_revoked`
   event with `who: "operator_script"` exists, and the open pushed `approval_revoked:<request_id>`
   notice is `urgent` for an `urgency: urgent` request and `warn` otherwise; an **empty** file at
   `S/cancels/<slug>/<action_id>` for an approved, unconsumed urgent pause → nothing revoked,
   `execute` succeeds (RED when `hand_made_file` still revokes); a marker whose content says `who:
   "operator_script"` but was written by the test with Python `open()` (as an evading agent could)
   → revoked **and** the pushed notice exists (the stated residual, observed); `act.py cancel
   <action_id>` on an approved, unconsumed action → exit 3 `approval_stands`, request unchanged;
   `gtm_cancel.sh <action_id> <slug>` on an **unsigned** pending request → request `denied`, action
   `cancelled`, `request_cancelled` event, and the app no longer offers Approve; **new cells
   (wave1c):** an `approver_menu` marker, and separately an `agent` marker, on a quarantined request
   (approved, `consume` line present, status `pending`) → marker deleted, request, action and
   `S/approval_nonces.jsonl` byte-identical, no event (RED when the operator marker revokes it); an
   `operator_script` marker on a pending request whose app denial record is not yet ingested →
   marker deleted, no event, and the next `authorize` sets the action `denied` (RED when the marker
   sets it `cancelled`); a marker with `who: "operatr_script"` on an approved, unconsumed request →
   nothing revoked, `execute` succeeds (RED when an unknown `who` is treated as operator).

### 5.2 Menu-bar list

Sections: pending `$` approvals (Approve/Deny per item), **approved, not yet executed** (a request
whose `status` is `pending`, whose record at `S/approvals/<slug>/<request_id>.json` has `decision ==
"approved"` — a denial record never qualifies — and whose payload nonce has no `consume` line in
`S/approval_nonces.jsonl`, read by the app read-only without the lock; **quarantined** rows —
the same but with a `consume` line — are shown in this section greyed as "quarantined — ask for a
new request" with **no Revoke button** (DECIDED (wave1c): hidden, because a spent nonce can never
be used and act.py's ingest of any marker for it changes nothing, §5.1 step 5 fourth bullet);
**Revoke** per unconsumed item writes `S/cancels/<slug>/<action_id>` with `who: "approver_menu"` — no Touch
ID, a revocation only prevents; the revoke itself is act.py's ingest of that marker, §5.1 step 5),
pending holds (from `hold` notices with `status: open`; **Cancel** per item writes
`S/cancels/<slug>/<action_id>` with `who: "approver_menu"` — no Touch ID), key status line (alg +
fingerprint, from the §5.3 "Existence checks and public-key reads" (2) read — no prompt, never the
secret). Every cancel marker the app writes is the 03_schemas.md §3.11 JSON `{"who":
"approver_menu", "ts": <UTC ts>, "reason": "approver_menu"}`, written to a 0600 temp file in
`S/cancels/<slug>/` (created 0700) and renamed into place. **Menu-bar Approve and Deny run
the same §5.1 step-3 path as the alert** (every pre-Approve check, the enable check, one LAContext
per signature, create-exclusive publication). C test (test build): with fixture requests that are
approved-unconsumed, quarantined (a `consume` line) and denied-not-ingested, the menu model lists
Revoke for the first only, the second as quarantined and the third not in this section (RED when
the section is keyed on the record's existence alone).

### 5.3 Binary modes (`GTMApprover.app/Contents/MacOS/GTMApprover`)

**Source and build (DECIDED HERE).** The Swift source (`tools/gtm/approver/Sources/*.swift`),
`GTMApprover.entitlements`, `Info.plist` and `build.sh` live in `tools/gtm/approver/` (a TRUST_PATH: it is inside `tools/gtm/`, §5.5 step 2).
`build.sh` never compiles the working tree: it extracts HEAD's `tools/gtm/approver/` into a fresh
`mktemp -d` directory and builds only from that extract. The app is installed outside `~/.claude`
(production); the test build is installed at `R/test_fixtures/GTMApprover.app`.

**`build.sh` interface (DECIDED HERE).** Usage: `tools/gtm/approver/build.sh [--test] [--no-install
--out <dir>]`. `R` and `T` follow the header's script root rule (`--test` requires `GTM_TEST=1`;
without it `--test` → exit 2). **A test run never installs outside `R` (DECIDED HERE):**
`GTM_TEST=1` requires either `--test` (installs the test build at `R/test_fixtures/GTMApprover.app`)
or `--no-install --out <dir>` (builds a **production** binary — no `-D GTM_TEST_BUILD` — into
`<dir>/GTMApprover.app` and installs nothing; `<dir>` must be an existing directory equal to or
under `R/test_fixtures/` by `realpath`); `GTM_TEST=1` with neither → exit 2 `usage`, nothing
built. `--no-install` without `--out`, or `--out` without `--no-install`, → exit 2. Outside test
mode `--no-install --out <dir>` is also accepted (any existing directory) and never touches
`~/Applications`. So `GTM_TEST=1 CLAUDE_DIR=/tmp/x build.sh` can never overwrite the operator's
installed approver. The nm C test below builds its production binary with `GTM_TEST=1 build.sh
--no-install --out <tmp R>/test_fixtures/prod`. C test: the real `<passwd
home>/Applications/GTMApprover.app` (when present) has the same mtime and `Contents/MacOS`
cdhash before and after the whole C build suite, and `GTM_TEST=1 build.sh` with no flags exits 2
(RED when the install destination is keyed on `--test` alone).
Steps, each aborting on a nonzero exit:
1. `X=$(/usr/bin/mktemp -d -t gtm_approver_build)`; `/usr/bin/git <step-2 flags and scrubbed env>
   -C <T> archive HEAD -- tools/gtm/approver/ | /usr/bin/tar -x -C "$X"` (both sides of the pipe
   checked with `set -o pipefail`); the sources are then under `$X/tools/gtm/approver/`.
2. `/usr/bin/xcrun swiftc -O -framework AppKit -framework
   LocalAuthentication -framework Security -framework CryptoKit [-D GTM_TEST_BUILD] -o
   "$X/GTMApprover" "$X"/tools/gtm/approver/Sources/*.swift` (`-D GTM_TEST_BUILD` only with
   `--test`).
3. Bundle assembly in `$X/GTMApprover.app`: `Contents/MacOS/GTMApprover` (the binary, mode 0755)
   and `Contents/Info.plist` (copied from `$X/tools/gtm/approver/Info.plist`).
4. `/usr/bin/codesign --force --sign - --options runtime --entitlements
   "$X/tools/gtm/approver/GTMApprover.entitlements" "$X/GTMApprover.app"`.
5. Install (skipped entirely under `--no-install`, which moves `$X/GTMApprover.app` to
   `<dir>/GTMApprover.app` instead, replacing any bundle already there): the destination is
   `gtm_env.approver_app_path()` semantics, keyed on **test mode**, never on the flag alone —
   `~/Applications/GTMApprover.app` (passwd home) only outside test mode, and
   `R/test_fixtures/GTMApprover.app` under `GTM_TEST=1 --test`; the old bundle is
   moved aside to `<dest>.old.<UTCts>` and the new one moved in with `/bin/mv` (same volume).
   **Rollback:** when moving the new bundle in fails, `build.sh` moves `<dest>.old.<UTCts>` back to
   `<dest>` before exiting 1 (stderr names the failed step, and, if the rollback `mv` itself fails,
   `rollback_failed <dest>.old.<UTCts>` so the operator can restore it by hand), so a failed install
   never leaves no app installed. C test: with the destination's parent made unwritable after the
   old bundle is moved aside (a test seam in `build.sh --test` only: `GTM_TEST_BUILD_FAIL_INSTALL=1`
   makes the second `mv` target an unwritable fixture directory), `build.sh --test` exits 1 and the
   old test bundle is back at `<dest>` byte-identical (RED when the rollback is removed).
6. Read the installed binary's cdhash by the **cdhash read rule** (below) and print it, lowercase,
   as the **last stdout line**; then `rm -rf "$X"`.
Exit codes: 0 built and installed; 2 usage (unknown argument, `--test` without `GTM_TEST=1`,
`CLAUDE_DIR` not enterable); 5 `root_mismatch` (header); 3 build failure (git archive, tar, swiftc
or codesign nonzero; nothing installed, the old bundle untouched); 1 install or cdhash-read failure
after a successful build (stderr names the step). `GTM_TEST_BUILD` seams are defined under "Test
build" below.

**cdhash read rule (one parser, used by `build.sh`, `trust_check` and `verify`; DECIDED HERE).**
Run `/usr/bin/codesign --display --verbose=4 <binary>` with the scrubbed environment of §5.5 step
2. `codesign` writes this report to **stderr**, not stdout (measured on this Mac: stdout empty,
`CDHash=<40 hex>` on stderr). The read succeeds only when the exit status is 0 **and** stderr
contains exactly one line matching `^CDHash=[0-9a-fA-F]{40}$`; the value is that hex, lowercased.
Lines starting `CandidateCDHash` or `CandidateCDHashFull` are ignored (they never match the
anchored pattern). Anything else (nonzero exit, zero or several matching lines) is a read failure.
A2 test: the real parser, run against a fixture ad-hoc-signed binary built by `build.sh --test`,
returns the same value as `codesign`'s stderr `CDHash=` line (RED when the parser reads stdout: it
then returns a failure).

**DECIDED HERE:** the entitlements plist is an empty `<dict/>` (no `keychain-access-groups`, which
needs a provisioning profile ad-hoc signing cannot carry; no `get-task-allow`). Whether a persistent
Secure Enclave key works under it is exactly what probe p measures.

**Test build (`-D GTM_TEST_BUILD`; DECIDED HERE).** The test build, and only it, compiles these
seams, all inside `#if GTM_TEST_BUILD` blocks so a production build contains none of them:
- **Presence stub.** `evaluatePolicy` is replaced by a stub that succeeds when the environment
  variable `GTM_TEST_PRESENCE=ok` is set, fails with `LAError.authenticationFailed` when it is
  `fail`, and fails with `LAError.userCancel` when it is unset; the stub counts its calls into
  `R/test_fixtures/approver_presence_calls.log` (one line per call).
- **Software key.** The "SE-shaped" key is a software P-256 key (`SecKeyCreateRandomKey` with
  `kSecAttrKeyTypeECSECPrimeRandom`, no Secure Enclave token, no access control), stored as a DER
  file `R/test_fixtures/approver_test_key.der` (0600). **The test build's Ed25519 key has one home
  rule (DECIDED HERE), whichever path created it (`--generate-key --alg ed25519` or the -34018
  fallback):** with `GTM_TEST_KEYCHAIN=record` it is stored through the keychain recorder below
  (one recorded `SecItemAdd` in the `fallback_store` form the probe file selects, service
  `com.oversight.gtm.approver`, account `signing-key-ed25519`); otherwise it is a CryptoKit raw key
  file `R/test_fixtures/approver_test_key_ed25519.raw` (0600). Lookup follows the same rule, so a
  key in one store is never found through the other. The `ambiguous_key` C test populates the DER
  file **and** the recorder store (with `GTM_TEST_KEYCHAIN=record`), and a second variant the DER
  file **and** the raw file (without it); both exit 1 `ambiguous_key`. `GTM_TEST_KEYGEN_STATUS=<decimal OSStatus>` (e.g. `-25308` =
  `errSecInteractionNotAllowed`, `-34018` = `errSecMissingEntitlement`; a non-integer value is
  ignored with a stderr warning) makes key creation return that status.
- **Keychain recorder.** With `GTM_TEST_KEYCHAIN=record`, the fallback-store calls
  (`SecItemAdd`, `SecItemCopyMatching`, `SecItemDelete`) go to an in-memory store that appends each
  call's attribute dictionary (keys and value types; key bytes redacted) to
  `R/test_fixtures/approver_keychain_calls.jsonl`; `GTM_TEST_SECITEMADD_STATUS=<decimal OSStatus>`
  makes `SecItemAdd` return that status. The "Key selection" C tests use these two seams.
- **File-access recorder.** Every `stat`, `open`, `openat` and `realpath` the pointer resolver of
  §5.1 step 1 performs is appended (the full path, `openat` resolved as `<dir path>/<component>`) to
  `R/test_fixtures/approver_fs_calls.log`.
- **Clock.** `GTM_FAKE_NOW` (00_global_paths.md §1.1) replaces the post-evaluation clock read.
**Seam symbols.** Each seam is one top-level function declared `@_silgen_name("gtmTestPresenceStub")`
(respectively `gtmTestSoftwareKey`, `gtmTestKeychainRecorder`, `gtmTestFsRecorder`) and
`@inline(never)`, so under `-O` it keeps exactly that unmangled symbol name and is neither inlined
nor dead-stripped. C test: `/usr/bin/nm -j` of the production binary built by `build.sh` (no
`--test`) has no line equal to any of `_gtmTestPresenceStub`, `_gtmTestSoftwareKey`,
`_gtmTestKeychainRecorder`, `_gtmTestFsRecorder` (Mach-O C symbols carry a leading `_`; exact
whole-line match, never a substring of a mangled name), and the test build has all four (RED when a
seam is moved outside its `#if`). "The production binary built by `build.sh` (no `--test`)" is the
one `GTM_TEST=1 build.sh --no-install --out <tmp R>/test_fixtures/prod` produces (build.sh
interface above), never the installed app.
So every C signing test runs unattended against the test build, with no real Touch ID and no real
Keychain item.

**Binary integrity (DECIDED HERE; plan §20.8 "even if the app were rebuilt").** User presence is
not content: a rebuilt `GTMApprover` could show "Approve 45.00 USD/day" in its NSAlert and reason
string and pass different bytes to the one signature the operator's Touch ID releases. The Secure
Enclave's `.userPresence` guarantees *that* the operator consented, never *what* the app signed. So
the approved build is pinned and checked:
- **Anchor.** `tools/gtm/approver_cdhash.txt` (tracked, a TRUST_PATH) holds exactly
  `cdhash:<40 lowercase hex>\n`, the cdhash `build.sh` printed for the build the operator installed,
  committed in the same reviewed commit as the pem (§5.6 install order) and again after any
  deliberate rebuild. **The anchor is valid iff its whole content matches
  `^cdhash:[0-9a-f]{40}\n$`**; its value is the 40-hex part after the `cdhash:` prefix, and only
  that part is compared. Any other content is `approver_vs_anchor` (`paths: ["anchor_malformed"]`).
- **Running identity.** The heartbeat (§5.7) carries `approver_cdhash`: the lowercase hex of the
  **first 20 bytes** of `kSecCodeInfoUnique`, read by the app from `SecCodeCopySelf` →
  `SecCodeCopySigningInformation` (intended to be the value `codesign` prints as `CDHash=`;
  **UNVERIFIED** here that `kSecCodeInfoUnique` is exactly 20 bytes on this macOS, so the app
  truncates to its first 20 bytes and the C test below proves equality).
  C test: the test build's heartbeat `approver_cdhash` equals the cdhash read rule's value for the
  same binary.
- **Checks.** `trust_check` (§5.6 TC3) and `approvals_verify.verify` at stages `mint`,
  `execute`, `run_holds` and `revert` read the installed binary's cdhash by the **cdhash read
  rule** above (`/usr/bin/codesign --display --verbose=4
  <gtm_env.approver_app_path()>/Contents/MacOS/GTMApprover`, stderr, scrubbed environment of §5.5
  step 2) and compare it with the HEAD anchor's hex part; `trust_check` also compares the
  heartbeat's `approver_cdhash`. Any difference is mismatch `approver_vs_anchor` (`paths` =
  `["installed:<hex>"]` or `["running:<hex>"]`); at a `verify` stage it refuses
  `ActError(EXIT_TRUST, "approver_vs_anchor")`. An unreadable binary or a `codesign` failure is
  `approver_vs_anchor` too (fail closed). No anchor in HEAD while a pem is in HEAD is
  `approver_vs_anchor` (`paths: ["anchor_missing"]`). The app path is `gtm_env.approver_app_path()`
  (R37): `~/Applications/GTMApprover.app` outside test mode, `R/test_fixtures/GTMApprover.app` in
  test mode, so A2 tests use a fixture binary. A2 tests: an anchor naming a different cdhash makes
  `execute` of a `$` action exit 11 `approver_vs_anchor` and the daily check report it; a heartbeat
  whose `approver_cdhash` differs is reported by the daily check.
- **Prevention.** R36 asks 04 to have G-B deny any agent Bash command that runs `build.sh`, `swiftc`
  or `codesign` with a `GTMApprover` target or writes under `~/Applications/GTMApprover.app`; R57
  asks 04 to deny any agent command that **runs the app binary itself** (direct exec, `open -a`,
  `--args`); R58 asks 04 §4.7 for the `bash_gate.sh` fast-path tokens without which neither rule
  can ever fire. A rebuild is an operator act in his own terminal, followed by a reviewed anchor
  commit.
- **What remains (stated plainly).** A rebuilt app that signs and is then swapped back before the
  next check is caught only by the `running:` heartbeat comparison and only while it runs. Whether
  an ad-hoc-rebuilt binary (new cdhash, same empty entitlements) can reach the existing Secure
  Enclave key at all is **UNVERIFIED**; probe p must record it (plan §17: "a rebuilt binary tries
  one signature: refused / OS consent prompt / signs after Touch ID"). If it signs, the controls
  above are the whole defence and this sentence is the recorded residual risk.

**Key selection (DECIDED HERE; fixed once generated).** `--generate-key` creates a Secure Enclave
P-256 key (§5.6). It falls back to the Ed25519 Keychain key **only** when `SecKeyCreateRandomKey`
fails with `errSecMissingEntitlement` (-34018) — the one outcome probe p records as "SE key
unavailable under ad-hoc signing" — **or** when it is run as `--generate-key --alg ed25519`, which
the app accepts only when `T/tools/gtm/approver_probe_p.json` in HEAD (read with the step-2 git
invocation, a TRUST_PATH) says `"se_key": "fail"`. That file is the machine-readable copy of plan
§17's probe-p record, landed by the reviewed path: exactly `{"probe_p": "pass"|"fail", "se_key":
"pass"|"fail", "rebuilt_binary": "refused"|"consent_prompt"|"signs"|null, "recorded_at": <ts>,
"plan_ref": "plan §17 …", "fallback_store": "dp_userpresence"|"legacy_acl"|"none"|null}` (§5.7
manual check (2) fills `rebuilt_binary`; `fallback_store` is filled whenever `se_key` is `fail`,
else `null`). Any other `SecKeyCreateRandomKey` error exits 7 with **no** key created (a transient
fault never downgrades the approver).

**Fallback key store (DECIDED HERE by probe p's measurement; R62).** The two macOS keychain
implementations cannot both apply to one item: `kSecAttrAccessControl` (`.userPresence`) and
`kSecUseAuthenticationContext` apply only to **data-protection keychain** items
(`kSecUseDataProtectionKeychain = true`), which generally need an application-identifier /
keychain-access-groups entitlement that the empty ad-hoc entitlements cannot carry (plausibly the
same -34018 that selected the fallback; **UNVERIFIED** until measured); a **legacy (file-based)
login-keychain** item instead carries a `SecAccess` trusted-application ACL and cannot take a
`SecAccessControl`. So probe p measures, under the exact ad-hoc configuration of this section, a
CryptoKit Ed25519 key stored (1) as a data-protection generic-password item with
`kSecAttrAccessControl = SecAccessControlCreateWithFlags(nil,
kSecAttrAccessibleWhenUnlockedThisDeviceOnly, .userPresence, …)` — does `SecItemAdd` succeed and
does a read without an evaluated context fail? — and (2) as a legacy login-keychain
generic-password item whose `SecAccess` trusted-application list is exactly the app itself — does
`SecItemAdd` succeed and does a read by a different binary get an OS consent prompt? It records
`fallback_store`:
- **`dp_userpresence`** (store (1) works): the fallback key is stored exactly as (1); the OS itself
  demands presence for every read, as for the SE key; the key lookup passes the evaluated
  `kSecUseAuthenticationContext` (§5.1 step 3).
- **`legacy_acl`** (only store (2) works): the fallback key is stored exactly as (2), with **no**
  `kSecAttrAccessControl` and no `kSecUseAuthenticationContext`. Presence is enforced by the app's
  own fresh `LAContext.evaluatePolicy` (§5.1 step 3) before every read of the item; a read without
  it is never attempted. **Residual (stated):** here presence is an app-side control, not an
  OS-side one; a rebuilt binary is not in the item's trusted-application list and so gets an OS
  consent prompt on read — plan §20.8's stated control for this case — and the cdhash anchor of
  "Binary integrity" above still applies.
- **`none`** (neither works): no fallback key can exist; §5.8 probe-p-failed mode applies
  (`probe_p: "fail"`).
The branch is read from HEAD's `approver_probe_p.json` at `--generate-key` time (install step (0b),
§5.6, commits it before the key is generated); a missing or null `fallback_store` while `se_key` is
`fail` → exit 7 `fallback_store_unmeasured`, no key. **The same exit applies when the file is
missing from HEAD, unreadable, not valid JSON, or not exactly the key set above with those value
types** at a moment the fallback branch needs it — `SecKeyCreateRandomKey` returned -34018, or
`--alg ed25519` was given — so a missing or malformed probe record never selects a store by
default. **Precedence for `--generate-key --alg ed25519` (one order, DECIDED HERE; rewritten
wave1c):** first the agent-invocation refusal (no Keychain call); then the `ambiguous_key` and
`key_exists` checks, which are **existence checks** as defined under "Existence checks and
public-key reads" below — attribute-only `SecItemCopyMatching` calls with authentication UI
skipped, never a data read and never an `LAContext`, and the only Keychain calls made before key
creation; then the fallback-store checks (1)–(3) below, each before any `LAContext`, key creation or
data read: (1) the HEAD file missing, unreadable, not valid JSON or
not exactly the key set and value types above → exit 7 `fallback_store_unmeasured`; (2) the file
valid with `se_key` ≠ `"fail"` → exit 2 `bad_argument` (the Secure Enclave key is available, so
the fallback may not be chosen by hand); (3) `se_key == "fail"` with `fallback_store` null or
`"none"` → exit 7 `fallback_store_unmeasured`; (4) otherwise the Ed25519 key is created in the
named store. The -34018 path skips (2) and applies (1), then (3) read as "`fallback_store` null
or `"none"`, whatever `se_key` says" (a valid file saying `se_key: "pass"` has `fallback_store:
null`, so -34018 there exits 7 `fallback_store_unmeasured`: probe p's record no longer matches
this Mac), then (4). C tests (test build, one
per branch, each asserting its exit code, its stderr token and that no key of either kind
exists afterwards): `--alg ed25519` with no fixture file → 7 `fallback_store_unmeasured`; with a
fixture JSON carrying an extra key → 7 `fallback_store_unmeasured`; with a valid fixture saying
`se_key: "pass"` → 2 `bad_argument`; with `se_key: "fail"`, `fallback_store: "none"` → 7
`fallback_store_unmeasured`; -34018 with no fixture file → 7 `fallback_store_unmeasured`. **Creation
failure:** a CryptoKit key-generation error, or `SecItemAdd` returning anything but
`errSecSuccess`, exits 7 with **no** key left (the app deletes any item it added in that run
before exiting; stderr names the failing call and its status).

**Existence checks and public-key reads (DECIDED (wave1c): the Ed25519 public key lives in the
fallback item's own `kSecAttrGeneric` — one item, one `SecItemAdd`, readable without presence).**
The Ed25519 fallback item carries its raw 32-byte public key as `kSecAttrGeneric` (CFData, exactly
32 bytes), set in the **same single** `SecItemAdd` that stores the private key, in either store
(`dp_userpresence` or `legacy_acl`). (1) **Existence** of either key is an attribute-only
`SecItemCopyMatching`: `kSecReturnAttributes = true`, `kSecMatchLimit = kSecMatchLimitOne`,
`kSecUseAuthenticationUI = kSecUseAuthenticationUISkip`, no `kSecReturnData`, no
`kSecUseAuthenticationContext` and no `LAContext` — for the SE key by its application tag
(`kSecClassKey`), for the fallback item by service and account in the probe-chosen store;
`errSecSuccess` or `errSecInteractionNotAllowed` (-25308) = present, `errSecItemNotFound` =
absent, any other status → exit 1 `internal`. (2) **Public key** — the only source for
`--fingerprint`, `--export-pubkey`, the menu's key status line (§5.2) and the heartbeat's
`pubkey_fingerprint` (§5.7): the SE key → `SecKeyCopyPublicKey` on the key reference (a
`kSecReturnRef` lookup of a Secure Enclave key needs no authentication; only signing with it
does); the fallback key → the `kSecAttrGeneric` bytes returned by the attribute-only query (1).
These four never read the secret and never prompt. A fallback item whose `kSecAttrGeneric` is
absent or not exactly 32 bytes → `--fingerprint`/`--export-pubkey` exit 1 (stderr `internal
pubkey_attr_invalid`), the status line shows "key error", and the heartbeat is written with
`"exit": 1`, `"status": "failed"`, `"pubkey_fingerprint": null` and a summary naming
`pubkey_attr_invalid` (so `heartbeat_audit` reports `job-failed` and TC3 reports
`pubkey_vs_heartbeat`). (3) **Binding to the secret:** every signing mode (`--self-test`,
`--sign-trust-edit`, `--sign-operator-ok`, Approve; Deny signs nothing), after its presence-gated data read,
derives the public key from the private key and requires it byte-equal to the stored
`kSecAttrGeneric`; a difference exits 7 `sign_failed` (detail `pubkey_attr_mismatch`) with nothing
signed or written (Approve: nothing published, the alert shows "Cannot approve: pubkey_attr_mismatch"), so an attribute that does not match the key can never be exported unnoticed
past the first signature (and a pem exported from it would fail every `verify` anyway). **Test
build:** the recorder store honours the same attributes; the raw-file store
(`approver_test_key_ed25519.raw`, no recorder) derives the public key from the file, a test-only
path with no presence semantics. C tests (test build, `GTM_TEST_KEYCHAIN=record`, each RED when
its rule is reverted): with an Ed25519 fallback key present, `--fingerprint` and `--export-pubkey`
each make **zero** presence-stub calls and the recorder log for the run holds no call with
`kSecReturnData`; the `ambiguous_key` and `key_exists` checks record only attribute-only queries;
a recorder item whose `kSecAttrGeneric` is 31 bytes makes `--fingerprint` exit 1
`internal pubkey_attr_invalid`; one whose `kSecAttrGeneric` is another key's 32 bytes makes
`--self-test` exit 7 `sign_failed` with no `S/approver_selftest.json` written.

Every other mode finds the key by lookup: the SE key by its application tag, else the fallback
item (service `com.oversight.gtm.approver`, account `signing-key-ed25519`, in the store the probe
chose). If both exist, every mode exits 1 `ambiguous_key` and signs nothing — **including
`--generate-key`, with or without `--rotate`** (`ambiguous_key` is checked before `key_exists`, and
`--rotate` never guesses which key to delete); the operator resolves it by hand (deletes the key he
does not want in Keychain Access or with `security`, then re-runs). C test (test build): with both
a test SE-shaped key and a test Ed25519 key present, `--generate-key` and `--generate-key --rotate`
each exit 1 `ambiguous_key` and both keys still exist. **`--generate-key`
writes no file in `S`**; the chosen `alg` is reported on its stdout and is recorded in
`S/approver_fingerprint.json` only by `--export-pubkey` (the one writer of that file). Tests (C,
test build with `GTM_TEST_KEYCHAIN=record`; "carries" means the recorded `SecItemAdd` attribute
dictionary): `GTM_TEST_KEYGEN_STATUS=-25308` (`errSecInteractionNotAllowed`) → exit 7 and no key
of either kind exists afterwards; `-34018` (`errSecMissingEntitlement`) with a fixture
`approver_probe_p.json` saying
`fallback_store: "dp_userpresence"` → an Ed25519 key whose item carries a `.userPresence` access
control and a 32-byte `kSecAttrGeneric`; with `"legacy_acl"` → an Ed25519 key in the legacy store
with no access control, a 32-byte `kSecAttrGeneric` (both RED when the public key is stored
anywhere else) and a signing that calls the presence stub exactly once (RED when the app reads the item before
`evaluatePolicy`); with `"none"` or no `fallback_store` → exit 7 and no key; a
`GTM_TEST_SECITEMADD_STATUS` failure → exit 7 and no item left in the recorder's store.

**Agent-invocation refusal (DECIDED HERE; friction, stated as such).** The prevention is G-B
(R51 for the script, R57 for the binary itself). In addition, every mode that signs, creates,
rotates or deletes a key — `--generate-key` (with or without `--rotate`), `--self-test`,
`--sign-trust-edit`, `--sign-operator-ok` — exits 2 (stderr `agent_invocation_refused`), before any
`LAContext` or Keychain call, when the environment variable `CLAUDECODE` is non-empty **or** the
process's parent chain contains a process whose executable basename is exactly `claude` or `node`.
**The walk (exact):** start at `getppid()`; for each pid, the name is the basename of
`proc_pidpath(pid)` (libproc), or, when `proc_pidpath` fails, `kp_proc.p_comm` from `sysctl`
`CTL_KERN, KERN_PROC, KERN_PROC_PID` (the kernel's command name, truncated to 16 bytes — `claude`
and `node` both fit); the next pid is that `sysctl` record's `kp_eproc.e_ppid`; stop at pid 1, at
pid 0, after 64 steps, or when `sysctl` fails (then the walk ends without a match). **Test build
only** (inside `#if GTM_TEST_BUILD`): the walk also stops, without examining it, at the pid named
by `GTM_TEST_WALK_STOP_PID`, and the C harness sets that to its own pid and removes `CLAUDECODE`
from the child's environment, so C tests run from an agent session (whose ancestors include
`claude`/`node`) judge only the fixture ancestors below the harness; a production build reads no
such variable. This is friction
only: an agent that scrubs its environment and double-forks is stopped by G-B, not by this check;
the Touch ID or password prompt remains the control. C tests (test build): each of the four modes
with `CLAUDECODE=1` exits 2 with zero presence-stub calls; the same with a fixture parent named
`node`, and again with one named `claude`, exits 2 — the fixture parent is a copy of
`/usr/bin/time` renamed `node` (respectively `claude`), which forks the binary as its child and
**stays alive waiting for it**, so the name is in the chain while the check runs (a renamed
`/usr/bin/env` would not do: env(1) execs the utility and replaces itself, leaving no `node`
process in the chain); and the same mode run under a parent named `nodejs` or `claude2` does not
exit with `agent_invocation_refused` (exact basename match).
**`--rotate` requires presence before it deletes anything:** `--generate-key --rotate` first runs
one fresh `LAContext.evaluatePolicy` (reason `"Delete the GTM approver key and create a new one"`)
and deletes the old key only after it succeeds; a failure or cancel exits 7 with the old key
untouched. C test: `--generate-key --rotate` with `GTM_TEST_PRESENCE=fail` exits 7 and the old test
key still exists (RED when the deletion precedes the presence check).
**Root check.** Every CLI mode of a production build first applies the header's app root rule and
exits 5 `root_mismatch` (header) before anything else (the test build its real-root refusal); the
table's exit columns omit it.
**Stderr tokens (DECIDED HERE).** On every nonzero exit the app prints **exactly one** line to
stderr whose first whitespace-separated token names the case (any detail follows on the same line):
exit 1 → `internal`, `write_failed`, `ambiguous_key`; exit 2 → `usage`, `bad_path`, `bad_argument`,
`agent_invocation_refused`; exit 3 → `key_exists`; exit 4 → `no_key`; exit 5 →
`root_mismatch`; exit 7 → `auth_failed` (presence failed or cancelled), `sign_failed`,
`key_create_failed`, `fallback_store_unmeasured`. A caller (`gtm_approve.sh`'s pass-through modes,
`operator_ok.sh`) distinguishes cases by exit code **plus** that token. C test: every exit path the
C suite exercises prints exactly one stderr line whose first token is in this list for its exit
code.

| mode | effect | stdout (one JSON line) | exit codes |
|---|---|---|---|
| (no args) | menu-bar agent (`LSUIElement`) | — | runs until quit |
| `--generate-key [--rotate] [--alg ed25519]` | creates the key (above; `--alg ed25519` only under a valid HEAD `approver_probe_p.json` saying `se_key: fail` with a named `fallback_store` — file missing or malformed → exit 7 `fallback_store_unmeasured`, valid with `se_key` ≠ `fail` → exit 2 `bad_argument`, `fallback_store` null/`none` → exit 7, "Fallback key store" precedence). **Refuses when any key exists** unless `--rotate`, which runs only step 2 of the §5.6 rotation procedure, after its own presence check (above); **both keys present → exit 1 `ambiguous_key`, with or without `--rotate`** (checked first) | `{"alg","fingerprint"}` | 0 created; 3 `key_exists` (no `--rotate`); 7 key creation, store, presence or auth failed (no key left, the old key untouched on a `--rotate` presence failure); 2 usage or `agent_invocation_refused`; 1 `ambiguous_key` or internal |
| `--export-pubkey [<path>]` | writes PEM SubjectPublicKeyInfo (§5.6), built from the public key read by "Existence checks and public-key reads" (2) (never the secret, no presence prompt), to `<path>`, default **`S/approver_pubkey.pem`** (never into `tools/gtm/` by default, so export alone never creates an untracked TRUST_PATH file). **`<path>` rule (DECIDED HERE):** ASCII, absolute, no empty, `.` or `..` component, no trailing `/`, its parent an existing directory that is not a symlink, the path itself absent or a regular file (never a symlink), and not equal to or under `T/tools/gtm/` or either Agency root (§5.1 step 1 (c) compare); otherwise exit 2 `bad_path` with nothing written. It also writes `S/approver_fingerprint.json` `{"fingerprint","alg","exported_at"}`, both atomic 0600 | `{"alg","fingerprint","path"}` | 0; 4 no key; 1 write failure; 2 usage |
| `--fingerprint` | prints the current key's identity, from the public key read by "Existence checks and public-key reads" (2) (never the secret, no presence prompt) | `{"alg","fingerprint"}` | 0; 4 no key; 1 (incl. `internal pubkey_attr_invalid`) |
| `--self-test` | §5.7: asks for Touch ID, signs the self-test payload, writes `S/approver_selftest.json` | `{"alg","fingerprint","path"}` | 0; 4 no key; 7 auth or sign failed; 2 `agent_invocation_refused`; 1 |
| `--sign-trust-edit <absolute path>` | the single-use trust-edit marker that 04_hooks.md §4.3 G-W "Trust roots" admits (F16). **Path self-check (DECIDED HERE):** the argument is accepted only when it is ASCII, starts with `/`, contains no empty, `.` or `..` component and no trailing `/`, **names an existing file** (Darwin `realpath(3)` fails for a missing path, so a marker can never admit creating a new TRUST_PATH file: new files land only through the reviewed commit path, §5.6 "Development protocol"; C test: a non-existent path under `<tmp R>/tools/gtm/` exits 2 `bad_path` with zero presence-stub calls), and Darwin `realpath(3)` of it equals it under ASCII case folding (so `/Users/<me>/.claude/tools/gtm/act.py` passes on this case-insensitive volume whatever casing `realpath(3)` returns, and a path through a symlink or with `..` is refused); otherwise exit 2. The payload's `path` is the argument bytes unchanged; G-W compares `canon(payload.path)` with `canon(target)` (04_hooks.md §4 `gtm_hooklib.canon` = normpath + casefold of realpath), which on ASCII paths equals ASCII case folding, the only form the app accepts. One fresh LAContext as in §5.1 step 3, reason `"Allow ONE edit of <path> within 15 minutes"`. Signs the canonical payload `{"v": 1, "kind": "trust_edit", "path": <path>, "nonce": <32 hex>, "expires": <now + 15 min>}` (exactly those keys; `now` = the single post-evaluation clock read of §5.1 step 3) and writes `S/trust_edit_allow.json` `{"schema": "gtm.trust_edit.v1", "payload_b64", "signature_b64", "alg", "key_fingerprint", "signed_at"}` atomically, 0600, replacing any earlier marker. The key set differs from §5.5 step 3a's, so this payload can never pass as a `$` approval, and a `$` payload can never pass G-W (`kind` check) | `{"alg","fingerprint","path","expires"}` | 0; 2 usage/bad path or `agent_invocation_refused`; 4 no key; 7 auth or sign failed; 1 |
| `--sign-operator-ok <command> <slug> <target>` | the signed single-use **operator marker** of 00_global_paths.md §1.4 "Operator authority" (IMP-03; requests/00_global_paths.md R29). **Argument self-check (DECIDED HERE):** `<command>` is a member of the app's compiled-in copy of `OPERATOR_OK_COMMANDS` (00 §1.4 "Shared literals"; a C test asserts the copy equals `system_names.OPERATOR_OK_COMMANDS`, so a command added there fails the test until the app follows); `<slug>` matches `^[a-z][a-z0-9-]{1,31}$` (00 §0.3, = `system_names.SLUG_RE`); `<target>` matches `^[A-Za-z0-9][A-Za-z0-9._@-]{0,127}$` (a pause file name such as `PAUSE.website_wordpress@remodeling`, `autonomous`, for `revert` the revert child's `action_id` (`act_<slug>_…`; §5.5 step 5 "Revert", R52), or another id-shaped target 00 §1.4 defines; never `/`, a leading `.` or NUL, so the file name cannot leave the directory); otherwise exit 2. One fresh LAContext as in §5.1 step 3, reason `"Allow ONE <command> of <target> for <slug> within 15 minutes"` (00 §1.4). Signs the canonical payload `{"v": 1, "kind": "operator_ok", "command": <command>, "company": <slug>, "target": <target>, "nonce": <32 hex>, "expires": <now + 15 min>}` (exactly those keys; `now` = the single post-evaluation clock read of §5.1 step 3) and writes `S/operator_ok/<command>.<slug>.<target>.json` `{"schema": "gtm.operator_ok.v1", "payload_b64", "signature_b64", "alg", "key_fingerprint", "signed_at"}` atomically, 0600 (directory `S/operator_ok/` created 0700), replacing an earlier marker of the same file name. Its key set differs from §5.5 step 3a's and from the trust-edit payload's, so no marker can pass as a `$` approval or as a trust-edit marker, and neither of those can pass as it. The app never verifies or consumes it: act.py does (00 §1.4: `approval_sig.verify_raw` against HEAD's pem, then a `consume` line with holder `operator-ok:<command>:<target>` in `S/approval_nonces.jsonl`, then delete) | `{"alg","fingerprint","path","expires"}` | 0; 2 usage/bad argument or `agent_invocation_refused`; 4 no key; 7 auth or sign failed; 1 |

Every file the app writes is written atomically per 00_global_paths.md §0.2, except approval and
denial records, which use the §5.1 step-3 create-exclusive rule.

### 5.4 Re-show and cancel scripts

Both scripts resolve `S = R/.gtm_state` with `R` taken **only** by the root rule of this file's
header (passwd home via `dscl`; `CLAUDE_DIR` honored only when it names the real root, or under
`GTM_TEST=1`, resolved with `pwd -P`; anything else exit 5 `root_mismatch`), never as
`${CLAUDE_DIR:-$HOME/.claude}` (test: under `GTM_TEST=1` the scripts' `S` equals
`company.gtm_state_dir()` for the same tmp `CLAUDE_DIR`, `/tmp/x` included). **The app path
(`<APP>`)** follows `gtm_env.approver_app_path()` semantics (R37): outside test mode
`<passwd home>/Applications/GTMApprover.app` (never `$HOME`); under `GTM_TEST=1`
`R/test_fixtures/GTMApprover.app` (the test build, §5.3), so no script test ever execs the
production app, needs a real Touch ID or writes the real `S`. Every mode except `trust-edit` and
`operator-ok` prints the number of markers written as its last stdout line **on exit 0 only**; a
nonzero exit prints nothing on stdout (its one stderr line is the only output).
**Exit codes, both scripts (one table; I15).** 0 success; 1 write failure; 2 usage / malformed
argument / `agent_invocation_refused`; 3 "nothing pending" (`gtm_approve.sh`: no pending request;
`gtm_cancel.sh`: no pending hold for that single action); 5 `root_mismatch` (header; never any
other condition). The pass-through modes (`trust-edit`, `operator-ok`) exit with the app's code
and pass its single stderr token line through unchanged (§5.3 "Stderr tokens"; the app uses 5 only
for `root_mismatch` as well). Every nonzero exit of a script's own prints exactly one stderr line
whose first token names it (`root_mismatch`, `no_pending_request`, `no_pending_hold`,
`malformed_id`, `slug_mismatch`, `usage`, `agent_invocation_refused`, `write_failed`). Exit codes
alone do **not** separate every case (exit 2 covers `usage`, `malformed_id`, `slug_mismatch` and
`agent_invocation_refused`; exit 1 is the script's `write_failed` or, in a pass-through mode, the
app's `internal`/`write_failed`/`ambiguous_key`), so a caller such as `operator_ok.sh` tells every
case apart by **exit code plus that single stderr token** (R60 asks 00 §1.4 to document that
`operator_ok.sh` passes exit 5 and the token through).
**Id and slug validation (both scripts; exact, before any path is built).** A request id must match
`^apr_[a-z][a-z0-9-]{1,31}_\d{8}T\d{6}Z_[0-9a-f]{6}$`, an action id
`^act_[a-z][a-z0-9-]{1,31}_\d{8}_\d{4}$`, a slug `^[a-z][a-z0-9-]{1,31}$` (= `system_names.SLUG_RE`; 00_global_paths.md
§0.3; bash `[[ =~ ]]` with `LC_ALL=C`, so `\d` is written `[0-9]`); anything else → exit 2
`malformed_id` (`usage` for a slug), nothing written. C test (RED under a wider grammar): a
33-character slug, a slug starting with a digit, and an `apr_`/`act_` id carrying either, each
exit 2 with nothing written. No path is ever built from an unvalidated
argument, so `../` can never reach `S/approver_inbox/`, `S/approval_requests/` or `S/cancels/`.
**Writes (both scripts).** Every file is written to a same-directory temp file created with
`umask 077` (mode 0600), then `/bin/mv` onto its name (atomic, 00_global_paths.md §0.2); every
directory a script creates is created 0700. A cancel marker's content is exactly
`{"who": "operator_script", "ts": "<UTC %Y-%m-%dT%H:%M:%SZ>", "reason": "operator_script"}`
(03_schemas.md §3.11). C tests: `gtm_approve.sh 'apr_x_../../y'` and `gtm_cancel.sh
'act_../../x_20260927_0001' <fixture slug>` each exit 2 `malformed_id` with nothing written anywhere;
every marker a script writes is mode 0600 and parses as that JSON.

- `scripts/gtm_approve.sh <request_id>` → the slug is the id's second `_` field
  (`apr_<slug>_<ts>_<hex>`). Touches `S/approver_inbox/show.<request_id>`; the app re-shows that
  alert and deletes the marker. It **cannot** approve (no signing path exists outside the app).
  Exit 0 marker written; 2 malformed id; 3 no pending request (`S/approval_requests/<slug>/<request_id>.json`
  absent, or its `status`, read with `/usr/bin/plutil -extract status raw -o -`, is not `pending`);
  1 write failure; 5 `root_mismatch`. It creates `S/approver_inbox/` 0700 when absent (§5.1
  step 5).
- `scripts/gtm_approve.sh trust-edit <absolute path>` → refuses exit 2 (`agent_invocation_refused`)
  when `CLAUDECODE` is non-empty (friction only, as for `operator-ok`), else execs
  `<APP>/Contents/MacOS/GTMApprover --sign-trust-edit <path>` and passes its exit code and stdout
  through (the signature still needs the operator's Touch ID or password in the app). This is the
  only producer of `S/trust_edit_allow.json` that 04_hooks.md §4.3 names. Tests (C, all under
  `GTM_TEST=1` with a tmp `CLAUDE_DIR` and the test build, `GTM_TEST_PRESENCE=ok`, so they run
  unattended and write only the tmp `S`): the marker's payload decodes to exactly the five keys,
  `expires − signed_at` = 15 min exactly (one clock read, §5.1 step 3), and
  `approval_sig.verify_signature` refuses it (`bad_keys`); `trust-edit <tmp R>/tools/gtm/act.py`
  (an existing file with a physical path) exits 0; the same path with a `/../gtm/` segment, a
  relative path, and a path through a symlinked directory each exit 2; with `CLAUDECODE=1` it
  exits 2 with zero presence-stub calls; the whole test file passes the test-footprint oracle,
  clause (iii) included (the real `S/trust_edit_allow.json`, if present, names no path containing
  `m`; reconciled wave1e — the former "mtime is unchanged" assertion fails whenever the operator
  signs a real trust edit during the run).
- `scripts/gtm_approve.sh operator-ok <command> <slug> <target>` → refuses exit 2 when `CLAUDECODE`
  is non-empty (friction only; the Touch ID is the control, 00_global_paths.md §1.4), else execs
  `<APP>/Contents/MacOS/GTMApprover --sign-operator-ok <command> <slug> <target>` and passes its
  exit code and stdout through. It is the one path `tools/gtm/operator_ok.sh`
  execs (00 §1.4 "Creation"); the app's argument self-check (§5.3) is the only argument validation.
  Tests (C, under `GTM_TEST=1` with the test build, as for `trust-edit`): the marker's payload
  decodes to exactly the seven keys with `kind: "operator_ok"`,
  `expires − signed_at` = 15 min exactly, and `approval_sig.verify_signature` refuses it
  (`bad_keys`); a `<target>` containing `/` or starting with `.`, and a `<command>` outside
  `OPERATOR_OK_COMMANDS`, each exit 2 with no marker written.
- `scripts/gtm_cancel.sh <action_id> <slug>` | `scripts/gtm_cancel.sh all <slug>` → writes cancel
  markers (03_schemas.md §3.11) with `who: "operator_script"`. Never calls act.py. (G-B rule g denies agents.)
  A **cancellable action** is (i) a **pending hold**: an open `hold` notice (`status: open`) in
  `S/notices/<slug>/` whose `action_id` matches; or (ii) a **pending `$` request, signed or
  not**: a request file in `S/approval_requests/<slug>/` whose `action_id` matches and whose
  `status` is `pending` — with an approval record at `S/approvals/<slug>/<request_id>.json` whose
  nonce is unconsumed (an approved, not yet executed action: the operator's revoke channel) **or
  with no decision record** (an unsigned request: the operator's cancel-without-deciding channel,
  which the mirrored card and the reshow notice name, §5.1 step 5, §5.8) — decided by the
  "Signed-request test in bash" below; act.py's ingest of the
  marker does the revoke or the cancel (§5.1 step 5 "Cancelling a `$` request"). The single-action
  form writes the marker for either; `all` writes one marker per pending hold (never for (ii):
  `all` stays the hold sweep plan §20.7 describes) **and always** the
  `S/cancels/<slug>/_all.<UTCts>` marker 03_schemas.md §3.11 requires (`<UTCts>` = `%Y%m%dT%H%M%SZ`;
  it also stops in-flight write tickets created before it, 04_hooks.md `ticket_cancelled`). The
  printed count is the number of per-hold markers; the `_all` marker is not counted. An
  `<action_id>` whose embedded slug (`act_<slug>_…`) differs from `<slug>` exits 2.
  **JSON parsing in bash (both scripts):** `/usr/bin/plutil -extract <key> raw -o - <file>` (reads
  JSON; SIP-protected; no `python3`, no `jq`); a nonzero `plutil` exit means "field absent or file
  unreadable" and the file is skipped (never counted as pending).
  **Signed-request test in bash (exact; DECIDED (wave1c)).** For a pending request (ii) the script
  decides the record state of §5.1 step 5 with `/usr/bin/plutil`, `/usr/bin/base64` and
  `/usr/bin/grep` only (measured on this Mac: `plutil -extract <key> raw -o - -` reads one JSON
  document from stdin; `base64 -D` decodes stdin): (1) no file at
  `S/approvals/<slug>/<request_id>.json` → *none* → cancellable; (2) `decision` = `plutil -extract
  decision raw -o - <record>`: `denied` → not cancellable; `approved` → step 3; plutil failing or
  any other value → treated as approved-unconsumed (cancellable: a cancel only prevents, and
  act.py's ingest is the authoritative second check); (3) `nonce` = `plutil -extract payload_b64 raw
  -o - <record> | /usr/bin/base64 -D | /usr/bin/plutil -extract nonce raw -o - -` (with `set -o
  pipefail`); a failure, or a value not matching `^[0-9a-f]{32}$` (bash `[[ =~ ]]`, `LC_ALL=C`), →
  treated as unconsumed (cancellable); (4) consumed iff `S/approval_nonces.jsonl` exists and some
  line of `/usr/bin/grep -F -- "$nonce" S/approval_nonces.jsonl`, fed line by line (`while IFS= read
  -r line`) to `printf '%s' "$line" | /usr/bin/plutil -extract <field> raw -o - -`, has `nonce` equal
  to the value and `op` equal to `consume` (the 03_schemas.md §3.9 field names); a line plutil cannot
  parse is skipped; consumed → not cancellable, else cancellable. The script takes **no** lock on
  the nonce ledger (a consume landing between this read and act.py's ingest is handled by the ingest,
  §5.1 step 5 fourth bullet) and writes no temp file for the decode.
  Exit codes (I15): 0 marker(s) written (also 0 for `all` with no pending holds or no
  `S/notices/<slug>/` directory, printing `0`, the `_all` marker still written), 2 bad id/slug/usage
  or slug mismatch, 3 no cancellable action for that single action id (neither a pending hold nor
  a pending `$` request; including no `S/notices/<slug>/` directory; token `no_pending_hold`), 1
  write failure, 5 `root_mismatch`. C tests (each RED when its case is dropped from the set): with a
  fixture approved, unconsumed request for `<action_id>` and no hold, `gtm_cancel.sh <action_id>
  <slug>` exits 0 and writes the marker; the same with an **unsigned** pending request (no record
  in `S/approvals/`) exits 0 and writes the marker; with a request whose `status` is `denied` or
  `expired` it exits 3 `no_pending_hold`; with a pending request whose approval record's nonce has a
  `consume` line in the fixture ledger (quarantined) it exits 3 `no_pending_hold` and writes nothing
  (RED when the nonce test is dropped); with a pending request carrying an app **denial** record it
  exits 3 `no_pending_hold`; with a ledger holding a malformed line before the matching `consume`
  line it still exits 3 (RED when a bad line aborts the scan).

### 5.5 Verification (A2 `approval_sig.py` + `approvals_verify.py`)

**The API is split in two layers (I2; one normative assignment of checks):**
- `approval_sig` (standalone, **stdlib only**, R12) = the trust root (steps 0–2) and
  `verify_signature` = steps **3a and 4** on top of the process's trust result: `payload_b64`
  byte-equal to the request's, canonical bytes, exact key set, key lookup by fingerprint, `alg`/key
  type, signature. **No** expiry, **no** action/value binding, **no** nonce operation, **no**
  `decision` test (callers filter `decision` themselves). Its one ledger dependency is the
  retired-key rule (§5.6), and it does not read the ledger itself: the caller passes
  `consume_ts(nonce) -> str | None` (the `ts` of that nonce's `consume` line in
  `S/approval_nonces.jsonl`, or None). A record under a retired key verifies iff `consume_ts` is
  given, returns a value, and that value `< valid_until` (both parsed as aware UTC, header "Formats";
an unparsable value is `key_retired`); otherwise `key_retired`. Callers:
  `approvals_verify.verify` passes `functools.partial(approvals_verify.consume_ts, ctx)` (the
  callback takes the nonce alone; `approvals_verify.consume_ts` itself takes `(ctx, nonce)`, so it
  is never passed bare); `ai_budget` passes its own
  stdlib reader of the same file (04_hooks.md §4.6); a caller that passes nothing gets `key_retired`
  for every retired-key record.
- **The single backend definition.** Step 4's backends verify **every** signature made by the
  approver key: `$` records (`verify_signature`), the self-test (`--self-test`), the trust-edit
  marker (`--verify-trust-edit`, below, which 04_hooks.md §4.3 G-W runs as a subprocess; R38) and
  the operator marker (§5.3 `--sign-operator-ok`, which act.py verifies with `verify_raw` after its
  step-0 trust check, 00_global_paths.md §1.4). No other verification stack for this key exists
  anywhere.
- `approvals_verify.verify` (A2, gtmlib) = `verify_signature` **plus** steps **3b and 5**:
  `decision == "approved"`, value and display binding to the action/request, `after_digest`, the
  per-stage expiry rule, and the nonce-ledger **state** tests (read only). `verify` performs **no**
  nonce operation and writes nothing; the only ledger writers are `reserve`/`consume`/`release`/
  `quarantine`. So a second `verify(stage="execute")` inside `connector_dispatch.execute`
  (06_connectors.md §6.2 "Money binding") is safe, and the stage-`execute` expiry rule is the one
  that layer applies for the `execute`, `run_holds` and API `revert` callers alike
  (requests/06_connectors.md R19).

```python
# approval_sig.py (A2) — stdlib + gtm_env only (gtm_env is itself stdlib-only, 00_global_paths.md §1.1);
# imported, with gtm_env, before any other tools/gtm module (step 0)
TRUST_KINDS = ("trust_root_mismatch", "trust_paths_modified", "trust_paths_untracked",
               "trust_interpreter", "trust_git_error")
class RootMismatch(Exception): ...                # owned by approval_sig (not gtm_env); every entry point maps it to
    # exit 3 "root_mismatch" (Python) — the scripts and the app use exit 5 (header)
def claude_dir() -> Path                          # Path(CLAUDE_DIR or ~/.claude).expanduser().resolve() (RESOLVED;
    # A2 test, CLAUDE_DIR SET only: equals company.claude_dir(), incl. CLAUDE_DIR=/tmp/x -> /private/tmp/x;
    # with CLAUDE_DIR unset company returns Path.home()/".claude" UNresolved, so that case is asserted with
    # gtm_env.same_root(approval_sig.claude_dir(), company.claude_dir()), never ==, incl. a HOME that is a
    # symlink of the passwd home — not test mode, 00 §1.1; R70 asks 00/company to resolve both branches)
def trust_root(R: Path) -> Path                   # T: gtm_env.real_root() outside test mode, R in test mode;
    # raises RootMismatch (callers: exit 3 "root_mismatch") when not test mode and
    # not gtm_env.same_root(R, gtm_env.real_root())   (samefile, else casefolded norm; 00 §1.1 — NEVER a
    # case-sensitive normpath compare, which is 00's named RED variant). A2 test: with HOME set to a case
    # variant of the passwd home (e.g. /users/<me>; not test mode, because same_root(HOME, real_home())
    # holds) and CLAUDE_DIR unset, trust_root(claude_dir()) returns real_root() and does not raise (RED
    # under a case-sensitive normpath compare)
def trust_root_ok(R: Path, *, require_key: bool = True) -> tuple[bool, list[dict]]
    # steps 0-2 against trust_root(R), via the cache (trust_result). Entries {"kind": <TRUST_KINDS member>,
    # "paths": [str, ...]}: EXACTLY ONE entry per kind present, whose `paths` is the sorted, de-duplicated
    # list of every offending path of that kind (two untracked files -> one trust_paths_untracked entry
    # with two paths); entries sorted by TRUST_KINDS order; ok iff the list is empty.
    # NEVER emits key_not_installed (not a TRUST_KINDS member): step 1 passes when neither HEAD nor the
    # working tree has approver_pubkey.pem. A working-tree pem with none in HEAD adds the path
    # "tools/gtm/approver_pubkey.pem" to the trust_paths_untracked entry; a working-tree pem that differs
    # from HEAD's, or HEAD's pem missing from the working tree, adds it to the trust_root_mismatch entry
    # (beside any "code_root:<dir>" path). The step-2 walk skips approver_pubkey.pem (step 1 owns it), so
    # a pem difference is never reported twice. `require_key` is accepted and IGNORED (both values give
    # the same result; kept so 02/04 call sites need no change, R39 asks them to drop it);
    # key_not_installed is decided only at key lookup in verify_signature.
    # (The §5.6 daily check's fingerprint-class mismatches are NOT trust_root_ok entries: there, one
    # entry per differing value, §5.6 TC3.)
def _compute_trust(R: Path) -> tuple[bool, list[dict]]    # the UNCACHED steps 0-2 computation; the only caller that
    # bypasses the cache is trust_check (§5.6 TC1/TC4), which then repopulates the cache with its last result.
    # A failing git invocation raises the INTERNAL class TrustGitError(subcommand: str, exit_status: int | None)
    # (exit_status None = git missing / timeout / unparsable output) inside the computation; _compute_trust
    # catches it and returns the public entry [{"kind": "trust_git_error", "paths": [subcommand]}] unchanged,
    # keeping the last TrustGitError on the cached result (trust_git_detail(R) -> tuple[str, int | None] | None)
    # so the notice writer below can name the exit status without changing the public entry shape
def trust_result(R: Path) -> tuple[bool, list[dict]]      # cached _compute_trust result: per process, keyed on
    # (realpath of T, R), reused while <= 60 s old, else recomputed
def trust_git_detail(R: Path) -> tuple[str, int | None] | None
    # (subcommand, exit_status) of the TrustGitError behind the latest computed result for (T, R), else None
def verify_raw(pem_bytes: bytes, data: bytes, signature: bytes, alg: str) -> tuple[bool, str]
    # step 4 only; reason ∈ {"ok","alg_mismatch","bad_signature","verifier_unavailable","malformed_record"}
def verify_signature(R: Path, record: dict, request: dict, *,
                     consume_ts: Callable[[str], str | None] | None = None) -> tuple[bool, str, dict | None]
    # trust_result(R) first, then 3a, key lookup (HEAD has no pem -> "key_not_installed"), the retired-key
    # rule via consume_ts (above), verify_raw -> (ok, reason, decoded payload)
    # on success returns (True, "ok", payload) — "ok" is the one success reason, exactly as verify_raw's;
    # on failure (False, reason, None) with
    # reason ∈ TRUST_KINDS ∪ {"key_not_installed","key_unknown","key_retired","malformed_record",
    #   "payload_mismatch","non_canonical","bad_keys","alg_mismatch","bad_signature","verifier_unavailable"}
def trust_check(R: Path, now: datetime, *, settle_seconds: int = 300,
                _between_runs: Callable[[], None] | None = None) -> dict
    # §5.6 daily check; writes PAUSE.trust + notices itself; ALWAYS returns all six keys
    # {"ok": bool, "installed": bool, "alg": str|None, "fingerprint": str|None,
    #  "mismatches": [{"kind": str, "paths": [str]}], "notes": [str]}
    # (fingerprint kinds carry paths: ["<fingerprint or cdhash>"]; §5.6 TC3)
    # Both of its steps-0-2 runs (TC1's git retry and TC4's settle re-check) call _compute_trust, never the
    # 60 s cache. `_between_runs` is a TEST SEAM, not a bypass: when given it is called once, after the
    # settle sleep and before the second _compute_trust, so a test can change the fixture tree between the
    # two runs with settle_seconds=0; it cannot skip, replace or alter any check. The CLI never passes it.
def write_notice(S: Path, slug: str, kind: str, severity: str, push: bool, title: str, body: str,
                 dedupe_key: str, *, created_by: str) -> None
    # THE stdlib-only direct writer of one 07_notices_schedules.md §7.1 notice record: `severity` a §7.1
    # severity ("info" | "warn" | "urgent"), `push` as given, status "open", the §7.1 id scheme
    # (ntc_<slug>_<UTCts>_<6 hex>, created exclusively, redraw on EEXIST, 00 §0.2/§0.3), the §7.1 notices
    # lock, and dedupe (skip when an open notice of the same company with the same dedupe_key and created_by
    # exists); `kind` must be a §7.1 NOTICE_KINDS member, `severity` one of the three, `created_by` a
    # NOTICE_CREATED_BY member and `slug` a GTM-slug-grammar string or "runtime" (else ValueError, nothing
    # written); calls gtm_env.refuse_real_state(R, None) first (R derived from S's parent). Imports nothing
    # from tools/gtm but gtm_env. A2 test: its record key set equals a notices.write_notice record's.
def write_urgent_notice(S: Path, slug: str, kind: str, title: str, body: str, dedupe_key: str, *,
                        created_by: str = "act") -> None
    # = write_notice(S, slug, kind, "urgent", True, title, body, dedupe_key, created_by=created_by); the
    # writer behind every step-0 fallback notice of 02_act.md §2.3 (the ingest-findings runaway_spend /
    # phi_encountered notices, 02 item 68) and behind write_trust_notice
def write_trust_notice(S: Path, entries: list[dict], *, created_by: str) -> None
    # the §5.6 trust-notice formula, written through write_urgent_notice(S, "runtime", "trust", ...) (R19)
def write_trust_git_notice(S: Path, *, subcommand: str, exit_status: int | None, created_by: str,
                           now: datetime) -> None
    # the warn notice of "Error mapping" below: write_notice(S, "runtime", "trust", "warn", False, …);
    # body names `subcommand` and `exit_status` ("none" when None); callers take both from trust_git_detail
# (The TC3 "trust code changed" info notice, §5.6, is written through write_notice(..., "info", False, ...).)
# __main__ (canonical CLI): /opt/homebrew/opt/python@3.13/bin/python3.13 <T>/tools/gtm/approval_sig.py
#   (always TRUSTED_PYTHON by full path, R59; a bare python3 start re-execs once, step 0)
#     --trust-check [--settle-seconds N] | --trust-result | --self-test [<file>] | --verify-trust-edit <target path>
#   every mode first runs step 0 (re-exec) and resolves T (RootMismatch -> exit 3 "root_mismatch"); bad argv -> exit 2;
#   a write refused by gtm_env.refuse_real_state (RealStateRefused) -> exit 3 "test_mode_real_state" (00 §1.1)
#   --trust-check prints the trust_check dict; exit 0 ok (clean, or not yet installed with steps 0-2 clean),
#     11 any mismatch (trust_git_error included), 3 root_mismatch, 2 usage, 1 internal
#   --trust-result prints {"ok": bool, "entries": [...]} (= trust_root_ok); exit 0 ok, 11 not ok, 3, 2, 1 —
#     the carrier for a caller that is not itself an isolated entry point (gate-gtm, §5.5 step 0)
#   --self-test runs steps 0-2 first; a trust failure prints {"ok": false, "alg": null, "fingerprint": null,
#     "installed": <bool>, "reason": <first TRUST_KINDS kind>} and exits 11; otherwise it verifies (§5.7) and
#     prints {"ok","alg","fingerprint","installed","reason"}; exit 0 verified, 7 not verified, 3, 2, 1
#   --verify-trust-edit runs steps 0-2, then verifies S/trust_edit_allow.json with step 4's backends against
#     HEAD's pem at T: canonical bytes first (else "non_canonical"), then exactly the five §5.3 keys, kind == "trust_edit", canon(payload.path) == canon(target),
#     expires > now; prints {"ok", "reason", "nonce", "expires"}; exit 0 valid, 7 invalid, 11 trust failure,
#     4 no marker, 3, 2, 1. It never consumes the marker (single use is G-W's, 04_hooks.md §4.3)

# approvals_verify.py (A2, gtmlib)
def create_request(ctx, action) -> dict
def load_approval(ctx, request_id) -> dict | None
def build_display(ctx, action) -> dict            # deterministic; its canon bytes are display_b64 (R10)
def verify(ctx, action, *, stage: str) -> dict    # stage ∈ {"authorize","mint","execute","complete","run_holds","revert"};
    # returns the decoded, verified payload; raises ActError(EXIT_APPROVAL, <reason>) or
    # ActError(EXIT_TRUST, <reason>) — never exits itself; at stage "mint" a too-near expiry is
    # raise ActError(EXIT_APPROVAL, "approval_expiring") (step 5)
def consume_ts(ctx, nonce: str) -> str | None     # ts of the nonce's consume line, else None (the verify_signature callback)
def reserve(ctx, action, holder: str) -> None; def consume(ctx, action, holder: str) -> None; def release(ctx, action, holder: str) -> None
    # `holder` is the FULL ledger string, prefix included: "ticket:<ticket_id>", "execute:<action_id>",
    # "run-holds:<action_id>" (03_schemas.md §3.9); these functions never add a prefix (R34 aligns 02's calls)
def quarantine(ctx, action, holder: str, *, reason: str) -> None
    # appends a consume line for `holder` plus event nonce_quarantined {request_id, reason}: the nonce is
    # spent without a completion, so the operator must re-approve (step 5 "Release or quarantine")
def trust_check(R: Path, now: datetime, *, settle_seconds: int = 300) -> dict
    # = approval_sig.trust_check (re-export, same signature minus the test seam)
# __main__: the step-0 pre-import block, under `if __name__ == "__main__":` (so importing this module never
#   re-execs), is the file's first statement after `from __future__ import annotations`; it re-execs the
#   literal TRUSTED_PYTHON (step 0 "Isolated interpreter" (1)) with step 0's flags on <code dir>/approval_sig.py
#   (code dir = the tools/gtm directory, step 0 "Code root": for this file dirname(dirname(abspath(__file__))))
#   with the same argv, so the old path keeps working (R20)
```
**Reason → exit code → `error.code` (the one complete table; DECIDED HERE).** `error.code` is
always the reason string itself (02_act.md §2.3). A reason not in this table is an implementation
defect; an A2 test enumerates `verify_signature`'s reason set and every `ActError` reason raised by
`approvals_verify` and asserts each is a row here. R64 asks 02 §2.3 and 03 §3.9 to cite this table.

| reason | exit | raised at |
|---|---|---|
| `trust_root_mismatch`, `trust_paths_modified`, `trust_paths_untracked`, `trust_interpreter`, `trust_git_error` (the `TRUST_KINDS`) | 11 (EXIT_TRUST) | steps 0–2 (and `verify_signature`'s first call to `trust_result`) |
| `key_not_installed` | 11 | 3a key lookup: HEAD has no pem (no pause, no notice, below) |
| `approver_vs_anchor` | 11 | §5.3 "Binary integrity" at `mint`/`execute`/`run_holds`/`revert` |
| `pubkey_vs_export` | 11 | §5.5 step 3a "Export binding" at `mint`/`execute`/`run_holds`/`revert` (the HEAD current key's fingerprint ≠ `S/approver_fingerprint.json`, or that file missing/unparsable while HEAD has a pem; R73 adds it and `request_missing` to 02 §2.3's code list) |
| `approver_not_installed` | 11 | the operator-marker route (00_global_paths.md §1.4; §5.5 step 5 "Revert") with no HEAD pem |
| `malformed_record`, `payload_mismatch`, `non_canonical`, `bad_keys`, `key_unknown`, `key_retired`, `alg_mismatch`, `bad_signature`, `verifier_unavailable` | 7 (EXIT_APPROVAL) | 3a / key lookup / step 4 |
| `request_missing` (no request file at `S/approval_requests/<slug>/<request_id>.json` for the action's `request_id`), `approval_missing` (no record at `S/approvals/<slug>/<request_id>.json`), `decision_not_approved`, `request_denied`, `request_superseded`, `request_expired`, `field_mismatch`, `digest_mismatch`, `display_mismatch`, `value_mismatch`, `unit_mismatch`, `null_not_allowed` | 7 | 3b |
| `approval_expired` (`expires ≤ now` where the stage table requires `expires > now`), `approval_expiring` (`mint` inside `MINT_MARGIN`) | 7 | step 5 |
| `nonce_held`, `nonce_replay`, `nonce_not_reserved` (`complete`: the nonce is not currently reserved by this `ticket:<ticket_id>`), `reserved_after_expiry` (`complete`: that reserve line's `ts ≥ expires`) | 7 | step 5 |
| `enable_amount_required`, `enable_no_budget_object` | 3 | `propose`/`authorize` (03_schemas.md §3.2, which owns both; §5.5 step 3b "Enable binding" cites them), before any `verify` |
| `enable_budget_mismatch`, `enable_not_agent_executable` | 3 | `ticket --write` mint (03_schemas.md §3.6 `budget_readback`; §5.5 step 3b "Freshness of the bound value"), after `verify(stage="mint")` succeeds and before any reservation |
| `root_mismatch` | 3 (Python entry points); 5 (scripts and app, header) | header root rule |

`key_not_installed` means "not verifiable, not forged": act.py refuses every `$` with exit 11
`key_not_installed` and writes no `PAUSE.trust` and no notice (the expected pre-install state), and
`ai_budget` falls back to `company.json` caps instead of marking buckets `forged` (R13). Every other
non-ok reason is a refusal (act.py) or `forged` (ai_budget).

**Error mapping and precedence.** Any `TRUST_KINDS` failure → exit 11 (EXIT_TRUST). When several
kinds are present, the reported kind (02_act.md §2.3 `error.code`) is the first one present in
`TRUST_KINDS` order (`trust_root_mismatch`, `trust_paths_modified`, `trust_paths_untracked`,
`trust_interpreter`, `trust_git_error`). **`trust_git_error` is always alone:** any git invocation
of steps 1–2 that fails (git missing, not a repository, no `HEAD`, exit other than 0, unparsable
output) aborts steps 1–2, so the result is exactly `[{"kind": "trust_git_error", "paths":
["<git subcommand>"]}]`, and the fingerprint comparisons of §5.6 TC3, which need HEAD, are
skipped. A mixed "git error plus path mismatch" result therefore cannot occur. `trust_git_error`
fails closed for the command (exit 11) but **never** writes `PAUSE.trust` and **never** goes through
`write_trust_notice`; instead the process calls `write_trust_git_notice`: slug `runtime`, kind
`trust`, severity `warn`, `push: false`, title `"GTM trust check could not run git — $ refused
until it can"`, body = the failing subcommand and its exit status (no path contents),
`dedupe_key = "trust_git:<UTC date YYYY-MM-DD>"`, `created_by` = `"act"` (dispatch) or
`"approvals_verify"` (daily check; both in 07_notices_schedules.md §7.1 `NOTICE_CREATED_BY`),
written by `write_trust_git_notice(S, subcommand=…, exit_status=…, …)` with both values taken from
`trust_git_detail(R)` (API above). So a
transient git fault cannot become a global operator-only pause (R40 amends 02 §2.3 to match). When
both a trust kind and a signature reason apply, the trust kind is reported (steps 0–2 run first and
stop).

0. **Interpreter and import order (F-interp; DECIDED HERE).** The check is only as good as the
   process running it, so:
   - **Which processes are entry points.** Trust-root code (`approval_sig`, and anything that calls
     `verify_signature`, `trust_root_ok` or `ai_budget`'s cap computation) runs **only** in a process
     that is itself an isolated entry point: `tools/gtm/act.py`; `approval_sig.py`'s,
     `approvals_verify.py`'s and `ai_budget.py`'s `__main__`; `run_gtm_job.sh`'s unsigned-caps check
     (R14). **A hook never imports `approval_sig` or `ai_budget` in-process** (DECIDED HERE, option
     (b)): `pretooluse_task.py` is started by `settings.json` as plain `python3
     ~/.claude/hooks/pretooluse_task.py` with no isolation, and re-exec'ing the whole T dispatcher
     (T1/T2 included) is 04's surface, not this file's. So gate-gtm obtains the trust result and the
     effective AI caps from an isolated **subprocess**: `gtm_env.TRUSTED_PYTHON -I -S -B -X
     pycache_prefix=<fresh P> <T>/tools/gtm/ai_budget.py <subcommand> --json` (the subcommand
     and its JSON are 04_hooks.md §4.6's to name; R41), which runs steps 0–2 itself and prints
     `forged`/`ok` per bucket; for the bare trust result, `approval_sig.py --trust-result`. gate-gtm
     parses the JSON (which already distinguishes `key_not_installed` → `company.json` caps from
     `forged`) and treats any nonzero exit, a timeout or unparsable output as `forged` (fail
     closed). R41 asks 04 to re-measure gate-gtm p95 against its 300 ms budget with
     this subprocess on the path. Test (B2): gate-gtm invoked through the **real dispatcher command
     line** of `settings.json` (`python3 <tmp R>/hooks/pretooluse_task.py` with a Task payload for a
     GTM seat) on a clean committed fixture tree returns a non-forged decision; the same with an
     untracked `tools/gtm/json.py` returns forged. **Test environment (exact; the 04_hooks.md §4.2
     `bash_gate.sh` pattern):** the hook process is started with `HOME=<tmp>/home`, where
     `<tmp>/home/.claude` is the fixture `R` (a real directory, or a symlink to it), **and**
     `CLAUDE_DIR=<the same path>`, `GTM_TEST=1`. `hooks/_lib.py` derives `_lib.CLAUDE_DIR` from
     `HOME` (it ignores `CLAUDE_DIR`), so without the `HOME` override the T2 pacer would claim leases
     in, and `_lib.log` would write to, the real `~/.claude/.agent_budget/` and
     `.enforcement/log.jsonl`. gate-gtm passes to the `ai_budget.py` subprocess the `T` that
     `gtm_env.test_mode(os.environ)` selects: test mode is on (`CLAUDE_DIR` and `GTM_TEST` are set, and
     `HOME` is not the passwd home), so `T = R` = the resolved fixture path, and the subprocess is
     `<T>/tools/gtm/ai_budget.py`. The test applies the header's **test-footprint oracle**: the
     Task payload's `session_id` and `tool_use_id` carry the run marker `m`, and no line appended to
     the real `~/.claude/.agent_budget/` files or `~/.claude/.enforcement/log.jsonl` during the run
     contains `m` (RED when `HOME` is not overridden: the pacer's claim row records the payload's
     `tool_use_id` and `session`, and `_lib.log`'s identity fields record `session`); it never
     compares the mtimes of those files, which concurrent dispatches write continuously. **The rest of the exact
     environment:** `CSA_ENFORCE=1` is also set (with a tmp `HOME` there is no `~/.claude/.enforce`,
     so `_lib.enforcing()` would be log-only and gate-gtm's deny would never be emitted); the fixture
     `R` holds `agents/<the GTM seat>.md` (with its `model:` frontmatter) and
     `knowledge/model_policy.json` pinning that seat to the same model, so T1 `model_pin_gate`
     (which reads `<HOME>/.claude/agents/` and the policy from the fixture) allows the dispatch and
     gate-gtm's own decision is the one observed. **Observation (both, and they must agree):** stdout
     of the dispatcher — a `forged` decision is the PreToolUse deny JSON whose reason names
     gate-gtm's `forged` code, a non-forged decision prints no deny — **and** the tmp
     `<tmp>/home/.claude/.enforcement/log.jsonl`, read with the dispatcher's **existing** row shape
     (`hooks/pretooluse_task.py` logs only when a gate blocks, `_lib.log(HOOK_NAME, "would-block",
     gate=…, reason=…, enforce=…)`, and nothing on allow; 04_hooks.md §4.6 gives gate-gtm's row):
     **forged** → exactly one row with `hook == "pretooluse_task"` (the dispatcher's `HOOK_NAME`),
     `decision == "would-block"`, `gate == "gtm_task_gate"` (04's module name for gate-gtm),
     `reason` == the deny code 04 §4.6 names for a forged budget (`gtm-budget` today), `enforce ==
     true`, and `forged == "trust_root"` on the trust-failure path; **non-forged** → **no** row with
     `gate == "gtm_task_gate"` and `decision == "would-block"` for the call (there is no allow row;
     should 04 ever add one, R77 asks it to name its `decision` string here and in R69, and this
     oracle then also requires that row). **Fail-closed lives inside gate-gtm:** the T dispatcher's
     outer `except Exception: return 0` fails open, so gate-gtm catches every exception of its own
     (subprocess spawn, JSON parse, timeout) and returns `forged`; R69 asks 04 §4.6 to state this.
     B2 test: gate-gtm with `ai_budget.py` replaced in the fixture tree by a script that raises →
     `forged`, observed as above (RED when gate-gtm lets the exception escape to the dispatcher).
   - **Isolated interpreter.** Every entry point runs under `gtm_env.TRUSTED_PYTHON -I -S -B -X
     pycache_prefix=<P>`. **All interpreter and prefix validation happens in the pre-import block,
     before any `tools/gtm` import (DECIDED HERE; the earlier placement inside
     `approval_sig.trust_root_ok` ran only after `import gtm_env`/`import approval_sig`, so a crafted
     pyc for either, read through a caller-supplied `-X pycache_prefix`, replaced the check itself
     before it ran — reproduced by review: under `TRUSTED_PYTHON -I -S -B -X pycache_prefix=P`, a
     timestamp-valid pyc at `P/<abs source dir>/<mod>.cpython-313.pyc` for an imported module
     executed while `P`'s top level held only a directory).**
     **The pre-import block (exact).** The file's first statements (after `from __future__ import
     annotations`, below) form a block that imports **only** `sys`, `os` and `atexit` — built-in or
     frozen in `TRUSTED_PYTHON` (measured 2026-09-28: `_imp.is_frozen` is true for `os`,
     `posixpath`, `stat`, `genericpath`; `sys` and `atexit` are in `sys.builtin_module_names`), so no
     pyc under any prefix is read for them — never `tempfile`, `json`, `shutil`, `gtm_env` or any
     `tools/gtm` module (under a non-isolated first interpreter `gtm_env` could be shadowed through
     the script directory or `PYTHONPATH`). It carries its own literal `TRUSTED_PYTHON =
     "/opt/homebrew/opt/python@3.13/bin/python3.13"` and its own temp-root function
     `_gtm_tmp_root() = os.path.realpath(os.environ.get("TMPDIR") or "/tmp")` (with `/tmp` when that
     value is not an existing directory) — the one definition of "the temp root" for this section
     (A2 test: the `TRUSTED_PYTHON` literal and the `_gtm_tmp_root` body are identical in each of the
     four entry-point files and equal `gtm_env.TRUSTED_PYTHON` / `gtm_env.gtm_tmp_root`, RED when
     one drifts; 00 §1.1 now exports `gtm_env.gtm_tmp_root()` with this body, R80 (d), and 04 §4
     "Isolated subprocesses" creates every `<fresh P>` directly under it, wave1e). In
     `approval_sig.py`, `gtmlib/approvals_verify.py` and `ai_budget.py`, which are also imported as
     modules, the block sits under `if __name__ == "__main__":`, so importing them never re-execs,
     strips `argv` or exits; `act.py` is only ever run. The block does, in order:
     (1) **Re-exec trigger.** When `argv[1]` is **not** `--gtm-reexeced` **and** any of these holds —
     `os.path.realpath(sys.executable) != os.path.realpath(TRUSTED_PYTHON)`; any of
     `sys.flags.isolated`, `sys.flags.no_site`, `sys.flags.dont_write_bytecode` is false;
     `sys.pycache_prefix` is `None`; `sys._xoptions.get("frozen_modules", "on") != "on"` (a caller's
     `-X frozen_modules=off` would make `os` load from source, and so from the prefix) — the block
     creates a fresh prefix `<P>` = `_gtm_tmp_root() + "/gtm_pyc_" + os.urandom(8).hex()` with
     `os.mkdir(<P>, 0o700)` (a new random name on `FileExistsError`, at most 100 tries, else exit
     11 `trust_interpreter`; no `tempfile` import) and `os.execv`s the literal `TRUSTED_PYTHON`
     (never `sys.executable`) with `-I -S -B -X pycache_prefix=<P>`, the absolute script path, the
     sentinel `--gtm-reexeced` as `argv[1]` and the original arguments unchanged. A prefix that is
     **set** but fails a fact of (3) does **not** trigger a re-exec: (3) refuses it.
     (2) **At most one re-exec.** When `argv[1]` is `--gtm-reexeced`, the sentinel is removed from
     `sys.argv` and no re-exec happens whatever the state, so a condition still false after the
     re-exec is refused by (3), exit 11, never a loop. (A caller that passes the sentinel itself
     gains nothing: it only suppresses the re-exec, (3) then fails closed, and — by the cleanup rule
     below — it cannot make the process delete anything it did not create.)
     (3) **Interpreter and prefix facts, checked here.** Every one must hold, else the block writes
     the fixed line `trust_interpreter` to stderr (and, for act.py, the literal failure line 02_act.md
     §2.3 names for a pre-import refusal, R75) and exits 11 **from the block**, before any further
     import: `os.path.realpath(sys.executable) == os.path.realpath(TRUSTED_PYTHON)`;
     `sys.flags.isolated`, `sys.flags.no_site` and `sys.flags.dont_write_bytecode` true;
     `sys._xoptions.get("frozen_modules", "on") == "on"`; `sys.version_info >= (3, 11)` (02_act.md
     §2.1 "Interpreter"); and `<P>` = `sys.pycache_prefix` is not `None` and: `os.lstat(<P>)` shows a
     directory and not a symlink; its permission bits are exactly `0o700`; it is owned by
     `os.geteuid()`; its basename starts with `gtm_pyc_`; `os.path.realpath(os.path.dirname(<P>))
     == _gtm_tmp_root()`; and it **contains no entry at all** (`os.scandir(<P>)` yields nothing — a
     subdirectory is an entry, so the prefix is empty recursively). **This one emptiness definition,
     "no entry", is used here, by the cleanup registration and by `trust_root_ok`.**
     (4) **Cleanup registration (only a prefix this process can prove it owns).** Only when `argv[1]`
     was the sentinel (so the pre-re-exec parent created `<P>` by (1)) — and (3) has passed for
     `<P>` — the block registers `atexit` → `os.rmdir(<P>)` with `OSError` ignored. `rmdir` removes
     only an **empty leaf directory** and fails on a symlink, a file or a non-empty directory, so even
     a prefix swapped after registration is never recursively deleted; `shutil.rmtree` is never used.
     A process started without the sentinel (a caller such as gate-gtm that passed its own fresh
     prefix) never removes `<P>`: its creator does. A crash leaves only an empty 0700 directory under
     the temp root.
     **Child order after the block (exact):** (5) append the code dir to `sys.path` ("Code root"
     below); (6) `import gtm_env` and `import approval_sig` (the pre-check set) — now compiled from
     source, because the prefix was proved empty and `-B` writes nothing into it; (7)
     `approval_sig.trust_root_ok(...)`, which **re-checks** the same interpreter and prefix facts of
     (3) as defence in depth (a caller that imports `approval_sig` in a process whose block did not
     run — e.g. a test — still gets `trust_interpreter`); only then any other import. **gate-gtm and
     any other caller that starts an entry point with its own prefix** create it by the same rule as
     (1) (`gtm_pyc_` + random hex under the same temp root, mode 0700, empty), or the child refuses
     it under (3) (R77 asks 04 §4.6 to use this rule). Because `TRUSTED_PYTHON` holds only
     `python3.13` (no `python3` in `dirname(TRUSTED_PYTHON)`, measured), `TRUSTED_PYTHON` is always
     named by its full path, never looked up.
     `-I` drops the script directory, user site and every `PYTHON*` variable. `-S` drops
     site-packages, so a writable venv or Homebrew site-packages (and its `.pth` files) never loads.
     `-B` stops bytecode writes. `<P>` is **always** fresh and empty, for act.py, the CLIs and every
     subprocess gate-gtm starts alike; there is no persistent bytecode prefix (the earlier
     `S/pycache/` option is withdrawn: `-B` never filled it, and Python would still **read** a crafted
     timestamp-valid pyc from it). With a fresh, empty prefix Python reads no pyc from an in-tree
     `__pycache__/` and none from anywhere else; every import after the block compiles from source
     (its latency is part of R41's measurement, never assumed).
     **Residual before the block (stated):** the interpreter's own start-up imports run before any
     statement of the file. Under `-I -S -B` the only non-builtin, non-frozen modules loaded at
     start-up are `encodings`, `encodings.aliases` and `encodings.utf_8` (measured 2026-09-28 with
     `sys.modules` and `_imp.is_frozen`), and Python looks for their pyc under the caller's prefix.
     Whether a crafted pyc there executes is **UNVERIFIED** here (an attempt to measure it was not
     run); the A2 test below records the outcome. Either way it is the same class as a
     `sitecustomize` hook in the first interpreter ("What stays outside this check"): it needs the
     caller to choose the prefix, and the control is preventive — R77 asks 04 G-B to deny agent
     commands that pass `-X pycache_prefix`, `-Xpycache_prefix`, `-X frozen_modules` or a
     `PYTHONPYCACHEPREFIX` assignment to a GTM entry point.
     A2 tests (each RED when its rule is reverted): an entry point started directly as
     `TRUSTED_PYTHON -I -S -B -X pycache_prefix=<dir> <file>` with a correctly named, 0700, empty
     `<dir>` under the temp root runs (no re-exec; the test observes a single process); the same
     with `<dir>` holding a file exits 11 `trust_interpreter` from the block (single process, no
     `tools/gtm` module in the import-recorder log); the same with `<dir>` whose top level holds
     **only a subdirectory** `private` → exit 11 (RED under a "contains no file" test); **the
     falsification test:** a crafted `approval_sig.cpython-313.pyc`, and separately a crafted
     `gtm_env.cpython-313.pyc`, each with a header matching the source mtime and size, placed at
     the mirrored path `<dir>/<abs source dir>/<mod>.cpython-313.pyc` of a prefix passed as `-X
     pycache_prefix=<dir>`, does not execute (its side effect — a marker file — is absent) and the
     run exits 11 `trust_interpreter` (RED when the prefix check is moved back into
     `trust_root_ok`); one started with `/usr/bin/python3` re-execs once and runs, and leaves no
     `gtm_pyc_*` directory behind; one started with `-X frozen_modules=off` and correct flags
     re-execs once and runs; one started as `TRUSTED_PYTHON <file> --gtm-reexeced …` without `-I`
     exits 11 `trust_interpreter` and spawns no child (RED when the sentinel is ignored); `import
     approval_sig` (and `ai_budget`, `gtmlib.approvals_verify`) from a test process with
     `sys.argv[1] = "--gtm-reexeced"` leaves `sys.argv` unchanged and does not exec or exit (RED
     when the block is not under `if __name__ == "__main__":`); a static test that every module the
     block imports is in `sys.builtin_module_names` or `_imp.is_frozen` under `TRUSTED_PYTHON`, and
     that the block imports nothing else (RED when `tempfile` is imported there); **cleanup** (each
     RED under the earlier `atexit → shutil.rmtree` rule): started as `TRUSTED_PYTHON -I -S -B -X
     pycache_prefix=<tmp dir holding a file> <file> --gtm-reexeced …` → exit 11 and that directory
     and its file intact; the same with an **empty** directory not named `gtm_pyc_*` → intact; the
     same with an empty `gtm_pyc_*` directory outside the temp root → intact; **startup residual
     (records, does not gate):** a crafted `encodings/aliases.cpython-313.pyc` at the mirrored path
     of a caller prefix — the test records whether its side effect occurs and asserts only that the
     entry point then exits 11 (the prefix is not empty), so the recorded outcome is the plan §17
     note for this residual.
   - **Python 3.9 parse rule for entry-point files (DECIDED HERE).** An entry point may be started
     by a bare `python3` that resolves to `/usr/bin/python3` 3.9.6 (launchd), and Python parses the
     whole file before its first statement runs, so a 3.10+ construct anywhere in an entry-point
     file is a `SyntaxError` before the re-exec. Every entry-point file — `tools/gtm/act.py`,
     `tools/gtm/approval_sig.py`, `tools/gtm/gtmlib/approvals_verify.py`, `tools/gtm/ai_budget.py`
     — therefore starts with `from __future__ import annotations` and uses no syntax newer than 3.9
     (no `match`, no parenthesized context managers, no `except*`, no PEP 695 generics); `X | Y`
     appears only in annotations. Modules they import after the re-exec are unaffected. A2 test:
     `/usr/bin/python3 -m py_compile` of each of the four files succeeds (skipped with a visible
     reason only when `/usr/bin/python3` is absent). Every documented command in this file names
     `gtm_env.TRUSTED_PYTHON` by full path as well (R59), so the re-exec is a backstop, not the
     normal path.
   - **Code root (DECIDED HERE).** The **code dir** is always the `tools/gtm` directory of the
     script path as started: `os.path.dirname(os.path.abspath(__file__))` for an entry point directly
     in `tools/gtm/` (`act.py`, `approval_sig.py`, `ai_budget.py`), and
     `os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` for
     `tools/gtm/gtmlib/approvals_verify.py` (one definition; the API's `__main__` comment uses the
     same). The entry point **appends** (never prepends) the code dir to `sys.path` — **without**
     symlink resolution (00_global_paths.md §1.5's test trees
     hold symlinked modules in a real tmp `tools/gtm/`; `resolve()` would jump to the real tree) and
     never `R/tools/gtm` (R is the state root). `trust_root_ok` reports `trust_root_mismatch`
     (`paths: ["code_root:<dir>"]`) when **`not gtm_env.same_root(<code dir>, T/"tools/gtm")`**
     (`samefile` when both exist, which they do for a running entry point) — never a `normpath` text
     compare, because on this Mac `/tmp → /private/tmp` and `$TMPDIR` (`/var/folders/…`) →
     `/private/var/folders/…` are symlinks, so an entry point started as `/tmp/x/tools/gtm/act.py`
     has the unresolved code dir `/tmp/x/tools/gtm` while `T` (resolved, header) is
     `/private/tmp/x`. The `sys.path` entry stays the unresolved directory (the symlinked-module
     reason above); only the comparison uses `same_root`. So code from one tree is never judged by
     another tree's check; tests therefore start `<tmp R>/tools/gtm/act.py`, never the real one. A2
     test: with `CLAUDE_DIR=/tmp/x` (unresolved), act.py started as `/tmp/x/tools/gtm/act.py` and as
     `/private/tmp/x/tools/gtm/act.py` each reports no `code_root` entry (RED under a `normpath`
     compare), and act.py of a second tmp tree started with `CLAUDE_DIR` naming the first reports
     `code_root:<dir>`. At the entry point a stdlib module wins over a same-named top-level tree
     module. **After** `activity_log`, `harvest_tool_trail` or `backup_state` load, that stops being
     true: each runs `sys.path.insert(0, str(Path(__file__).resolve().parent))` as import-time code
     (activity_log.py:53, harvest_tool_trail.py:45, backup_state.py:26); `company` does the same only
     lazily, inside `company._pack_system_set`, the function that imports `activity_log` (cited by
     name: line numbers drift; R42/R61's `company.py:894` is stale, R70). All four insert the
     **resolved** directory, which in 00_global_paths.md §1.5's symlinked test trees is the real
     tree. **The one rule for those four is 00's (adopted here; R80 withdraws R42's "append"
     wording):** 00_global_paths.md §1.5 decides that the Appendix C item 14 coordinator change
     makes each of them **remove any existing entry for, then insert at index 0**, the
     **unresolved** directory `str(Path(os.path.abspath(__file__)).parent)` (requests/00_global_paths.md
     R41). Consequence, stated: once any of them has loaded, the code dir sits at `sys.path[0]`,
     ahead of the stdlib, so from then on a top-level `tools/gtm` module **would** shadow a
     same-named stdlib module (and, until the retrofit lands, in a symlinked test tree the real
     tree's directory is the one at index 0). That is harmless only because the trust check has
     already passed before any of them can load (steps 0–2 run first) and the A2 static test (step
     2) holds: no top-level `tools/gtm` module name is in `sys.stdlib_module_names`. R61 extends
     the same rule to any later import-time insert.
   - **Interpreter pin (DECIDED HERE).** `gtm_env.TRUSTED_PYTHON =
     "/opt/homebrew/opt/python@3.13/bin/python3.13"` (the Homebrew `opt` link, which survives
     `brew upgrade` within 3.13; its realpath today is
     `/opt/homebrew/Cellar/python@3.13/3.13.14_1/Frameworks/Python.framework/Versions/3.13/bin/python3.13`).
     `gtm_env` is in the pre-check set (write-protected, "Which TRUST_PATHS are prevented", §5.6),
     so the pin cannot be edited undetected by an agent. It is never `python3` on `PATH`: in CSA
     sessions that is the repo's `.venv/bin/python3`, a symlink in an agent-writable directory, and
     under launchd it is `/usr/bin/python3` 3.9.6. R43 asks 04 to deny agent writes under
     `/opt/homebrew/opt/python@3.13/` and `/opt/homebrew/Cellar/python@3.13/` and agent `brew`
     commands naming `python@3.13`. R43's other half (07 setting `__PY_DIR__` to
     `dirname(TRUSTED_PYTHON)`) does **not** work as written: that directory holds only
     `python3.13` (measured: no `python3` there), so a bare `python3` would still resolve elsewhere
     on `PATH`. R59 replaces it: every command 07/08 render or document for a GTM entry point names
     `/opt/homebrew/opt/python@3.13/bin/python3.13` (= `TRUSTED_PYTHON`) by full path.
   - **Check before import.** An entry point imports `approval_sig` and calls `trust_root_ok`
     **before importing any other `tools/gtm` module** (gtmlib, company, …). `approval_sig`
     imports only the stdlib and `gtm_env` (stdlib-only; it supplies `real_root`/`test_mode`,
     00_global_paths.md §1.1). These two are the **pre-check set**: they load before the check can
     judge them, so they must be write-protected, not detected (see "Which TRUST_PATHS are
     prevented" in §5.6). `ed25519_verify.py` is imported only after the check passes (step 4), so
     the check covers it. So nothing else a modified module could patch is
     loaded when the check runs. **On failure act.py imports nothing further and exits 11 for every
     subcommand**, read-policy ones included: a modified gtmlib would run with credentials, so it
     must never load. **The exceptions are exactly the stdlib-only fallbacks of 02_act.md §2.3
     "Stdlib spool exceptions"** — the four there today plus the read-ticket fallback below (R67) —
     (that section owns their behaviour; each writes create-exclusive 0600 files, imports nothing
     from `tools/gtm` beyond `approval_sig`/`gtm_env`/`act_fallback`, and exits 0 with
     `result.fallback: "trust"` after the trust notice is written): `lead-append` (spools its raw
     input to `S/lead_spool/`; the first trusted run replays it into `ST/lead_fallback.jsonl`,
     03_schemas.md §3.14, so no **received** lead is lost, R11); `ingest-findings` (spools to
     `S/findings_spool/` and writes one urgent pushed notice per `runaway_spend` /
     `phi_encountered` finding through `approval_sig.write_urgent_notice`, API above — the path by
     which plan §20.6's "urgent cards notify through every channel" survives a trust failure);
     `pause` (spools to `S/pause_spool/`, which G-A reads as a company-wide pause); `cancel`
     (writes the ordinary `S/cancels/<slug>/<action_id>` marker, `who: "agent"` — **after the same
     `approval_stands` check as the normal path (DECIDED HERE):** under the nonce-ledger lock
     (03_schemas.md §3.9, taken with stdlib `fcntl`) it reads, with stdlib `json` only, the action's
     request `S/approval_requests/<slug>/<request_id>.json` (the `request_id` found by scanning that
     directory for the matching `action_id`), `S/approvals/<slug>/<request_id>.json` and the nonce's
     lines in `S/approval_nonces.jsonl`; when an approval record exists whose `decision` is
     `approved` and whose payload nonce has no `consume` line, it refuses exit 3 `approval_stands`
     and writes **nothing** (no marker, no notice); an unreadable or unparsable request, record or
     ledger also refuses exit 3 `approval_stands` (fail closed: a trust drift must never let an
     agent stop an operator-signed action). The ingest rule of §5.1 step 5 is the second barrier: a
     `who: "agent"` marker never cancels an action with an approval record, and G-A rule 6b ignores
     it for such an action's ticket, R77); and **`ticket --read` /
     `ticket --close <read ticket>`** (below).
     **Read-ticket fallback (DECIDED HERE; keeps inbox lead capture running during landings and dev
     drift, plan §5 "never lets a lead sit unlogged", §6.8, §7.4 step 3).** A read ticket grants only
     `click` and `navigate_back` (plus the always-allowed reads) on a fixed host list (plan §6.7), so
     minting one needs no untrusted module. Under a step-0 failure, `ticket --read --company <slug>
     --systems a,b[,…] [--run <id>]` is served by `act_fallback`: (i) it lists `HEAD:tools/gtm/runbooks/`
     and reads each runbook's bytes with the **step-2 `/usr/bin/git` invocation** (`ls-tree -r -z
     --full-tree HEAD -- tools/gtm/runbooks/`, then `cat-file blob HEAD:<path>`) — never the working
     tree, so an uncommitted runbook edit cannot widen host scope; (ii) for each named system it
     requires **exactly one** HEAD runbook whose JSON has `"schema": "gtm.runbook.v1"` and `system`
     equal to that name (06_connectors.md §6.4: `system` = the file stem; R67 asks 06 to confirm the
     stem equals the tier-system name for every system with read paths), and `read_hosts`/`login_hosts`
     that are lists of lowercase hostnames matching
     `^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$`; (iii) it writes
     the 03_schemas.md §3.6 read-ticket record — `class: "read"`, `allowed_hosts` = the union of
     those lists, `allowed_tools = ["click", "navigate_back"]` (+ the always-allowed reads, exactly as
     the ordinary mint writes them), `max_calls` 60 per system, `expires` 10 min per system capped at
     60 min, `bound_agent_id: null`, `session_id` from the same source the ordinary mint uses (02
     §2.4), plus `"minted_by": "trust_fallback"` — create-exclusive 0600 at
     `S/tickets/<slug>/<ticket_id>.json` (id per 00 §0.3), so G-A reads it unchanged. No pause check
     is needed: every pause row allows read tickets (03_schemas.md §3.10). `ticket --close <id>` is
     served only when that file's `class` is `read` (it becomes `closed`); any other close keeps
     the exit-11 refusal. **Refusals** (any of (i)–(ii) failing — git error, no or several runbooks
     for a name, a malformed runbook) keep the exit-11 refusal **and** write the per-company notice
     below, so lead capture is never silently lost. The ordinary mint's pack-dependent checks are
     skipped only because none restricts a read ticket beyond host validation, which the L3 manifest
     test already ran on the committed runbooks (06_connectors.md §6.4); R67 asks 02 to confirm this,
     and should 02 name a pack-dependent read-ticket check, the fallback refuses that company
     instead of skipping it.
     **Deviation from plan §20.8 (stated, narrowed): the refusal is still wider than `$`.** Plan §20.8
     scopes a trust mismatch to money: act.py "refuses every `$` action" and `PAUSE.trust` means "all
     `$` refused". This contract refuses every act.py subcommand except the fallbacks, because the
     modules a non-`$` command imports (gtmlib, connectors) are exactly what the check could not vouch
     for, and they run with the company's credentials. **Consequence, stated plainly:** while any
     TRUST_PATH differs from HEAD, `read-run`, `verify`, `snapshot`, non-money `authorize`/`execute`
     and non-money `revert` are refused for every company — including the `read-run`, `verify` and
     `revert` plan §6.8 keeps running under stops. Inbox lead capture continues (read-ticket fallback
     above; leads spool through `lead-append`). **This residual is not ratified by the plan** (a
     grep of the plan on 2026-09-28 finds no amendment for it): it is entry **V2** of the §5.9
     Deviation register, which **blocks the start of WP-A2 implementation** until the planner lands
     a plan §20.x amendment recording it — with an explicit operator-facing ratification that
     verify, read-run and non-money revert stop globally during any trust drift, which happens
     during every landing and every in-tree edit — or this contract is conformed (§5.9 names the
     candidate narrowing: running verify and revert from a verified `git archive HEAD` extract of the
     trust root). R67 and R81 carry the ask. Plan §5's "never lets a lead sit unlogged" is kept for the
     fallback's own refusal cases by telling the operator: (1) the trust notice body (§5.6 "Trust
     notice") always ends with the line "While this lasts, verify, read-run and non-money reverts
     are refused for every company; inbox lead capture continues."; (2) a `ticket --read` that the
     fallback refuses writes, through `approval_sig.write_urgent_notice`, one urgent pushed
     **`task`** notice per company it was asked for (slug = `--company`, title `"GTM inbox check
     could not run — check <company>'s inboxes by hand today"`, `dedupe_key =
     "lead_capture_stopped:<slug>:<UTC date>"`) before exiting 11 (R54 asks 02 §2.3 to add this to
     the `ticket --read` refusal); this notice is the plan §5 same-day operator task for the
     duration, because the home's own task surface (a gtmlib write) cannot be written while gtmlib
     must not load; (3) the first trusted inbox run after the tree clears adds, on each home's
     operator task surface, a same-day task "GTM lead capture was stopped from <first
     lead_capture_stopped ts> to <now>; check <inboxes> for that window" and resolves the
     `lead_capture_stopped` notices (R54 asks 07's inbox prompt for this).
     A2/B2 tests: with an uncommitted `tools/gtm/x.py` in a fixture tree, `act.py ticket --read
     --company <fixture slug> --systems gbp` exits 0 with `result.fallback: "trust"`, the ticket file's
     `allowed_hosts` equal the HEAD `gbp` runbook's `read_hosts ∪ login_hosts`, and no `gtmlib`
     module is in `sys.modules` at exit (RED when the fallback imports gtmlib); with the working-tree
     `gbp.runbook.json` also edited to add `evil.example`, the ticket still excludes it (RED when the
     runbook is read from the working tree); `ticket --close` of that ticket exits 0 and marks it
     `closed`; with the fixture tree's HEAD runbook for `gbp` removed, the call exits 11 and an open
     urgent `task` notice with `dedupe_key` `lead_capture_stopped:<fixture slug>:<date>` exists (RED
     when (2) is removed); the `runtime` trust notice body contains "inbox lead capture continues";
     after the file is committed, the next inbox run's trusted path writes the home-surface task and
     resolves any `lead_capture_stopped` notice.
     A2 test for the fallback `cancel` (RED when the fallback writes the marker without the check):
     a fixture tree with an uncommitted TRUST_PATH (`tools/gtm/x.py`) plus an operator-approved,
     unconsumed `urgency: urgent` campaign pause → `act.py cancel <action_id>` exits 3
     `approval_stands`, no file exists at `S/cancels/<slug>/<action_id>`, and after the file is
     committed `execute` of the pause succeeds and the platform fixture records it; the same
     fallback `cancel` of an unsigned `held` action writes its marker and exits 0 (`result.fallback:
     "trust"`).
   - **What stays outside this check, stated plainly.** Code that runs before act.py's first line
     — a `sitecustomize`/`usercustomize`/`.pth` hook picked up by the *first* (non-isolated)
     interpreter, or a fake `python3` on `PATH` — can defeat any in-process check, the re-exec
     included. That boundary is preventive, not detective: G-B denies act.py commands carrying any
     `PYTHON*=` assignment or `export PYTHON…`, and writes to `site-packages`, `*.pth`,
     `sitecustomize.py` or `usercustomize.py` anywhere (R15). After the re-exec the interpreter is
     `TRUSTED_PYTHON` (checked by realpath above); its own files are trusted, protected only by
     R43's denial. `/opt/homebrew` is writable by the operator's user, so this is a stated residual
     risk, not a proof.
1. **Public key.** Read with `git cat-file blob HEAD:tools/gtm/approver_pubkey.pem` using the step-2 git
   invocation. Working-tree bytes ≠ HEAD bytes, or a HEAD pem absent from the working tree →
   `trust_root_mismatch`. No HEAD copy: step 1 passes when the working tree has none either (the
   not-yet-installed state; `verify_signature` then returns `key_not_installed` at key lookup), and
   is `trust_paths_untracked` when it has one. The pem contributes one path to its kind's single
   entry (API comment above).
   Retired keys (§5.6 rotation) are read the same way from `HEAD:tools/gtm/approver_pubkeys/`.
2. **Working tree equals HEAD, independent of index, ignore rules and caller environment.**
   - **Git invocation.** Always `/usr/bin/git`, never `PATH` git, with a scrubbed environment:
     `{PATH: "/usr/bin:/bin", HOME, LANG: "C", GIT_CONFIG_NOSYSTEM: "1", GIT_CONFIG_GLOBAL:
     "/dev/null", GIT_NO_REPLACE_OBJECTS: "1"}`. No other `GIT_*` variable, no `DEVELOPER_DIR`.
     Arguments: `/usr/bin/git --no-replace-objects -c core.fsmonitor=false -c core.untrackedCache=false -C <T> …`
     (`T` = the trust root, header; every TRUST_PATH below is relative to `T`).
   - **HEAD side.** `ls-tree -r -z --full-tree HEAD -- <TRUST_PATHS>` gives `(mode, blob sha, path)`,
     then **filtered by the same exclusion set as the walk** (below). The exclusion set is one
     function, `approval_sig._excluded(relpath) -> bool`, applied to both lists before any
     comparison.
   - **Working-tree side.** For a **directory** TRUST_PATH, `os.walk(followlinks=False)` — which
     still lists a symlink to a directory in `dirnames` (it only does not descend into it), so the
     walk `os.lstat`s every entry of **both** `dirnames` and `filenames` and judges any symlink
     among them by the symlink rule below (never as a directory to skip, never as a missing file); for a
     **file** TRUST_PATH (`telemetry/pricing.json`), `os.lstat` and hash it directly (an `os.walk`
     over a file yields nothing and would report it missing). No `git diff`, no `ls-files`, no
     index, no `.gitignore`: `update-index --skip-worktree`/`--assume-unchanged`, an fsmonitor hook
     and ignore rules therefore cannot hide a file. `tools/gtm/approver_pubkey.pem` is skipped on
     both sides here (step 1 owns it).
   - **Rules.** Every walked file (after the exclusions below) must be in the (filtered) HEAD list, else
     `trust_paths_untracked`. Its blob sha, computed in Python as
     `sha1(b"blob %d\0" % len(data) + data)`, must equal HEAD's, else `trust_paths_modified`. A
     (filtered) HEAD path missing from the walk is `trust_paths_modified`; an excluded tracked path
     (e.g. `tools/gtm/tests/test_x.py`, `tools/gtm/README.md`) is never compared, on either side. A symlink (file or directory) passes only
     when HEAD has that path with mode `120000` and the same target bytes. Any `*.so`, `*.dylib`,
     `*.pyd` or `*.pth` anywhere, and any `*.pyc`/`*.pyo` outside a `__pycache__/` directory, is
     `trust_paths_untracked` even when tracked (a sourceless pyc beside a module, or an extension
     module, would load ahead of the source).
   - **TRUST_PATHS (DECIDED HERE; the whole import closure).** `tools/gtm/` (the entire subtree)
     and `telemetry/pricing.json`. This covers `act.py`, `__init__.py`, `gtmlib/`, `connectors/`,
     every standalone module (`approval_sig`, `ai_budget`, `gtm_pricing`, `company`,
     `system_names`, `gtm_result`, `provenance`, `project_dirs`, `transcript_index`,
     `autonomy_ladder`, `notices`, `gtm_lists`, `activity_log`, `harvest_tool_trail`, `gtm_env`,
     the Ed25519 verifier `ed25519_verify.py`, …), `company_schema.json`, `tier_table.json`,
     `review_lanes.json`, `approver_pubkey.pem`, `approver_pubkeys/`, `approver_fingerprint.txt`,
     `approver_cdhash.txt`, `approver_probe_p.json` and the approver source `approver/` (§5.3).
     A new module needs no list edit, and an untracked `tools/gtm/json.py` is caught.
     **Excluded (named, fixed; `_excluded`, applied to BOTH sides):** `tools/gtm/tests/`,
     `tools/gtm/gtmlib/tests/`, `tools/gtm/connectors/*/tests/`, `tools/gtm/contracts/`,
     `tools/gtm/wave2_pending/` (04_hooks.md's pending wiring patches; `.patch` files, never
     imported), top-level `tools/gtm/*.md`, files named `.DS_Store`, and the contents of
     `__pycache__/` directories (never read, because every entry point sets a fresh
     `pycache_prefix`; step 0). **Detection vs prevention differ on purpose (stated):** 04's
     prevention predicate `trust_root_path()` (§5.6 "Which TRUST_PATHS are prevented") excludes only
     `tests/`, `connectors/*/tests/`, `contracts/` and top-level `*.md`, so `gtmlib/tests/`,
     `wave2_pending/`, `.DS_Store` files and `__pycache__/` contents are **prevented** (a live-tree
     tool edit there needs a trust-edit marker) but **not detected** here. Prevention broader than
     detection is the safe direction: detection must skip them because they are never imported and
     their churn must not become a global trust failure, while nothing is lost by also guarding
     them against agent writes. R77 asks 04 to state the asymmetry beside `trust_root_path()` (and,
     should 04 ever narrow prevention to match, to keep every path this list does **not** exclude
     prevented). A2 static test: no TRUST_PATHS module imports a `tests` module or
     anything under `wave2_pending/`, and no top-level `tools/gtm` module name is in
     `sys.stdlib_module_names`. A2 test (RED when the HEAD-side filter is removed): a fixture repo
     that **commits** `tools/gtm/tests/test_fixture.py`, `tools/gtm/gtmlib/tests/test_g.py`,
     `tools/gtm/wave2_pending/x.patch` and a top-level `tools/gtm/README.md`, with a clean working
     tree, gives `trust_root_ok` → `(True, [])` and `--trust-check` exit 0; deleting the committed
     `tests/test_fixture.py` from the working tree also stays clean.
   - **Reasons for the closure.** `gtm_result` decides reviewer/verifier identity (maker-checker);
     `provenance` is the AI-label check; `project_dirs` decides spend attribution (an edit that
     returns False makes rows `unattributed`, not charged, and silently disables the cap);
     `autonomy_ladder` decides shadow exit and breaker-pause removal; the tier table and lanes
     decide money class. All of them run in act.py's process or in gate-gtm's isolated subprocess
     (step 0).
   - **Where it runs (F-trust):** once per process at entry (step 0) for every act.py command; in
     `ai_budget.effective_ai_caps`/`budget_state` (04_hooks.md §4.6, via the cached result), which
     run only inside the isolated `ai_budget.py` subprocess gate-gtm starts (step 0), never in the
     hook process; inside
     `verify_signature` (cached result); and daily via `--trust-check` (§5.6). Never only for actions
     already classed `money`, since these files decide that class. A process computes the full walk
     once; `verify_signature` reuses `trust_result(R)` (≤ 60 s old), so a dispatch that verifies N
     records spawns git once, not N×3 times.
   - **Falsification tests (A2, each passing once its check is reverted):** an untracked
     `connectors/zz/write.py` makes every money operation exit 11; an untracked `tools/gtm/json.py`
     makes a money operation exit 11; an uncommitted edit to `gtm_result.py`, to `provenance.py`, and
     to `project_dirs.py` (returning False) each make a money operation exit 11 (and B2: that
     `project_dirs.py` edit puts the company in budget state); an uncommitted edit to
     `tier_table.json` makes a non-money `authorize` exit 11 (A1, 02_act.md §2.3);
     `git update-index --skip-worktree tools/gtm/tier_table.json` plus an edit still exits 11;
     with an uncommitted `tier_table.json` edit, `PATH=<dir with a fake git that prints nothing>`
     still exits 11 (only `/usr/bin/git` is ever run); a crafted
     `gtmlib/__pycache__/store.cpython-313.pyc` whose header matches the source mtime and size does
     not execute (its side effect is absent) and the command proceeds; a sourceless
     `gtmlib/zz.pyc` exits 11; act.py started with `PYTHONPATH` pointing at a dir holding `json.py`
     does not import it (re-exec with `-I`); an uncommitted `gtmlib/store.py` that replaces
     `approval_sig.trust_root_ok` with `lambda *a, **k: (True, [])` at import still exits 11,
     because act.py runs the check before importing gtmlib. These tests run the entry points as
     subprocesses against a tmp `CLAUDE_DIR` git repo; there is no environment variable or flag that
     skips any part of steps 0–2 (a test-only bypass would be a production bypass).
     **Fixture trees hold real copies of every file a test edits (DECIDED HERE; never write through a
     symlink into the live tree).** 00_global_paths.md §1.5's B2 recipe builds the tmp
     `tools/gtm/` with its `*.py` modules and `gtmlib/`/`connectors/` as **symlinks** to the real
     files; an uncommitted-edit test that followed that recipe would write through the link into the
     live `~/.claude/tools/gtm` — a real global trust failure and a `PAUSE.trust` at the next daily
     check. So every trust-root falsification fixture in this section (step 0, step 2, IMP-05 below,
     §5.6) is a **real directory tree of real file copies** (`shutil.copytree(src, dst,
     symlinks=False)` of the committed files, then `git init`/`add`/`commit` inside the tmp
     `CLAUDE_DIR`), and a test that edits a file first asserts `not os.path.islink(<path>)` and that
     no ancestor of it inside the fixture is a symlink. A session-scoped fixture records, before the
     first such test and after the last, the sha256 and `st_mtime_ns` of every file under the real
     `gtm_env.real_root()/tools/gtm/` and of the real `real_root()/telemetry/pricing.json`, and fails
     the run on any difference (RED when a fixture is built from the symlinked recipe; a concurrent
     in-tree edit by another session also fails it, which the §5.6 development protocol forbids
     anyway).
   **Every other input that decides the AI-spend cap (IMP-05; DECIDED HERE):**
   - `telemetry/pricing.json` (tracked; `gtm_pricing`'s fallback price table, plan §17) is a
     TRUST_PATH. `gtm_pricing` parses it itself with `json`, never through `hooks/cycle_telemetry.py`
     (03_schemas.md §3.19).
   - `usage-dashboard/ccdash/pricing.py` **cannot** be a TRUST_PATH: it is git-ignored in `~/.claude`
     (`.gitignore` line 3 `/*` allowlist; `git check-ignore` verified 2026-09-27), so HEAD has no copy.
     Instead `gtm_pricing.py` (a TRUST_PATH) carries `CCDASH_PRICING_SHA256`, the sha256 of the
     ccdash file it was reviewed against. `price_usd` reads the file's bytes, hashes them **before
     importing anything from it**, and only when the hash equals the pin loads it from those same
     bytes: `mod = types.ModuleType("gtm_ccdash_pricing")`, `mod.__file__ = <path>`,
     `sys.modules["gtm_ccdash_pricing"] = mod` (registered first, so its `NamedTuple` resolves
     `__module__`), then `exec(compile(data, <path>, "exec"), mod.__dict__)`. Otherwise it prices from
     `telemetry/pricing.json` alone (plan §17's fallback order is kept) and its caller records the
     note `ccdash_unpinned` (03_schemas.md §3.19). So an edit to the ignored file can neither lower a
     price nor run code in gate-gtm's process.
   - `knowledge/model_policy.json` is deliberately **not** a TRUST_PATH. Ordinary non-GTM pin work
     edits it (16 commits 2026-07-01..09-27), and every uncommitted pin edit would otherwise be a
     global trust failure. Instead `system_names.seat_sets()` returns, per set, the **union** of the
     committed constant and the policy list (04_hooks.md §4). The policy can add a seat but never
     remove one. That is safe because all three sets only add enforcement: deny outside a GTM
     session, sequential browser dispatch, and budget counting.
   - Hook entry files under `hooks/` are not TRUST_PATHS: they do not run in act.py's process. Their
     integrity is the hook chain's own (HIGH-tier review, 04_hooks.md).
   - Falsification tests (A2 + B2 + G, each passing once its fix is reverted): an uncommitted edit to
     `telemetry/pricing.json` makes every money operation exit 11 and puts every company in budget
     state (forged); an edit to the ccdash file that makes `compute_cost_usd` return 0 makes a fixture
     spend window price from `telemetry/pricing.json` (non-zero, note `ccdash_unpinned`) and runs
     none of the edited file's module-level code; deleting a seat from `gtm_seats` in `model_policy.json` leaves that seat
     enforced by gate-gtm.

   The company pack (`<H>/.claude/gtm/company.json` and the pack files beside it) is not a
   TRUST_PATH. It lives in each company's own repo, and a pack edit must stop only that company. It
   is covered by the pack-from-HEAD rule (02_act.md §2.3, refusal `pack_uncommitted`, FID-07):
   `make_ctx` loads the pack from the home repo's `HEAD`, so every act.py stage, the money stages
   of step 5 included, runs against the committed pack.
3. **3a (in `verify_signature`):** the record parses and carries `payload_b64`, `signature_b64`,
   `alg`, `key_fingerprint` as strings with valid base64, else `malformed_record`; `payload_b64`
   byte-equal to the request's; decoded bytes == `canon(json.loads(decoded))` (non-canonical bytes
   refused); payload keys exactly `{v, company, card_id, action_id, system, account_id,
   new_absolute_value, unit, after_digest, display_sha256, nonce, expires}` (12 keys; R10) — a
   self-test payload can therefore never pass here. **Key lookup:** `key_fingerprint` equal to the
   HEAD current key's fingerprint → that key; equal to a retired key in
   `HEAD:tools/gtm/approver_pubkeys/index.json` → that key under the retired-key rule (§5.6
   rotation); otherwise `key_unknown`.
   **Export binding (in `approvals_verify.verify`, at stages `mint`, `execute`, `run_holds` and
   `revert`, right after the key lookup; plan §20.8 N1 "the trust root is not agent-editable").**
   HEAD holds the pem **and** its fingerprint anchor, and a commit can change both together (see §5.6
   "What the HEAD trust root does and does not guarantee": a non-GTM session can commit TRUST_PATH
   changes), so a commit that swapped in a self-generated key and a matching anchor would otherwise
   verify its own `$` signatures until the next daily check. So every money stage also requires the
   HEAD **current** key's fingerprint to equal `S/approver_fingerprint.json`'s `fingerprint` — a
   file written only by the app's `--export-pubkey` (§5.3) and closed to agents (04_hooks.md G-W and
   G-B rule c: `machine_written()` covers all of `S`). A difference, or that file missing, unreadable
   or without a valid `sha256:<64 hex>` `fingerprint` while HEAD has a pem, refuses
   `ActError(EXIT_TRUST, "pubkey_vs_export")` (exit 11); the operator recovers by re-running
   `--export-pubkey` (the daily check's `approver_export_missing` note stays a note there, TC3, but a
   money stage never proceeds without the export). Stages `authorize` and `complete` do not apply it
   (`authorize` spends nothing; `complete` records a platform write that already happened, step 5).
   A2 tests (each RED when the check is removed): a fixture tree whose HEAD commits a pem **and** an
   `approver_fingerprint.txt` for a fixture software key, with `S/approver_fingerprint.json` still
   naming the old key, and a record validly signed by the fixture key → `execute` exits 11
   `pubkey_vs_export` with zero connector calls; the same with `S/approver_fingerprint.json` absent →
   exit 11; with the export updated to the fixture key → `execute` proceeds.
   **`verify`'s exact order (DECIDED HERE; every refusal code depends on it):** (1) load the
   request file `S/approval_requests/<slug>/<request_id>.json` for the action's `request_id` (absent
   → `request_missing`, exit 7); (2) load the decision record (absent → `approval_missing`); (3) the
   request's `status` (→ `request_denied` / `request_superseded` / `request_expired`, except at
   `complete`, step 5); (4) `decision == "approved"` (→ `decision_not_approved`; a denial record has
   no `signature_b64`, so this runs before 3a, which would otherwise report `malformed_record`); (5)
   `verify_signature` (trust result, 3a, key lookup, retired-key rule, step 4); (6) the export
   binding above and the §5.3 cdhash check (money stages); (7) the 3b bindings **in the order
   listed below** (`field_mismatch`, `digest_mismatch`, `display_mismatch`, `value_mismatch`,
   `unit_mismatch`, `null_not_allowed`, then the enable binding); (8) step 5 (expiry, then the nonce
   state tests). The first failing test's reason is the one raised.
   **3b (in `approvals_verify.verify` only):** `decision == "approved"`; the request's `status` ∈
   {`pending`, `approved`} (`approved` is set by exactly one writer at exactly one moment: act.py,
   inside the nonce-ledger lock, in the same critical section as a **success** `consume` line at
   `execute`, `run_holds`, API `revert` or `complete` — never at a quarantine consume, which leaves
   the status `pending`: the nonce is spent, so every later stage refuses `nonce_replay`, the
   request stays listed in the app's "approved, not yet executed" section as a greyed
   **quarantined** row with no Revoke button (§5.2) until `expires`, and any cancel marker for it
   changes nothing (§5.1 step 5 fourth bullet) because its nonce is consumed — so later stages see `approved` only after the nonce is spent and refuse by
   `nonce_replay`; this is the `pending → approved` transition 03_schemas.md §3.7 already allows A2
   to make; R63 asks 02 §2.4 to name it at those four consume sites) (a request **denied in
   GTMApprover** (an app denial record, `decided_via: "app"`, ingested at `authorize`/`run-holds`),
   **revoked or cancelled through the operator's cancel channels** (§5.1 step 5), or
   `superseded`/`expired` → `request_denied` / `request_superseded` / `request_expired`,
   EXIT_APPROVAL, at every stage except the `complete` rule of step 5; a card answer never changes
   the status, §5.1 step 5); every payload value equals the action/request (`company` =
   the action's company and the request's directory slug, `card_id == request_id`, `action_id`,
   `system`, `account_id`); `after_digest == action.after_digest`; `display_sha256 ==
   sha256(canon(build_display(ctx, action)))`, so what the operator saw is bound to the action
   (R10); `new_absolute_value == action.after.new_absolute_value` **and** `unit ==
   action.after.unit` (03_schemas.md §3.7 added `unit` to stop a daily/monthly confusion; the unit
   is bound directly, never only through the display). **`build_display` never reads a payload:**
   its `new_absolute_value`, `unit` and every other value come from the action (`after`, `before`,
   the matched row, the pack), so the `display_sha256` comparison is an independent recomputation,
   not a circular one (R44 asks 03 §3.7 to change the `new_absolute_value`, `unit` row's source from
   "the payload values" to `action.after`). Refusal reasons (all EXIT_APPROVAL):
   `decision_not_approved`, `request_denied`, `request_superseded`, `request_expired`,
   `field_mismatch` (company/card_id/action_id/system/account_id), `digest_mismatch`,
   `display_mismatch`, `value_mismatch`, `unit_mismatch`, `null_not_allowed`.
   **Null rule:** `new_absolute_value` and `unit` are both `null` only for (i) an amount-less
   `_nomatch` action, (ii) a money row with `amount_required: false`, or (iii) an action that is
   class `money` **only** because `spend_delta_monthly ≠ 0` on a `money: false` row (03_schemas.md
   §3.4.3; check 10 forbids amount keys there). Case (iii) is signed over `after_digest`, and its
   display shows `spend_delta_monthly` (R18). Any other null is refused (EXIT_APPROVAL). Expiry is
   per stage (step 5).
   **Operator-executed actions (DECIDED HERE; plan §20.8 "the operator makes it in the platform UI
   … logged with `record-external --kind owner_executed`").** Some signed `$` actions are never made
   by an agent: every `_nomatch` action and every money row with no connector `write_rows` entry
   and no runbook `writes[<row>]` entry (06_connectors.md §6.2 "Never agent-executable",
   `not_agent_executable`; 03_schemas.md §3.4 purchase rows), and every enable-bound row on a tier
   system with no `access: api` account serving `committed_ceiling` (06 §6.2 "Agent-executable
   enables", 03_schemas.md §3.6 `enable_not_agent_executable` — e.g. OtherCompanyB's browser-only Meta
   campaign enables). **Stops are never in the enable group — fixed to the row's declared resulting
   status, never to verb tokens (DECIDED (wave1c); corrected (wave1d), finding 05-MAJOR).** The
   wave1c text keyed this exemption off `display.change_kind`, itself derived by `tiers.change_kind`
   from a **verb-token** scan of the action's own name (§5.1 step 3's stop-token set {`pause`,
   `paused`, `stop`, `end`, `disable`, `remove`, `delete`, `archive`, `off`}, tokenized on `_`). That
   is unsound for exemption purposes: a verb like `remove_end_date`, `delete_spend_limit`,
   `disable_budget_cap` or `remove_pause_until` tokenizes to a set containing `remove`/`delete`/
   `disable` and so would be classified `"remove"` or `"pause"` by the same token scan — **while its
   actual effect is to resume or uncap spend**, the opposite of a stop. Exempting it from the enable
   binding/G-A rule 9d on that basis would let a spend-resuming action through the write path with no
   fresh ceiling read-back, exactly the hole the enable binding exists to close. **Fix: the exemption
   is never derived from `display.change_kind`/verb tokens at all — it is read from one explicit,
   authored schema field on the matched tier row (03_schemas.md §3.2/§3.4, siblings of
   `commits_on_enable`): `resulting_status: "paused" | "removed" | "active" | "unbounded" |
   "unchanged"` (03 §3.4.1, landed wave1e; **required on every row with `money: true` or
   `commits_on_enable: true`**, the `_nomatch` pseudo-row excepted — absent is a schema-authoring
   defect refused at load `resulting_status_missing`, never defaulted to an exempt status).** An
   action is in the "stop" group **iff** its matched row's `resulting_status` is `"paused"` or
   `"removed"` — never by the action's own name, and never by verb tokens; `display.change_kind` is
   withdrawn (wave1e), and the dialog text (§5.1 step 3) and §5.8's requested state read the same
   field through `display.resulting_status`. **`commits_on_enable: true` rows
   are never exempt, unconditionally, regardless of what their `resulting_status` or verb tokens say
   (DECIDED (wave1d)):** `commits_on_enable` and `resulting_status` are independent flags on the same
   row, so a row can never claim "this both commits a ceiling at enable AND is exempt as a stop" — a
   row's exemption is `row.resulting_status in {"paused", "removed"} and not
   row.get("commits_on_enable", False)`; a row that somehow sets both is a schema-authoring defect,
   refused at load (`commits_on_enable_and_resulting_status_conflict`), never silently resolved
   either way. `remove_end_date`/`delete_spend_limit`/`disable_budget_cap`/`remove_pause_until`-shaped
   rows are therefore authored with `resulting_status: "active"` or `"unbounded"` (they resume
   spend) and `commits_on_enable: true` where the resumed spend has a configured ceiling to bind —
   so they fall through to the ordinary enable-binding/G-A rule 9d path like any other
   ceiling-committing action, never the stop exemption. An action whose matched row has
   `resulting_status ∈ {"paused", "removed"}` commits no ceiling, so FID-03's API read-back has
   nothing to bind and `owner_execution_reason` never returns `enable_not_agent_executable` for it; a
   signed stop (urgent or not) whose row has a connector `write_rows` or runbook `writes[<row>]`
   entry runs under an ordinary signed write ticket like any other `$` write (G-A rule 9d applies
   only to rows that are enable-bound **and** not exempt by `resulting_status`), and is
   `operator_executes` only through the `not_agent_executable`
   branch (a `_nomatch` stop, or a stop row with no write entry; R84 asks 03 §3.6 and 06 §6.2 to
   state the exclusion **by `resulting_status`, never by verb token or `display.change_kind`**).
   **Departure, stated:** plan §20.8 and §6.1 allow `owner_executed` only as
   the probe-p-failed fallback; making the operator execute these actions in **every** mode is §5.9
   entry **V6, UNRATIFIED, which blocks WP-A2**. For these the operator's signature is a decision
   **and** an instruction to himself, and he must be told so before he signs.
   **Test (A2, wave1d, RED when the exemption reads `display.change_kind`/verb tokens instead of
   `resulting_status`):** a tier row named `meta.remove_end_date` (tokenizes to include `remove`,
   so `tiers.change_kind` would classify it `"remove"`) authored with `resulting_status: "active"`,
   `commits_on_enable: true` and a configured ceiling → the action is **not** exempt: it is
   enable-bound, `verify` applies the enable binding (`value_mismatch`/`unit_mismatch` on a stale
   `before.value`), `ticket --write` mint performs the `budget_readback` re-check, and G-A rule 9d
   denies the mutating call on a stale/absent read-back — none of the stop-group behavior (no
   `owner_execution_reason` short-circuit, no skip of `budget_readback`) fires for it; the same test
   with the row instead authored `resulting_status: "removed"`, `commits_on_enable: false` (a
   genuine stop, unrelated to the misleading name) **is** exempt, proving the field — not the name —
   decides.
   So `build_display` sets **`display.operator_executes`** (bool, always present on a `$` request) =
   `connector_dispatch.owner_execution_reason(actx, action) is not None`, the one predicate R78 asks
   06 to expose beside `api_executable_reason`: it returns `"not_agent_executable"` or
   `"enable_not_agent_executable"` exactly by the two 06 §6.2 rules above (the same facts `execute`
   and `ticket --write` refuse on), and `None` otherwise — never a transient code (`manifest_*`, a
   credential problem), which keeps its execution-time refusal, and `None` for `gtm_ai` (internal,
   §5.5 "AI-spend cap"). It sits inside `display`, so `display_sha256` binds it: the operator
   cannot be shown "agents will execute" for an action they cannot, and should a committed pack,
   manifest or runbook change flip the predicate between signing and execution, `verify` refuses
   `display_mismatch` (fail closed; the session asks for a new request). When it is true: the
   request's notice, mirrored card, NSAlert body and reason string carry the "You make this change
   yourself after approving —" text of §5.1 steps 1 and 3; `execute`/`ticket --write` still refuse
   `not_agent_executable`/`enable_not_agent_executable`; and the daily run's owner-executed step
   (§5.8 "Closing trigger", D6b) closes the action **in every mode**, not only probe-p-failed, once
   the request is signed and a verify-read shows the requested state (§5.8 "Requested state"),
   through `act.py record-external --kind owner_executed` (02_act.md §2.11). **Reminder before
   expiry:** when a signed, `operator_executes` request is still `pending` (not closed) and
   `expires − now ≤ 24 h`, the D6b query (`act.py queue --kind approval --owner-executable`,
   in-process) writes one notice: kind `money_card`, severity `warn`, `push: true`, title exactly
   `"You approved <request_id> but the change is not made yet — it expires <expires>"`, body exactly
   `"Make the change in <system> (account <account_id>) before <expires>, or it lapses and a new
   request is needed. The daily run closes it once the change is visible."` (regulated pack: the
   same text — ids, system, account and a timestamp only), `dedupe_key =
   "owner_exec_due:<request_id>"`, `created_by: "act"` (R75 asks 02 for the query's write, R79 asks
   07 to reserve the prefix and to run D6b in every mode for these rows). A2/C tests (each RED when
   its rule is reverted): a signed `urgency: urgent` pause on a browser-only `L` system whose
   runbook has a `writes[<pause row>]` entry → `display.operator_executes: false` and `ticket
   --write` mints with no `budget_readback` (RED when stops fall under `enable_not_agent_executable`);
   with a HEAD `approver_probe_p.json` saying `"probe_p": "pass"` and a
   committed pem, a **signed browser-only `meta.campaign_enable`** (no API `committed_ceiling`
   account) → `display.operator_executes: true`, `ticket --write` exits 3
   `enable_not_agent_executable`, and D6b with a verify-read showing `status: "enabled"` at the
   signed ceiling closes it `completed`, `executed_by: "owner"`, request `superseded`; a **signed
   `_nomatch`** action in the same mode with a verify-read whose digest matches closes the same way;
   the same two **unsigned** with matching verify-reads are **not** closed (normal mode closes only
   signed requests); a signed one 23 h before `expires` gets exactly one open
   `owner_exec_due:<request_id>` notice, and none at 25 h; the C dialog test of §5.1 step 3 (the
   reason string starts `You make this change yourself after approving —`); and an agent-executable
   API budget edit has `operator_executes: false` and D6b never lists it.
   **Enable binding (FID-03).** **Scope = the one 03_schemas.md §3.2 predicate, never restated
   here:** an action is enable-bound iff `tiers.is_enable_action(ctx, action, row)` (A1; 03 §3.2
   "Enable actions" owns its enable tokens, the budget-object test by most-specific key, and the
   status-key guard; requests/03_schemas.md R56). 3b calls that function; this file lists no verb or
   token. **An enable-bound action must carry an amount:** an amount-less one is refused at
   `propose`/`authorize` (`enable_amount_required`, exit 3; R9, 03 §3.2), and should one ever reach
   `verify`, 3b refuses it `null_not_allowed`. 3b requires `new_absolute_value ==
   action.before.value.current_absolute_value` (else `value_mismatch`) **and** `unit ==
   action.before.value.unit` (else `unit_mismatch`).
   **Outside the predicate, 03 §3.2 decides the routing (adopted here; the earlier "withdrawn"
   reading of `enable_no_budget_object` is retracted, R76 supersedes R68):** a `_nomatch` action
   carrying an enable token whose most specific key is a known within-ceiling child is refused at
   `propose` exit 3 `enable_no_budget_object` (no event) — plan §20.13's autonomous child resume
   goes through the committed auto rows `google_ads.{ad,ad_group,keyword}_enable` and
   `meta.ad_enable` (03 §3.4.4), never through `_nomatch`; a `_nomatch` on a budget object that
   fails 03's status guard is refused `paid_object_use_money_row`/`status_change_use_money_row`;
   every other non-budget `_nomatch` enable (empty `target_ids`, a paid add-on, a lead-marketplace
   category on an `L` system, an unknown paid feature) takes the ordinary `_nomatch` `$` path, or
   with no amount null rule case (i), and is `operator_executes` (above). Table rows whose verb is
   an enable but that commit no configured ceiling (`google_ads.auto_apply_enable`,
   `amount_required: false`; `paid_api.usage_enable`, `current_value: zero`) follow their own flags
   and the null rule. The enable tests are 03 §3.2's (its P2 A1 list, which goes RED when the
   predicate is reverted to a verb list); this file adds only the A2 `verify` tests below.
   **Freshness of the bound value (the mechanical binding is the API read-back; 03_schemas.md
   §3.2/§3.6, 06_connectors.md §6.2, 04_hooks.md §4.1 rule 9d).** At `authorize` the signed value
   comes from a fresh platform read (connector op `committed_ceiling`) for an API system, or, for a
   browser system, from the `committed_ceiling` snapshot at `before.evidence_ref` (recorded by
   `act.py snapshot` in the same run, ≤ 24 h old, 02_act.md §2.6 rule 5a) — so approve-time equality
   is only as fresh as that read. The money is committed at execution, and **execution is bound by
   an API read, never by a snapshot or by a worker's own report**:
   - **API path.** At `execute` act.py passes the **verified payload's** `new_absolute_value` and
     `unit` as `connector_dispatch.execute(..., approval=…)`, which becomes `ctx.approved`
     (06_connectors.md §6.2); the connector's before re-check re-reads the object's configured
     ceiling immediately before the enable and fails `before_mismatch`, with no platform write, on
     any difference.
   - **Browser path.** `ticket --write` (stage `mint`), **after** `verify(stage="mint")` succeeds
     and **before** any reservation, reads the object's configured ceiling through the connector
     read op `committed_ceiling` **by API** and copies it onto the ticket as `budget_readback:
     {"value", "unit", "read_at", "via": "api", "target_ref"}` beside `signed_amount` (03_schemas.md
     §3.6). Mint refuses exit 3 **`enable_budget_mismatch`** — no ticket, no reservation, nothing
     written — when the read value is not `Decimal`-equal to the signed `new_absolute_value` or its
     unit differs; and exit 3 **`enable_not_agent_executable`** when the tier system has no API
     `committed_ceiling` read at all (such an action is `operator_executes`, above: the operator
     makes the change and D6b closes it — §5.9 V6, UNRATIFIED; never for a stop, above). At the click, **G-A rule 9d** denies every mutating call
     on the enable-bound ticket whose read-back is absent, not `via: "api"`, outside
     `[created_at − 5 min, created_at]`, or unequal to `signed_amount`/unit (04_hooks.md §4.1,
     requests/04_hooks.md R33). The runbook's mandatory ceiling before-check (06_connectors.md
     §6.4) is the **second** check, performed and reported by gtm-operator — never the only one.
   P2 falsification tests (A2 with L's fake-HTTP testkit, each passing once its check is reverted):
   a paused campaign configured at `1000.00` USD/day with a signed enable of `45.00` is refused at
   `execute` with `before_mismatch` and zero mutating calls; **at stage `mint`, an API read-back of
   `1000.00` USD/day for a signed browser enable of `45.00` → exit 3 `enable_budget_mismatch`, no
   file under `S/tickets/<slug>/`, and no `reserve` line for the nonce** (RED when mint skips the
   read-back); the same enable on a system with no API account → exit 3
   `enable_not_agent_executable`, no ticket, no reservation; an enable action whose
   `before.value.current_absolute_value` ≠ its signed value is refused by `verify` (exit 7
   `value_mismatch`); the same test goes RED when the row flag is read under any other name than
   `commits_on_enable` (e.g. `row.get("ceiling_enable")`); a `google_ads.auto_apply_enable` action
   (no amount) and a `paid_api.usage_enable` action reach a decision without any ceiling read (RED
   when 3b applies the binding outside `tiers.is_enable_action`). App test (C): a
   `commits_on_enable` request whose `display.current_value` differs from the payload value is shown
   without Approve.
   **Generic 3b and end-to-end tests (A2, plan §20.8's P2 list; each RED when its check is
   reverted):** (1) an approval record written with Python `open()` into `S/approvals/<slug>/`,
   carrying the request's real `payload_b64` and a random 64-byte/DER-shaped `signature_b64` →
   `execute` exits 7 `bad_signature`; (2) `execute` of an approved `$` action succeeds, then a second
   `execute` (and a `run-holds` pass) on the same approval → exit 7 `nonce_replay`, zero connector
   calls; (3) a budget-edit (non-enable) action with `after.new_absolute_value` `"45.00"` and a
   validly signed fixture payload carrying `"1000.00"` (every other key matching) → exit 7
   (`value_mismatch`); (4) a payload signed with
   `unit: "USD/month"` for an action whose `after.unit` is `"USD/day"` → exit 7 (`unit_mismatch`);
   (5) an enable action whose `before.value.unit` differs from the payload `unit` → exit 7
   (`unit_mismatch`).
4. **Signature, by the PEM key type.** EC P-256 → `ecdsa-p256-sha256` (DER X9.62 signature over
   SHA-256 of the bytes = Swift `SecKeyCreateSignature(.ecdsaSignatureMessageX962SHA256)`); Ed25519 →
   `ed25519` (raw 64-byte signature = CryptoKit `Curve25519.Signing`). `alg` in the record must match
   the key type (`alg_mismatch`). **Backends (DECIDED HERE; no third-party package):**
   - ECDSA P-256 → always **`/usr/bin/openssl`** (SIP-protected; LibreSSL 3.3.6 on this Mac), run with
     the scrubbed environment of step 2 plus no `OPENSSL_*` variable: `openssl dgst -sha256 -verify
     <pem> -signature <sig.der> <data>` must print `Verified OK` and exit 0.
   - Ed25519 → `tools/gtm/ed25519_verify.py`, a stdlib-only RFC 8032 §5.1.7 verifier (a TRUST_PATH,
     imported only after the trust check), because LibreSSL 3.3.6 cannot verify Ed25519. It is
     tested against the RFC 8032 §7.1 vectors and against a CryptoKit signature produced by C's test
     build.
   - `cryptography` is never imported: a user-installable package could fake success (R12). A
     missing `/usr/bin/openssl` → `verifier_unavailable` (exit 7), never a pass.
   - **This step is the one backend definition for every approver-key signature**, `$` records and
     the §5.3 trust-edit marker alike. 04_hooks.md §4.3 G-W does not verify the marker in-process
     (its `cryptography` wording and `R`/unscrubbed `git show` reading are superseded): it runs
     `gtm_env.TRUSTED_PYTHON -I -S -B -X pycache_prefix=<fresh P> <T>/tools/gtm/approval_sig.py
     --verify-trust-edit <target>` and admits the write only on exit 0 (R38, extending R27).
   - Tests (A2): a stub `cryptography` package on `sys.path` that returns success leaves a forged
     record refused; `verify_raw` rejects a one-bit-flipped signature for both algorithms.
5. **Stages, nonce ops and expiry (03_schemas.md §3.9).** A reserve attempted while another holder
   holds the nonce refuses `nonce_held` (exit 7; not `nonce_reserved`, which is only the ticket field
   of 03_schemas.md §3.6; R34 asks 03 §3.9 to use `nonce_held`); any op after `consume` refuses
   `nonce_replay` (exit 7). Holders are the full ledger strings (`ticket:<ticket_id>`,
   `execute:<action_id>`, `run-holds:<action_id>`), passed as such to `reserve`/`consume`/`release`.

   | stage | caller | expiry check | nonce ops (holder) |
   |---|---|---|---|
   | `authorize` | `authorize` re-run on `awaiting_approval` | `expires > now` | none |
   | `mint` | `ticket --write` (browser) | `expires > now` **and** `expires − now ≥ MINT_MARGIN` (= `WRITE_TICKET_TTL` + 5 min = 35 min, header "Formats"; 03_schemas.md §3.6), else `raise ActError(EXIT_APPROVAL, "approval_expiring")` (exit 7; the approval is valid, only too near expiry; the operator re-approves a fresh request) with no ticket and no reservation | reserve (`ticket:<ticket_id>`). **This exit 7 is the settled one**; 02_act.md §2.4's `ticket --write` row, which says exit 3, is corrected by R72 |
   | `execute` | `execute` (API) | `expires > now` | reserve (`execute:<action_id>`); consume on success; on failure, **release or quarantine** (below) |
   | `run_holds` | `run-holds` executing a due held money action (API) | `expires > now` | reserve (`run-holds:<action_id>`); consume on success; on failure, release or quarantine (below) |
   | `revert` | `revert --child <id> --approval <request_id>` step 2 (money) | `expires > now` | API: as `execute` with holder `execute:<child id>`; browser: none (the child goes to `authorized` and takes the `mint`/`complete` path) |
   | `complete` | `complete` of a browser write | **no** `expires > now` test and **no** request-status test; instead the nonce must currently be reserved by the holder `"ticket:" + action.ticket_id` (the ticket id is read from the **action**, never from a caller argument; R72 asks 02 §2.4 `complete` to refuse a `--ticket` that differs from `action.ticket_id` before `verify`) and that reserve line's `ts < expires` (both parsed, header "Formats") (a `complete` refused by a pause is retried after the pause lifts, 02_act.md §2.4, possibly after `expires`; the platform write already happened) | consume (`ticket:<ticket_id>`); a `--failed` complete: release or quarantine (below) |

   **Deviation from plan §20.8 (stated; §5.9 Deviation register entry V3, unratified — blocks the
   start of WP-A2 implementation until ratified or conformed).** The plan requires the approval to be "unexpired" at
   `complete`. This contract replaces that with "the ticket's reserve line has `ts < expires`",
   because the platform write has already happened by `complete`, and refusing to record it after a
   pause-delayed retry would lose the record of committed money, not prevent it. For the same reason
   a request revoked by the operator's cancel while its ticket is in flight (§5.1 step 5) still `complete`s:
   the outcome is recorded (`completed` or `failed`) and the `revoked_late:<request_id>` urgent
   notice of §5.1 step 5 asks the operator whether to revert.

   **Release or quarantine (DECIDED HERE; plan §20.6 `$` list). Deviation from plan §20.8
   (stated; §5.9 Deviation register entry V4, unratified — blocks the start of WP-A2
   implementation until ratified or conformed):** the plan says "a failed/abandoned ticket releases the reservation"; this rule
   releases only a proven no-write or idempotent failure and quarantines the rest, because one
   signature must never authorize a second write after an unknown outcome. One signed approval must never
   authorize a second platform write after a first attempt whose side effect is unknown (a timeout
   after the write landed; gtm-operator clicking "Buy" and dying). So a failed or abandoned attempt
   **releases** the nonce (the same approval may be retried) only when it is proven to have made no
   platform write:
   - API (`execute`, `run_holds`, API `revert`): the connector result is `ok: false` with
     `side_effect: "none"` (06_connectors.md §6.2; R46 asks 06 to define that field, set only for a
     failure raised before the first mutating HTTP call or on a 4xx the platform documents as
     "nothing applied"). Any other failure — a timeout, a 5xx, a transport error, a missing or
     other `side_effect` — is ambiguous;
   - browser (`complete --failed`, reconcile of an abandoned/expired/stopped-past-grace ticket,
     03_schemas.md §3.6): the ticket's `mutating_calls_used == 0` (no mutating tool call was ever
     admitted by G-A). Otherwise ambiguous.
   An ambiguous outcome **releases** only when a repeat is idempotent: the payload carries a
   non-null `new_absolute_value` and the matched row's `current_value` is not `zero` (an absolute
   budget/cap set: setting 45.00 twice is 45.00). Every other ambiguous outcome — a `current_value:
   zero` row (purchase, subscription, paid trial, `paid_api.usage_enable`), an amount-less action
   (null case (i)–(iii), step 3b) — **quarantines** the nonce (`quarantine(ctx, action, holder,
   reason=…)`: a `consume` line plus `nonce_quarantined {request_id, reason}`), the action goes to
   `failed`, and act.py writes one notice (07_notices_schedules.md §7.1 record): slug = the
   request's company, kind `money_card`, severity `urgent`, `push: true`, title exactly `"Outcome
   unknown for <request_id> — check <system> (account <account_id>) before re-approving"`, body
   exactly `"The attempt to make <request_id> (<new_absolute_value> <unit>, or "no amount") on
   <system> failed after it may have reached the platform, so its approval is used up. Check
   <system>, account <account_id>: if the change did not land and you still want it, approve a new
   request; if it landed and you do not want it, run act.py revert."` (regulated pack: the same
   text — ids, amount, system and account only), `dedupe_key =
   "nonce_quarantined:<request_id>"` (R79 asks 07 to reserve the prefix), `created_by: "act"`. A2 tests (each RED when its rule is reverted to plain "release on failure"):
   an abandoned purchase-row ticket with `mutating_calls_used: 1` → the nonce is consumed and a
   second `ticket --write` on the same approval exits 7 `nonce_replay`; the same ticket with
   `mutating_calls_used: 0` → released, and a new ticket mints; an API `execute` of a `current_value:
   zero` row whose fake connector times out → quarantined; an API budget edit whose fake connector
   times out → released.

   The mint margin makes a normal `complete` land before `expires`; the `complete` rule keeps a
   pause-delayed one recordable. Tests (A2; the same thresholds as 03_schemas.md §3.6's test):
   mint at `expires − (MINT_MARGIN − 1 min)` → exit 7 `approval_expiring`, no ticket, no reserve
   line; mint at `expires − (MINT_MARGIN + 1 min)` → minted; that ticket stopped at its minute 30 and
   completed at its minute 45 (after `expires`) → `completed` (RED under an `expires > now` test at
   `complete`); a second reserve by another holder → `nonce_held`.

   **Revert under `DISABLED`/`PAUSE` (plan §20.8, applied as written; the earlier money-only
   "interpretation" is withdrawn).** Plan §20.8 says "`revert --approval <card id>` (§6.8) means 'a
   signed approval for that revert action'", with no money qualifier, and it points at the plan
   §6.8 pause row ("manual PAUSE/DISABLED: revert only with `--approval <card id>`"). Under
   `DISABLED`/`PAUSE` a revert is the one mutation still allowed, so text an agent can write (an
   answered card in the operator-input archive, which plan §20.8 says "is for humans only" and
   which round 10, plan §20.16 B1/B2, moved approvals away from) must never unlock it. So **every**
   `revert --child <id> --approval <id>` step 2 that runs while `R/schedules/DISABLED` exists or the
   company-wide manual `PAUSE` exists requires a **signed** approval (`PAUSE.budget`, `PAUSE.chain` and `PAUSE.trust` keep their
   own rows).
   **`PAUSE.<system>[@<brand>]` blocks revert, as plan §6.8 reads (conformed; DECIDED HERE).** Plan
   §6.8 has two rows here: `PAUSE.<system>` (breakers, and owner pauses carried in at P1 such as
   `PAUSE.website_remodeling` for owner pause A0022) blocks "that system's non-T0 actions and write
   tickets" and does **not** list revert as still allowed; only the "manual `PAUSE`/`DISABLED`" row
   allows revert with an approval. This contract applies the two rows as written: **every**
   `PAUSE.<system>[@<brand>]` that covers the child — a breaker (`created_by: "breaker"`), an owner
   or ruled pause, an `act`/`migration` pause, or an empty/hand-made file — **blocks** a revert of
   that system's child: `pauses.blocking` refuses `revert` step 1 and step 2 with exit 5 and
   nothing is consumed (a marker or approval is left in place). The operator repairs by lifting the
   pause first (its own route, 02_act.md §2.4 `resume`), then reverting. The earlier reading that
   let a breaker pause admit a signed revert (former R71 (a)) is **withdrawn**, so it is no longer a
   deviation (§5.9); should the planner want it, it needs a plan §6.8 amendment first, and R71 (a)
   stays open only as that ask. R71 (b) still asks 02 §2.4 / 03 §3.10 to state in the `revert` row
   and the pause-scope table that every `PAUSE.<system>[@<brand>]` blocks revert (the 03 §3.10
   stop-row exemption applies to stop actions, never to revert).
   - **money child** — unchanged: the signed approval of the request `revert` step 1 created for
     that child (02_act.md §2.4, I21), verified by `approvals_verify.verify(ctx, child,
     stage="revert")` (this section's stage table);
   - **non-money child** — the GTMApprover **operator marker** of 00_global_paths.md §1.4 with
     `command = "revert"`, `company = <slug>`, `target = <child action_id>` (an `act_<slug>_…` id,
     which already matches the §5.3 `<target>` grammar), created by the operator in his own
     terminal (`tools/gtm/operator_ok.sh revert <slug> <child action_id>` → `gtm_approve.sh
     operator-ok` → Touch ID/password, reason `"Allow ONE revert of <child> for <slug> within 15
     minutes"`). act.py looks for exactly `S/operator_ok/revert.<slug>.<child action_id>.json` and
     verifies and consumes it exactly as for `resume` (00 §1.4 "Validation" (1)–(5): `verify_raw`
     against HEAD's pem at `T`, canonical payload with the seven keys and `kind == "operator_ok"`,
     `command`/`company`/`target` equal to the invocation's, `now < expires ≤ now + 15 min`, a
     `consume` line with holder `operator-ok:revert:<child action_id>`, marker deleted before any
     state change). The marker is found by the child id, so in this form `--approval` carries the
     child id itself (any other value → exit 3 `revert_approval_mismatch`); no marker → exit 3
     `operator_ok_required`. A marker that fails any check is left in place and step 2 refuses
     as with no marker. After the marker passes, checks 1 and 5 re-run (never-class) exactly as on
     the card path. No HEAD pem → `approver_not_installed` (exit 11): before install a non-money
     revert under `DISABLED`/`PAUSE` is unavailable, and the operator lifts the pause (its own
     card route, 02_act.md §2.4 `resume`) or removes `DISABLED` himself first — **stated**: that is
     the price of not letting archive text act under a stop.
   Outside `DISABLED`/`PAUSE`, a non-money revert keeps its ordinary card path (`cards.require_approved(ctx,
   card_id, "revert <child action_id>")`, 02_act.md §2.4): that path is plan §20.6's normal
   non-money approval, not the §6.8 stop row. R52 asks 00 to add `"revert"` to
   `system_names.OPERATOR_OK_COMMANDS` (and so to the app's compiled copy, whose C test fails until
   it follows, §5.3), and R53 asks 02 §2.4 `revert` step 2 to use the marker instead of
   `cards.require_approved` for a non-money child under `DISABLED`/`PAUSE`, and step 1's
   `awaiting_card` notice under a stop to name the `operator_ok.sh revert` command instead of a
   card. A2 tests (each RED when its rule is reverted to the card path): under a company `PAUSE`, a
   non-money revert child in `awaiting_card` with an **archive card answered "Yes" under subject
   `revert <child>`** (forged: written by the test, as an agent could) → `revert --child <child>
   --approval <child>` exits 3 `operator_ok_required`, the child stays `awaiting_card`, nothing is
   executed; the same child with a valid signed `revert` marker for it → executes (API) or goes to
   `authorized` (browser), the marker is consumed and a replayed marker exits 3; a valid marker
   naming a different child → refused, left in place; with the pause lifted, the ordinary approved
   `revert <child>` card still works; with no HEAD pem under `PAUSE` → exit 11
   `approver_not_installed`; under an **owner-ruled** `ST/PAUSE.website_remodeling` (`ruling_ref:
   "A0022"`) a revert child of that system with a valid signed marker (non-money) or a valid signed
   approval (money) → exit 5, nothing executed, marker/approval left in place (RED when owner pauses
   are merged into the manual row); under a **breaker** `ST/PAUSE.gbp` (`created_by: "breaker"`,
   null `ruling_ref`/`lift_card`) the same valid marker, and a valid signed approval for a money
   child → also exit 5, nothing executed, left in place (RED under the withdrawn breaker reading);
   after that breaker pause is lifted the same marker → proceeds. (If the planner prefers the card
   path under a stop, that needs an explicit plan §20 amendment, not a contract reading.)
   **AI-spend cap (`gtm_ai.weekly_cap_edit`).** The row has no connector: `execute` verifies,
   reserves and consumes the nonce and records `completed`. The consumed signed approval **is** the
   new cap gate-gtm reads. **Ordering comes from signed bytes, never `signed_at`** (which sits
   outside the signature): among records that pass `verify_signature` and whose nonce is consumed,
   the effective cap for `(company, account_id)` is the latest by the payload's `expires`, then its
   `card_id` (both signed; `expires` = creation + 72 h, so this orders by creation), exactly as
   04_hooks.md §4.6 decides (it supersedes R13 (a)'s ledger-order rule and R21 (c); R45 asks
   03_schemas.md §3.7's `expires` bullet, which still says "whose `consume` line comes **last**",
   to cite this rule instead). A consumed cap is never un-done by a card answer (§5.1 step 5: a card
   answer decides nothing); the operator lowers it with a new signed request.
   **Supersession touches only unsigned requests (DECIDED HERE; plan §20.6/[122]: a budget
   decrease is the operator's).** When `create_request` makes a new `gtm_ai` request, it sets to
   `superseded` every older `gtm_ai` request for the same `(company, account_id)` whose `status` is
   `pending` **and** that has **no** record at `S/approvals/<slug>/<request_id>.json` (checked under
   the nonce-ledger lock, 03_schemas.md §3.9, so it cannot race the app's create-exclusive
   publication: a record published first keeps its request `pending`). A request the operator has
   already signed — including an urgent **ZERO CAP** — is never superseded by an agent-triggered
   `authorize`: it stays `pending`, executes (verify, reserve, consume) on the next `execute` or
   `run-holds` pass, and becomes effective. No correctness depends on supersession: the effective
   cap is already ordered by the signed payload's `expires` (then `card_id`), so the newest
   **consumed** signed request wins whatever the consume order, and an older signed cap consumed
   late can never override a newer one already consumed. The app re-reads `status` before signing
   (§5.1 step 3), so an unsigned request superseded while its alert is open is never signed.
   Tests (B2/A2, each RED when its rule is reverted): rewriting `signed_at` on an older consumed
   higher-cap record leaves the effective cap unchanged; **a signed, unconsumed `"0.00"` ZERO-CAP
   request followed by an agent-triggered `authorize` of a higher-cap request** → the zero-cap
   request stays `pending`, the next `execute` consumes it, and `ai_budget` reports `usd: "0.00"`
   (source `signed:<zero-cap id>`) until the higher request is itself signed and consumed, after
   which it (the later `expires`) is effective (RED when supersession ignores the approval record);
   an **unsigned** older `gtm_ai` request is set `superseded` by the newer `authorize` and the app
   no longer offers Approve for it.

### 5.6 Keys, rotation, export and the daily trust check

Preferred (probe p): Secure Enclave P-256, `SecAccessControlCreateWithFlags(…, .privateKeyUsage |
.userPresence)`, application tag `com.oversight.gtm.approver.signing`. Fallback (only under §5.3's
fallback rule): a CryptoKit Ed25519 private key stored as a generic-password item, service
`com.oversight.gtm.approver`, account `signing-key-ed25519`, in **exactly one** of the two stores
probe p measured (§5.3 "Fallback key store"): `dp_userpresence` — a data-protection keychain item
with `kSecAttrAccessControl` `.userPresence`, read with the evaluated
`kSecUseAuthenticationContext` (§5.1 step 3); or `legacy_acl` — a legacy login-keychain item whose
`SecAccess` trusted-application list is only the app, with no access control, presence enforced by
the app's own `LAContext` before each read (the stated residual of §5.3). The two are never combined
on one item. In either store the item's `kSecAttrGeneric` holds the raw 32-byte public key, the one
source of every fingerprint and export (§5.3 "Existence checks and public-key reads"). `--export-pubkey` writes PEM
SubjectPublicKeyInfo: P-256 = DER prefix `3059301306072a8648ce3d020106082a8648ce3d030107034200` +
65-byte uncompressed point; Ed25519 = DER prefix `302a300506032b6570032100` + 32-byte key.
Fingerprint = `"sha256:" + sha256(SPKI DER)` in lowercase hex. **Anchor file bytes:**
`tools/gtm/approver_fingerprint.txt` is exactly `sha256:<64 lowercase hex>\n` and
`tools/gtm/approver_cdhash.txt` exactly `cdhash:<40 lowercase hex>\n`. A reader validates the
**whole** content against `^sha256:[0-9a-f]{64}\n$` / `^cdhash:[0-9a-f]{40}\n$` (any other content
is a mismatch: `pubkey_vs_anchor` / `approver_vs_anchor` `anchor_malformed`), then compares the
fingerprint as the full `sha256:<hex>` string and the cdhash as the 40-hex part after `cdhash:`
(§5.3; the heartbeat and the cdhash read rule give bare hex).

**Install order (DECIDED HERE).**
(0) **Precondition — the verifier is preventive first.** The 04_hooks.md G-W and G-B rule c
denials for the live `tools/gtm/` subtree, the pre-check set included, are specified in 04
(`trust_root_path()`, "Which TRUST_PATHS are prevented" below). The pem is not committed (step 4)
until they are **confirmed by the P2 test** in the live installation: an agent `Write`, an agent
`Edit` and an agent Bash write (`echo x >> …`, `sed -i`, `cp …`) to each of
`tools/gtm/approval_sig.py` and `tools/gtm/gtm_env.py` is denied. Until that test passes `$` stays
refused (`key_not_installed`), because the verifier is otherwise editable without detection
(below). Recorded in 08_seats_wps.md Appendix B (R32).
(0b) **the probe record lands first:** `tools/gtm/approver_probe_p.json` (§5.3, the machine copy of
plan §17's probe-p record) is committed through the same reviewed landing path as step 4
(trust-architect reviewer-of-record, HIGH tier) **before** step 1, because `--generate-key` reads it
from HEAD whenever the fallback branch is taken; a missing or malformed file at that moment exits 7
`fallback_store_unmeasured` with no key (§5.3 "Fallback key store"). R74 asks 08 Appendix B to list
this step;
(1) the operator builds the app (`tools/gtm/approver/build.sh`, §5.3) and runs `--generate-key`;
(2) `--export-pubkey` (default `S/approver_pubkey.pem`, outside the tree);
(3) `--self-test`, then `/opt/homebrew/opt/python@3.13/bin/python3.13 <T>/tools/gtm/approval_sig.py
--self-test` (`TRUSTED_PYTHON` by full path, step 0), which verifies against
the **exported** pem while HEAD has none (reporting `installed: false`) so the key is proven before
it is committed;
(4) **the operator's part is only** the Touch ID/password prompts of steps 1–3 and his answer on the
approver's install card, which quotes the fingerprint `--fingerprint` printed and the cdhash
`build.sh` printed. **An agent session does the rest:** it copies `S/approver_pubkey.pem` to
`tools/gtm/approver_pubkey.pem`, writes `tools/gtm/approver_fingerprint.txt` and
`tools/gtm/approver_cdhash.txt` from the card's quoted values (never from `S`), and lands all three
in **one** commit through the ordinary reviewed landing path (prepared in a lane or worktree,
integrated as one patch; trust-architect reviewer-of-record, HIGH tier; the commit message names
the card id). The reviewer must confirm that the committed pem's fingerprint equals the card's
quoted fingerprint and that the cdhash equals the card's quoted cdhash; a mismatch is a blocker.
**Why no `--sign-trust-edit` marker here (stated):** a marker is verified against HEAD's committed
key (§5.5 step 4, `--verify-trust-edit`), and at install HEAD has none, so no marker could ever
verify; the operator's quoted values plus the reviewed commit are the install control;
(5) the operator removes `S/PAUSE.trust` if a check wrote one in between.
Between the landing's integration and its commit the tree holds untracked TRUST_PATHs, so act.py
refuses every command except the stdlib fallbacks (§5.5 step 0) with exit 11 for that window; do it while no `com.oversight.gtm.*` schedule is
loaded. Until HEAD holds the pem, every `$` action is refused (`key_not_installed`).

**Rotation and loss (DECIDED HERE).** Keys retire; they are never silently replaced.
`HEAD:tools/gtm/approver_pubkeys/` holds `<64 lowercase hex>.pem` (the fingerprint without its
`sha256:` prefix) for every retired key and `index.json` `{"sha256:<hex>": {"alg", "valid_from",
"valid_until"}}` (keys are the full fingerprint; times `%Y-%m-%dT%H:%M:%SZ`, from the commits'
cards, not from any record). A record signed by a **retired** key verifies only when its nonce has a
`consume` line in the ledger with `ts < valid_until` (supplied by the caller's `consume_ts`, §5.5
API). That keeps every consumed `gtm_ai` cap and completed action verifiable after rotation. An
unconsumed approval under a retired key is refused `key_retired`, and the operator re-approves under
the new key. Procedure (new Mac, Secure Enclave reset, probe-p fallback switching algorithms, or a
deliberate rotation):
1. commit the current pem into `approver_pubkeys/` with `valid_until` = now (reviewed, HIGH tier);
2. `--generate-key --rotate`, in the operator's own terminal, first passes one fresh presence
   check (§5.3 "`--rotate` requires presence"), then deletes the old private key if present (a lost
   key simply is not there) and creates the new one; agents can never run it (§5.3
   agent-invocation refusal, R57);
3. export, self-test, and land the new `approver_pubkey.pem`, `approver_fingerprint.txt` and (after
   any rebuild) `approver_cdhash.txt` exactly as in install step 4; the operator removes any
   `PAUSE.trust`.
`--generate-key` without `--rotate` refuses (exit 3) whenever any key exists. Tests: (C)
`--generate-key` twice exits 3 the second time; (A2/B2) after a fixture rotation, a consumed
old-key `gtm_ai` cap still verifies and is not `forged` (with `consume_ts` passed); the same record
verified with no `consume_ts` → `key_retired`; an unconsumed old-key approval is refused
`key_retired`; a record naming a fingerprint in neither place is `key_unknown`.

**Daily trust check (I4).** WP-K's daily prompt only **runs**
`/opt/homebrew/opt/python@3.13/bin/python3.13 <T>/tools/gtm/approval_sig.py --trust-check`
(`TRUSTED_PYTHON` by full path; R59) and reads its JSON; the agent writes nothing (the
step-0 re-exec is only a backstop).
`trust_check(R, now, *, settle_seconds=300)` (CLI `--settle-seconds N`; tests pass 0). Its own steps
are labelled **TC1–TC5**; "§5.5 steps 0–2" always means the verification steps of §5.5 (the trust
root), computed here by the **uncached** `_compute_trust` (API above), never by the 60 s
`trust_result` cache.
**First, before TC1 and before any write of any kind** (TC1's git warn notice, TC3's
`S/trust_tree_seen.json` and its `info` notice, TC5's pause and notice), `trust_check` calls
`gtm_env.refuse_real_state(R, None)` (00_global_paths.md §1.1 consequence 3: test mode never writes
real state); a refusal raises `gtm_env.RealStateRefused` before anything is written, and the CLI
maps it to exit 3 **`test_mode_real_state`** (00 §1.1: every CLI maps `RealStateRefused` to that
code; `root_mismatch` stays the separate `RootMismatch` case of the header). A2 test: `--trust-check`
in test mode with `R` = the fixture real root exits 3 and prints `test_mode_real_state` (RED when it
prints `root_mismatch`).
- **TC1.** Run §5.5 steps 0–2. This runs **before and regardless of** install state (plan §20.8:
  the daily run checks the tree against HEAD unconditionally), and its failures are entries in
  `mismatches[]` even when `installed` is false. **`trust_git_error`:** sleep `settle_seconds`,
  call `_between_runs` if given, then run §5.5 steps 0–2 once more (uncached); if it persists,
  write only the warn notice of §5.5 "Error mapping" (`write_trust_git_notice`, with the subcommand
  and exit status from `trust_git_detail`), return `ok: false` with that single entry,
  **`installed: false`, `alg: null`, `fingerprint: null`** (HEAD could not be read, so install state
  is unknown and reported as not installed), `notes: []`, exit 11, and **skip TC2–TC5** — no
  `PAUSE.trust`, no `write_trust_notice`, no TC3 change note.
- **TC2.** HEAD has no `tools/gtm/approver_pubkey.pem` → `installed: false`; the fingerprint and
  cdhash comparisons of TC3 are skipped (deliberately: there is nothing to compare, and every `$`
  is refused anyway).
- **TC3.** Else compute the HEAD key's fingerprint and compare it with:
  - `HEAD:tools/gtm/approver_fingerprint.txt` — **the anchor** (below). A difference, or the file
    missing while the pem is present, is mismatch `pubkey_vs_anchor`;
  - `S/approver_fingerprint.json.fingerprint` → mismatch `pubkey_vs_export`; the file missing (a
    fresh `S`, a restore) is a note `approver_export_missing`, not a mismatch;
  - `pubkey_fingerprint` in `R/schedules/heartbeats/com.oversight.gtm.approver.json` → mismatch
    `pubkey_vs_heartbeat`; a missing heartbeat is a note `approver_heartbeat_missing` (the
    approver may not be loaded yet), and one older than 15 min is a note `approver_heartbeat_stale`.
  and compare the hex part of `HEAD:tools/gtm/approver_cdhash.txt` (§5.3 anchor rule) with the
  installed binary's cdhash (§5.3 cdhash read rule) and with the heartbeat's `approver_cdhash` →
  mismatch `approver_vs_anchor` (§5.3 "Binary integrity"; a missing heartbeat skips only the
  `running:` half).
  Every fingerprint-class entry has the shape `{"kind": <kind>, "paths": ["<the differing value>"]}`
  (the fingerprint, or `installed:<hex>` / `running:<hex>` / `anchor_missing` /
  `anchor_malformed`), one entry per differing value, so `mismatches[]` has one element shape and
  `write_trust_notice(entries)` takes it unchanged.
  **Trust-code change note (detective control for the HEAD residual risk, below).** The check
  computes one digest of the TRUST_PATHS in HEAD and compares it with `S/trust_tree_seen.json`
  `{"tree": "<40 hex>", "head": "<commit>", "ts"}`. **`tree` (exact):** run the step-2 invocation
  `ls-tree -r -z --full-tree HEAD -- <TRUST_PATHS>`; split its stdout bytes on `b"\0"` and drop
  the final empty element; each record is the raw bytes `<mode> SP <type> SP <sha> TAB <path>`;
  keep the records whose `<path>` (the bytes after the first TAB, decoded UTF-8) passes
  `not _excluded(path)` (the pem is **kept**: a key change is a trust-code change); sort the kept
  records by their raw bytes; `tree = hashlib.sha1(b"\0".join(records) + b"\0").hexdigest()`
  (lowercase). A2 test: two fixture repos whose TRUST_PATHS differ only in one excluded file give
  the same `tree`, and one differing in `tier_table.json` gives a different one. When they differ it adds note `trust_code_changed:<old head>..<new head>`,
  writes an `info` notice through `write_notice(S, "runtime", "trust", "info", False, …)` (§5.5
  API; title "GTM trust code
  changed in HEAD", body = the one-line subjects of `git log --format=%h\ %s <old>..<new> --
  <TRUST_PATHS>`, dedupe `trust_code:<new tree sha>[:8]`) and rewrites the file atomically. A
  first run with no file only writes it.
- **TC4. Settle re-check (F-dev).** If TC1 found only `trust_paths_*` entries, sleep
  `settle_seconds`, call `_between_runs` if given, and run §5.5 steps 0–2 again **uncached**. Only
  entries present in both runs count (per kind, the intersection of the two `paths` lists), so a
  landing commit in progress does not become a global pause. After the second run, the cache is
  repopulated with its result. **A second run that returns `trust_git_error`** is handled exactly
  as TC1's git branch (warn notice, `ok: false` with that single entry, `installed: false`, exit
  11, TC5 skipped): a git fault during the settle never turns into, or hides, a pause decision.
- **TC5.** Any remaining mismatch (never `trust_git_error`, TC1) → the function **itself**:
  - writes `S/PAUSE.trust` create-exclusive with exactly this JSON (03_schemas.md §3.10):
    `{"reason": <comma-joined kind:path pairs, fingerprint kinds as kind:<value>, truncated at 1000
    chars with "…+<n more>">, "created_by": "act", "requested_via": null, "ruling_ref": null,
    "card_id": null, "lift_card": null, "run_id": null, "ts": <now>}`. `requested_via: null` is
    load-bearing: under 03_schemas.md §3.10 only a `requested_via: "self"` act pause is removable
    without the operator marker, so this one is operator-only. An existing `PAUSE.trust` is left
    untouched and never rewritten;
  - writes the trust notice (below) via `write_trust_notice(S, entries, created_by=
    "approvals_verify")`;
  - returns the six-key dict with `ok: false`. The CLI maps that to exit 11.
  A clean result returns the six-key dict with `ok: true`, `mismatches: []` and writes nothing
  except the TC3 change note (exit 0).
Tests (A2): each non-git mismatch kind writes the pause (with `requested_via: null`) and the
notice; a clean tree exits 0 and writes nothing; an untracked file under `tools/gtm/` with **no**
pem in HEAD still reports `trust_paths_untracked`; **settle** — `trust_check(..., settle_seconds=0,
_between_runs=<delete the untracked fixture file>)` on a tree with one untracked `tools/gtm/x.py`
writes no pause and no notice and returns `ok: true` (RED when TC4 reads the 60 s cache: the
cached first result would still show the file), and the same with `_between_runs=None` writes
both; two untracked files give exactly one `trust_paths_untracked` entry with both paths (RED
under one entry per path); the daily check run against a test-mode fixture `T` that is not a git
repository (so `/usr/bin/git` fails; no test hook replaces the git binary, §5.5 step 2) → exit
11, a `trust_git:<date>` warn notice, **no** `PAUSE.trust` (RED when TC1's git branch is removed);
in test mode with `R` = the real root, `trust_check` is refused by `refuse_real_state` **before
TC1**, on both a clean and a mismatching fixture (the mismatching one's untracked file named
`tools/gtm/x_<m>.py`), judged by the header's **test-footprint oracle** plus an in-process write
spy: the test wraps `gtm_env`'s atomic writer and `os.open`/`os.mkdir`/`os.replace` for the call
and requires zero calls whose path is under the real root, and no file under the real
`S/notices/runtime/` carries `m` (RED when the call stays inside TC5: TC3 would already have
written the change note). It compares no mtime of `S/trust_tree_seen.json` or `S/PAUSE.trust`,
which a loaded real `com.oversight.gtm.*` daily job may write during the run.

**Anchor (deviation from plan §20.8, stated; §5.9 Deviation register entry V5, unratified — blocks the start of WP-A2 implementation until ratified or conformed).** The plan compares the fingerprint with "the value
recorded on the approver's install card". This contract uses `tools/gtm/approver_fingerprint.txt`
in HEAD, which holds that value, committed in the same reviewed commit as the pem, with the card id
in the commit message. It does not parse the card archive at check time, because the archive
parser is gtmlib code, which must not load before the trust check (step 0).
**What the HEAD trust root does and does not guarantee (stated plainly).** `S/approver_fingerprint.json`
and the heartbeat are written by the app into `S`; the anchors are in HEAD. But "in HEAD" is not
"reviewed": under the runtime contract local commits need no permission, gate 3b fails open on
tooling errors, the review tier is advisory (runtime CLAUDE.md §10), and 04's rule c never judges
git subcommands. A session that edits `tier_table.json`, `gtm_result.py` or an anchor, records a
review and commits leaves a tree equal to HEAD that passes every check here. The controls against
that are: (i) R33 asks 04 to have G-B deny `git commit`, `git apply`, `git am`, `git merge`, `git
cherry-pick` and `git revert` whose pathspec or patch touches a TRUST_PATH from any GTM session or
GTM seat (`CLAUDE_GTM_COMPANY` set or a GTM `agent_type`), so the agents that act on money never
change the code that judges them; (ii) the TC3 change note puts every commit that changes trust
code in front of the operator the next day; (iii) the fingerprint and cdhash anchors are also
compared with values the app writes, so an anchor-only commit is still a mismatch; (iv) **at every
money stage** (`mint`, `execute`, `run_holds`, `revert`), not only daily, the HEAD current key's
fingerprint must equal `S/approver_fingerprint.json` — written only by the app's `--export-pubkey`
and closed to agents (§5.5 step 3a "Export binding", `pubkey_vs_export`, exit 11) — and the
installed binary's cdhash must equal the HEAD anchor (§5.3). So a commit that swaps the pem **and**
the fingerprint anchor for a self-generated key signs nothing that verifies: the export file still
names the operator's key, and the cdhash anchor still names his build. A non-GTM development session
that commits a malicious change to other trust code (the tier table, `gtm_result.py`) is **not**
prevented; it is detected by (ii) only. That is the residual risk.

**Trust notice (one formula, owned here; 02_act.md §2.3 cites it, R11).** `write_trust_notice`
first calls `gtm_env.refuse_real_state(R, None)`, then writes slug `runtime`, kind `trust`,
severity `urgent`, `push: true`, `title = "GTM trust root: <n> mismatch(es) — $ refused"`, a body
that lists every entry as `kind: path` (F-dev: the operator can tell in-progress development from
tampering) **and always ends with the line "While this lasts, verify, read-run and non-money
reverts are refused for every company; inbox lead capture continues."** (§5.5 step 0 deviation:
only the stdlib fallbacks, `ticket --read` among them, run while the tree differs from HEAD), and `dedupe_key = "trust:" + sha256(canon(sorted entries))[:8]`,
where each entry's `paths` is sorted. It is written through `write_urgent_notice(S, "runtime",
"trust", title, body, dedupe_key, created_by=…)` (§5.5 API). So a new offending path set opens a new notice, and a repeat of the same set is
deduplicated. `created_by` is `"act"` (dispatch) or `"approvals_verify"` (daily check) — both in
07_notices_schedules.md §7.1 `NOTICE_CREATED_BY`, which also names `approvals_verify` for this
writer. It is never called for `trust_git_error` (§5.5 "Error mapping").

**Who writes `PAUSE.trust` (plan §20.8 split; DECIDED HERE).** A dispatch-time failure refuses
(exit 11) and writes the trust notice (or, for `trust_git_error`, the warn notice), but **never**
`PAUSE.trust`: the refusal already stops every `$` for that process. Only the daily `trust_check`,
after its settle re-check, writes the global, operator-only `PAUSE.trust`, and never for
`trust_git_error` (R11 amends 02_act.md §2.3/§2.9 to match; R40 adds the git-error exclusion).

**Which TRUST_PATHS are prevented and which are detect-after.** 04_hooks.md has landed the
prevention this file relies on: `gtm_hooklib.trust_root_path()` (04 §4 API) is the one predicate
for G-W's `trust-root` rule (04 §4.3 "Trust roots") and for G-B rule c (04 §4.2), and it covers the
**whole live `R/tools/gtm/` subtree** except `tests/`, `connectors/*/tests/`, `contracts/` and
top-level `*.md`, plus `R/telemetry/pricing.json` — the pre-check set (`approval_sig.py`,
`gtm_env.py`, step 0) included (R15 (a)/R28). Every tool edit there additionally needs a
GTMApprover-signed single-use trust-edit marker (04 §4.3; §5.3 `--sign-trust-edit`). Worktree and
lane copies are not under the live subtree and stay writable, which matches the development
protocol below. **What stays detect-after (stated):** rule c is a parser over shell text, so
interpreter-built writes (`python3 -c` with a string-built path, `node -e`, …) and git subcommands
that write the tree (`git apply`, `git am`) are not judged by it (04 §4.2 rule c "Known shell-write
reach"); for every TRUST_PATH except the pre-check set those are caught after the fact by steps 1–2.
For the pre-check set they cannot be (the check runs **as** that code), so the listed unparsed
shell forms are the residual for exactly those two files. **Install step (0) is the activation
gate:** no pem is committed, and so no `$` can execute, until the P2 test of install step (0)
confirms that an agent `Write`, `Edit` and Bash write (`echo x >> …`, `sed -i`, `cp …`) to each of
`approval_sig.py` and `gtm_env.py` is denied in the live tree. The signature is the control, and it
is only the control while the verifier is intact.

**Development protocol (F-dev; stated because the check is global).** Any uncommitted or untracked
file under `TRUST_PATHS` in the live `~/.claude` tree (Wave-3 work on `gtmlib` or a connector, a new
module, a non-GTM edit to `telemetry/pricing.json`; files under the excluded directories of §5.5
step 2 do not count) has these effects:
- every act.py command refuses with exit 11 at dispatch (step 0), read-policy commands included,
  except the stdlib fallbacks of 02_act.md §2.3 (`lead-append`, `ingest-findings`, `pause`,
  `cancel`, and `ticket --read` / `ticket --close` of a read ticket; §5.5 step 0, R67), plus a trust
  notice (02_act.md §2.3); so `read-run`, `verify` and non-money `revert` stop for every company
  (the stated, not-yet-ratified residual of §5.5 step 0);
- **inbox lead capture continues**: the read-ticket fallback mints from HEAD's runbooks, the
  lead-capture analyst allowance reads the inboxes, and leads spool through `lead-append`; only a
  fallback refusal (git error, missing HEAD runbook) writes the per-company urgent
  `lead_capture_stopped` task notice (§5.5 step 0);
- gate-gtm puts every company in forged budget state (04_hooks.md §4.6); the lead-capture analyst
  allowance is still admitted, and with the fallback read ticket it can read (R54's ask to 04 §4.6
  is amended by R67 accordingly);
- if the difference is still there at the daily check's two runs, the global `S/PAUSE.trust` (all
  `$` refused for every company, operator-only removal).
That is intended behaviour, not a false alarm. So **GTM tool development happens in a lane or
worktree (runtime CLAUDE.md §2, case (b)/(d)), never in the live `~/.claude` tree while any
`com.oversight.gtm.*` schedule is loaded.** Landing (integrate-and-commit) into the live tree is
the one moment the tree differs from HEAD. The coordinator lands GTM changes as one reviewed commit
with the `run-holds`, inbox and daily schedules quiet: either `R/schedules/DISABLED` is present for
the landing, or no `com.oversight.gtm.*` job is loaded. **This is mechanical, not prose:** R67 asks
08 to give the coordinator's landing procedure one command (the TRUST_PATH landing step) that
refuses, with nothing applied, unless `R/schedules/DISABLED` exists or `launchctl list` shows no
`com.oversight.gtm.*` label loaded, and that refuses to remove `DISABLED` itself (the operator
lifts it; 04_hooks.md G-B rule c already denies agent removal). The daily check's settle re-check
covers a landing that overlaps it. Before the schedules are loaded (all of Wave 2), refusals during
in-tree development are expected, and the operator removes any `S/PAUSE.trust` once the tree is
committed; the next trusted inbox run posts the catch-up task and resolves any
`lead_capture_stopped` notices itself (§5.5 step 0). `--verify-trust-edit` runs steps 0–2 first, so a trust-edit marker admits an edit only
on a clean tree: one marker-admitted edit, then its commit, before the next.

### 5.7 Self-test and heartbeat

`--self-test` (app) asks for Touch ID (one LAContext, §5.1 step 3), signs
`canon({"v":1,"self_test":true,"nonce":<32 hex>,"ts":<now>})`, writes `S/approver_selftest.json`
`{payload_b64, signature_b64, alg, key_fingerprint, signed_at}`. `approval_sig.py --self-test
[<file>]` (default `S/approver_selftest.json`) first runs steps 0–2 (a trust failure → exit 11,
§5.5 API), then refuses non-canonical bytes (`non_canonical`, before the key-set check; §5
header "Swift canonical JSON"), then requires exactly that payload shape (keys `{v, self_test, nonce, ts}`,
`self_test: true`) and verifies it with `verify_raw` — never `verify_signature`, whose 3a key set
rejects it by design. The key is HEAD's pem, or while HEAD has none the exported
`S/approver_pubkey.pem`, reporting `installed: false`. Output and exit codes are as in the §5.5 API.
**Manual checks recorded in plan §17:** (1) one Approve produces exactly one system prompt, and that
prompt shows the amount-bearing reason string; two Approves in quick succession produce two prompts
(reuse duration 0). (2) **Rebuilt-app check (plan §20.8 P2 list):** a copy of the app rebuilt from
the same source with one changed byte (a new cdhash) is started and asked to sign a fixture
request; record whether the OS refuses, shows a consent prompt, or signs after Touch ID, and
confirm that `trust_check` then reports `approver_vs_anchor` (`installed:` and, while it runs,
`running:`). The outcome is recorded with probe p in plan §17 and decides the residual-risk
sentence of §5.3.

Heartbeat every 5 min to `R/schedules/heartbeats/com.oversight.gtm.approver.json`:
`{"job": "com.oversight.gtm.approver", "started_at": <beat ts>, "finished_at": <beat ts>, "exit": 0,
"cadence": "every 5 min", "summary": "alive; <n> pending approvals; <m> holds; alg=<alg>",
"status": "ok", "pubkey_fingerprint": "sha256:<hex>", "approver_cdhash": "<40 hex>",
"app_started_at": <ts>}` (keys per `heartbeat_audit.REQUIRED_KEYS`; every time
`%Y-%m-%dT%H:%M:%SZ`, which `heartbeat_audit._UTC_TS_RE` accepts). `pubkey_fingerprint` comes only
from the §5.3 "Existence checks and public-key reads" (2) read — never the secret, never a presence
prompt, so a 5-minute beat never asks for Touch ID; its failure form is stated there. Plist
`schedules/com.oversight.gtm.approver.plist`: `KeepAlive` true, `LimitLoadToSessionType` `Aqua`,
`ProgramArguments` = the binary, absolute paths like the existing plists, never loaded by the WP
(the operator loads it via the batched sign-in card). The label needs its
`knowledge/oversight_install.md` §2 row (`expected_state` unloaded until that card is answered)
landed with the plist (the row 07_notices_schedules.md §7.1's signin card (b) already cites; plists
per §7.3), or `heartbeat_audit` reports it. That row's cadence cell is exactly `every 5 min` (the
heartbeat's own `cadence` value), which `heartbeat_audit.cadence_seconds` parses as 300 s through
its launchd `StartInterval` branch; a K/D test asserts `cadence_seconds(<the row's cell>) ==
300.0` (RED for any text it cannot classify, which would make staleness undeterminable).

### 5.8 Probe-p-failed mode (plan §20.8 fallback)

When probe p fails (plan §17 records FAIL; `tools/gtm/approver_probe_p.json` in HEAD says
`"probe_p": "fail"`, §5.3; R31 asks 00 to list the file), agents never execute `$`:
- The app is not built or loaded, and no pem is committed, so every `$` stage refuses
  `key_not_installed` and nothing can sign.
- `authorize` still writes the request and the notice, so the operator sees the same information.
  **Non-regulated packs:** the `money_card` notice body and the mirrored human card say, verbatim:
  "Signing is unavailable on this Mac (probe p failed). Make this change yourself in <system>,
  account <account_id>: <object_ref>, set <new_absolute_value> <unit> (or: the change in
  after_full). The daily run checks the platform and closes this request once the change is
  visible; no reply is needed. A reply on this card changes nothing. To cancel it, run
  gtm_cancel.sh <action_id> <slug> in your terminal, or let it expire at <expires>." (the
  cancellable set of §5.4 includes unsigned pending `$` requests). The card also carries the prepared change:
  values, click path, and snapshot paths. **Regulated packs (`regulated ∋ hipaa`):** the notice
  body and push text carry only `company_display`, `system`, the amount (or "no amount") and the
  `request_id` (§5.1 step 1); the object, values, click path and snapshot paths appear only on the
  home-surface card (the home's operator-input file), never in push text.
- **Closing trigger (named).** The daily run's owner-executed step (R48 asks 07 §7.5 for a D-list
  step after D6, "D6b"; R55 narrows it; R79 widens it as below) runs its query `act.py queue
  --company <slug> --kind approval --owner-executable` (02 R62, widened by R75), which returns, with
  every gate read from HEAD by the §5.5 step-2 git invocation, never the working tree:
  (a) **probe-p-failed mode** (HEAD's `tools/gtm/approver_probe_p.json` says `"probe_p": "fail"`
  and HEAD has no pem): every `awaiting_approval` action whose request is `pending` — nothing can
  be signed, and the notice asked the operator to make the change himself;
  (b) **every mode (DECIDED HERE; §5.5 step 3b "Operator-executed actions"; a departure from plan
  §20.8/§6.1 — §5.9 V6, UNRATIFIED, blocks WP-A2):** every
  `awaiting_approval` or `authorized` action whose request is `pending`, has
  `display.operator_executes: true` **and** has an approval record at
  `S/approvals/<slug>/<request_id>.json` that `approvals_verify.verify(stage="authorize")` accepts —
  the dialog told the operator he makes the change after approving, so a signed request of this
  kind must be closable once he has. An **unsigned** `operator_executes` request is not returned
  outside mode (a) (it lapses at `expires`, as the notice says to approve first).
  It returns **no** other row: in the ordinary Wave-2 pre-install period (HEAD has no pem but probe
  p passed or is not yet recorded) no notice asked the operator to make any change himself, so an
  auto-closure could only record a completion nobody performed. For the returned rows D6b runs one
  read ticket plus one gtm-analyst verify-read for those actions' systems, and for each action whose
  verification shows the **requested state** (below; 02_act.md §2.11 `owner_executed` rule) runs
  `act.py record-external --company <slug> --kind owner_executed --card <request_id> --action <id>
  --verify-from-agent <analyst id>` (the full 02_act.md §2.4 argument set; subject to 02 §2.11's
  checks). The action becomes `completed` with `executed_by: "owner"`; the request's `status`
  becomes `superseded` (the one field 03_schemas.md §3.7 allows to change), no other request field
  is written, and the signed nonce is left unconsumed (it can never be used: the request is no
  longer `pending`, so every stage refuses `request_superseded`); the reason lives only in the
  action's `completed` event. An unmatched action is left pending, the §5.5 step 3b
  `owner_exec_due:` reminder fires 24 h before `expires`, and the request expires as usual.
  **Requested state (DECIDED HERE; value equality alone is not enough).** For a budget or cap edit,
  the requested state is `observed.new_absolute_value` and `observed.unit` equal to the request's.
  For an **enable** action (`display.commits_on_enable: true`, FID-03), §5.5 3b forces the signed
  value to equal the paused object's configured ceiling, so the paused object already "shows the
  requested value" before anyone acts; the requested state is therefore `observed.status ==
  "enabled"` (the object's own serving status, as the verify-read reports it) **and**
  `observed.new_absolute_value`/`observed.unit` equal to the signed value (the committed ceiling).
  For a **pause/stop** action (`display.resulting_status` `"paused"` or `"removed"` — the matched
  row's authored field, 03_schemas.md §3.4.1, never verb tokens; DECIDED (wave1e), finding
  wave1d-B3; a pause is amount 0, plan §20.13, so the platform budget does not change), the
  requested state is `observed.status == display.resulting_status` (`"paused"` or `"removed"`),
  whatever the budget value. Any other `display.resulting_status` (`active`, `unbounded`,
  `unchanged`, absent) is **never** closed on an `observed.status` of `"paused"` or `"removed"`: it
  takes the enable rule above when `display.commits_on_enable` is true, else the budget/cap rule. R55 asks 02 §2.11 to compare `observed.status` for
  these two classes. A2 tests: an enable request whose paused campaign's configured budget equals
  the signed value, verify-read `{"status": "paused", "new_absolute_value": <that value>}` → not
  closed, request still `pending` (RED under value-only matching); the same with `"status":
  "enabled"` → closed; an owner-paused campaign (verify-read `"status": "paused"`, budget unchanged)
  closes its pause request (RED under value-only matching, which never matches a pause);
  **(wave1e, RED when the requested state is chosen from verb tokens or `change_kind`)** a request
  on a `meta.remove_end_date`-shaped row authored `resulting_status: "unbounded"`,
  `commits_on_enable: false`, whose verify-read is `{"status": "removed"}` with an unchanged value,
  is **not** closed (request still `pending`), and the same request closes only on a verify-read
  whose `new_absolute_value`/`unit` equal the signed ones; with a
  HEAD `approver_probe_p.json` saying `"probe_p": "pass"` and no pem, the query returns no row for
  an agent-executable request and a matching verify-read closes nothing (the `operator_executes`
  rows of (b) are tested in §5.5 step 3b).
- The §5.1 step-5 rule is unchanged: a card answer never approves and never denies; any answer
  re-shows the request in GTMApprover and writes the `approval_reshow:` info notice. Cancelling
  without deciding is `gtm_cancel.sh <action_id> <slug>` (§5.4) or letting the request expire.
Tests (A2): with no pem in HEAD, `ticket --write` and `execute` on a `$` action exit 11
`key_not_installed`, and (probe-p-failed fixture) `record-external --kind owner_executed --card
<request_id> --action <id> --verify-from-agent <aid>` with a verify-read showing the requested
state closes it (`completed`, request
`superseded`, no `superseded_by` key); a regulated-fixture request's notice body contains none of
`object_ref`, the values or the click path; a non-regulated probe-p-failed notice body contains
`gtm_cancel.sh <action_id> <slug>` and does not contain `Reply 'No'` (RED when the old card text
returns); and that fixture's card archived "No" leaves the request `pending` (§5.1 step 5).

### 5.9 Deviation register (every stated departure from the plan text; DECIDED HERE)

A deviation disclosed only inside this contract is not ratified. On 2026-09-28 a grep of
`~/.claude/plans/gtm_autonomous_department_plan.md` for each entry below (and for `quarantine`,
`R66`, `R67`, `R71`, `cdhash`, `approver_fingerprint`, `read-ticket fallback`, `trust drift`)
found **none** of them in the plan. So, binding:
- **Gate.** **WP-A2 implementation does not start** (08_seats_wps.md §9 WP table, Appendix B)
  until every entry marked UNRATIFIED below is either **ratified** — a plan §20.x amendment the
  planner lands, reviewed in a plan-review round, citing the entry id (and, for V2, an explicit
  operator-facing ratification) — or **conformed** (this file edited to the plan's letter and the
  entry marked CONFORMED). WP-C (the app) is not blocked by V2–V6 (none of them is app behaviour;
  under V6 the app only renders `display.operator_executes` as given);
  V1 binds the app's Revoke and the scripts, so WP-C conforms to whatever V1's ratification says.
- **Tracking.** Until then each UNRATIFIED entry is a tracked finding, never only an R-number
  (runtime CLAUDE.md §8). R81 (extended to V6 by R85) asks the coordinator to file **one** tracked
  issue with a checklist of V1–V6 (one pass, one root cause: "05 departs from plan text") before any WP-A2 work is
  dispatched, and to tick an entry only with the ratifying plan commit or the conforming 05 commit.

| id | where | plan text | this contract | why | status |
|---|---|---|---|---|---|
| V1 | §5.1 step 5 "Cancelling a `$` request" (former R66) | §20.7 "cancelling only prevents, so it may come from any channel" | for a `$` request the operator has **signed** (approval record, nonce unconsumed), only his two cancel channels (menu Revoke, `gtm_cancel.sh`) revoke it; `act.py cancel`, the fallback cancel, a card answer and an empty/hand-made marker never do (an unsigned request keeps §20.7 as written) | agent-writable text must not stop an operator-signed spend stop (§20.6) | UNRATIFIED |
| V2 | §5.5 step 0 "Deviation from plan §20.8 (stated, narrowed)" (former R67) | §20.8: a trust mismatch refuses every `$`; §6.8 keeps verify, read-run and revert running under every stop | every act.py command except the stdlib fallbacks (lead capture, findings, pause, the checked cancel, read tickets) is refused while any TRUST_PATH differs from HEAD — **verify, read-run and non-money revert stop for every company during every landing and every in-tree edit** | the modules those commands import are what the check could not vouch for, and they run with credentials | UNRATIFIED — needs the operator's explicit ratification. **Candidate narrowing to conform (for the planner's round, not adopted here):** on a step-0 failure act.py re-runs itself for `verify`/`revert` only from a fresh 0700 `git archive HEAD -- tools/gtm telemetry/pricing.json` extract under the temp root, re-verified blob-by-blob against HEAD after extraction and before exec, with the extract as code root; the TOCTOU window on an agent-writable temp dir is the open question that keeps it unadopted |
| V3 | §5.5 step 5 `complete` row | §20.8: the approval is "unexpired" at `complete` | the ticket's reserve line has `ts < expires` | refusing to record a platform write that already happened loses the record of committed money | UNRATIFIED |
| V4 | §5.5 step 5 "Release or quarantine" | §20.8: "a failed/abandoned ticket releases the reservation" | only a proven no-write or idempotent failure releases; the rest quarantines | one signature must never authorize a second write after an unknown outcome | UNRATIFIED |
| V5 | §5.6 "Anchor" | §20.8: compare the fingerprint with "the value recorded on the approver's install card" | compare with `tools/gtm/approver_fingerprint.txt` in HEAD (the card's value, committed with the card id) | the card archive parser is gtmlib code, which must not load before the trust check | UNRATIFIED |
| V6 | §5.5 step 3b "Operator-executed actions", "Freshness of the bound value" browser path (`enable_not_agent_executable`), §5.8 "Closing trigger" (b) (added wave1c, 2026-09-28) | §20.8 "Fallback if probe p fails: agents never execute `$` actions … the operator makes it in the platform UI … `record-external --kind owner_executed`"; §6.1 `owner_executed` "per §20.8's fallback"; §20.8 expects signed `$` browser actions to run through `ticket --write` | in **every** mode (probe p passing included) the operator executes, and D6b closes, every `_nomatch` action, every money row with no connector/runbook write entry, and every enable-bound action on a system with no API `committed_ceiling` read — e.g. every OtherCompanyB browser-only Meta campaign/ad-set enable and every `_nomatch` or write-entry-less action on an `L` lead-marketplace system; stops (`change_kind` pause/remove) are excluded from the enable group (§5.5 3b) | FID-03: an enable commits money at execution and only an API read-back binds it; a `_nomatch` or write-entry-less action has no reviewed flow an agent could follow | UNRATIFIED — **candidate conformance (for the planner's round, not adopted here):** browser-only enables run under a signed write ticket with the runbook's mandatory ceiling re-read immediately before the click plus a G-A-checked browser read-back (FID-03's own browser fix), leaving the API-only rule as a later hardening; this needs 03 §3.6, 04 rule 9d and 06 §6.2 changed together |
| — | §5.5 step 5 "Revert under `DISABLED`/`PAUSE`" (former R71 (a)) | §6.8 `PAUSE.<system>` does not allow revert | every `PAUSE.<system>[@<brand>]` blocks revert | — | CONFORMED 2026-09-28 (no longer a deviation) |

**Cross-file prerequisites (not deviations; tracked with the same issue).** These amendments must
land in their owning files before the named WP starts, because this file's text depends on them:
(p1) 03_schemas.md §3.7 display key `operator_executes` (R76 (c)) — WP-C and WP-A2 (`display.resulting_status`
and the §3.4.1 `resulting_status` row field landed in 03 wave1e; `change_kind` withdrawn); (p2) 03_schemas.md §3.11 no longer describing a `card_deny` cancel
marker written by act.py on a card deny, and §3.7/§3.8 no longer describing a `decided_via: "card"`
denial (R75/R76) — WP-A2; (p3) 00_global_paths.md `gtm_env.approver_app_path()` (R37) and
`gtm_env.gtm_tmp_root()` (R80; **landed in 00 §1.1's export table wave1e**) — WP-C and WP-A2; (p4) 06_connectors.md
`owner_execution_reason` (R78) — WP-A2; (p5) 07_notices_schedules.md D6b widening and the reserved
dedupe prefixes (R79) — WP-A2 and WP-K; (p6) 04_hooks.md G-A rule 6b ignoring agent markers for
signed actions and the G-B `-X pycache_prefix` denial (R77) — WP-A2.
A2 test (documentation gate, K-style): the WP-A2 dispatch checklist in 08_seats_wps.md Appendix B
names this register and refuses to start while any row reads UNRATIFIED (R81 asks 08 for the
line); removing a row without a CONFORMED/RATIFIED status fails it.
