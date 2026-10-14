#!/usr/bin/env bash
# lane.sh — LANE CONTROL: one issue, one worktree, one branch, one ledger row.
#
# WHY THIS EXISTS
# ---------------
# `~/.claude/plans/handoff_lane_control_2026_09_23.md` and the adoption master
# plan (`plans/exampleapp/plan_lane_control_adoption_master_2026_09_20.md`).
# Agents accumulate worktrees with nothing tracking who owns them, whether their
# content ever landed, or whether they are safe to remove. CSA had 236 such
# checkouts. This helper makes a lane a FIRST-CLASS, LEDGERED object: it is
# opened against a real, pick-source-eligible issue, it is reaped only once its
# content is provably on the base ref, and every state transition appends one
# JSON row to `~/.claude/.lanes/lanes.jsonl`.
#
# GATE-CHAIN STANDING (the reason this is a script and not inline Bash)
# ---------------------------------------------------------------------
# CLAUDE.md §0/§2 forbid an AGENT from TYPING `git worktree add`, `git branch -D`,
# and friends. Both live PreToolUse chains -- the runtime one
# (`~/.claude/hooks/_lib.py`, `argv0 != "git" -> continue`) and Agency's own
# second, independent chain (`<repo>/.claude/hooks/bash_gate.py` ->
# local `block_branch_ops._classify_command`, also token-based and
# leading-git-only, VERIFIED live 2026-09-23 by tripping it) tokenize the
# literal typed command and only engage when argv[0] is `git`. A
# `bash scripts/lane.sh open 42` segment is therefore never classified as a git
# state verb, and the `git worktree add` this script runs INTERNALLY is a
# subprocess call no PreToolUse hook ever sees. This is exactly the standing
# `gh_issue.sh` already has for its internal `gh issue close`.
#
# THE INVERSE IS ALSO TRUE AND LOAD-BEARING: because agents cannot hand-type the
# recovery commands (Agency's local chain blocks even bare `git branch <name>`
# CREATION, strictly more than the runtime chain blocks), this helper must be
# complete enough that manual fallback is never needed. Hence: every refusal is
# checked BEFORE any mutation, so a refused `open` leaves zero trace to clean up.
#
# CONFIGURATION — per-repo, never hardcoded, never defaulted
# -----------------------------------------------------------
# Read from `<repo>/.claude/oversight/manifest.json` via `repo_manifest.py get`.
# A MISSING KEY IS A REFUSAL, never a guess: a silently-defaulted `lane.base_ref`
# would branch a lane off the wrong ref and the mistake would only surface at
# reap time, after work was done in it.
#   lane.base_ref       e.g. origin/main    (what a lane branches FROM)
#   lane.pr_target      e.g. main           (what its PR targets)
#   lane.branch_prefix  e.g. issues         (REQUIRED, `open` only; one lowercase
#                        path segment, pattern `^[a-z][a-z0-9-]*$`, no default —
#                        a wrong default would strand a lane under a branch name
#                        its own repo's push gate rejects. `reap`/`abandon`/`status`
#                        never read it; they take the branch from the ledger row.)
#   lane.pick_source    {kind:"project_status",project,owner,status}
#                        | {kind:"label",label} — eligibility for `open`,
#                        validated before any network call; an unknown or
#                        malformed shape refuses `bad-manifest`
#   lane.max_open       int — cap on simultaneously open lanes
#   lane.max_abandoned  int — cap on un-reaped abandoned lanes
#   lane.tracking_issue int, OPTIONAL — issue number the lane skills comment orphan
#                        findings to, IN ADDITION to always carding them (never
#                        instead of the card). This script (lane.sh) never reads
#                        this key itself; it exists only for `/lane-start` and
#                        `/lane-cleanup` (`~/.claude/skills/lane-start/SKILL.md`,
#                        `lane-cleanup/SKILL.md`), which read it via
#                        `repo_manifest.py get lane.tracking_issue`. Absent or
#                        non-integer means: card only, comment nowhere — never a
#                        guessed or hardcoded issue number, and never another
#                        repo's issue. Documented here only as a comment; no code
#                        in this script parses or validates it (tracked on
#                        #5908).
#
# TWO NAMED, DELIBERATE EXCEPTIONS to "a missing key is a refusal" above:
#   lane.link_paths     array of repo-relative strings, OPTIONAL. Genuinely
#                        optional, unlike every other `lane.*` key: read via
#                        `repo_manifest.py get --raw` directly (never `cfg()`),
#                        2>/dev/null, and a missing key / empty list / a
#                        `repo_manifest.py` failure is treated identically as
#                        "nothing extra to link" -- `lane.sh open` behaves
#                        exactly as it does with no key at all (CSA today has
#                        none). See `link_extra_paths()` below for validation
#                        (absolute paths, `..` segments, glob characters, a
#                        leading `#`/`!`/`-`, and embedded whitespace are all
#                        refused per-entry, never repo-wide) and P10 in
#                        `plans/otherapp_lane_cutover_after_deploy.md` for the
#                        rationale (a lane otherwise runs with no CI venv and
#                        no PII denylist).
#   lane.prepush_check   object, OPTIONAL. NOT read by this script at all --
#                        it is read and interpreted entirely by
#                        `~/.claude/skills/lane-cleanup/SKILL.md`'s 6.1 push
#                        card (the venv-freshness / pip-audit check run
#                        immediately before a lane's push). Documented here
#                        only so the two "optional manifest object" exceptions
#                        are named in one place; this script has no code path
#                        that touches it.
#
# SUBCOMMANDS
#   lane.sh open <issue#>              open a lane; exactly one argument, no
#                                       flags (e.g. no --repo); any extra
#                                       argument refuses `bad-args`. New
#                                       refusals: `issue-closed` (the issue is
#                                       not OPEN, for either pick-source kind)
#                                       and a widened `bad-manifest` (a bad
#                                       `lane.branch_prefix`, an unknown
#                                       `pick_source.kind`, a `label` kind with
#                                       no non-empty label, or a bad
#                                       `project_status` project/owner/status).
#   lane.sh reap <issue#>              remove a lane whose content landed
#   lane.sh reap --abandoned <issue#>  same checks, for an abandoned lane
#   lane.sh abandon <issue#>           mark abandoned; KEEPS the worktree
#   lane.sh status                     read-only ledger/worktree reconciliation;
#                                       prints five columns, ISSUE STATE ONDISK
#                                       WORKTREE BRANCH, branch from the ledger row
#
# THE `gh issue view` EXIT-CODE TRAP (the single most important correctness
# detail in this script)
# ----------------------------------------------------------------------------
# The spec says `open` must fail CLOSED on "no such issue" but WARN-ONLY when
# GitHub is unreachable. `gh issue view` returns EXIT 1 FOR BOTH (measured
# 2026-09-23: `gh issue view 999999` -> exit 1 "GraphQL: Could not resolve to an
# issue or pull request"; `GH_HOST=nonexistent.invalid gh issue view 1` -> exit 1
# "error connecting to ..."). A naive `if ! gh issue view; then refuse` inverts
# the contract on a network outage. The ONLY reliable discriminator is the
# stderr text `Could not resolve to an issue or pull request`. See `_issue_exists`.
# A CLOSED issue returns exit 0 from that same call, so "exists" != "eligible":
# a CLOSED issue is refused `issue-closed`, using the `state` field from the
# very same `--json number,state` reply, whenever GitHub answered at all
# (`ex == 0`). On the unreachable path (`ex == 2`) lane.sh cannot see the
# state at all -- that check belongs to `/lane-start`, which stops on the
# `github-unreachable` warning and re-checks on resume. Pick-source membership
# is a separate, later check (R4).
#
# N5: `repo_manifest.py get` expands `~` and `${slug}` inside every string
# value, even with `--raw`. So `${slug}` in `lane.branch_prefix` becomes the
# repo's actual slug and is accepted if that slug matches the pattern below.
# `~x` MAY expand (only when a real user `x` exists on this machine); rejected
# either way, because neither form matches `^[a-z][a-z0-9-]*$`. That is
# harmless and deliberate -- do not "fix" the expansion.
#
# N4: `open` now makes three `gh issue view` round-trips (existence, labels,
# title). Folding `title,labels` into the existence call's single
# `--json number,state,title,labels` is a follow-up, not done here.
#
# ENV OVERRIDES (for the hermetic test suite; never set in normal use)
#   LANE_DIR   — ledger dir (default ~/.claude/.lanes)
#   CLAUDE_DIR — runtime root, used to find repo_manifest.py (default ~/.claude)
#   LANE_BOARD_ITEM_LIMIT — max project items one pick-source read may return
#                (default 10000; empty, non-numeric or leading-zero values fall
#                back to the default). An ENV knob, not a manifest key: the
#                read is filtered server-side to the pick-source status, so the
#                default is never approached in practice (#5957).

set -uo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
LANE_DIR="${LANE_DIR:-$CLAUDE_DIR/.lanes}"
LEDGER="$LANE_DIR/lanes.jsonl"
REPO_MANIFEST="${REPO_MANIFEST_PY:-$CLAUDE_DIR/scripts/repo_manifest.py}"
# How deep link_node_modules() looks (find -maxdepth): a node_modules root may sit
# this many directories below the repo root. Agency's deepest are
# proposals/web-dev/otherapp/functions/node_modules and .../functions-quinn/node_modules,
# five levels down (the cap was 4 and missed both, so G0.30/G0.31 failed in a lane,
# OtherApp #6003). Keep in step with NODE_MODULES_MAX_DEPTH in Agency's
# scripts/ci/make_push_clone.sh.
LANE_NODE_MODULES_MAX_DEPTH=5

die() { printf 'lane: %s\n' "$*" >&2; exit 1; }
warn() { printf 'lane: %s\n' "$*" >&2; }
refuse() { printf 'lane: REFUSED (%s) %s\n' "$1" "$2" >&2; exit 1; }

# Bounded external call. `timeout`/`gtimeout` DO NOT EXIST on this machine; the
# perl alarm idiom is the runtime's standard substitute. It exits 142 on SIGALRM,
# which every caller here treats as an ordinary non-zero (failure) exit.
bounded() { local s="$1"; shift; perl -e 'alarm shift; exec @ARGV' "$s" "$@"; }

# ---------------------------------------------------------------------------
# repo + manifest resolution
# ---------------------------------------------------------------------------

resolve_repo() {
  REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)" || \
    refuse "not-a-repo" "not inside a git repository"
  # A lane must be opened from the MAIN checkout, never from inside another lane.
  case "$REPO_ROOT" in
    */.claude/worktrees/*) refuse "nested-lane" "run lane.sh from the main checkout, not from inside a worktree ($REPO_ROOT)" ;;
  esac
  [ -f "$REPO_ROOT/.claude/oversight/manifest.json" ] || \
    refuse "no-manifest" "$REPO_ROOT/.claude/oversight/manifest.json is absent; lane.sh has no per-repo config to read"
}

# cfg <dotted.key> -> stdout. Missing key is fatal, never defaulted.
cfg() {
  local key="$1" val
  val="$(python3 "$REPO_MANIFEST" get "$key" --repo "$REPO_ROOT" --raw 2>/dev/null)" || \
    refuse "manifest-key-missing" "$key is absent from $REPO_ROOT/.claude/oversight/manifest.json (lane.sh never defaults a lane key)"
  [ -n "$val" ] || \
    refuse "manifest-key-missing" "$key is empty in $REPO_ROOT/.claude/oversight/manifest.json"
  printf '%s' "$val"
}

load_lane_cfg() {
  LANE_BASE_REF="$(cfg lane.base_ref)" || exit 1
  LANE_PR_TARGET="$(cfg lane.pr_target)" || exit 1
  LANE_MAX_OPEN="$(cfg lane.max_open)" || exit 1
  LANE_MAX_ABANDONED="$(cfg lane.max_abandoned)" || exit 1
  LANE_PICK_SOURCE="$(cfg lane.pick_source)" || exit 1
  LANE_BOARD_ITEM_LIMIT="${LANE_BOARD_ITEM_LIMIT:-10000}"
  case "$LANE_BOARD_ITEM_LIMIT" in ''|*[!0-9]*|0*) LANE_BOARD_ITEM_LIMIT=10000 ;; esac
  GH_REPO="$(cfg github.repo)" || exit 1
  case "$LANE_MAX_OPEN" in ''|*[!0-9]*) refuse "bad-manifest" "lane.max_open must be an integer, got '$LANE_MAX_OPEN'" ;; esac
  case "$LANE_MAX_ABANDONED" in ''|*[!0-9]*) refuse "bad-manifest" "lane.max_abandoned must be an integer, got '$LANE_MAX_ABANDONED'" ;; esac
  # The remote half of e.g. `origin/main`, for `git fetch <remote> <branch>`.
  LANE_REMOTE="${LANE_BASE_REF%%/*}"
  LANE_BASE_BRANCH="${LANE_BASE_REF#*/}"
}

# ---------------------------------------------------------------------------
# ledger — append-only JSONL, one object per line
# ---------------------------------------------------------------------------
# Rows are written with a single `printf >>` to an O_APPEND fd. At these row
# sizes (well under PIPE_BUF) that is atomic, so two concurrent lanes in
# different sessions cannot interleave a half-written row.

ledger_append() {
  local event="$1" issue="$2" worktree="$3" branch="$4"
  mkdir -p "$LANE_DIR" 2>/dev/null || true
  # OWNER PID: `CLAUDE_PID` (the Claude Code CLI's own long-lived pid for this
  # session), NEVER this script's `$$`. lane.sh exits within a second of
  # writing the row, so its own pid is knowably dead the instant it lands --
  # recording it makes `lane_orphans.sh` report `dead-owner` on EVERY normally
  # opened lane (observed directly in the 2026-09-23 proof run before this
  # fix). When CLAUDE_PID is absent or unparseable the field is left NULL
  # rather than filled with a dead pid: "liveness unknown" is the honest
  # answer, and lane_orphans.sh fails OPEN on it. This mirrors
  # `hooks/file_claims.py::_owner_pid()` exactly (#4670 item 1) -- a real
  # but already-dead pid is worse than no pid, because it MASQUERADES as a
  # liveness signal instead of honestly having none.
  python3 - "$LEDGER" "$event" "$issue" "$REPO_ROOT" "$worktree" "$branch" \
      "${LANE_PR_TARGET:-}" "${CLAUDE_SESSION_ID:-}" "${CLAUDE_PID:-}" <<'PY'
import json, os, socket, sys, time
ledger, event, issue, repo, wt, branch, pr_base, session, pid = sys.argv[1:10]
try:
    owner_pid = int(pid)
except (TypeError, ValueError):
    owner_pid = None  # honest "unknown", never a knowably-dead fallback
row = {
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
    "event": event,
    "issue": int(issue),
    "repo": repo,
    "worktree": wt,
    "branch": branch,
    "pr_base": pr_base,
    "pr": None,
    "session": session or None,
    "pid": owner_pid,
    "host": socket.gethostname(),
}
line = json.dumps(row, separators=(",", ":")) + "\n"
fd = os.open(ledger, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
try:
    os.write(fd, line.encode())
finally:
    os.close(fd)
PY
}

# ledger_state -> prints "<issue>\t<state>\t<worktree>\t<branch>" for every issue
# whose LAST event is open or abandoned (i.e. every un-reaped lane), scoped to
# this repo. Last-event-wins is what makes an append-only ledger a state machine.
ledger_state() {
  [ -f "$LEDGER" ] || return 0
  python3 - "$LEDGER" "$REPO_ROOT" <<'PY'
import json, sys
ledger, repo = sys.argv[1], sys.argv[2]
last = {}
with open(ledger) as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue  # a corrupt row never wedges the tool
        if row.get("repo") != repo:
            continue
        last[row.get("issue")] = row
for issue, row in sorted(last.items(), key=lambda kv: (kv[0] is None, kv[0])):
    if row.get("event") in ("open", "abandoned"):
        print("\t".join(str(x) for x in (
            issue, row.get("event"), row.get("worktree") or "", row.get("branch") or "")))
PY
}

# ---------------------------------------------------------------------------
# issue eligibility
# ---------------------------------------------------------------------------

# _issue_exists <n> -> 0 exists | 1 provably-absent | 2 indeterminate (unreachable)
# See the exit-code-trap note in the header. The discriminator is stderr TEXT.
# On rc == 0 also sets GH_STATE from the same reply's `state` field (D2): no
# extra network call, since --json number,state already returns it. Piping
# into `python3 -c` is safe here because the SCRIPT is the `-c` argument, so
# stdin carries only data -- the lane.sh:246-idiom lesson is about `python3 -`,
# whose script itself comes from stdin, which this is not. A crash (not JSON,
# not an object) prints nothing, so GH_STATE stays empty, which the D2 check
# in cmd_open treats as unparseable and refuses -- fail-closed, never
# fail-open on a parse error.
_issue_exists() {
  local n="$1" err out rc
  err="$(mktemp 2>/dev/null)" || err=""
  if [ -n "$err" ]; then
    out="$(bounded 25 gh issue view "$n" --repo "$GH_REPO" --json number,state 2>"$err")"; rc=$?
  else
    out="$(bounded 25 gh issue view "$n" --repo "$GH_REPO" --json number,state 2>/dev/null)"; rc=$?
  fi
  GH_ERRTEXT=""
  GH_STATE=""
  [ -n "$err" ] && { GH_ERRTEXT="$(head -c 500 "$err" 2>/dev/null)"; rm -f "$err"; }
  if [ "$rc" -eq 0 ]; then
    GH_STATE="$(printf '%s' "$out" | python3 -c 'import json,sys
try:
    d = json.load(sys.stdin)
    s = d.get("state")
    print(s if isinstance(s, str) else "")
except Exception:
    pass' 2>/dev/null)"
    return 0
  fi
  case "$GH_ERRTEXT" in
    *"Could not resolve to an issue or pull request"*) return 1 ;;
  esac
  # Non-zero for any OTHER reason (network, auth, rate limit, timeout, or a
  # missing `mktemp` that cost us the error text): INDETERMINATE. Warn-only.
  return 2
}

# _in_pick_source <n> -> 0 eligible | 1 not eligible | 2 indeterminate
# (2 also covers a project_status board read that may be cut off, or board JSON
# of an unexpected shape -- never a false "not eligible"; #5957).
#
# Reads $LANE_PICK_KIND (and, for the label kind, $LANE_PICK_LABEL), set by
# cmd_open's D3 shape validation -- never re-parses $LANE_PICK_SOURCE itself.
# The `*)` unknown-kind arm is a defensive backstop cmd_open can no longer
# reach (D3 refuses `bad-manifest` on any kind other than project_status or
# label before this function is ever called).
_in_pick_source() {
  local n="$1"
  case "$LANE_PICK_KIND" in
    project_status) _in_pick_source_project_status "$n"; return $? ;;
    label) _in_pick_source_label "$n"; return $? ;;
    *) warn "unknown lane.pick_source.kind '${LANE_PICK_KIND:-}'; treating membership as INDETERMINATE"; return 2 ;;
  esac
}

_in_pick_source_project_status() {
  local n="$1" project owner status
  project="$(printf '%s' "$LANE_PICK_SOURCE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("project",""))')"
  owner="$(printf '%s' "$LANE_PICK_SOURCE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("owner",""))')"
  status="$(printf '%s' "$LANE_PICK_SOURCE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("status",""))')"
  # The status goes inside a quoted --query filter; a double quote or backslash
  # in it cannot be expressed there, so membership is INDETERMINATE (#5957).
  case "$status" in *'"'*|*'\'*) warn "pick-source status contains a quote or backslash; cannot build the board query"; return 2 ;; esac
  local tmpf rc
  tmpf="$(mktemp 2>/dev/null)" || return 2
  # Filter SERVER-SIDE to the pick-source status (#5957). An unfiltered read
  # of a 1,742-item board took ~34 s and ~1,750 GraphQL points (a third of the
  # hourly budget every session shares), and the old --limit 800 hid every
  # item past the 800th -- a Ready issue read as "not in the pick source".
  # The JSON goes straight to a FILE: `python3 -` reads its SCRIPT from stdin,
  # so piping the payload there would execute it as Python (found by
  # test_not_in_pick_source_refuses, 2026-09-23).
  if ! bounded 60 gh project item-list "$project" --owner "$owner" --format json \
      --limit "$LANE_BOARD_ITEM_LIMIT" --query "status:\"$status\"" > "$tmpf" 2>/dev/null; then
    rm -f "$tmpf"; return 2
  fi
  [ -s "$tmpf" ] || { rm -f "$tmpf"; return 2; }
  python3 - "$n" "$status" "$tmpf" "$LANE_BOARD_ITEM_LIMIT" "$GH_REPO" <<'PY'
import json, sys
n, status, path, limit, repo = int(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
def indeterminate(why):
    print(f"lane: pick-source board read inconclusive: {why}", file=sys.stderr)
    sys.exit(2)
try:
    with open(path) as fh:
        data = json.load(fh)
    items = data["items"]
    if not isinstance(items, list):
        raise TypeError("items is not a list")
except Exception as exc:  # unexpected shape is never a verdict (label arm's GAP 2)
    indeterminate(f"unexpected board JSON ({type(exc).__name__})")
for item in items:
    if not isinstance(item, dict):
        indeterminate("board item is not an object")
    content = item.get("content") or {}
    if not isinstance(content, dict):
        continue
    # Match repo AND type too: an org-owned board can hold other repos' items
    # with the same bare number (cf. priority_backfill.py CROSS-REPO SAFETY).
    if (content.get("number") == n and content.get("type") == "Issue"
            and str(content.get("repository") or "").lower() == repo.lower()):
        sys.exit(0 if item.get("status") == status else 1)
# Not found: a verdict only when the list is provably complete.
total = data.get("totalCount")
if len(items) >= limit:
    indeterminate(f"read {len(items)} items, which reached the limit {limit}")
if not isinstance(total, int) or isinstance(total, bool):
    indeterminate("board read carries no numeric totalCount")
if total > len(items):
    indeterminate(f"read {len(items)} of {total} items")
sys.exit(1)
PY
  rc=$?
  rm -f "$tmpf"
  return $rc
}

_in_pick_source_label() {
  local n="$1" tmpf rc
  tmpf="$(mktemp 2>/dev/null)" || return 2
  bounded 25 gh issue view "$n" --repo "$GH_REPO" --json labels >"$tmpf" 2>/dev/null
  if [ $? -ne 0 ]; then
    rm -f "$tmpf"
    return 2
  fi
  # Parse the FILE, never stdin -- same idiom as the project_status arm above.
  # The whole body sits in try/except Exception (GAP 2): an uncaught exception
  # would exit 1, the "not eligible" code, masquerading as a real non-match.
  # SystemExit is not an Exception, so the deliberate sys.exit calls pass
  # through untouched.
  python3 - "$LANE_PICK_LABEL" "$tmpf" <<'PY'
import json, sys
label, path = sys.argv[1], sys.argv[2]
try:
    try:
        with open(path) as fh:
            data = json.load(fh)
    except Exception:
        sys.exit(2)
    if not isinstance(data, dict):
        sys.exit(2)
    labels = data.get("labels")
    if not isinstance(labels, list):
        sys.exit(2)
    malformed = False
    for el in labels:
        if not isinstance(el, dict) or not isinstance(el.get("name"), str):
            malformed = True
            continue
        if el.get("name") == label:
            sys.exit(0)
    sys.exit(2 if malformed else 1)
except Exception:
    sys.exit(2)
PY
  rc=$?
  rm -f "$tmpf"
  return $rc
}

slugify() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]' \
    | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//' | cut -c1-40
}

# ---------------------------------------------------------------------------
# open
# ---------------------------------------------------------------------------
# EVERY refusal precedes EVERY mutation. A refused open leaves zero trace.

cmd_open() {
  # D9: `open` takes exactly one argument. lane.sh has no flags (no --repo):
  # a trailing argument is never silently dropped, it is refused before
  # anything else runs -- including before the bad-issue check, so `open`
  # with no argument still reaches that check normally ($# is 0 here).
  if [ "$#" -gt 1 ]; then
    shift
    refuse "bad-args" "open takes exactly one argument, the issue number; got extra argument(s) '$*'. lane.sh has no flags (no --repo): run it from the target repo's main checkout. Nothing was created"
  fi

  local n="${1:-}"
  case "$n" in ''|*[!0-9]*) refuse "bad-issue" "issue number must be all digits, got '${n:-<empty>}'" ;; esac

  resolve_repo
  load_lane_cfg

  # D1: lane.branch_prefix -- required, read here and nowhere else. Validated
  # before any network call.
  #
  # The pattern test is a regex kept in a variable, `[[ "$v" =~ $re ]]`, and
  # NOT a `case` glob range (`[a-z]`). A bash 3.2 `case` bracket range follows
  # the active locale's collation order: under en_US.UTF-8 (this machine's
  # AppleLocale), `[a-z]` also matches uppercase and accented letters, so a
  # glob-range check would ACCEPT `Issue`/`issué` there while rejecting them
  # under C/C.UTF-8.
  #
  # `[[ =~ ]]` with the pattern in a variable is NOT locale-independent
  # either when the pattern itself spells a POSIX-style range like `[a-z]`:
  # bash's ERE engine also follows LC_COLLATE for bracket-expression ranges,
  # so `[a-z]` inside `$re` still widens under some single-byte locales.
  # Measured: `Issue`/`ISSUES`/`iSsue` are wrongly ACCEPTED under
  # en_US.ISO8859-1, en_US.ISO8859-15, en_US.US-ASCII and de_DE.ISO8859-1
  # (the trigger is LC_COLLATE specifically, not LC_CTYPE), while C,
  # C.UTF-8, an unset locale, en_US.UTF-8, and every other tested locale
  # (et_EE.UTF-8, lt_LT.UTF-8, tr_TR.UTF-8) reject correctly. The fix is an
  # explicit character LIST, not a range: `[abc...z]` enumerates each byte
  # individually, so there is no range for collation order to reinterpret.
  # Verified locale-independent (accepts issues/tuvwxy/zz-9/a-b, rejects
  # Issue/ISSUES/iSsue/issué/é) under all locales above.
  # `null`/`true`/`false` are checked separately because they
  # are all-lowercase-letter strings the pattern alone would accept.
  LANE_BRANCH_PREFIX="$(cfg lane.branch_prefix)" || exit 1
  case "$LANE_BRANCH_PREFIX" in
    null|true|false)
      refuse "bad-manifest" "lane.branch_prefix must be one lowercase path segment (a letter, then lowercase letters, digits or hyphens; no slash), got '$LANE_BRANCH_PREFIX'"
      ;;
  esac
  local bp_re='^[abcdefghijklmnopqrstuvwxyz][abcdefghijklmnopqrstuvwxyz0123456789-]*$'
  [[ "$LANE_BRANCH_PREFIX" =~ $bp_re ]] || \
    refuse "bad-manifest" "lane.branch_prefix must be one lowercase path segment (a letter, then lowercase letters, digits or hyphens; no slash), got '$LANE_BRANCH_PREFIX'"

  # D3: pick_source shape validation, for every kind, before any network call.
  # $LANE_PICK_SOURCE is passed as an ARGV argument, never on stdin: the
  # script body is the heredoc, so stdin is unused here (a pipe into this
  # call would be silently discarded by the heredoc redirection, not merged
  # with it -- unlike the single-line `python3 -c '...'` idiom used elsewhere
  # in this file, which genuinely reads $LANE_PICK_SOURCE from a pipe).
  local vout
  vout="$(python3 - "$LANE_PICK_SOURCE" <<'PY' 2>/dev/null
import json, sys


def s(v):
    return v if isinstance(v, str) else json.dumps(v)


try:
    d = json.loads(sys.argv[1])
except Exception:
    print("lane.pick_source must be a JSON object")
    sys.exit(0)
if not isinstance(d, dict):
    print("lane.pick_source must be a JSON object")
    sys.exit(0)
kind = d.get("kind")
if kind not in ("project_status", "label"):
    print("lane.pick_source.kind must be project_status or label, got " + repr(s(kind)))
    sys.exit(0)
if kind == "label":
    label = d.get("label")
    if not isinstance(label, str) or label.strip() == "":
        print("lane.pick_source.label must be a non-empty string when kind is label")
        sys.exit(0)
else:
    project = d.get("project")
    if not isinstance(project, int) or isinstance(project, bool) or project <= 0:
        print("lane.pick_source.project must be a positive integer when kind is project_status")
        sys.exit(0)
    owner = d.get("owner")
    if not isinstance(owner, str) or owner.strip() == "":
        print("lane.pick_source.owner must be a non-empty string when kind is project_status")
        sys.exit(0)
    status = d.get("status")
    if not isinstance(status, str) or status.strip() == "":
        print("lane.pick_source.status must be a non-empty string when kind is project_status")
        sys.exit(0)
print("OK")
PY
)"
  if [ "$vout" != "OK" ]; then
    refuse "bad-manifest" "${vout:-lane.pick_source could not be validated}"
  fi
  LANE_PICK_KIND="$(printf '%s' "$LANE_PICK_SOURCE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("kind",""))' 2>/dev/null)"
  LANE_PICK_LABEL=""
  if [ "$LANE_PICK_KIND" = "label" ]; then
    LANE_PICK_LABEL="$(printf '%s' "$LANE_PICK_SOURCE" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("label",""))' 2>/dev/null)"
  fi

  # R3: existence, with the exit-code trap handled. Also sets GH_STATE.
  _issue_exists "$n"; local ex=$?
  if [ "$ex" -eq 1 ]; then
    refuse "no-such-issue" "issue #$n does not exist in $GH_REPO; nothing was created"
  elif [ "$ex" -eq 2 ]; then
    warn "WARNING github-unreachable: could not confirm issue #$n exists (${GH_ERRTEXT:-no error text}); proceeding per spec (fail CLOSED only on a proven 'no such issue')"
  fi

  # D2: closed issues are refused, for every pick-source kind, whenever
  # GitHub answered at all (ex == 0). On the unreachable path (ex == 2) the
  # state is unknown; that OPEN check belongs to /lane-start.
  if [ "$ex" -eq 0 ]; then
    [ "$GH_STATE" = "OPEN" ] || \
      refuse "issue-closed" "issue #$n is '${GH_STATE:-<unparseable>}', not OPEN, in $GH_REPO; a lane opens only on an open issue; nothing was created"
  fi

  # R4: pick-source membership (a separate question from existence -- a CLOSED
  # issue exists, but is already refused above). Indeterminate is a warn,
  # matching R3's posture, with a kind-neutral message (B2).
  if [ "$ex" -eq 0 ]; then
    _in_pick_source "$n"; local ps=$?
    if [ "$ps" -eq 1 ]; then
      if [ "$LANE_PICK_KIND" = "label" ]; then
        refuse "not-in-pick-source" "issue #$n does not carry the label '$LANE_PICK_LABEL' in $GH_REPO (exact, case-sensitive match); add that label, then retry"
      else
        refuse "not-in-pick-source" "issue #$n is not in this repo's lane pick source ($LANE_PICK_SOURCE); move it there first, then retry"
      fi
    elif [ "$ps" -eq 2 ]; then
      warn "WARNING pick-source-unreachable: could not confirm issue #$n's pick-source membership (kind ${LANE_PICK_KIND:-<none>}); proceeding"
    fi
  fi

  # R5/R6: caps.
  local state open_n abandoned_n
  state="$(ledger_state)"
  open_n="$(printf '%s\n' "$state" | grep -c $'\topen\t' || true)"
  abandoned_n="$(printf '%s\n' "$state" | grep -c $'\tabandoned\t' || true)"
  if [ "$open_n" -ge "$LANE_MAX_OPEN" ]; then
    refuse "cap-reached" "$open_n open lane(s), cap is $LANE_MAX_OPEN; reap or abandon one first (lane.sh status)"
  fi
  if [ "$abandoned_n" -ge "$LANE_MAX_ABANDONED" ]; then
    refuse "abandoned-backlog" "$abandoned_n un-reaped abandoned lane(s), cap is $LANE_MAX_ABANDONED; post the operator prune card in THIS turn and reap them before opening another"
  fi

  # R7: collision.
  local title slug branch wt
  title=""
  if [ "$ex" -eq 0 ]; then
    title="$(bounded 25 gh issue view "$n" --repo "$GH_REPO" --json title -q .title 2>/dev/null)" || title=""
  fi
  slug="$(slugify "${title:-lane}")"
  [ -n "$slug" ] || slug="lane"
  branch="${LANE_BRANCH_PREFIX}/${n}-${slug}"
  wt="$REPO_ROOT/.claude/worktrees/issue-${n}-${slug}"
  [ -e "$wt" ] && refuse "lane-exists" "$wt already exists"
  if git -C "$REPO_ROOT" show-ref --verify --quiet "refs/heads/$branch"; then
    refuse "lane-exists" "branch $branch already exists"
  fi

  # ---- mutations begin here, and not one line earlier ----
  bounded 120 git -C "$REPO_ROOT" fetch "$LANE_REMOTE" "$LANE_BASE_BRANCH" >/dev/null 2>&1 || \
    warn "WARNING fetch of $LANE_BASE_REF failed; branching from the local copy of that ref"
  git -C "$REPO_ROOT" rev-parse --verify --quiet "$LANE_BASE_REF" >/dev/null || \
    refuse "no-base-ref" "$LANE_BASE_REF does not resolve in $REPO_ROOT; nothing was created"

  mkdir -p "$REPO_ROOT/.claude/worktrees" || die "cannot create .claude/worktrees"
  # INTERNAL call -- see the gate-chain note in this file's header.
  git -C "$REPO_ROOT" worktree add -b "$branch" "$wt" "$LANE_BASE_REF" >/dev/null 2>&1 || \
    die "git worktree add failed for $wt"

  link_node_modules "$wt"
  link_extra_paths "$wt"
  # "${arr[@]:-}" not "${arr[@]}": under `set -u` on this machine's bash 3.2,
  # a bare "${arr[@]}" on a genuinely EMPTY array is "unbound variable"
  # (verified live). The `:-` default does NOT make an empty array expand to
  # nothing on this bash -- it passes ONE empty-string argument instead (a
  # known bash 3.2 quirk with `${arr[@]:-default}` on an empty array), so
  # `ensure_exclude` receives `""` as `$1` when nothing was linked. That is
  # harmless here only because `ensure_exclude`'s own loop guards each
  # positional with `[ -n "$rel" ] || continue` (see below), which silently
  # skips exactly that empty argument. Do not remove either half without the
  # other: the `:-` avoids the "unbound variable" abort, and the `[ -n ]`
  # guard is what makes its one-empty-argument side effect inert.
  ensure_exclude "${LANE_EXTRA_LINKED[@]:-}"

  ledger_append open "$n" "$wt" "$branch"
  printf 'lane: opened #%s\n  worktree %s\n  branch   %s\n  base     %s (PR -> %s)\n' \
    "$n" "$wt" "$branch" "$LANE_BASE_REF" "$LANE_PR_TARGET"
}

# A worktree carries no `node_modules`. Agency has several roots, not one -- a
# single-root recipe produces a lane that appears to work and then fails in
# `agency/src/`, `admin-app/` or the marketing functions under
# `proposals/web-dev/otherapp/`. This discovers them from the main checkout
# rather than hardcoding a list, so it is correct in any repo.
#
# Each root is printed and pruned: find never descends into a node_modules tree
# (thousands of directories, which a deeper cap would otherwise walk), nor into
# `.git` or `.claude/worktrees` (other checkouts), so a node_modules nested inside
# another one is never listed and the cap costs almost nothing.
link_node_modules() {
  local wt="$1" rel src dst
  while IFS= read -r src; do
    [ -d "$src" ] || continue
    rel="${src#$REPO_ROOT/}"
    dst="$wt/$rel"
    [ -e "$dst" ] && continue
    mkdir -p "$(dirname "$dst")" 2>/dev/null || continue
    ln -s "$src" "$dst" 2>/dev/null || warn "could not link $rel"
  done < <(find "$REPO_ROOT" -maxdepth "$LANE_NODE_MODULES_MAX_DEPTH" \
             \( -type d \( -name .git -o -path '*/.claude/worktrees' \) -prune \) -o \
             \( -type d -name node_modules -print -prune \) 2>/dev/null)
}

# ---------------------------------------------------------------------------
# link_extra_paths -- P10 (lane.link_paths, optional manifest key)
# ---------------------------------------------------------------------------
# Links a manifest-listed set of extra paths (files or directories) into the
# lane, the same way link_node_modules does for node_modules. Agency's value:
# ["agency/backend/.venv_py313_ci", "scripts/hooks/pii_denylist.txt",
#  "scripts/hooks/pii_allowlist.txt"] -- see P10 in
# plans/otherapp_lane_cutover_after_deploy.md for the full rationale (CI venv
# + PII denylist/allowlist a lane would otherwise silently run without).
#
# HARD REQUIREMENT: `lane.link_paths` is genuinely OPTIONAL. `cfg()` refuses
# by design on a missing or empty key ("lane.sh never defaults a lane key"),
# which is correct for every OTHER lane key but wrong here: a repo with no
# `lane.link_paths` (e.g. CSA today) must still open lanes exactly as before.
# So this reads the key directly through `repo_manifest.py get --raw`,
# 2>/dev/null, and NEVER treats a missing key, an empty list, or a
# repo_manifest.py failure as anything other than "no extra paths to link".
#
# Sets LANE_EXTRA_LINKED (space-free array via newline-splitting is avoided;
# a global bash array) to the repo-relative paths actually linked this call,
# so cmd_open can hand them to ensure_exclude.
LANE_EXTRA_LINKED=()

link_extra_paths() {
  local wt="$1" raw
  LANE_EXTRA_LINKED=()

  # Tolerant read: cfg() is deliberately NOT used (see the header comment
  # above). A missing key exits 3 with nothing on stdout (verified against
  # repo_manifest.py's cmd_get: KeyError -> stderr "key-missing: ..." + exit
  # 3, stdout untouched); any other repo_manifest.py failure is likewise
  # swallowed. Either way `raw` is empty and this function is a silent no-op.
  raw="$(python3 "$REPO_MANIFEST" get lane.link_paths --repo "$REPO_ROOT" --raw 2>/dev/null)" || raw=""
  [ -n "$raw" ] || return 0

  # Parse + validate the JSON array in one Python pass. Each accepted entry is
  # printed as "<repo-relative path>" on its own stdout line; a rejected
  # entry is warned about here (never fatal) via stderr, which the caller's
  # `warn` convention (printf to fd 2) matches directly -- this function
  # prints the warning text itself so bash doesn't need to re-parse reasons.
  local list
  list="$(printf '%s' "$raw" | python3 -c '
import json, sys

try:
    items = json.loads(sys.stdin.read())
except Exception as e:
    print(f"lane: WARNING lane.link_paths is not valid JSON ({e}); linking nothing extra", file=sys.stderr)
    sys.exit(0)

if not isinstance(items, list):
    print("lane: WARNING lane.link_paths is not a JSON array; linking nothing extra", file=sys.stderr)
    sys.exit(0)

for item in items:
    if not isinstance(item, str) or not item:
        print(f"lane: WARNING lane.link_paths entry {item!r} is not a non-empty string; skipped", file=sys.stderr)
        continue
    print(item)
')"

  local rel src dst
  while IFS= read -r rel; do
    [ -n "$rel" ] || continue

    # Normalize before validating: strip one leading "./" and one trailing
    # "/" so "./x" and "x/" are treated identically to "x" (a manifest author
    # copy-pasting a path from a shell prompt commonly carries one or the
    # other, and rejecting them outright would be a needless surprise for a
    # spelling that names the exact same path).
    case "$rel" in ./*) rel="${rel#./}" ;; esac
    case "$rel" in */) rel="${rel%/}" ;; esac
    [ -n "$rel" ] || continue

    # Reject glob/metacharacters and control-shape entries outright, before
    # any filesystem touch: `lane.link_paths` is a list of exact repo-relative
    # PATHS, never a pattern. `*?[]` are glob wildcards that could silently
    # expand to something the manifest author never named; a leading `#`,
    # `!` or `-` are the classic "this looks like an option/comment/negation
    # to some OTHER tool that reads this string" shapes (this file's own
    # `ensure_exclude` writes these entries verbatim into `.git/info/exclude`,
    # where a leading `!`/`#` DOES change meaning); embedded whitespace or a
    # newline can never be a legitimate single path component either.
    case "$rel" in
      *[\*\?\[\]]*)
        warn "lane.link_paths entry '$rel' contains a glob character (* ? [ ]); refused, skipped"
        continue
        ;;
      '#'*|'!'*|'-'*)
        warn "lane.link_paths entry '$rel' starts with '#', '!' or '-'; refused, skipped"
        continue
        ;;
    esac
    case "$rel" in
      *[[:space:]]*)
        warn "lane.link_paths entry '$rel' contains whitespace; refused, skipped"
        continue
        ;;
    esac

    # R1: reject absolute paths and any ".." segment outright -- before ever
    # touching the filesystem. An absolute path or a ".." segment could name
    # something outside REPO_ROOT even before symlink resolution.
    case "$rel" in
      /*)
        warn "lane.link_paths entry '$rel' is absolute; refused, skipped"
        continue
        ;;
      *..*)
        # Catches both a literal ".." segment (../x, a/../b, a/..) and a
        # component containing ".." as a substring (a..b) -- the latter is a
        # false-positive-safe over-reject, never an under-reject, which is
        # the correct bias for a safety check.
        warn "lane.link_paths entry '$rel' contains '..'; refused, skipped"
        continue
        ;;
      .git|.git/*)
        # Never link anything under .git itself: this function's own
        # destination is inside the LANE's .git (a real directory in a
        # worktree, distinct from the main tree's), so an entry naming `.git`
        # or a `.git/...` path would either try to symlink INTO the lane's own
        # git internals (corrupting them) or shadow files git itself manages.
        warn "lane.link_paths entry '$rel' is under .git; refused, skipped"
        continue
        ;;
      .claude/worktrees|.claude/worktrees/*)
        # Never link anything under .claude/worktrees: that is where every
        # lane's own worktree lives. An entry naming a path under it could
        # symlink one lane's content into another lane, or into itself.
        warn "lane.link_paths entry '$rel' is under .claude/worktrees; refused, skipped"
        continue
        ;;
    esac

    src="$REPO_ROOT/$rel"

    # R2: the resolved path must stay inside REPO_ROOT. `cd -P` resolves any
    # symlink components in the path itself (not just the final target),
    # which a pure string check on `$rel` cannot do. Only the DIRNAME needs
    # to physically exist to resolve this way; a symlink-free, ".."-free
    # relative path under an existing directory always satisfies that.
    local parent_phys
    parent_phys="$(cd -P "$(dirname "$src")" 2>/dev/null && pwd)" || parent_phys=""
    if [ -z "$parent_phys" ]; then
      # Parent directory doesn't exist on disk at all -- handled uniformly
      # below by the "not present in the main tree" skip, not a refusal: an
      # absent path is a legitimate, expected shape (P10's own scope note),
      # never an unsafe one.
      :
    else
      case "$parent_phys/" in
        "$REPO_ROOT"/*) : ;;
        *)
          warn "lane.link_paths entry '$rel' resolves outside $REPO_ROOT; refused, skipped"
          continue
          ;;
      esac
    fi

    # Skip (not fatal) a listed path absent from the main tree.
    if [ ! -e "$src" ]; then
      warn "lane.link_paths entry '$rel' does not exist in $REPO_ROOT; skipped (not created)"
      continue
    fi

    dst="$wt/$rel"
    if [ -L "$dst" ]; then
      # A symlink already sits here (e.g. a re-run of `open`, or it overlaps a
      # node_modules link). Record it ONLY when its target actually resolves
      # to the SAME source this entry names -- never a link this call did not
      # create and does not recognize. `readlink` gives the raw link text,
      # which may itself be relative; resolve it the same way the filesystem
      # would (relative to the link's own directory) before comparing.
      local existing_target existing_resolved
      existing_target="$(readlink "$dst" 2>/dev/null)" || existing_target=""
      case "$existing_target" in
        /*) existing_resolved="$existing_target" ;;
        *)  existing_resolved="$(cd -P "$(dirname "$dst")" 2>/dev/null && cd -P "$(dirname "$existing_target")" 2>/dev/null && printf '%s/%s' "$(pwd)" "$(basename "$existing_target")")" ;;
      esac
      if [ -n "$existing_resolved" ] && [ "$existing_resolved" = "$(cd -P "$(dirname "$src")" 2>/dev/null && printf '%s/%s' "$(pwd)" "$(basename "$src")")" ]; then
        LANE_EXTRA_LINKED+=("$rel")
      else
        warn "lane.link_paths entry '$rel': $dst is an existing symlink to a DIFFERENT target ($existing_target); left alone, not recorded, not excluded"
      fi
      continue
    fi
    if [ -e "$dst" ]; then
      # Real tracked or untracked content already occupies this path in the
      # lane -- e.g. the worktree genuinely carries this file/dir on its own.
      # Recording it here would write a permanent `.git/info/exclude` line for
      # it, silently hiding any FUTURE untracked content at this path from
      # `git status` in the main tree's own exclude file (ensure_exclude
      # writes into `$REPO_ROOT/.git/info/exclude`, not the lane's). Warn and
      # skip: never overwritten, never followed, never recorded as "ours".
      warn "lane.link_paths entry '$rel': $dst already exists as real content (not a symlink); left alone, not recorded, not excluded"
      continue
    fi
    mkdir -p "$(dirname "$dst")" 2>/dev/null || { warn "could not create parent dir for $rel"; continue; }
    if ln -s "$src" "$dst" 2>/dev/null; then
      LANE_EXTRA_LINKED+=("$rel")
    else
      warn "could not link $rel"
    fi
  done <<< "$list"
}

# `node_modules` symlinks must never show up as untracked noise in a lane's
# `git status` -- a dirty-looking tree blocks reap and hides real changes.
# Extra arguments (P10: LANE_EXTRA_LINKED, one repo-relative path per element)
# each get their own bare exclude line, with NO trailing slash: a symlink is
# not a directory to git, so a `foo/` pattern never matches a symlink named
# `foo`, even when the symlink's TARGET is a directory (the reason node_modules
# above is already written bare, never as `node_modules/`).
ensure_exclude() {
  local ex="$REPO_ROOT/.git/info/exclude" rel
  [ -d "$REPO_ROOT/.git" ] || return 0
  mkdir -p "$(dirname "$ex")" 2>/dev/null || return 0
  touch "$ex" 2>/dev/null || return 0
  grep -qxF -e 'node_modules' "$ex" 2>/dev/null || printf 'node_modules\n' >> "$ex"
  grep -qxF -e '**/node_modules' "$ex" 2>/dev/null || printf '**/node_modules\n' >> "$ex"
  for rel in "$@"; do
    [ -n "$rel" ] || continue
    # `-e` (not a bare pattern argument) so an entry that happens to start
    # with `-` is never misread as a grep flag -- defense in depth alongside
    # link_extra_paths's own upstream rejection of a leading `-` entry.
    grep -qxF -e "$rel" "$ex" 2>/dev/null || printf '%s\n' "$rel" >> "$ex"
  done
}

# ---------------------------------------------------------------------------
# reap
# ---------------------------------------------------------------------------
# All three checks run BEFORE anything is removed. Any failure changes nothing.

cmd_reap() {
  local want_abandoned=0
  if [ "${1:-}" = "--abandoned" ]; then want_abandoned=1; shift; fi
  local n="${1:-}"
  case "$n" in ''|*[!0-9]*) refuse "bad-issue" "issue number must be all digits, got '${n:-<empty>}'" ;; esac

  resolve_repo
  load_lane_cfg

  local row state wt branch
  row="$(ledger_state | awk -F'\t' -v n="$n" '$1==n {print; exit}')"
  [ -n "$row" ] || refuse "no-such-lane" "no open or abandoned lane for issue #$n in $REPO_ROOT"
  state="$(printf '%s' "$row" | cut -f2)"
  wt="$(printf '%s' "$row" | cut -f3)"
  branch="$(printf '%s' "$row" | cut -f4)"
  if [ "$want_abandoned" -eq 1 ] && [ "$state" != "abandoned" ]; then
    # NOTE: no backticks in these message strings -- inside double quotes a
    # backtick is COMMAND SUBSTITUTION, not quoting. An earlier draft wrote
    # "use `lane.sh reap $n`" here, which made bash RUN lane.sh recursively
    # while merely building the refusal text (found 2026-09-23).
    refuse "not-abandoned" "lane #$n is '$state', not abandoned; use: lane.sh reap $n"
  fi

  bounded 120 git -C "$REPO_ROOT" fetch "$LANE_REMOTE" "$LANE_BASE_BRANCH" >/dev/null 2>&1 || \
    warn "WARNING fetch of $LANE_BASE_REF failed; ancestry is checked against the local copy of that ref"

  # CHECK 1 — ancestry. This is what makes `git branch -D` safe below: the
  # content is provably already on the base ref, so deleting the branch
  # discards nothing. A squash-merge does NOT satisfy this and is meant not to:
  # squashed content is a different commit, so the honest answer is
  # needs-manual-reap rather than a delete this script cannot prove is safe.
  local tip
  tip="$(git -C "$REPO_ROOT" rev-parse --verify --quiet "refs/heads/$branch")" || \
    refuse "no-branch" "branch $branch does not exist; nothing removed (run: lane.sh status)"
  if ! git -C "$REPO_ROOT" merge-base --is-ancestor "$tip" "$LANE_BASE_REF" 2>/dev/null; then
    refuse "needs-manual-reap" "lane #$n tip ($branch) is NOT an ancestor of $LANE_BASE_REF; its work has not landed (or landed as a squash-merge). Nothing was removed: the worktree and branch are both still present."
  fi

  # CHECK 2 — clean tree. A git ERROR prints nothing on stdout and must never
  # read as "clean" (CLAUDE.md §2 calls this trap out by name), so the EXIT
  # STATUS is checked independently of the output being empty.
  if [ -d "$wt" ]; then
    local porcelain rc
    porcelain="$(git -C "$wt" status --porcelain 2>/dev/null)"; rc=$?
    if [ "$rc" -ne 0 ]; then
      refuse "status-unverifiable" "'git status' failed (exit $rc) in $wt; an errored status is NOT proof of a clean tree. Nothing was removed."
    fi
    if [ -n "$porcelain" ]; then
      refuse "dirty-tree" "$wt has uncommitted changes; commit or abandon them first. Nothing was removed."
    fi
  fi

  # CHECK 3 — nobody is standing in it.
  if [ -d "$wt" ] && command -v lsof >/dev/null 2>&1; then
    local busy
    busy="$(bounded 15 lsof -t +D "$wt" 2>/dev/null | head -5)"
    if [ -n "$busy" ]; then
      refuse "lane-busy" "process(es) [$(printf '%s' "$busy" | tr '\n' ' ')] have files open under $wt; nothing was removed"
    fi
  fi

  # ---- removal. NEVER --force: forcing is exactly the discard this gate exists
  # to prevent, and it is forbidden outright by CLAUDE.md §2. ----
  if [ -d "$wt" ]; then
    git -C "$REPO_ROOT" worktree remove "$wt" >/dev/null 2>&1 || \
      die "git worktree remove failed for $wt (NOT retried with --force, which is forbidden)"
  fi
  git -C "$REPO_ROOT" worktree prune >/dev/null 2>&1 || true
  git -C "$REPO_ROOT" branch -D "$branch" >/dev/null 2>&1 || \
    warn "branch -D $branch failed; the worktree is gone but the branch remains"

  ledger_append reaped "$n" "$wt" "$branch"
  printf 'lane: reaped #%s (%s; content confirmed on %s)\n' "$n" "$branch" "$LANE_BASE_REF"
}

# ---------------------------------------------------------------------------
# abandon — ledger only. The worktree is KEPT, deliberately: abandoning says
# "I am not working this now", never "destroy what is in it". Abandoned lanes
# do not count toward the open cap (they have their own, separate cap).
# ---------------------------------------------------------------------------

cmd_abandon() {
  local n="${1:-}"
  case "$n" in ''|*[!0-9]*) refuse "bad-issue" "issue number must be all digits, got '${n:-<empty>}'" ;; esac
  resolve_repo
  load_lane_cfg
  local row wt branch
  row="$(ledger_state | awk -F'\t' -v n="$n" '$1==n {print; exit}')"
  [ -n "$row" ] || refuse "no-such-lane" "no open lane for issue #$n in $REPO_ROOT"
  wt="$(printf '%s' "$row" | cut -f3)"
  branch="$(printf '%s' "$row" | cut -f4)"
  ledger_append abandoned "$n" "$wt" "$branch"
  printf 'lane: abandoned #%s (worktree KEPT at %s)\n' "$n" "$wt"
}

# ---------------------------------------------------------------------------
# status — pure read. Without it, every refusal above ("cap reached") is
# unactionable, because there is no other way to see which lanes are open.
# ---------------------------------------------------------------------------

cmd_status() {
  resolve_repo
  local state
  state="$(ledger_state)"
  if [ -z "$state" ]; then
    printf 'lane: no open or abandoned lanes in %s\n' "$REPO_ROOT"
    return 0
  fi
  printf '%-8s %-10s %-8s %s  %s\n' ISSUE STATE ONDISK WORKTREE BRANCH
  while IFS=$'\t' read -r issue st wt branch; do
    [ -n "$issue" ] || continue
    local ondisk=missing
    [ -d "$wt" ] && ondisk=present
    printf '%-8s %-10s %-8s %s  %s\n' "#$issue" "$st" "$ondisk" "$wt" "$branch"
  done <<< "$state"
}

# ---------------------------------------------------------------------------

usage() {
  cat >&2 <<'EOF'
usage: lane.sh open <issue#>
       lane.sh reap [--abandoned] <issue#>
       lane.sh abandon <issue#>
       lane.sh status
EOF
  exit 2
}

case "${1:-}" in
  open)    shift; cmd_open "$@" ;;
  reap)    shift; cmd_reap "$@" ;;
  abandon) shift; cmd_abandon "$@" ;;
  status)  shift; cmd_status "$@" ;;
  *) usage ;;
esac
