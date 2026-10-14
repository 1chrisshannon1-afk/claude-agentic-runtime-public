#!/usr/bin/env python3
"""priority_backfill — board-metadata backfill + reset helper (dev runtime, product-agnostic).

WHY THIS EXISTS
----------------
`plan_lane_control_adoption_master_2026_09_20.md` §2 Phase A / finding F12: 74% of
open GitHub Project items have an empty Priority FIELD even though 67% carry a
priority LABEL, and 239 items sit in `Ready #1` (meant to be the operator's short,
hand-picked queue) with no signal distinguishing an operator pick from an agent
move. This script performs both narrow, mechanical, reversible board-metadata
fixes the plan calls for, and nothing else: it never creates, closes, or edits
issue bodies/labels, and it never touches the Status options list.

This is a PRODUCT-AGNOSTIC runtime script (stdlib only): the repo owner/name and
project number are always caller-supplied arguments, never hardcoded, so it can
run against any GitHub Project on this machine.

SUBCOMMANDS
-----------
  plan --for backfill-priority|reset-ready --owner O --repo OWNER/NAME
       --project N [--min-budget N]
      Performs the ONE full board read (`gh project item-list` + `gh issue
      list`) and computes candidates via the SAME `plan_backfill`/
      `plan_reset_ready` functions `backfill-priority`/`reset-ready` use —
      identical mapping, floor-fold, conflict, unmapped, foreign-repo, and
      truncation-refusal rules, never a fork. Writes
      `~/.claude/.board_state/plan_<for>_<UTC timestamp>.jsonl`: a header row
      (`kind: "plan-header"`, `for`, owner, repo, project, `created_at`,
      per-disposition candidate counts, this script's own sha256) followed by
      one candidate row per write the corresponding `--apply` run would make
      (repo, issue, item_id, field, old_value, new_value, disposition).
      Prints the plan path and the same human summary the dry-run prints
      today. WRITES NOTHING TO GITHUB — this is a read-only planning pass,
      meant to be run ONCE, with `backfill-priority --from-plan`/
      `reset-ready --from-plan` consuming it across many cheap passes
      afterwards (see FROM-PLAN below) — this is what turns "1,834 points per
      invocation, every pass" into "1,834 points once, then ~1 point per
      write" (measured 2026-09-20; see FROM-PLAN).

  backfill-priority --owner O --repo OWNER/NAME --project N [--apply] [--dry-run]
                     [--limit 40] [--delay SECONDS] [--from-plan FILE]
      For every OPEN issue IN --repo on the project whose Priority FIELD is
      empty and which carries a priority-shaped LABEL, write the field via
      `gh_issue.sh transition <n> --status <value> --project N --owner O
      --field Priority`, followed by a corrective `gh_issue.sh comment`
      (gh_issue.sh's own transition auto-comment hardcodes the word "Status"
      even when --field Priority is used — see gh_issue.sh:204, `_do_transition`
      — so this script always posts a follow-up comment naming Priority
      explicitly after every successful Priority write). Items belonging to
      any OTHER repository on the same project board are skipped and reported
      under `foreign-repo (skipped)`, never touched (see B2 in the module
      history below).

  reset-ready --owner O --repo OWNER/NAME --project N [--apply] [--dry-run]
              [--limit 40] [--delay SECONDS]
      Moves every OPEN item IN --repo whose Status is exactly "Ready #1" or
      "Ready #2" back to "Backlog" (operator-approved reset, card [97]/plan
      §11 item 3 — "Empty your Ready #1 list ... back into the backlog").
      Nothing is deleted.

  reverse --log <file> [--apply] [--dry-run] [--limit 40] [--delay SECONDS]
           [--force-changed ISSUE# [ISSUE# ...]] [--include-indeterminate]
      Replays a log written by either subcommand above BACKWARDS: for each
      row whose field write actually succeeded (latest outcome `ok`,
      `comment-failed`, or `comment-repaired` — see B1/B4 below), writes
      `old_value` back to `field` on `issue` — REVERSE is not a blind replay,
      it is NEVER reversed against a `reverse` log itself (refused outright,
      see cmd_reverse). Before planning, re-reads the LIVE VALUE of each
      candidate row's own (issue, field) — one LIVE FIELD CHECK GraphQL call
      per candidate (see LIVE FIELD CHECK above), NOT a full `gh project
      item-list` board read (2026-09-20 — `reverse`'s candidate set already
      comes from the LOG it is given, never from the board, so a full-board
      read was always more than this needed; replaced to close the same
      1,834-point-per-invocation cost the FROM-PLAN mechanism above closes
      for the two forward subcommands) — and classifies each candidate row
      into exactly one of three outcomes (see `classify_reverse_row` —
      round-2 B2, NOT a binary "already reversed?" check, which was proven
      live to clobber a deliberate human edit made on the board after the
      forward write landed):
        - live value == the row's `new_value` (this script's own write is
          still there) -> reverse it.
        - live value == the row's `old_value` (nothing to do) -> skip; this
          is what makes reverse resumable across multiple runs over a log
          bigger than one `--limit` batch (B3).
        - live value == neither -> a human (or something else) touched this
          field since the write landed. Refused by default, listed under
          "changed-since-write (skipped)"; only overwritten when its issue
          number is named explicitly via `--force-changed`.
      A write-intent row with NO recorded outcome at all (a crash between
      the log write and the outcome row — see B1) is INDETERMINATE, never
      silently dropped: reported by name, and only classified against the
      live board (same three-way logic above) when `--include-indeterminate`
      is passed — never automatically, since whether the write landed is
      genuinely unknown without it.
      A row whose `old_value` was empty (every `backfill-priority` row — the
      field had no prior value) is restored to empty via `gh project
      item-edit --clear`, using the LIVE item id for (repo, issue) — never a
      stale id recorded in the log (round-2 item 5) — the ONE write in this
      entire script that does not go through `gh_issue.sh`, because
      `gh_issue.sh transition` has no "unset a field" verb; see
      `restore_to_empty` below for why this is safe and narrowly scoped, and
      why it refuses outright for any row whose `field` is not `Priority`
      (round-2 item 4). Dry-run by default, identical semantics to the two
      subcommands above.

Every subcommand is DRY-RUN BY DEFAULT: it prints every planned write and
touches nothing. `--dry-run` is also accepted explicitly (mutually exclusive
with `--apply`) for callers that want to say so out loud; omitting both flags
is identical to passing `--dry-run`. `--apply` performs at most `--limit`
mutations (default 40, HARD MAX 40 — the plan's own per-pass cap) and reports
how many remain.

FROM-PLAN (2026-09-20 — the reason this subsystem exists: a full board read
via `gh project item-list` on ~1,500 items plus the `gh issue list` open-set
read cost a MEASURED 1,834 GraphQL points out of the account's 5,000/hour
budget, a budget SHARED by every session on the machine — running the ~15
`--apply` passes the approved ~295-Priority/~247-Status write plan needs, the
OLD way (a full read every pass), would cost ~27,000 points, more than five
times the hourly budget, and exhausted it twice in one evening. `--from-plan
<file>` on `backfill-priority`/`reset-ready` eliminates the board-wide read
entirely for every pass after the first:
    1. The plan file's header is validated: `--for` must match the
       subcommand being run, and owner/repo/project must match the plan's
       own header — any mismatch refuses (exit 1) rather than silently
       running a stale or wrong-board plan.
    2. A plan older than 24 hours is refused (exit 1), with a message to
       re-run `plan` — the board moves in ways a day-old plan cannot know
       about (issues closed, fields hand-edited, items removed).
    3. The candidates already WRITTEN are determined by reading this
       script's own existing per-write append logs (the SAME logs `reverse`
       reads) for the plan's `--for` subcommand: a candidate with a latest
       outcome of `ok`/`comment-failed`/`comment-repaired` is done and
       skipped; a candidate with an intent row but NO outcome row at all is
       INDETERMINATE — skipped and listed by issue number, exactly as
       `reverse` already treats that state (never silently re-attempted,
       since whether the earlier write landed is genuinely unknown). A
       candidate whose latest recorded outcome is `skipped-*` of any kind
       (see LIVE FIELD CHECK below) is re-offered on the NEXT pass at most
       ONCE MORE (the underlying condition may have been transient or
       human-corrected); after TWO skips of any `skipped-*` kind for the
       same (issue, field), it is excluded from `to_check` permanently and
       reported separately as "permanently skipped — re-run `plan` to
       reconsider" — never silently retried forever, and never allowed to
       eat `--limit` slots indefinitely on a plan full of stale rows.
    4. The next up-to-`--limit` (hard max still 40) NOT-yet-done, not-yet-
       permanently-skipped candidates, in the plan's own recorded order, are
       taken as WRITE ATTEMPTS — a `skipped-*` outcome does not count toward
       `--limit` (a pass fills `--limit` WRITES where possible, not
       `--limit` candidates checked), but the number of LIVE FIELD CHECKS in
       one pass is capped at 3x `--limit` so a plan dominated by skips can
       never turn one pass into an unbounded scan of the whole file.
    5. An EXCLUSIVE, NON-BLOCKING file lock (see LOCKING below) is held for
       the duration of the pass, so two concurrent `--apply` passes against
       the same board can never double-write or blow the 40-write cap
       between them.
    6. IMMEDIATELY BEFORE writing each one, this script performs ONE
       single-issue GraphQL read of that item's LIVE field value (see
       LIVE FIELD CHECK below; ~2 points, UNMEASURED — see that section) and
       classifies it against the plan row's `old_value` (and, for
       backfill-priority, the row's `item_id`):
         - the issue is OPEN, still on THIS project, the live item id
           matches the plan row's `item_id`, the read was not a suspected
           truncation, AND the live field value equals `old_value` -> the
           board is exactly as the plan assumed; write proceeds exactly as
           a normal `--apply` write (same `gh_issue.sh transition` call,
           same corrective comment for Priority, same intent-then-outcome
           logging, same `--delay` pacing).
         - ANY of those checks comes back "I don't know" or "no" — the
           issue is not OPEN, the item is not found on this project at all,
           the item id changed, the read looked truncated, or the field
           value simply differs from `old_value` — the write is SKIPPED
           with its own named `skipped-*` outcome (never conflated with
           "field is empty", which is the ONE state that authorizes a
           backfill write) and reported in the run's output. See LIVE FIELD
           CHECK for the full list of skip kinds and exactly what each one
           means.
       This per-issue check is what preserves the SAME safety property the
       full-board-read path has always had — "only ever fill an EMPTY
       Priority field on an OPEN, on-board issue" / "only move an OPEN item
       still sitting in Ready #1/#2" — without paying for a full board read
       on every pass: a stale OR TAMPERED plan can propose a write (see B3
       under ROW VALIDATION below for what a tampered plan can and cannot
       make this script do), but it can never blindly EXECUTE a write
       against a board state the live check cannot positively confirm.
    A `--from-plan` DRY RUN performs the same per-issue live reads for the
    next up-to-`--limit` not-yet-done candidates and writes nothing, so a
    dry-run preview is exactly as accurate as the real `--apply` pass would
    be, at the same live-check cost rather than a full re-read.

ROW VALIDATION + INTEGRITY (B3, 2026-09-20 fix round)
--------------------------------------------------------
A plan file is written by this script but READ from disk as untrusted input
— a hand-edit, a merge artifact, or a genuinely adversarial rewrite must
never be able to make `--from-plan` perform a write this script is not
otherwise approved to make. `load_plan_file` validates EVERY candidate row
before returning any of them, refusing the WHOLE file (naming the row number
and the reason) on the first violation of: `field` is exactly `"Priority"`
(for a `--for backfill-priority` plan) or exactly `"Status"` (for
`--for reset-ready`) and never the other; `new_value` is one of
`VALID_PRIORITIES` for a Priority row or exactly `BACKLOG_STATUS` for a
Status row; `old_value` is `None` for a Priority row or one of
`READY_STATUSES` for a Status row; `issue` is a positive `int` (a `bool`,
`float`, or numeric `str` is REJECTED, never coerced — `bool` is a
particularly sharp edge in Python, being a subtype of `int`); `repo`, when
present on the row, is case-insensitively equal to the invocation's `--repo`;
and no `(repo, issue)` pair repeats across rows. The SAME invariants are
re-checked a SECOND time at the actual write call site in
`_run_from_plan_candidates` (mirroring `restore_to_empty`'s existing
"checked at the actual write call, never just trusted from the caller"
precedent) — defense in depth, not a substitute for the load-time check.
The header additionally carries a `rows_sha256`: a SHA-256 over the
canonical (sorted-key, newline-joined) JSON serialization of every candidate
row, computed by `plan` at write time and RECOMPUTED and compared by
`load_plan_file` on every read — a mismatch refuses the whole file. State
plainly: this integrity check catches an ACCIDENTAL edit or casual
tampering with the ROWS; it does NOT defend against an adversary who can
also rewrite the header's own `rows_sha256` alongside the rows. Row
validation is what bounds the damage in THAT case — the worst a fully
forged plan (rows AND header) can make this script do is set a valid
Priority value on an open, on-project, empty-Priority issue in `--repo`, or
move an open Ready item to Backlog — i.e. only writes this script is
approved to make anyway, on a candidate the live field check still verifies
independently before writing.

LOCKING (B4, 2026-09-20 fix round)
--------------------------------------
Two concurrent `--apply` passes against the SAME board (same owner/repo/
project) — whether `--from-plan` or the legacy full-read path, and
regardless of subcommand — could previously both read the same "not yet
done" state and both write the same candidates, double-writing issues and
silently breaching the 40-write-per-pass cap in aggregate. Every `--apply`
run of `backfill-priority`, `reset-ready`, and `reverse` now holds an
EXCLUSIVE, NON-BLOCKING `fcntl.flock` on
`~/.claude/.board_state/.lock_<owner>_<repo-slug>_<project>` for the
duration of the run (one board = one writer at a time, regardless of which
plan file or log is in play). If the lock is already held, the run refuses
IMMEDIATELY (exit 1, naming the lockfile and stating another pass is
running) — it never blocks or waits. The OS releases the lock automatically
on process exit or death (including a crash or SIGKILL), so there is no
stale-lock file to clean up and no recovery procedure needed beyond letting
the holding process end. Dry runs never take this lock (they perform no
writes, so there is nothing to serialize).

LIVE FIELD CHECK (the per-issue GraphQL read `--from-plan` and `reverse` both
use in place of a full board read)
------------------------------------------------------------------------------
Modeled directly on `gh_issue.sh`'s OWN item-id resolution (`_do_transition`,
gh_issue.sh:334) — the same query shape, extended with `fieldValueByName` so
one round trip returns both the project-item id AND the field's current
value, rather than needing a second call. `gh issue view <num> --json
id,url,state` (one call, ESTIMATE — not yet measured live) resolves the
issue's node id AND its OPEN/CLOSED state in the same call the original
version only used for the node id — zero extra API calls for the state
check B2 below needs:

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

`$id` is the issue's node id; the result is filtered client-side to the node
whose `project.id` matches this run's `--project` (mirroring gh_issue.sh's
own filter) — a bare issue number can be on more than one board, and, per B2,
this script never trusts a bare number alone. Both fields this script ever
reads (Priority, Status) are `ProjectV2SingleSelectField`s, so
`ProjectV2ItemFieldSingleSelectValue.name` is the value read in practice; the
`ProjectV2ItemFieldTextValue` fragment is included defensively (a text-typed
field returns `.text` instead) rather than assumed away.

RESULT TYPE (2026-09-20 fix round, root cause of B1/B2): `fetch_live_item_field`
returns a `LiveField` named tuple (`found: bool`, `item_id: str | None`,
`value: Any`, `is_open: bool | None`, `truncated: bool`), NEVER a bare
`(item_id, value)` pair — the earlier shape collapsed FIVE genuinely
different conditions (field legitimately empty; item not on THIS project;
issue on no project at all; `node` null because the issue was deleted;
`projectItems(first: 50)` silently truncated past 50 items on one issue)
into the same `(None, None)`, which a Priority row's `old_value: None`
compares EQUAL to — so every one of those "I don't know" conditions used to
look identical to "field is genuinely empty, safe to write." They are not
the same state, and only the first is ever safe to write. The caller
(`_run_from_plan_candidates`, `cmd_reverse`) now classifies on
`LiveField.found`/`.is_open`/`.truncated` FIRST, and only reads `.value`
once all three confirm the read is trustworthy:
    - `found=False` (no matching project item for this project, issue on no
      board, or a null `node`) -> `skipped-not-on-board`, never treated as
      "empty".
    - `truncated=True` (the query returned exactly 50 project-item nodes
      and none matched this project — mirrors the truncation-refusal this
      script already applies to `fetch_project_items`/
      `fetch_open_issue_numbers`) -> `skipped-live-read-truncated`.
    - `is_open=False` (issue state is not `OPEN`) -> `skipped-not-open` —
      the legacy full-read paths have always excluded closed issues via
      `fetch_open_issue_numbers`; `--from-plan` checks it here instead,
      from the same `gh issue view` call that already resolves the node id.
    - a `data`+`errors` GraphQL response (partial data at HTTP 200) ->
      raised as a read failure, never silently treated as "empty" data.
    - for `backfill-priority` candidates specifically: the LIVE item id
      returned differs from the plan row's own `item_id` (the issue was
      removed from the project and re-added, getting a new item id, since
      the plan was cut) -> `skipped-item-id-changed`, defense in depth on
      top of the value comparison.
    - only once ALL of the above are clear does `.value == old_value`
      decide write-vs-`skipped-changed-since-plan`, exactly as before.
Estimated cost per call, ESTIMATE — NOT YET MEASURED LIVE (see BUDGET
AWARENESS): the `gh issue view` resolve (~1 point) plus the GraphQL query
itself (~1 point, a single-node lookup — GraphQL point cost is dominated by
returned object count, and this returns one issue's item list, at most 50
nodes) — roughly 2 points per candidate CHECKED, not per write attempted (a
skipped candidate of any kind costs the same ~2 points as a written one,
since the check happens before the decision). This contrasts with the
MEASURED 1,834-point full board read the `plan`/legacy paths still pay once.

LOGGING (B1 — rewritten from the original single-batch-append design)
-----------------------------------------------------------------------
The log file (`~/.claude/.board_state/<subcommand>_<YYYY-MM-DD>.jsonl`) is
opened ONCE per `--apply` run and each row is appended ONE AT A TIME,
IMMEDIATELY BEFORE the write it describes — never as a batch before the loop
starts. Every appended line is `flush()`-ed and `os.fsync()`-ed before the
write is attempted, so a crash between the log write and the actual `gh_issue.sh`
call still leaves an accurate row on disk. Each row carries its OWN timestamp
(not a shared batch timestamp). Immediately after the write attempt, a SECOND
row is appended recording the OUTCOME: `"outcome": "ok"` (transition and
comment both succeeded), `"outcome": "transition-failed"` (the field write
itself failed — the run stops here, nothing after this row was attempted) or
`"outcome": "comment-failed"` (the field write succeeded but the corrective
comment failed — see B4 below). `reverse` reads the FULL append log and, for
each issue+field pair, uses the LATEST row's outcome to decide whether that
write actually landed: only `ok` and `comment-failed` rows are reversible,
because in both cases the field write itself succeeded — a `transition-failed`
row changed nothing on the board and must never be "reversed" (there is
nothing to reverse). A DRY-RUN preview is never written to this log — see
`planned_*.jsonl` below.

`~/.claude/.board_state/planned_<subcommand>_<YYYY-MM-DD>.jsonl` — an OPTIONAL,
purely informational batch-level preview written at the START of an `--apply`
run (before the first real write), listing every row the run INTENDS to
attempt. `reverse` never reads this file — only the per-write append log
above, so a planned-but-never-attempted row (because an earlier row in the
same batch failed) can never be mistaken for a real write.

CROSS-REPO SAFETY (B2)
-----------------------
A GitHub Project board can hold items from multiple repositories. The
original version of this script inferred "the" repository from the first
item on the board and fetched a single open-issue-number set for it, so an
item from a DIFFERENT repository whose bare number happened to also be open
in the first repository would incorrectly pass the "is this open" check —
and because `gh_issue.sh transition` resolves a bare issue number against the
CURRENT WORKING DIRECTORY's git remote (it never receives an explicit
`--repo`), the write would then land on the WRONG issue in the CWD's repo.
`--repo OWNER/NAME` is now REQUIRED on every subcommand that reads the board;
every candidate is keyed on `(repo_slug, number)`, not the bare number alone;
the open-issue-number set is fetched for `--repo` only; and any project item
belonging to a different repository is skipped and reported under
`foreign-repo (skipped)` with its count, never touched. Additionally, before
ANY `--apply` write, the script verifies the CURRENT WORKING DIRECTORY's git
remote actually resolves to the same `--repo` value (`git remote get-url
origin`, parsed defensively) and refuses non-zero if it does not — since that
CWD-repo binding is exactly what `gh_issue.sh transition` relies on
implicitly, verifying it here closes the loop rather than trusting it silently.

PARTIAL-WRITE HANDLING (B4)
-----------------------------
`gh_issue.sh transition ... --field Priority` performs TWO separate calls
internally: it always posts an auto-comment ("Status → **<value>**") THEN
writes the real field. This script's OWN corrective-comment call is a further
THIRD `gh_issue.sh comment` call after that. If the field transition succeeds
but the corrective comment fails, the board's actual state is: the Priority
field IS correctly set, but the issue's comment thread carries only the
generic, misleading "Status → **<value>**" auto-comment with no correction.
This is reported distinctly (never folded into a generic failure): a
`PARTIAL: #<n> ...` message, an outcome of `comment-failed` in the log,
and a DISTINCT exit code, 3 (never conflated with exit code 1, which means
"the field write itself never landed"). On a SUBSEQUENT run, before planning
any NEW writes, the script scans the existing per-day logs for
`comment-failed` rows and attempts to re-post the corrective comment for each
(idempotent — a successful repair is logged `comment-repaired`; the
transition itself is NEVER re-run for a `comment-failed` row, since the field
was already correctly written).

EXIT CODES
-----------
    0  success (including a no-op dry run, or an apply run with nothing to do)
    1  a field-write (transition) failed, an argument error (INCLUDING one
       caught by argparse itself — a missing required flag, `--apply` and
       `--dry-run` both given, a non-integer --project, etc.: this script
       installs a custom ArgumentParser whose `error()` raises the same
       BoardBackfillError every other failure does, specifically so argparse
       never produces its own undocumented exit code 2 — round-2 item 6), a
       missing/malformed log, a truncated read, the CWD-repo mismatch
       refusal, or a `reverse` refusing to reverse a `reverse` log
    3  a field write succeeded but its corrective comment failed (PARTIAL —
       see B4); only ever returned by backfill-priority --apply
    4  a READ failed with rate-limit-shaped output (see PACING below); no
       write was attempted this run — ALSO returned by a `--min-budget`
       refusal (insufficient remaining GraphQL quota) and by a failure of
       the budget query itself (fail-closed: an unreadable budget is treated
       as a rate-limit abort, never as "unknown, carry on")

There is no exit code 2 anywhere in this script's own contract: argparse's
native `sys.exit(2)` behavior is deliberately intercepted and normalized to
1, so "1 means an argument error, among other things" is true without
exception, never true for parse-time errors only.

PACING AND RATE LIMITS
------------------------
`--delay SECONDS` (default 1.0; 0 is valid, used by tests) is slept between
each individual write inside an `--apply` batch, so a 40-row batch does not
fire 40 back-to-back `gh_issue.sh` invocations with no pacing. Every READ
call's stderr (and non-JSON stdout) is scanned for rate-limit-shaped text
("rate limit", "RATE_LIMIT", "secondary rate", or the misleading
"unknown owner type" string `gh project` has been observed to emit for the
same underlying condition — see the 2026-09-20 session history). A read that
looks rate-limited ABORTS the entire run BEFORE any write is attempted, with
exit code 4 and a message stating the run is safely resumable once the quota
recovers — the script never proceeds on a partial or empty item list. A WRITE
failure that looks rate-limited is reported plainly (it still stops the run
via the normal `transition-failed` path — a write already in flight cannot be
un-sent) but is not a distinct exit code, since B1's per-write logging already
makes that boundary exact and resumable.

BUDGET AWARENESS (`--min-budget N`, 2026-09-20)
--------------------------------------------------
`gh api rate_limit` MISREPORTS the GraphQL budget as 5000/5000 regardless of
actual usage (measured live, 2026-09-20) — this script NEVER uses it. The
real remaining GraphQL budget is read via `gh api graphql -f
query='query{rateLimit{remaining resetAt}}'` (its own ~1-point cost), BEFORE
any other read in a run. `--min-budget N` refuses (exit 4, remaining/resetAt
named in the message) when the live `remaining` is below N — BEFORE that
read, and before any write. Defaults (overridable): 2500 for any subcommand
that performs a full board read (`plan`, and `backfill-priority`/
`reset-ready` when `--from-plan` is NOT given, and `reverse` — see below);
300 for `backfill-priority --from-plan`/`reset-ready --from-plan`, sized for
roughly the per-candidate LIVE FIELD CHECK cost above times `--limit`. If the
budget query itself fails (network error, unparsable output, non-zero exit),
that is treated as a rate-limit abort BEFORE any write — never as "budget
unknown, proceed anyway" — fail-closed for writes, exactly like every other
read failure in this script. The budget is queried a SECOND time at the end
of the run, and every run prints one line: "GraphQL cost of this run: <cost>
points (remaining <x>, resets <t>)", where `<cost>` is the before/after
delta — this is the script's own self-measurement of the very problem this
subsystem exists to fix.

LABEL SHAPE (robustness item 5)
---------------------------------
The real board fetched live (2026-09-20, example-org project 1, 1740
items) always returned `labels` as a flat list of PLAIN STRINGS (e.g.
`"priority: P2"`), never as a list of `{"name": ...}` objects. `gh project
item-list --format json` does not appear to ever emit the object form for
`labels`, unlike some other `gh`/GraphQL label surfaces. This script still
normalizes defensively (`_normalize_labels`) in case a future `gh` version,
a differently-configured board, or a hand-edited fixture supplies the object
shape, since assuming the string-only shape forever would silently drop every
label on the day that changes.

MAPPING (backfill-priority; verified live against example-org project 1,
2026-09-20 — see the plan's Phase A.2 table)
------------------------------------------------------------------------------
    priority: P0|P1|P2|P3   -> same value            ("priority: P2" -> P2)
    bare P0|P1|P2|P3        -> same value             ("P2" -> P2)
    priority: critical      -> P0
    priority: P4  (bare P4) -> P3   (FLOOR-FOLD: the Priority field's only
                                      options are P0-P3, verified via
                                      `gh project field-list`; logged as
                                      `floor-fold`, not as an error)
    two DIFFERENT mapped values on one issue -> the HIGHER priority wins
                                      (P0 highest), logged `conflict`
                                      (e.g. ["critical", "P3"] -> P0, conflict)
    any other priority-looking label  -> left untouched, listed under
                                      `unmapped` (never guessed at)
An issue whose Priority field is already set (including an explicit empty
string `""`, which this script treats as "already has a value" rather than
"empty" — see `_priority_field_present` for why) is always skipped, regardless
of its labels.

ORDERING: every subcommand processes candidates in ascending issue number
within `--repo`, so a run is deterministic and a partial `--apply` run's
boundary is reproducible.

NETWORKING: every read goes through `gh` directly (project item-list, issue
list); every WRITE goes through `~/.claude/scripts/gh_issue.sh transition`/
`comment`, with the SOLE exception of `reverse`'s restore-to-empty path,
which calls `gh project item-edit --clear` directly (see RESTORE-TO-EMPTY in
this docstring's LOGGING section and `restore_to_empty` below).
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, NamedTuple

HARD_MAX_LIMIT = 40
DEFAULT_LIMIT = 40
DEFAULT_DELAY_SECONDS = 1.0
BOARD_STATE_DIR = Path(os.environ.get("CLAUDE_DIR", str(Path.home() / ".claude"))) / ".board_state"

# Budget-awareness defaults (see BUDGET AWARENESS in the module docstring).
# A full-board-read path (plan, the legacy no-`--from-plan` paths, reverse)
# needs headroom for the ~1,834-point read this whole subsystem exists to
# avoid paying repeatedly; a --from-plan pass only ever needs headroom for
# roughly 2 points (one LIVE FIELD CHECK) times --limit candidates.
DEFAULT_MIN_BUDGET_FULL_READ = 2500
DEFAULT_MIN_BUDGET_FROM_PLAN = 300

# A plan file older than this is refused by --from-plan -- the board moves in
# ways a stale plan cannot know about (issues closed, fields hand-edited).
PLAN_MAX_AGE_HOURS = 24

# The full taxonomy of `skipped-*` outcomes a --from-plan write-candidate
# check can produce (fix round, 2026-09-20) -- every one of these means "the
# live check could not positively confirm the board still matches the plan
# row", and NONE of them is ever treated as equivalent to "field is empty" /
# "safe to write". See LIVE FIELD CHECK in the module docstring.
SKIP_NOT_ON_BOARD = "skipped-not-on-board"
SKIP_TRUNCATED = "skipped-live-read-truncated"
SKIP_NOT_OPEN = "skipped-not-open"
SKIP_ITEM_ID_CHANGED = "skipped-item-id-changed"
SKIP_CHANGED_SINCE_PLAN = "skipped-changed-since-plan"
ALL_SKIP_OUTCOMES = (SKIP_NOT_ON_BOARD, SKIP_TRUNCATED, SKIP_NOT_OPEN, SKIP_ITEM_ID_CHANGED, SKIP_CHANGED_SINCE_PLAN)

# item 6: a plan dominated by skips must never let one pass scan the whole
# file -- bound the number of LIVE FIELD CHECKS performed in one pass, even
# though `--limit` itself governs WRITES, not checks.
FROM_PLAN_CHECK_MULTIPLIER = 3

# The one write path every SET goes through. Overridable via env for tests
# (a fake gh_issue.sh on PATH, or an absolute override).
GH_ISSUE_SH = os.environ.get(
    "PRIORITY_BACKFILL_GH_ISSUE_SH",
    str(Path(os.environ.get("CLAUDE_DIR", str(Path.home() / ".claude"))) / "scripts" / "gh_issue.sh"),
)
GH_BIN = os.environ.get("PRIORITY_BACKFILL_GH_BIN", "gh")

PRIORITY_FIELD = "Priority"
STATUS_FIELD = "Status"
BACKLOG_STATUS = "Backlog"
READY_STATUSES = ("Ready #1", "Ready #2")
VALID_PRIORITIES = ("P0", "P1", "P2", "P3")
_PRIORITY_RANK = {"P0": 0, "P1": 1, "P2": 2, "P3": 3}  # lower rank = higher priority

_LABEL_QUALIFIED_RE = re.compile(r"^priority:\s*(P[0-4]|critical)\s*$", re.IGNORECASE)
_LABEL_BARE_RE = re.compile(r"^(P[0-4])$", re.IGNORECASE)

_RATE_LIMIT_MARKERS = ("rate limit", "RATE_LIMIT", "secondary rate", "unknown owner type")

# item 7: `--delay` only paces WITHIN one --apply pass; it does nothing
# between successive passes, which is the real usage shape for a >40-row
# job (~7 passes for a 247-item reset, ~8 for a ~300-item backfill, per the
# plan's own measured counts). Printed once at the end of any --apply pass
# that still has rows remaining.
_PACING_REMINDER = (
    "  PACING: {remaining} row(s) remain beyond this pass. GitHub's secondary GraphQL rate limit "
    "is shared across every session on this machine -- pause before running the next --apply pass "
    "rather than firing it immediately back to back (see docs/subsystems/board-state.md)."
)

# Exit codes (see module docstring EXIT CODES section).
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARTIAL_COMMENT_FAILED = 3
EXIT_RATE_LIMITED_READ = 4

# item 9: a per-run id, generated once per process invocation, stamped onto
# every row this run writes to a planned_*.jsonl preview -- so multiple
# `--apply` runs against the same day's preview file can be told apart. The
# authoritative per-write append log (log_path) does not need this: each of
# its rows already carries its own timestamp (B1) and is never batched.
_run_id = uuid.uuid4().hex[:12]


class BoardBackfillError(RuntimeError):
    """Raised for any condition that must stop the run (a failed write, a
    malformed log, an unresolvable read, an argument error). Caught once at
    the CLI boundary. `exit_code` lets specific failure classes (rate-limited
    reads) surface a distinct code without every raise site plumbing it
    through by hand."""

    def __init__(self, message: str, *, exit_code: int = EXIT_ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class RateLimitedReadError(BoardBackfillError):
    """A read call's output looked rate-limit-shaped. Raised before any write
    in the run is attempted; always carries EXIT_RATE_LIMITED_READ."""

    def __init__(self, message: str) -> None:
        super().__init__(message, exit_code=EXIT_RATE_LIMITED_READ)


# --------------------------------------------------------------------------
# gh reads
# --------------------------------------------------------------------------


def _run(cmd: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        timeout=120,
    )


def _looks_rate_limited(text: str) -> bool:
    lowered = text.lower()
    for marker in _RATE_LIMIT_MARKERS:
        if marker.lower() in lowered:
            return True
    return False


def _read_or_raise(proc: subprocess.CompletedProcess, *, what: str) -> str:
    """Shared read-failure handling for every `gh` read call in this module:
    a rate-limit-shaped failure raises RateLimitedReadError (distinct exit
    code, caught before any write); any other non-zero exit raises the plain
    BoardBackfillError. Never returns on failure."""
    if proc.returncode != 0:
        combined = f"{proc.stdout}\n{proc.stderr}"
        if _looks_rate_limited(combined):
            raise RateLimitedReadError(
                f"{what} looks rate-limited ({proc.stderr.strip() or proc.stdout.strip()}) — "
                "aborting before any write; this run is safely resumable once the GitHub API "
                "quota recovers (nothing was written)."
            )
        raise BoardBackfillError(f"{what} failed: {proc.stderr.strip()}")
    # A successful exit can STILL carry rate-limit-shaped text in some gh
    # failure modes (observed live 2026-09-20: `gh project item-list` printed
    # "unknown owner type" to stdout with exit 0 during a genuine rate-limit
    # condition) — treat that the same way rather than trusting the exit code
    # alone once JSON parsing below also fails.
    return proc.stdout


# --------------------------------------------------------------------------
# Budget awareness (see BUDGET AWARENESS in the module docstring). NEVER uses
# `gh api rate_limit` -- that endpoint misreports the GraphQL budget as a
# constant 5000/5000 regardless of actual usage (measured live, 2026-09-20).
# --------------------------------------------------------------------------

_RATE_LIMIT_QUERY = "query{rateLimit{remaining resetAt}}"


def fetch_graphql_rate_limit() -> tuple[int, str]:
    """The REAL remaining GraphQL point budget + reset time, via
    `gh api graphql -f query='query{rateLimit{remaining resetAt}}'`. Raises
    BoardBackfillError on ANY failure (non-zero exit, unparsable JSON, a
    missing/non-numeric `remaining`) -- callers treat that failure as a
    rate-limit abort (fail-closed for writes), never as "unknown, proceed
    anyway" (see BUDGET AWARENESS)."""
    proc = _run([GH_BIN, "api", "graphql", "-f", f"query={_RATE_LIMIT_QUERY}"])
    if proc.returncode != 0:
        raise BoardBackfillError(
            f"gh api graphql (rateLimit) failed: {proc.stderr.strip() or proc.stdout.strip()}"
        )
    try:
        data = json.loads(proc.stdout)
        rate = data["data"]["rateLimit"]
        remaining = int(rate["remaining"])
        reset_at = str(rate["resetAt"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise BoardBackfillError(f"gh api graphql (rateLimit) returned unparsable output: {exc}") from exc
    return remaining, reset_at


def assert_min_budget(min_budget: int, *, what: str) -> tuple[int, str]:
    """Refuses (RateLimitedReadError, exit 4) when the LIVE remaining GraphQL
    budget is below `min_budget`, BEFORE any other read or write this run
    would perform. A failure of the budget query itself is ALSO a refusal
    (fail-closed — see fetch_graphql_rate_limit). Returns (remaining,
    reset_at) on success, so the caller can reuse the reading for the
    end-of-run cost line rather than querying a third time.

    item 10: `--min-budget 0` is a valid, deliberate way to disable the gate
    entirely -- this prints one explicit line naming exactly that whenever
    `min_budget == 0`, rather than let a waived gate look identical to a
    normally-passing one, and genuinely SKIPS the `remaining < min_budget`
    comparison (never relies on "0 is never less than any real remaining
    value" -- a budget query failure, or this test harness's own decrement-
    past-zero counter, can make `remaining` negative, which WOULD be less
    than 0 and wrongly refuse a caller that explicitly asked to waive the
    gate)."""
    if min_budget == 0:
        print(f"  budget gate WAIVED (--min-budget 0) for {what} -- no minimum enforced.")
    try:
        remaining, reset_at = fetch_graphql_rate_limit()
    except BoardBackfillError as exc:
        raise RateLimitedReadError(
            f"could not verify the GraphQL rate-limit budget before {what} ({exc}) — refusing to "
            "proceed (fail-closed: an unreadable budget is treated as a rate-limit abort, never as "
            "'unknown, carry on'); nothing was written"
        ) from exc
    if min_budget > 0 and remaining < min_budget:
        raise RateLimitedReadError(
            f"GraphQL budget too low for {what}: remaining={remaining} < --min-budget={min_budget} "
            f"(resets {reset_at}) — refusing to proceed; nothing was written. This budget is shared "
            "across every session on this machine — wait for it to recover or lower --min-budget "
            "deliberately if you understand the risk."
        )
    return remaining, reset_at


def _print_graphql_cost(before_remaining: int, *, min_budget_for_final_check: int) -> None:
    """Prints the end-of-run 'GraphQL cost of this run' line (BUDGET
    AWARENESS) -- queries the budget a second time and reports the
    before/after delta. Never raises: a failure here is reported as
    'unknown' rather than turning a successful run's own exit code into a
    budget-check failure after the real work is already done."""
    try:
        after_remaining, reset_at = fetch_graphql_rate_limit()
        cost = before_remaining - after_remaining
        print(f"  GraphQL cost of this run: {cost} points (remaining {after_remaining}, resets {reset_at})")
    except BoardBackfillError as exc:
        print(f"  GraphQL cost of this run: unknown (final budget query failed: {exc})")


def fetch_open_issue_numbers(repo: str) -> set[int]:
    """The set of currently-OPEN issue numbers in owner/repo, via `gh issue list`.

    A separate call from `gh project item-list` because that command's JSON
    output carries no open/closed state field at all (verified live,
    2026-09-20) — only `gh issue list --state open` does.
    """
    limit = 2000
    proc = _run(
        [
            GH_BIN,
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--json",
            "number",
            "--limit",
            str(limit),
        ]
    )
    stdout = _read_or_raise(proc, what="gh issue list")
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError as exc:
        if _looks_rate_limited(stdout):
            raise RateLimitedReadError(
                f"gh issue list returned rate-limit-shaped, unparsable output — aborting before "
                f"any write (nothing was written): {stdout.strip()[:200]}"
            ) from exc
        raise BoardBackfillError(f"gh issue list returned unparsable JSON: {exc}") from exc
    if len(rows) == limit:
        raise BoardBackfillError(
            f"gh issue list returned exactly the requested --limit ({limit}) — this may be a "
            "silent truncation, not the true count. Refusing to proceed on a possibly-incomplete "
            "open-issue set (nothing was written)."
        )
    return {int(r["number"]) for r in rows}


def fetch_project_items(owner: str, project: int, limit: int = 2000) -> list[dict[str, Any]]:
    """Every item on the project board, via `gh project item-list --format json`.

    Each item dict, per the live-verified shape (2026-09-20):
        {"content": {"number": int, "type": "Issue"|"PullRequest"|"DraftIssue", ...},
         "id": "PVTI_...", "status": "Backlog"|..., "labels": [...] | absent,
         "priority": "P0".."P3"}   # 'priority' key is ABSENT (not "") when
                                    # the field is empty in the common case —
                                    # verified: no item in a live 1740-item
                                    # board carried an explicit empty-string
                                    # priority value. This script still treats
                                    # an explicit "" as "present" defensively
                                    # (see _priority_field_present) rather
                                    # than assuming that can never happen.
    A DraftIssue item's `content` carries no `number` at all — candidates
    without a `content.number` are always skipped (see plan_backfill /
    plan_reset_ready), which naturally excludes drafts.
    """
    proc = _run(
        [
            GH_BIN,
            "project",
            "item-list",
            str(project),
            "--owner",
            owner,
            "--format",
            "json",
            "--limit",
            str(limit),
        ]
    )
    stdout = _read_or_raise(proc, what="gh project item-list")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        if _looks_rate_limited(stdout):
            raise RateLimitedReadError(
                f"gh project item-list returned rate-limit-shaped, unparsable output — aborting "
                f"before any write (nothing was written): {stdout.strip()[:200]}"
            ) from exc
        raise BoardBackfillError(f"gh project item-list returned unparsable JSON: {exc}") from exc
    items = data.get("items", [])
    if not isinstance(items, list):
        raise BoardBackfillError("gh project item-list JSON has no 'items' array")
    if len(items) == limit:
        raise BoardBackfillError(
            f"gh project item-list returned exactly the requested --limit ({limit}) — this may "
            "be a silent truncation, not the true item count. Refusing to proceed on a possibly-"
            "incomplete board read (nothing was written)."
        )
    return items


def resolve_cwd_repo() -> str | None:
    """Best-effort 'OWNER/NAME' for the CWD's git origin remote, via
    `gh repo view --json nameWithOwner` (falls back to None on any failure —
    callers decide how to treat an unresolvable CWD repo)."""
    proc = _run([GH_BIN, "repo", "view", "--json", "nameWithOwner"])
    if proc.returncode != 0:
        return None
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None
    slug = data.get("nameWithOwner")
    return str(slug) if slug else None


def assert_cwd_matches_repo(repo: str) -> None:
    """B2: before ANY --apply write, verify the CWD's git remote actually
    resolves to --repo, since `gh_issue.sh transition` resolves a bare issue
    number against the CWD's remote implicitly. Refuses (non-zero) rather
    than silently trusting the caller-supplied --repo value."""
    cwd_repo = resolve_cwd_repo()
    if cwd_repo is None:
        raise BoardBackfillError(
            "could not resolve the current working directory's git repository "
            "(`gh repo view --json nameWithOwner` failed) — refusing to write, since "
            "gh_issue.sh resolves bare issue numbers against the CWD's git remote and that "
            "binding could not be verified against --repo"
        )
    if cwd_repo.lower() != repo.lower():
        raise BoardBackfillError(
            f"--repo {repo!r} does not match the current working directory's git repository "
            f"({cwd_repo!r}) — refusing to write, since gh_issue.sh resolves bare issue numbers "
            "against the CWD's git remote; run this from a checkout of --repo instead"
        )


# --------------------------------------------------------------------------
# LOCKING (B4, 2026-09-20 fix round) -- see module docstring's LOCKING
# section for the full rationale. One exclusive, non-blocking fcntl.flock
# per (owner, repo, project) board for the duration of any --apply run.
# --------------------------------------------------------------------------


def _lock_slug(owner: str, repo: str, project: int) -> str:
    """A filesystem-safe slug for the lockfile name -- repo's '/' would
    otherwise create a path segment, not a filename."""
    safe_repo = repo.replace("/", "_")
    return f"{owner}_{safe_repo}_{project}".lower()


def board_lock_path(owner: str, repo: str, project: int) -> Path:
    return BOARD_STATE_DIR / f".lock_{_lock_slug(owner, repo, project)}"


class BoardLockHeld(BoardBackfillError):
    """Raised when another process already holds this board's write lock.
    A distinct subclass (still exit code 1, the plain BoardBackfillError
    default) so a test or caller can distinguish it from any other refusal
    if it ever needs to, without relying on message-string matching."""


def acquire_board_lock(owner: str, repo: str, project: int) -> Any:
    """Acquires an EXCLUSIVE, NON-BLOCKING fcntl.flock on this board's
    lockfile. Returns the open file handle — the caller MUST keep a
    reference to it for the lock's lifetime (closing/garbage-collecting the
    handle releases the lock) and should let it go out of scope (or close
    it explicitly) when the run ends. Raises BoardLockHeld IMMEDIATELY
    (never blocks/waits) if another process already holds it. The OS
    releases the lock automatically on process exit or death (including a
    crash or SIGKILL) -- there is no stale-lock file to clean up and no
    separate recovery procedure; a leftover lockfile with nobody holding it
    is simply inert (LOCK_EX|LOCK_NB on it succeeds immediately)."""
    lock_path = board_lock_path(owner, repo, project)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = lock_path.open("a+")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        fh.close()
        raise BoardLockHeld(
            f"another --apply pass is already running against this board (owner={owner!r} "
            f"repo={repo!r} project={project}) -- lockfile: {lock_path}. Refusing to run "
            "concurrently (never waits); try again once the other pass finishes."
        ) from exc
    return fh


# --------------------------------------------------------------------------
# backfill-priority: label -> Priority-field mapping
# --------------------------------------------------------------------------


def _normalize_labels(raw_labels: Any) -> list[str]:
    """Labels observed live (2026-09-20, example-org project 1, 1740
    items) are always a flat list of plain strings (e.g. "priority: P2") —
    `gh project item-list --format json` was never seen emitting the
    `{"name": ...}` object shape some other GitHub label surfaces use. This
    still normalizes defensively: a dict entry contributes its "name" key if
    present, and any non-string/non-dict entry is dropped rather than raising,
    so an unexpected future shape degrades to "no label seen" instead of
    crashing the whole run."""
    if not isinstance(raw_labels, list):
        return []
    out: list[str] = []
    for entry in raw_labels:
        if isinstance(entry, str):
            out.append(entry)
        elif isinstance(entry, dict):
            name = entry.get("name")
            if isinstance(name, str):
                out.append(name)
        # else: silently dropped (not a recognized label shape).
    return out


def classify_priority_labels(labels: list[str]) -> tuple[list[str], list[str]]:
    """Split an issue's labels into (priority_tokens, unmapped_labels).

    priority_tokens are the RAW matched tokens (e.g. "P4", "critical", "P2"),
    upper-cased where applicable — mapping to a final field value happens in
    `resolve_priority_value`, kept separate so a floor-fold vs. a conflict can
    each be distinguished and logged accurately.
    unmapped_labels holds any label that LOOKS priority-shaped (starts with
    "priority:" or matches a bare P-token pattern loosely) but did not match
    either recognized shape — reported to the caller, never guessed at.
    """
    tokens: list[str] = []
    unmapped: list[str] = []
    for label in labels:
        stripped = label.strip()
        m = _LABEL_QUALIFIED_RE.match(stripped)
        if m:
            tokens.append(m.group(1).upper())
            continue
        m = _LABEL_BARE_RE.match(stripped)
        if m:
            tokens.append(m.group(1).upper())
            continue
        # Anything else "priority-looking" that didn't match: only flag it if
        # it plausibly intends to be a priority label, so a wholly unrelated
        # label list doesn't spuriously get logged every time.
        if stripped.lower().startswith("priority:") or re.match(r"^p[0-9]+$", stripped, re.IGNORECASE):
            unmapped.append(stripped)
    return tokens, unmapped


def resolve_priority_value(tokens: list[str]) -> tuple[str | None, str]:
    """Map raw priority tokens to a single Priority-field value.

    Returns (value_or_None, disposition) where disposition is one of:
      "mapped"      - a single, unambiguous mapped value
      "floor-fold"  - the only mapped value came from P4 (folded to P3)
      "conflict"    - two or more DIFFERENT mapped values were present;
                       value is the HIGHER priority (P0 highest)
      "unmapped"    - tokens existed but none mapped to a valid field value
                       (should not happen given classify_priority_labels'
                       matching, but handled defensively rather than assumed)
    """
    if not tokens:
        return None, "unmapped"

    mapped_values: set[str] = set()
    saw_p4 = False
    for tok in tokens:
        upper = tok.upper()
        if upper == "CRITICAL":
            mapped_values.add("P0")
        elif upper == "P4":
            saw_p4 = True
            mapped_values.add("P3")
        elif upper in VALID_PRIORITIES:
            mapped_values.add(upper)
        # else: not a recognized token; ignored here (classify_priority_labels
        # already routes genuinely unrecognized shapes to `unmapped` before
        # this function is ever called with them as `tokens`).

    if not mapped_values:
        return None, "unmapped"

    if len(mapped_values) > 1:
        winner = min(mapped_values, key=lambda v: _PRIORITY_RANK[v])
        return winner, "conflict"

    (only_value,) = tuple(mapped_values)
    if saw_p4 and only_value == "P3":
        # Every mapped-value case where a P4 label contributed lands here,
        # whether P4 was the sole signal or one of several labels that all
        # independently resolved to P3 (e.g. "priority: P4" alongside
        # "priority: P3") — P4 has no Priority-field option, so any P4
        # contribution is always reported as a floor-fold, never a plain map.
        return "P3", "floor-fold"
    return only_value, "mapped"


def _priority_field_present(item: dict[str, Any]) -> bool:
    """True when the item's Priority field already carries a value —
    including an explicit empty string "". Pinned choice: an explicit ""
    is treated as PRESENT (skip the issue), not as "empty, eligible for
    backfill". Rationale: this script has never observed a live "" value
    (only an absent key means empty on the real board, per the module
    docstring), so an explicit "" — if the API or a hand-built fixture ever
    produces one — is closer to "a value was actively cleared" than to "no
    value was ever set"; treating it as empty risks silently overwriting a
    deliberate clear. The safer, narrower reading is chosen: skip it."""
    return "priority" in item and item.get("priority") is not None


# --------------------------------------------------------------------------
# gh_issue.sh transition + comment wrapper (the single write path)
# --------------------------------------------------------------------------


def write_field(
    *,
    issue_num: int,
    status_value: str,
    project: int,
    owner: str,
    field: str,
) -> None:
    """Writes a project field via gh_issue.sh transition. Raises
    BoardBackfillError on any non-zero exit (the caller stops the whole run,
    per this script's no-silent-partial-state contract)."""
    cmd = [
        "bash",
        GH_ISSUE_SH,
        "transition",
        str(issue_num),
        "--status",
        status_value,
        "--project",
        str(project),
        "--owner",
        owner,
        "--field",
        field,
    ]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise BoardBackfillError(
            f"gh_issue.sh transition failed for #{issue_num} "
            f"(field={field!r} value={status_value!r}): {proc.stderr.strip()}"
        )


def post_priority_correction_comment(*, issue_num: int, value: str) -> None:
    """gh_issue.sh's own transition auto-comment always says "Status →
    **<value>**" (gh_issue.sh:204), even when --field Priority was used to
    write a DIFFERENT field. After every successful Priority write, post a
    corrective comment saying the Priority field — not Status — was set, so
    the issue's own history is not misleading about which field changed.
    Raises BoardBackfillError on failure; the caller distinguishes this from
    a transition failure (see B4)."""
    import tempfile

    body = (
        f"Priority field set to **{value}** (via `priority_backfill.py backfill-priority`; "
        f"the preceding auto-comment's \"Status → {value}\" wording is gh_issue.sh's generic "
        "transition message — no Status change occurred)."
    )
    # Item 17: the comment body is a purely transient scratch file, never
    # part of this script's durable state — it lives under the system temp
    # dir via `tempfile`, not inside .board_state/, so it can never be
    # mistaken for one of this script's own log/preview files.
    fd, tmp_name = tempfile.mkstemp(prefix="priority_backfill_comment_", suffix=".md")
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        cmd = ["bash", GH_ISSUE_SH, "comment", str(issue_num), "--body-file", str(tmp_path)]
        proc = _run(cmd)
        if proc.returncode != 0:
            raise BoardBackfillError(
                f"gh_issue.sh comment (Priority correction) failed for #{issue_num}: {proc.stderr.strip()}"
            )
    finally:
        tmp_path.unlink(missing_ok=True)


def repost_priority_correction_comment(*, issue_num: int, value: str) -> bool:
    """Idempotent repair path for a previously comment-failed row (B4): tries
    the corrective comment again. Returns True on success, False on failure
    (never raises — the caller logs `comment-repaired` or leaves the row for
    a future run)."""
    try:
        post_priority_correction_comment(issue_num=issue_num, value=value)
        return True
    except BoardBackfillError:
        return False


# --------------------------------------------------------------------------
# Logging (~/.claude/.board_state/) — B1: one row per write, appended
# immediately before the write, plus a paired outcome row after.
# --------------------------------------------------------------------------


def log_path(subcommand: str, *, today: str | None = None) -> Path:
    day = today or datetime.date.today().isoformat()
    return BOARD_STATE_DIR / f"{subcommand}_{day}.jsonl"


def planned_log_path(subcommand: str, *, today: str | None = None) -> Path:
    day = today or datetime.date.today().isoformat()
    return BOARD_STATE_DIR / f"planned_{subcommand}_{day}.jsonl"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_log_row(path: Path, row: dict[str, Any]) -> None:
    """Append exactly ONE row, flushed and fsynced before returning (B1) —
    the durability guarantee a mid-batch crash relies on."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True))
        fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())


def write_planned_preview(path: Path, rows: list[dict[str, Any]]) -> None:
    """The informational, non-authoritative batch preview (see module
    docstring) — `reverse` never reads this file. Every row carries this
    process's `run_id` (item 9) so multiple `--apply` runs writing into the
    same day's preview file can be distinguished from one another."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps({**row, "run_id": _run_id}, sort_keys=True))
            fh.write("\n")
        fh.flush()


def _all_log_rows_for_subcommand(subcommand: str) -> list[dict[str, Any]]:
    """Every row ever appended to `<subcommand>_*.jsonl` (across all dates),
    ascending by file/date then file order — used by the comment-repair scan
    (B4) and by anything wanting a full history rather than just today's."""
    pattern = str(BOARD_STATE_DIR / f"{subcommand}_*.jsonl")
    rows: list[dict[str, Any]] = []
    for fname in sorted(glob.glob(pattern)):
        p = Path(fname)
        if p.name.startswith("planned_"):
            continue
        with p.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # a malformed line in a historical log is skipped, not fatal
    return rows


def repair_comment_failed_rows(*, owner: str, repo: str, project: int) -> list[int]:
    """B4 repair pass: scan every `backfill-priority` log for the latest
    outcome per issue; for any issue whose latest outcome is
    `comment-failed` AND whose write-intent row belongs to THIS invocation's
    `(owner, repo, project)` — never any other board (round-2 item 8: a bare
    issue number can collide across boards, and re-posting a comment on the
    wrong board's same-numbered issue in the CWD repo is exactly the
    cross-board hazard this scoping closes) — re-attempt the corrective
    comment (never the transition). Returns the list of issue numbers
    successfully repaired. Repairs are logged as their own `comment-repaired`
    outcome row so a repeated repair pass is itself idempotent (a
    `comment-repaired` row becomes the new "latest outcome" for that issue,
    so it is never re-attempted)."""
    rows = _all_log_rows_for_subcommand("backfill-priority")

    # Outcome rows carry no repo/owner/project (only intent rows do), so the
    # board scope has to be read off the LATEST intent row for each issue,
    # joined against that issue's latest outcome.
    latest_intent_by_issue: dict[int, dict[str, Any]] = {}
    latest_outcome_by_issue: dict[int, dict[str, Any]] = {}
    for row in rows:
        issue = row.get("issue")
        if issue is None:
            continue
        issue = int(issue)
        if "outcome" in row:
            latest_outcome_by_issue[issue] = row
        elif "old_value" in row:
            latest_intent_by_issue[issue] = row

    repaired: list[int] = []
    for issue_num in sorted(latest_outcome_by_issue):
        outcome_row = latest_outcome_by_issue[issue_num]
        if outcome_row.get("outcome") != "comment-failed":
            continue
        intent_row = latest_intent_by_issue.get(issue_num)
        if intent_row is None:
            continue  # no matching intent row found -- can't verify board scope, skip
        if (
            str(intent_row.get("owner", "")).lower() != owner.lower()
            or str(intent_row.get("repo", "")).lower() != repo.lower()
            or intent_row.get("project") != project
        ):
            continue  # belongs to a DIFFERENT board -- never touched by this invocation
        value = outcome_row.get("new_value") or intent_row.get("new_value")
        if not value:
            continue
        ok = repost_priority_correction_comment(issue_num=issue_num, value=str(value))
        new_outcome_row = {
            "ts": _now_iso(),
            "subcommand": "backfill-priority",
            "issue": issue_num,
            "field": PRIORITY_FIELD,
            "new_value": value,
            "owner": owner,
            "repo": repo,
            "project": project,
            "outcome": "comment-repaired" if ok else "comment-failed",
        }
        append_log_row(log_path("backfill-priority"), new_outcome_row)
        if ok:
            repaired.append(issue_num)
    return repaired


# --------------------------------------------------------------------------
# plan / --from-plan (see FROM-PLAN in the module docstring)
# --------------------------------------------------------------------------

PLAN_KIND = "plan-header"


def _script_sha256() -> str | None:
    """This script's own bytes, hashed for the plan header's provenance
    field -- cheap (one file read) and lets a stale/mismatched plan be
    correlated with which version of the script produced it. Never raises:
    a failure to hash (e.g. running from a frozen/zipped context with no
    readable __file__) degrades to None rather than blocking planning."""
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError:
        return None


def plan_path(for_subcommand: str, *, ts: str | None = None) -> Path:
    """`~/.claude/.board_state/plan_<for>_<UTC timestamp>.jsonl` -- the
    timestamp (not a date, unlike the per-write logs) is part of the
    filename so multiple plans for the same subcommand on the same day never
    collide, and so a plan's own age is readable straight off its name."""
    stamp = ts or datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return BOARD_STATE_DIR / f"plan_{for_subcommand}_{stamp}.jsonl"


def _plan_row_canonical(row: dict[str, Any]) -> dict[str, Any]:
    """The exact five fields (in this exact set) that participate in the
    B3 integrity hash and in row validation -- deliberately excludes
    `disposition` (informational only, never used to decide a write)."""
    return {
        "repo": row.get("repo"),
        "issue": row.get("issue"),
        "item_id": row.get("item_id"),
        "field": row.get("field"),
        "old_value": row.get("old_value"),
        "new_value": row.get("new_value"),
    }


def _plan_rows_sha256(writes: list[dict[str, Any]]) -> str:
    """B3 integrity hash: SHA-256 over the canonical (sorted-key,
    newline-joined) JSON serialization of every candidate row, in the exact
    order they will be written. Computed by `plan`/`write_plan_file` and
    recomputed by `load_plan_file` on every read -- a mismatch means the
    ROWS were edited after the header was written (accidental edit or
    casual tampering; see ROW VALIDATION + INTEGRITY in the module
    docstring for what this does and does not defend against)."""
    canonical_lines = [json.dumps(_plan_row_canonical(w), sort_keys=True) for w in writes]
    return hashlib.sha256("\n".join(canonical_lines).encode("utf-8")).hexdigest()


def write_plan_file(
    *,
    for_subcommand: str,
    owner: str,
    repo: str,
    project: int,
    writes: list[dict[str, Any]],
    counts: dict[str, int],
) -> Path:
    """Writes the plan header row + one candidate row per write, fsynced.
    Returns the path written.

    The integrity hash (`rows_sha256`) is computed over the ACTUAL on-disk
    row dicts (built once, below, then both hashed AND written from the
    same list) — never over the raw `writes` input. The raw input rows
    (e.g. from `plan_backfill`) carry no `"repo"` key at all; only this
    function's own row-construction adds it. Hashing the raw input would
    hash a DIFFERENT shape than `load_plan_file` re-hashes on read (which
    always sees `repo` populated, since it's on every line in the file) —
    a genuine plan would then fail its own integrity check on the very
    first read, which is exactly the bug this comment exists to prevent
    reintroducing."""
    path = plan_path(for_subcommand)
    path.parent.mkdir(parents=True, exist_ok=True)
    on_disk_rows = [
        {
            "repo": repo,
            "issue": w["issue"],
            "item_id": w.get("item_id"),
            "field": w["field"],
            "old_value": w["old_value"],
            "new_value": w["new_value"],
            "disposition": w.get("disposition"),
        }
        for w in writes
    ]
    header = {
        "kind": PLAN_KIND,
        "for": for_subcommand,
        "owner": owner,
        "repo": repo,
        "project": project,
        "created_at": _now_iso(),
        "counts": counts,
        "script_sha256": _script_sha256(),
        "rows_sha256": _plan_rows_sha256(on_disk_rows),
    }
    with path.open("w", encoding="utf-8") as fh:
        fh.write(json.dumps(header, sort_keys=True))
        fh.write("\n")
        for row in on_disk_rows:
            fh.write(json.dumps(row, sort_keys=True))
            fh.write("\n")
        fh.flush()
        os.fsync(fh.fileno())
    return path


def _validate_plan_row(row: dict[str, Any], *, index: int, for_subcommand: str, repo: str) -> None:
    """B3: validates ONE candidate row against the exact invariants a
    genuine `plan` output always satisfies. Raises BoardBackfillError naming
    the row's position (1-based among candidate rows, matching what an
    operator eyeballing the file would count) and the specific violation on
    the FIRST failure — `load_plan_file` calls this for every row before
    returning any of them, so a single bad row refuses the WHOLE file
    rather than silently dropping just that row (a silently-dropped row is
    invisible; a refused file is not). Re-checked a SECOND time at the
    actual write call site in `_run_from_plan_candidates` — this function is
    the single source of truth for both checks, called from both places, so
    the two can never drift apart."""
    where = f"candidate row {index}"

    expected_field = PRIORITY_FIELD if for_subcommand == "backfill-priority" else STATUS_FIELD
    field = row.get("field")
    if field != expected_field:
        raise BoardBackfillError(
            f"{where}: field={field!r}, expected exactly {expected_field!r} for a `--for "
            f"{for_subcommand}` plan -- refusing the whole file"
        )

    issue = row.get("issue")
    if isinstance(issue, bool) or not isinstance(issue, int) or issue <= 0:
        raise BoardBackfillError(f"{where}: issue={issue!r} is not a positive int -- refusing the whole file")

    old_value = row.get("old_value")
    new_value = row.get("new_value")
    if field == PRIORITY_FIELD:
        if old_value is not None:
            raise BoardBackfillError(f"{where}: old_value={old_value!r}, expected None for a Priority row -- refusing the whole file")
        if new_value not in VALID_PRIORITIES:
            raise BoardBackfillError(f"{where}: new_value={new_value!r} is not one of {VALID_PRIORITIES} -- refusing the whole file")
    else:  # STATUS_FIELD
        if old_value not in READY_STATUSES:
            raise BoardBackfillError(f"{where}: old_value={old_value!r} is not one of {READY_STATUSES} -- refusing the whole file")
        if new_value != BACKLOG_STATUS:
            raise BoardBackfillError(f"{where}: new_value={new_value!r}, expected exactly {BACKLOG_STATUS!r} -- refusing the whole file")

    row_repo = row.get("repo")
    if row_repo is not None and str(row_repo).lower() != repo.lower():
        raise BoardBackfillError(f"{where}: repo={row_repo!r} does not match --repo {repo!r} -- refusing the whole file")


def load_plan_file(path: Path, *, for_subcommand: str, owner: str, repo: str, project: int) -> list[dict[str, Any]]:
    """Reads + validates a plan file written by `plan`. Raises
    BoardBackfillError on: a missing file, a malformed/missing header, a
    header whose `for`/owner/repo/project does not match this invocation's
    flags, a header older than PLAN_MAX_AGE_HOURS, a `rows_sha256` mismatch
    (B3 integrity check — the rows were edited after the header was
    written), or ANY candidate row failing `_validate_plan_row` (B3 — the
    whole file is refused, never a partial/best-effort load) — including a
    duplicate `(repo, issue)` pair across rows, checked here rather than in
    `_validate_plan_row` since it is a property of the ROW SET, not any one
    row. Returns the candidate rows (header excluded), in the file's own
    recorded order."""
    if not path.is_file():
        raise BoardBackfillError(f"plan file not found: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        raise BoardBackfillError(f"plan file is empty: {path}")

    try:
        header = json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise BoardBackfillError(f"{path}: malformed plan header: {exc}") from exc

    if header.get("kind") != PLAN_KIND:
        raise BoardBackfillError(f"{path}: first row is not a plan header (kind={header.get('kind')!r})")
    if header.get("for") != for_subcommand:
        raise BoardBackfillError(
            f"{path}: plan was created `--for {header.get('for')!r}`, but this is `{for_subcommand}` "
            "-- refusing to run a mismatched plan. Re-run `plan --for "
            f"{for_subcommand}` to produce a matching one."
        )
    if str(header.get("owner", "")).lower() != owner.lower() or str(header.get("repo", "")).lower() != repo.lower() or header.get("project") != project:
        raise BoardBackfillError(
            f"{path}: plan header (owner={header.get('owner')!r} repo={header.get('repo')!r} "
            f"project={header.get('project')!r}) does not match this invocation's "
            f"(owner={owner!r} repo={repo!r} project={project!r}) -- refusing to run a plan cut "
            "against a different board. Re-run `plan` with these flags."
        )

    created_at = header.get("created_at")
    try:
        created_dt = datetime.datetime.strptime(str(created_at), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)
    except (ValueError, TypeError) as exc:
        raise BoardBackfillError(f"{path}: plan header has an unparsable created_at: {created_at!r}") from exc
    age = datetime.datetime.now(datetime.timezone.utc) - created_dt
    if age > datetime.timedelta(hours=PLAN_MAX_AGE_HOURS):
        raise BoardBackfillError(
            f"{path}: plan is {age} old, older than the {PLAN_MAX_AGE_HOURS}-hour limit -- the "
            f"board may have moved since it was cut. Re-run `plan --for {for_subcommand} --owner "
            f"{owner} --repo {repo} --project {project}` to produce a fresh one."
        )

    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines[1:], start=2):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise BoardBackfillError(f"{path}:{lineno}: malformed plan candidate row: {exc}") from exc

    # B3 integrity check: the header's rows_sha256 must match a fresh hash
    # of the rows as loaded. A plan written before this fix round carries no
    # rows_sha256 at all -- refused with a message pointing at re-running
    # `plan`, never silently trusted as "no hash means no tampering."
    expected_hash = header.get("rows_sha256")
    if not expected_hash:
        raise BoardBackfillError(
            f"{path}: plan header carries no rows_sha256 (written by an older version of this "
            "script, or hand-edited) -- refusing to trust an unverifiable plan. Re-run `plan` to "
            "produce one with the integrity hash."
        )
    actual_hash = _plan_rows_sha256(rows)
    if actual_hash != expected_hash:
        raise BoardBackfillError(
            f"{path}: rows_sha256 mismatch (header says {expected_hash}, rows hash to {actual_hash}) "
            "-- the candidate rows were edited after the header was written. Refusing the whole "
            "file. Re-run `plan` to produce a fresh, untampered one."
        )

    # B3 row validation: every row checked BEFORE any are returned -- a
    # single bad row refuses the whole file.
    seen_keys: set[tuple[str, int]] = set()
    for index, row in enumerate(rows, start=1):
        _validate_plan_row(row, index=index, for_subcommand=for_subcommand, repo=repo)
        key = (str(row.get("repo", repo)).lower(), int(row["issue"]))
        if key in seen_keys:
            raise BoardBackfillError(f"candidate row {index}: duplicate (repo, issue) {key} already appeared earlier in this plan -- refusing the whole file")
        seen_keys.add(key)

    return rows


# item 6: a candidate is re-offered on the NEXT pass at most once more
# after a skipped-* outcome (the underlying condition may have been
# transient, or a human may have corrected it) -- after this many TOTAL
# skipped-* outcomes for the same (issue, field), it is excluded
# permanently and must wait for a fresh `plan`.
MAX_SKIPS_BEFORE_PERMANENT = 2


def _done_and_indeterminate_issue_keys(
    subcommand: str,
) -> tuple[set[tuple[int, str]], set[tuple[int, str]], dict[tuple[int, str], int]]:
    """Reads this script's OWN existing per-write append logs for
    `subcommand` (the same logs `reverse` reads — see `_all_log_rows_for_subcommand`)
    and returns (done_keys, indeterminate_keys, skip_counts) as (issue, field)
    tuples/counts:
        done_keys           - latest outcome is ok/comment-failed/comment-repaired
                               (the write landed; skip this candidate in a
                               --from-plan pass)
        indeterminate_keys  - an intent row exists with NO recorded outcome at
                               all (a crash between the log write and the
                               outcome write) -- skipped AND listed, never
                               silently re-attempted, exactly as `reverse`
                               already treats this state.
        skip_counts         - TOTAL number of `skipped-*` outcome rows ever
                               recorded for that (issue, field), across every
                               log this subcommand has ever written (item 6 —
                               the permanently-skipped rule).
    A `transition-failed` outcome means the write never landed -- excluded
    from both sets, so that candidate is still offered again."""
    rows = _all_log_rows_for_subcommand(subcommand)
    classified = _latest_write_rows(rows)
    done: set[tuple[int, str]] = set()
    for r in classified["reversible"]:
        done.add((int(r["issue"]), str(r["field"])))
    indeterminate: set[tuple[int, str]] = set()
    for r in classified["indeterminate"]:
        indeterminate.add((int(r["issue"]), str(r["field"])))
    skip_counts: dict[tuple[int, str], int] = {}
    for row in rows:
        outcome = row.get("outcome")
        if outcome in ALL_SKIP_OUTCOMES:
            issue = row.get("issue")
            field = row.get("field")
            if issue is None or field is None:
                continue
            key = (int(issue), str(field))
            skip_counts[key] = skip_counts.get(key, 0) + 1
    return done, indeterminate, skip_counts


def select_from_plan_candidates(
    plan_rows: list[dict[str, Any]], *, subcommand: str, limit: int
) -> dict[str, list[dict[str, Any]]]:
    """Filters a loaded plan's candidate rows against this script's own
    write-outcome logs (see `_done_and_indeterminate_issue_keys`) and returns
    the next up-to-`FROM_PLAN_CHECK_MULTIPLIER * limit` not-yet-done
    candidates (item 6 — a generous slice, since `skipped-*` outcomes don't
    count against `--limit`; `_run_from_plan_candidates` enforces the real
    per-pass check cap itself), plus the ones set aside for each reason --
    pure function, no I/O, so it is unit-testable directly."""
    done_keys, indeterminate_keys, skip_counts = _done_and_indeterminate_issue_keys(subcommand)
    to_check: list[dict[str, Any]] = []
    already_done: list[dict[str, Any]] = []
    indeterminate: list[dict[str, Any]] = []
    permanently_skipped: list[dict[str, Any]] = []
    for row in plan_rows:
        key = (int(row["issue"]), str(row["field"]))
        if key in done_keys:
            already_done.append(row)
        elif key in indeterminate_keys:
            indeterminate.append(row)
        elif skip_counts.get(key, 0) >= MAX_SKIPS_BEFORE_PERMANENT:
            permanently_skipped.append({**row, "_skip_count": skip_counts[key]})
        else:
            to_check.append(row)
    # item 6: `to_check` is intentionally sized larger than `--limit` here --
    # skipped-* candidates consume a live check but not a --limit slot, so
    # the loop needs headroom to find `limit` genuinely writable candidates
    # without truncating them out before it even tries. The caller
    # (_run_from_plan_candidates) enforces the real per-pass bounds (limit
    # writes, FROM_PLAN_CHECK_MULTIPLIER*limit checks).
    check_slice_size = FROM_PLAN_CHECK_MULTIPLIER * limit
    return {
        "to_check": to_check[:check_slice_size],
        "remaining_after": to_check[check_slice_size:],
        "already_done": already_done,
        "indeterminate": indeterminate,
        "permanently_skipped": permanently_skipped,
    }


# --------------------------------------------------------------------------
# backfill-priority
# --------------------------------------------------------------------------


def plan_backfill(
    items: list[dict[str, Any]], open_numbers: set[int], repo: str
) -> dict[str, list[dict[str, Any]]]:
    """Build the full plan for backfill-priority, deterministically ordered
    by ascending issue number within --repo. Returns a dict with keys:
        "writes"        - rows that WILL be written (mapped + floor-fold + conflict)
        "unmapped"      - issues with priority-looking labels that didn't resolve
        "skipped"       - issues whose Priority field is already set (informational only)
        "foreign_repo"  - items on the board belonging to a DIFFERENT repo (B2)
    """
    writes: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    foreign_repo: list[dict[str, Any]] = []

    candidates = []
    for item in items:
        content = item.get("content", {})
        if content.get("type") != "Issue":
            continue
        num = content.get("number")
        if num is None:
            continue
        item_repo = _repo_slug_from_item(item)
        if item_repo is not None and item_repo.lower() != repo.lower():
            foreign_repo.append({"issue": int(num), "repo": item_repo})
            continue
        if int(num) not in open_numbers:
            continue
        candidates.append(item)

    candidates.sort(key=lambda it: int(it["content"]["number"]))

    for item in candidates:
        num = int(item["content"]["number"])
        if _priority_field_present(item):
            skipped.append({"issue": num, "priority": item.get("priority")})
            continue

        labels = _normalize_labels(item.get("labels", []))
        tokens, unmapped_labels = classify_priority_labels(labels)
        value, disposition = resolve_priority_value(tokens)

        if value is None:
            if unmapped_labels:
                unmapped.append({"issue": num, "labels": unmapped_labels})
            # else: no priority-shaped label at all -- not reported (the
            # overwhelming majority case; Phase D closes that separately).
            continue

        writes.append(
            {
                "issue": num,
                "item_id": item.get("id"),
                "field": PRIORITY_FIELD,
                "old_value": None,
                "new_value": value,
                "disposition": disposition,
                "matched_labels": tokens,
            }
        )

    return {"writes": writes, "unmapped": unmapped, "skipped": skipped, "foreign_repo": foreign_repo}


def _print_foreign_repo(foreign_repo: list[dict[str, Any]], repo: str) -> None:
    print(f"  foreign-repo (skipped, not in --repo {repo}): {len(foreign_repo)}")
    if foreign_repo:
        for f in foreign_repo[:20]:
            print(f"    #{f['issue']} ({f['repo']})")
        if len(foreign_repo) > 20:
            print(f"    ... and {len(foreign_repo) - 20} more")


def cmd_plan(args: argparse.Namespace) -> int:
    owner = args.owner
    project = args.project
    repo = args.repo
    for_subcommand = args.for_subcommand
    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FULL_READ

    before_remaining, _ = assert_min_budget(min_budget, what=f"plan --for {for_subcommand}")

    items = fetch_project_items(owner, project)
    open_numbers = fetch_open_issue_numbers(repo)

    if for_subcommand == "backfill-priority":
        computed = plan_backfill(items, open_numbers, repo)
        writes = computed["writes"]
        unmapped = computed["unmapped"]
        foreign_repo = computed["foreign_repo"]
        mapped_ct = sum(1 for w in writes if w["disposition"] == "mapped")
        floor_fold_ct = sum(1 for w in writes if w["disposition"] == "floor-fold")
        conflict_ct = sum(1 for w in writes if w["disposition"] == "conflict")
        counts = {
            "writes": len(writes),
            "mapped": mapped_ct,
            "floor_fold": floor_fold_ct,
            "conflict": conflict_ct,
            "unmapped": len(unmapped),
            "foreign_repo": len(foreign_repo),
        }
        plan_writes = [{**w, "field": PRIORITY_FIELD} for w in writes]
    else:  # reset-ready
        computed = plan_reset_ready(items, open_numbers, repo)
        candidates = computed["writes"]
        foreign_repo = computed["foreign_repo"]
        r1_ct = sum(1 for r in candidates if r["old_value"] == "Ready #1")
        r2_ct = sum(1 for r in candidates if r["old_value"] == "Ready #2")
        counts = {"writes": len(candidates), "ready_1": r1_ct, "ready_2": r2_ct, "foreign_repo": len(foreign_repo)}
        plan_writes = [
            {
                "issue": r["issue"],
                "item_id": r.get("item_id"),
                "field": STATUS_FIELD,
                "old_value": r["old_value"],
                "new_value": BACKLOG_STATUS,
                "disposition": None,
            }
            for r in candidates
        ]

    path = write_plan_file(for_subcommand=for_subcommand, owner=owner, repo=repo, project=project, writes=plan_writes, counts=counts)

    print(f"priority_backfill: plan --for {for_subcommand} — owner={owner} repo={repo} project={project}")
    print(f"  wrote {len(plan_writes)} candidate row(s) to {path}")
    for k, v in counts.items():
        print(f"    {k}: {v}")
    _print_foreign_repo(foreign_repo, repo)
    print(f"  NOTHING was written to GitHub by this run. Next: run `{for_subcommand} --from-plan {path} --apply` (repeatedly, one pass per --limit batch).")
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


def _classify_live_check(row: dict[str, Any], live: LiveField) -> str | None:
    """Pure classification (unit-testable without a subprocess): given a
    plan candidate row and its LiveField read, returns the `skipped-*`
    outcome name if the row must be skipped, or None if it is safe to
    write. Checked in a fixed, deliberate order — not-on-board and
    truncation are checked before open-state (an item that isn't found at
    all has no meaningful open state to report), open-state before item-id
    (closed-since-plan is a more specific, more useful message than a
    coincidental id mismatch on a closed issue), and item-id before the
    plain value comparison (a changed item id makes the value comparison
    meaningless regardless of what the value happens to be)."""
    if live.truncated:
        return SKIP_TRUNCATED
    if not live.found:
        return SKIP_NOT_ON_BOARD
    if live.is_open is not True:
        # None means "could not be determined" (LiveField's contract): never assume open.
        return SKIP_NOT_OPEN
    plan_item_id = row.get("item_id")
    if plan_item_id and live.item_id and str(plan_item_id) != str(live.item_id):
        return SKIP_ITEM_ID_CHANGED
    if live.value != row.get("old_value"):
        return SKIP_CHANGED_SINCE_PLAN
    return None


def _run_from_plan_candidates(
    *,
    to_check: list[dict[str, Any]],
    owner: str,
    repo: str,
    project: int,
    subcommand: str,
    apply: bool,
    limit: int,
    delay: float,
    project_node_id: str | None,
) -> dict[str, Any]:
    """Shared `--from-plan` per-candidate loop for both backfill-priority and
    reset-ready: for each candidate (already filtered to not-yet-done by
    `select_from_plan_candidates`), performs ONE live field check
    immediately before deciding whether to write (see FROM-PLAN / LIVE FIELD
    CHECK in the module docstring). Returns a dict describing what happened,
    for the caller to print/log -- this function itself performs the writes
    (via write_field/post_priority_correction_comment) and the B1 append-log
    rows, mirroring the full-read --apply loops exactly, so a
    --from-plan write is byte-for-byte the same kind of write/log/comment
    sequence as a normal --apply write.

    item 6: a `skipped-*` candidate does NOT count against `--limit` — this
    loop keeps taking candidates from `to_check` until `limit` WRITES (in
    --apply mode) or would-writes (in dry-run) have happened, or `to_check`
    is exhausted, whichever comes first. The number of LIVE FIELD CHECKS
    performed is separately capped at `FROM_PLAN_CHECK_MULTIPLIER * limit`
    so a plan dominated by skips can never turn one pass into an unbounded
    scan (the caller is expected to pass a `to_check` slice sized generously
    enough — see `select_from_plan_candidates` — but this loop enforces its
    own hard stop regardless of what it is handed)."""
    lp = log_path(subcommand)
    written: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    partial_comment_failure = False
    applied_count = 0
    checked_count = 0
    max_checks = FROM_PLAN_CHECK_MULTIPLIER * limit

    for row in to_check:
        if applied_count >= limit or checked_count >= max_checks:
            break
        issue_num = int(row["issue"])
        field = str(row["field"])
        old_value = row.get("old_value")
        new_value = row["new_value"]

        live = fetch_live_item_field(issue_num=issue_num, field=field, project_node_id=project_node_id or "")
        checked_count += 1

        skip_outcome = _classify_live_check(row, live)
        if skip_outcome is not None:
            skipped.append({**row, "_outcome": skip_outcome, "_live_value": live.value, "_is_open": live.is_open})
            print(
                f"  SKIPPED #{issue_num} {field} ({skip_outcome}): plan expected old={old_value!r}, "
                f"live found={live.found} open={live.is_open} truncated={live.truncated} value={live.value!r}"
            )
            if apply:
                append_log_row(
                    lp,
                    {
                        "ts": _now_iso(),
                        "subcommand": subcommand,
                        "issue": issue_num,
                        "field": field,
                        "old_value": old_value,
                        "new_value": new_value,
                        "owner": owner,
                        "repo": repo,
                        "project": project,
                        "outcome": skip_outcome,
                        "live_value": live.value,
                    },
                )
            continue

        if not apply:
            verb = "set" if field == PRIORITY_FIELD else "move"
            print(f"    would {verb} #{issue_num} {field} = {new_value} (from-plan; live matches plan)")
            applied_count += 1
            continue

        # B3 defense in depth: re-validate this exact row's invariants
        # immediately before the write, mirroring restore_to_empty's own
        # "checked at the actual write call, never just trusted from the
        # caller" precedent -- the SAME function `load_plan_file` already
        # ran at load time, so the two checks can never drift apart.
        _validate_plan_row(row, index=-1, for_subcommand=subcommand, repo=repo)

        write_row = {
            "ts": _now_iso(),
            "subcommand": subcommand,
            "issue": issue_num,
            "item_id": live.item_id or row.get("item_id"),
            "field": field,
            "old_value": old_value,
            "new_value": new_value,
            "owner": owner,
            "repo": repo,
            "project": project,
        }
        if field == PRIORITY_FIELD and row.get("disposition"):
            write_row["disposition"] = row["disposition"]
        append_log_row(lp, write_row)  # B1: before the write, own timestamp, fsynced.

        try:
            write_field(issue_num=issue_num, status_value=str(new_value), project=project, owner=owner, field=field)
        except BoardBackfillError as exc:
            append_log_row(lp, {"ts": _now_iso(), "subcommand": subcommand, "issue": issue_num, "field": field, "outcome": "transition-failed"})
            raise BoardBackfillError(f"stopping run: {exc}") from exc

        if field == PRIORITY_FIELD:
            try:
                post_priority_correction_comment(issue_num=issue_num, value=str(new_value))
            except BoardBackfillError as exc:
                append_log_row(
                    lp,
                    {"ts": _now_iso(), "subcommand": subcommand, "issue": issue_num, "field": field, "new_value": new_value, "outcome": "comment-failed"},
                )
                print(
                    f"  PARTIAL: #{issue_num} Priority WAS written to {new_value}; the corrective "
                    f"comment FAILED ({exc}) — repaired automatically on the next run of this "
                    "script before it plans any new writes.",
                    file=sys.stderr,
                )
                partial_comment_failure = True
                applied_count += 1
                written.append(row)
                break

        append_log_row(lp, {"ts": _now_iso(), "subcommand": subcommand, "issue": issue_num, "field": field, "new_value": new_value, "outcome": "ok"})
        verb_done = "wrote" if field == PRIORITY_FIELD else "moved"
        print(f"  {verb_done} #{issue_num} {field} = {new_value} (from-plan)")
        applied_count += 1
        written.append(row)
        if applied_count < limit and checked_count < max_checks:
            time.sleep(delay)

    return {
        "written": written,
        "skipped": skipped,
        "applied_count": applied_count,
        "checked_count": checked_count,
        "partial_comment_failure": partial_comment_failure,
    }


def cmd_backfill_priority(args: argparse.Namespace) -> int:
    owner = args.owner
    project = args.project
    repo = args.repo
    limit = _resolve_limit(args.limit)
    delay = args.delay

    if args.from_plan:
        return _run_backfill_from_plan(args, owner=owner, project=project, repo=repo, limit=limit, delay=delay)

    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FULL_READ
    before_remaining, _ = assert_min_budget(min_budget, what="backfill-priority (full board read)")

    items = fetch_project_items(owner, project)
    open_numbers = fetch_open_issue_numbers(repo)

    plan = plan_backfill(items, open_numbers, repo)
    writes = plan["writes"]
    unmapped = plan["unmapped"]
    foreign_repo = plan["foreign_repo"]

    mapped_ct = sum(1 for w in writes if w["disposition"] == "mapped")
    floor_fold_ct = sum(1 for w in writes if w["disposition"] == "floor-fold")
    conflict_ct = sum(1 for w in writes if w["disposition"] == "conflict")

    print(f"priority_backfill: backfill-priority — owner={owner} repo={repo} project={project}")
    print(f"  candidates with a Priority write to make: {len(writes)}")
    print(f"    mapped:       {mapped_ct}")
    print(f"    floor-fold:   {floor_fold_ct}  (P4 -> P3, field has no P4 option)")
    print(f"    conflict:     {conflict_ct}  (multiple differing priority labels; higher wins)")
    print(f"  unmapped (priority-looking label, left untouched): {len(unmapped)}")
    if unmapped:
        for u in unmapped[:20]:
            print(f"    #{u['issue']}: {u['labels']}")
        if len(unmapped) > 20:
            print(f"    ... and {len(unmapped) - 20} more")
    _print_foreign_repo(foreign_repo, repo)

    if not args.apply:
        print("  DRY RUN — no writes performed. Pass --apply to write (up to --limit).")
        for w in writes[:limit]:
            print(f"    would set #{w['issue']} Priority = {w['new_value']} ({w['disposition']})")
        if len(writes) > limit:
            print(f"    ... and {len(writes) - limit} more beyond this run's --limit={limit}")
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    # round-2 item 8: the CWD-repo check runs BEFORE the repair pass (not
    # after) -- repairing comments is itself a write (gh_issue.sh comment)
    # that relies on the same CWD-repo binding every other write in this
    # script relies on, so it must clear the same safety check first.
    assert_cwd_matches_repo(repo)
    _board_lock = acquire_board_lock(owner, repo, project)  # B4: held for the rest of this --apply run

    # B4: repair any prior comment-failed rows BEFORE planning new writes,
    # scoped to THIS invocation's (owner, repo, project) only (item 8).
    repaired = repair_comment_failed_rows(owner=owner, repo=repo, project=project)
    if repaired:
        print(f"  repaired {len(repaired)} prior comment-failed row(s): {repaired}")

    to_apply = writes[:limit]
    remaining = len(writes) - len(to_apply)

    if to_apply:
        write_planned_preview(
            planned_log_path("backfill-priority"),
            [
                {
                    "ts": _now_iso(),
                    "subcommand": "backfill-priority",
                    "issue": w["issue"],
                    "field": PRIORITY_FIELD,
                    "old_value": w["old_value"],
                    "new_value": w["new_value"],
                    "disposition": w["disposition"],
                    "owner": owner,
                    "repo": repo,
                    "project": project,
                }
                for w in to_apply
            ],
        )

    lp = log_path("backfill-priority")
    partial_comment_failure = False
    applied_count = 0
    for i, w in enumerate(to_apply):
        row = {
            "ts": _now_iso(),
            "subcommand": "backfill-priority",
            "issue": w["issue"],
            "item_id": w.get("item_id"),
            "field": PRIORITY_FIELD,
            "old_value": w["old_value"],
            "new_value": w["new_value"],
            "disposition": w["disposition"],
            "owner": owner,
            "repo": repo,
            "project": project,
        }
        append_log_row(lp, row)  # B1: written BEFORE the write, own timestamp, fsynced.

        try:
            write_field(issue_num=w["issue"], status_value=w["new_value"], project=project, owner=owner, field=PRIORITY_FIELD)
        except BoardBackfillError as exc:
            append_log_row(
                lp,
                {"ts": _now_iso(), "subcommand": "backfill-priority", "issue": w["issue"], "field": PRIORITY_FIELD, "outcome": "transition-failed"},
            )
            raise BoardBackfillError(f"stopping run: {exc}") from exc

        try:
            post_priority_correction_comment(issue_num=w["issue"], value=w["new_value"])
        except BoardBackfillError as exc:
            append_log_row(
                lp,
                {"ts": _now_iso(), "subcommand": "backfill-priority", "issue": w["issue"], "field": PRIORITY_FIELD, "new_value": w["new_value"], "outcome": "comment-failed"},
            )
            print(
                f"  PARTIAL: #{w['issue']} Priority WAS written to {w['new_value']}; the corrective "
                f"comment FAILED ({exc}) — the issue now shows gh_issue.sh's \"Status → \" comment "
                f"only. Re-post with: bash {GH_ISSUE_SH} comment {w['issue']} --body-file <file "
                f"saying 'Priority field set to {w['new_value']}'>. This is repaired automatically "
                "on the next run of this script before it plans any new writes.",
                file=sys.stderr,
            )
            partial_comment_failure = True
            applied_count = i + 1
            break  # the row's own bookkeeping is done; the run stops here per B4.

        append_log_row(
            lp,
            {"ts": _now_iso(), "subcommand": "backfill-priority", "issue": w["issue"], "field": PRIORITY_FIELD, "new_value": w["new_value"], "outcome": "ok"},
        )
        print(f"  wrote #{w['issue']} Priority = {w['new_value']} ({w['disposition']})")
        applied_count = i + 1
        if i < len(to_apply) - 1:
            time.sleep(delay)

    if partial_comment_failure:
        remaining = len(writes) - applied_count
        print(f"  applied {applied_count} write(s) (last one PARTIAL); {remaining} remaining beyond this run's --limit={limit}")
        if remaining > 0:
            print(_PACING_REMINDER.format(remaining=remaining))
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_PARTIAL_COMMENT_FAILED

    print(f"  applied {applied_count} write(s); {remaining} remaining beyond this run's --limit={limit}")
    if remaining > 0:
        print(_PACING_REMINDER.format(remaining=remaining))
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


def _print_from_plan_selection_summary(selection: dict[str, list[dict[str, Any]]], *, limit: int) -> None:
    """Shared reporting for `--from-plan` (both subcommands): already-done,
    indeterminate, and permanently-skipped (item 6) candidate counts, plus
    how many are queued for this pass's live checks."""
    print(f"  already done (found in this script's own write logs): {len(selection['already_done'])}")
    if selection["indeterminate"]:
        print(f"  indeterminate (intent logged, no outcome recorded — skipped): {sorted(int(r['issue']) for r in selection['indeterminate'])}")
    if selection["permanently_skipped"]:
        print(
            f"  permanently skipped — re-run `plan` to reconsider ({len(selection['permanently_skipped'])} "
            f"candidate(s), each skipped {MAX_SKIPS_BEFORE_PERMANENT}+ times):"
        )
        for r in selection["permanently_skipped"][:20]:
            print(f"    #{r['issue']} {r['field']} (skipped {r['_skip_count']}x)")
        if len(selection["permanently_skipped"]) > 20:
            print(f"    ... and {len(selection['permanently_skipped']) - 20} more")
    print(f"  candidates queued for this pass's live checks (up to --limit={limit} writes): {len(selection['to_check'])}")


def _print_from_plan_skip_report(skipped: list[dict[str, Any]]) -> None:
    """Shared reporting for the live-check-time skip outcomes (grouped by
    kind, since B1/B2's fix round means there are now five distinct
    reasons a candidate can be skipped, never just one)."""
    if not skipped:
        return
    by_outcome: dict[str, list[int]] = {}
    for r in skipped:
        by_outcome.setdefault(r["_outcome"], []).append(int(r["issue"]))
    for outcome in ALL_SKIP_OUTCOMES:
        issues = by_outcome.get(outcome)
        if issues:
            print(f"  {outcome}: {sorted(issues)}")


def _run_backfill_from_plan(
    args: argparse.Namespace, *, owner: str, project: int, repo: str, limit: int, delay: float
) -> int:
    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FROM_PLAN
    before_remaining, _ = assert_min_budget(min_budget, what="backfill-priority --from-plan")

    plan_rows = load_plan_file(Path(args.from_plan), for_subcommand="backfill-priority", owner=owner, repo=repo, project=project)
    selection = select_from_plan_candidates(plan_rows, subcommand="backfill-priority", limit=limit)

    print(f"priority_backfill: backfill-priority --from-plan {args.from_plan} — owner={owner} repo={repo} project={project}")
    print(f"  plan candidates: {len(plan_rows)}")
    _print_from_plan_selection_summary(selection, limit=limit)
    print(f"  remaining in plan beyond this pass: {len(selection['remaining_after'])}")

    if not selection["to_check"]:
        print("  nothing left to do from this plan.")
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    if not args.apply:
        print("  DRY RUN — checking live values for the next candidates, no writes performed.")

    if args.apply:
        assert_cwd_matches_repo(repo)
        _board_lock = acquire_board_lock(owner, repo, project)  # B4: held for the rest of this --apply run
        repaired = repair_comment_failed_rows(owner=owner, repo=repo, project=project)
        if repaired:
            print(f"  repaired {len(repaired)} prior comment-failed row(s): {repaired}")

    project_id = _resolve_project_id(owner, project)

    result = _run_from_plan_candidates(
        to_check=selection["to_check"],
        owner=owner,
        repo=repo,
        project=project,
        subcommand="backfill-priority",
        apply=args.apply,
        limit=limit,
        delay=delay,
        project_node_id=project_id,
    )

    _print_from_plan_skip_report(result["skipped"])

    if not args.apply:
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    remaining = len(selection["remaining_after"])
    if result["partial_comment_failure"]:
        print(f"  applied {result['applied_count']} write(s) (last one PARTIAL); {remaining} remaining beyond this run's --limit={limit}")
        if remaining > 0:
            print(_PACING_REMINDER.format(remaining=remaining))
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_PARTIAL_COMMENT_FAILED

    print(f"  applied {result['applied_count']} write(s); {remaining} remaining beyond this run's --limit={limit}")
    if remaining > 0:
        print(_PACING_REMINDER.format(remaining=remaining))
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


# --------------------------------------------------------------------------
# reset-ready
# --------------------------------------------------------------------------


def plan_reset_ready(items: list[dict[str, Any]], open_numbers: set[int], repo: str) -> dict[str, list[dict[str, Any]]]:
    """Every OPEN issue IN --repo whose Status is Ready #1 or Ready #2,
    ascending by issue number, as (issue, old_status) rows. Also reports
    foreign-repo items (B2), same shape as plan_backfill."""
    candidates = []
    foreign_repo: list[dict[str, Any]] = []
    for item in items:
        content = item.get("content", {})
        if content.get("type") != "Issue":
            continue
        num = content.get("number")
        if num is None:
            continue
        item_repo = _repo_slug_from_item(item)
        if item_repo is not None and item_repo.lower() != repo.lower():
            foreign_repo.append({"issue": int(num), "repo": item_repo})
            continue
        if int(num) not in open_numbers:
            continue
        status = item.get("status")
        if status not in READY_STATUSES:
            continue
        candidates.append({"issue": int(num), "item_id": item.get("id"), "old_value": status})
    candidates.sort(key=lambda r: r["issue"])
    return {"writes": candidates, "foreign_repo": foreign_repo}


def cmd_reset_ready(args: argparse.Namespace) -> int:
    owner = args.owner
    project = args.project
    repo = args.repo
    limit = _resolve_limit(args.limit)
    delay = args.delay

    if args.from_plan:
        return _run_reset_ready_from_plan(args, owner=owner, project=project, repo=repo, limit=limit, delay=delay)

    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FULL_READ
    before_remaining, _ = assert_min_budget(min_budget, what="reset-ready (full board read)")

    items = fetch_project_items(owner, project)
    open_numbers = fetch_open_issue_numbers(repo)

    plan = plan_reset_ready(items, open_numbers, repo)
    candidates = plan["writes"]
    foreign_repo = plan["foreign_repo"]
    r1_ct = sum(1 for r in candidates if r["old_value"] == "Ready #1")
    r2_ct = sum(1 for r in candidates if r["old_value"] == "Ready #2")

    print(f"priority_backfill: reset-ready — owner={owner} repo={repo} project={project}")
    print(f"  Ready #1 items to move to Backlog: {r1_ct}")
    print(f"  Ready #2 items to move to Backlog: {r2_ct}")
    print(f"  total: {len(candidates)}")
    _print_foreign_repo(foreign_repo, repo)

    if not args.apply:
        print("  DRY RUN — no writes performed. Pass --apply to write (up to --limit).")
        for r in candidates[:limit]:
            print(f"    would move #{r['issue']} {r['old_value']} -> {BACKLOG_STATUS}")
        if len(candidates) > limit:
            print(f"    ... and {len(candidates) - limit} more beyond this run's --limit={limit}")
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    assert_cwd_matches_repo(repo)
    _board_lock = acquire_board_lock(owner, repo, project)  # B4: held for the rest of this --apply run

    to_apply = candidates[:limit]
    remaining = len(candidates) - len(to_apply)

    if to_apply:
        write_planned_preview(
            planned_log_path("reset-ready"),
            [
                {
                    "ts": _now_iso(),
                    "subcommand": "reset-ready",
                    "issue": r["issue"],
                    "field": STATUS_FIELD,
                    "old_value": r["old_value"],
                    "new_value": BACKLOG_STATUS,
                    "owner": owner,
                    "repo": repo,
                    "project": project,
                }
                for r in to_apply
            ],
        )

    lp = log_path("reset-ready")
    applied_count = 0
    for i, r in enumerate(to_apply):
        row = {
            "ts": _now_iso(),
            "subcommand": "reset-ready",
            "issue": r["issue"],
            "item_id": r.get("item_id"),
            "field": STATUS_FIELD,
            "old_value": r["old_value"],
            "new_value": BACKLOG_STATUS,
            "owner": owner,
            "repo": repo,
            "project": project,
        }
        append_log_row(lp, row)  # B1

        try:
            write_field(issue_num=r["issue"], status_value=BACKLOG_STATUS, project=project, owner=owner, field=STATUS_FIELD)
        except BoardBackfillError as exc:
            append_log_row(
                lp,
                {"ts": _now_iso(), "subcommand": "reset-ready", "issue": r["issue"], "field": STATUS_FIELD, "outcome": "transition-failed"},
            )
            raise BoardBackfillError(f"stopping run: {exc}") from exc

        append_log_row(
            lp,
            {"ts": _now_iso(), "subcommand": "reset-ready", "issue": r["issue"], "field": STATUS_FIELD, "new_value": BACKLOG_STATUS, "outcome": "ok"},
        )
        print(f"  moved #{r['issue']} {r['old_value']} -> {BACKLOG_STATUS}")
        applied_count = i + 1
        if i < len(to_apply) - 1:
            time.sleep(delay)

    print(f"  applied {applied_count} write(s); {remaining} remaining beyond this run's --limit={limit}")
    if remaining > 0:
        print(_PACING_REMINDER.format(remaining=remaining))
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


def _run_reset_ready_from_plan(
    args: argparse.Namespace, *, owner: str, project: int, repo: str, limit: int, delay: float
) -> int:
    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FROM_PLAN
    before_remaining, _ = assert_min_budget(min_budget, what="reset-ready --from-plan")

    plan_rows = load_plan_file(Path(args.from_plan), for_subcommand="reset-ready", owner=owner, repo=repo, project=project)
    selection = select_from_plan_candidates(plan_rows, subcommand="reset-ready", limit=limit)

    print(f"priority_backfill: reset-ready --from-plan {args.from_plan} — owner={owner} repo={repo} project={project}")
    print(f"  plan candidates: {len(plan_rows)}")
    _print_from_plan_selection_summary(selection, limit=limit)
    print(f"  remaining in plan beyond this pass: {len(selection['remaining_after'])}")

    if not selection["to_check"]:
        print("  nothing left to do from this plan.")
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    if not args.apply:
        print("  DRY RUN — checking live values for the next candidates, no writes performed.")

    if args.apply:
        assert_cwd_matches_repo(repo)
        _board_lock = acquire_board_lock(owner, repo, project)  # B4: held for the rest of this --apply run

    # reset-ready never needs a FIELD id resolved at all (it has no
    # restore-to-empty path); only the PROJECT id, for the live field
    # check's project filter (fetch_live_item_field always filters by
    # project node id, regardless of field). Resolving via the field-
    # requiring combined helper here was itself a B5-shaped bug: it would
    # raise on any board lacking a Priority field even though reset-ready
    # never touches Priority -- use the project-only resolver.
    project_id = _resolve_project_id(owner, project)

    result = _run_from_plan_candidates(
        to_check=selection["to_check"],
        owner=owner,
        repo=repo,
        project=project,
        subcommand="reset-ready",
        apply=args.apply,
        limit=limit,
        delay=delay,
        project_node_id=project_id,
    )

    _print_from_plan_skip_report(result["skipped"])

    if not args.apply:
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    remaining = len(selection["remaining_after"])
    print(f"  applied {result['applied_count']} write(s); {remaining} remaining beyond this run's --limit={limit}")
    if remaining > 0:
        print(_PACING_REMINDER.format(remaining=remaining))
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


# --------------------------------------------------------------------------
# reverse
# --------------------------------------------------------------------------


def load_log_rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise BoardBackfillError(f"log file not found: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise BoardBackfillError(f"{path}:{lineno}: malformed JSON row: {exc}") from exc
            rows.append(row)
    return rows


REVERSIBLE_OUTCOMES = {"ok", "comment-failed", "comment-repaired"}


def _latest_write_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """B1: a real log now interleaves write-intent rows (no "outcome" key)
    with outcome rows ("outcome" key present). Collapse this into one row
    per (issue, field) — the write-intent row's old_value/new_value merged
    with that same write's LATEST outcome. Returns a dict:
        "reversible"    - latest outcome is `ok`/`comment-failed`/
                           `comment-repaired`: the field write itself
                           succeeded and this row is a genuine reverse
                           candidate.
        "indeterminate" - the intent row has NO recorded outcome at all
                           (item 3: a crash between the log write and the
                           outcome row) — the write may or may not have
                           landed; never silently dropped.
    A `transition-failed` outcome is excluded from BOTH lists: nothing was
    written to the board, so there is nothing to reverse and nothing
    indeterminate about it.

    Ordered by (issue, field) key, using the LAST write-intent row seen for
    that key (so a later re-run overwriting an earlier attempt on the same
    issue+field is what gets reversed, not a stale first attempt)."""
    intents: dict[tuple[int, str], dict[str, Any]] = {}
    latest_outcome: dict[tuple[int, str], str] = {}
    seen_intent_without_outcome: set[tuple[int, str]] = set()
    for row in rows:
        issue = row.get("issue")
        field = row.get("field")
        if issue is None or field is None:
            continue
        key = (int(issue), str(field))
        if "outcome" in row:
            latest_outcome[key] = row["outcome"]
            seen_intent_without_outcome.discard(key)
        elif "old_value" in row:
            # A write-intent row (has old_value, even if None) -- a repair
            # row carrying new_value but no old_value never reaches here.
            intents[key] = row
            seen_intent_without_outcome.add(key)

    reversible: list[dict[str, Any]] = []
    indeterminate: list[dict[str, Any]] = []
    for key, intent_row in intents.items():
        outcome = latest_outcome.get(key)
        if key in seen_intent_without_outcome and outcome is None:
            indeterminate.append(intent_row)
        elif outcome in REVERSIBLE_OUTCOMES:
            reversible.append(intent_row)
        # else: outcome == "transition-failed" -- excluded from both lists.

    reversible.sort(key=lambda r: (int(r["issue"]), str(r["field"])))
    indeterminate.sort(key=lambda r: (int(r["issue"]), str(r["field"])))
    return {"reversible": reversible, "indeterminate": indeterminate}


def _repo_and_owner_for_reverse(rows: list[dict[str, Any]]) -> tuple[str | None, str | None, int | None]:
    for row in rows:
        if row.get("repo") and row.get("owner") and row.get("project") is not None:
            return row["repo"], row["owner"], row["project"]
    return None, None, None


def restore_to_empty(*, field: str, item_id: str, project_id: str, field_id: str) -> None:
    """The ONE write in this script that does not go through `gh_issue.sh`.

    Why: `gh_issue.sh transition` writes a NAMED option value to a single-
    select field or a text value to a text field — it has no verb for
    "clear this field back to empty", because clearing is not a normal
    board-hygiene operation any of its callers need. `backfill-priority`'s
    old_value is ALWAYS empty (that is the entire premise of a "backfill" —
    the field had no prior value), so reversing it requires clearing the
    field, not writing some other value to it. `gh project item-edit --clear
    --id <item-id> --field-id <field-id> --project-id <project-id>` is the
    only `gh` verb that does this. It is scoped as narrowly as possible: it
    is called ONLY from `reverse`, ONLY for a row whose recorded old_value is
    None, and takes exactly the three IDs needed for one field on one item —
    it can never write an arbitrary value, only clear one.

    HARD GUARD (round-2 item 4, also flagged independently by the security
    reviewer of the board-steward grant): this script only ever intends to
    clear the PRIORITY field (only `backfill-priority` rows ever have an
    empty old_value — `reset-ready` always has a real prior Status). `field`
    is REQUIRED and checked here, at the actual write call, rather than
    trusted from the caller alone — a `reset-ready`-shaped row (or any
    hand-edited log row) with `field != "Priority"` and `old_value: null` is
    refused outright, nothing is cleared. This is defense in depth on top of
    the caller-side check in `cmd_reverse`, not a replacement for it.
    """
    if field != PRIORITY_FIELD:
        raise BoardBackfillError(
            f"restore_to_empty called for field {field!r}, not {PRIORITY_FIELD!r} — refusing to "
            "clear a non-Priority field; this script never intends to clear anything but Priority "
            "(a Status row should never have an empty old_value)"
        )
    cmd = [GH_BIN, "project", "item-edit", "--id", item_id, "--field-id", field_id, "--project-id", project_id, "--clear"]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise BoardBackfillError(f"gh project item-edit --clear failed for item {item_id}: {proc.stderr.strip()}")


def _resolve_project_id(owner: str, project: int) -> str:
    """Resolve just the project's own node id via `gh project view`. Split
    out from the combined field-id resolver below (B5, 2026-09-20 fix
    round): a caller that only needs the project id (e.g. the LIVE FIELD
    CHECK's project-filter, needed for EVERY board regardless of which
    field it carries) must never be forced through a field-name lookup that
    can raise on a board that simply doesn't have that field — at HEAD
    before this split, `cmd_reverse` called the combined resolver just to
    get the project id and it raised on a board with no Priority field,
    breaking `reverse` of a `reset-ready` log outright (a regression: the
    project id was previously resolved unconditionally while the Priority
    FIELD id was resolved only inside the one branch that actually needed
    it — this split restores that separation)."""
    proc = _run([GH_BIN, "project", "view", str(project), "--owner", owner, "--format", "json"])
    stdout = _read_or_raise(proc, what="gh project view")
    try:
        proj_data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BoardBackfillError(f"gh project view returned unparsable JSON: {exc}") from exc
    project_id = proj_data.get("id")
    if not project_id:
        raise BoardBackfillError(f"gh project view returned no id for project #{project} (owner {owner!r})")
    return str(project_id)


def _resolve_field_id(owner: str, project: int, field_name: str) -> str:
    """Resolve just the named field's node id via `gh project field-list`.
    Split out alongside `_resolve_project_id` (B5) so a caller needing ONLY
    the field id never pays for (or depends on) the project-id call, and
    vice versa."""
    proc = _run([GH_BIN, "project", "field-list", str(project), "--owner", owner, "--format", "json"])
    stdout = _read_or_raise(proc, what="gh project field-list")
    try:
        field_data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise BoardBackfillError(f"gh project field-list returned unparsable JSON: {exc}") from exc
    field_id = None
    for f in field_data.get("fields", []):
        if f.get("name") == field_name:
            field_id = f.get("id")
            break
    if not field_id:
        raise BoardBackfillError(f"field {field_name!r} not found on project #{project} (owner {owner!r})")
    return str(field_id)


def _resolve_project_and_field_ids(owner: str, project: int, field_name: str) -> tuple[str, str]:
    """Resolve (project_id, field_id) for --clear, mirroring gh_issue.sh's
    own resolution (`gh project view` then `gh project field-list`). Thin
    composition of the two split-out resolvers above — kept as a single
    call for `restore_to_empty`'s caller, which always needs both."""
    return _resolve_project_id(owner, project), _resolve_field_id(owner, project, field_name)


_LIVE_FIELD_QUERY = """
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
"""

_LIVE_FIELD_PAGE_SIZE = 50  # must match the `first: 50` literal in _LIVE_FIELD_QUERY above


class LiveField(NamedTuple):
    """The LIVE FIELD CHECK's result (2026-09-20 fix round, root cause of
    B1/B2): distinguishes "field genuinely empty" from every "I don't know"
    condition, which a bare `(item_id, value)` pair could not — see the
    RESULT TYPE section of the module docstring for the full rationale and
    the list of conditions this collapses.
        found      - a project item for this issue on THIS project was
                     found at all. False means: no matching project item,
                     the issue is on no project, or `node` was null
                     (deleted issue). When False, `item_id`/`value` are
                     always None and must never be read.
        item_id    - the live project-item node id, or None if not found.
        value      - the field's current value (None means genuinely
                     empty), meaningful ONLY when found=True, truncated=False,
                     and is_open is not False.
        is_open    - the issue's live state: True (OPEN), False (any other
                     state), or None (state could not be determined, e.g.
                     the issue view call did not return one — treated the
                     same as False by every caller: never assume open).
        truncated  - True if the query returned exactly _LIVE_FIELD_PAGE_SIZE
                     project-item nodes and NONE of them matched this
                     project — the real match may be one of the un-returned
                     nodes past the page boundary, so this must never be
                     read as "not on this project" (found=False) OR as
                     "found, value is whatever we saw" -- it is its own
                     distinct "don't know" state.
    """

    found: bool
    item_id: str | None
    value: Any
    is_open: bool | None
    truncated: bool


def fetch_live_item_field(*, issue_num: int, field: str, project_node_id: str) -> LiveField:
    """The LIVE FIELD CHECK (module docstring): resolves the CURRENT
    project-item id, CURRENT value of `field`, and CURRENT open/closed state
    for `issue_num`, via ONE single-issue GraphQL round trip (plus the `gh
    issue view` node-id + state resolve) — modeled directly on gh_issue.sh's
    own `_do_transition` item-id resolution (gh_issue.sh:334), extended with
    `fieldValueByName` so a single query returns both the item id and the
    field value. Used by `--from-plan` (to compare against a plan row's
    `old_value` before writing) and by `reverse` (in place of a full board
    read — see B3/B2). Returns a `LiveField` — NEVER a bare value — so the
    caller can never conflate "field is empty" with "issue not found" /
    "issue not open" / "read looked truncated", the root cause this fix
    round closes (B1/B2). Raises BoardBackfillError (or
    RateLimitedReadError) on any hard read failure (including a GraphQL
    `errors` array in an otherwise-200 response) — never silently returns a
    guessed value."""
    proc = _run([GH_BIN, "issue", "view", str(issue_num), "--json", "id,url,state"])
    stdout = _read_or_raise(proc, what=f"gh issue view #{issue_num}")
    try:
        issue_data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        if _looks_rate_limited(stdout):
            raise RateLimitedReadError(
                f"gh issue view #{issue_num} returned rate-limit-shaped, unparsable output — "
                f"aborting before any write (nothing was written): {stdout.strip()[:200]}"
            ) from exc
        raise BoardBackfillError(f"gh issue view #{issue_num} returned unparsable JSON: {exc}") from exc
    issue_node_id = issue_data.get("id")
    if not issue_node_id:
        raise BoardBackfillError(f"gh issue view #{issue_num} returned no node id — issue may not exist")
    # `gh issue view --json state` returns the string "OPEN"/"CLOSED" (never
    # absent for a resolvable issue) -- anything other than exactly "OPEN"
    # is treated as not-open, including an unexpected/missing value: never
    # assume open on ambiguous data.
    is_open = issue_data.get("state") == "OPEN"

    proc = _run([GH_BIN, "api", "graphql", "-f", f"query={_LIVE_FIELD_QUERY}", "-f", f"id={issue_node_id}", "-f", f"field={field}"])
    stdout = _read_or_raise(proc, what=f"gh api graphql (live field check) #{issue_num}")
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        if _looks_rate_limited(stdout):
            raise RateLimitedReadError(
                f"live field check for #{issue_num} returned rate-limit-shaped, unparsable output — "
                f"aborting before any write (nothing was written): {stdout.strip()[:200]}"
            ) from exc
        raise BoardBackfillError(f"live field check for #{issue_num} returned unparsable JSON: {exc}") from exc

    # Finding 11: a partial GraphQL response ("data" AND "errors" both
    # present, HTTP 200) must be a read failure, never silently treated as
    # if the (possibly null/incomplete) "data" were trustworthy.
    if data.get("errors"):
        raise BoardBackfillError(f"live field check for #{issue_num} returned GraphQL errors: {data['errors']}")

    node = (data.get("data") or {}).get("node") or {}
    nodes = ((node.get("projectItems") or {}).get("nodes")) or []
    # Truncation guard (mirrors fetch_project_items/fetch_open_issue_numbers'
    # existing suspected-truncation refusal): if the page came back FULL and
    # none of the returned nodes matched this project, the real match may be
    # sitting past the page boundary -- this is a distinct "don't know",
    # never "not found".
    page_is_full = len(nodes) >= _LIVE_FIELD_PAGE_SIZE
    for item_node in nodes:
        proj = item_node.get("project") or {}
        if proj.get("id") != project_node_id:
            continue
        item_id = item_node.get("id")
        fv = item_node.get("fieldValueByName")
        if fv is None:
            live_value: Any = None
        elif "name" in fv:
            live_value = fv["name"]
        elif "text" in fv:
            live_value = fv["text"]
        else:
            live_value = None
        return LiveField(found=True, item_id=item_id, value=live_value, is_open=is_open, truncated=False)
    if page_is_full:
        return LiveField(found=False, item_id=None, value=None, is_open=is_open, truncated=True)
    return LiveField(found=False, item_id=None, value=None, is_open=is_open, truncated=False)


# B2 (round 2): the three-way reverse decision. A binary "already reversed?"
# check silently overwrites any deliberate human edit made on the board
# after the forward write landed (proven live: an operator hand-set a value,
# a naive reverse clobbered it because it only checked "does the live value
# equal old_value"). The correct question has THREE possible answers:
DECISION_REVERSE = "reverse"  # live == new_value: this script's own write is still there -> undo it
DECISION_ALREADY_REVERSED = "already-reversed"  # live == old_value: nothing to do, safe to skip (B3 resumability)
DECISION_CHANGED_SINCE_WRITE = "changed-since-write"  # live == neither: a human (or something else) touched it since
DECISION_INDETERMINATE = "indeterminate"  # no outcome row recorded -- the write may or may not have landed (item 3)


def classify_reverse_row(*, live_value: Any, old_value: Any, new_value: Any) -> str:
    """Pure decision function (unit-testable without a subprocess): given the
    live board value and this row's recorded old_value/new_value, returns one
    of the DECISION_* constants above. `live_value == new_value` is checked
    FIRST and `== old_value` SECOND, so a degenerate row where old_value
    happens to equal new_value (never produced by this script, but not
    provably impossible from a hand-edited log) is treated as "still needs
    reversing" rather than "already reversed" -- the safer reading, since
    "reverse" is always a safe no-op-shaped write when live already equals
    the target, while silently skipping a row that might not actually be
    reversed yet is not."""
    if live_value == new_value:
        return DECISION_REVERSE
    if live_value == old_value:
        return DECISION_ALREADY_REVERSED
    return DECISION_CHANGED_SINCE_WRITE


def cmd_reverse(args: argparse.Namespace) -> int:
    log_file = Path(args.log)
    limit = _resolve_limit(args.limit)
    delay = args.delay
    force_changed = args.force_changed
    include_indeterminate = args.include_indeterminate

    rows = load_log_rows(log_file)

    # item 10 (double-reverse): a `reverse` log's own rows carry
    # subcommand="reverse" -- refuse reversing a reverse log outright, with a
    # clear message, rather than silently chaining un-dos of un-dos.
    if any(row.get("subcommand") == "reverse" for row in rows):
        raise BoardBackfillError(
            f"{log_file} is itself a `reverse` log (it contains rows with subcommand=\"reverse\") "
            "-- reversing a reverse is refused. If you need to undo a reverse run, reverse the "
            "ORIGINAL backfill-priority/reset-ready log again (a second reverse of the same "
            "original log will re-apply the original write, since the board should be back at "
            "old_value)."
        )

    classified = _latest_write_rows(rows)
    reversible = classified["reversible"]
    indeterminate = classified["indeterminate"]

    repo, owner, project = _repo_and_owner_for_reverse(rows)
    if repo is None or owner is None or project is None:
        raise BoardBackfillError("log rows carry no repo/owner/project — cannot reverse without a target board")

    # item 8 (fix round, 2026-09-20): reverse no longer performs a full
    # board read (see below) -- its default budget floor is the same
    # FROM-PLAN default as the other per-issue-live-check paths, not the
    # full-read default.
    min_budget = args.min_budget if args.min_budget is not None else DEFAULT_MIN_BUDGET_FROM_PLAN
    before_remaining, _ = assert_min_budget(min_budget, what="reverse")

    # 2026-09-20: reverse's candidate set already comes from the LOG it is
    # given, never from the board -- so a full `gh project item-list` read
    # was always more than this needed. Resolve the project's node id ONCE
    # (one call, PROJECT-ONLY resolver -- B5 fix round: the combined
    # project+field resolver used here at HEAD raised on any board lacking a
    # Priority field, breaking `reverse` of a `reset-ready` log outright,
    # since a reset-ready log never needs the Priority field to exist at
    # all) and, for each candidate, use the same per-issue LIVE FIELD CHECK
    # `--from-plan` uses (see fetch_live_item_field / module docstring) in
    # place of a board-wide read + client-side filter.
    project_node_id = _resolve_project_id(owner, project)

    def _live_lookup(issue_num: int, field: str) -> LiveField:
        return fetch_live_item_field(issue_num=issue_num, field=field, project_node_id=project_node_id)

    # B2 (round 2): three-way classification against the live board, never a
    # binary "already reversed?" check -- see classify_reverse_row.
    # Fix-round B2 (2026-09-20): a live read that comes back "I don't know"
    # (not found on this project, or a suspected-truncated page) must NEVER
    # reach classify_reverse_row at all -- that function only ever sees a
    # genuinely observed value. Those rows are pulled out as `unreadable`
    # BEFORE classification, distinct from `changed-since-write` (which
    # means the value WAS read and differs). A CLOSED issue is deliberately
    # NOT pulled out here: undoing a write must not be blocked merely
    # because the issue was closed afterwards -- classify_reverse_row still
    # decides reverse/already-reversed/changed-since-write from the value
    # exactly as before, so closing an issue never by itself prevents (or
    # forces) a reversal.
    to_reverse: list[dict[str, Any]] = []
    already_reversed_ct = 0
    changed_since_write: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    live_item_ids: dict[int, str] = {}
    for r in reversible:
        live = _live_lookup(int(r["issue"]), str(r["field"]))
        if not live.found:
            unreadable.append({**r, "_reason": "truncated" if live.truncated else "not-found"})
            continue
        live_item_ids[int(r["issue"])] = str(live.item_id)
        decision = classify_reverse_row(live_value=live.value, old_value=r["old_value"], new_value=r.get("new_value"))
        if decision == DECISION_REVERSE:
            to_reverse.append(r)
        elif decision == DECISION_ALREADY_REVERSED:
            already_reversed_ct += 1
        else:  # DECISION_CHANGED_SINCE_WRITE
            changed_since_write.append({**r, "_live_value": live.value})

    # item 3: indeterminate rows are classified the same way IF the caller
    # opts in via --include-indeterminate (never automatically, since we do
    # not know for certain the write landed) -- live == new_value -> treat as
    # written, offer to reverse; live == old_value -> never landed, skip;
    # anything else -> changed-since-write, same as a reversible row.
    indeterminate_to_reverse: list[dict[str, Any]] = []
    indeterminate_never_landed = 0
    indeterminate_changed: list[dict[str, Any]] = []
    if include_indeterminate:
        for r in indeterminate:
            live = _live_lookup(int(r["issue"]), str(r["field"]))
            if not live.found:
                unreadable.append({**r, "_reason": "truncated" if live.truncated else "not-found"})
                continue
            live_item_ids[int(r["issue"])] = str(live.item_id)
            decision = classify_reverse_row(live_value=live.value, old_value=r["old_value"], new_value=r.get("new_value"))
            if decision == DECISION_REVERSE:
                indeterminate_to_reverse.append(r)
            elif decision == DECISION_ALREADY_REVERSED:
                indeterminate_never_landed += 1
            else:
                indeterminate_changed.append({**r, "_live_value": live.value})

    # A row a human has explicitly force-accepted travels through to_reverse
    # too, but ONLY the ones actually named by --force-changed (issue
    # numbers) -- never a blanket "force everything changed-since-write".
    forced: list[dict[str, Any]] = []
    still_refused: list[dict[str, Any]] = []
    if force_changed:
        forced_numbers = set(force_changed)
        for r in changed_since_write:
            if int(r["issue"]) in forced_numbers:
                forced.append(r)
            else:
                still_refused.append(r)
        for r in indeterminate_changed:
            if int(r["issue"]) in forced_numbers:
                forced.append(r)
            else:
                still_refused.append(r)
    else:
        still_refused = list(changed_since_write) + list(indeterminate_changed)

    to_process = to_reverse + indeterminate_to_reverse + forced

    print(f"priority_backfill: reverse — log={log_file}")
    print(f"  rows in log: {len(rows)}")
    print(f"  reversible write rows (outcome ok/comment-failed/comment-repaired): {len(reversible)}")
    if indeterminate:
        print(f"  {len(indeterminate)} row(s) have no recorded outcome — the write may or may not have landed; check these issues: {sorted(int(r['issue']) for r in indeterminate)}")
        if not include_indeterminate:
            print("    (pass --include-indeterminate to classify these against the live board)")
    print(f"  already reversed (live value matches old_value; skipped): {already_reversed_ct + indeterminate_never_landed}")
    if changed_since_write or indeterminate_changed:
        all_changed = changed_since_write + indeterminate_changed
        print(f"  changed-since-write (skipped — live value matches neither old_value nor new_value): {len(all_changed)}")
        for r in all_changed[:20]:
            print(f"    #{r['issue']} {r['field']}: expected old={r['old_value']!r} or new={r.get('new_value')!r}, live={r['_live_value']!r}")
        if len(all_changed) > 20:
            print(f"    ... and {len(all_changed) - 20} more")
        if not force_changed:
            print("    (pass --force-changed <issue#> [<issue#>...] to overwrite a specific one anyway)")
    if forced:
        print(f"  force-changed (will be overwritten despite a live value that matched neither old nor new): {sorted(int(r['issue']) for r in forced)}")
    if still_refused:
        print(f"  still refused (not named by --force-changed): {sorted(int(r['issue']) for r in still_refused)}")
    if unreadable:
        print(f"  unreadable (live read could not confirm this item — never a write, distinct from changed-since-write): {len(unreadable)}")
        for r in unreadable[:20]:
            print(f"    #{r['issue']} {r['field']}: {r['_reason']}")
        if len(unreadable) > 20:
            print(f"    ... and {len(unreadable) - 20} more")
    print(f"  remaining to restore: {len(to_process)}")

    if not args.apply:
        print("  DRY RUN — no writes performed. Pass --apply to write (up to --limit).")
        for r in to_process[:limit]:
            if r["old_value"] is None:
                print(f"    would CLEAR #{r['issue']} {r['field']} (was {r.get('new_value')!r}) via gh project item-edit --clear")
            else:
                print(f"    would restore #{r['issue']} {r['field']} = {r['old_value']} (was {r.get('new_value')!r})")
        if len(to_process) > limit:
            print(f"    ... and {len(to_process) - limit} more beyond this run's --limit={limit}")
        _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
        return EXIT_OK

    assert_cwd_matches_repo(repo)
    _board_lock = acquire_board_lock(str(owner), str(repo), int(project))  # B4: held for the rest of this --apply run

    to_apply = to_process[:limit]
    remaining = len(to_process) - len(to_apply)

    # project_node_id was already resolved above for the live field checks;
    # restore_to_empty needs the Priority FIELD id specifically, resolved
    # once here only if this batch actually needs a clear -- via the
    # field-only resolver (B5 split) so this never re-fetches the project id.
    field_id_priority = None
    if any(r["old_value"] is None for r in to_apply):
        field_id_priority = _resolve_field_id(owner, project, PRIORITY_FIELD)

    if to_apply:
        write_planned_preview(
            planned_log_path("reverse"),
            [
                {
                    "ts": _now_iso(),
                    "subcommand": "reverse",
                    "issue": r["issue"],
                    "field": r["field"],
                    "old_value": r.get("new_value"),
                    "new_value": r["old_value"],
                    "owner": owner,
                    "repo": repo,
                    "project": project,
                    "reversed_of": str(log_file),
                }
                for r in to_apply
            ],
        )

    lp = log_path("reverse")
    applied_count = 0
    for i, r in enumerate(to_apply):
        row = {
            "ts": _now_iso(),
            "subcommand": "reverse",
            "issue": r["issue"],
            "field": r["field"],
            "old_value": r.get("new_value"),
            "new_value": r["old_value"],
            "owner": owner,
            "repo": repo,
            "project": project,
            "reversed_of": str(log_file),
        }
        append_log_row(lp, row)  # B1

        try:
            if r["old_value"] is None:
                # item 5: use the LIVE item id for (repo, issue), never the
                # id recorded in the log -- a stale logged id could point at
                # a since-recreated or since-moved item. Reuses the id
                # captured during classification above (one live field check
                # per candidate already resolved it); falls back to a fresh
                # per-issue lookup only if that candidate's id was somehow
                # never captured (e.g. it was not on the board at
                # classification time either).
                live_item_id = live_item_ids.get(int(r["issue"]))
                if live_item_id is None:
                    fresh = _live_lookup(int(r["issue"]), str(r["field"]))
                    live_item_id = fresh.item_id
                if live_item_id is None:
                    raise BoardBackfillError(
                        f"#{r['issue']} is not present on the live board for --repo {repo} — "
                        "refusing to clear by a stale logged item id"
                    )
                restore_to_empty(field=str(r["field"]), item_id=str(live_item_id), project_id=str(project_node_id), field_id=str(field_id_priority))
            else:
                write_field(issue_num=int(r["issue"]), status_value=str(r["old_value"]), project=int(project), owner=str(owner), field=str(r["field"]))
        except BoardBackfillError as exc:
            append_log_row(lp, {"ts": _now_iso(), "subcommand": "reverse", "issue": r["issue"], "field": r["field"], "outcome": "transition-failed"})
            raise BoardBackfillError(f"stopping run: {exc}") from exc

        append_log_row(lp, {"ts": _now_iso(), "subcommand": "reverse", "issue": r["issue"], "field": r["field"], "new_value": r["old_value"], "outcome": "ok"})
        if r["old_value"] is None:
            print(f"  cleared #{r['issue']} {r['field']} (was {r.get('new_value')})")
        else:
            print(f"  restored #{r['issue']} {r['field']} = {r['old_value']} (was {r.get('new_value')})")
        applied_count = i + 1
        if i < len(to_apply) - 1:
            time.sleep(delay)

    print(f"  applied {applied_count} write(s); {remaining} remaining beyond this run's --limit={limit}")
    if remaining > 0:
        print(_PACING_REMINDER.format(remaining=remaining))
    _print_graphql_cost(before_remaining, min_budget_for_final_check=min_budget)
    return EXIT_OK


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------


def _resolve_limit(requested: int) -> int:
    if requested > HARD_MAX_LIMIT:
        raise BoardBackfillError(f"--limit {requested} exceeds the hard max of {HARD_MAX_LIMIT}")
    if requested < 1:
        raise BoardBackfillError("--limit must be >= 1")
    return requested


def _repo_slug_from_item(item: dict[str, Any]) -> str | None:
    """Extract 'owner/repo' from an item's repository URL
    (e.g. "https://github.com/example-org/ExampleApp")."""
    repo_url = item.get("repository") or item.get("content", {}).get("repository")
    if not repo_url:
        return None
    parts = str(repo_url).rstrip("/").split("/")
    if len(parts) < 2:
        return None
    return f"{parts[-2]}/{parts[-1]}"


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


class _NormalizedExitParser(argparse.ArgumentParser):
    """argparse's own `error()` calls `sys.exit(2)` directly, bypassing
    main()'s try/except entirely and producing an undocumented exit code
    (round-2 item 6). Rather than adding and documenting a THIRD distinct
    "argument error" exit code alongside 1/3/4, this normalizes every
    argparse-level failure (missing required flag, mutually-exclusive
    conflict, bad --project int, etc.) to EXIT_ERROR (1) -- the module
    docstring's EXIT CODES block already says "1 ... an argument error", so
    this makes that claim true for EVERY argument error, not just the ones
    raised after parsing succeeds."""

    def error(self, message: str) -> None:  # noqa: D102 - argparse's own signature
        self.print_usage(sys.stderr)
        raise BoardBackfillError(f"{self.prog}: error: {message}", exit_code=EXIT_ERROR)


def _min_budget_type(raw: str) -> int:
    """argparse `type=` for `--min-budget` (item 10): 0 is a valid,
    deliberate way to waive the gate (see assert_min_budget's WAIVED
    print); a NEGATIVE value has no sane meaning (a budget floor below zero
    refuses nothing a 0 floor doesn't already refuse, and silently
    accepting one masks what is almost certainly a typo) and is rejected
    here, at parse time, via argparse's own int() conversion plus an
    explicit range check -- raising plain ValueError is what argparse's
    `type=` protocol expects; it turns this into the SAME normalized-to-1
    argument-error path as every other bad flag (_NormalizedExitParser)."""
    value = int(raw)  # raises ValueError on a non-integer, same as bare `type=int` would
    if value < 0:
        raise ValueError(f"--min-budget must be >= 0 (got {value})")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = _NormalizedExitParser(
        prog="priority_backfill.py",
        description="Board-metadata backfill/reset helper for a GitHub Project (product-agnostic).",
    )
    # parser_class ensures every SUBparser (backfill-priority/reset-ready/
    # reverse) also raises BoardBackfillError on its own argument errors,
    # not just the top-level parser -- argparse does not inherit this
    # automatically from the parent.
    sub = parser.add_subparsers(dest="subcommand", required=True, parser_class=_NormalizedExitParser)

    def _add_common(p: argparse.ArgumentParser) -> None:
        run_mode = p.add_mutually_exclusive_group()
        run_mode.add_argument("--apply", action="store_true", help="Perform writes (default: dry run).")
        run_mode.add_argument("--dry-run", action="store_true", help="Explicitly request dry-run (this is already the default).")
        p.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help=f"Max mutations this run (default {DEFAULT_LIMIT}, hard max {HARD_MAX_LIMIT}).")
        p.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS, help=f"Seconds to sleep between writes (default {DEFAULT_DELAY_SECONDS}).")
        p.add_argument(
            "--min-budget",
            type=_min_budget_type,
            default=None,
            metavar="N",
            help="Refuse (exit 4) if the live remaining GraphQL budget is below N before this run's "
            f"reads/writes begin. Default {DEFAULT_MIN_BUDGET_FULL_READ} for a full-board-read run, "
            f"{DEFAULT_MIN_BUDGET_FROM_PLAN} for a --from-plan run (see BUDGET AWARENESS). 0 waives "
            "the gate entirely (a WAIVED line is printed); negative values are rejected.",
        )

    def _add_from_plan(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--from-plan",
            metavar="FILE",
            default=None,
            help="Run against a plan file written by `plan --for <this-subcommand>` instead of "
            "performing a full board read — see FROM-PLAN in the module docstring. Still performs "
            "ONE live field check per candidate immediately before each write.",
        )

    p_plan = sub.add_parser("plan", help="Perform the one full board read and write a reusable plan file (writes NOTHING to GitHub).")
    p_plan.add_argument("--for", dest="for_subcommand", required=True, choices=["backfill-priority", "reset-ready"], help="Which subcommand's candidates to compute and save.")
    p_plan.add_argument("--owner", required=True, help="GitHub org/user that owns the project.")
    p_plan.add_argument("--repo", required=True, help="OWNER/NAME of the repository whose issues to plan for (required — see B2).")
    p_plan.add_argument("--project", required=True, type=int, help="Project number.")
    p_plan.add_argument(
        "--min-budget",
        type=_min_budget_type,
        default=None,
        metavar="N",
        help=f"Refuse (exit 4) if the live remaining GraphQL budget is below N. Default {DEFAULT_MIN_BUDGET_FULL_READ}. "
        "0 waives the gate entirely (a WAIVED line is printed); negative values are rejected.",
    )
    p_plan.set_defaults(func=cmd_plan)

    p_backfill = sub.add_parser("backfill-priority", help="Backfill the Priority field from priority labels.")
    p_backfill.add_argument("--owner", required=True, help="GitHub org/user that owns the project.")
    p_backfill.add_argument("--repo", required=True, help="OWNER/NAME of the repository whose issues to backfill (required — see B2).")
    p_backfill.add_argument("--project", required=True, type=int, help="Project number.")
    _add_common(p_backfill)
    _add_from_plan(p_backfill)
    p_backfill.set_defaults(func=cmd_backfill_priority)

    p_reset = sub.add_parser("reset-ready", help='Move every "Ready #1"/"Ready #2" open item back to Backlog.')
    p_reset.add_argument("--owner", required=True, help="GitHub org/user that owns the project.")
    p_reset.add_argument("--repo", required=True, help="OWNER/NAME of the repository whose issues to reset (required — see B2).")
    p_reset.add_argument("--project", required=True, type=int, help="Project number.")
    _add_common(p_reset)
    _add_from_plan(p_reset)
    p_reset.set_defaults(func=cmd_reset_ready)

    p_reverse = sub.add_parser("reverse", help="Replay a backfill/reset log backwards.")
    p_reverse.add_argument("--log", required=True, help="Path to a jsonl log written by backfill-priority or reset-ready.")
    p_reverse.add_argument(
        "--force-changed",
        nargs="+",
        type=int,
        metavar="ISSUE#",
        default=[],
        help="Issue number(s) to overwrite anyway even though their live value matches neither "
        "old_value nor new_value (changed-since-write — see B2). Never a blanket force; names "
        "each issue explicitly.",
    )
    p_reverse.add_argument(
        "--include-indeterminate",
        action="store_true",
        help="Also classify rows with no recorded outcome (a crash between the log write and the "
        "outcome row) against the live board, instead of leaving them out entirely (see item 3).",
    )
    _add_common(p_reverse)
    p_reverse.set_defaults(func=cmd_reverse)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except BoardBackfillError as exc:
        print(f"priority_backfill: ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    try:
        return args.func(args)
    except BoardBackfillError as exc:
        print(f"priority_backfill: ERROR: {exc}", file=sys.stderr)
        return exc.exit_code
    except Exception as exc:  # noqa: BLE001 - item 5: never a raw traceback to the caller
        print(f"priority_backfill: ERROR: unexpected failure: {exc}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
