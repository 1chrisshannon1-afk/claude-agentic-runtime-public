#!/usr/bin/env python3
"""claude_md_rule_net — the WS3 regression net for the CLAUDE.md refactor.

WHAT IT IS FOR. The master plan (§4 / WS3, "3.4 Regression net") requires
that before any CLAUDE.md trim, an independent pass enumerates every rule
from the PRE-TRIM file at a pinned sha, and that a later pass diffs the
POST-TRIM file against that artifact. This module is that diff.

The artifact is ``knowledge/claude_md_rule_inventory_<sha>.md``: a table of
``R-<section>-<nn>`` rows, each carrying the rule in one line, its
condition, and a VERBATIM-CRITICAL flag for the §3.2 load-bearing set.

WHAT IT CHECKS

  * ``rule-missing``      -- a rule in the inventory whose distinctive
                             anchor no longer appears anywhere in the file.
                             The trim is allowed to RELOCATE prose (the
                             plan's own method is "relocate, never delete"),
                             so an anchor found in a named relocation target
                             counts as present.
  * ``verbatim-changed``  -- a VERBATIM-CRITICAL rule whose anchor text is
                             no longer byte-identical. §3.2 names these as
                             load-bearing and read mechanically; a
                             paraphrase there is a behaviour change.
  * ``section-renumbered``-- a ``## <n>.`` heading that moved or vanished.
                             ~234 inbound ``CLAUDE.md §N`` citations depend
                             on the numbering, which §3.1 says must not
                             change.

WHAT IT CANNOT CHECK, stated rather than implied.

COVERAGE -- the larger hole, and the one a reader will otherwise miss. Only
a rule carrying a literal backticked token can be anchored. Against the
970dfdd inventory that is 163 of 260 rules: **97 rules (37%) are SKIPPED
ENTIRELY**, including a large share of the VERBATIM-CRITICAL set. For a
skipped rule an outright DELETION produces no finding at all.

A clean run therefore means "no ANCHORED rule went missing". It NEVER means
"no rule was lost." Three deletions proven undetectable against the real
files: `Prior approval never carries over` (R-04-05); `Two Opus review
points, and only two` (R-10-01); and inverting non-negotiable #3 to "Tests
may assert current behavior; docs can follow later" (R-00-04) -- all three
VERBATIM-CRITICAL, all three silent. **Always cite the coverage ratio with
any verdict from this tool**; `main()` prints it for exactly that reason.

It also compares ANCHORS, not meaning: a rule whose wording is rewritten so
thoroughly that its anchor survives while its CONDITION is dropped will pass
here. That is why the plan pairs this net with a `consistency-auditor` read
and why §3.3 rule 1 ("a rule's CONDITION travels with it") is a human
obligation, not a mechanical one.

POSITIVE CONTROL. A net never seen failing proves nothing. ``--self-test``
deletes one known rule from an in-memory copy and asserts this module flags
it; it is run by the test suite and can be run by hand before trusting any
green verdict.

Usage:
    python3 ~/.claude/hooks/claude_md_rule_net.py                  # report
    python3 ~/.claude/hooks/claude_md_rule_net.py --strict         # exit 1 on findings
    python3 ~/.claude/hooks/claude_md_rule_net.py --self-test      # positive control
    python3 ~/.claude/hooks/claude_md_rule_net.py --file <path> --inventory <path>

Tracked on #5829 (WS3).
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

# Where relocated narrative is allowed to live. The plan's method is
# "relocate, never delete", so an anchor found in one of these is PRESENT,
# not missing.
#
# DECLARED, NOT INFERRED -- and that distinction is the whole point. This was
# three globs, two of them recursive (`knowledge/*.md`, `knowledge/**/*.md`,
# `docs/subsystems/*.md`), which inherited 143 files as potential masking
# surface when only four are real relocation targets. Any rule whose anchor
# happened to be quoted ANYWHERE in that tree was silently marked
# "relocated" rather than "missing" -- and distinctive phrases are quoted all
# over the documentation, which is why requiring corpus-absence once found no
# self-test victim at all.
#
# With an explicit list, each trim widens the masking surface by exactly the
# file it names, VISIBLY, in a diff. Adding a target is a deliberate line in
# a reviewed change rather than a side effect of creating a file.
#
# To add one: append it here IN THE SAME COMMIT as the trim that relocates
# into it, and say so in the commit message.
_RELOCATION_FILES = (
    "knowledge/sanctioned_opus_roster_history.md",
    "knowledge/worktree_integration_flow.md",
    "knowledge/review_gate_incident_history.md",
    "knowledge/model_default_regression_history.md",
    "knowledge/worktree_and_disk_incident_history.md",
)

# `[0-9a-z]+` did NOT match the inventory's 26 `R-PRE-*` rows (the preamble
# section, whose key is uppercase), so they were silently dropped before any
# anchoring even ran -- a blind spot inside the blind spot, found only by
# reconciling a reported 260 against a parsed 234. Uppercase is now accepted.
_ROW = re.compile(
    r"^\|\s*(?P<id>R-[0-9A-Za-z]+-\d+)\s*\|"   # R-10-04, R-PRE-07
    r"(?P<rest>.*)$"
)
_HEADING = re.compile(r"(?m)^##\s+(?P<num>\d+)\.\s")


def _anchor_of(rule_text: str) -> str | None:
    """The most distinctive fragment of a rule row that can be searched for
    in CLAUDE.md itself.

    CRITICAL, and the reason an earlier cut of this function produced 74
    false findings against an UNMODIFIED file: an inventory row states the
    rule in the CATALOGUER'S OWN WORDS, not verbatim from the contract. So a
    window of the row's prose is not an anchor -- it never appeared in
    CLAUDE.md in the first place, and "missing" would mean nothing.

    What DOES survive paraphrase is a literal token the cataloguer had to
    copy exactly because it names a real thing: an inline `code span` (a
    flag, a path, a constant, a command). Those are quoted from the contract
    by necessity. A row with no such token yields no anchor and is skipped,
    which is honest -- a rule the net cannot anchor is a rule the net cannot
    check, and pretending otherwise is how a net becomes theatre.
    """
    if not rule_text:
        return None
    code = [c for c in re.findall(r"`([^`]{4,80})`", rule_text) if not c.startswith("R-")]
    if not code:
        return None
    # Longest is the most distinctive; a 4-char minimum keeps out `§3`-style
    # fragments that would match hundreds of places.
    best = max(code, key=len)
    return best if len(best) >= 6 else None


def inventory_coverage(path: str) -> tuple[int, int]:
    """(anchorable, total) rule rows. The gap between them is the blind
    spot -- rules this net cannot check at all. Never raises."""
    try:
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return (0, 0)
    total = sum(1 for line in text.splitlines() if _ROW.match(line.strip()))
    return (len(parse_inventory(path)), total)


def parse_inventory(path: str) -> list[dict]:
    """Every rule row. Never raises on a malformed row -- it skips it and
    says so, because a parser that dies on one bad line would take the whole
    net down at exactly the moment it is needed."""
    rows: list[dict] = []
    try:
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return rows
    for line in text.splitlines():
        m = _ROW.match(line.strip())
        if not m:
            continue
        cells = [c.strip() for c in m.group("rest").split("|")]
        rule = cells[1] if len(cells) > 1 else (cells[0] if cells else "")
        verbatim = any(c.strip().upper().startswith("YES") for c in cells[-2:])
        anchor = _anchor_of(rule)
        if not anchor:
            continue
        rows.append(
            {
                "id": m.group("id"),
                "rule": rule,
                "anchor": anchor,
                "verbatim": verbatim,
            }
        )
    return rows


def _relocation_corpus(root: str, exclude: str | None = None) -> str:
    """Concatenated text of every file the trim may relocate prose INTO.

    EXCLUDES the inventory artifact itself. It lives in `knowledge/` and by
    construction quotes every rule it catalogues, so counting it as a
    relocation target would make EVERY deletion look like a relocation --
    the net would report nothing while appearing to work. Found by a test
    written to prove the corpus was root-scoped, which instead proved this.
    """
    out: list[str] = []
    excl = os.path.abspath(exclude) if exclude else None
    for rel in _RELOCATION_FILES:
        p = os.path.join(root, rel)
        if excl and os.path.abspath(p) == excl:
            continue
        if "claude_md_rule_inventory_" in os.path.basename(p):
            continue
        try:
            out.append(open(p, "r", encoding="utf-8", errors="replace").read())
        except OSError:
            continue  # a declared target that does not exist yet is not an error
    return "\n".join(out)


def check(
    claude_md_path: str,
    inventory_path: str,
    root: str,
    head_text: str | None = None,
) -> list[dict]:
    """Findings comparing the CURRENT CLAUDE.md against the inventory."""
    findings: list[dict] = []
    rows = parse_inventory(inventory_path)
    if not rows:
        return [
            {
                "rule": "inventory-unreadable",
                "id": "-",
                "detail": f"no rule rows parsed from {inventory_path}",
            }
        ]
    try:
        current = open(claude_md_path, "r", encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return [{"rule": "file-unreadable", "id": "-", "detail": str(exc)}]

    relocated = _relocation_corpus(root, exclude=inventory_path)

    for r in rows:
        anchor = r["anchor"]
        in_file = anchor in current
        in_reloc = (not in_file) and (anchor in relocated)
        if not in_file and not in_reloc:
            findings.append(
                {
                    "rule": "rule-missing",
                    "id": r["id"],
                    "detail": f"anchor not found in CLAUDE.md nor any relocation target: {anchor!r}",
                }
            )
            continue
        if r["verbatim"] and not in_file:
            # A load-bearing rule may not be relocated out of the contract:
            # §3.2 names these as read mechanically, in place.
            findings.append(
                {
                    "rule": "verbatim-changed",
                    "id": r["id"],
                    "detail": f"VERBATIM-CRITICAL rule left CLAUDE.md (found only in a relocation target): {anchor!r}",
                }
            )

    # Section numbering: ~234 inbound citations depend on it (§3.1).
    if head_text is not None:
        before = _HEADING.findall(head_text)
        after = _HEADING.findall(current)
        if before != after:
            findings.append(
                {
                    "rule": "section-renumbered",
                    "id": "-",
                    "detail": f"## headings changed: {before} -> {after}",
                }
            )
    return findings


def self_test(claude_md_path: str, inventory_path: str, root: str) -> tuple[bool, str]:
    """POSITIVE CONTROL: delete one known rule and confirm we flag it.

    Returns (passed, message). A net that has never been seen failing is not
    evidence of anything."""
    rows = parse_inventory(inventory_path)
    if not rows:
        return (False, "inventory produced no rows — cannot self-test")
    try:
        text = open(claude_md_path, "r", encoding="utf-8", errors="replace").read()
    except OSError as exc:
        return (False, f"cannot read {claude_md_path}: {exc}")

    # Choose a row whose anchor is genuinely present in CLAUDE.md, so the
    # deletion is unambiguous. An earlier cut ALSO required the anchor to be
    # absent from the whole relocation corpus and found NO victim at all --
    # the corpus was then every knowledge/ and docs/subsystems/ file
    # (~3.8MB), and any phrase distinctive enough to be an anchor is quoted
    # somewhere in it. Requiring global uniqueness made the control
    # unrunnable, which is the failure mode it exists to prevent.
    #
    # Narrowing the corpus to the four DECLARED targets (~39KB) revives that
    # option -- 60 rows now satisfy the strict rule (measured). It is kept
    # as-is regardless, for a reason the old comment could not give: the
    # both-copies mutation does not depend on the corpus AT ALL, so it
    # cannot be re-broken by a future trim widening the declared list. The
    # strict rule would be silently weakened by exactly the growth this
    # refactor makes routine.
    #
    # The control instead deletes the anchor from BOTH copies for the
    # duration of the check, so "did the net notice a rule vanish" is asked
    # cleanly without depending on where else the phrase appears.
    # Prefer the most DISTINCTIVE victim: fewest occurrences first, then
    # longest anchor. Taking the first match picked `~/.claude/` (70
    # occurrences in CLAUDE.md) -- the control still passed, since the
    # mutation replaces every copy, but a victim that generic exercises a
    # weaker path than a rule-specific token does, so the control tested
    # less than it appeared to.
    victim = None
    candidates = [r for r in rows if text.count(r["anchor"]) >= 1]
    if candidates:
        victim = min(candidates, key=lambda r: (text.count(r["anchor"]), -len(r["anchor"])))
    if victim is None:
        return (False, "no anchored rule present in the file to mutate")

    mutated = text.replace(victim["anchor"], "__DELETED_BY_SELF_TEST__")
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(mutated)
        tmp = fh.name
    # An EMPTY relocation root, so the control asks only "did the net notice
    # this rule leave CLAUDE.md" without the corpus answering for it.
    empty_root = tempfile.mkdtemp()
    try:
        findings = check(tmp, inventory_path, empty_root)
    finally:
        os.unlink(tmp)
        os.rmdir(empty_root)

    hit = [f for f in findings if f["id"] == victim["id"] and f["rule"] == "rule-missing"]
    if hit:
        return (True, f"positive control PASSED: deleting {victim['id']} was flagged")
    return (
        False,
        f"positive control FAILED: deleted {victim['id']} ({victim['anchor']!r}) and the net did NOT flag it",
    )


def main(argv: list[str] | None = None) -> int:
    root_default = os.path.expanduser("~/.claude")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--root", default=root_default)
    ap.add_argument("--file", default=None, help="the CLAUDE.md to check (default: <root>/CLAUDE.md)")
    ap.add_argument("--inventory", default=None, help="default: newest knowledge/claude_md_rule_inventory_*.md")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--self-test", action="store_true", help="run the positive control and exit")
    args = ap.parse_args(argv)

    claude_md = args.file or os.path.join(args.root, "CLAUDE.md")
    inventory = args.inventory
    if not inventory:
        cands = sorted(glob.glob(os.path.join(args.root, "knowledge", "claude_md_rule_inventory_*.md")))
        if not cands:
            print("claude_md_rule_net: no inventory artifact found — run the WS3 inventory step first", file=sys.stderr)
            return 0
        inventory = cands[-1]

    if args.self_test:
        ok, msg = self_test(claude_md, inventory, args.root)
        print(msg)
        return 0 if ok else 1

    try:
        findings = check(claude_md, inventory, args.root)
    except Exception as exc:  # a net must never take down its caller
        print(f"claude_md_rule_net: skipped ({exc.__class__.__name__}: {exc})", file=sys.stderr)
        return 0

    if args.json:
        print(json.dumps(findings, indent=2))
    else:
        for f in findings:
            print(f"{f['rule']}\t{f['id']}\t{f['detail']}")
        anchored, total = inventory_coverage(inventory)
        unchecked = total - anchored
        print(
            f"claude_md_rule_net: {len(findings)} finding(s) against "
            f"{os.path.basename(inventory)} — {anchored}/{total} rules anchored, "
            f"{unchecked} UNANCHORABLE and NOT checked "
            f"(a clean run means no ANCHORED TOKEN went missing — not that no rule was "
            f"lost, and not that an anchored rule's MEANING survived; the median anchor "
            f"covers ~8% of its rule's text)"
        )
    return 1 if (args.strict and findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
