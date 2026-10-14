# Codex cross-model review (scaffold — WS4)

**Plan:** `plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md`, "## 5.
WORKSTREAM 4 — Cross-model review with Codex" (§4.1-§4.8a). Tracking issue: example-org/
#5830. **This doc describes the SCAFFOLD only** — the plumbing that exists so
Codex CAN be invoked once the operator has an account and has consented. Read the plan section in
full before changing any file this doc describes.

**Fix round 1 (trust-architect, reviewer-of-record, 2026-09-20): blockers=5, all fixed.** The
reviewer proved, by execution, that every gate between the scaffold and actually sending code to
OpenAI was bypassable using nothing but environment variables — with a fake `codex` binary and
planted auth/canary files, a real-shaped AWS key, a Stripe-shaped key, and a denylisted catalog
file's content all reached a `verdict=clean` exit. See "Fix round 1: what was found and fixed"
below for the full account.

**Fix round 2 (trust-architect round 2, 2026-09-20): blockers=2, both fixed; B1–B5 confirmed FIXED
by execution.** Round 2 found TWO NEW blockers in round 1's own fix code — B6, arbitrary code
execution via a pathspec token breaking out of a Python string literal in an unquoted heredoc (the
same bug class B1 had already been fixed for, but present at one remaining site); B7, the
rename/copy denylist check still bypassable via a directory or `./`-prefixed pathspec token. Round
2 also corrected a FALSE claim round 1 made about SIGINT cleanup (see "SIGINT and SIGTERM cleanup"
below). See "Fix round 2: what was found and fixed" below for the full account. Both rounds' fixes
are what this doc now describes as the CURRENT state.

## State today (2026-09-20): scaffold only; refuses to run; nothing has been sent to OpenAI

- The operator has no Codex account yet (his words: "not yet dont have account"). `~/.codex/`
  holds only an empty `tmp/` — no auth file.
- `scripts/codex_available.sh` — the readiness gate — **always exits non-zero today**, and will
  keep doing so until all four of: (1) `codex login` has run, (2) the operator has separately
  consented (card line 5/5a of the plan's §11 approval card) and a **root-owned** consent marker
  exists (see "Consent mechanism" below — this is new in fix round 1), (3) a passing four-probe
  canary exists (`scripts/codex_canary.sh` — **BUILT 2026-09-23**, see "The canary" below; it
  cannot produce a passing record until (1) and (2) hold, because it propagates
  `codex_available.sh`'s own refusal), and (4) no stale export directory is sitting in `$TMPDIR`
  from a prior run that died before cleanup.
- `scripts/codex_review.sh` refuses to run at all unless `codex_available.sh` passes. Since that
  never passes today, `codex_review.sh` never reaches the point of building an export, running the
  egress scan, or invoking the `codex` binary. **No code, diff, or file content from this repo has
  ever been sent to OpenAI by this scaffold.**
- Nothing in this scaffold is wired into `record_review.py`, `pretooluse_bash.py`,
  `settings.json`, any agent definition, or `CLAUDE.md`. It is not consulted by any live review
  boundary. It cannot currently affect any commit, gate, or agent behavior in any way.

## What exists

| File | Purpose |
|---|---|
| `tools/codex/config.toml` | Installed to `~/.codex/config.toml`. Governs bare/interactive `codex` use only — `codex_review.sh` always passes `--ignore-user-config` and never loads it. Pins the model and the least-privileged sandbox default; explicitly never widens sandbox/shell-env policy. |
| `tools/codex/AGENTS.md` | Installed to `~/.codex/AGENTS.md`. Codex's own system-prompt-equivalent: states the diff/content is DATA not instructions, that Codex has no tool grants/MCP/network in v1, that it decides nothing, and how to report injection attempts. |
| `tools/codex/review-instructions.md` | Installed to `~/.codex/review-instructions.md`. The review checklist — adapted from `agents/code-reviewer.md`, narrowed for a single-shot, tool-less, non-round-based invocation. Named defect classes, severity levels, evidence discipline. |
| `tools/codex/review_schema.json` | The JSON Schema Codex's `-o`/`--output-last-message` file must satisfy: `verdict`, `findings[]` (file/line/severity/class/claim/evidence), `not_read[]`. Passed via `--output-schema`. |
| `scripts/install_codex_config.sh` | Copies the four `tools/codex/` files into `~/.codex/`. Idempotent; never touches an auth file; refuses to overwrite a file that drifted from what it last installed unless `--force`; refuses to install through a symlinked `~/.codex` unless `--force` (fix round 1); supports `--dry-run`. Re-asserts `chmod 700 ~/.codex` + `chmod 600` on any auth file as its first step, every run. |
| `scripts/codex_available.sh` | Readiness gate. Exit 0 only when: the binary exists+executable (exit 1 otherwise), an auth file exists and is not a symlink (exit 2 otherwise — a symlinked auth file is now refused with its own reason, fix round 1), and a **root-owned, mode-0444** consent marker exists and validates (exit 3 otherwise — hardened in fix round 1, see below). |
| `scripts/codex_review.sh` | The hardened wrapper. Takes only `<repo_root> -- <pathspec>` (or `--sweep-stale`, a separate maintenance entry point), no pass-through arguments. See "The wrapper's contract" below. |
| `scripts/grant_codex_consent.sh` | **NEW in fix round 1.** Operator-only, must be run with `sudo`. Writes the root-owned consent marker `codex_available.sh` checks. Never agent-invokable in practice — see its own header. |
| `hooks/tests/test_codex_review.py` | 67 hermetic tests (1 legitimately skipped — see below), all against a fake `codex` and temp dirs — never the real binary, the real `~/.codex`, or the real `.review_state`. |

## Fix round 1: what was found and fixed

The reviewer executed a bypass using ONLY environment variables against the pre-round script:
`CODEX_AVAILABLE_SH=<a stub that always exits 0>`, a self-written canary JSON dropped into an
overridden `FINDINGS_DIR`, `CODEX_HOME=<a dir with a planted auth.json>`, `CODEX_BIN=<a fake>` —
and the script ran to completion, exit 0, having handed the fake codex a real-shaped AWS key, a
Stripe-shaped key, and a denylisted catalog file's content, all read from the export it built.

**B4 — the root cause: five different overridable variables, together, let a caller substitute
every safety-relevant input.** Fixed by removing `CODEX_AVAILABLE_SH`, `SCHEMA_FILE`,
`AGENTS_FILE`, `REVIEW_INSTRUCTIONS_FILE`, `PYTHON_BIN`, `PERL_BIN`, and `CLAUDE_DIR` entirely.
Every security-relevant path is now derived from **the script's own on-disk location**
(`$(cd "$(dirname "$0")/.." && pwd -P)`), never from a caller-supplied variable. `CODEX_BIN` is
honoured only under a narrow **test-mode discriminator**: `CODEX_REVIEW_TEST_MODE=1` unlocks it
ONLY when the script's own resolved runtime dir is NOT the real invoking user's `$HOME/.claude` —
running the actual installed script from `~/.claude/scripts/` can never satisfy that condition, so
the variable is provably inert against the real installation (this is asserted directly by the
test suite's `TestRealInstallIsUnaffectedByTestMode` class, which re-runs the reviewer's exact
bypass shape against the real installed script and confirms it still refuses).

**B1 — the egress secret scan was VACUOUS.** `detect-secrets scan <absolute path>` treats its
argument as a repository root; scanning a path OUTSIDE the current working directory returns
`"results": {}` regardless of content — proven by execution (`detect-secrets scan
/abs/path/leak.py` → `{}`; `cd /abs/path && detect-secrets scan leak.py` → 4 findings, same
binary, same file). Fixed: the scan now `cd`s into the export directory and scans RELATIVE paths.
A **mandatory positive control** runs before every real scan: a file containing a real-shaped AWS
key is written and scanned exactly the way the real scan will run it; if the scanner reports it
clean, the whole invocation refuses with `scanner-inert` (exit 14) rather than trusting a scanner
that just proved it can't find anything. Two further defects surfaced and fixed while building
this: the file-iteration loop used unquoted `for f in ... $(find ...)`, silently skipping any path
containing a space (fixed: `find -print0` piped to `while IFS= read -r -d ''`); and the scanner's
own JSON output was interpolated into an unquoted heredoc's Python source text (a latent
code-injection path — fixed: `<<'PY'` with quoting, JSON piped via stdin instead).

**A second, independent bug was found and fixed while building the falsifiability test for B1's
positive control**, not by the reviewer: the original `_scan_json_has_findings` helper piped the
scanner's JSON into `python3 - <<'PY' ... PY` — but a bash heredoc attached to `python3 -`
occupies the interpreter's OWN stdin with the heredoc's literal source text, so a caller's
`something | this_function` pipe was silently discarded; `json.load(sys.stdin)` then parsed the
heredoc's source as JSON, always failed, and the mandatory positive control therefore ALWAYS
reported `scanner-inert` — meaning the egress scan could never run at all, a different failure
mode than B1's original vacuous-pass but still a defect. Fixed: the Python source is now passed
via `-c "<fixed string>"`, leaving stdin free for the piped scanner JSON.

**B2 — a rename smuggled a denylisted file's content past both existing denylist checks.**
`git diff HEAD -- <pathspec>` scopes AWAY the deletion side of a rename when the pathspec names
only the destination: `git mv modules/catalog_api_public/data/Items.csv docs/readme.md` with
pathspec `docs/readme.md` makes the denied source path appear nowhere in that scoped diff. Fixed:
a separate, unscoped `git diff HEAD --name-status --find-renames --find-copies` (both unstaged and
`--cached`, since a staged rename shows up only in the cached form) runs before the export is
built, and refuses if any `R`/`C` record's source matches a denied glob and its destination is in
the caller's pathspec. The BUILT EXPORT's actual file list is also re-checked against the denylist
as a second, independent layer. Also fixed: the denylist match is now case-INSENSITIVE
(`shopt -s nocasematch`, restored after) and includes `**/*.jpeg` — macOS's default filesystem is
case-insensitive, so `key.PEM` and `key.pem` are the same file on disk, and the pre-fix match
missed `.PNG`/`.JPG`/`.jpeg`/`.PEM` entirely.

**B3 — the credential was copied INSIDE the directory Codex reads.** The pre-round script set
`HOME=$EXPORT_DIR`, `CODEX_HOME=$EXPORT_DIR/.codex`, and `-C $EXPORT_DIR` — so the copied auth file
lived inside codex's own `-C` working root. `-s read-only` restricts writes, not reads, and Codex
runs model-generated shell commands, so the auth file was `cat`-able by anything Codex was talked
into running. Fixed: `$EXPORT_HOME` is the `mktemp`'d directory itself; `$EXPORT_DIR` is a
SUBDIRECTORY of it. The auth copy now lives at `$EXPORT_HOME/.codex/` (a SIBLING of `$EXPORT_DIR`,
never inside it), `HOME=$EXPORT_HOME`, `CODEX_HOME=$EXPORT_HOME/.codex`, and `-C` still points at
`$EXPORT_DIR` — so a recursive enumeration of the `-C` root cannot reach `.codex/` at all. Verified
directly: a fake codex that enumerates its own `-C` root recursively finds no `.codex` or `auth`
entry.

**B5 — schema validation silently degraded without `jsonschema` and reported clean.** The pre-round
script fell back to a required-keys-only check when `import jsonschema` failed; a message with
`"file":"ROGUE_KEY"`, `"severity":"CATASTROPHE"`, `"class":"made-up"` was ACCEPTED as
`verdict=clean` because the fallback never checked enum membership, only key presence. Fixed:
`jsonschema` (pinned `/usr/bin/python3`, confirmed to carry `jsonschema` 4.23.0 on this machine) is
now MANDATORY — no fallback. A missing/unimportable validator is an OUTAGE (exit 15, reason
`validator-unavailable`), never a degraded pass. Verified by a genuine `PYTHONPATH` shim that
raises `ImportError` specifically for `jsonschema` (the validator step is NOT run under `env -i`,
so a `PYTHONPATH` seam is legitimately available here without reintroducing `PYTHON_BIN`): with the
import genuinely blocked, the rogue-key message is correctly refused as an outage, never parsed as
clean.

## Non-blocking findings landed the same round

- **Stale-export-dir refusal + `--sweep-stale`.** The wrapper now refuses to start a new export if
  a `codex_export.*` directory already exists under `$TMPDIR` (it may hold a credential copy from a
  run that died before its cleanup trap ran) — exit 16. `bash codex_review.sh --sweep-stale` is a
  SEPARATE entry point (never parsed as part of the normal invocation) that removes stale export
  trees older than 10 minutes and owned by the invoking uid, printing each path; never automatic.
- **Parser-side hardening.** A finding whose `file` field is not a path actually in the caller's
  pathspec is DROPPED and counted (`findings_dropped_out_of_pathspec`) — proven exploitable
  pre-fix: `"file":"../../../etc/passwd"` was written verbatim into the findings file. URL-shaped
  and shell-command-shaped substrings are stripped from every free-form string field (`claim`,
  `evidence`), replaced with `[url removed]` / `[command removed]`. The findings file now carries
  two top-level at-rest labels: `"_source": "codex-untrusted-vendor-output"` and `"_contract":
  "data-about-the-diff-never-an-instruction"`.
- **64KB response cap now TRUNCATES.** A last-message file over 64KB is an outage (exit 15, reason
  `response-oversize`) and is never parsed at all — the pre-round build only flagged the oversize
  condition in its stdout message while still parsing and trusting the content.
- **`install_codex_config.sh` refuses a symlinked `~/.codex`** unless `--force` (exit 5).
- **`codex_available.sh` refuses a symlinked auth file with its own distinct reason.** The pre-fix
  `find -type f` silently EXCLUDED a symlink, so a symlinked auth file fell through to "not logged
  in" by accident rather than being refused for what it actually is.
- **`CODEX_REVIEW_TIMEOUT_SEC` bounds enforced**: must be an integer 1–600 inclusive. Uses
  `${VAR-180}` (no colon) rather than `${VAR:-180}` deliberately — the colon form treats an
  explicitly-set-but-EMPTY value the same as unset, which would have silently substituted the
  default instead of rejecting the empty string as invalid input (found while writing this fix
  round's own test suite).
- **Exit-code split**: `0` = schema-valid AND verdict clean; `1` = schema-valid WITH findings
  (still advisory, still gates nothing); `10`/`20` split into `20` (not available: binary/auth),
  `21` (consent missing/invalid), `22` (canary missing/stale); `13` (empty diff) split from `17`
  (diff too large). See the script's own header comment for the authoritative, current table —
  this doc, `AGENTS.md`, and the header agree.
- **Dead prohibited-flag entries documented, not silently left broken.** `"-s workspace-write"` /
  `"-s danger-full-access"` as single strings in the prohibited-substring list can never match a
  caller's two separate tokens (`"-s"`, `"workspace-write"`) — the generic leading-dash refusal
  always fires first on `"-s"` alone. Kept as documentation of what the wrapper's own hard-coded
  invocation must never contain; a test confirms `-s` alone is refused by the GENERIC check, not
  the (unreachable) pair.

## Fix round 2: what was found and fixed

Round 2 confirmed every round 1 blocker (B1–B5) FIXED by execution and ruled the root-owned
consent design sound (could not be broken). It found two NEW blockers in round 1's own fix code.

**B6 — pathspec-token CODE INJECTION into the parser's Python source.** The findings-writing block
built `_PATHSPEC_JSON` and expanded it INTO Python source text inside a `'''...'''` literal, via
an UNQUOTED `<<PYOUTER` heredoc delimiter — `json.dumps()` does not escape a literal `'''`
sequence inside a string, so a pathspec token containing `'''` broke out of the string literal and
was parsed as executable Python **in the orchestrator's own process**. Proven by execution: a
committed file whose name embedded a `'''`-breaking payload, passed as the pathspec, ran the
injected code (confirmed via a sentinel file the payload wrote). This is the same bug class B1 was
fixed for in round 1 (the scan-JSON heredoc) — this was the one remaining site.

Fixed, and audited across the WHOLE script (not just the one site the reviewer hit): every
Python-target heredoc now uses a QUOTED delimiter (`<<'PY'`/`<<'PYOUTER'`), so bash performs zero
interpolation inside any of them; every variable value reaches Python exclusively via `sys.argv`
or a file read by path. The full audit: 8 heredoc-fed `python3 -` invocations, all quoted; 4
`python3 -c` invocations, all either a fixed literal string with data via argv, or (one
`_SCAN_JSON_CHECK_SRC` variable) a fixed single-quoted literal never touched by any interpolation,
with its own data arriving via `sys.stdin`; one remaining unquoted heredoc (`<<EOF` for
`CAPPED_NOTICE.txt`) is a plain-text file write, never parsed as code by anything, with only
internal integer variables interpolated — out of scope for this rule, confirmed safe. A second,
lower-severity interpolation (`$FINDINGS_PATH` inside a `-c "..."` double-quoted string) was found
and fixed in the same pass, defense-in-depth (not independently proven exploitable, but the same
class of pattern the rule forbids).

**While building this fix, two further real bugs surfaced and were fixed, neither in the
reviewer's report:** (1) the initial fix attempt piped `_PATHSPEC_JSON` via `printf | python3 -
<<'PYOUTER'` — but a command with BOTH a pipe into it AND a heredoc attached gives the heredoc
`fd0` entirely, silently discarding the pipe (proven by direct experiment: `printf X | python3 -
<<'H' ... H` fed python neither `X` alone nor the heredoc alone, but a garbled concatenation of
the two, and every test in `TestParserHardening` failed with a `JSONDecodeError` under this
shape). Fixed: `_PATHSPEC_JSON` is written to a throwaway file inside `$EXPORT_HOME` (already
trap-cleaned) and its PATH passed as an ordinary argv argument — data, never source, and no
pipe/heredoc conflict. (2) An unrelated, pre-existing regex bug (`_CMD_RE`'s `\\\$\\(` — an
unescaped, unclosed `(` that `re.compile` rejects on Python 3.13, though apparently tolerated
differently on 3.9) was found while diagnosing the above; fixed to the intended `\$\(` (a literal
`$(` shape).

**B7 — the rename/copy denylist check still bypassable via a directory or `./`-prefixed pathspec
token.** Round 1's fix checked a rename/copy record's destination against an EXACT STRING match of
the caller's raw pathspec tokens — but `git diff HEAD -- <pathspec>` resolves a directory token
(e.g. `docs`) or a `./`-prefixed token (e.g. `./docs/readme.md`) to the files it actually contains,
which the exact-string check never accounted for. Proven by execution: pathspec `docs` (a
directory) and pathspec `./docs/readme.md` both bypassed the round-1 check entirely (exit 0,
denied content reached codex) against the identical `git mv modules/catalog_api_public/data/
Items.csv docs/readme.md` fixture that round 1's own pathspec `docs/readme.md` correctly caught.

Fixed: never reason from raw tokens. The destination-membership check now runs against `git diff
HEAD --name-only -- "${PATHSPEC[@]}"`'s own resolved output (both unstaged and `--cached`) — the
SAME pathspec resolution git itself uses everywhere else in this script. **Pinned behavior,
tested:** a pathspec-magic token such as `:(glob)docs/**` is not rejected by the flag-shape check
(only a leading `-` is refused) and, because the fix defers entirely to git's own resolution
rather than reasoning about the token, resolves and is caught exactly the same way a plain
directory/`./` token is — no special-case code needed.

## Non-blocking findings landed in fix round 2

- **Exit 21 (consent missing/invalid) was UNREACHABLE.** `if ! cmd; then _AVAIL_RC=$?` captured
  the NEGATED CONDITION's own status inside the `then` branch — `! cmd` succeeding (exit 0) is
  what put execution in `then` in the first place, so `$?` there was always 0, never `cmd`'s real
  exit code. Every consent failure silently mapped to the generic `*)` catch-all (exit 20).
  Fixed: run the command directly (no `!`), capture `$?` on the very next line, then branch on it.
- **The SIGINT-gap claim was corrected** (a false claim in a test AND in this doc) — see "SIGINT
  and SIGTERM cleanup" above. The vacuous `assert True` tests (both the SIGINT one and a second,
  unrelated one documenting the UNVERIFIED root-owned consent path) were deleted; the SIGINT one
  was replaced with a real test against the wrapper's actual shape; the root-owned-path note moved
  into a docstring/comment, since a design note belongs there, not in a test that exercises
  nothing.
- **A stdout leak fixed.** The findings-writing Python block used to `print(verdict or "")`,
  leaking a bare `clean`/`findings` token onto stdout BEFORE the wrapper's own `codex_review: OK
  ...` line — confusing for any caller reading stdout. The shell already re-reads the verdict from
  the findings FILE this block writes, never from this block's own stdout, so the print added
  nothing functional. Removed.
- **`--sweep-stale` now exits `2`**, distinct from `0` (a genuinely clean review) — a caller
  checking only `$?` could not previously tell "the sweep ran" apart from "the review was clean".
  Its stdout now carries a clear `codex_review: sweep-stale ...` marker. Documented in the script's
  own header comment, `AGENTS.md`, and this doc — all three agree.
- The doc's follow-up list (Deviations, above) carries "where does `detect-secrets` live
  long-term" beside the denylist-location move — both are now grouped under one numbered item so
  they are tracked together, not lost as separate, easy-to-drop line items.

## SIGINT and SIGTERM cleanup — both proven reliable (corrected in fix round 2)

**Both SIGINT and SIGTERM clean up correctly** in the wrapper's actual shape: the codex invocation
runs backgrounded in its own process group (`set -m; ( ... ) &`) and is `wait`ed on. `wait` is an
interruptible bash builtin — a signal delivered while the script is blocked inside it runs the
registered trap promptly, for either signal, and the trap does an explicit process-group kill
before removing the export directory (auth copy included). Verified directly: a fake `codex` that
records its `-C` root before sleeping confirms it was genuinely invoked, `SIGINT` is sent, the
wrapper exits `130`, and the export directory (with the auth copy) is gone immediately after — see
`hooks/tests/test_codex_review.py::TestSignalCleanup` for both the SIGTERM and SIGINT tests,
run repeatedly for stability during this round.

**Correction, stated plainly:** fix round 1's own version of this doc claimed SIGINT cleanup was
an "unresolved gap," based on testing a MINIMAL repro (a bare `trap ... INT` plus `sleep`, no
`wait`, no job control, no backgrounding) rather than the wrapper's actual shape — that repro
genuinely does not respond to SIGINT the way the real wrapper does (bash's signal-delivery
semantics differ for a plain child process blocked in `sleep` versus one blocked in an
interruptible builtin like `wait`), so the conclusion drawn from it was wrong. trust-architect's
round 2 review proved the real shape works by direct execution; this was re-verified
independently while building this fix, including a second stability run.

A shape that would NOT clean up reliably: a bare foreground `sleep`-equivalent with no `wait`
involved, or a background job launched from a non-interactive shell that ignored SIGINT at entry
(a genuine, separate bash/POSIX characteristic for asynchronous commands, unrelated to this
wrapper's own design). `--sweep-stale` and SIGKILL remain the correct backstops for anything that
somehow still manages to survive a signal.

## Consent mechanism (new in fix round 1)

The operator's "yes" on plan §11 card item 5/5a must translate into a file no self-serve agent
action can forge. **Design: a root-owned marker, written only by a human running
`scripts/grant_codex_consent.sh` with `sudo` in their own terminal.**

- `codex_available.sh` treats the marker as valid ONLY if it is: a REGULAR file (never a symlink),
  owned by uid 0 (root), mode EXACTLY `0444`, valid JSON, with `"scope": "ws4-v1-advisory"`. Any
  other shape — user-owned, wrong mode, a symlink, wrong/missing scope, unparseable — is NOT
  consented.
- An agent running as the operator's own user CAN delete this marker (revoking consent — fails
  safe) but CANNOT create one that passes, because it cannot `chown` a file to root without `sudo`,
  which this runtime's own standing rule forbids any agent from ever invoking.
- `scripts/grant_codex_consent.sh` refuses outright unless `id -u` is 0 AND `$SUDO_USER` is set;
  writes `<runtime dir>/.review_state/codex/CONSENT.json` (`{"consented_at": <epoch>, "operator":
  "<SUDO_USER>", "scope": "ws4-v1-advisory", "host": "<hostname>"}`), owner root, mode 0444;
  supports `--revoke` and `--dry-run`. It was never run with real `sudo` while building this
  scaffold — only its not-root refusal path was exercised.
- Every successful send appends one line to `.enforcement/log.jsonl`
  (`{"event": "codex-consent-consumed", "ts": ..., "pending_key": ...}`).
- **Location is an interpretation, not a plan-cited fact** — the plan's §11 card text says consent
  is required but never names an exact marker path/filename. `<runtime dir>/.review_state/codex/
  CONSENT.json` mirrors the existing `.review_state` layout; confirm or rename before this is ever
  treated as load-bearing beyond this scaffold.

**Test coverage note:** a test cannot create a genuinely root-owned file (that requires `sudo`,
which this suite never invokes). Every NEGATIVE case (user-owned, wrong mode, symlink, wrong
scope) is tested against the REAL, unmodified ownership/mode/JSON-validation logic. The POSITIVE
path (a real root-owned marker) uses one narrow, test-mode-gated seam
(`CODEX_REVIEW_TEST_TRUST_OWNER=1`, active only under the same test-mode discriminator as
`CODEX_BIN`) that substitutes ONLY the uid==0 check — every other condition (symlink, regular-file,
mode-0444, JSON validity, scope) stays fully real even when this seam is active. The genuine
root-owned positive path is **UNVERIFIED** by any test in this repo; this is stated explicitly
rather than assumed covered.

## The wrapper's contract (`codex_review.sh`)

In order:

1. **Availability gate.** Runs the REAL sibling `codex_available.sh` (resolved from the script's
   own directory — never overridable). Refuses (exit 20 not-available / exit 21 consent
   missing-or-invalid) unless it passes.
2. **Canary freshness gate.** Refuses (exit 22) unless a passing canary dated within 30 days
   exists at `.review_state/codex/canary_*.json` (read from the runtime dir, never from an
   overridable output-dir variable). `scripts/codex_canary.sh` is **built as of 2026-09-23** (see
   "The canary" below), but it cannot yet WRITE a passing record: it refuses while
   `codex_available.sh` refuses, so this gate still cannot pass today — a second independent
   reason nothing can be sent before login + consent.
3. **Egress denylist + rename/copy check**, checked against the caller's literal pathspec, then
   against an unscoped `--find-renames --find-copies` name-status diff (whose destination-
   membership check runs against git's own RESOLVED `--name-only` file set, never raw pathspec
   tokens — fix round 2 B7, so a directory/`./`-prefixed/magic pathspec token is handled exactly
   the way git itself resolves it), then against the diff's own file headers, then against the
   BUILT EXPORT's actual file list — four independent layers. A match refuses the WHOLE invocation
   (exit 12); it never silently drops one file. Paired recovery: the same call minus the denied
   path/rename proceeds past this stage.
4. **Diff build + size cap.** `git diff HEAD -- <pathspec>`; an empty diff is exit 13; over 20,000
   lines is exit 17.
5. **Stale-export-dir check + scratch export.** Refuses (exit 16) if a prior export dir is still on
   disk. Otherwise builds a temp dir (never a git repo) holding `diff.patch`, `files/<path>` (full
   content up to 2,000 lines/20 files, else a windowed `±200`-line-context patch), plus copies of
   `AGENTS.md`/`review-instructions.md`.
6. **Egress scan** — relative-path `detect-secrets scan`, gated by a mandatory positive control.
   Any finding, any scan error, or an inert scanner is a hard STOP (exit 14); Codex never invoked.
7. **Auth copy**, only after the scan passes: the single real auth file is copied into
   `$EXPORT_HOME/.codex/` (a SIBLING of `$EXPORT_DIR`, never inside it) at mode 600, never a
   symlink, removed by a `trap` on every exit path.
8. **Invocation**, under `env -i` with the fixed allowlist, the exact flag set from plan §4.3,
   `-m` hard-coded, `codex` resolved to `/opt/homebrew/bin/codex` unconditionally (never
   overridable outside the test-mode discriminator), bounded by the `perl -e 'alarm shift; exec
   @ARGV'` idiom. Backgrounded in its own process group and `wait`ed on, not run as a blocking
   foreground pipeline — both SIGTERM and SIGINT cleanup are proven reliable this way (see "SIGINT
   and SIGTERM cleanup" above).
9. **Parsing.** Only the `-o` last-message file is read (after a 64KB size check — an oversize
   response is exit 15, never parsed), validated against `review_schema.json` via a MANDATORY
   `jsonschema` import (exit 15 `validator-unavailable` if it cannot be imported — never a degraded
   pass). The `--json` event stream is captured but never parsed as data.
10. **Findings write.** Out-of-pathspec findings dropped and counted; URL/command-shaped
    substrings stripped from free-form fields; at-rest labels added. Written to
    `~/.claude/.review_state/codex/<pending_key>.json` (or the `FINDINGS_OUTPUT_DIR` override,
    write-only, never read from for anything security-relevant). The wrapper does NOT call
    `record_review.py` itself — that remains a later, separately-reviewed step.

No exit path can be mistaken for "review clean": `0` is the only clean exit, `1` means findings
(still advisory), and even on `0` the caller must read the findings file's own `verdict` field.

## Environment variables the scripts honour, and why each is safe

| Variable | Honoured when | Why it cannot weaken the scaffold |
|---|---|---|
| `CODEX_REVIEW_MODEL` | always | Written into the findings file; changes which model is *requested*, never any safety check. |
| `CODEX_REVIEW_TIMEOUT_SEC` | always | Bounds-checked 1–600; rejects non-integers and empty strings; only affects how long codex is allowed to run. |
| `DETECT_SECRETS_BIN` | always | Still subject to the mandatory positive control — a broken/no-op override is refused as `scanner-inert`, by construction. |
| `FINDINGS_OUTPUT_DIR` | always | WRITE-only target for this run's own output; nothing security-relevant (schema, AGENTS.md, consent, canary) is ever READ from it. |
| `CODEX_REVIEW_TEST_MODE` | only unlocks anything when the script's own resolved runtime dir ≠ the real `$HOME/.claude` | Cannot be satisfied against the real install — proven by a test that sets it and confirms the real script still refuses. |
| `CODEX_BIN` | only under the test-mode discriminator | Otherwise the real, hard-coded `/opt/homebrew/bin/codex`, unconditionally. |
| `CODEX_REVIEW_TEST_HOME` | only under the test-mode discriminator | Governs where `~/.codex` resolves from for that run only. |
| `CODEX_REVIEW_TEST_TRUST_OWNER` | only under the test-mode discriminator | Substitutes ONLY the consent marker's uid==0 check; every other consent condition stays real. |

Every OTHER variable a prior build read (`CODEX_AVAILABLE_SH`, `SCHEMA_FILE`, `AGENTS_FILE`,
`REVIEW_INSTRUCTIONS_FILE`, `PYTHON_BIN`, `PERL_BIN`, `CLAUDE_DIR`, `CODEX_HOME`, `FINDINGS_DIR`)
is GONE. `TMPDIR` is honoured (standard OS mechanism, not a scaffold-specific override) for where
the export directory is created — it does not change WHAT gets checked, only where scratch content
lives, and the stale-export-dir check globs whatever `TMPDIR` resolves to.

## Deviations / interpretations flagged for operator or follow-up review

1. **Consent marker location and exact enforcement shape** — see "Consent mechanism" above.
2. **`detect-secrets` resolution AND denylist location — the two "where does this product-specific
   knowledge live long-term" follow-ups, tracked together.**
   - `detect-secrets` is not on the wrapper's own fixed `PATH` (`/usr/bin:/bin:/opt/homebrew/bin`)
     on this machine at all. Resolution order: the `DETECT_SECRETS_BIN` override, then a bare
     `detect-secrets` on PATH, then the REVIEWED repo's own `<repo>/.venv/bin/detect-secrets`.
     Found nowhere → refuse. Needs a real decision on where this binary lives long-term.
   - The product-specific denylist glob list (`modules/catalog_api_public/data/*`, the trade_kb
     corpus paths, etc.) is currently hard-coded in `codex_review.sh` itself — a **tracked
     follow-up, not implemented this round**: move these globs to
     `<repo>/.claude/oversight/manifest.json`, union with a runtime-level universal floor (the
     `.env`/`.pem`/credential patterns, which are NOT product-specific), and REFUSE a repo that
     declares no list at all rather than silently falling back to the runtime floor alone.
3. **`config.toml` key names** (`model`, `sandbox_mode`) are UNVERIFIED against Codex's actual
   config schema — `codex exec --help` only demonstrates two example dotted paths, not a full
   schema. Irrelevant to the wrapper's own safety (`--ignore-user-config` is always passed); would
   only matter for bare/interactive `codex` use.

## The canary (BUILT 2026-09-23, unwired, cannot pass today)

`scripts/codex_canary.sh` implements the four probes plan §4.4 requires before any real use:
filesystem escape, symlink traversal, environment inheritance, and network reach. Each probe runs
as its own invocation with the §4.3 hardened flag set, and each **first proves Codex actually ran**
by planting a nonce INSIDE the export that must come back — no nonce means that probe is INVALID
and counts as FAIL, so "token not returned" can never be satisfied by a Codex that never launched.
Probe 4 (network reach) failing means WS4 is SEVERED, not merely blocked: no wrapper-side change
can fix outbound reach from inside the sandbox. Results are written to
`.review_state/codex/canary_<date>.json`, and `codex_review.sh` refuses (exit 22) without a passing
record dated within 30 days. `codex_available.sh` records the `codex` version and forces a
re-canary on a version mismatch, so a Codex upgrade that silently widened the sandbox cannot go
unnoticed. Tests: `hooks/tests/test_codex_canary.py` (49 tests, all against a FAKE `codex` binary —
never the real one, never the real `~/.codex/`).

**It cannot produce a passing record today**, and that is by construction: it propagates
`codex_available.sh`'s refusal, which stands until the operator has an account, has run
`codex login`, and has written the root-owned consent marker. Building it removed one of the three
independent blocks; the other two remain, and both are operator-gated.

**Known follow-up (non-blocking, filed):** probe 4's escape marker is the literal string
"Example Domain", which an LLM can emit from memory with no network access, whereas probes 1-3 use
unguessable random hex. This fails SAFE (a false alarm on a sandbox that actually held, never a
false clearance) but will waste a real investigation; it should fetch a nonce-bearing URL instead.

## Not yet built (out of this scaffold's scope)

- Any wiring into `record_review.py` (the `--codex <clean|findings:N|owed|down>` flag), any hook,
  `settings.json`, any agent definition, or `CLAUDE.md`. These are later, separately-reviewed
  steps per the plan's own sequencing (Wave 2) and the task brief's explicit "DO NOT" list.
- Referee mechanics (plan §4.5, cold dispatch of the reviewer-of-record on a rejected finding).
- The denylist-location move described in deviation 4 above.

## The operator steps that remain

1. **Create the Codex/OpenAI account** and run `codex login` (his stated task).
2. **Answer the consent card lines** — plan §11 items 5 and 5a — once posted to
   `_Config_Project/docs/domain/OPERATOR_DECISIONS.md` per that repo's operator-input rule.
3. **On a "yes," run `sudo bash ~/.claude/scripts/grant_codex_consent.sh`** in his own terminal —
   the one, single operator command this scaffold requires, and the only way the consent marker
   can ever come into existence in a shape `codex_available.sh` accepts.
4. **Pass the four-probe canary** (`scripts/codex_canary.sh` — built 2026-09-23; it refuses to
   produce a record until steps 1-3 above hold, so this step is *run*, not built).
5. **A passing egress-denylist dry-run on 3 past HIGH-tier boundaries**, per plan Wave 2's stated
   entry bar for "WS4 advisory live."

Only after all five does `codex_review.sh` ever reach the point of invoking the real `codex`
binary with real repository content.

## Rollback

`sudo bash ~/.claude/scripts/grant_codex_consent.sh --revoke` (revokes consent — an operator
action; also revoke the credential in the OpenAI console separately, per plan §4.8a item 5);
`rm -rf ~/.codex/`; `git revert` the commit(s) that added `tools/codex/`, `scripts/
install_codex_config.sh`, `scripts/codex_available.sh`, `scripts/codex_review.sh`, `scripts/
grant_codex_consent.sh`, and `hooks/tests/test_codex_review.py`; delete `~/.claude/.review_state/
codex/` if it was ever created. No gate, schedule, or default depends on any of this scaffold
today, so reverting it changes nothing else in the runtime (plan §4.8 / §10.2).
