#!/usr/bin/env python3
"""Replay the review-round ledger under alternative boundary predicates.

WHY THIS EXISTS
---------------
`record_review.derive_review_round` decides "is this ledger entry the same
review boundary as this call?" and today answers it with
`file_claims.paths_overlap` -- UNION semantics (any shared path matches).
That predicate is correct for its own caller (contested file claims) and
wrong here: two independent features sharing one file are walked as one
chain, so a brand-new boundary can derive a high round it never earned.

Changing that predicate is not a code question, it is a MEASUREMENT
question: which real, already-recorded boundaries move, in which direction,
in which repo? This script answers it against the live ledger by replaying
every entry under both the current predicate and a candidate one.

It exists because a first attempt at that fix measured ONE repo
(`~/.claude`, ~12% of the replayable entries) and reported the result as
if it covered the whole ledger. The per-repo split is the whole point:
under the REJECTED pure-subset variant (`--reset-predicate same
--trunc-fallback none`) the runtime repo showed almost no movement while
ExampleApp showed 172 changed entries and a RISE in its tripwire
population, 76->93. A single global number would have hidden both.

Every figure here names its variant, because a figure quoted without one
is the exact error this tool exists to prevent. Counts drift: the ledger
is append-only, so re-run rather than trusting any number in this
docstring. Tracked on #5828.

READ-ONLY. Never writes to the ledger, never touches git, never calls the
network. Safe to run at any time.

USAGE
-----
    python3 ~/.claude/scripts/replay_review_rounds.py    # the ADOPTED rule
    python3 ~/.claude/scripts/replay_review_rounds.py --self-test   # no ledger needed
    python3 ~/.claude/scripts/replay_review_rounds.py --json

    # the rejected pure-subset variant, for comparison:
    python3 ~/.claude/scripts/replay_review_rounds.py \
            --reset-predicate same --trunc-fallback none

EXIT CODE IS AN ASSERTION: 0 = monotone (the rule can only remove a
false-high round), 1 = NOT monotone (it manufactures at least one), 2 =
nothing replayable. `--min-entries` is a DISPLAY filter only and can never
change the verdict or the exit code.

`--self-test` runs the predicate table from the plan's own shape analysis
and needs no ledger, so the tool's core logic is checkable on a machine
with no review history.

WHAT THE OUTPUT MEANS
---------------------
Per repo: how many entries change round, split up/down; the peak round
under each rule; and the population at or above the tripwire (>=3) and
escalation (>=4) thresholds.

An entry moving UP is the direction that matters. Because the candidate
predicate matches a strict SUBSET of what `paths_overlap` matches, a round
can only RISE when a previously-matching CLEAN entry stops matching and so
no longer closes the chain. That is a false-HIGH vector, not a correction.

KNOWN LIMIT -- TRUNCATION
-------------------------
`record_review._paths_field` stores only the first `_MAX_PATHS_IN_FIELD`
paths (12 today, but never hardcode it -- `is_truncated` keys on the stored
count vs the true one), in caller
order, UNSORTED. Entries wider than that are compared on a 12-path sample,
and two recordings of one wide boundary can store different samples. The
union rule is robust to this (any shared path still matches); a containment
rule is NOT. `--trunc-fallback` chooses how to handle it, and the
`prev=`-linked pairs are the ground truth for it: the caller DECLARED those
pairs to be one boundary, so any pair that is neither subset nor superset
is a case the candidate predicate would get wrong.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys

sys.path.insert(0, os.path.expanduser("~/.claude/hooks"))

import file_claims as fc  # noqa: E402
import record_review as rr  # noqa: E402

LEDGER = os.path.expanduser("~/.claude/.review_state/last_reviewed")
PREFIX = "precommit:"


def covers(outer, inner) -> bool:
    """True when every path in `inner` is at or under some path in `outer`.

    Empty `inner` returns False, NOT the vacuous True of `all([])`: an
    entry with no stored paths is missing data, and treating it as
    "contained in everything" would make it match every call -- a silent
    chain-merger strictly worse than the defect being fixed.
    """
    if not inner or not outer:
        return False
    return all(any(i == o or i.startswith(o + "/") for o in outer) for i in inner)


def same_boundary(call, entry) -> bool:
    """Candidate predicate: one pathspec contains the other."""
    return covers(call, entry) or covers(entry, call)


def is_truncated(e) -> bool:
    """The entry stored fewer paths than the boundary actually had.

    Keyed on the STORED count, never a hardcoded 12: `_MAX_PATHS_IN_FIELD`
    is a writer-side constant that can change, and a literal here would
    silently stop matching if it did. Only the ENTRY side can be truncated
    -- a live call carries its raw_paths in full.
    """
    return e["n_paths"] > len(e["paths"])


def half_sample_under_call(call, entry_paths) -> bool:
    """>=50% of the entry's STORED sample is at or under some call path.

    The truncation fallback (variant E). A plain `paths_overlap` fallback
    (variant D) keeps today's shape-5 overcount alive on the 17% of entries
    that are truncated -- the defect this exists to fix, preserved for one
    entry in six. This rule still separates shape 5 under truncation: a
    12-path sample sharing only `README.md` with a 2-path call is 1/12,
    far below the line.
    """
    if not entry_paths or not call:
        return False
    hit = sum(1 for i in entry_paths
              if any(i == o or i.startswith(o + "/") for o in call))
    return hit * 2 >= len(entry_paths)


def overlap(call, entry) -> bool:
    """The CURRENT predicate, as shipped -- union semantics."""
    return fc.paths_overlap(call, entry)


PREDICATES = {"subset": same_boundary, "overlap": overlap}


def _elide(repo: str, width: int = 52) -> str:
    """Shorten a repo path from the MIDDLE, never the left.

    Left-truncation renders `.../worktrees/69-reap-sweep-5260-v2` and
    `.../worktrees/69-reap-sweep-5260` near-identically, which is exactly
    backwards: the distinguishing part of a repo path is usually its tail.
    """
    if len(repo) <= width:
        return repo
    keep = width - 3
    head = keep // 3
    return repo[:head] + "..." + repo[-(keep - head):]


def load_entries(path: str = LEDGER) -> list[dict]:
    """Every replayable ledger entry: precommit-keyed, with a `paths=` field.

    The ledger holds more precommit-keyed lines than this returns -- only
    those carrying `paths=` AND a clean/blockers outcome can be replayed.
    Quote THIS number, not the raw line count.
    """
    try:
        lines = open(path, encoding="utf-8", errors="replace").read().splitlines()
    except OSError:
        return []
    out = []
    malformed_paths_n = 0
    for n, line in enumerate(lines):
        # Anchor on " precommit:" -- NOT the first space. A repo root may
        # contain spaces (the live ledger has
        # `/Users/x/Desktop/other project`), and a
        # first-space split silently DROPS every such repo: it gets no row
        # at all, so the per-repo table omits a repo production walks.
        # Production anchors the same way (`record_review.py:1344,1350`).
        # rpartition, not partition: production knows `repo_root` up front
        # and matches a prefix (`record_review.py:1344`), so a root that
        # itself contains " precommit:" parses fine there. This tool must
        # INFER the root, and splitting on the FIRST occurrence would cut
        # such a root in half and drop the row entirely. Taking the LAST
        # occurrence reproduces production for every real shape, since the
        # key that follows never contains a space.
        repo, sep, after = line.rpartition(" " + PREFIX)
        if not sep:
            continue
        rest = PREFIX + after
        key, _, token = rest.partition(" ")
        if not token:
            continue
        status, _count = rr.parse_outcome_token(token)
        if status not in (rr.OUTCOME_CLEAN, rr.OUTCOME_BLOCKERS):
            continue
        fields = rr.parse_ledger_fields(token)
        raw = fields.get("paths")
        if not raw:
            continue
        paths = frozenset(fc.normalize_path(x) for x in raw.split("#") if x)
        if not paths:
            continue
        # A malformed `paths_n=` must not abort a full-ledger run: the
        # ledger is append-only and multi-writer, and this tool's contract
        # is "safe to run at any time". Fall back to the stored count, but
        # COUNT the occurrences -- a silent fallback would hide corruption.
        raw_n = fields.get("paths_n")
        try:
            n_paths = int(raw_n) if raw_n else len(raw.split("#"))
        except (TypeError, ValueError):
            n_paths = len(raw.split("#"))
            malformed_paths_n += 1
        out.append(
            {
                "line": n + 1,
                "repo": repo,
                "key": key[len(PREFIX):],
                "status": status,
                "paths": paths,
                "fields": fields,
                # The TRUE path count, from `paths_n=` -- never recomputed
                # from `paths=`, which is already capped at
                # `_MAX_PATHS_IN_FIELD` (12). record_review.py:542 warns
                # about exactly this: a count derived from the truncated
                # field silently reports 0% truncation.
                "n_paths": n_paths,
            }
        )
    if malformed_paths_n:
        print(f"replay_review_rounds: {malformed_paths_n} entr(ies) have a "
              f"malformed `paths_n=`; fell back to the stored path count for "
              f"those, so the truncation figure UNDERSTATES.", file=sys.stderr)
    return out


def derive(pred, repo: str, wanted, prior: list[dict]) -> int:
    """Re-derive one entry's round, mirroring `derive_review_round`'s walk.

    A CLEAN predecessor on the same boundary RESETS the count (that chain
    closed); a blockers round increments it.
    """
    count = 0
    for e in prior:
        if e["repo"] != repo or not pred(wanted, e["paths"]):
            continue
        count = 0 if e["status"] == rr.OUTCOME_CLEAN else count + 1
    return count + 1


def replay(entries: list[dict], pred, reset_pred=None, trunc_fallback="none",
           *, reset_uses_candidate: bool) -> dict:
    """`reset_pred` defaults to `pred` (the consistent rule). The ADOPTED
    rule passes `overlap`, which makes the change provably monotone: a round
    can then only fall, never rise."""
    reset_pred = reset_pred or pred
    # `reset_uses_candidate` is MANDATORY and keyword-only. It must never
    # be inferred from `reset_pred is overlap`: a semantically identical
    # wrapper (a lambda, a functools.partial) is a different object, and
    # that identity check silently flipped this tool's headline from
    # "88 changed, monotone" to "184 changed, 101 up" -- the verdict
    # depended on HOW the callable was built, not on what it computes.
    # An inferred DEFAULT reproduces the same defect for the next caller,
    # so there is no default: the caller states its intent or it does not
    # call.

    def inc_match(call, e):
        if pred(call, e["paths"]):
            return True
        if trunc_fallback == "none" or not is_truncated(e):
            return False
        if trunc_fallback == "overlap":
            return overlap(call, e["paths"])
        return half_sample_under_call(call, e["paths"])

    per_repo: dict[str, dict] = collections.defaultdict(
        lambda: dict(total=0, changed=0, up=0, down=0, peak_old=0, peak_new=0,
                     ge3_old=0, ge3_new=0, ge4_old=0, ge4_new=0, changes=[])
    )
    def reset_match(call, e):
        """A CLEAN entry closes the chain.

        When the reset predicate is `overlap` (the adopted rule) the
        truncation fallback is irrelevant -- overlap already matches on any
        shared path. It applies only when the reset uses the CANDIDATE
        predicate, which is otherwise strictly harder than today's and
        would leave truncated chains un-closed.
        """
        if not reset_uses_candidate:
            return reset_pred(call, e["paths"])
        return inc_match(call, e)

    def derive_new(repo, wanted, prior):
        count = 0
        for e in prior:
            if e["repo"] != repo:
                continue
            if e["status"] == rr.OUTCOME_CLEAN:
                if reset_match(wanted, e):
                    count = 0
            elif inc_match(wanted, e):
                count += 1
        return count + 1

    for i, e in enumerate(entries):
        prior = entries[:i]
        old = derive(overlap, e["repo"], e["paths"], prior)
        new = derive_new(e["repo"], e["paths"], prior)
        r = per_repo[e["repo"]]
        r["total"] += 1
        r["peak_old"] = max(r["peak_old"], old)
        r["peak_new"] = max(r["peak_new"], new)
        for t in (3, 4):
            r[f"ge{t}_old"] += old >= t
            r[f"ge{t}_new"] += new >= t
        if old != new:
            r["changed"] += 1
            r["up" if new > old else "down"] += 1
            r["changes"].append(
                {"line": e["line"], "old": old, "new": new,
                 "paths": sorted(e["paths"])[:4], "status": e["status"]}
            )
    return per_repo


def prev_linked_relations(entries: list[dict]) -> tuple[collections.Counter, list]:
    """Ground truth: for pairs the CALLER declared one boundary via `--prev`,
    what is the actual path relation? A pair that is neither subset nor
    superset is one the candidate predicate would get WRONG."""
    by_key = {(e["repo"], e["key"]): e for e in entries}
    rel: collections.Counter = collections.Counter()
    partial = []
    for e in entries:
        prev = e["fields"].get("prev")
        if not prev or not prev.startswith(PREFIX):
            continue
        p = by_key.get((e["repo"], prev[len(PREFIX):]))
        if p is None:
            rel["dangling"] += 1
            continue
        a, b = e["paths"], p["paths"]
        if a == b:
            rel["identical"] += 1
        elif covers(b, a):
            rel["call-subset-of-prev"] += 1
        elif covers(a, b):
            rel["call-superset-of-prev"] += 1
        elif overlap(a, b):
            rel["PARTIAL (neither) -- predicate would MISS"] += 1
            partial.append({"line": e["line"], "repo": e["repo"],
                            "truncated": is_truncated(e) or is_truncated(p)})
        else:
            rel["disjoint"] += 1
    return rel, partial


def self_test() -> int:
    """The shape table, checkable without any ledger."""
    cases = [
        ("identical", {"a.py"}, {"a.py"}, True),
        ("fix narrows", {"a.py"}, {"a.py", "b.py"}, True),
        ("fix widens", {"a.py", "b.py"}, {"a.py"}, True),
        ("dir then file under it", {"m/x.py"}, {"m"}, True),
        ("two features sharing README", {"f1.py", "README.md"}, {"f2.py", "README.md"}, False),
        ("disjoint", {"a.py"}, {"b.py"}, False),
        ("prefix but not a dir boundary", {"foo.py.bak"}, {"foo.py"}, False),
        ("empty entry never matches", {"a.py"}, set(), False),
        ("empty call never matches", set(), {"a.py"}, False),
    ]
    failed = 0
    for name, call, entry, want in cases:
        got = same_boundary(frozenset(call), frozenset(entry))
        ok = got == want
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: expected {want}, got {got}")
    # The shapes NO pathspec-only rule can fix -- pinned so a future chain-id
    # fix must consciously rewrite them rather than silently inherit them.
    print("  (known-unfixable, asserted to still MERGE:)")
    for name, call, entry in [
        ("dir-scoped entry captures unrelated file", {"m/new.py"}, {"m"}),
    ]:
        got = same_boundary(frozenset(call), frozenset(entry))
        ok = got is True
        failed += not ok
        print(f"  {'PASS' if ok else 'FAIL'}  {name}: still merges (got {got})")
    print(f"\n{'ALL PASS' if not failed else f'{failed} FAILED'}")
    return 1 if failed else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--predicate", choices=sorted(PREDICATES), default="subset",
                    help="candidate predicate to compare against the shipped one")
    ap.add_argument("--reset-predicate", choices=("same", "overlap"),
                    default="overlap",
                    help="predicate a CLEAN entry uses to CLOSE a chain. "
                         "'overlap' (default, the adopted rule) keeps today's "
                         "reset semantics and makes the change monotone; "
                         "'same' applies the candidate to both and can raise "
                         "rounds.")
    ap.add_argument("--trunc-fallback", choices=("none", "overlap", "half-sample"),
                    default="half-sample",
                    help="how to match an entry whose stored paths were "
                         "truncated. 'half-sample' (default) is variant E.")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true",
                    help="run the shape table; needs no ledger")
    ap.add_argument("--min-entries", type=int, default=1,
                    help="hide repos with fewer entries than this (default 1)")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    entries = load_entries(args.ledger)
    if not entries:
        print(f"replay_review_rounds: no replayable entries in {args.ledger} -- "
              "either the ledger is absent/empty, or no entry carries a `paths=` "
              "field. This is NOT a result about the predicate.", file=sys.stderr)
        return 2

    reset_pred = same_boundary if args.reset_predicate == "same" else overlap
    per_repo = replay(entries, PREDICATES[args.predicate],
                      reset_pred=reset_pred, trunc_fallback=args.trunc_fallback,
                      reset_uses_candidate=(args.reset_predicate == "same"))
    rel, partial = prev_linked_relations(entries)
    trunc = sum(1 for e in entries if is_truncated(e))

    if args.json:
        # The JSON path carries the SAME verdict and the SAME exit code as
        # the text path -- it is the one a caller actually gates on, and it
        # previously returned 0 unconditionally, so the monotone assertion
        # protected only the human-readable output. It also records the
        # FULL variant (reset + fallback, not just the predicate): a saved
        # artifact that cannot be tied to the config that produced it is
        # the exact attribution failure that started #5828.
        j_up = sum(r["up"] for r in per_repo.values())
        print(json.dumps(
            {"replayable_entries": len(entries), "predicate": args.predicate,
             "reset_predicate": args.reset_predicate,
             "trunc_fallback": args.trunc_fallback,
             "monotone": j_up == 0, "up_moves": j_up,
             "truncated_entries": trunc,
             "prev_linked_relations": dict(rel),
             "partial_pairs": partial,
             "per_repo": {k: v for k, v in per_repo.items()}},
            indent=2, default=list))
        return 1 if j_up else 0

    print(f"replayable entries: {len(entries)}  "
          f"(candidate predicate: {args.predicate})")
    print(f"truncated entries (stored < true path count): {trunc} "
          f"({100.0*trunc/max(len(entries),1):.1f}%)\n")
    # The verdict and exit code come from the FULL result set, NEVER from
    # the display-filtered subset. `--min-entries` is cosmetic; letting it
    # feed the monotone assertion meant a display flag could turn a failing
    # assertion GREEN (measured: --min-entries 1800 printed "up == 0 in
    # every repo" and exited 0 for a rule that manufactures 112).
    full = collections.Counter()
    for r in per_repo.values():
        for k in ("total", "changed", "up", "down"):
            full[k] += r[k]
    hidden = sum(1 for r in per_repo.values() if r["total"] < args.min_entries)

    tot = collections.Counter()
    hdr = f"{'repo':<52} {'n':>5} {'chg':>5} {'up':>4} {'down':>5} {'peak':>9} {'>=3':>9} {'>=4':>9}"
    print(hdr)
    print("-" * len(hdr))
    for repo, r in sorted(per_repo.items(), key=lambda kv: -kv[1]["total"]):
        if r["total"] < args.min_entries:
            continue
        for k in ("total", "changed", "up", "down"):
            tot[k] += r[k]
        print(f"{_elide(repo):<52} {r['total']:>5} {r['changed']:>5} {r['up']:>4} "
              f"{r['down']:>5} {r['peak_old']:>4}->{r['peak_new']:<4} "
              f"{r['ge3_old']:>4}->{r['ge3_new']:<4} {r['ge4_old']:>4}->{r['ge4_new']:<4}")
    print("-" * len(hdr))
    label = "ALL (shown rows)" if hidden else "ALL"
    print(f"{label:<52} {tot['total']:>5} {tot['changed']:>5} {tot['up']:>4} {tot['down']:>5}")

    print("\nprev=-linked pairs (the caller DECLARED these one boundary):")
    for k, v in rel.most_common():
        print(f"  {v:>5}  {k}")
    if partial:
        n_tr = sum(1 for p in partial if p["truncated"])
        print(f"\n  of {len(partial)} partial pairs, {n_tr} have a side whose "
              f"stored sample was truncated\n  -- i.e. truncation, not a genuine "
              f"re-scope, is the likely cause")
    if hidden:
        print(f"\n({hidden} repo(s) hidden by --min-entries {args.min_entries}; "
              f"the verdict below covers ALL {full['total']} entries.)")
    if full["up"]:
        print(f"\n*** NOT MONOTONE: {full['up']} entries derive a HIGHER round. "
              f"This rule CAN manufacture a false-high round. ***")
    else:
        print("\nMONOTONE: up == 0 in every repo -- this rule can only REMOVE "
              "a\nfalse-high round, never manufacture one.")
    print(f"\nUP moves are the RISK direction -- a round rises when a CLEAN "
          f"entry stops\nclosing the chain, manufacturing a false-high round. "
          f"Inspect all {full['up']}.\nDOWN moves ({full['down']}) are the "
          f"intended correction: independent chains\nthat shared a path are no "
          f"longer merged.")
    # Exit 1 when the rule is NOT monotone, so "up == 0" is an assertion a
    # caller can check rather than a line a reader must notice.
    return 1 if full["up"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
