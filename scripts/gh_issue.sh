#!/usr/bin/env bash
# gh_issue.sh — GitHub issue LIFECYCLE helper (dev runtime, product-agnostic).
#
# Turns the multi-step "create / keep-live / resolve" issue discipline into one
# command so agents stop forgetting the steps. The PRODUCT-specific field
# taxonomy (priority values, story points, label sets, the Resolution template)
# lives in each repo's engineering standards — pass those in via flags/labels.
#
# A --project N (with matching/absent --owner) naming a board listed in
# ~/.claude/knowledge/protected_boards.json is DENIED by the PreToolUse gate
# chain's gate 5b (protected_board_guard.py) — this script never special-cases
# it itself; see that gate's own docstring / GH #5490.
#
# Subcommands:
#   create   --title T --body-file F [--label L]... [--assignee A] [--milestone M]
#              [--force-new] [--related <num>]
#              [--triage S [--project N] --owner O [--field F]]
#              Create an issue. Pass every triage label with repeated --label.
#              DEDUP GUARD: before creating, searches OPEN issues for plausible
#              overlap on the title's significant words. If matches are found,
#              refuses to create and prints them to stderr — unless:
#                --force-new     skips the duplicate search entirely (unchanged
#                                from prior behavior — it never calls
#                                `gh issue list` at all) and creates anyway,
#                                confirming this is genuinely a new/distinct
#                                issue. Logs one line to stderr (the script's
#                                existing "gh_issue: ..." bypass-notice
#                                convention) saying the duplicate check was
#                                SKIPPED because --force-new was given — this
#                                is unconditional and does not depend on
#                                whether the (never-run) search would have
#                                failed or matched; running the search first
#                                just to learn that would cost a real GitHub
#                                GraphQL call on every forced create for no
#                                benefit.
#                --related <num> posts a cross-reference comment on issue <num>
#                                instead of creating a new issue (exits 0, no
#                                new issue created), SHORT-CIRCUITING before
#                                the dedup search even runs, by design -- a
#                                --related call creates no issue, so there is
#                                nothing to dedupe-check. Use this to fold a
#                                finding into an existing issue.
#              WITHOUT --force-new, a FAILED dedup search (gh error, no
#              network, auth failure, rate limit) REFUSES creation (#5827,
#              2026-09-20) -- "the search failed" and "the search found
#              nothing" must never be indistinguishable, since the latter is
#              what lets a duplicate slip through unchecked. Prints gh's own
#              error text (truncated to ~500 bytes, so an oversized gh stderr
#              payload never blows up the refusal message), says to retry, and
#              names the escape hatch (--force-new, which — per above — skips
#              the search on the retry too, not just tolerates its failure).
#              The fail-closed signal is the search command's real exit
#              status, never the presence of `mktemp` on PATH -- `mktemp` is
#              OPTIONAL for `create` (used only to capture nicer error TEXT;
#              its absence degrades the error text to empty/generic, never to
#              a false "the search failed" for a search that actually ran and
#              succeeded). This matters because `create` is a hot path that
#              unattended launchd/cron jobs run under a minimal PATH that can
#              genuinely lack `mktemp` -- unlike `resolve --evidence-repo` /
#              `dispose duplicate-of` below, which still require a real
#              `mktemp` (used there only for an already-rarer throwaway
#              git-repo check, not on this hot path).
#              --triage S (optional): after a successful create, runs the exact
#              same board-transition logic 'transition' below uses (same
#              --project/--owner/--field flags, same comment-then-field-write
#              order, same FAIL LOUD contract on a field-write error) against
#              the issue this call just created — so filing + triage is one
#              call instead of two. Backward compatible: omitting --triage
#              leaves 'create' exactly as it always behaved (create only, no
#              transition attempted). --triage is validated BEFORE the issue
#              is created whenever --project is given: an S that is not one of
#              that project's field's real live options refuses with the
#              options list and creates NOTHING (the same refusal
#              'transition' would give, just moved earlier so a typo'd status
#              never leaves an issue filed-but-untriaged behind it). Without
#              --project, S is unvalidated free text, identical to a bare
#              'transition' call with no --project — same COMMENT-ONLY warning
#              on stderr, same reasoning: this script never hardcodes a
#              status domain, since it is product-agnostic by design.
#   comment  <num> --body-file F
#              Post a progress/update comment (keep board state live).
#   transition <num> --status S [--project N] --owner O [--field F]
#              Post a status comment (best-effort, always attempted first), then
#              — IF --project is given — actually WRITE the project board's
#              Status field via `gh project item-edit` (resolving the project's
#              node ID AND the target field's ID/type/options in ONE GraphQL
#              query — `repositoryOwner(login:...){ ... on ProjectV2Owner {
#              projectV2(number:...){ id field(name:...){...}
#              fields(first:100){totalCount nodes{...}} } } }` (the
#              `fields(first:100)` selection is a names-only pass used only
#              to detect a duplicate field NAME, not to fetch every field's
#              options) — rather than `gh project view` + `gh project
#              field-list`, which fetch every field and every single-select
#              option on the whole board;
#              measured 2026-09-20, #5827: field-list alone cost ~101 GraphQL
#              points per call on this board, ~105-113 points per transition
#              total, against a 5,000/hour budget shared by every session on
#              this machine — the single-field query costs ~1. Then resolves
#              the issue's project-item ID via GraphQL; adds the issue to the
#              project first via `gh project item-add` if it isn't on the
#              board yet).
#              --owner (org/user that owns the numbered project) is REQUIRED
#              whenever --project is given — pass it explicitly or set
#              $GH_PROJECT_OWNER; this script is product-agnostic and never
#              hardcodes any repo's project owner.
#              If --project is OMITTED, behavior is unchanged from before:
#              comment-only, no field write attempted (backward compatible) —
#              but a clear WARNING is printed to stderr saying the board was
#              NOT updated, so the unqualified "OK transitioned" success line
#              is never mistaken for a real board write.
#              If --project IS given and the field write fails for ANY reason
#              (issue not addable to the board, field/option not found,
#              permissions, network), this FAILS LOUD — clear error on stderr,
#              non-zero exit — it never silently prints-and-continues. The
#              status comment is still posted first, so there's at least a
#              textual record even when the field write fails.
#   resolve  <num> --commit <sha> [--commit <sha>]... --body-file F
#            [--evidence-repo <path>]
#              Post the resolution comment and CLOSE the issue — but REFUSES to
#              close unless every --commit <sha> resolves to a real commit in
#              this repo (guards against fabricated "Resolution" comments with no
#              actual fix). --evidence-repo <path> names a DIFFERENT local git
#              repo to verify the shas against instead (for issues filed on this
#              board whose fix legitimately lands in another repo, e.g. the
#              runtime — the §13 filing convention; #5066). The path must be a
#              real git WORK-TREE repo (a bare repo is refused by the
#              validation), the guard still verifies every sha there, and the
#              posted comment gains an explicit "Evidence repo:" trailer so the
#              close record names where the commits live. The body-file should
#              follow the repo's closing template.
#   dispose  <num> --disposition <D> --body-file F
#              The sanctioned NOT-PLANNED close (#4400, 2026-08-23): closes with
#              --reason "not planned" and a structured "Disposition:" marker so
#              the runtime's close gate can distinguish an honest no-fix close
#              from a fabricated resolution. <D> must be one of:
#                "duplicate-of #N"   (N a real, OPEN issue number — a closed
#                                     target is refused, not just warned about)
#                "stale-superseded"
#                "wont-fix"
#              The marker + reason ride IN the close command itself (the gate
#              checks the close's own segment). Discipline: every not-planned
#              close BATCH is operator-approved before dispose runs — this
#              subcommand is the execution mechanism, never the approval.
#              Rationale text: never use resolution phrasing ("fixed in <sha>")
#              in a disposition rationale — a cited sha turns the close into a
#              resolution claim and the gate's exemption correctly refuses it.
#
# Requires: gh (authenticated), git. jq is required ONLY for 'transition' when
# --project is given (board-write path resolves project/field/option IDs via
# jq); create/comment/resolve/transition-without-project never need it, and
# the jq check is performed lazily inside the 'transition' branch so this
# script works on jq-less machines for every other subcommand. `mktemp` is
# OPTIONAL on 'create' (its dedup search degrades to empty/generic error text
# without it, never to a false search-failure verdict for a search that
# actually ran -- #5827 round 2, 2026-09-20) but IS required for
# 'resolve --evidence-repo' and 'dispose duplicate-of', which use it for an
# already-rarer throwaway git-repo check those two paths cannot skip. Never
# pushes. Never closes without a real commit.

set -u

# Defense-in-depth (fix-round addition, 2026-09-07): every gh call in this
# script that parses stdout as data now captures stderr separately, so gh's
# update-notifier can no longer corrupt a data channel — but suppressing the
# notifier at the source removes the noise outright rather than relying on
# every future stdout-parsing call site to remember the separation.
export GH_NO_UPDATE_NOTIFIER=1

_die() { echo "gh_issue: $*" >&2; exit 1; }
command -v gh  >/dev/null 2>&1 || _die "gh CLI not found / not authenticated"
command -v git >/dev/null 2>&1 || _die "git not found"

SUB="${1:-}"; shift 2>/dev/null || true
[ -n "$SUB" ] || _die "usage: gh_issue.sh {create|comment|transition|resolve} ..."

# --- shared arg collection ---
TITLE=""; BODY_FILE=""; STATUS=""; PROJECT=""; FIELD="Status"; MILESTONE=""; ASSIGNEE=""
OWNER="${GH_PROJECT_OWNER:-}"
NUM=""; LABELS=(); COMMITS=(); FORCE_NEW=""; RELATED=""; DISPOSITION=""; TRIAGE=""; EVIDENCE_REPO=""
PRIORITY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --title)     TITLE="${2:-}"; shift 2 ;;
    --body-file) BODY_FILE="${2:-}"; shift 2 ;;
    --label)     LABELS+=("${2:-}"); shift 2 ;;
    --assignee)  ASSIGNEE="${2:-}"; shift 2 ;;
    --milestone) MILESTONE="${2:-}"; shift 2 ;;
    --status)    STATUS="${2:-}"; shift 2 ;;
    --project)   PROJECT="${2:-}"; shift 2 ;;
    --owner)     OWNER="${2:-}"; shift 2 ;;
    --field)     FIELD="${2:-}"; shift 2 ;;
    --commit)    COMMITS+=("${2:-}"); shift 2 ;;
    --evidence-repo) EVIDENCE_REPO="${2:-}"; shift 2 ;;
    --force-new) FORCE_NEW="1"; shift ;;
    --related)   RELATED="${2:-}"; shift 2 ;;
    --disposition) DISPOSITION="${2:-}"; shift 2 ;;
    --triage)    TRIAGE="${2:-}"; shift 2 ;;
    --priority)  PRIORITY="${2:-}"; shift 2 ;;
    -*)          _die "unknown flag: $1" ;;
    *)           [ -z "$NUM" ] && NUM="$1" && shift || { shift; } ;;
  esac
done

# The Priority project field's own name — always "Priority", never the
# --field value (which is reserved for --triage/transition's own Status-or-
# whatever-the-caller-named target field). Fixed rather than configurable:
# `create --priority` and `--triage` write two DIFFERENT fields on the SAME
# issue in the same call, so they cannot share one $FIELD variable.
PRIORITY_FIELD="Priority"
_PRIORITY_VALUES="P0 P1 P2 P3"

_body_arg() {
  # echo the gh --body-file arg if a readable file was given
  [ -n "$BODY_FILE" ] && [ -r "$BODY_FILE" ] && printf -- '--body-file\n%s\n' "$BODY_FILE"
}

_search_query() {
  # derive a plausible-overlap search query from a title: lowercase, strip to
  # alnum tokens, drop stopwords + short tokens, keep the first 6 significant words.
  printf '%s\n' "$1" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9' ' ' | awk '{
    n = split($0, w, " ")
    split("a an the and or of to in on for with is are this that from by as at it its into via when then than but not no new add adds added fix fixes fixed update updates updated bug bugs issue issues feature features support need needs should must can will would could do does did has have had use uses using used", sw, " ")
    for (i in sw) stop[sw[i]] = 1
    c = 0; out = ""
    for (i = 1; i <= n && c < 6; i++) {
      t = w[i]
      if (length(t) < 3) continue
      if (t in stop) continue
      c++
      out = out (c > 1 ? " " : "") t
    }
    print out
  }'
}

_find_dupes() {
  # populate DUPES with "num\ttitle\turl" lines for OPEN issues plausibly
  # overlapping title "$1", and DUPES_SEARCH_FAILED ("1"/"") to distinguish
  # "searched and found nothing" from "the search itself failed" (#5827: the
  # two used to be indistinguishable -- any gh error, e.g. network/auth/rate-
  # limit, silently left DUPES empty exactly like a genuine no-match search,
  # so `create` filed with no duplicate check at all whenever gh hiccupped).
  # An empty/unsearchable title is NOT a search failure -- there was nothing
  # to search for, so DUPES is empty and DUPES_SEARCH_FAILED stays "".
  DUPES=""
  DUPES_SEARCH_FAILED=""
  DUPES_SEARCH_ERROR=""
  local q
  q="$(_search_query "$1")"
  [ -n "$q" ] || return 0
  # Capture stdout and stderr separately (never merge with 2>&1 -- gh's own
  # update-notifier writes to stderr on success too, which would otherwise
  # corrupt the tab-separated DUPES data channel) and capture the real exit
  # status explicitly into a variable -- never rely on `set -e` to catch a
  # failure inside this command substitution; `set -e` does not propagate
  # into `$(...)` the way a caller might expect, so the exit code must be
  # read from $? right after the substitution, before anything else runs.
  #
  # `mktemp` is OPTIONAL here (fix-round correction, #5827 round 2): the EXIT
  # STATUS of the `gh issue list` call is the actual fail-closed signal, not
  # the temp file -- the temp file only carries the error TEXT for a nicer
  # message. `create` is a hot path that unattended launchd/cron jobs run
  # with a minimal PATH that can genuinely lack `mktemp` (unlike
  # `resolve --evidence-repo` / `dispose duplicate-of`, which use mktemp only
  # for a throwaway git-repo check, an already-rarer path). Without this
  # fallback, a MISSING `mktemp` on a search that would have SUCCEEDED and
  # found a real duplicate is misreported as "the search failed", the real
  # duplicate is never shown, `gh` is never even called, and the refusal
  # message advises --force-new -- which then files the duplicate. That is
  # the exact defect this whole fix exists to close, just relocated to a
  # different trigger. So: when mktemp is available, use it for nicer error
  # text; when it is not, still run the real search with stderr discarded
  # (empty error text on failure, never a fabricated "could not allocate a
  # temp file" excuse that masks an unrelated real search failure).
  local out err rc
  err=""
  if command -v mktemp >/dev/null 2>&1; then err="$(mktemp 2>/dev/null)" || err=""; fi
  if [ -n "$err" ]; then
    out="$(gh issue list --search "$q" --state open --json number,title,url --limit 10 \
      --jq '.[] | "\(.number)\t\(.title)\t\(.url)"' 2>"$err")"
    rc=$?
    # Truncate the captured error text (finding 6, round 2): gh stderr can
    # carry an enormous payload (e.g. a multi-KB HTML error page on a proxy
    # failure), and it lands verbatim in the refusal message below -- cap it
    # so the message stays readable. `head` is one of the small set of
    # binaries this script otherwise assumes is present (it is already relied
    # on elsewhere for similar defensive parsing), but under the same
    # hermetic/minimal PATH concern as mktemp, guard it too: missing `head`
    # degrades to empty error text, never to a false "search failed".
    if command -v head >/dev/null 2>&1; then
      DUPES_SEARCH_ERROR="$(head -c 500 "$err" 2>/dev/null)"
    else
      DUPES_SEARCH_ERROR=""
    fi
    rm -f "$err"
  else
    out="$(gh issue list --search "$q" --state open --json number,title,url --limit 10 \
      --jq '.[] | "\(.number)\t\(.title)\t\(.url)"' 2>/dev/null)"
    rc=$?
    DUPES_SEARCH_ERROR=""
  fi
  if [ "$rc" -ne 0 ]; then
    DUPES_SEARCH_FAILED="1"
    DUPES=""
    return 0
  fi
  DUPES="$out"
}

# _resolve_project_and_field <project> <owner> <field> — populates the
# caller's `proj_id`, `field_json`, `field_id`, `field_type`,
# `field_match_count` variables (plain assignment, not `local` — this is a
# helper invoked from within _do_transition/_validate_triage_status, which
# already declare those as `local` in their own scope, so the assignment
# here lands in the caller's locals; bash has no separate variable scope for
# a sourced-in-the-same-file function call) by resolving the project's node
# ID AND the named field's id/type/options in ONE GraphQL query, replacing
# the old two-call sequence (`gh project view` + `gh project field-list`)
# that fetched the ENTIRE project (every field, every single-select option)
# just to find one field's id. Cost measured 2026-09-20 (#5827): the old
# sequence cost ~101 GraphQL points per call (19 fields, every option); this
# one costs ~1 (verified live — a names-only `fields(first:100)` selection,
# below, costs the same ~1 point as the targeted `field(name:...)` lookup;
# GitHub's per-call cost is driven by selection complexity/depth — options
# connections were what drove the old 101, not the field count itself).
#
# $owner/$number/$field are passed as GraphQL VARIABLES (-f/-F), never
# interpolated into the query string — the query text itself carries no
# literal owner/number/field value.
#
# `repositoryOwner(login:...)` returns the `RepositoryOwner` interface, which
# does NOT itself expose `projectV2` — only `ProjectV2Owner` (implemented by
# both `Organization` and `User`) does. Fragmenting on `ProjectV2Owner`
# directly resolves correctly for either owner type (verified live against
# this board's Organization owner; GraphQL resolves a fragment on any type
# the concrete object implements, regardless of which interface the parent
# field is declared to return) without needing separate
# `... on Organization` / `... on User` fragments.
#
# `ProjectV2.field(name:...)` returns the `ProjectV2FieldConfiguration`
# UNION (ProjectV2Field | ProjectV2IterationField | ProjectV2MultiSelectField
# | ProjectV2SingleSelectField) — `__typename` is requested explicitly so
# `field_type` is read the SAME way (the literal GraphQL type name) the old
# `gh project field-list`-derived `.type` was; fragmenting on
# `ProjectV2SingleSelectField` additionally captures `options` for that one
# type, and `ProjectV2FieldCommon` (id/name only) covers every member for
# the id/name fields common to all of them. A field whose `__typename` is
# neither `ProjectV2SingleSelectField` nor `ProjectV2Field` (e.g. an
# iteration or multi-select field) is passed through to the existing
# downstream `case "$field_type" in ... *) _die "...unsupported type..."`
# arm unchanged — this resolver never itself decides what's supported.
#
# AMBIGUOUS (duplicate-named) FIELD DETECTION (preserved from the old
# field-list-based check, f028962 2026-08-03 — a deliberate safety fix, not
# incidental behavior; GitHub's ProjectV2 schema does NOT enforce unique
# field names, so this is a real, reachable case): `field(name:...)` alone
# gives no signal about how many fields share that name, so the SAME query
# also requests a names-only `fields(first: 100) { totalCount nodes {
# __typename ... on ProjectV2FieldCommon { name } } }` selection (still ~1
# point total — no per-field `options` are requested here) and
# `field_match_count` is the count of nodes whose name equals `$field`,
# computed client-side. `totalCount > 100` REFUSES — this function RETURNS
# 1 with the reason in `$_RESOLVE_ERR`, and **every caller MUST check the
# return value**. An unchecked caller is a live bug, not a style nit: the
# early `return 1` never assigns `field_match_count`, so it is EMPTY, the
# caller's own `[[ "${n:-0}" =~ ^[0-9]+$ ]] && [ "${n:-0}" -gt 1 ]`
# ambiguity guard evaluates cleanly against the DEFAULT 0 and therefore
# does not fire, and execution falls through to a silent write on the
# WRONG field on any project with 2+ same-named fields past the first 100 (fix-round blocker, 2026-09-20 — proven live on a 120-field
# two-"Status"-fields board; re-proven in fix-round 3 by adding a fifth,
# return-ignoring call site, which reached the write with an empty
# field_match_count and no guard firing).
#
# It did not always work this way, and the history matters for anyone
# tempted to "simplify" it back: this check used to `_die` directly from
# inside the resolver, which DID make the fall-through unreachable by
# construction — but it also bypassed the post-create PARTIAL contract
# entirely, exiting 1 with an issue already filed, which drove unattended
# callers to retry and file duplicates (fix-round 2, blocker B2). Returning
# 1 is what lets `_write_priority_field` / `_write_status_field` route this
# through `_priority_partial` / `_status_write_fail` like every other
# failure. The cost of that is exactly this: the guard now depends on
# callers checking, so a NEW call site that ignores the return value
# silently re-opens B2's original defect. Check the return. All four
# current call sites do.
#
# No real project has ever been observed anywhere near 100 custom fields,
# so this is a defensive tripwire, not a real limit in practice, but it
# refuses outright rather than silently under-counting.
#
# `gh api graphql` exits non-zero on a GraphQL `errors` response (verified
# live: a missing field name, a missing project number) but STILL writes
# valid partial JSON (`data` + `errors`) to stdout — so stdout is always
# captured regardless of exit status, and the caller must not treat a
# nonzero exit alone as "no data" (mirroring this script's existing
# `item_json` GraphQL call two blocks below, which already captures stdout
# unconditionally and lets a null/absent jq path decide, ignoring `gh`'s own
# exit code).
# _RESOLVE_ERR — set by _resolve_project_and_field on its ONE internal
# failure condition (the >100-fields ambiguity-check-cannot-page case); the
# caller reads it immediately after a non-zero return. Global rather than a
# local the caller can't see: this function's other outputs (proj_id,
# field_json, ...) are already communicated the same way (plain assignment
# into the CALLER's locals, per this function's own pre-existing
# convention — see its callers' own `local proj_id field_json ...`
# declarations), so this follows the established pattern rather than
# inventing a second one.
_RESOLVE_ERR=""

# _resolve_project_and_field <project> <owner> <field> — resolves the
# project's node ID AND the target field's id/type/options in ONE GraphQL
# query (see the module header comment for the shape and cost measurement,
# #5827). RETURNS 1 (never `_die`s — fix-round 2, B1/B2) on its one
# internal failure condition: a project with more than 100 fields, which
# the duplicate-field-name ambiguity check cannot safely page past. Message
# text in `_RESOLVE_ERR` is IDENTICAL to the pre-fix `_die` text so no
# existing test's assertion on that text changes — only the control-flow
# mechanism moved, not the wording.
#
# WHY THIS MATTERS (fix-round 2): every caller of this function used to
# inherit an unconditional `_die` (real exit 1) buried three call-frames
# deep, including from a POST-CREATE call site where the issue already
# exists — an exit 1 there reads as "nothing happened" and drives an
# unattended caller to retry, filing a DUPLICATE. Returning instead of
# dying lets EVERY caller decide the right contract for its own position:
# `_validate_triage_status` (pre-create) still refuses hard via
# `_triage_fail`; `_write_priority_field` and `_write_status_field`
# (post-create) route it through their own PARTIAL contract
# (`_priority_partial`/`_write_status_field`'s own helper) instead.
_resolve_project_and_field() {
  local project="$1" owner="$2" field="$3"
  local resp total_count
  _RESOLVE_ERR=""
  resp="$(gh api graphql -f query='
    query($owner: String!, $number: Int!, $field: String!) {
      repositoryOwner(login: $owner) {
        ... on ProjectV2Owner {
          projectV2(number: $number) {
            id
            field(name: $field) {
              __typename
              ... on ProjectV2SingleSelectField { id name options { id name } }
              ... on ProjectV2FieldCommon { id name }
            }
            fields(first: 100) {
              totalCount
              nodes { __typename ... on ProjectV2FieldCommon { name } }
            }
          }
        }
      }
    }' -f owner="$owner" -F number="$project" -f field="$field" 2>/dev/null)"
  proj_id="$(printf '%s' "$resp" | jq -r '.data.repositoryOwner.projectV2.id // empty' 2>/dev/null)"
  field_json="$(printf '%s' "$resp" | jq -c '.data.repositoryOwner.projectV2.field // empty' 2>/dev/null)"
  total_count="$(printf '%s' "$resp" | jq -r '.data.repositoryOwner.projectV2.fields.totalCount // 0' 2>/dev/null)"
  if [[ "${total_count:-0}" =~ ^[0-9]+$ ]] && [ "${total_count:-0}" -gt 100 ]; then
    _RESOLVE_ERR="project #$project (owner '$owner') has $total_count fields — more than the 100 the duplicate-field-name ambiguity check can read in one page; refusing to guess which '$field' to use"
    return 1
  fi
  field_match_count="$(printf '%s' "$resp" | jq -r --arg f "$field" '[(.data.repositoryOwner.projectV2.fields.nodes // [])[] | select(.name == $f)] | length' 2>/dev/null)"
  if [ -n "$field_json" ] && [ "$field_json" != "null" ]; then
    field_id="$(printf '%s' "$field_json" | jq -r '.id')"
    field_type="$(printf '%s' "$field_json" | jq -r '.__typename')"
  else
    field_json=""
    field_id=""
    field_type=""
  fi
  return 0
}

# _do_transition <num> <status> — the shared board-transition logic used by
# both the 'transition' subcommand and 'create --triage'. Reads $PROJECT/
# $OWNER/$FIELD from the already-parsed globals (both callsites share the
# same flag-parsing block above, so there is nothing to pass separately).
# Posts a best-effort status comment first (so there is a textual record even
# if the field write below fails), then — IF $PROJECT is set — resolves and
# writes the real project board Status field, FAILING LOUD on any resolution
# error (unknown field, unknown option, permissions, network). Without
# $PROJECT, this is comment-only (unchanged, backward-compatible behavior)
# with a WARNING on stderr that the board was not updated.
_do_transition() {
  local num="$1" status="$2"
  [ -n "$num" ] || _die "transition requires <issue-number>"
  [ -n "$status" ] || _die "transition requires --status"
  # Best-effort: post a status note so board state is visible even without project wiring.
  # Order matters: comment first, so there's at least a textual record even if
  # the field write below fails.
  gh issue comment "$num" --body "Status → **$status**" >/dev/null 2>&1 || true

  if [ -n "$PROJECT" ]; then
    [ -n "$OWNER" ] || _die "transition --project $PROJECT given but no --owner (or \$GH_PROJECT_OWNER) — cannot resolve the project; board update FAILED for #$num"
    command -v jq >/dev/null 2>&1 || _die "jq not found (required to resolve project/field/option IDs for a --project board write) — board update FAILED for #$num"

    # Resolve the project's node ID AND the target field's ID/type/options
    # in ONE GraphQL query (see _resolve_project_and_field's own docstring
    # for the shape and cost measurement, #5827) — replaces the old
    # `gh project view` + `gh project field-list` two-call sequence.
    #
    # This is the STANDALONE 'transition' subcommand's own path — nothing
    # has been filed by THIS function (unlike create's post-create Status
    # write, which uses _write_status_field instead precisely so it can
    # carry a DIFFERENT, PARTIAL contract — see that function's own
    # docstring for why the two must never be unified). _die on a resolver
    # failure here is CORRECT and DELIBERATELY UNCHANGED (fix-round 2):
    # exit 1 genuinely means "nothing was filed" on this path.
    local proj_id field_json field_id field_type field_match_count
    _resolve_project_and_field "$PROJECT" "$OWNER" "$FIELD" || _die "$_RESOLVE_ERR — board update FAILED for #$num"
    [ -n "$proj_id" ] || _die "transition: could not resolve project #$PROJECT for owner '$OWNER' (project field-resolution query failed) — board update FAILED for #$num"
    if [[ "${field_match_count:-0}" =~ ^[0-9]+$ ]] && [ "${field_match_count:-0}" -gt 1 ]; then
      _die "transition: multiple fields named '$FIELD' on project #$PROJECT (owner '$OWNER') — ambiguous, refusing to guess which one to write — board update FAILED for #$num"
    fi
    [ -n "$field_json" ] && [ "$field_json" != "null" ] || _die "transition: field '$FIELD' not found on project #$PROJECT (owner '$OWNER') — board update FAILED for #$num"

    # Resolve the issue's node ID + URL in one call (URL only needed if we must add it to the board).
    issue_json="$(gh issue view "$num" --json id,url 2>/dev/null)"
    issue_node_id="$(printf '%s' "$issue_json" | jq -r '.id // empty')"
    issue_url="$(printf '%s' "$issue_json" | jq -r '.url // empty')"
    [ -n "$issue_node_id" ] || _die "transition: could not resolve issue #$num (gh issue view failed) — board update FAILED"

    # Resolve this issue's project-item ID via GraphQL (cheaper than paging gh project item-list).
    item_json="$(gh api graphql -f query='
      query($id: ID!) {
        node(id: $id) {
          ... on Issue {
            projectItems(first: 50) { nodes { id project { id } } }
          }
        }
      }' -f id="$issue_node_id" 2>/dev/null)"
    item_id="$(printf '%s' "$item_json" | jq -r --arg pid "$proj_id" '(.data.node.projectItems.nodes // [])[] | select(.project.id == $pid) | .id' 2>/dev/null | head -n1)"

    if [ -z "$item_id" ]; then
      # Not on the board yet — add it (idempotent; returns the existing item if already present).
      add_json="$(gh project item-add "$PROJECT" --owner "$OWNER" --url "$issue_url" --format json 2>&1)"
      item_id="$(printf '%s' "$add_json" | jq -r '.id // empty' 2>/dev/null)"
      [ -n "$item_id" ] || _die "transition: issue #$num is not on project #$PROJECT and could not be added (gh project item-add failed: $add_json) — board update FAILED"
    fi

    # Write the field value; the write flag depends on the field's type.
    edit_value_args=()
    case "$field_type" in
      ProjectV2SingleSelectField)
        opt_id="$(printf '%s' "$field_json" | jq -r --arg s "$status" '.options[]? | select(.name == $s) | .id')"
        [ -n "$opt_id" ] || _die "transition: '$status' is not a valid option for field '$FIELD' on project #$PROJECT (options: $(printf '%s' "$field_json" | jq -r '[.options[]?.name] | join(", ")')) — board update FAILED for #$num"
        edit_value_args=(--single-select-option-id "$opt_id")
        ;;
      ProjectV2Field)
        edit_value_args=(--text "$status")
        ;;
      *)
        _die "transition: field '$FIELD' has unsupported type '$field_type' for an automated status write — board update FAILED for #$num"
        ;;
    esac

    gh project item-edit --id "$item_id" --field-id "$field_id" --project-id "$proj_id" "${edit_value_args[@]}" >/dev/null \
      || _die "transition: gh project item-edit failed for #$num (project #$PROJECT, field '$FIELD' = '$status') — board update FAILED"

    echo "gh_issue: set project #$PROJECT field '$FIELD' = '$status' for issue #$num" >&2
  else
    echo "gh_issue: WARNING — no --project given for #$num; this was a COMMENT-ONLY transition, the project board was NOT updated" >&2
  fi
  echo "OK transitioned #$num -> $status"
}

# _validate_triage_status <status> — the SAME live-option validation
# _do_transition's ProjectV2SingleSelectField branch performs, run standalone
# so 'create --triage' can refuse an unknown status BEFORE creating anything
# (never leaving a filed-but-untriaged issue behind a typo). A no-op
# (always valid) when $PROJECT is unset, mirroring _do_transition's own
# comment-only/no-validation behavior in that case — this script never
# invents a status domain for a caller that isn't writing to a real project
# field. Dies with the same "options: ..." shape _do_transition's own
# opt_id lookup would have produced.
# _triage_fail <message> — the SOFT/HARD split fix-round 1 (A1) requires: a
# DEFAULTED --triage (TRIAGE_WAS_DEFAULTED=1, see the Backlog default above)
# must never refuse the create outright — Phase D's own "nothing is ever
# dropped or refused" — so it prints a WARNING to stderr and clears $TRIAGE
# (the create proceeds untriaged rather than not at all). An EXPLICIT
# --triage stays HARD: _die, refusing to create, exactly as before. Every
# _validate_triage_status failure branch below routes through this single
# helper so the soft/hard decision lives in ONE place, not re-derived at
# each of the function's five failure sites.
_triage_fail() {
  local message="$1"
  if [ -n "${TRIAGE_WAS_DEFAULTED:-}" ]; then
    echo "gh_issue: WARNING — $message — issue will be filed with NO Status set (defaulted --triage Backlog was soft; pass an explicit --triage <valid option> to make this hard, or set the option by hand after filing)" >&2
    TRIAGE=""
    return 0
  fi
  _die "$message"
}

_validate_triage_status() {
  local status="$1"
  [ -n "$PROJECT" ] || return 0
  if [ -z "$OWNER" ]; then
    _triage_fail "create --triage $status --project $PROJECT given but no --owner (or \$GH_PROJECT_OWNER) — cannot resolve the project"
    return 0
  fi
  if ! command -v jq >/dev/null 2>&1; then
    _triage_fail "jq not found (required to resolve project/field/option IDs for --triage validation)"
    return 0
  fi

  # Resolve the project's node ID AND the target field's ID/type/options in
  # ONE GraphQL query (see _resolve_project_and_field's own docstring for
  # the shape and cost measurement, #5827) — the project node ID this
  # returns is unused here (this function only validates, it never writes).
  # A nonexistent project resolves to an empty field_json exactly like a
  # nonexistent field did under the old `gh project field-list`-based
  # lookup (that command failed/returned empty for either case, and both
  # collapsed onto the same "field not found" message) — preserved here by
  # NOT special-casing an empty proj_id into a separate die message.
  local proj_id field_json field_id field_type field_match_count
  if ! _resolve_project_and_field "$PROJECT" "$OWNER" "$FIELD"; then
    _triage_fail "$_RESOLVE_ERR"
    return 0
  fi
  if [[ "${field_match_count:-0}" =~ ^[0-9]+$ ]] && [ "${field_match_count:-0}" -gt 1 ]; then
    _triage_fail "create --triage: multiple fields named '$FIELD' on project #$PROJECT (owner '$OWNER') — ambiguous, refusing to guess which one to validate against"
    return 0
  fi
  if [ -z "$field_json" ] || [ "$field_json" = "null" ]; then
    _triage_fail "create --triage: field '$FIELD' not found on project #$PROJECT (owner '$OWNER')"
    return 0
  fi

  case "$field_type" in
    ProjectV2SingleSelectField)
      local opt_id
      opt_id="$(printf '%s' "$field_json" | jq -r --arg s "$status" '.options[]? | select(.name == $s) | .id')"
      if [ -z "$opt_id" ]; then
        _triage_fail "create --triage: '$status' is not a valid option for field '$FIELD' on project #$PROJECT (options: $(printf '%s' "$field_json" | jq -r '[.options[]?.name] | join(", ")'))"
        return 0
      fi
      ;;
    ProjectV2Field) : ;;  # free-text field — any status string is valid, same as _do_transition's own ProjectV2Field branch
    *)
      _triage_fail "create --triage: field '$FIELD' has unsupported type '$field_type' for an automated status write"
      return 0
      ;;
  esac
}

# _write_priority_field <num> <value> — writes the fixed "Priority" project
# field (#5827, master plan WS1 Phase D — the issue-
# CREATION quality gate). Deliberately SEPARATE from _do_transition rather
# than reusing it: _do_transition posts a "Status → **$status**" comment
# unconditionally, which is the wrong text for a Priority write (and would
# double-post alongside a --triage call in the same 'create' invocation).
# Uses the SAME `_resolve_project_and_field` one-query resolver as --triage/
# transition (see that function's own docstring for the GraphQL-cost
# rationale, #5827) and the SAME "resolve the issue's project-item id,
# add-if-absent, then item-edit" sequence _do_transition already uses —
# duplicated here rather than factored out, since the two write DIFFERENT
# fields with DIFFERENT validation (a fixed P0-P3 domain here, vs.
# _do_transition's live-options lookup) and sharing risks entangling the
# two into one harder-to-read function for no real benefit at this size.
#
# $value MUST be one of P0/P1/P2/P3 (checked by the caller via
# _validate_priority_value BEFORE this is ever invoked — this function
# itself trusts its caller and does not re-validate, exactly like
# _do_transition trusts $status once past its own opt_id lookup).
#
# EXIT_PARTIAL=3 — fix-round 1 (A2): once _write_priority_field is ever
# invoked, issue #$num ALREADY EXISTS (created successfully). A failure past
# this point is categorically different from a pre-create refusal: `_die`'s
# plain exit 1 reads as "nothing happened", which is false here and drives a
# caller to retry the whole `create` — filing a DUPLICATE issue. A named
# PARTIAL exit code (distinct from both 0=clean and 1=nothing-filed) lets a
# caller tell the three outcomes apart mechanically, not just from message
# text.
EXIT_PARTIAL=3

# _priority_partial <num> <message> — prints "$message", NAMING THE ISSUE
# NUMBER on stdout (never buried only in stderr — a caller must be able to
# find #$num even from stdout alone), and exits EXIT_PARTIAL. Every
# _write_priority_field failure branch routes through this so "the issue
# was filed, the Priority write failed" is reported identically everywhere,
# and so `create`'s own already-printed issue URL/number is never mistaken
# for "nothing happened" — unlike _triage_fail (A1), there is no soft/hard
# distinction here: the ISSUE ALREADY EXISTS regardless of why the write
# failed, so there is nothing left to make "hard" (refusing would have
# nothing left to refuse).
_priority_partial() {
  local num="$1" message="$2"
  echo "gh_issue: PARTIAL — $message — issue #$num WAS filed; Priority NOT set" >&2
  echo "PARTIAL #$num — Priority NOT set: $message"
  exit "$EXIT_PARTIAL"
}

# FAILS PARTIAL (exit 3, never a bare 1) on any resolution/write error
# (project not found, field not found, option not found, gh project
# item-edit failure) — see _priority_partial above. This is a CALLER-error/
# infrastructure-error path, never a "budget" refusal; Phase D is
# observer-first and NEVER refuses issue creation for missing
# priority/labels (see the create-time WARN-ONLY block in the 'create'
# case arm below) — this function is only ever reached once a value has
# already been confirmed valid.
#
# [ -n "$PROJECT" ] is the LITERAL FIRST GUARD (A2 fix): the call site below
# already skips this function entirely when $PROJECT is empty (see the
# create-time guard), but this function trusts NO caller assumption for a
# check this cheap — without it, `_resolve_project_and_field ""  "$OWNER"
# ...` fires a REAL GraphQL call with an EMPTY project number (`-F
# number=`), proven live in fix-round review. Checking here, before that
# call, makes the empty-number query structurally unreachable rather than
# merely avoided by convention at one call site.
_write_priority_field() {
  local num="$1" value="$2"
  [ -n "$PROJECT" ] || _priority_partial "$num" "no --project given — Priority write skipped"
  [ -n "$OWNER" ] || _priority_partial "$num" "create --priority $value --project $PROJECT given but no --owner (or \$GH_PROJECT_OWNER) — cannot resolve the project"
  command -v jq >/dev/null 2>&1 || _priority_partial "$num" "jq not found (required to resolve project/field/option IDs for a --priority board write)"

  local proj_id field_json field_id field_type field_match_count
  # fix-round 2 (B2): _resolve_project_and_field's own >100-fields
  # ambiguity check used to `_die` from INSIDE this call, bypassing
  # _priority_partial entirely — rc=1 with the issue already filed and no
  # PARTIAL marker anywhere. It now RETURNS 1 with the message in
  # $_RESOLVE_ERR instead, so this check routes it through the same
  # PARTIAL contract as every other failure in this function.
  _resolve_project_and_field "$PROJECT" "$OWNER" "$PRIORITY_FIELD" || _priority_partial "$num" "$_RESOLVE_ERR"
  [ -n "$proj_id" ] || _priority_partial "$num" "could not resolve project #$PROJECT for owner '$OWNER' (project field-resolution query failed)"
  if [[ "${field_match_count:-0}" =~ ^[0-9]+$ ]] && [ "${field_match_count:-0}" -gt 1 ]; then
    _priority_partial "$num" "multiple fields named '$PRIORITY_FIELD' on project #$PROJECT (owner '$OWNER') — ambiguous, refusing to guess which one to write"
  fi
  [ -n "$field_json" ] && [ "$field_json" != "null" ] || _priority_partial "$num" "field '$PRIORITY_FIELD' not found on project #$PROJECT (owner '$OWNER')"

  issue_json="$(gh issue view "$num" --json id,url 2>/dev/null)"
  issue_node_id="$(printf '%s' "$issue_json" | jq -r '.id // empty')"
  issue_url="$(printf '%s' "$issue_json" | jq -r '.url // empty')"
  [ -n "$issue_node_id" ] || _priority_partial "$num" "could not resolve issue #$num (gh issue view failed)"

  item_json="$(gh api graphql -f query='
    query($id: ID!) {
      node(id: $id) {
        ... on Issue {
          projectItems(first: 50) { nodes { id project { id } } }
        }
      }
    }' -f id="$issue_node_id" 2>/dev/null)"
  item_id="$(printf '%s' "$item_json" | jq -r --arg pid "$proj_id" '(.data.node.projectItems.nodes // [])[] | select(.project.id == $pid) | .id' 2>/dev/null | head -n1)"

  if [ -z "$item_id" ]; then
    add_json="$(gh project item-add "$PROJECT" --owner "$OWNER" --url "$issue_url" --format json 2>&1)"
    item_id="$(printf '%s' "$add_json" | jq -r '.id // empty' 2>/dev/null)"
    [ -n "$item_id" ] || _priority_partial "$num" "issue #$num is not on project #$PROJECT and could not be added (gh project item-add failed: $add_json)"
  fi

  case "$field_type" in
    ProjectV2SingleSelectField)
      opt_id="$(printf '%s' "$field_json" | jq -r --arg s "$value" '.options[]? | select(.name == $s) | .id')"
      [ -n "$opt_id" ] || _priority_partial "$num" "'$value' is not a valid option for field '$PRIORITY_FIELD' on project #$PROJECT (options: $(printf '%s' "$field_json" | jq -r '[.options[]?.name] | join(", ")'))"
      gh project item-edit --id "$item_id" --field-id "$field_id" --project-id "$proj_id" --single-select-option-id "$opt_id" >/dev/null \
        || _priority_partial "$num" "gh project item-edit failed for #$num (project #$PROJECT, field '$PRIORITY_FIELD' = '$value')"
      ;;
    ProjectV2Field)
      gh project item-edit --id "$item_id" --field-id "$field_id" --project-id "$proj_id" --text "$value" >/dev/null \
        || _priority_partial "$num" "gh project item-edit failed for #$num (project #$PROJECT, field '$PRIORITY_FIELD' = '$value')"
      ;;
    *)
      _priority_partial "$num" "field '$PRIORITY_FIELD' has unsupported type '$field_type' for an automated write"
      ;;
  esac

  echo "gh_issue: set project #$PROJECT field '$PRIORITY_FIELD' = '$value' for issue #$num" >&2
}

# _status_write_fail <num> <message> — fix-round 2 (B1): the post-create
# Status write's OWN failure contract, distinct from BOTH `_triage_fail`
# (pre-create, A1) and `_priority_partial` (post-create, always-PARTIAL,
# A2) because THIS write's failure severity depends on whether the value
# being written was DEFAULTED or EXPLICIT — a distinction that exists
# nowhere else in this script:
#   - DEFAULTED (TRIAGE_WAS_DEFAULTED=1, the Backlog auto-fill): SOFTEST
#     possible outcome — warn on stderr, exit 0. Mirrors A1's own
#     soft/hard split ("a defaulted value never costs the caller an
#     error") extended to the post-create write, not just pre-create
#     validation: a defaulted Backlog that turns out unwritable (a failed
#     item-edit, a missing field, an over-100-fields board) must cost the
#     caller NOTHING, exactly like a defaulted Backlog that turns out to
#     be an invalid OPTION already costs nothing via A1.
#   - EXPLICIT (`--triage <status>` given by the caller): PARTIAL — the
#     issue exists, the caller asked for this write specifically, so its
#     failure is reported exactly like a failed Priority write (exit 3,
#     issue number on stdout, message naming what did not get set) —
#     never a bare exit 1, which would read as "nothing happened" and
#     invite a retry that files a duplicate (the exact defect this whole
#     fix-round exists to close).
_status_write_fail() {
  local num="$1" message="$2"
  if [ -n "${TRIAGE_WAS_DEFAULTED:-}" ]; then
    echo "gh_issue: WARNING — $message — issue #$num WAS filed with NO Status set (defaulted --triage Backlog was soft; pass an explicit --triage <valid option> to make this hard, or set the option by hand)" >&2
    return 0
  fi
  echo "gh_issue: PARTIAL — $message — issue #$num WAS filed; Status NOT set" >&2
  echo "PARTIAL #$num — Status NOT set: $message"
  exit "$EXIT_PARTIAL"
}

# _write_status_field <num> <status> — the POST-CREATE Status write used
# ONLY by `create`'s own triage path (never by the standalone `transition`
# subcommand, which keeps using `_do_transition` — see that function's own
# comment on why the two must stay separate). Mirrors `_write_priority_
# field`'s structure and GraphQL-cost rationale exactly (same one-query
# resolver, same resolve-item/add-if-absent/item-edit sequence), but routes
# every failure through `_status_write_fail` instead of `_priority_partial`
# so the DEFAULTED-vs-EXPLICIT distinction above is honored.
#
# COMMENT-ONLY PARITY (fix-round 3, blocker B3). When $PROJECT is set, this
# does NOT post the "Status → **$status**" comment `_do_transition` posts:
# the project field write IS the record, and a duplicate best-effort comment
# adds noise, not signal. When $PROJECT is EMPTY, however, there is no field
# write to be the record, so this falls back to exactly what HEAD's
# `_do_transition` did for `create --triage` with no --project — post the
# comment, warn COMMENT-ONLY, exit 0 — preserving that documented call
# shape (see this script's own header) rather than regressing it to a
# PARTIAL 3 for a create that fully succeeded.
#
# [ -n "$PROJECT" ] is the LITERAL FIRST GUARD, mirroring
# `_write_priority_field`'s own (A2 fix) for the identical reason: the call
# site below also guards, but this function trusts NO caller convention for
# a check this cheap — without it, `_resolve_project_and_field "" "$OWNER"
# ...` fires a REAL GraphQL call with an EMPTY project number (`-F number=`)
# whenever $OWNER happens to be set, which is the documented standard setup
# ($GH_PROJECT_OWNER exported). Checking here makes the empty-number query
# structurally unreachable rather than merely avoided at one call site.
_write_status_field() {
  local num="$1" status="$2"
  if [ -z "$PROJECT" ]; then
    gh issue comment "$num" --body "Status → **$status**" >/dev/null 2>&1 || true
    echo "gh_issue: WARNING — no --project given for #$num; this was a COMMENT-ONLY transition, the project board was NOT updated" >&2
    return 0
  fi
  [ -n "$OWNER" ] || { _status_write_fail "$num" "create --triage $status --project $PROJECT given but no --owner (or \$GH_PROJECT_OWNER) — cannot resolve the project"; return 0; }
  if ! command -v jq >/dev/null 2>&1; then
    _status_write_fail "$num" "jq not found (required to resolve project/field/option IDs for a --triage board write)"
    return 0
  fi

  local proj_id field_json field_id field_type field_match_count
  if ! _resolve_project_and_field "$PROJECT" "$OWNER" "$FIELD"; then
    _status_write_fail "$num" "$_RESOLVE_ERR"
    return 0
  fi
  if [ -z "$proj_id" ]; then
    _status_write_fail "$num" "could not resolve project #$PROJECT for owner '$OWNER' (project field-resolution query failed)"
    return 0
  fi
  if [[ "${field_match_count:-0}" =~ ^[0-9]+$ ]] && [ "${field_match_count:-0}" -gt 1 ]; then
    _status_write_fail "$num" "multiple fields named '$FIELD' on project #$PROJECT (owner '$OWNER') — ambiguous, refusing to guess which one to write"
    return 0
  fi
  if [ -z "$field_json" ] || [ "$field_json" = "null" ]; then
    _status_write_fail "$num" "field '$FIELD' not found on project #$PROJECT (owner '$OWNER')"
    return 0
  fi

  issue_json="$(gh issue view "$num" --json id,url 2>/dev/null)"
  issue_node_id="$(printf '%s' "$issue_json" | jq -r '.id // empty')"
  issue_url="$(printf '%s' "$issue_json" | jq -r '.url // empty')"
  if [ -z "$issue_node_id" ]; then
    _status_write_fail "$num" "could not resolve issue #$num (gh issue view failed)"
    return 0
  fi

  item_json="$(gh api graphql -f query='
    query($id: ID!) {
      node(id: $id) {
        ... on Issue {
          projectItems(first: 50) { nodes { id project { id } } }
        }
      }
    }' -f id="$issue_node_id" 2>/dev/null)"
  item_id="$(printf '%s' "$item_json" | jq -r --arg pid "$proj_id" '(.data.node.projectItems.nodes // [])[] | select(.project.id == $pid) | .id' 2>/dev/null | head -n1)"

  if [ -z "$item_id" ]; then
    add_json="$(gh project item-add "$PROJECT" --owner "$OWNER" --url "$issue_url" --format json 2>&1)"
    item_id="$(printf '%s' "$add_json" | jq -r '.id // empty' 2>/dev/null)"
    if [ -z "$item_id" ]; then
      _status_write_fail "$num" "issue #$num is not on project #$PROJECT and could not be added (gh project item-add failed: $add_json)"
      return 0
    fi
  fi

  case "$field_type" in
    ProjectV2SingleSelectField)
      opt_id="$(printf '%s' "$field_json" | jq -r --arg s "$status" '.options[]? | select(.name == $s) | .id')"
      if [ -z "$opt_id" ]; then
        _status_write_fail "$num" "'$status' is not a valid option for field '$FIELD' on project #$PROJECT (options: $(printf '%s' "$field_json" | jq -r '[.options[]?.name] | join(", ")'))"
        return 0
      fi
      gh project item-edit --id "$item_id" --field-id "$field_id" --project-id "$proj_id" --single-select-option-id "$opt_id" >/dev/null \
        || { _status_write_fail "$num" "gh project item-edit failed for #$num (project #$PROJECT, field '$FIELD' = '$status')"; return 0; }
      ;;
    ProjectV2Field)
      gh project item-edit --id "$item_id" --field-id "$field_id" --project-id "$proj_id" --text "$status" >/dev/null \
        || { _status_write_fail "$num" "gh project item-edit failed for #$num (project #$PROJECT, field '$FIELD' = '$status')"; return 0; }
      ;;
    *)
      _status_write_fail "$num" "field '$FIELD' has unsupported type '$field_type' for an automated status write"
      return 0
      ;;
  esac

  echo "gh_issue: set project #$PROJECT field '$FIELD' = '$status' for issue #$num" >&2
}

# _validate_priority_value <value> — a caller-error check, NOT a budget
# refusal: `--priority` must be one of P0/P1/P2/P3 (see $_PRIORITY_VALUES)
# or the flag was mistyped. Refuses BEFORE creating anything, mirroring
# _validate_triage_status's own "never leave a filed-but-mistyped issue
# behind" discipline. This is unconditional (unlike the WARN-ONLY missing-
# priority/label observer window below) — an explicitly-passed-but-invalid
# value is always a hard error, since there is no live-options lookup
# possible before the project is even resolved and Phase D's fixed P0-P3
# domain is not something this script guesses at.
_validate_priority_value() {
  local value="$1"
  case " $_PRIORITY_VALUES " in
    *" $value "*) return 0 ;;
    *) _die "create --priority: '$value' is not one of the valid priority values ($_PRIORITY_VALUES); refusing to create (nothing was filed)" ;;
  esac
}

case "$SUB" in
  create)
    [ -n "$TITLE" ] || _die "create requires --title"

    if [ -n "$RELATED" ]; then
      # Fold this finding into an existing issue instead of creating a new one.
      rel_body="Related finding (folded here instead of filing a new issue): **$TITLE**"
      [ -n "$BODY_FILE" ] && [ -r "$BODY_FILE" ] && rel_body="$rel_body

$(cat "$BODY_FILE")"
      gh issue comment "$RELATED" --body "$rel_body" || _die "failed to post cross-reference comment on #$RELATED"
      echo "OK cross-referenced on #$RELATED (no new issue created)"
      exit 0
    fi

    if [ -n "$FORCE_NEW" ]; then
      # --force-new's existing meaning is preserved exactly (#5827 fix-round
      # correction, 2026-09-20): it SKIPS the dedupe search entirely -- it
      # never even calls `gh issue list` -- rather than running it just to
      # learn whether a failure would have happened. Running the search here
      # anyway would cost a real GitHub GraphQL call on every forced create
      # for no operational benefit (this account's GraphQL budget was
      # exhausted twice in one day by exactly this kind of avoidable
      # overhead). The bypass is still LOGGED, unconditionally, so the record
      # of "a duplicate check was skipped here" never depends on knowing
      # whether the (never-run) search would have failed or matched.
      echo "gh_issue: duplicate check SKIPPED (--force-new given)" >&2
    else
      _find_dupes "$TITLE"
      if [ -n "$DUPES_SEARCH_FAILED" ]; then
        _die "duplicate search failed (${DUPES_SEARCH_ERROR:-gh returned a non-zero exit with no error text}) — refusing to create without a duplicate check; retry the search, or pass --force-new to create anyway if you are confident this is genuinely new/distinct"
      elif [ -n "$DUPES" ]; then
        echo "gh_issue: possible duplicate/overlapping OPEN issue(s) found for title: $TITLE" >&2
        echo "$DUPES" | while IFS="$(printf '\t')" read -r n t u; do
          echo "  #$n  $t  ($u)" >&2
        done
        _die "refusing to create a likely-duplicate issue — use --force-new if this is genuinely new/distinct, or --related <num> to fold it into the existing issue instead"
      fi
    fi

    # --priority validation happens BEFORE creation (never after) — a caller
    # error (an unknown value), never a budget refusal; see
    # _validate_priority_value's own docstring.
    [ -n "$PRIORITY" ] && _validate_priority_value "$PRIORITY"

    # Phase D default (#5827, master plan WS1 Phase D — "Backlog IS the
    # parked state... every new issue... lands in Backlog"): when --project
    # is given (so a board write is even possible — this script is
    # product-agnostic and never hardcodes a project number) but --triage
    # was NOT, default the triage status to Backlog so `create` always adds
    # the issue to the board rather than leaving it off entirely. An
    # explicit --triage always wins; this only fills a genuine omission.
    #
    # TRIAGE_WAS_DEFAULTED (fix-round 1, A1): a DEFAULTED value is SOFT, an
    # EXPLICIT --triage stays HARD. Pre-fix, this default flowed into
    # _validate_triage_status exactly like an explicit --triage, which
    # _die'd BEFORE creation on any board whose Status field has no literal
    # "Backlog" option — filing NOTHING, the exact "lost finding" Phase D
    # forbids (proven by execution: a project fixture with no Backlog
    # option refused create outright). The flag lets the validation branch
    # below tell the two cases apart without threading a second parameter
    # through _validate_triage_status's existing single-arg signature.
    TRIAGE_WAS_DEFAULTED=""
    if [ -z "$TRIAGE" ] && [ -n "$PROJECT" ]; then
      TRIAGE="Backlog"
      TRIAGE_WAS_DEFAULTED="1"
    fi

    # --triage validation happens BEFORE creation (never after) so an
    # EXPLICIT unknown status still refuses cleanly with nothing filed — see
    # _validate_triage_status. A DEFAULTED Backlog that turns out invalid on
    # THIS board is handled inside _validate_triage_status itself (soft:
    # warns and clears $TRIAGE rather than dying), per TRIAGE_WAS_DEFAULTED
    # above.
    [ -n "$TRIAGE" ] && _validate_triage_status "$TRIAGE"

    # OBSERVER-FIRST WARN (#5827, master plan WS1 Phase D — "Layer 1 is
    # warn-first too"): during the observer window a create lacking
    # --priority OR any of the three label classes (type/area:/difficulty:)
    # logs `create-missing-triage` and STILL FILES — nothing is ever
    # dropped or refused for budget reasons. This is Layer 1's own log
    # line, distinct from (and in addition to) Layer 2's
    # issue_create_observer.py hook, which observes the Bash tool call
    # itself rather than what this script decided; both are expected to
    # agree in practice, but this line is emitted from inside the script so
    # it fires even when gh_issue.sh is invoked in a context the PreToolUse
    # hook chain never sees (e.g. a unit test driving this script directly,
    # or CSA_DISABLE_HOOKS=1).
    #
    # The stderr WARNING fires HERE, before creation (an agent watching the
    # command run should see it immediately) — but the JSONL WRITE is
    # DEFERRED to after `created_num` is known (fix-round 1, A3): writing it
    # here, before the issue exists, produced a row with NO issue number,
    # which board-steward's 30-event false-positive audit (the gate that
    # decides whether Phase D enforcement ever lands) cannot join back to
    # the issue it describes. `_MISSING_TRIAGE` is computed once, now, and
    # reused by `_write_missing_triage_log` below once a number (or its
    # absence, on the exec-gh fast path) is known. Best-effort, fail-open
    # (`|| true`) throughout — a logging failure must never affect whether
    # the issue gets created.
    _missing_triage_pieces() {
      local missing="" has_type="" has_area="" has_difficulty=""
      [ -n "$PRIORITY" ] || missing="${missing}priority,"
      for l in "${LABELS[@]:-}"; do
        case "$(printf '%s' "$l" | tr '[:upper:]' '[:lower:]')" in
          bug|enhancement|feature|chore|epic|documentation) has_type=1 ;;
        esac
        case "$(printf '%s' "$l" | tr '[:upper:]' '[:lower:]')" in
          area:*) has_area=1 ;;
        esac
        case "$(printf '%s' "$l" | tr '[:upper:]' '[:lower:]')" in
          difficulty:*) has_difficulty=1 ;;
        esac
      done
      [ -n "$has_type" ]       || missing="${missing}type-label,"
      [ -n "$has_area" ]       || missing="${missing}area-label,"
      [ -n "$has_difficulty" ] || missing="${missing}difficulty-label,"
      printf '%s' "${missing%,}"
    }
    # _write_missing_triage_log <issue-or-empty> <note-or-empty> — the
    # deferred JSONL write (A3). `issue` is the real issue number once
    # known, or "" on the exec-gh fast path (no number ever captured); in
    # that case `note` explains why and the JSON carries `"issue": null`
    # rather than a fabricated/guessed number.
    _write_missing_triage_log() {
      local issue="$1" note="$2"
      command -v python3 >/dev/null 2>&1 || return 0
      _ENF_LOG="${HOME}/.claude/.enforcement/log.jsonl"
      mkdir -p "$(dirname "$_ENF_LOG")" 2>/dev/null || true
      python3 - "$_ENF_LOG" "$_MISSING_TRIAGE" "$TITLE" "$issue" "$note" <<'PY' 2>/dev/null || true
import json, sys, time
log_path, missing, title, issue, note = sys.argv[1:6]
try:
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "hook": "gh_issue_sh",
        "decision": "create-missing-triage",
        "missing": missing.split(",") if missing else [],
        "title": title[:200],
        "issue": int(issue) if issue.strip().isdigit() else None,
    }
    if note:
        row["note"] = note
    with open(log_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row) + "\n")
except Exception:
    pass
PY
    }
    _MISSING_TRIAGE="$(_missing_triage_pieces)"
    if [ -n "$_MISSING_TRIAGE" ]; then
      echo "gh_issue: WARNING — create is missing: $_MISSING_TRIAGE (observer window, #5827 — filing anyway; nothing is ever refused for this)" >&2
    fi

    args=(issue create --title "$TITLE")
    [ -n "$BODY_FILE" ] && args+=(--body-file "$BODY_FILE")
    for l in "${LABELS[@]:-}"; do [ -n "$l" ] && args+=(--label "$l"); done
    [ -n "$ASSIGNEE" ]  && args+=(--assignee "$ASSIGNEE")
    [ -n "$MILESTONE" ] && args+=(--milestone "$MILESTONE")

    if [ -z "$TRIAGE" ] && [ -z "$PRIORITY" ]; then
      # Neither --triage (nor its Backlog default, since --project was also
      # absent) nor --priority given: behavior is UNCHANGED from before
      # (backward compatible) — exec replaces this process with gh's own,
      # so gh's exact stdout/stderr/exit code pass through untouched.
      #
      # A3: this is the exec-gh FAST PATH — this process is about to be
      # REPLACED by gh's own (exec never returns), so the deferred JSONL
      # write must happen NOW, before exec, or it never happens at all. No
      # real issue number is ever captured on this path (gh's own stdout is
      # never parsed here), so the row carries "issue": null with an
      # explicit note rather than a guessed/fabricated number.
      if [ -n "$_MISSING_TRIAGE" ]; then
        _write_missing_triage_log "" "exec-path, number unavailable"
      fi
      exec gh "${args[@]}"
    fi

    # --triage and/or --priority given: capture gh's STDOUT ONLY (never
    # merge stderr into it — `2>&1` interleaves the two streams and can
    # reorder them relative to each other, corrupting the "URL is the final
    # line" assumption below; stderr is left to flow through LIVE to this
    # script's own stderr, via process substitution, so any real gh
    # warning/error is still visible to the caller exactly when gh emits
    # it, never silently swallowed or buffered until after the fact) so the
    # created issue's number/URL can be parsed and handed to _do_transition/
    # _write_priority_field below.
    create_out="$(gh "${args[@]}" 2> >(cat >&2))"
    create_rc=$?
    printf '%s\n' "$create_out"
    [ "$create_rc" -eq 0 ] || _die "create failed (gh exit $create_rc) — nothing to triage"
    # `gh issue create` prints the new issue's URL somewhere in its stdout
    # (documented as the final line, but parsed defensively rather than via
    # a bare `tail -n1`, which would silently misparse if gh ever emits a
    # trailing blank line or an extra informational line after the URL):
    # extract the LAST token anywhere in stdout that actually looks like an
    # issue URL (`.../issues/<digits>`), then take its trailing digits.
    created_url="$(printf '%s\n' "$create_out" | grep -oE 'https://[^[:space:]]+/issues/[0-9]+' | tail -n1)"
    created_num="${created_url##*/}"
    # Quoted with printf %q rather than bash 4.4+'s "${var@Q}" transform —
    # this script's shebang is `#!/usr/bin/env bash`, and on this machine
    # (and any stock macOS install) that resolves to the system /bin/bash,
    # which is 3.2 and has no @Q operator parameter transformation at all
    # ("bad substitution" — a real, live crash on the exact refusal path
    # this line exists for, verified against /bin/bash 3.2.57 here);
    # printf %q is POSIX-adjacent shell-quoting support present since
    # bash 2.x and portable to every bash this script actually runs under.
    quoted_out="$(printf '%q' "$create_out")"
    if [[ -z "$created_url" || ! "$created_num" =~ ^[0-9]+$ ]]; then
      # Finding 3 (fix-round 2): this branch's OWN message always said "the
      # issue was filed, triage it manually" -- encoding that as a bare
      # exit 1 contradicted the very message it prints. The issue number is
      # genuinely unknown here (gh's URL-parse failed), so PARTIAL prints
      # what evidence exists (the raw, quoted gh output) rather than a
      # fabricated number, and still exits 3, never 1.
      echo "gh_issue: PARTIAL — create succeeded but could not parse an issue number from gh's output ($quoted_out) — the issue was filed, triage/priority it manually" >&2
      echo "PARTIAL #<unknown> — issue filed, number unparseable: $quoted_out"
      exit "$EXIT_PARTIAL"
    fi
    # A3: the deferred JSONL write, now that the real issue number is known
    # — see _write_missing_triage_log's own docstring for why this can no
    # longer happen before creation.
    if [ -n "$_MISSING_TRIAGE" ]; then
      _write_missing_triage_log "$created_num" ""
    fi
    # B1 (fix-round 2): the post-create Status write uses _write_status_field,
    # NEVER _do_transition — _do_transition's eleven internal _die sites all
    # exit 1 (correct for the STANDALONE 'transition' subcommand, where
    # nothing has been filed — see that function's own comment) but WRONG
    # here, where issue #$created_num already exists and an exit 1 reads as
    # "nothing happened", driving an unattended caller to retry and file a
    # duplicate. _write_status_field carries the DEFAULTED-soft/EXPLICIT-
    # PARTIAL contract this path actually needs (see its own docstring).
    # NOTE the asymmetry with the --priority branch below, which DOES
    # carry a call-site [ -n "$PROJECT" ] test: there is deliberately no
    # such test here, and the guard lives in _write_status_field itself
    # (its literal first statement, per the trust-no-caller-convention
    # rule in its docstring). The two paths differ because an empty
    # $PROJECT means different things to them. For --priority it is a
    # dead end: there is no board to write a Priority to, so the call site
    # skips the function entirely. For --triage it is a REAL, CORRECT
    # behavior — the comment-only transition HEAD has always performed —
    # so the function must be ENTERED to perform it. A call-site test here
    # would therefore have to either duplicate that fallback or wrongly
    # skip it. Do not "restore symmetry" by adding one.
    [ -n "$TRIAGE" ] && _write_status_field "$created_num" "$TRIAGE"
    if [ -n "$PRIORITY" ]; then
      if [ -n "$PROJECT" ]; then
        # _write_priority_field itself EXITS (0 on success, EXIT_PARTIAL=3
        # on a post-create write failure — see its own docstring) rather
        # than returning, so nothing after this call in this branch ever
        # runs on failure; that is intentional, not a fallthrough bug.
        _write_priority_field "$created_num" "$PRIORITY"
      else
        # A2 fix (fix-round 1): --priority WITHOUT --project used to fall
        # through into _write_priority_field anyway, which then fired a
        # REAL GraphQL call with an EMPTY project number before dying —
        # exit 1, told the caller "the command failed" when issue
        # #$created_num already existed, and a retry filed a duplicate.
        # This is a SOFT case (Priority was never actionable without
        # --project in the first place, same class as A1's defaulted
        # Backlog) — warn, name the issue number, keep exit 0.
        echo "gh_issue: WARNING — --priority given without --project; issue #$created_num filed, Priority not set" >&2
      fi
    fi
    # Neither `[ -n "$TRIAGE" ] && ...` above nor the PRIORITY branch just
    # above it may be the LAST executed statement in this case arm: with an
    # empty $TRIAGE the `[ -n ]` test itself exits 1, and with no `set -e`
    # that becomes THIS SCRIPT'S OWN exit status (the last command run)
    # even though the write it guards succeeded (or was correctly skipped)
    # — a caller passing only --priority (TRIAGE empty) would see a false
    # non-zero exit. Pin the real exit status explicitly.
    exit 0
    ;;

  comment)
    [ -n "$NUM" ] || _die "comment requires <issue-number>"
    [ -n "$BODY_FILE" ] && [ -r "$BODY_FILE" ] || _die "comment requires a readable --body-file"
    exec gh issue comment "$NUM" --body-file "$BODY_FILE"
    ;;

  transition)
    _do_transition "$NUM" "$STATUS"
    ;;

  resolve)
    [ -n "$NUM" ] || _die "resolve requires <issue-number>"
    [ -n "$BODY_FILE" ] && [ -r "$BODY_FILE" ] || _die "resolve requires a readable --body-file (the Resolution comment)"
    [ "${#COMMITS[@]}" -gt 0 ] || _die "resolve requires at least one --commit <sha> (no close without a real fix)"
    # GUARD: every referenced commit must exist in this repo — or, with
    # --evidence-repo, in the NAMED local repo (validated as a real git repo
    # first; #5066: cross-repo evidence for board issues fixed in the runtime).
    # The guard's default is unchanged; the flag never weakens it, it only
    # redirects WHICH repo's graph is consulted, and the close comment then
    # names that repo explicitly.
    if [ -n "$EVIDENCE_REPO" ]; then
      git -C "$EVIDENCE_REPO" rev-parse --git-dir >/dev/null 2>&1 \
        || _die "--evidence-repo '$EVIDENCE_REPO' is not a git repository — refusing to close #$NUM"
    fi
    for sha in "${COMMITS[@]}"; do
      if [ -n "$EVIDENCE_REPO" ]; then
        git -C "$EVIDENCE_REPO" cat-file -e "${sha}^{commit}" 2>/dev/null \
          || _die "commit '$sha' not found in evidence repo '$EVIDENCE_REPO' — refusing to close #$NUM (fabricated-resolution guard)"
      else
        git cat-file -e "${sha}^{commit}" 2>/dev/null || _die "commit '$sha' not found in this repo — refusing to close #$NUM (fabricated-resolution guard)"
      fi
    done
    resolve_body="$BODY_FILE"
    if [ -n "$EVIDENCE_REPO" ]; then
      # The close record must NAME where the commits live — a reader of the
      # issue alone cannot otherwise tell the shas belong to a different repo.
      ev_real="$(git -C "$EVIDENCE_REPO" rev-parse --show-toplevel 2>/dev/null)" || ev_real="$EVIDENCE_REPO"
      resolve_body="$(mktemp)"
      # Cleanup on EVERY exit path (success and both _die exits below) — the
      # dispose path's own mktemp 40 lines down pairs with rm -f; this trap
      # covers the _die exits without three duplicated cleanups. Set only
      # inside this branch: on the default path resolve_body IS $BODY_FILE
      # (caller-owned, never removed).
      trap 'rm -f "$resolve_body"' EXIT
      cat "$BODY_FILE" > "$resolve_body"
      printf '\n---\n**Evidence repo:** `%s` — the resolving commit(s) above were verified against THAT repo'"'"'s git graph, not this one'"'"'s (cross-repo close per the runtime filing convention; gh_issue.sh --evidence-repo).\n' "$ev_real" >> "$resolve_body"
    fi
    gh issue comment "$NUM" --body-file "$resolve_body" || _die "failed to post resolution comment"
    gh issue close "$NUM" || _die "failed to close #$NUM"
    if [ -n "$EVIDENCE_REPO" ]; then
      echo "OK resolved & closed #$NUM (verified commits: ${COMMITS[*]} in evidence repo $ev_real)"
    else
      echo "OK resolved & closed #$NUM (verified commits: ${COMMITS[*]})"
    fi
    ;;

  dispose)
    [ -n "$NUM" ] || _die "dispose requires <issue-number>"
    [ -n "$BODY_FILE" ] && [ -r "$BODY_FILE" ] || _die "dispose requires a readable --body-file (the disposition rationale)"
    [ -n "$DISPOSITION" ] || _die "dispose requires --disposition \"duplicate-of #N\"|stale-superseded|wont-fix"
    case "$DISPOSITION" in
      "stale-superseded"|"wont-fix") : ;;
      duplicate-of*)
        dup_num="$(printf '%s' "$DISPOSITION" | sed -n 's/^duplicate-of[[:space:]]*#\([0-9][0-9]*\)$/\1/p')"
        [ -n "$dup_num" ] || _die "dispose: malformed duplicate-of disposition '$DISPOSITION' (expected \"duplicate-of #N\")"
        # Existence + open-state check, fail-OPEN only on gh TROUBLE (offline/
        # auth/rate-limit — the batch is operator-approved for those). A
        # determinate not-found, OR a determinate CLOSED target, both refuse:
        # a duplicate-of pointing at an already-closed issue is a structural
        # defect the caller must fix, not something to wave through (found by
        # agentic-systems-architect audit of the CSA repo's now-retired
        # issue-burndown workflow, .claude/workflows/issue-burndown.js
        # (deleted THE ISSUE WHEEL rollout commit 9), 2026-09-07 — the old
        # number-only check let a stale duplicate-of target pass silently).
        # This guard is unrelated to that workflow's own fate and stays
        # wired regardless of which caller drives gh_issue.sh dispose.
        #
        # stdout and stderr are captured SEPARATELY (fix-round correction,
        # code-reviewer 2026-09-07): merging them (`2>&1`) let gh's own
        # update-notifier ("a new release of gh is available...", emitted to
        # stderr on ANY command, exit 0, once/24h, no opt-out flag set here)
        # prepend onto the state string, so a genuinely CLOSED target no
        # longer matched the `CLOSED)` arm and fell through to the fail-open
        # `*)` branch — silently reintroducing the exact bug this check
        # exists to close. Reproduced by execution; see
        # test_dispose_duplicate_of_closed_target_stderr_noise_still_refused.
        dup_err_file="$(mktemp)"
        dup_state="$(gh issue view "$dup_num" --json state --jq .state 2>"$dup_err_file")"
        dup_rc=$?
        dup_err="$(cat "$dup_err_file")"
        rm -f "$dup_err_file"
        dup_state="$(printf '%s' "$dup_state" | tr -d '[:space:]')"
        if [ "$dup_rc" -eq 0 ]; then
          case "$dup_state" in
            CLOSED) _die "dispose: duplicate-of target #$dup_num is CLOSED — pick an OPEN duplicate target" ;;
            OPEN) : ;;
            *) echo "gh_issue: WARNING — duplicate-of #$dup_num returned unexpected state '$dup_state'; proceeding fail-open (batch is operator-approved)" >&2 ;;
          esac
        else
          case "$dup_err" in
            *"not found"*|*"Could not resolve"*) _die "dispose: duplicate-of target #$dup_num does not exist" ;;
            *) echo "gh_issue: WARNING — could not verify duplicate-of #$dup_num (offline?); proceeding fail-open (batch is operator-approved)" >&2 ;;
          esac
        fi
        ;;
      *) _die "dispose: unknown disposition '$DISPOSITION' (allowed: \"duplicate-of #N\", stale-superseded, wont-fix)" ;;
    esac
    dispose_comment="Disposition: $DISPOSITION — $(cat "$BODY_FILE")"
    gh issue close "$NUM" --reason "not planned" --comment "$dispose_comment" \
      || _die "dispose: gh issue close failed for #$NUM"
    echo "OK disposed #$NUM (not planned: $DISPOSITION)"
    ;;

  *)
    _die "unknown subcommand '$SUB' (create|comment|transition|resolve|dispose)"
    ;;
esac
