#!/usr/bin/env python3
"""protected_board_guard — PreToolUse gate for adding items to a PROTECTED
GitHub Projects (v2) board.

Operator directive (verbatim, 2026-09-14): "make sure that only tickets from
the saas ticketing center go here. when a user files a ticket it goes here.
none of our agents should create issues here." The referenced board — GitHub
org project #5, "Example Support Tickets"
(`https://github.com/orgs/example-org/projects/5/views/1`, node id
`PVT_kwDOEXAMPLE00000`) — is a CUSTOMER-ONLY inbox: the product's own
support-ticket mirror is its sole legitimate writer. No agent, of any kind,
in any repo, may add an item to it. This hook makes that MECHANICAL rather
than a norm an agent might forget.

PRODUCT-AGNOSTIC BY DESIGN: this module hardcodes no product's board id. The
set of protected boards lives in a registry,
``~/.claude/knowledge/protected_boards.json`` (see :func:`load_registry`):

    {"boards": [{"owner": "...", "number": N, "node_id": "PVT_...",
                 "title": "...", "reason": "...", "tracker": "..."}]}

Any repo/product can add its own protected board by adding an entry — the
runtime code never changes to name a specific board.

DENIES a Bash segment that would ADD an item to a protected board:
  (a) ``gh project item-add|item-create <number> --owner <owner> ...`` where
      `<number>` matches a protected board's ``number`` AND `--owner` (when
      present) matches that board's ``owner`` (case-insensitive) — an ABSENT
      `--owner` also matches, since `gh project item-add` defaults to the
      authenticated user/current repo's org, and the protected board's own
      owner is exactly the org this runtime's product repos authenticate
      against; a caller cannot use omission to dodge the gate.
  (b) ``gh api graphql`` (or ``gh api -X POST .../graphql``) whose text
      contains an ``addProjectV2ItemById`` or ``addProjectV2DraftIssue``
      mutation TOGETHER WITH a protected board's ``node_id`` — including the
      node id appearing only as an ``-F``/``-f`` variable value in the same
      segment (a raw text scan, not a JSON/GraphQL parse, so a variable
      substitution can't dodge it).
  (c) ``gh issue create`` / ``gh issue edit`` / ``gh pr create`` / ``gh pr
      edit`` carrying ``--project``/``--add-project``/the short ``-p`` form
      (``gh issue create``'s own ``-p, --project title``) whose value — or
      ANY one comma-separated element of it, since ``gh``'s own
      ``--add-project`` accepts a comma-separated list and the flag may also
      be repeated — equals a protected board's ``title`` (case-insensitive,
      surrounding quotes stripped) or ``number``.
  (d) a ``gh_issue.sh`` invocation (this runtime's own issue-lifecycle
      helper, ``~/.claude/scripts/gh_issue.sh``) carrying ``--project
      <number>`` matching a protected board, with a matching or absent
      ``--owner``.

KNOWN LIMITS (deliberately out of scope for this gate — closed by
``agents/board-steward.md``'s prose rule and the operator directive, not by
mechanical inspection here): this gate covers the ergonomic ``gh`` /
``gh_issue.sh`` paths an agent actually reaches for. It does NOT inspect a
file-based GraphQL body (``gh api graphql -f query=@file.graphql``, or
``gh api --input body.json``), a raw HTTP client (``curl``/``python -c ...``
hitting ``api.github.com`` directly), ``xargs``-indirected argv construction,
or a ``gh alias`` that wraps one of these shapes under a new name — all of
that is the same "arbitrary HTTP client" class no Bash-argv gate can fully
close. Separately: the board's own LEGITIMATE writer — this product's
support-ticket mirror — runs inside the deployed backend service using its
own service credentials, never through an agent's Bash tool call, so it is
never subject to (and never needs to be exempted from) this gate at all.

ALLOWS everything else, in particular:
  * reads — ``gh project view|item-list|field-list <number>``, a GraphQL
    QUERY that merely mentions the node id with no add mutation present;
  * ``item-edit`` / ``updateProjectV2ItemFieldValue`` on the protected board
    (triaging an EXISTING customer ticket — moving its status, setting a
    field — is legitimate steward work, only ADDING a new item is not);
  * ``item-delete``;
  * any operation on a DIFFERENT project (a different number, or the SAME
    number under an explicitly different owner).

Tokenizes with ``shlex`` (via ``_lib._split_segments`` for compound-command
splitting, exactly like every sibling gate). On an UNTOKENIZABLE segment that
carries both a `gh` mention and a protected-board add shape (a protected
node id, or `gh` + `project` + `item-add`/`item-create`/`--add-project`
tokens all present in the raw segment text), this fails CLOSED — matching
gate 1's own posture for an ambiguous git segment: an unparseable wrapper
around a dangerous shape is a bypass vector, not an innocuous parse quirk.
Every other untokenizable segment is allowed (nothing to act on).

CONTRACT (matching every other gate in this chain):
  * PURE decision function ``decide(command) -> (block: bool, reason: str)``.
    No I/O beyond loading the (static, on-disk) registry file.
  * Thin ``main()``: read event, decide, log always on a would-block, emit
    the canonical deny only when ``enforcing()``. Always exits 0 — a deny is
    the JSON object, never an exit code.
  * ``CSA_DISABLE_HOOKS=1`` master-OFF: no-op allow before anything else.
  * Only the Bash tool is gated; every other tool is allowed.
  * A missing or unparseable registry file degrades to ALLOW (fail open,
    logged) — a registry outage must never wedge every `gh project` command
    on the machine; it never crashes.

This module owns exactly two files:
  ~/.claude/hooks/protected_board_guard.py           (this file)
  ~/.claude/hooks/tests/test_protected_board_guard.py
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, mirroring the other hooks)

HOOK_NAME = "protected_board_guard"

DEFAULT_REGISTRY_PATH_SUFFIX = ("knowledge", "protected_boards.json")


def registry_path() -> str:
    """Where the protected-boards registry lives, relative to `_lib.CLAUDE_DIR`
    (not a module-level constant) so the sandbox test fixture's
    `monkeypatch.setattr(_lib, "CLAUDE_DIR", ...)` is honored automatically —
    matching `delivery_report.py`/`model_pin_parity.py`'s own pattern for
    `repo_registry.json`. Never raises."""
    try:
        return os.path.join(_lib.CLAUDE_DIR, *DEFAULT_REGISTRY_PATH_SUFFIX)
    except Exception:
        return os.path.join(os.path.expanduser("~"), ".claude", *DEFAULT_REGISTRY_PATH_SUFFIX)


def load_registry(path: str | None = None) -> list[dict]:
    """Load the list of protected-board dicts from the registry file.

    Returns ``[]`` on ANY problem (missing file, unparseable JSON, wrong
    shape) — fail OPEN, matching this module's own "a registry outage must
    never wedge every gh project command" contract. Never raises.
    """
    try:
        p = path if path is not None else registry_path()
        with open(p, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        boards = data.get("boards") if isinstance(data, dict) else None
        if not isinstance(boards, list):
            return []
        out = []
        for b in boards:
            if isinstance(b, dict) and "number" in b and "owner" in b:
                out.append(b)
        return out
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Matching helpers (pure, given an already-loaded registry list).
# ---------------------------------------------------------------------------


def _norm(s) -> str:
    """Lowercase, quote-and-whitespace-stripped normalization for a
    title/owner comparison. Never raises. ``None`` normalizes to ``""``
    explicitly (rather than falling through to ``str(None) == "none"``,
    which would wrongly match a board literally titled/owned "None")."""
    if s is None:
        return ""
    try:
        return str(s).strip().strip("'\"").strip().lower()
    except Exception:
        return ""


def find_board_by_number_owner(boards: list[dict], number: str, owner: str | None) -> dict | None:
    """Find a protected board matching `number` (string or int) and `owner`.

    `owner` of ``None`` (the flag was absent from the command) MATCHES any
    board with that number — see module docstring: an absent `--owner` must
    never be read as "this can't be the protected board", since
    `gh project item-add` without `--owner` defaults to the org/user context
    gh is already authenticated against, which for this runtime's product
    repos IS the protected board's own owner. An EXPLICIT owner must match
    case-insensitively; an explicit, DIFFERENT owner never matches (that is
    the sanctioned "same number, different owner" allow case).
    """
    try:
        num_str = str(number).strip()
    except Exception:
        return None
    if not num_str:
        return None
    for b in boards:
        try:
            if str(b.get("number")).strip() != num_str:
                continue
            if owner is None:
                return b
            if _norm(owner) == _norm(b.get("owner")):
                return b
        except Exception:
            continue
    return None


def find_board_by_title_or_number(boards: list[dict], value: str) -> dict | None:
    """Find a protected board whose `title` (case-insensitive, quotes
    stripped) or `number` equals `value` — used for `--project`/
    `--add-project` flags on gh issue/pr commands, which take either form."""
    norm_value = _norm(value)
    if not norm_value:
        return None
    for b in boards:
        try:
            if _norm(b.get("title")) == norm_value:
                return b
            if str(b.get("number")).strip() == str(value).strip():
                return b
        except Exception:
            continue
    return None


def find_board_by_node_id(boards: list[dict], text: str) -> dict | None:
    """Find a protected board whose `node_id` appears anywhere in `text` (a
    raw substring scan — deliberately not a JSON/GraphQL parse, so a
    node id smuggled in as an `-F`/`-f` variable VALUE in the same segment
    still matches, per the module docstring's (b) shape)."""
    if not text:
        return None
    for b in boards:
        node_id = b.get("node_id")
        if node_id and str(node_id) in text:
            return b
    return None


# ---------------------------------------------------------------------------
# Command classification (pure, tokenized argv per segment).
# ---------------------------------------------------------------------------

_ADD_MUTATION_RE = re.compile(r"\baddProjectV2(?:ItemById|DraftIssue)\b")

# Whole-word "gh" mention, for the untokenizable-segment fail-closed check —
# mirrors block_gcloud_identity._mentions_gcloud's exact contract for a
# different literal token.
_GH_WORD_RE = re.compile(r"(^|[^A-Za-z])gh([^A-Za-z]|$)")


def _mentions_gh(text: str) -> bool:
    try:
        return bool(_GH_WORD_RE.search(text))
    except Exception:
        return False


def _is_gh(argv: list[str]) -> bool:
    """True if argv's program is the `gh` CLI (basename match, mirroring
    gh_issue_close_gate._is_gh)."""
    if not argv:
        return False
    try:
        return argv[0].rsplit("/", 1)[-1] == "gh"
    except Exception:
        return False


def _is_gh_issue_sh(argv: list[str]) -> bool:
    """True if argv's program is this runtime's own gh_issue.sh helper
    (basename match, any path prefix)."""
    if not argv:
        return False
    try:
        return argv[0].rsplit("/", 1)[-1] == "gh_issue.sh"
    except Exception:
        return False


# gh's own global flags that can appear BEFORE the subcommand/verb tokens
# (`gh -R owner/repo project item-add ...`, `gh --hostname ghe.example.com ...`)
# -- skipped by token scan so shape (a)/(c)/(d) never assume the verb sits at
# a fixed argv position. Each maps to whether it takes a separate value token
# (True) or is a bare boolean flag (False). Short forms included where gh
# documents one (`-R` for `--repo`).
_GH_GLOBAL_FLAGS_WITH_VALUE = {
    "--repo": True,
    "-R": True,
    "--hostname": True,
}


def _skip_gh_globals(argv: list[str]) -> list[str]:
    """Drop `gh`'s own leading global flags (and their values) from argv,
    returning the remaining tokens starting at the real subcommand/verb.
    Assumes argv[0] is `gh` (or a `gh`-basename path) and is included
    unchanged as the first element of the result. Never raises."""
    try:
        if not argv:
            return argv
        out = [argv[0]]
        i = 1
        n = len(argv)
        while i < n:
            tok = argv[i]
            takes_value = _GH_GLOBAL_FLAGS_WITH_VALUE.get(tok)
            if takes_value is None:
                for name, eq_val in (
                    ("--repo=", True),
                    ("--hostname=", True),
                ):
                    if tok.startswith(name):
                        takes_value = "inline"
                        break
            if takes_value is True:
                i += 2
                continue
            if takes_value == "inline":
                i += 1
                continue
            break
        out.extend(argv[i:])
        return out
    except Exception:
        return argv


def _flag_values(argv: list[str], names: tuple[str, ...], short: tuple[str, ...] = ()) -> list[str]:
    """EVERY value of a `--name value`, `--name=value`, or short `-x value` /
    `-x=value` flag in argv whose long name is in `names` or whose short form
    is in `short` (gh's own short-flag convention, e.g. `-p` for `--project`
    on `gh issue create`). Returns them in argv order; empty list if absent.
    Collecting ALL occurrences (not just the first) matters because gh
    accepts a flag repeated (`--project A --project B`) as well as a single
    comma-separated value (`--add-project "A,B"`) — see `_shape_c_block`,
    which further splits each returned value on commas. Never raises."""
    out: list[str] = []
    try:
        n = len(argv)
        i = 0
        while i < n:
            tok = argv[i]
            matched_value = None
            for name in names:
                long_flag = "--" + name
                if tok == long_flag and i + 1 < n:
                    matched_value = argv[i + 1]
                    i += 1
                    break
                prefix = long_flag + "="
                if tok.startswith(prefix):
                    matched_value = tok[len(prefix) :]
                    break
            if matched_value is None:
                for s in short:
                    if tok == s and i + 1 < n:
                        matched_value = argv[i + 1]
                        i += 1
                        break
                    prefix = s + "="
                    if tok.startswith(prefix):
                        matched_value = tok[len(prefix) :]
                        break
            if matched_value is not None:
                out.append(matched_value)
            i += 1
        return out
    except Exception:
        return out


def _flag_value(argv: list[str], names: tuple[str, ...], short: tuple[str, ...] = ()) -> str | None:
    """The FIRST value among :func:`_flag_values` for `names`/`short`, or
    None if absent. Kept for callers (shape a/d) that only ever need a single
    flag occurrence (gh's own `--owner` is not documented as repeatable).
    Never raises."""
    values = _flag_values(argv, names, short)
    return values[0] if values else None


def _shape_a_block(argv: list[str], boards: list[dict]) -> tuple[bool, str]:
    """(a) `gh project item-add|item-create <number> [--owner O] ...`.

    Token-scanned (via :func:`_skip_gh_globals`) rather than fixed-position,
    so a leading gh global flag (`gh -R owner/repo project item-add ...`)
    doesn't shift `project`/`item-add` out of the positions this used to
    assume.
    """
    argv = _skip_gh_globals(argv)
    if len(argv) < 4:
        return (False, "")
    if argv[1] != "project" or argv[2] not in ("item-add", "item-create"):
        return (False, "")
    number = argv[3]
    if number.startswith("-"):
        return (False, "")
    owner = _flag_value(argv, ("owner",))
    board = find_board_by_number_owner(boards, number, owner)
    if board is None:
        return (False, "")
    return (True, f"protected-board-item-add:{board.get('title')}")


def _shape_b_block(seg_text: str, boards: list[dict]) -> tuple[bool, str]:
    """(b) `gh api graphql ...` (or `gh api -X POST .../graphql ...`) with an
    add-item/draft-issue mutation AND a protected node_id, anywhere in the
    segment's raw text (so an `-F`/`-f` variable value counts too)."""
    if not _ADD_MUTATION_RE.search(seg_text):
        return (False, "")
    board = find_board_by_node_id(boards, seg_text)
    if board is None:
        return (False, "")
    return (True, f"protected-board-graphql-add:{board.get('title')}")


_SHAPE_C_VERB_PAIRS = (
    ("issue", "create"),
    ("issue", "edit"),
    ("pr", "create"),
    ("pr", "edit"),
)


def _shape_c_block(argv: list[str], boards: list[dict]) -> tuple[bool, str]:
    """(c) `gh issue create|edit` / `gh pr create|edit` with
    `--project`/`--add-project`/short `-p` naming a protected board's title
    or number.

    Collects EVERY occurrence of the flag (gh accepts it repeated) and splits
    each value on `,` (gh's own `--add-project` accepts a comma-separated
    list) before testing each element against the registry — a caller
    cannot dodge the gate by hiding the protected title/number as one element
    of a multi-value list or a second repeated flag.
    """
    argv = _skip_gh_globals(argv)
    if len(argv) < 3:
        return (False, "")
    verb_pair = (argv[1], argv[2])
    if verb_pair not in _SHAPE_C_VERB_PAIRS:
        return (False, "")
    values = _flag_values(argv, ("project", "add-project"), short=("-p",))
    for raw_value in values:
        for element in raw_value.split(","):
            element = element.strip()
            if not element:
                continue
            board = find_board_by_title_or_number(boards, element)
            if board is not None:
                return (True, f"protected-board-project-flag:{board.get('title')}")
    return (False, "")


def _shape_d_block(argv: list[str], boards: list[dict]) -> tuple[bool, str]:
    """(d) a `gh_issue.sh` invocation carrying `--project <number>` matching
    a protected board, with matching/absent `--owner`."""
    number = _flag_value(argv, ("project",))
    if number is None:
        return (False, "")
    owner = _flag_value(argv, ("owner",))
    board = find_board_by_number_owner(boards, number, owner)
    if board is None:
        return (False, "")
    return (True, f"protected-board-gh-issue-sh:{board.get('title')}")


# Leading bare words that merely re-invoke a program (not a gh global flag,
# not an ENV=val assignment) and must be dropped before `_is_gh`/
# `_is_gh_issue_sh` inspect argv[0] — `env gh ...`, `command gh ...`. Only
# ONE such leading word is dropped (mirroring `_lib._strip_prefix`'s own
# single-pass-until-first-non-match contract); `env FOO=x gh ...` is handled
# by `_lib._strip_prefix` running first and stripping the ENV assignment,
# then this stripping `env` itself on the next pass in `decide()`.
_LEADING_INVOKER_WORDS = ("env", "command")


def _strip_leading_invokers(argv: list[str]) -> list[str]:
    """Drop leading `env`/`command` tokens (each possibly followed by more
    `ENV=val` assignments, which `_lib._strip_prefix` handles) so `argv[0]`
    is the real program name. Never raises."""
    try:
        out = list(argv)
        changed = True
        while changed and out:
            changed = False
            if out[0] in _LEADING_INVOKER_WORDS:
                out = out[1:]
                changed = True
            out = _lib._strip_prefix(out)
        return out
    except Exception:
        return argv


def _evaluate_segment(seg_text: str, boards: list[dict]) -> tuple[bool, str]:
    """Evaluate one shell segment (raw text) against every shape. Returns
    (block, reason). An untokenizable segment is handled by the caller
    (decide()), not here — this function assumes `seg_text` tokenizes.

    Strips a leading `ENV=val` prefix and/or `env`/`command` invoker word
    before classifying argv[0] — `GH_TOKEN=x gh project item-add ...`,
    `env gh project item-add ...` must be recognized as `gh` invocations,
    not skipped because argv[0] was the assignment or the invoker word.
    """
    try:
        argv = shlex.split(seg_text)
    except ValueError:
        # Caller (decide()) handles the untokenizable fail-closed check via
        # the raw segment text; nothing more to do with an argv here.
        return (False, "")
    if not argv:
        return (False, "")
    argv = _strip_leading_invokers(argv)
    if not argv:
        return (False, "")

    if _is_gh(argv):
        block, reason = _shape_a_block(argv, boards)
        if block:
            return (block, reason)
        block, reason = _shape_c_block(argv, boards)
        if block:
            return (block, reason)
        # Shape (b) — `gh api graphql ...` — is evaluated against the RAW
        # segment text (a mutation string / -F variable value is text, not
        # a flag argv can resolve positionally), so it runs here on seg_text
        # rather than argv, but only once we know this segment is really a
        # `gh api` invocation at all (token-scanned past any leading gh
        # global flag, e.g. `gh -R owner/repo api graphql ...`).
        skipped = _skip_gh_globals(argv)
        if len(skipped) >= 2 and skipped[1] == "api":
            block, reason = _shape_b_block(seg_text, boards)
            if block:
                return (block, reason)
        return (False, "")

    if _is_gh_issue_sh(argv):
        return _shape_d_block(argv, boards)

    return (False, "")


# ---------------------------------------------------------------------------
# Pure top-level decision.
# ---------------------------------------------------------------------------


def decide(command: str, boards: list[dict] | None = None) -> tuple[bool, str]:
    """Pure policy: should this Bash command be blocked? -> (block, reason).

    `boards` lets a caller (tests) inject an already-loaded registry list;
    ``None`` (every production call) loads it fresh via :func:`load_registry`.

    Precedence, mirroring every sibling gate:
      1. Empty/whitespace command, or no protected boards configured
         (empty/missing/unparseable registry) -> allow.
      2. Per-segment evaluation (compound commands: &&, ||, ;, |, \\n) —
         the FIRST blocking segment blocks the whole line.
      3. A segment that mentions `gh` (or a `gh_issue.sh`-shaped invocation)
         but cannot be tokenized, AND whose RAW TEXT carries a protected-board
         add shape (a protected node id, OR the combination of `gh` +
         `project` + one of `item-add`/`item-create`/`--add-project`/
         `--project` tokens) -> BLOCK, fail-closed (untokenizable-segment-
         with-protected-board-shape).
      4. No blocking segment -> allow.

    Never raises: any error degrades to (False, "decision-error") — fail
    OPEN on this module's own bugs, matching every sibling gate's contract.
    """
    try:
        if not command or not command.strip():
            return (False, "empty-command")

        boards = boards if boards is not None else load_registry()
        if not boards:
            return (False, "no-protected-boards-configured")

        for seg in _lib._split_segments(command):
            if not seg.strip():
                continue
            try:
                argv = shlex.split(seg)
            except ValueError:
                argv = None
            if argv is None:
                if _mentions_gh(seg) and _looks_like_add_shape(seg, boards):
                    return (True, "untokenizable-segment-with-protected-board-shape")
                continue
            block, reason = _evaluate_segment(seg, boards)
            if block:
                return (True, reason)
        return (False, "no-protected-board-mutation")
    except Exception:
        return (False, "decision-error")


_ADD_SHAPE_HINT_RE = re.compile(
    r"\bproject\b.*\b(?:item-add|item-create)\b|\b(?:item-add|item-create)\b.*\bproject\b"
    r"|--add-project\b|--project\b",
    re.IGNORECASE | re.DOTALL,
)


def _looks_like_add_shape(seg_text: str, boards: list[dict]) -> bool:
    """Fail-closed heuristic for an UNTOKENIZABLE segment: does its raw text
    carry either a protected node id, or the shape of a `gh project`
    item-add/item-create/--project/--add-project invocation? Used only when
    the segment could not be shlex-split at all — matching block_branch_ops'
    own posture that an ambiguous wrapper around a dangerous shape is a
    bypass vector, not something to wave through. Never raises."""
    try:
        if find_board_by_node_id(boards, seg_text) is not None:
            return True
        if _ADD_MUTATION_RE.search(seg_text) is not None:
            return True
        return bool(_ADD_SHAPE_HINT_RE.search(seg_text))
    except Exception:
        return True  # ambiguous heuristic failure -> fail closed, same posture


# ---------------------------------------------------------------------------
# Thin main() — read event, decide, emit/log, exit 0.
# ---------------------------------------------------------------------------


def message_for(reason: str, boards: list[dict] | None = None) -> str:
    """The operator/agent-facing deny text for a given block reason."""
    title = None
    tracker = None
    if ":" in reason:
        prefix, title = reason.split(":", 1)
    else:
        prefix = reason
    boards = boards if boards is not None else load_registry()
    if title:
        for b in boards:
            if b.get("title") == title:
                tracker = b.get("tracker")
                break
    base = (
        f"protected_board_guard: blocked an attempt to ADD an item to the protected board "
        f"{title or 'unknown'} ({prefix}). This board is a customer-only inbox — only the "
        "SaaS support-ticket mirror may add items here; no agent may create or add issues "
        "to it directly. If this is a DIFFERENT project that merely shares this board's "
        "number, pass an explicit --owner naming that project's real owner (a number-only "
        "match with no --owner is deliberately treated as this protected board, by design)."
    )
    if tracker:
        base += f" See {tracker}."
    base += " See ~/.claude/.enforcement/log.jsonl."
    return base


def main() -> int:
    """Entry point. Always exits 0; a deny is emitted as JSON, never as status."""
    if _lib.disabled():
        return 0

    event = _lib.read_event()
    if _lib.tool_name(event) != "Bash":
        return 0

    command = _lib.bash_command(event)
    where = _lib.cwd(event)

    boards = load_registry()
    block, reason = decide(command, boards)
    if not block:
        return 0

    enforce = _lib.enforcing(where)
    detail = {"command": command[:2000], "reason": reason}
    if enforce:
        _lib.emit_pretooluse_deny(message_for(reason, boards))
        _lib.log(HOOK_NAME, "deny", enforce=enforce, **detail)
    else:
        _lib.log(HOOK_NAME, "would-deny", enforce=enforce, **detail)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess in tests
    sys.exit(main())
