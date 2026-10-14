# Board state (`priority_backfill.py` + `.board_state/`)

*Rollback and mechanics reference for `~/.claude/scripts/priority_backfill.py`. Read the script's
own module docstring first — this page orients and points there; it does not restate the mapping
table or the full B1-B4 rationale.*

## `plan` / `--from-plan` — the recommended way to run a large batch (2026-09-20)

**Read this section before running either of the approved bulk batches (`backfill-priority`,
`reset-ready`).** A single full board read — `gh project item-list` on the live example-org
board (~1,500 items) plus the `gh issue list` open-issue-number read — was **measured at 1,834
GraphQL points**, out of the account's 5,000-points/hour budget. That budget is **shared by every
Claude session on this machine**, including a release session that needs `gh pr create`/`gh pr
merge`. Every invocation of `backfill-priority`/`reset-ready`/`reverse` — dry-run or `--apply` alike
— used to perform that full read. The approved batches (~295 Priority writes + ~247 Status writes,
capped at 40 writes per `--apply` pass) need roughly 15 passes; at 1,834 points per pass that is
~27,000 points — over five times the hourly budget — and it exhausted the real budget twice in one
evening (2026-09-20) before this subsystem existed.

**The fix: read the board ONCE, save a plan, then run many cheap passes against the saved plan.**

```
# 1. One full read, writes a plan file, touches NOTHING on GitHub:
python3 ~/.claude/scripts/priority_backfill.py plan --for backfill-priority \
    --owner example-org --repo example-org/ExampleApp --project 1

# 2. Many cheap passes against the saved plan (repeat until "nothing left to do"):
python3 ~/.claude/scripts/priority_backfill.py backfill-priority --apply \
    --owner example-org --repo example-org/ExampleApp --project 1 \
    --from-plan ~/.claude/.board_state/plan_backfill-priority_<timestamp>.jsonl
```

`plan --for <subcommand>` runs the SAME candidate-computation functions (`plan_backfill`/
`plan_reset_ready`) the old full-read path always used — identical mapping, floor-fold, conflict,
unmapped, foreign-repo, and truncation-refusal rules, never a fork — and writes
`~/.claude/.board_state/plan_<for>_<UTC-timestamp>.jsonl`: a header row (`kind`, `for`, owner, repo,
project, `created_at`, per-disposition counts, this script's own sha256) followed by one row per
candidate write (issue, field, old_value, new_value, disposition). It writes nothing to GitHub.

`backfill-priority --from-plan <file>` / `reset-ready --from-plan <file>` then run with **zero**
board-wide reads:

1. The plan header is validated: `--for` must match the subcommand being run, and owner/repo/project
   must match the plan's own header — a mismatch refuses (exit 1).
2. **A plan older than 24 hours is refused** (exit 1) — re-run `plan` to get a fresh one. The board
   moves in ways a stale plan cannot know about.
3. **Every candidate row is validated, and the header's `rows_sha256` integrity hash is checked**
   (2026-09-20 fix round, B3 — see ROW VALIDATION + INTEGRITY below) — a single bad row, or any
   post-write edit to the rows, refuses the WHOLE file before anything is offered for a write.
4. Candidates already written are determined by reading this script's own existing per-write append
   logs (the same logs `reverse` reads): a candidate whose latest outcome is
   `ok`/`comment-failed`/`comment-repaired` is done and skipped; one with an intent row but no
   outcome row at all is INDETERMINATE — skipped and listed by issue number, never silently
   re-attempted, exactly as `reverse` already treats that state. A candidate whose latest recorded
   outcome is any `skipped-*` kind (see below) is re-offered on the NEXT pass once, then — after 2
   total `skipped-*` outcomes — excluded PERMANENTLY until a fresh `plan` is cut (see
   PERMANENTLY-SKIPPED below).
5. The next candidates are taken, in the plan's own order, up to `--limit` (hard max still 40)
   genuine WRITES — a `skipped-*` outcome does NOT consume a `--limit` slot (see LIVE FIELD CHECK
   below for why), though the number of live checks performed in one pass is separately bounded so a
   plan dominated by skips can never turn one pass into an unbounded scan.
6. **An exclusive, non-blocking file lock is held for the duration of the pass** (2026-09-20 fix
   round, B4 — see LOCKING below), so two concurrent `--apply` passes against the same board can
   never double-write or blow the 40-write cap between them.
7. **Immediately before writing each one**, the script performs ONE per-issue GraphQL read of that
   item's LIVE state (the "live field check" — see below; ESTIMATE, not yet measured live — see
   Budget awareness) and classifies it (see LIVE FIELD CHECK below for the full decision order and
   every `skipped-*` outcome this can produce). Only when the issue is confirmed OPEN, still on THIS
   project, under the SAME item id the plan recorded, the live read was NOT truncated, and the live
   field value equals the plan row's `old_value` does the write proceed — exactly as a normal
   `--apply` write (same `gh_issue.sh transition` call, same corrective comment, same logging, same
   `--delay` pacing). Any other outcome is a SKIP, never a write, and never silently retried as if it
   had succeeded.

**What the per-issue check verifies, precisely (corrected 2026-09-20 fix round — the prior wording
here, "preserves the exact same safety property," did not say WHAT it checks and a first version
of the mechanism collapsed five different "I don't know" conditions into the same result as "field is
genuinely empty," making the claim false until fixed — see LIVE FIELD CHECK below for the full
story):** a candidate write proceeds ONLY when the live read positively confirms ALL of — the issue
is still OPEN; the project item is still found on THIS project (not removed, not on a different
project); the live item id still matches what the plan recorded (not removed-and-re-added since);
the read was not a suspected truncation; AND the live field value equals the plan row's recorded
`old_value`. A stale OR TAMPERED plan can PROPOSE a write, but it can never blindly EXECUTE one
against a board state the live check cannot positively confirm — this is what makes it safe to run
many cheap passes against one board-wide read instead of re-reading the whole board every time. A
`--from-plan` DRY RUN performs the same per-issue live reads and writes nothing, so its preview is
exactly as accurate as the real `--apply` pass would be.

### ROW VALIDATION + INTEGRITY (B3, 2026-09-20 fix round)

A plan file is written by this script but READ from disk as untrusted input on every `--from-plan`
run — a hand-edit, a merge artifact, or deliberate tampering must never be able to make `--from-plan`
write an arbitrary value to an arbitrary field on an arbitrary issue. Two independent layers:

1. **The header carries a `rows_sha256`** — a SHA-256 over the canonical serialization of every
   candidate row, computed by `plan` at write time and RECOMPUTED and compared by `load_plan_file` on
   every read. A mismatch refuses the whole file. **This catches an ACCIDENTAL edit or casual
   tampering with the rows. It does NOT defend against an adversary who can also rewrite the header's
   own `rows_sha256` alongside the rows** — state this plainly, never soften it.
2. **Every candidate row is validated against the exact invariants a genuine `plan` output always
   satisfies** — checked BOTH when the plan is loaded (refusing the whole file, naming the row number
   and the reason, on the first violation) AND a second time immediately before each individual write
   (mirroring `restore_to_empty`'s own "checked at the actual write call, never just trusted from the
   caller" precedent): `field` is exactly `Priority` for a `backfill-priority` plan or exactly
   `Status` for a `reset-ready` plan, never the other; `new_value` is a real Priority option or
   exactly `Backlog`; `old_value` is `None` (Priority) or a real Ready status (Status); `issue` is a
   positive `int` (a `bool`, `float`, or numeric string is rejected, never coerced); `repo`, when
   present on the row, matches `--repo`; and no `(repo, issue)` pair repeats.

Row validation is what bounds the damage even if BOTH layers are defeated (a fully forged plan,
rows and header both rewritten to agree): the worst it can make this script do is set a valid
Priority value on an open, on-project, empty-Priority issue in `--repo`, or move an open Ready item
to Backlog — i.e. only writes this script is approved to make anyway, and the live field check
(above) still verifies that candidate independently before writing it.

### LIVE FIELD CHECK (also used by `reverse`)

`reverse`'s candidate set already comes from the LOG it is given, never from the board — so it never
needed a full board read either, and now uses the same per-issue live field check `--from-plan` uses,
in place of `gh project item-list`.

**Root cause of the 2026-09-20 fix round (B1/B2):** the first version of this check resolved a live
project-item id and field value as a bare `(item_id, value)` pair. That pair collapsed FIVE genuinely
different conditions into the identical `(None, None)` result: the field is genuinely empty; the item
is not on THIS project; the issue is on no project at all; the GraphQL `node` came back null (a
deleted issue); or the query's `projectItems(first: 50)` page came back full with no match, meaning
the real item might be sitting past the page boundary (a suspected truncation). A Priority candidate
row's `old_value` is always `None`, so ALL FIVE compared equal to it — every one of those "I don't
know" conditions looked identical to "field is empty, safe to write." Executed live under this
module's own test harness: a write landed on an issue that had been REMOVED from the board entirely,
and on issues CLOSED since the plan was cut (both subcommands). The fix: the live check now returns a
`LiveField` result — `found`, `item_id`, `value`, `is_open`, `truncated` — as SEPARATE fields, never
collapsed, and the caller checks `found`/`is_open`/`truncated` FIRST, reading `value` only once all
three positively confirm the read is trustworthy.

The query (modeled directly on `gh_issue.sh`'s own item-id resolution, `gh_issue.sh:334`, extended
with `fieldValueByName` so one round trip returns both the project-item id and the field's current
value):

```graphql
query($id: ID!, $field: String!) {
  node(id: $id) {
    ... on Issue {
      projectItems(first: 50) {
        nodes {
          id
          project { id }
          fieldValueByName(name: $field) {
            ... on ProjectV2ItemFieldSingleSelectValue { name }
            ... on ProjectV2ItemFieldTextValue { text }
          }
        }
      }
    }
  }
}
```

`$id` is the issue's node id, resolved via one `gh issue view <num> --json id,url,state` call first
(the `state` field is what B2's OPEN/CLOSED check reads, at zero extra API calls — added in this same
fix round); the result is filtered client-side to the node whose `project.id` matches the run's
`--project` (mirroring gh_issue.sh's own filter — a bare issue number can sit on more than one
board). A `data`+`errors` partial GraphQL response (HTTP 200 with both keys present) is raised as a
read failure, never silently treated as trustworthy data (finding 11 of the fix round).

**Every `skipped-*` outcome this check can produce**, checked in this order (truncation and
not-found first, since an item that isn't found has no meaningful open state to report; open-state
before item-id, since a more specific "closed" message is more useful than a coincidental id
mismatch on a closed issue; item-id before the value comparison, since a changed item id makes the
value comparison meaningless regardless of what it happens to read):

| Outcome | Meaning | Never treated as |
|---|---|---|
| `skipped-live-read-truncated` | the query returned a full page (50 nodes) and none matched this project — the real match may be past the page boundary | "not found" or "found, value as seen" |
| `skipped-not-on-board` | no matching project item on THIS project, the issue is on no project, or `node` was null | "field is empty" |
| `skipped-not-open` | the issue's live state is not `OPEN` | "field is empty" or "changed-since-plan" |
| `skipped-item-id-changed` | the live project-item id differs from the plan row's own `item_id` (removed and re-added since the plan was cut) | a value comparison worth trusting |
| `skipped-changed-since-plan` | the live field value differs from the plan row's `old_value`, and everything above was clear | "the board still matches the plan" |

**Cost estimate — NOT YET MEASURED LIVE against real GitHub (label this honestly wherever it
appears):** ~1 point for the `gh issue view` resolve + ~1 point for the GraphQL query itself (a
single-node lookup returning at most 50 project-item nodes) — **roughly 2 points per candidate
CHECKED** (ESTIMATE), whether it ends up written or skipped, regardless of which `skipped-*` kind.
The `fieldValueByName` query shape itself is **UNVERIFIED end-to-end** against a real project item —
confirmed only by live GraphQL schema introspection (`ProjectV2Item.fieldValueByName` and its two
fragment types genuinely exist), never exercised against a real board (this subsystem was built and
fix-rounded entirely under the fake-`gh` test harness, per the standing rule never to run it against
the real board — not even dry-run).

### PERMANENTLY-SKIPPED (non-blocking item 6, 2026-09-20 fix round)

A `skipped-*` candidate is re-offered on the very next pass **at most once more** (the underlying
condition may have been transient, or a human may have corrected it — e.g. reopened a closed issue).
After **2 total** `skipped-*` outcomes recorded for the same (issue, field) across every log this
subcommand has ever written, that candidate is excluded from `to_check` PERMANENTLY and reported
under its own heading, "permanently skipped — re-run `plan` to reconsider," naming its last skip
reason. There is no way to force a permanently-skipped candidate back into consideration except
cutting a fresh `plan` (which starts its own, independent skip count for every candidate).

### LOCKING (B4, 2026-09-20 fix round)

Two concurrent `--apply` passes against the SAME board (same owner/repo/project) — `--from-plan` or
the legacy full-read path, any of `backfill-priority`/`reset-ready`/`reverse` — could previously both
read the same "not yet done" state and both write the same candidates: executed live under this
module's own harness, two processes racing the same 6-candidate plan at `--limit 6` produced 9
writes, three issues written twice, silently breaching the per-pass cap in aggregate. Every `--apply`
run now holds an EXCLUSIVE, NON-BLOCKING `fcntl.flock` on
`~/.claude/.board_state/.lock_<owner>_<repo-slug>_<project>` for the duration of the run — one board,
one writer, at a time, regardless of which plan file or log is in play. If another process already
holds the lock, the run refuses IMMEDIATELY (exit 1, naming the lockfile) — it never blocks or waits.
The OS releases the lock automatically on process exit or death (crash, `SIGKILL`, anything) — there
is no stale-lock file to clean up and no separate recovery procedure; just retry once the other pass
finishes. Dry runs never take this lock (they write nothing, so there is nothing to serialize).

### Budget awareness (`--min-budget`)

**`gh api rate_limit` MISREPORTS the GraphQL budget as a constant 5000/5000 regardless of actual
usage** (measured live, 2026-09-20) — this script never uses it. The real remaining budget is read
via:

```
gh api graphql -f query='query{rateLimit{remaining resetAt}}'
```

Every subcommand queries this BEFORE any other read, and `--min-budget N` refuses (exit 4, with
`remaining`/`resetAt` in the message) when the live remaining is below N. Defaults: **2500** for any
subcommand doing a full board read (`plan`, the legacy no-`--from-plan` paths); **300** for
`--from-plan` and for `reverse` (2026-09-20 fix round, non-blocking item 8 — `reverse` no longer
performs a full board read either, so its default floor was moved off the full-read default it
inherited before this round). `--min-budget 0` deliberately WAIVES the gate entirely — printing an
explicit `budget gate WAIVED (--min-budget 0)` line so a waived run is never silently indistinguishable
from a normally-passing one — and a negative value is rejected outright at the argument parser
(exit 1, never a silently-accepted nonsense floor). If the budget query itself fails (network error,
unparsable output, non-zero exit), that is treated as a rate-limit abort BEFORE any write —
fail-closed, never "budget unknown, proceed anyway." Every run also queries the budget a SECOND time
at the end and prints one line:

```
GraphQL cost of this run: <n> points (remaining <x>, resets <t>)
```

— the script's own self-measurement of the exact problem this subsystem exists to fix. Like the
per-candidate cost above, these numbers are the script's OWN live reading of `rateLimit`, not an
estimate — this line IS measured, even though the ~2-points-per-candidate figure it's derived from is
not yet independently confirmed against a real GitHub project board.

### First real run — a checklist

Before ever running this against the real board with `--apply`, in order:

1. `plan --for <subcommand> ...` (no `--apply` exists for `plan` — it never writes).
2. Read the plan file's first few rows BY HAND (`head -5 <plan file>`) — do the issue numbers,
   old/new values, and dispositions look right for what you expect this batch to do?
3. Pick one candidate from the file and check it in the browser — does the live issue's Priority
   (or Status) genuinely match what the plan row's `old_value` claims?
4. `<subcommand> --from-plan <file>` WITHOUT `--apply` (the default dry run) — does the preview match
   what you expect, including zero unexpected `skipped-*` rows for issues you know are fine?
5. Confirm the printed "GraphQL cost of this run" line is single digits or low tens of points, NOT
   anywhere near the ~1,834-point full-read figure — if it's high, something fell back to a full read.
6. `<subcommand> --from-plan <file> --apply --limit 1` — one single write, the smallest possible
   blast radius.
7. Verify the ONE field that should have changed changed, and that nothing else moved (e.g. a
   `backfill-priority` write must never have touched Status).
8. Tail the day's append log (`~/.claude/.board_state/<subcommand>_<date>.jsonl`) and confirm both an
   intent row and an `"outcome": "ok"` row landed for that one issue.
9. Dry-run `reverse --log <that log file>` once, to confirm you know how to undo this batch before
   running it at scale.
Only after all nine steps look right, widen `--limit` and run the remaining passes.

## What `.board_state/` holds

`~/.claude/.board_state/` is per-machine, untracked state for `priority_backfill.py`'s writes
against a GitHub Project board. Nothing in this directory is committed; it is the durable record of
what the script has actually changed, so a run can be audited or reversed later.

Four kinds of file live there, all newline-delimited JSON (`.jsonl`) except the lockfiles:

- **`backfill-priority_*.jsonl` / `reset-ready_*.jsonl` / `reverse_*.jsonl`** — the AUTHORITATIVE
  per-write append log. Each real write appends TWO rows: a write-INTENT row (issue, field,
  old_value, new_value, its own timestamp) written and `fsync`'d immediately BEFORE the write is
  attempted, followed by an OUTCOME row (`"outcome": "ok"` / `"transition-failed"` /
  `"comment-failed"` / `"comment-repaired"`) appended immediately after. This is what `reverse`
  reads — it consumes only the LATEST outcome per (issue, field), and only `ok`/`comment-failed`/
  `comment-repaired` outcomes are treated as "this field write actually landed and is reversible."
  A `transition-failed` outcome means nothing was written to the board; reversing it would be
  writing a value that was never really set.
- **`planned_<subcommand>_*.jsonl`** — a purely INFORMATIONAL batch-level preview written once at
  the start of an `--apply` run, before the first real write. Every row carries a `run_id` (a short
  per-process token, generated fresh each time the script runs) so multiple `--apply` runs writing
  into the same day's preview file can be told apart. `reverse` never reads these files — only the
  per-write append log above — so a row that was merely PLANNED but never actually attempted
  (because an earlier row in the same batch failed first) can never be mistaken for a real write
  during a reversal.
- **`plan_<for>_<UTC-timestamp>.jsonl`** — the reusable plan file written by `plan --for <subcommand>`
  (see above): a header row (including the `rows_sha256` integrity hash — see ROW VALIDATION +
  INTEGRITY above) plus one candidate row per prospective write. Read by `backfill-priority
  --from-plan`/`reset-ready --from-plan`, which re-validate each candidate against a fresh per-issue
  live read before ever writing it — a plan file on its own authorizes nothing.
- **`.lock_<owner>_<repo-slug>_<project>`** (2026-09-20 fix round, B4 — see LOCKING above) — NOT
  JSONL; an empty or near-empty file that exists purely to be `flock`'d. One per board. Never carries
  meaningful content, never read by anything, and safe to delete by hand if it is ever orphaned with
  nothing holding it (an `flock` attempt on an unheld lockfile always succeeds immediately, so an
  orphaned lockfile is inert, not a hazard).

## The four subcommands

- **`plan --for backfill-priority|reset-ready --owner O --repo OWNER/NAME --project N`** — the ONE
  full board read; writes a reusable plan file; writes NOTHING to GitHub (see above).
- **`backfill-priority --owner O --repo OWNER/NAME --project N`** — writes the Priority field from
  a priority-shaped label, for every open issue in `--repo` whose Priority field is empty. Add
  `--from-plan <file>` to run against a saved plan instead of a full board read.
- **`reset-ready --owner O --repo OWNER/NAME --project N`** — moves every open `Ready #1`/`Ready #2`
  item in `--repo` back to `Backlog`. Also accepts `--from-plan <file>`.
- **`reverse --log <file>`** — replays either log above backwards; never performs a full board read
  (uses the same per-issue live field check `--from-plan` uses).

`backfill-priority`/`reset-ready`/`reverse` are dry-run by default (`--apply` performs writes, capped
at `--limit`, default and hard max 40 per invocation) and accept `--delay SECONDS` (default 1.0)
slept between writes to avoid firing a burst of back-to-back `gh_issue.sh` calls. All four
subcommands accept `--min-budget N` (see Budget awareness above); `plan` has no `--apply`/`--dry-run`/
`--limit`/`--delay` — it never writes to GitHub at all.

## Reverse's three-way decision — never a blind "already reversed?" check

An earlier version of `reverse` asked only one question per row: does the live value already equal
`old_value`? If not, it wrote `old_value` unconditionally. That silently clobbers a deliberate human
edit made on the board AFTER the forward write landed — proven live both ways: `backfill-priority`
wrote P1, the operator hand-set P0, a naive `reverse` cleared it back to empty anyway; `reset-ready`
moved an issue to `Backlog`, the operator moved it to `In progress`, a naive `reverse` put it back in
`Ready #1` anyway. Since this tool exists FOR an operator who will be hand-picking on this exact
board, that is not an acceptable failure mode.

`reverse` now re-reads the LIVE VALUE of each candidate row's own (issue, field) — one per-issue
live field check per candidate (2026-09-20; see "`plan` / `--from-plan`" above — never a full `gh
project item-list` board read, since `reverse`'s candidates already come from the log it is given)
— before planning any writes, and classifies every candidate row into exactly one of three outcomes:

- **live value == the row's `new_value`** (this script's own write is still there) → reverse it.
- **live value == the row's `old_value`** (nothing to do) → skip, silently. This is what makes
  `reverse` resumable across multiple runs over a log bigger than one `--limit` batch: a second run
  naturally picks up wherever the first one left off, because the rows it already reversed no longer
  look like candidates.
- **live value == neither** ("changed-since-write") → REFUSED by default, listed by issue number.
  Only overwritten when that issue's number is passed explicitly via `--force-changed <issue#>
  [<issue#> ...]` — never a blanket "force everything", always named one at a time.

A write-intent row with **no recorded outcome at all** (a crash between the log write and the
outcome write — see the per-write log format above) is INDETERMINATE: reported by issue number,
never silently dropped, and only classified against the live board (same three-way logic) when
`--include-indeterminate` is passed.

**`unreadable` — a FOURTH bucket, distinct from all three above (2026-09-20 fix round, B2).** If the
live field check for a candidate comes back `skipped-not-on-board` or `skipped-live-read-truncated`
(see LIVE FIELD CHECK above), that row is NEVER passed into the three-way classification at all — it
is pulled out first and reported separately as `unreadable`, since the classification above only ever
makes sense against a value that was genuinely read. **A CLOSED issue is deliberately NOT pulled
into `unreadable`** — undoing a write must never be blocked merely because the issue was closed
afterwards, so a closed issue's live value still flows into the normal three-way classification above
exactly as an open issue's would; closing an issue, by itself, never prevents (or forces) its own
reversal.

## Restore-to-empty (the one non-`gh_issue.sh` write)

Every `backfill-priority` row's `old_value` is empty (that is the entire premise of a backfill — the
field had no prior value), and `gh_issue.sh transition` has no verb for clearing a field back to
empty. `reverse` handles this ONE case by calling `gh project item-edit --id <item-id> --field-id
<field-id> --project-id <project-id> --clear` directly — resolving the project id and field id via
its OWN separate `gh project view` + `gh project field-list` calls (`_resolve_project_id` /
`_resolve_field_id` in `priority_backfill.py`, unchanged by the #5827 fix described next — this
script's own resolution never went through `gh_issue.sh` and is out of that fix's scope). **`gh_issue.sh
transition` itself no longer resolves the project/field ids this way** (#5827,
2026-09-20): the old `gh project view` + `gh project field-list` two-call sequence measured ~101
GraphQL points per call (`field-list` alone — every field, every single-select option on the whole
board, just to find one field's id) — ~105-113 points per `transition --project` write in total —
against the account's 5,000-points/hour budget shared by every session on this machine. It is
replaced by ONE targeted GraphQL query (`repositoryOwner(login:...){ ... on ProjectV2Owner {
projectV2(number:...){ id field(name:...){...} fields(first:100){totalCount nodes{...}} } } }`,
`_resolve_project_and_field` in `gh_issue.sh`) that resolves the SAME project id, field id, field
type, and options (plus the duplicate-field-name ambiguity check f028962 added) at a MEASURED live
cost of ~1 point. So a `gh_issue.sh transition --project` write is now ~2-4 points total (the field
query + the pre-existing issue-view and item-id-lookup calls it already made), down from the
~105-113 measured pre-fix — the post-fix END-TO-END total (including the `item-edit` write itself)
is UNVERIFIED against a real write, since this subsystem is built and tested entirely under the
fake-`gh` harness per the standing rule never to run it against the real board. This doc's own "live
field check" cost estimate above (~2 points per candidate CHECKED) is a DIFFERENT read (an
`issue view` + a `fieldValueByName` GraphQL query, made by `priority_backfill.py` itself before each
write) and is UNCHANGED by this fix — do not conflate the two.

The **item id is always read fresh from the LIVE board** for
the row's `(repo, issue number)` — never the id recorded in the log — so a since-recreated or
since-moved item can never be cleared by a stale id; if the issue is no longer present on the live
board at all, that row is refused rather than guessed at. `restore_to_empty` also REFUSES outright
for any row whose `field` is not `Priority` (a `reset-ready`/Status row should never have an empty
`old_value`, and this is checked at the actual write call, not just trusted from the caller).

This is the ONLY write in the whole script that bypasses `gh_issue.sh`, and it is scoped as narrowly
as possible: called only from `reverse`, only for a row whose recorded `old_value` is empty AND
whose field is Priority, resolved against the live board, and it can only clear the one named field
on the one named item — **it is unconditionally destructive of whatever value is currently there
when it runs** (there is no "changed-since-write" softening once a row reaches this path — the
three-way classification above is what decides WHETHER a row reaches it at all; `--force-changed`
on an empty-`old_value` row means the clear proceeds even though the live value matched neither old
nor new).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success — including a no-op dry run |
| 1 | a field write (transition) failed, an argument error, a missing/malformed log, a truncated read, the CWD-repo mismatch refusal, or `reverse` refusing to reverse a `reverse` log (see below) |
| 3 | PARTIAL — a field write succeeded but its corrective comment failed; `backfill-priority --apply` only |
| 4 | a READ looked rate-limited; the run aborted before any write was attempted — safely resumable once the quota recovers. Also returned by a `--min-budget` refusal (live remaining GraphQL budget too low) and by a failure of the budget query itself (fail-closed) |

**There is no exit code 2.** `argparse`'s native behavior (a missing required flag, `--apply` and
`--dry-run` both given, a non-integer `--project`, etc.) normally calls `sys.exit(2)` directly,
bypassing this script's own error handling. `priority_backfill.py` installs a custom
`ArgumentParser` whose `error()` raises the same error class every other failure in this script
raises, so every argument error — parse-time or not — is normalized to exit code 1. "1 means an
argument error, among other things" is true without exception.

A `comment-failed` row (exit 3) is repaired automatically on the NEXT run of `backfill-priority`,
before it plans any new writes — the corrective comment is re-attempted, but the transition itself
is never re-run for that row (the field was already correctly written).

## Cross-repo safety

A single Project board can hold items from more than one repository. `--repo OWNER/NAME` is
required on every read-then-write subcommand; every candidate is keyed on `(repo, issue number)`,
not the bare number alone, and any item belonging to a different repository is skipped and reported
under "foreign-repo (skipped)". Before any `--apply` write, the script also verifies the current
working directory's own git remote resolves to the same `--repo` (`gh repo view --json
nameWithOwner`) and refuses otherwise — `gh_issue.sh transition` resolves a bare issue number
against the CWD's git remote implicitly, so this check closes the loop rather than trusting that
binding silently.

## Pacing and rate limits

Every read's output is scanned for rate-limit-shaped text (`"rate limit"`, `"RATE_LIMIT"`,
`"secondary rate"`, and the misleading `"unknown owner type"` string `gh project` has been observed
to emit for the same underlying condition — see the 2026-09-20 session history in project memory). A
read that looks rate-limited aborts the ENTIRE run before any write is attempted (exit 4) — the
script never proceeds on a partial or empty item list.

**`--delay SECONDS` only paces WITHIN one `--apply` pass** — it does nothing between successive
passes, and successive passes are the REAL usage shape for anything bigger than 40 items: the
plan's own measured counts are roughly 7 passes to fully empty `Ready #1`/`Ready #2` back to
`Backlog` (247 items) and roughly 8 passes for a full Priority backfill (~300 items). GitHub's
secondary GraphQL rate limit is a SHARED, machine-wide budget, not scoped to this script or this
session — **pause between `--apply` passes** (a minute or more is reasonable) rather than firing the
next one immediately after the previous one finishes, especially when other sessions may also be
making `gh` calls. Any `--apply` pass that still has rows remaining prints a one-line reminder
saying so before it exits. **Run the passes via `--from-plan`** (see above) — a `--from-plan` pass
costs roughly 2 points per candidate checked (ESTIMATE, not yet measured live) instead of the
1,834-point (measured) full board read every
legacy (no-`--from-plan`) pass performs, which is what actually makes firing ~15 passes in one
evening affordable at all.

## Rollback

**Not every write this script makes is reversible without qualification** — read this section
before assuming `reverse` will always cleanly undo a run:

- A row whose latest recorded outcome is `ok`, `comment-failed`, or `comment-repaired` — i.e. the
  field write itself genuinely landed — IS reversible, PROVIDED the live board still shows this
  script's own written value (`new_value`). If a human (or anything else) changed that field again
  since the write landed, `reverse` REFUSES that row by default (`changed-since-write`) rather than
  overwriting a deliberate edit — see "Reverse's three-way decision" above. It is only overwritten
  when its issue number is explicitly named via `--force-changed`, and `--force-changed` on such a
  row is **unconditionally destructive** of whatever value is currently there.
- A row whose latest outcome is `transition-failed` was never actually written to the board — there
  is nothing to reverse, and `reverse` correctly excludes it.
- A row with NO recorded outcome at all (INDETERMINATE) is never silently reversed; it is reported,
  and only acted on with `--include-indeterminate`, using the same live-board classification (and
  the same `changed-since-write` protection) as every other row.
- **`reverse` itself refuses to be reversed.** A `reverse` log's own rows are never valid input to a
  second `reverse` call — if you need to undo a `reverse` run, reverse the ORIGINAL
  `backfill-priority`/`reset-ready` log again instead (the board should be back at that log's
  `old_value`, so a second pass over the original log re-applies the original write cleanly).
- **A row the live check cannot positively read (`unreadable`) is never written and never silently
  skipped over** (2026-09-20 fix round, B2) — it is listed by issue number and reason, distinct from
  `changed-since-write`, so an operator can tell "this needs a human look" apart from "this was
  legitimately edited since." A closed issue is NOT `unreadable` on its own — see "Reverse's
  three-way decision" above.

To attempt a reversal:

```
python3 ~/.claude/scripts/priority_backfill.py reverse --log ~/.claude/.board_state/<subcommand>_<date>.jsonl --apply
```

Run it dry-run first (the default) to see exactly what it proposes, including any
`changed-since-write` rows it will refuse. If the log is larger than one `--limit` batch, re-run the
same command again after the first batch lands (with a pause in between — see Pacing above) — it
will pick up where it left off (see "Reverse's three-way decision" above). `reverse` never performs
a full board read (see above), so repeated passes are already cheap without needing a `plan` file of
their own. Nothing is ever deleted from `.board_state/` by this script; the logs are the permanent
record of every write it has ever made.
