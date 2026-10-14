#!/usr/bin/env python3
"""issue_wheel_queue — Component A of THE ISSUE WHEEL: the Queue Keeper.

Renamed from sdw_queue.py (issue_wheel_consolidation.md §5, commit 2 of the
rollout) — this is the SAME module, made repo-agnostic instead of CSA-only,
plus a new fourth ranking input and a fifth merge source:

  * FIX-Q1: the ledger path is now `--ledger-rel` (relative to `--repo`),
    default byte-identical to CSA's old hardcoded path.
  * FIX-Q2: the ranked-queue snapshot glob is now `--ranked-glob` (default
    `csa_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html`, a
    date-anchored fnmatch pattern selecting exactly the same files CSA's old
    hardcoded regex `^csa_state_\\d{4}-\\d{2}-\\d{2}\\.html$` did -- code-
    reviewer round 1 found a bare `csa_state_*.html` default is NOT
    byte-identical: `*` also matches a non-date name like
    `csa_state_draft.html`, which could silently sort as "newest" ahead of
    a real dated snapshot), and its directory is a per-repo, per-`--slug`
    subdirectory (`~/.claude/plans/wheel/<slug>/`) rather than the shared
    plans/ dir, so two repos' ranked snapshots can never cross-contaminate
    each other's candidate set.
  * FIX-Q3: an item with no ranked-queue survivor at all now falls back to
    the fixed UNRANKED_FLOOR constant (1000), not "one past the worst
    ranked item" (which degenerated to rank 1 for every item whenever NO
    item had a real rank).
  * FIX-Q4: a new fourth data source, `load_tracker_tiers()`, reads the
    target repo's own launch-readiness/QA tracker HTML (`--tracker-rel`)
    and assigns every tracked issue a tier (0 = failed/blocked/notstarted,
    1 = local, 2 = everything else, deployed included — see FIX-Q5). The
    sort key is now lexicographic on (tier, effective_rank, issue), so a
    tier-2 (backlog) item can never outrank a tier-0/1 item at any age.
    Aging is also now BOUNDED (per-week, floored at 1 — see
    compute_effective_rank's own docstring) rather than unbounded-per-day.
  * FIX-Q5: `deployed` rows are deliberately tier 2, not tier 1 (see
    load_tracker_tiers's own comment) — a `wheel_repos.json`-driven
    per-repo override is a later commit, not this one.
  * FIX-Q6 (precondition only, no code here): a later commit adds rank
    inheritance / `atomic:false` pre-filtering to the ranked-queue schema.
  * FIX-Q7: a new, real fourth `merge_sources()` parameter,
    `fresh_triage_items`, unions same-night P1 triage output (verbatim P1
    `needs_work[]` schema) into the candidate set BETWEEN the ledger and
    ranked-queue merge passes — see merge_sources's own docstring for the
    exact semantics and why the existing round-3 size_points-drop branch is
    intentionally left firing against fresh items too.

`main()`'s `run` sub-command is now real `argparse` (`--repo`, `--slug`,
`--ledger-rel`, `--tracker-rel`, `--ranked-glob`, `--fresh-triage`, `--out`)
instead of the old hand-rolled `_repo_arg_from_argv` single-flag scanner
(deleted).

DETERMINISTIC, NO LLM. This module's entire job is to merge four sources of
"work that might be ready" into one deduped, validated, ranked list, and write
it to a ready.json. It never judges quality, never decides what a fix should
look like, and never dispatches anything — it is pure data plumbing plus a
fixed predicate, so its output is reproducible and auditable the same way
file_claims.py's ledger is.

Why this exists (ASA SDW design, operator-directed autonomy redesign): the
weekly ranked queue (`<slug>_state_*.html` by default `csa_state_*.html`) is
a point-in-time snapshot that goes stale daily (issues close, paths move) —
see weekly_report.txt's own mandatory pre-embed validation, added alongside
this module, which stops NEW staleness from being embedded. This module
additionally re-validates every candidate at READ time (paths on disk NOW,
git status NOW), so staleness that crept in AFTER the weekly snapshot was
written still never reaches ready.json. It is the mechanical answer to "9 of
the last 10 loop items parked" — a queue that was never actually checked
against present reality.

Four input sources, unioned and deduped by issue number:
  1. `gh issue list --state open` (with labels) — the live tracker.
  2. The newest issue_burndown_ledger.json's waves[].needs_work[] entries —
     already-triaged, real, unresolved findings with recorded size_points and
     files_touched.
  3. The newest `--ranked-glob`-matched ranked-queue HTML in
     `~/.claude/plans/wheel/<slug>/` (the embedded
     `<script type="application/json" id="oversight-ranked-queue">` element)
     — carries `rank`, which nothing else does.
  4. Same-night P1 triage output (`fresh_triage_items`, FIX-Q7) — see
     merge_sources's own docstring.

Plus one ranking-only input (FIX-Q4, not merged into candidate fields):
  5. `load_tracker_tiers()` against `--tracker-rel` — assigns a `tier` used
     only by the sort key, never merged field-by-field like `paths`.

VALID predicate (apply_valid_predicate) — ALL of:
  * open — CONFIRMED open, never merely "not known to be closed." An item
    present in source 1's own gh open-issue list is confirmed open by that
    presence; every OTHER item (ledger/ranked-queue-only, absent from that
    list) is individually confirmed via `gh issue view <n> --json state`
    (see resolve_open_state/confirm_issue_state) BEFORE ever reaching this
    predicate — an item whose state cannot be confirmed (gh unreachable, or
    the per-issue view call itself fails) is treated as closed, fail-closed,
    never silently assumed open. This predicate itself never defaults a
    missing `open` key to True.
  * not labeled dept:*, operator-only, or needs-ruling.
  * last tracker comment does not match
    /needs (a )?ruling|do not fix|blocked on operator/i.
  * every declared path in `paths` is CONTAINED inside `repo` (resolved via
    resolve_repo_relative_path — an absolute path or a `../` traversal that
    escapes the repo root is rejected outright as `path-escapes-repo`,
    regardless of whether the resolved target exists on disk) AND is NOT the
    repo root itself (a `.` or any other path/glob that resolves exactly to
    `repo` is rejected outright as `whole-repo-path`, unconditionally, even
    when other declared paths on the same item survive — mirrors the git
    commit gate's own bulk-pathspec refusal: naming "everything" is never a
    legitimate narrow path claim) AND EXISTS on disk once resolved to its
    repo-relative form (a glob is expanded; zero matches is a fail for that
    path — mirrors weekly_report.txt's own pre-embed check). An item with NO
    surviving valid path is dropped entirely; one with a partial surviving
    set is emitted with `paths` narrowed to the survivors.
  * no declared (surviving) path is currently DIRTY per `git status`
    (uncommitted local changes) — never grab a file another agent has open.
  * size_points <= 5 (unknown size_points defaults to "unknown", which fails
    this leg — a queue item this module cannot size is not "small enough",
    it is unverifiable, and the failure mode this whole module exists to
    prevent is exactly "assume it's fine and proceed").
  * not in the estimate-loop's EXCLUSIVE path set (ESTIMATE_LOOP_EXCLUSIVE) —
    that loop (harness.run_pipeline / runner.py) already owns those paths;
    the wheel must never contend with it. (NOTE — commit-2 scope: this stays
    a CSA-shaped hardcoded prefix list unchanged for now; moving it into a
    per-slug `~/.claude/knowledge/wheel_repos.json` config block is FIX-Q1's
    other half, deferred to a later commit in the rollout, not built here.)

SORT KEY (FIX-Q4): items sort lexicographically on
`(tier, effective_rank, issue)` — tier first, so a tier-2 (backlog) item can
never outrank a tier-0/1 item at any age; effective_rank second; issue number
last, for determinism. `tier` comes from `load_tracker_tiers()` (see its own
docstring) and defaults to 2 ("everything else") for any issue the tracker
doesn't mention at all.

AGING: effective_rank = rank - min(floor(age_days / 7), rank - 1) — see
compute_effective_rank's own docstring for the exact bounded-per-week,
floored-at-1 formula and the UNRANKED_FLOOR fallback (FIX-Q3). `rank` is the
item's rank from the newest ranked-queue snapshot when present (an item with
no ranked-queue survivor at all falls back to the fixed UNRANKED_FLOOR
constant), and `age_days` is computed from `first_ready_at` — the first cycle
this module has ever seen the item pass the VALID predicate, persisted across
runs in ready.json itself so an item's age survives a re-run (see
_carry_forward_first_ready_at). This makes an old, still-valid item
eventually out-rank a fresher, nominally-higher-ranked one WITHIN THE SAME
TIER (aging never crosses a tier boundary — the sort key's tier component is
evaluated first), which is the point of aging: rank alone would let a
low-priority item sit at the bottom of its tier forever while newer items
keep leapfrogging it.

RESERVED SLOT: the single OLDEST live item (by first_ready_at, ties broken by
issue number ascending for determinism) is marked reserved_slot: true in the
emitted file, guaranteeing that even under aggressive re-ranking the
longest-waiting item is never silently starved out by decision-flow alone —
a caller MAY choose to route around it, but the marker itself is unconditional
and always present whenever ready.json is non-empty.

CLI:
  python3 issue_wheel_queue.py run --repo <path> --slug <slug>
      --tracker-rel <path relative to repo>
      [--ledger-rel <path relative to repo>] [--ranked-glob <glob>]
      [--fresh-triage <path.json>] [--out <path>]
      Runs the full merge/validate/rank/write pipeline once. Prints the
      emitted JSON to stdout as well as writing it. `--repo` and `--slug`
      and `--tracker-rel` are REQUIRED — there is no baked-in product-repo
      default (this runtime is product-agnostic). `--ledger-rel` defaults to
      `_Config_Project/docs/domain/issue_burndown_ledger.json` (CSA's
      historical path, byte-identical when omitted); `--ranked-glob`
      defaults to `csa_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html`
      (a date-anchored glob, same byte-identical-selectivity rationale as
      CSA's old hardcoded regex -- see DEFAULT_RANKED_GLOB's own comment).
      `--fresh-triage`, when omitted, leaves
      `fresh_triage_items` unset/None — identical to today's behavior with
      no fresh union at all. `--out`, when present, overrides
      `CSA_SDW_READY_PATH`/`ready_path_from_env()`'s value for this
      invocation only.
  python3 issue_wheel_queue.py status
      Prints the current ready.json, if any.

Config env:
  CSA_SDW_REPO            repo to operate against. NO DEFAULT — this
                           runtime is product-agnostic (CLAUDE.md's own
                           preamble forbids a hardcoded product-repo path
                           baked into runtime config); `main()` refuses with
                           a clear message when neither this env var nor a
                           `--repo` CLI flag is supplied.
  CSA_SDW_READY_PATH       override for the emitted ready.json path (tests).
  CSA_DISABLE_HOOKS=1      master OFF (mirrors every other hook in this dir).
"""

from __future__ import annotations

import argparse
import fnmatch
import glob
import json
import math
import os
import posixpath
import re
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - conftest already inserts it
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim)

HOOK_NAME = "issue_wheel_queue"

# DEFAULT_READY_PATH still points at the old telemetry/sdw/ directory
# deliberately -- code-reviewer nit: the telemetry/sdw/ -> telemetry/wheel/
# <slug>/ move is explicitly commit 8c's scope in the rollout plan
# (issue_wheel_consolidation.md §10.1/§12), not this commit's. The
# CSA_SDW_READY_PATH env var (which every real caller sets) overrides this
# default anyway; only a caller relying on the bare default would notice.
DEFAULT_READY_PATH = os.path.join(_lib.CLAUDE_DIR, "telemetry", "sdw", "ready.json")
DEFAULT_PLANS_DIR = os.path.join(_lib.CLAUDE_DIR, "plans")
DEFAULT_MAX_SIZE_POINTS = 5
DEFAULT_LEDGER_REL = os.path.join("_Config_Project", "docs", "domain", "issue_burndown_ledger.json")
# code-reviewer blocker 2: `csa_state_*.html` (a bare `*`) is NOT selective
# enough -- fnmatch's `*` matches ANY characters including a non-date
# filename (`csa_state_draft.html`, `csa_state_backup.html`), which the old
# hardcoded regex `^csa_state_\d{4}-\d{2}-\d{2}\.html$` rejected outright.
# Since "newest" is decided by a lexicographic sort of the MATCHED
# candidates, a non-date name that sorts after every real ISO-dated
# snapshot would silently become "the newest ranked queue," feeding wrong
# ranks into the wheel with no error anywhere. This date-anchored
# character-class glob (fnmatch supports `[0-9]` classes) is the byte-
# identical-selectivity default the docstring below actually promises.
DEFAULT_RANKED_GLOB = "csa_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html"

# FIX-Q3: the constant floor a ranked-queue-unranked item's effective_rank
# falls back to, replacing the old computed "one past the worst ranked
# item" (which degenerated to a fallback of 1 -- and therefore every item
# tying at effective_rank 1 -- whenever NO item in the whole candidate set
# had a real rank at all; see compute_effective_rank's own docstring and
# rank_and_reserve's call site).
UNRANKED_FLOOR = 1000

# Labels that make an item invalid regardless of everything else. "dept:*" is
# a prefix match (see _has_excluded_label) — any dept:<name> label (the GTM
# department's own inbound-bus convention, CLAUDE.md's dispatch-only-agents
# roster) routes to that department, never this generic delivery wheel.
EXCLUDED_LABEL_PREFIXES = ("dept:",)
# "wheel:hold" (plan_wheel_exclusion_and_quiescence_2026_09_13.md, Finding 1a):
# durable, self-service, per-repo convention for any session to fence an
# issue off from the wheel (gh issue edit <n> --add-label wheel:hold),
# without needing wheel-side plumbing beyond this constant.
EXCLUDED_LABELS_EXACT = ("operator-only", "needs-ruling", "wheel:hold")

# Case-insensitive; matched against the LAST comment body only (source 1's gh
# issue view --json comments, or source 3/2's own recorded text where
# present). A hit anywhere in the comment marks the item invalid.
NEEDS_RULING_RE = re.compile(r"needs (a )?ruling|do not fix|blocked on operator", re.IGNORECASE)

# The estimate-engine loop's own exclusive path set (CLAUDE.md's own
# "⛔ BEFORE WRITING ANY TEST OR TOUCHING THE ESTIMATE ENGINE" rule + the
# harness's own domain) — the SDW must never contend with that loop's files.
# Each entry is a glob-style prefix; matched via _path_in_exclusive_set.
ESTIMATE_LOOP_EXCLUSIVE = (
    "modules/estimate_engine_v3/**",
    "modules/catalog_api_public/data/catalog_source_v3/*",
    "_Config_Project/docs/domain/catalog_rules_and_rulings.md",
    "repo_tooling/estimate_engine_tests/**",
    "_Config_Project/trade_kb/**",
)


# ---------------------------------------------------------------------------
# PURE helpers — no filesystem/network, fully unit-testable.
# ---------------------------------------------------------------------------


def repo_from_env(environ: dict | None = None) -> str | None:
    """Returns CSA_SDW_REPO, or None when unset — NIT 13's fix: this module
    is runtime infrastructure, never a specific product's code (CLAUDE.md's
    own preamble forbids a hardcoded product-repo path baked into runtime
    config), so there is no DEFAULT_REPO fallback. A caller (main()) that
    gets None back and has no `--repo` flag either must refuse outright with
    a clear message, never silently operate against an unintended repo.
    """
    env = os.environ if environ is None else environ
    return env.get("CSA_SDW_REPO") or None


def ready_path_from_env(environ: dict | None = None) -> str:
    env = os.environ if environ is None else environ
    return env.get("CSA_SDW_READY_PATH") or DEFAULT_READY_PATH


def resolve_repo_relative_path(repo: str, candidate: str) -> str | None:
    """Resolve `candidate` (as declared by an external source — gh/ledger/
    ranked-queue data, never trusted verbatim) against `repo`, and return its
    REPO-RELATIVE, normalized form iff it stays contained inside `repo`.
    Returns None when containment cannot be established — an absolute path
    (which silently discards `repo` under a naive os.path.join), a `../`
    traversal, or a symlink that resolves outside the repo root — this is the
    single choke point every declared path must pass through before it is
    trusted as "this repo's own path" anywhere downstream (dirty-path
    matching, the estimate-loop exclusive-set check). Both `repo` and
    `candidate` are resolved via os.path.realpath (symlinks included) so
    containment is checked against the SAME resolved filesystem identity on
    both sides, not a string prefix comparison that a symlink or a `..`
    segment could defeat. Pure aside from the two realpath() stats (no
    network, and realpath() itself never raises for a nonexistent path — it
    resolves as far as it can and returns the rest unresolved).
    """
    if not isinstance(candidate, str) or not candidate.strip():
        return None
    real_repo = os.path.realpath(repo)
    real_candidate = os.path.realpath(os.path.join(repo, candidate.strip()))
    if os.path.commonpath([real_candidate, real_repo]) != real_repo:
        return None
    rel = os.path.relpath(real_candidate, real_repo)
    if rel == os.curdir:
        return ""
    return rel.replace(os.sep, "/")


def _normalize_repo_relative(path: str) -> str:
    """Normalize a repo-relative path STRING for comparison purposes only —
    posixpath.normpath-based (collapses `./`, internal `..` segments, and
    duplicate separators; case-sensitive, unlike the old char-class
    `lstrip("./")` this replaces, which malformed a leading dotdir segment
    such as `.github/x` by stripping its literal leading `.`/`g` characters
    rather than treating `./` as a unit). This performs NO filesystem
    containment check and no repo-root resolution — callers that need actual
    containment guarantees use resolve_repo_relative_path() first; this is
    purely a string-shape normalizer for matching an ALREADY-TRUSTED
    repo-relative path (e.g. the surviving output of expand_and_check_paths,
    or a dirty_paths entry from `git status`, both of which are already
    repo-relative by construction) against another such path. Pure.
    """
    if not isinstance(path, str):
        return ""
    norm = posixpath.normpath(path.strip()).replace(os.sep, "/")
    if norm == ".":
        return ""
    if norm.startswith("./"):
        norm = norm[2:]
    return norm


def _path_in_exclusive_set(path: str, exclusive_set=ESTIMATE_LOOP_EXCLUSIVE) -> bool:
    """True iff `path` (repo-relative, already containment-checked by
    resolve_repo_relative_path — this function does not itself re-resolve
    against a repo root, it only normalizes the string form) falls under any
    of the estimate loop's exclusive glob prefixes. `**` matches across path
    separators (a directory subtree); a plain trailing `*` matches one path
    segment only — mirrors fnmatch's own semantics for `*` (it already
    crosses `/` since fnmatch has no directory concept), so `**` and a single
    `*` behave identically under fnmatch — both are accepted verbatim as the
    caller wrote them, since the net effect (anything under that prefix
    matches) is what matters here, not glob purity.
    """
    norm = _normalize_repo_relative(path)
    for pattern in exclusive_set:
        if fnmatch.fnmatch(norm, pattern):
            return True
        # A glob ending in "**" or "*" whose fixed prefix matches the path's
        # own prefix also counts — fnmatch already handles most of this, but
        # a literal non-glob path listed as an exact "directory" (no
        # trailing wildcard) should still match anything nested under it.
        prefix = pattern.rstrip("*")
        if prefix and prefix != pattern and norm.startswith(prefix):
            return True
        if not any(c in pattern for c in "*?[") and (norm == pattern or norm.startswith(pattern.rstrip("/") + "/")):
            return True
    return False


def _has_excluded_label(labels) -> str | None:
    """Return the offending label if `labels` (a list of label-name strings)
    carries an excluded one, else None. Pure.
    """
    for name in labels or []:
        if not isinstance(name, str):
            continue
        low = name.strip().lower()
        if low in EXCLUDED_LABELS_EXACT:
            return name
        for prefix in EXCLUDED_LABEL_PREFIXES:
            if low.startswith(prefix):
                return name
    return None


def _comment_blocks(comment_text: str | None) -> bool:
    """True iff the last-comment text matches the needs-ruling pattern. Pure."""
    if not comment_text:
        return False
    return bool(NEEDS_RULING_RE.search(comment_text))


def expand_and_check_paths(
    repo: str, paths: list, *, glob_fn=None, isfile_or_dir=None
) -> tuple[list, list, list, list]:
    """Split `paths` (repo-relative, but NEVER TRUSTED verbatim — see below)
    into (surviving, dropped, escaped, whole_repo).

    Every candidate — literal or glob-bearing — is FIRST checked for
    repo-containment via resolve_repo_relative_path(): an absolute path (which
    a naive os.path.join(repo, p) would silently let bypass `repo` entirely —
    os.path.join discards its first argument whenever the second is absolute)
    or a `../` traversal that resolves outside `repo` is rejected outright
    into `escaped`, never treated as merely "missing" (`dropped`) — a caller
    (apply_valid_predicate) must be able to tell "this path doesn't exist" from
    "this path was never actually inside the repo" and reason accordingly.
    Escape-checking happens BEFORE existence checking so an escaping path can
    never accidentally survive by resolving to something that happens to exist
    outside the repo.

    MAJOR fix (round 3): a candidate that resolves to the REPO ROOT ITSELF
    (resolve_repo_relative_path returns "" — the shape produced by "." or any
    other path/traversal that lands exactly on `repo`) is rejected into
    `whole_repo`, never `surviving`. Pre-fix, "" passed containment (it IS
    the repo, trivially), then passed _path_in_exclusive_set("") (an empty
    string matches no glob prefix) and the dirty guard (an empty string
    matches no dirty entry) — so a whole-repo claim rode through every other
    check as if it were an ordinary, narrow, single-file path, emitted as a
    reserved_slot item even with unrelated engine files dirty. This mirrors
    the git commit gate's own bulk-pathspec refusal (check_staged_scope.py):
    naming "everything" is not the same as naming specific paths, and this
    module's whole purpose is validating specific, narrow path claims.

    A literal (non-escaping, resolved-relative, non-repo-root) path survives
    iff it exists on disk (file OR directory — os.path.exists), checked
    against its RESOLVED repo-relative form. A glob-bearing path (contains
    any of `*?[`) is expanded against the repo root and every match is
    independently containment- and repo-root-checked the same way (a glob
    match can in principle resolve to the repo root itself for a pattern like
    a bare `**`, so this applies the identical guard rather than assuming a
    glob match can't misbehave); it survives iff at least one match remains
    after that check. ALL of a glob's surviving matches are folded into
    `surviving` as their resolved repo-relative form (so a `**` pattern's
    individual matches become the concrete paths downstream checks — dirty-
    check, exclusive-set — actually operate on), never the raw glob string
    itself.

    `glob_fn`/`isfile_or_dir` are injectable for hermetic tests (never touch
    the real filesystem when supplied). Pure otherwise it's a thin wrapper
    over stdlib glob.glob/os.path.exists.
    """
    glob_fn = glob_fn if glob_fn is not None else glob.glob
    isfile_or_dir = isfile_or_dir if isfile_or_dir is not None else os.path.exists

    surviving: list = []
    dropped: list = []
    escaped: list = []
    whole_repo: list = []
    for raw in paths or []:
        if not isinstance(raw, str) or not raw.strip():
            continue
        p = raw.strip()
        is_glob = any(c in p for c in "*?[")
        if is_glob:
            # Contain the GLOB PATTERN itself first -- an absolute or ../
            # pattern must never even be handed to glob.glob against the repo
            # root (glob.glob("/etc/**", ...) would happily walk /etc).
            resolved_pattern_rel = resolve_repo_relative_path(repo, p)
            if resolved_pattern_rel is None:
                escaped.append(p)
                continue
            abs_pattern = os.path.join(repo, p)
            matches = sorted(glob_fn(abs_pattern, recursive=True))
            survivors_for_p: list = []
            saw_whole_repo_match = False
            for m in matches:
                resolved_rel = resolve_repo_relative_path(repo, os.path.relpath(m, repo))
                if resolved_rel is None:
                    continue
                if resolved_rel == "":
                    saw_whole_repo_match = True
                    continue
                survivors_for_p.append(resolved_rel)
            if not survivors_for_p:
                if saw_whole_repo_match:
                    whole_repo.append(p)
                else:
                    dropped.append(p)
                continue
            surviving.extend(survivors_for_p)
        else:
            resolved_rel = resolve_repo_relative_path(repo, p)
            if resolved_rel is None:
                escaped.append(p)
                continue
            if resolved_rel == "":
                whole_repo.append(p)
                continue
            abs_path = os.path.join(repo, resolved_rel)
            if isfile_or_dir(abs_path):
                surviving.append(resolved_rel)
            else:
                dropped.append(p)
    return surviving, dropped, escaped, whole_repo


def compute_effective_rank(rank: int | None, first_ready_at, now_ts: float, fallback_rank: int) -> float:
    """effective_rank = rank - min(floor(age_days / 7), rank - 1).

    Two independent fixes live in this function (FIX-Q3 + FIX-Q4's aging
    half — described together since both changed this function's semantics
    in the same commit):

    FIX-Q3 — the fallback: `rank` None => `fallback_rank` is used instead,
    so a ledger-only item with no weekly-report rank still ages normally
    rather than crashing or being silently excluded from ranking.
    `fallback_rank` is passed in by the caller (rank_and_reserve) as the
    fixed module constant UNRANKED_FLOOR, not a computed "one past the
    worst ranked item" — the old computed fallback degenerated to rank 1
    for EVERY item whenever no item in the whole candidate set had a real
    rank at all (worst_rank defaulted to 0, so fallback_rank = 1), which is
    exactly the opposite of "unranked items sort after everything real."
    UNRANKED_FLOOR is deliberately far below any real rank, so an unranked
    item reliably sorts after every genuinely ranked one regardless of how
    many (or how few) other items in the batch have real ranks.

    FIX-Q4 — bounded, per-week aging: age is now measured in whole WEEKS,
    not days (`age_weeks = age_days // 7`), and is capped at `eff_rank - 1`
    so effective_rank can never drop below 1 — an old, low-priority item's
    rank can shrink towards 1 as it ages but never go negative or hit zero,
    which the old unbounded per-day formula could do for an old enough
    item. `eff_rank <= 0` (never expected in practice, but handled rather
    than raising) skips aging entirely (bounded_age = 0) rather than
    computing a nonsensical negative cap. Aging stays entirely WITHIN a
    tier by construction — this function has no notion of `tier` at all;
    the sort key (rank_and_reserve) evaluates `tier` before `effective_rank`,
    so no amount of aging here can ever cross a tier boundary.

    `first_ready_at` is an ISO-8601 UTC string (or None/unparseable, which
    is treated as "just became ready now" — age_days = 0, the conservative
    default that never artificially ages an item this function cannot
    actually date). Pure; never raises.
    """
    eff_rank = rank if isinstance(rank, (int, float)) else fallback_rank
    age_days = 0
    if first_ready_at:
        ts = _try_parse_iso(first_ready_at)
        if ts is not None:
            age_days = max(0, int(math.floor((now_ts - ts) / 86400.0)))
    age_weeks = age_days // 7
    bounded_age = min(age_weeks, eff_rank - 1) if eff_rank > 0 else 0
    return eff_rank - bounded_age


def _try_parse_iso(value: str) -> float | None:
    """Best-effort ISO-8601 -> epoch seconds. Never raises."""
    if not isinstance(value, str) or not value:
        return None
    v = value.strip()
    if v.endswith("Z"):
        v = v[:-1] + "+00:00"
    try:
        import datetime

        return datetime.datetime.fromisoformat(v).timestamp()
    except Exception:
        return None


def apply_valid_predicate(
    item: dict,
    *,
    repo: str,
    dirty_paths: set,
    max_size_points: int = DEFAULT_MAX_SIZE_POINTS,
    glob_fn=None,
    isfile_or_dir=None,
) -> tuple[bool, str | None, dict]:
    """Apply the full VALID predicate to one merged candidate item.

    Returns (is_valid, reason_if_invalid, possibly_narrowed_item). `item` is
    the merged, deduped candidate (see merge_sources) — this function is pure
    aside from the injectable path-check callables (no network, no git
    subprocess: `dirty_paths` is precomputed and passed in by the caller so
    this stays hermetically testable).

    Order matches the module docstring's VALID predicate list; the first
    failing leg short-circuits (cheap checks first, expensive-conceptually
    checks — path existence, dirty-check — last, mirroring the module
    docstring's own ordering).

    BLOCKER 3 fix: a MISSING `open` key defaults to False (fail closed), not
    True. `run()`'s real pipeline always resolves `open` explicitly (gh
    presence, or a confirm_issue_state() lookup) before ever calling this
    function, so a genuinely missing key here means the caller skipped that
    confirmation step — treating that as "assume open" is exactly the
    unconfirmed-state bug this predicate exists to refuse.

    MINOR 3 fix (round 3): when `open` is explicitly False AND the item
    carries an `open_state_reason` (resolve_open_state()'s own more specific
    marker — "gh-unreachable" or "unconfirmable", set alongside open=False
    for anything it could not positively confirm CLOSED), that reason is
    reported here rather than the generic "closed". Pre-fix, run()'s dropped
    log collapsed every one of these distinct cases — a genuinely confirmed
    CLOSED issue, an issue gh could not reach at all, and an issue whose
    per-issue `gh issue view` call itself failed/returned garbage — into the
    single reason string "closed", indistinguishable from each other in the
    emitted ready.json even though only ONE of the three means the issue is
    actually confirmed closed.
    """
    if not item.get("open", False):
        reason = item.get("open_state_reason")
        if not reason:
            reason = "closed" if "open" in item else "state-unconfirmed"
        return False, reason, item

    offending_label = _has_excluded_label(item.get("labels"))
    if offending_label:
        return False, f"excluded-label:{offending_label}", item

    if _comment_blocks(item.get("last_comment")):
        return False, "blocked-by-comment", item

    declared_paths = item.get("paths") or []
    surviving, dropped, escaped, whole_repo = expand_and_check_paths(
        repo, declared_paths, glob_fn=glob_fn, isfile_or_dir=isfile_or_dir
    )
    if whole_repo:
        # MAJOR fix (round 3): a candidate that resolved to the repo root
        # itself (".", or any path/glob that lands exactly on `repo`) is
        # ALWAYS invalid, regardless of whether other declared paths also
        # survived -- a whole-repo claim is never a legitimate narrow path
        # claim, and letting it ride along with unrelated surviving paths
        # would still authorize the whole tree via that one entry. Reported
        # ahead of the escaped/no-existing-paths legs since it is the
        # sharpest, most actionable reason when present at all.
        return False, f"whole-repo-path:{whole_repo[0]}", item
    if declared_paths and not surviving:
        if escaped and not dropped:
            # Every declared path was rejected specifically for escaping the
            # repo (never merely "missing") -- surface the sharper reason so
            # a caller/auditor can distinguish a data-integrity attack/bug
            # from an ordinary stale path. A MIX of escaped+dropped paths
            # still reports the generic "no-existing-paths" (both legs failed
            # for different reasons; neither alone explains the whole drop).
            return False, f"path-escapes-repo:{escaped[0]}", item
        return False, "no-existing-paths", item
    if surviving:
        item = dict(item, paths=surviving)
        if dropped:
            item["dropped_paths"] = dropped
        if escaped:
            item["escaped_paths"] = escaped

    for p in item.get("paths") or []:
        norm = _normalize_repo_relative(p)
        if norm in dirty_paths or any(
            d == norm or d.startswith(norm + "/") or norm.startswith(d + "/") for d in dirty_paths
        ):
            return False, f"dirty-path:{p}", item

    size_points = item.get("size_points")
    if not isinstance(size_points, (int, float)):
        return False, "size-unknown", item
    if size_points > max_size_points:
        return False, f"too-large:{size_points}", item

    for p in item.get("paths") or []:
        if _path_in_exclusive_set(p):
            return False, f"estimate-loop-exclusive:{p}", item

    return True, None, item


def merge_sources(
    gh_items: list,
    ledger_items: list,
    ranked_queue_items: list,
    fresh_triage_items=(),
    tracker_tiers: dict | None = None,
) -> list:
    """Union the sources by issue number, deduped, carrying every field
    each source contributes (later sources fill gaps left by earlier ones;
    the ranked queue's own `rank`/`title`/`paths` win when present since it
    is the most curated/authoritative source for those specific fields).

    Merge ORDER: gh_items -> ledger_items -> fresh_triage_items (FIX-Q7) ->
    ranked_queue_items -> a final `tier` lookup pass (FIX-Q4) over the fully
    merged dict.

    Each input item is a plain dict already normalized to this module's
    common shape by its own loader (_load_gh_open_issues /
    _load_ledger_needs_work / _load_ranked_queue) — this function performs
    no I/O and does no normalization of its own; it only merges. Pure.

    FIX-Q7 — `fresh_triage_items` (default `()`, keyword-only-in-practice
    but not keyword-enforced, matching this module's existing convention):
    same-night P1 triage output, in P1's OWN raw field-shape
    (`number`/`files_touched`/`size_points`/`reason`/`lane_hint` — the exact
    same shape load_ledger_needs_work translates from, never the internal
    `issue`/`paths`/`title` shape). Runs BETWEEN the ledger and ranked-queue
    loops: fresh values are always more current than a ledger row that may
    be up to 10 waves old, but the ranked-queue loop's existing round-3
    size_points-drop branch (below) still fires against fresh's own
    `paths`/`size_points` exactly as it does for the ledger's — this is
    intentional, not a gap; see that branch's own comment. A fresh entry
    never gets `open=True` set here (matching this function's own
    BLOCKER-3 discipline below) — `run()`'s existing confirm_issue_state_fn
    pass is the only path that resolves `open` for a fresh-only item.

    FIX-Q4 — `tracker_tiers` (default `None`, guarded to `{}` at this
    function's own use, matching the caller's `tracker_tiers or {}` guard):
    a `{issue_number: tier}` map from `load_tracker_tiers()`. After every
    other source has merged, a final pass sets `entry["tier"]` for every
    merged entry from this map, defaulting to `2` ("everything else," see
    FIX-Q5) for any issue the tracker doesn't mention. This is a lookup
    pass over the already-merged dict, NOT another per-source loop — a tier
    is a property of the issue number alone, never merged/overwritten
    field-by-field the way `paths`/`size_points` are.

    BLOCKER fix (round 3): when the ranked queue's `paths` overwrites an
    entry that already carries a `size_points` from the ledger loop above,
    and the incoming paths genuinely DIFFER from what the entry already
    had, `size_points` is dropped back to unknown rather than surviving
    coupled to a path set it was never actually sized against — see the
    `paths` branch below for the full rationale and the real-world repro it
    closes. When the ranked queue re-asserts the SAME paths the ledger
    already sized, size_points is legitimately kept.

    BLOCKER 3 fix: `open` is set to True ONLY for an item actually present in
    `gh_items` (source 1's own `gh issue list --state open` result — genuine
    confirmation the issue is open right now). A ledger-only or
    ranked-queue-only item NEVER defaults to open here — `gh issue list
    --state open` proves nothing about an issue absent from it (it could be
    closed, or simply not yet reflected in this run's gh call), so
    defaulting to open=True for those sources is exactly the "#9 was already
    CLOSED" bug class this module exists to close. Such an item is left with
    NO `open` key at all; the caller (run()) is responsible for confirming
    its real state via confirm_issue_state() before it can ever be treated as
    valid — apply_valid_predicate() itself still fails closed on a missing
    `open` key (see its own `item.get("open", False)` callsite note: that
    default only fires for a synthetic/test item built without going through
    this merge function at all; run()'s real pipeline always resolves `open`
    explicitly before calling the predicate).
    """
    merged: dict[int, dict] = {}

    for src in gh_items:
        num = src.get("issue")
        if not isinstance(num, int):
            continue
        merged.setdefault(num, {"issue": num})
        entry = merged[num]
        entry["open"] = True
        entry.setdefault("title", src.get("title"))
        entry.setdefault("labels", src.get("labels", []))
        entry.setdefault("last_comment", src.get("last_comment"))

    for src in ledger_items:
        num = src.get("issue")
        if not isinstance(num, int):
            continue
        merged.setdefault(num, {"issue": num})
        entry = merged[num]
        entry.setdefault("title", src.get("title"))
        entry.setdefault("paths", src.get("paths"))
        entry.setdefault("size_points", src.get("size_points"))
        entry.setdefault("lane_hint", src.get("lane_hint"))

    for src in fresh_triage_items:
        num = src.get("number")            # P1's own field name, matching
        if not isinstance(num, int):        # load_ledger_needs_work's identical
            continue                        # translation of the same raw shape
        merged.setdefault(num, {"issue": num})
        entry = merged[num]
        # Fresh triage OVERWRITES paths/size_points, but ONLY when the
        # incoming value is present and well-typed (a partial fresh record
        # never destroys a good prior ledger value).
        fresh_paths = src.get("files_touched")
        if fresh_paths:
            entry["paths"] = fresh_paths
        fresh_size = src.get("size_points")
        if isinstance(fresh_size, (int, float)):
            entry["size_points"] = fresh_size
        if src.get("reason"):
            entry["title"] = src.get("reason")
        if src.get("lane_hint"):
            entry["lane_hint"] = src.get("lane_hint")
        # Fresh values are TONIGHT's, always more current than a ledger row
        # that may be up to 10 waves old -- but ONLY when present and
        # well-typed (the four guarded assignments above are the complete
        # behavior; there is no unconditional fallback beneath them).

    for src in ranked_queue_items:
        num = src.get("issue")
        if not isinstance(num, int):
            continue
        merged.setdefault(num, {"issue": num})
        entry = merged[num]
        # The ranked queue is the most curated source for these three -
        # overwrite rather than setdefault.
        if src.get("rank") is not None:
            entry["rank"] = src.get("rank")
        if src.get("title"):
            entry["title"] = src.get("title")
        if src.get("paths"):
            # BLOCKER fix (round 3): `paths` is about to be overwritten with
            # the ranked queue's own set, which may be an entirely different
            # (and larger) set of files than whatever `size_points` was
            # sized against. `size_points` is set ONLY by the ledger loop
            # above (via setdefault), so it describes the LEDGER's paths,
            # never the ranked queue's — if this entry already carries a
            # size_points from that other source AND the incoming ranked
            # paths genuinely DIFFER from the paths currently on the entry
            # (a real swap, not merely the ranked queue re-asserting the
            # same set the ledger already sized), that size_points is now
            # stale relative to the paths about to replace it and must not
            # survive unchanged (real-world repro: ledger
            # {paths:['small/file.py'], size_points:1} + ranked
            # {paths:['huge/subsystem/**']} would otherwise emit VALID:True
            # on size 1 while authorizing every file the ranked glob expands
            # to). Drop it back to size-unknown (fails closed at
            # apply_valid_predicate's own size-points leg) rather than let a
            # stale size ride along with a swapped-out path set. When the
            # incoming paths are IDENTICAL to what the entry already has
            # (both sources genuinely agree on the same file set — the
            # control case), the existing size_points is still legitimately
            # sized against those exact paths and is kept. When the ranked
            # queue is the ONLY source for this issue (no ledger
            # size_points ever set), there is nothing stale to drop — the
            # entry was already size-unknown, and this is a no-op either
            # way.
            if "size_points" in entry and entry.get("paths") != src.get("paths"):
                entry.pop("size_points", None)
            entry["paths"] = src.get("paths")

    # FIX-Q4: final lookup pass, over the fully-merged dict, never another
    # per-source merge loop -- tier is a property of the issue number alone.
    tiers = tracker_tiers or {}
    for num, entry in merged.items():
        entry["tier"] = tiers.get(num, 2)

    return list(merged.values())


def _carry_forward_first_ready_at(candidates: list, previous_ready: dict, now_iso: str) -> None:
    """Mutate `candidates` in place: set first_ready_at from the PREVIOUS
    ready.json emission when that issue was already present there, else
    now_iso (this is genuinely the first cycle it has been seen ready).

    `previous_ready` is the parsed prior ready.json ({"items": [...]}) or {}
    if none exists yet. Pure aside from the in-place mutation, which is the
    documented contract (mirrors the rest of this module's "cheap in-place
    helper" shape used by merge_sources' callers).
    """
    prior_by_issue = {}
    for it in (previous_ready or {}).get("items", []) or []:
        num = it.get("issue")
        if isinstance(num, int):
            prior_by_issue[num] = it.get("first_ready_at")

    for item in candidates:
        num = item.get("issue")
        prior_ts = prior_by_issue.get(num)
        item["first_ready_at"] = prior_ts if prior_ts else now_iso


def rank_and_reserve(valid_items: list, now_ts: float) -> list:
    """Sort valid_items lexicographically on (tier, effective_rank, issue) —
    tier first (FIX-Q4: lower tier = more urgent, a tier-2 item can never
    outrank a tier-0/1 item at any age), then effective_rank ascending
    (lower = more urgent, matching the ranked queue's own rank convention:
    rank 1 is top priority), then issue number ascending for determinism —
    then mark the single oldest item (by first_ready_at, same tie-break)
    reserved_slot: true. Returns a NEW list (does not mutate the input);
    every item gets an "effective_rank" field. Pure.
    """
    if not valid_items:
        return []

    scored = []
    for it in valid_items:
        eff = compute_effective_rank(it.get("rank"), it.get("first_ready_at"), now_ts, UNRANKED_FLOOR)
        scored.append(dict(it, effective_rank=eff, reserved_slot=False))

    scored.sort(key=lambda x: (x.get("tier", 2), x["effective_rank"], x["issue"]))

    def _age_sort_key(it):
        fra = it.get("first_ready_at")
        ts = _try_parse_iso(fra) if fra else None
        # Older (smaller ts) sorts first; unparseable/missing treated as
        # "just now" (never wins the oldest-item reservation over a genuinely
        # dated item) - mirrors compute_effective_rank's own conservative
        # default.
        return (ts if ts is not None else float("inf"), it["issue"])

    oldest = min(scored, key=_age_sort_key)
    oldest["reserved_slot"] = True

    return scored


# ---------------------------------------------------------------------------
# Impure loaders — the only layer that touches gh/git/filesystem.
# ---------------------------------------------------------------------------


def _run(cmd: list, cwd: str | None = None, timeout: float = 30.0) -> tuple[str | None, bool]:
    """Run `cmd`. Returns (stdout_or_None, reachable).

    `reachable` is True iff the command process itself actually launched and
    returned SOME exit code (0 or otherwise) — i.e. `gh`/`git` was invoked at
    all. `reachable=False` means the command could not even be run (binary
    missing, permission error, timeout, any other launch-time exception) —
    this is the signal BLOCKER 4's fix distinguishes from "the command ran
    and legitimately reported zero results," which callers must never
    conflate with an unreachable tool (see load_gh_open_issues' own
    docstring). `stdout_or_None` is None on a nonzero exit code OR an
    unreachable launch — a caller that only cares about the data (the
    pre-existing contract) can keep checking that alone; BLOCKER 4's fix
    additionally consults `reachable` before deciding "confirmed empty" vs.
    "could not confirm anything."
    """
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if proc.returncode != 0:
            return None, True
        return proc.stdout, True
    except Exception:
        return None, False


def load_gh_open_issues(repo: str) -> tuple[list, bool]:
    """Source 1: `gh issue list --state open` with labels + last comment.

    Returns (items, reachable). `reachable=False` (gh binary missing,
    permission error, timeout, or any other launch-time failure — see
    _run()'s own docstring) means gh could not even be invoked — the caller
    (run()) must treat every candidate whose open/closed state depends on
    this source as UNCONFIRMABLE, never silently "not present -> assume
    closed" or "not present -> assume open" (BLOCKER 4: a gh outage must
    never silently disable the open/label/comment gates the way an
    indistinguishable "confirmed zero issues" response would).
    `reachable=True` with items=[] means gh genuinely ran and reported no
    open issues — a real, trustworthy signal, not a degraded one. A
    malformed/unparseable JSON response (gh ran, but its own output was
    garbage) is treated as reachable=True, items=[] — the process itself
    answered; a broken response body is a data-shape problem, not a
    connectivity one, and every OTHER source (ledger, ranked queue) still
    needs a definitive answer either way, which is exactly what
    confirm_issue_state() supplies per-issue for anything gh_open_issues
    didn't already resolve.
    """
    out, reachable = _run(
        [
            "gh",
            "issue",
            "list",
            "--state",
            "open",
            "--limit",
            "200",
            "--json",
            "number,title,labels,comments",
        ],
        cwd=repo,
    )
    if not reachable:
        return [], False
    if not out:
        return [], True
    try:
        rows = json.loads(out)
    except Exception:
        return [], True
    if not isinstance(rows, list):
        return [], True
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        num = row.get("number")
        if not isinstance(num, int):
            continue
        labels = [entry.get("name") for entry in (row.get("labels") or []) if isinstance(entry, dict)]
        comments = row.get("comments") or []
        last_comment = None
        if comments and isinstance(comments, list):
            last = comments[-1]
            if isinstance(last, dict):
                last_comment = last.get("body")
        result.append(
            {
                "issue": num,
                "open": True,
                "title": row.get("title"),
                "labels": labels,
                "last_comment": last_comment,
            }
        )
    return result, True


def confirm_issue_state(repo: str, issue_num: int) -> tuple[str | None, list | None, str | None]:
    """BLOCKER 3: confirm ONE issue's real state via `gh issue view <n>
    --json state,labels,comments`. Returns (state, labels, last_comment):
    `state` is "OPEN", "CLOSED", or None (unconfirmable — gh unreachable, a
    nonzero exit, or unparseable/empty output). This is the per-issue
    fallback source 1's own open-list query cannot itself provide a negative
    answer for: `gh issue list --state open` tells you which issues ARE
    open, never which ones are confirmed CLOSED — an issue simply absent
    from that list could be closed, or could be a ledger/ranked-queue-only
    item gh never had a chance to report on this run. Every such candidate
    must be individually confirmed here rather than defaulting to open (the
    exact "#9 was already CLOSED" class of bug this module exists to
    close — see the module docstring).

    MINOR 2 fix (round 3): pre-fix, this call fetched `--json state` only,
    so a ledger/ranked-queue-only item's `labels`/`last_comment` were NEVER
    populated for anything confirmed through THIS path (only gh's own
    open-list source 1 ever set them) — the excluded-label and
    blocked-by-comment gates in apply_valid_predicate then evaluated against
    None/[] VACUOUSLY (a dept:-labeled or ruling-blocked ledger/ranked-only
    OPEN item passed both gates as if it carried no labels/comments at all).
    This now fetches `state,labels,comments` in the SAME call — one gh
    round-trip, not two — so resolve_open_state can populate the item's real
    `labels`/`last_comment` fields for every candidate this function
    confirms, exactly like source 1 already does for its own items.
    `labels`/`last_comment` are None when the state itself could not be
    confirmed (unreachable/nonzero/unparseable) — there is no trustworthy
    label/comment data to report in that case either.
    """
    out, reachable = _run(
        ["gh", "issue", "view", str(issue_num), "--json", "state,labels,comments"],
        cwd=repo,
    )
    if not reachable or out is None:
        return None, None, None
    try:
        data = json.loads(out)
    except Exception:
        return None, None, None
    if not isinstance(data, dict):
        return None, None, None
    state = data.get("state")
    if state not in ("OPEN", "CLOSED"):
        return None, None, None
    labels = [entry.get("name") for entry in (data.get("labels") or []) if isinstance(entry, dict)]
    comments = data.get("comments") or []
    last_comment = None
    if comments and isinstance(comments, list):
        last = comments[-1]
        if isinstance(last, dict):
            last_comment = last.get("body")
    return state, labels, last_comment


def load_ledger_needs_work(ledger_path: str) -> list:
    """Source 2: the newest wave's waves[].needs_work[] entries.

    "Newest" = the highest `wave` number carrying a `needs_work` key at all
    (an earlier wave may not have reached triage yet). Returns [] on any
    read/parse failure or if no wave has needs_work.

    NIT 5 fix (round 3): this no longer emits a dead `"open": True` field —
    merge_sources()'s ledger loop never reads `open` off a ledger item (only
    `title`/`paths`/`size_points`/`lane_hint`; see its own docstring), so
    the value was silently dropped on every merge and never reached
    anywhere downstream. A ledger-only item's real open/closed state is
    established exclusively via confirm_issue_state() (see merge_sources'
    and resolve_open_state's own docstrings) — emitting a hardcoded True
    here that nothing consults was dead weight, not a real signal.
    """
    try:
        with open(ledger_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:
        return []
    waves = data.get("waves") if isinstance(data, dict) else None
    if not isinstance(waves, list):
        return []

    best_wave_num = None
    best_entries = None
    for w in waves:
        if not isinstance(w, dict) or not isinstance(w.get("needs_work"), list):
            continue
        wave_num = w.get("wave")
        if not isinstance(wave_num, (int, float)):
            continue
        if best_wave_num is None or wave_num > best_wave_num:
            best_wave_num = wave_num
            best_entries = w["needs_work"]

    if not best_entries:
        return []

    result = []
    for entry in best_entries:
        if not isinstance(entry, dict):
            continue
        num = entry.get("number")
        if not isinstance(num, int):
            continue
        result.append(
            {
                "issue": num,
                "title": entry.get("reason"),
                "paths": entry.get("files_touched") or [],
                "size_points": entry.get("size_points"),
                "lane_hint": "burndown-ledger",
            }
        )
    return result


def _newest_ranked_state_html(plans_dir: str, glob_pattern: str = DEFAULT_RANKED_GLOB) -> str | None:
    """FIX-Q2: `glob_pattern` (shell-glob syntax, e.g. the date-anchored
    default below, or an Agency-shaped
    `agency_state_[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].html`) replaces
    the old literal regex `^csa_state_\\d{4}-\\d{2}-\\d{2}\\.html$` —
    matched via `fnmatch.fnmatch` against each candidate filename rather
    than a hardcoded CSA-only regex, so a repo-scoped glob (thread from
    `--ranked-glob`) is exactly as selective as the old hardcoded pattern
    was for CSA's own default, without hardcoding CSA's naming convention
    into this function itself. **A bare `*` wildcard in the caller's own
    `--ranked-glob` is NOT date-anchored and can match a non-date filename
    (`csa_state_draft.html`) that sorts as "newest" ahead of a real dated
    snapshot — code-reviewer blocker, closed by making the DEFAULT
    date-anchored via character classes; a caller passing a genuinely
    looser custom glob is accepting that risk explicitly, not this
    function's own default posture.** "Newest" is still decided by
    lexicographic filename sort (ISO dates sort lexicographically =
    chronologically, same as before) — this function does not assume any
    particular date-embedding scheme beyond what the glob itself selects.
    """
    try:
        candidates = [f for f in os.listdir(plans_dir) if fnmatch.fnmatch(f, glob_pattern)]
    except Exception:
        return None
    if not candidates:
        return None
    candidates.sort()  # ISO dates sort lexicographically = chronologically
    return os.path.join(plans_dir, candidates[-1])


def load_ranked_queue(plans_dir: str, glob_pattern: str = DEFAULT_RANKED_GLOB) -> list:
    """Source 3: the newest `glob_pattern`-matched ranked-queue HTML's
    embedded ranked-queue script tag. Returns [] on any failure (no file,
    unparseable JSON, missing tag, or a missing `plans_dir` — a repo-scoped
    `~/.claude/plans/wheel/<slug>/` subdirectory that does not exist yet
    behaves identically to "no ranked queue found," never raises).

    FIX-Q2: `plans_dir` is now expected to be a REPO-SCOPED subdirectory
    (`~/.claude/plans/wheel/<slug>/`, built by the caller from `--slug`),
    not the shared `DEFAULT_PLANS_DIR` — two repos' ranked snapshots must
    never be able to cross-contaminate each other's candidate set (an
    Agency run reading CSA's ranked queue would merge CSA issue numbers
    into Agency's own candidate set, since merge_sources unions by issue
    number alone with no repo key).
    """
    path = _newest_ranked_state_html(plans_dir, glob_pattern)
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
    except Exception:
        return []
    m = re.search(
        r'<script type="application/json" id="oversight-ranked-queue">(.*?)</script>',
        html,
        re.S,
    )
    if not m:
        return []
    try:
        rows = json.loads(m.group(1))
    except Exception:
        return []
    if not isinstance(rows, list):
        return []
    result = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        num = row.get("issue")
        if not isinstance(num, int):
            continue
        result.append(
            {
                "issue": num,
                "rank": row.get("rank"),
                "title": row.get("title"),
                "paths": row.get("paths") or [],
            }
        )
    return result


def _extract_qa_rows_text(html: str) -> str | None:
    """FIX-Q4: bracket-depth-balanced, string-literal-aware scan for the
    bare `const QA_ROWS = [...]` JS array literal a launch-readiness/QA
    tracker HTML embeds (never wrapped in a `<script type="application/
    json">` tag the way the ranked queue is). A naive non-greedy regex
    FAILS on real tracker files whose array contains `];`-like substrings
    inside string values (verified against both CSA's and Agency's real
    tracker files) — this scans character-by-character, tracking bracket
    depth and whether the cursor is inside a JSON string (so a `[`/`]`
    appearing inside quoted text never perturbs depth), and returns the
    exact substring from the opening `[` through its matching closing `]`.
    Returns None when the literal isn't found or the array never closes
    (malformed source — never guess at a truncated array).
    """
    m = re.search(r'const QA_ROWS = \[', html)
    if not m:
        return None
    start = m.end() - 1  # position of the opening '['
    depth, i, in_str, esc = 0, start, False, False
    n = len(html)
    while i < n:
        c = html[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == '[':
                depth += 1
            elif c == ']':
                depth -= 1
                if depth == 0:
                    return html[start:i + 1]
        i += 1
    return None  # unterminated -- malformed source, never guess


def _strip_html_comments_outside_strings(text: str) -> str:
    """FIX-Q4: strip raw `<!-- ... -->` HTML comments that occur OUTSIDE
    any JSON string literal (never strip inside a string — a comment-shaped
    substring inside quoted text is real data, not markup). Agency's real
    tracker file embeds such comments BETWEEN array elements, which
    `json.loads` cannot parse even once the array is correctly bounded by
    `_extract_qa_rows_text` — this is an independent second defect from the
    bracket-balancing one above, not the same fix twice.
    """
    out, i, n, in_str, esc = [], 0, len(text), False, False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            i += 1
            continue
        if c == '"':
            in_str = True
            out.append(c)
            i += 1
            continue
        if text[i:i + 4] == "<!--":
            end = text.find("-->", i + 4)
            if end == -1:
                break
            i = end + 3
            continue
        out.append(c)
        i += 1
    return "".join(out)


# A row's `s` (status) field puts it in tier 0 (most urgent) when it is one
# of these three -- see load_tracker_tiers's own docstring and FIX-Q5's
# comment on why `deployed` is deliberately NOT included here or in tier 1.
_TIER_0_STATUSES = frozenset({"failed", "blocked", "notstarted"})
_TIER_1_STATUS = "local"


def load_tracker_tiers(repo: str, tracker_rel: str) -> dict:
    """FIX-Q4 — a genuine 4th data source (distinct from FIX-Q7's
    `fresh_triage_items`): reads the target repo's own launch-readiness/QA
    tracker HTML (`os.path.join(repo, tracker_rel)`), whose `const QA_ROWS`
    bare JS array literal carries every tracked issue's current status, and
    returns `{issue_number: tier}` for every issue referenced anywhere in
    it. Fails soft on ANY exception (matching load_ranked_queue's own
    established convention) — returns `{}`, never raises or propagates an
    uncaught JSONDecodeError.

    Tiering: tier 0 = a row whose `s` field is one of
    failed/blocked/notstarted (the most urgent — something is actively
    broken or stalled); tier 1 = a row whose `s` field is exactly `local`;
    tier 2 = everything else, INCLUDING `deployed` (FIX-Q5's deliberate
    decision — see the comment at the tier-assignment line below; a
    `wheel_repos.json`-driven override to promote `deployed` into tier 1 is
    a future config change, never built here).

    Issue-ref extraction: a row's `i` field is routinely a comma/space-
    separated list or free text (e.g. `"#4724, #4725"`, `"no-id"`), not a
    single token -- EVERY `#(\\d+)` match is extracted via
    `re.findall(r'#(\\d+)', str(row.get('i') or ''))` and mapped to that
    row's tier; a row with no `i` field or none matching contributes
    nothing. Collision rule: when one issue number is named by rows of two
    different tiers, it takes the LOWER (more urgent) tier number.
    """
    try:
        path = os.path.join(repo, tracker_rel)
        with open(path, encoding="utf-8") as fh:
            html = fh.read()
        arr_text = _extract_qa_rows_text(html)
        if arr_text is None:
            return {}
        stripped = _strip_html_comments_outside_strings(arr_text)
        rows = json.loads(stripped)
        if not isinstance(rows, list):
            return {}
        tiers: dict[int, int] = {}
        for row in rows:
            if not isinstance(row, dict):
                continue
            status = row.get("s")
            if status in _TIER_0_STATUSES:
                tier = 0
            elif status == _TIER_1_STATUS:
                tier = 1
            else:
                # FIX-Q5: `deployed` (and everything else not explicitly
                # tier 0/1) is deliberately tier 2 here, not tier 1 -- see
                # this function's own docstring for the rationale.
                tier = 2
            for num_str in re.findall(r'#(\d+)', str(row.get("i") or "")):
                num = int(num_str)
                if num in tiers:
                    tiers[num] = min(tiers[num], tier)
                else:
                    tiers[num] = tier
        return tiers
    except Exception:
        return {}


def load_dirty_paths(repo: str) -> tuple[set, bool]:
    """Every path (repo-relative, normalized) with an uncommitted change per
    `git status --porcelain`. Returns (dirty_paths, reachable).

    MINOR 9 fix: the module's own stated safety posture is fail-CLOSED for
    anything that could result in a WRITE (BLOCKER 3/4's open-state
    resolution both fail closed on an unconfirmed state) — an earlier
    version of this docstring said exactly that ("fails OPEN... is the wrong
    direction for a WRITE") and then contradicted itself by returning an
    empty set on failure, which IS failing open toward "nothing is dirty".
    This function now reports its own reachability explicitly instead of
    silently claiming "nothing is dirty" when git itself could not be
    consulted: `reachable=False` means `git status` could not be run at all
    (binary missing, timeout, cwd not a git repo, or any other launch-time
    failure) — the caller (run(), mirroring resolve_open_state()'s identical
    pattern for gh) must treat this the same way a gh outage is treated:
    mark the run `degraded` and refuse to emit ANY item whose dirtiness
    cannot be confirmed, rather than silently trusting an empty dirty-set
    that might just mean "couldn't check." `reachable=True` with an empty
    set is the genuine, trustworthy "nothing is dirty right now" signal.
    """
    out, _launch_ok = _run(["git", "status", "--porcelain", "-z", "-uall"], cwd=repo)
    if out is None:
        # Either the process itself never launched (_launch_ok False) or it
        # launched but exited nonzero (not a git repo, corrupt index, etc.) —
        # both mean "no trustworthy git status was obtained," which this
        # function reports uniformly as reachable=False; a caller does not
        # need (and should not have to reason about) the finer distinction
        # _run() itself draws.
        return set(), False
    dirty = set()
    # -z NUL-separates entries; a rename record is "XY old\x00new\x00".
    parts = out.split("\x00")
    i = 0
    while i < len(parts):
        entry = parts[i]
        i += 1
        if not entry:
            continue
        if len(entry) < 4:
            continue
        code = entry[:2]
        rel = entry[3:]
        dirty.add(rel)
        if code[0] == "R":  # rename: the NEXT NUL-separated part is the new path
            if i < len(parts) and parts[i]:
                dirty.add(parts[i])
                i += 1
    return dirty, True


def _read_previous_ready(ready_path: str) -> dict:
    try:
        with open(ready_path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _atomic_write_json(path: str, payload: dict) -> None:
    """Atomically REPLACE `path` with `payload` (temp file in the same dir +
    os.replace) — mirrors agent_budget._write_table's convention (see that
    module's docstring) so a crash mid-write can never corrupt/truncate
    ready.json.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Orchestration — the one impure "run everything" entry point.
# ---------------------------------------------------------------------------


def resolve_open_state(
    candidates: list,
    *,
    gh_reachable: bool,
    repo: str,
    confirm_issue_state_fn=None,
) -> tuple[list, bool]:
    """BLOCKER 3 + 4: resolve a definitive `open` field for every merged
    candidate, and report whether this run stayed fully confirmable.

    Every candidate merge_sources() emitted already carries `open: True` iff
    it was present in gh's own `--state open` list (genuine confirmation) —
    see merge_sources()'s own docstring. For every OTHER candidate (ledger-
    only or ranked-queue-only, absent from that list), this function
    confirms the real state directly via `confirm_issue_state_fn` (defaults
    to confirm_issue_state()) rather than assuming either open or closed.

    Returns (candidates_with_open_resolved, degraded). `degraded` is True
    iff gh was unreachable for the open-list call itself (`gh_reachable`
    False) — in that case NO candidate can be trusted as gh-open-list-
    confirmed, so every item lacking an explicit prior `open: True` is
    marked open=False (fail closed) WITHOUT even attempting the per-issue
    confirm call (an unreachable `gh issue list` strongly predicts an
    unreachable `gh issue view` too, and there's no reason to burn N more
    subprocess calls establishing that). When gh IS reachable, `degraded`
    stays False regardless of how many individual confirm_issue_state_fn
    calls come back unconfirmable — an unconfirmable SINGLE issue is
    represented by that item simply failing the predicate's `open` check
    (state-unconfirmed / closed), not by degrading the whole run; `degraded`
    is specifically the "the run-wide gh connectivity itself failed" signal
    BLOCKER 4 asks for, so a caller can tell "some old issue got dropped"
    from "this entire run's open/closed data cannot be trusted."

    MINOR 2 fix (round 3): `confirm_issue_state_fn` now returns
    `(state, labels, last_comment)` (mirroring confirm_issue_state()'s own
    real contract, see its docstring) rather than a bare state string — the
    label/comment data confirm_issue_state()'s single gh call already fetches
    is populated onto the item here (`item["labels"]`, `item["last_comment"]`)
    whenever the confirm call actually resolved a state, so a ledger/ranked-
    only item's excluded-label and blocked-by-comment gates see real data
    instead of evaluating vacuously against None/[].
    """
    confirm_fn = confirm_issue_state_fn if confirm_issue_state_fn is not None else confirm_issue_state
    resolved = []
    for item in candidates:
        if item.get("open") is True:
            resolved.append(item)
            continue
        item = dict(item)
        if not gh_reachable:
            item["open"] = False
            item["open_state_reason"] = "gh-unreachable"
            resolved.append(item)
            continue
        num = item.get("issue")
        state, labels, last_comment = confirm_fn(repo, num) if isinstance(num, int) else (None, None, None)
        if state == "OPEN":
            item["open"] = True
            item["labels"] = labels
            item["last_comment"] = last_comment
        elif state == "CLOSED":
            item["open"] = False
            item["labels"] = labels
            item["last_comment"] = last_comment
        else:
            item["open"] = False
            item["open_state_reason"] = "unconfirmable"
        resolved.append(item)
    return resolved, (not gh_reachable)


def run(
    *,
    repo: str,
    ledger_path: str,
    plans_dir: str,
    ready_path: str,
    ranked_glob: str = DEFAULT_RANKED_GLOB,
    tracker_rel: str | None = None,
    fresh_triage_items: list | None = None,
    now_ts: float | None = None,
    now_iso: str | None = None,
    gh_items: list | tuple | None = None,
    gh_reachable: bool | None = None,
    dirty_paths: set | tuple | None = None,
    dirty_paths_reachable: bool | None = None,
    confirm_issue_state_fn=None,
    exclude_issues: set[int] | None = None,
) -> dict:
    """Full pipeline: load sources -> merge -> resolve confirmed open/closed
    state -> carry-forward ages -> apply VALID predicate -> rank+reserve ->
    write ready.json. Returns the emitted payload dict (same shape written to
    disk).

    `gh_items`/`dirty_paths` are injectable so callers (and tests) can bypass
    the real `gh`/`git` subprocess calls entirely; when None, the real
    loaders run. `gh_items` may be a plain list (treated as a confirmed,
    reachable response — the pre-existing test convention) or a
    `(items, reachable)` tuple (BLOCKER 4: lets a test simulate gh being
    genuinely unreachable without going through the real subprocess).
    `gh_reachable` lets a caller override reachability independently of
    `gh_items` (e.g. force a degraded run against a real gh_items list, for
    testing resolve_open_state's fail-closed leg specifically). `dirty_paths`
    mirrors the same shape (a plain set = confirmed reachable, the
    pre-existing test convention; or a `(set, reachable)` tuple — MINOR 9's
    fix: git status being unreachable degrades the run exactly like gh being
    unreachable does, never silently reads as "nothing is dirty").
    `dirty_paths_reachable` is the independent override, mirroring
    `gh_reachable`.
    `confirm_issue_state_fn` is injectable (mirrors every other subprocess
    seam in this module) for BLOCKER 3's per-issue state confirmation.
    `now_ts`/`now_iso` are injectable for deterministic aging tests.
    `exclude_issues` (plan_wheel_exclusion_and_quiescence_2026_09_13.md,
    Finding 1b, P4 entry point) is a single-run-scoped set of issue numbers
    to drop from `valid_items` regardless of everything else; each dropped
    item is still recorded in `dropped_log` (reason `"env-excluded:<n>"`),
    never silently vanished from the payload. None (the default) means no
    env-sourced exclusions for this run.

    `ranked_glob` (FIX-Q2) is passed straight through to load_ranked_queue.
    `tracker_rel` (FIX-Q4), when supplied, is read via
    load_tracker_tiers(repo, tracker_rel) to build the tier map merge_sources
    consumes; when None (the default — no `--tracker-rel` given), every item
    defaults to tier 2, matching this module's pre-FIX-Q4 behavior (no
    tiering at all). `fresh_triage_items` (FIX-Q7), when supplied, is passed
    straight through to merge_sources's own `fresh_triage_items` parameter
    (guarded to `()` when None, matching the tracker_tiers guard pattern);
    when None (the default), the fresh-triage union is a no-op, identical to
    today's behavior.

    The emitted payload also carries `ranked_source: {dir, glob,
    matched_file, ranked_count}` (H6, the ranked-queue path's own
    visibility signal) — `dir`/`glob` are this call's own `plans_dir`/
    `ranked_glob`, `matched_file` is the newest ranked-queue snapshot
    `load_ranked_queue` actually read (None when the directory is absent or
    empty, or nothing matches `ranked_glob` — the SAME lookup
    `load_ranked_queue` performs internally, reused via
    `_newest_ranked_state_html` rather than re-scanning a second, possibly-
    divergent way), and `ranked_count` is the number of items that snapshot
    contributed to the candidate merge (0 whenever `matched_file` is None,
    but also possibly 0 with a real `matched_file` if that file's own
    embedded array is empty or unparseable — both are genuinely "no ranked
    data," reported identically). This is a visibility field only: it does
    not itself gate anything in this module or set `degraded` — a caller
    (issue_wheel.txt) reads it to decide whether "triaged items exist but
    ranked_count == 0" should be surfaced as `degraded_reason:
    "ranked-queue-empty"`, which is evaluated between phases, outside this
    function, exactly like RULE G-BATCH-LOSS reads P1's own `totals`.
    """
    import time as _time

    if now_ts is None:
        now_ts = _time.time()
    if now_iso is None:
        now_iso = _iso_now(now_ts)

    if gh_items is None:
        resolved_gh_items, resolved_gh_reachable = load_gh_open_issues(repo)
    elif isinstance(gh_items, tuple):
        resolved_gh_items, resolved_gh_reachable = gh_items
    else:
        resolved_gh_items, resolved_gh_reachable = gh_items, True
    if gh_reachable is not None:
        resolved_gh_reachable = gh_reachable

    ledger_items = load_ledger_needs_work(ledger_path)
    ranked_items = load_ranked_queue(plans_dir, ranked_glob)
    # H6 (rev-3 merge): ranked_source is a VISIBILITY field, not a candidate
    # input -- it reports what load_ranked_queue actually found (or didn't),
    # so a caller (issue_wheel.txt) can tell "genuinely zero ranked items"
    # apart from every other reason the queue might be thin. matched_file
    # reuses _newest_ranked_state_html's own lookup (the exact same file
    # load_ranked_queue itself just read) rather than re-scanning plans_dir
    # a second, possibly-divergent way.
    ranked_matched_file = _newest_ranked_state_html(plans_dir, ranked_glob)
    ranked_source = {
        "dir": plans_dir,
        "glob": ranked_glob,
        "matched_file": ranked_matched_file,
        "ranked_count": len(ranked_items),
    }
    tracker_tiers = load_tracker_tiers(repo, tracker_rel) if tracker_rel else {}

    if dirty_paths is None:
        resolved_dirty, resolved_dirty_reachable = load_dirty_paths(repo)
    elif isinstance(dirty_paths, tuple):
        resolved_dirty, resolved_dirty_reachable = dirty_paths
    else:
        resolved_dirty, resolved_dirty_reachable = dirty_paths, True
    if dirty_paths_reachable is not None:
        resolved_dirty_reachable = dirty_paths_reachable

    candidates = merge_sources(
        resolved_gh_items,
        ledger_items,
        ranked_items,
        fresh_triage_items or (),
        tracker_tiers or {},
    )
    candidates, gh_degraded = resolve_open_state(
        candidates,
        gh_reachable=resolved_gh_reachable,
        repo=repo,
        confirm_issue_state_fn=confirm_issue_state_fn,
    )
    degraded = gh_degraded or (not resolved_dirty_reachable)

    previous = _read_previous_ready(ready_path)
    _carry_forward_first_ready_at(candidates, previous, now_iso)

    valid_items = []
    dropped_log = []
    for item in candidates:
        if not resolved_dirty_reachable:
            # MINOR 9 fix: git status could not be confirmed at all -- no
            # item's paths can be trusted as clean, so every candidate is
            # refused (never silently treated as "not dirty"), mirroring
            # BLOCKER 4's identical fail-closed treatment of a gh outage.
            # trust-architect m7: this check deliberately runs BEFORE the
            # exclude_issues check below -- the fail-closed dirty guard must
            # win regardless of exclusion state. One side effect: an
            # explicitly-excluded issue reports "dirty-state-unconfirmed"
            # rather than "env-excluded" when git is unreachable, so
            # excluded_issues can under-report in that degraded case. Do not
            # reorder these two checks to "fix" that -- the dirty guard's
            # fail-closed priority is the more important property.
            dropped_log.append({"issue": item.get("issue"), "reason": "dirty-state-unconfirmed"})
            continue
        if exclude_issues is not None and item.get("issue") in exclude_issues:
            # trust-architect m6: use .get("issue") consistently with the
            # branch above, even though direct subscript is safe today (the
            # `in exclude_issues` check above already guarantees "issue" is
            # present and hashable) -- avoids a latent KeyError if this
            # branch is ever reordered or exclude_issues's population logic
            # changes.
            dropped_log.append(
                {"issue": item.get("issue"), "reason": f"env-excluded:{item.get('issue')}"}
            )
            continue
        ok, reason, resolved_item = apply_valid_predicate(item, repo=repo, dirty_paths=resolved_dirty)
        if ok:
            valid_items.append(resolved_item)
        else:
            dropped_log.append({"issue": item.get("issue"), "reason": reason})

    ranked = rank_and_reserve(valid_items, now_ts)

    payload = {
        "generated_at": now_iso,
        "repo": repo,
        "items": ranked,
        "dropped": dropped_log,
        "degraded": degraded,
        "ranked_source": ranked_source,
    }
    if degraded:
        reasons = []
        if gh_degraded:
            reasons.append("gh-unreachable")
        if not resolved_dirty_reachable:
            reasons.append("git-status-unreachable")
        payload["degraded_reason"] = "+".join(reasons)
    _atomic_write_json(ready_path, payload)
    return payload


def _iso_now(ts: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------------------
# Thin CLI.
# ---------------------------------------------------------------------------


def _build_run_arg_parser() -> argparse.ArgumentParser:
    """The `run` sub-command's real argparse parser (structural prerequisite
    for FIX-Q1/Q2/Q4/Q7 — none of those fixes are reachable from the CLI
    without it). Replaces the old hand-rolled `_repo_arg_from_argv` single-
    flag scanner (deleted — its only caller was `main()`'s `run` branch,
    replaced wholesale by this parser).

    `--repo` has NO default (unlike every other flag here) — deliberately:
    this runtime carries no baked-in product-repo default (CLAUDE.md's own
    preamble forbids one), so a missing `--repo` (and no CSA_SDW_REPO env
    var either) is handled explicitly in `main()` itself with the module's
    existing clear-refusal message, not argparse's own generic
    `required=True` error text — `--repo` is therefore NOT marked
    `required=True` on the parser; `main()` checks `repo_from_env()` as a
    fallback the parser itself cannot express.
    """
    parser = argparse.ArgumentParser(prog="issue_wheel_queue.py run", add_help=True)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--ledger-rel", default=DEFAULT_LEDGER_REL)
    # OPTIONAL as of THE ISSUE WHEEL plan, Phase C item 4 (FIX-Q1's other
    # half, retired rather than wired): `--tracker-rel` pointed at
    # `launch_readiness.html`/`launch-plan.html`, both deleted 2026-09-16
    # when launch readiness moved to GitHub issues — every real caller's
    # `load_tracker_tiers()` read was already failing soft to `{}` (its own
    # documented fail-soft contract), so the flag was silently dead weight
    # on every run, not a genuine dependency. Previously `required=True`;
    # `main()`'s `run` branch below now logs `tracker-disabled` once per run
    # when it is omitted rather than passing an empty string through, which
    # would have read as a genuinely-missing-but-configured tracker file
    # instead of "no tracker at all, by design".
    parser.add_argument("--tracker-rel", default=None)
    parser.add_argument("--ranked-glob", default=DEFAULT_RANKED_GLOB)
    parser.add_argument("--fresh-triage", default=None)
    parser.add_argument("--out", default=None)
    parser.add_argument("--exclude-issues", default=None)
    return parser


def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    try:
        if _lib.disabled():
            return 0
        sub = argv[0] if argv else "run"
        ready_path = ready_path_from_env()

        if sub == "run":
            parser = _build_run_arg_parser()
            args = parser.parse_args(argv[1:])

            repo = args.repo or repo_from_env()
            if not repo:
                print(
                    "issue_wheel_queue.py: error: no repo specified -- pass --repo <path> or "
                    "set CSA_SDW_REPO (this runtime carries no baked-in product-repo default)",
                    file=sys.stderr,
                )
                return 2

            # code-reviewer blocker 1: a bad --fresh-triage path/JSON must
            # refuse loudly (exit 2, no output written), never fall through
            # to the top-level `except Exception: return 0` guard below --
            # that guard existed for genuinely defensive cases before this
            # commit (main() did no file I/O of its own pre-FIX-Q7), and
            # letting a missing/corrupt P1 handoff exit 0 with a STALE
            # ready.json left on disk is exactly the "queue that was never
            # actually checked against present reality" failure this module
            # exists to prevent -- a caller checking $? would see success.
            fresh_triage_items = None
            if args.fresh_triage:
                try:
                    with open(args.fresh_triage, encoding="utf-8") as fh:
                        fresh_triage_items = json.load(fh)
                except Exception as exc:
                    print(
                        f"issue_wheel_queue.py: error: could not read --fresh-triage "
                        f"{args.fresh_triage!r}: {exc}",
                        file=sys.stderr,
                    )
                    return 2

            # Same rationale as the --fresh-triage guard immediately above: a
            # malformed --exclude-issues value must refuse loudly (exit 2),
            # never fall through to the top-level `except Exception: return 0`
            # guard, which would make a caller's $? read as success while the
            # requested exclusion silently failed to apply.
            exclude_issues = None
            if args.exclude_issues:
                tokens = args.exclude_issues.split(",")
                try:
                    # trust-architect M3: bare int() accepts a leading "+"
                    # sign and a lone "-5" (only the sign makes it negative,
                    # which is not a "bare non-negative integer" per HARD
                    # STOP 4b's contract in issue_wheel.txt), neither of which
                    # .isdigit() accepts. .isdigit() also rejects any empty
                    # token from a stray comma. trust-architect R2 correction:
                    # str.isdigit() is Unicode-aware and DOES accept non-ASCII
                    # decimal digits (e.g. full-width "１２３" or Arabic-Indic
                    # "٣") -- they parse to the correct int either way
                    # (int("１２３") == 123), so this is harmless in practice,
                    # not a validation gap; it is called out here only so a
                    # future reader does not assume ASCII-only from this
                    # comment (an earlier version of this comment claimed
                    # .isdigit() rejects non-ASCII digits, which is false).
                    stripped = [tok.strip() for tok in tokens]
                    if not all(tok.isdigit() for tok in stripped):
                        raise ValueError(
                            f"every token must be a bare non-negative integer: {stripped!r}"
                        )
                    exclude_issues = {int(tok) for tok in stripped}
                except ValueError as exc:
                    print(
                        f"issue_wheel_queue.py: error: could not parse --exclude-issues "
                        f"{args.exclude_issues!r}: {exc}",
                        file=sys.stderr,
                    )
                    return 2

            # Phase C item 4: log the disabled-tracker state ONCE per run,
            # to stderr (never stdout — stdout is the payload JSON a caller
            # may pipe/parse) rather than silently proceeding with no
            # visible trace that tiering was skipped this run.
            if not args.tracker_rel:
                print("issue_wheel_queue.py: tracker-disabled (no --tracker-rel given; every item defaults to tier 2)", file=sys.stderr)

            out_path = args.out or ready_path
            plans_dir = os.path.join(_lib.CLAUDE_DIR, "plans", "wheel", args.slug)
            payload = run(
                repo=repo,
                ledger_path=os.path.join(repo, args.ledger_rel),
                plans_dir=plans_dir,
                ready_path=out_path,
                ranked_glob=args.ranked_glob,
                tracker_rel=args.tracker_rel,
                fresh_triage_items=fresh_triage_items,
                exclude_issues=exclude_issues,
            )
            print(json.dumps(payload, indent=2))
            return 0

        if sub == "status":
            payload = _read_previous_ready(ready_path)
            print(json.dumps(payload, indent=2))
            return 0

        print("usage: issue_wheel_queue.py {run|status}", file=sys.stderr)
        return 0
    except Exception as exc:  # pragma: no cover - defensive top-level guard
        print(f"issue_wheel_queue.py: error: {exc}", file=sys.stderr)
        return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
