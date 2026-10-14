#!/usr/bin/env python3
"""check_safety_core_parity — self-consistency validator for the hook runtime.

Ported from the proven bash reporter ~/.claude/scripts/enforcement_doctor.sh,
narrowed to its *validator* slice: instead of merely PRINTING the wired hooks
and the allowlist summary, this module ASSERTS the runtime is internally
consistent and surfaces every drift as a structured problem.

What it checks (the SPEC):
  1. Every hook command wired in ~/.claude/settings.json that references a
     hooks/ script (bash ~/.claude/scripts/<x>.sh, or a hooks/<x>.py module)
     points at a file that actually EXISTS. A wired-but-missing script is a
     dangling reference.
  2. ~/.claude/live-testing/allowlist.json PARSES as a JSON object and carries
     every REQUIRED key (the four the bash doctor summarizes):
       allowed_origins, allowed_company_tenants, test_recipients,
       denied_action_patterns.
  3. settings.json itself parses as an object and its `hooks` block is
     well-formed (a dict of event -> list-of-matcher-objects, each carrying a
     `hooks` list of command entries).
  4. GUARD WIRING (2026-08-03, added after #gh_issue_close_gate shipped fully
     unwired for a whole session -- "guard exists on disk, guard never fires,
     nothing here caught it"): every on-disk hooks/*.py module that LOOKS like
     a PreToolUse guard (its own source calls ``_lib.emit_pretooluse_deny(``,
     i.e. it is itself capable of emitting a deny, not merely a shared library
     other guards call into) must be reachable from a settings.json-wired
     command by walking (a) script refs literally named in a wired command,
     (b) script refs found INSIDE a reachable ``.sh`` dispatcher's own body
     (e.g. bash_gate.sh's ``python3 "$HOME/.claude/hooks/pretooluse_bash.py"``),
     and (c) top-level ``import X`` / ``from X import ...`` statements inside a
     reachable ``.py`` module's own body, where ``X.py`` is itself an on-disk
     hooks module (see :func:`wired_module_paths`). A guard module that is
     reachable by NEITHER path, and is not explicitly declared in
     :data:`STANDALONE_GUARD_MODULES` with a documented reason, is a
     self-consistency problem: it exists, but nothing would ever invoke it.

Structure (per the task contract):
  * check(settings, files) -> list[str]   — the PURE decision function. No I/O,
    no env reads; deterministic on its two inputs. `files` is the set/collection
    of paths that are known to EXIST (so tests inject a synthetic filesystem and
    the real runtime injects the real one). Trivial to cover.
  * main() — the thin adapter: reads the Stop/SessionStart event, loads
    settings.json + allowlist.json + the on-disk file set, calls check(),
    LOG-ONLY unless enforcing(); a Stop *block* is emitted only under enforce.
    Deny/block is JSON, never an exit code. Always exits 0.
  * CSA_DISABLE_HOOKS master-off short-circuits main() to a clean exit.

Never raises out to the caller: a crashing self-check must not wedge the agent.
"""

from __future__ import annotations

import json
import os
import re
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
if _HOOKS_DIR not in sys.path:  # pragma: no cover - runs at first import, before coverage attaches
    sys.path.insert(0, _HOOKS_DIR)

import _lib  # noqa: E402  (import after sys.path shim, matching sibling modules)

HOOK_NAME = "check_safety_core_parity"

# The keys the bash enforcement_doctor.sh summarizes out of allowlist.json. A
# live-testing policy missing any of these is drifted (browser_pool/prod_proxy
# read them and would fault on absence).
REQUIRED_ALLOWLIST_KEYS = (
    "allowed_origins",
    "allowed_company_tenants",
    "test_recipients",
    "denied_action_patterns",
)

# A hook command string references a script we can existence-check when it names
# either a bash script under ~/.claude/scripts/ OR a python module under
# ~/.claude/hooks/. These patterns pull the referenced path out of the command
# string exactly as it is wired in settings.json OR embedded inside another
# already-wired script's own body (see wired_module_paths -- e.g. bash_gate.sh
# invokes pretooluse_bash.py via `python3 "$HOME/.claude/hooks/x.py"`, using
# $HOME rather than ~, which is why that prefix is recognized too).
#   bash ~/.claude/scripts/git_guard.sh
#   python3 ~/.claude/hooks/git_guard.py   (future python-native wiring)
#   ~/.claude/hooks/git_guard.py           (bare, direct exec)
#   python3 "$HOME/.claude/hooks/git_guard.py"   (quoted, $HOME-prefixed)
_SCRIPT_REF = re.compile(
    r"(?:^|\s)[\"']?"  # start or whitespace before the path, optional opening quote
    r"((?:~|\$HOME)?/[^\s;&|]*?"  # a path token (no shell separators): ~/, $HOME/, or bare /
    r"(?:\.claude/scripts/|\.claude/hooks/)"
    r"[^\s;&|]+?\.(?:sh|py))"  # ending in .sh or .py
)

_HOME_PREFIX = "$HOME/"


def _expand_ref(raw: str) -> str:
    """Expand a captured script-ref token to an absolute path.

    Handles both the ``~/...`` convention (``os.path.expanduser``) and the
    ``$HOME/...`` convention some hook scripts use instead (bash_gate.sh /
    post_bash_gate.sh's own bodies) — Python's expanduser does not expand
    ``$HOME``, so that prefix is substituted explicitly. Never raises.
    """
    try:
        if raw.startswith(_HOME_PREFIX):
            return os.path.join(os.path.expanduser("~"), raw[len(_HOME_PREFIX) :])
        return os.path.expanduser(raw)
    except Exception:  # pragma: no cover - str ops on a str cannot realistically raise
        return raw


def extract_script_refs(command: str) -> list[str]:
    """Pull every ~/.claude/{scripts,hooks} script path out of a hook command.

    A single wired command may chain a kill-switch guard and the real script,
    e.g. `[ "$CSA_DISABLE_HOOKS" = 1 ] && exit 0; bash ~/.claude/scripts/x.sh`.
    We return each referenced script path (expanded ~ / $HOME -> the real
    home) in order. A command that references no such script (e.g. a bare
    `printf ...` banner) yields []. Never raises.
    """
    if not isinstance(command, str) or not command:
        return []
    try:
        refs: list[str] = []
        for m in _SCRIPT_REF.finditer(command):
            refs.append(_expand_ref(m.group(1)))
        return refs
    except Exception:  # pragma: no cover - regex over str cannot realistically raise
        return []


# ---------------------------------------------------------------------------
# Guard wiring (spec item 4) — PURE. Detects a hooks/*.py module that LOOKS
# like a PreToolUse guard but is unreachable from anything settings.json
# actually wires: "guard exists, guard never fires" (the exact class of bug
# gh_issue_close_gate.py shipped as — see the module docstring's item 4).
# ---------------------------------------------------------------------------

# A module counts as a PreToolUse-guard CANDIDATE when its own source calls
# `_lib.emit_pretooluse_deny(` -- i.e. it is ITSELF capable of emitting a
# PreToolUse deny, not merely a shared library some other guard calls into.
# `_lib.py` (the definer of that function) is excluded by construction: its
# own source never contains the `_lib.`-prefixed call on itself.
_GUARD_SIGNAL_RE = re.compile(r"_lib\.emit_pretooluse_deny\(")

# Top-level `import X` / `from X import ...` -- used to walk which OTHER
# on-disk hooks module a reachable .py module pulls in as a sibling import.
_IMPORT_RE = re.compile(
    r"^[ \t]*(?:import[ \t]+([A-Za-z_][A-Za-z0-9_]*)"
    r"|from[ \t]+([A-Za-z_][A-Za-z0-9_]*)[ \t]+import\b)",
    re.MULTILINE,
)

# Guard modules that are DELIBERATELY unreachable via the settings.json ->
# script -> python-import closure this module walks. Every entry needs a
# documented reason here -- this is not an escape hatch for forgetting to
# wire a guard, it is a record of a module whose activation mechanism is
# structurally different from that closure.
STANDALONE_GUARD_MODULES = frozenset(
    {
        # mint_prod_session.py self-gates: is_mint_invocation() inspects the
        # INVOKED command's own basename (argv[0]) rather than being imported
        # by a dispatcher -- an operator/agent runs it directly (aliased via
        # the `get_test_secret.sh` permissions.allow entry in settings.json),
        # it is not a module some other guard imports. See that module's own
        # docstring.
        "mint_prod_session.py",
    }
)


def local_python_imports(source: str, local_module_names) -> set:
    """Top-level `import X` / `from X import ...` refs in `source` where X is
    in `local_module_names` (the basenames, without ``.py``, of the on-disk
    hooks modules) — i.e. imports of a SIBLING hooks module, never a stdlib or
    third-party name (those simply won't be in `local_module_names`). Pure;
    never raises.
    """
    try:
        names = set(local_module_names) if local_module_names else set()
        found: set = set()
        for m in _IMPORT_RE.finditer(source or ""):
            name = m.group(1) or m.group(2)
            if name and name in names:
                found.add(name)
        return found
    except Exception:
        return set()


def wired_module_paths(command_script_refs, module_sources: dict) -> set:
    """BFS closure of every hooks-dir path reachable from settings.json's
    wired commands.

    Follows THREE edge types, breadth-first, from the `command_script_refs`
    roots (script paths already extracted from every wired settings.json
    command — see check()):
      (a) the roots themselves;
      (b) a script ref found INSIDE a reachable ``.sh`` file's own body (e.g.
          bash_gate.sh's ``python3 "$HOME/.claude/hooks/pretooluse_bash.py"``)
          — same extractor (extract_script_refs), applied to the file's text;
      (c) a top-level python `import X` inside a reachable ``.py`` file's own
          body, where ``X.py`` is itself a key of `module_sources`.

    `module_sources` maps an ABSOLUTE path -> its full text, for every
    on-disk hooks/*.py and hooks/*.sh file (real filesystem via main(); tests
    inject a synthetic mapping). A path with no entry in `module_sources` is a
    dead end (no body to walk further, but it's still marked reachable if it
    was reached). Never raises: any internal error degrades to an empty set
    (fail toward reporting MORE problems, not silently hiding a real gap).
    """
    try:
        local_by_name = {
            os.path.splitext(os.path.basename(p))[0]: p
            for p in module_sources
            if p.endswith(".py")
        }
        local_names = set(local_by_name)

        seen: set = set()
        queue: list = list(command_script_refs or [])
        while queue:
            path = queue.pop()
            if path in seen:
                continue
            seen.add(path)
            source = module_sources.get(path)
            if not source:
                continue
            for ref in extract_script_refs(source):
                if ref not in seen:
                    queue.append(ref)
            if path.endswith(".py"):
                for name in local_python_imports(source, local_names):
                    target = local_by_name.get(name)
                    if target and target not in seen:
                        queue.append(target)
        return seen
    except Exception:
        return set()


# Modules structurally excluded from candidacy regardless of what
# _GUARD_SIGNAL_RE finds in their source:
#   _lib.py                       — the DEFINER of emit_pretooluse_deny; its
#                                    own source never contains the `_lib.`-
#                                    prefixed call on itself (belt and
#                                    suspenders).
#   check_safety_core_parity.py   — THIS module. It is the one place in the
#                                    codebase whose job is to document the
#                                    `_lib.emit_pretooluse_deny(` signal in
#                                    prose (this very docstring, the problem
#                                    message text, etc.) — that prose contains
#                                    the exact substring _GUARD_SIGNAL_RE looks
#                                    for, which would otherwise make this
#                                    self-consistency checker flag ITSELF as
#                                    an unwired guard on every real run. It
#                                    genuinely is not a PreToolUse guard — it
#                                    is a Stop-event checker (main() calls
#                                    ``_lib.emit_stop_block``, never
#                                    ``emit_pretooluse_deny``).
_NOT_A_GUARD_CANDIDATE = frozenset({"_lib.py", "check_safety_core_parity.py"})


def looks_like_pretooluse_guard(basename: str, source: str) -> bool:
    """True iff a hooks/*.py module's OWN source calls
    ``_lib.emit_pretooluse_deny(`` — see the module-level comment above
    :data:`_GUARD_SIGNAL_RE`. See :data:`_NOT_A_GUARD_CANDIDATE` for the two
    modules structurally excluded regardless of what the regex finds. Never
    raises.
    """
    if basename in _NOT_A_GUARD_CANDIDATE or not source:
        return False
    try:
        return bool(_GUARD_SIGNAL_RE.search(source))
    except Exception:
        return False


def guard_wiring_problems(module_sources: dict, wired, standalone=None) -> list[str]:
    """{problem strings} for every hooks/*.py guard-shaped module that is
    NEITHER in `wired` NOR declared in `standalone`. Pure; deterministic
    (sorted by path). `standalone` defaults to
    :data:`STANDALONE_GUARD_MODULES`.
    """
    allow = standalone if standalone is not None else STANDALONE_GUARD_MODULES
    problems: list[str] = []
    try:
        for path in sorted(p for p in module_sources if p.endswith(".py")):
            basename = os.path.basename(path)
            if basename in allow:
                continue
            if not looks_like_pretooluse_guard(basename, module_sources.get(path, "")):
                continue
            if path not in wired:
                problems.append(
                    "hooks/%s looks like a PreToolUse guard (its source calls "
                    "_lib.emit_pretooluse_deny) but is never wired into any "
                    "dispatcher reachable from settings.json -- it would never "
                    "fire. Wire it in, or add it to STANDALONE_GUARD_MODULES "
                    "with a documented reason if it is intentionally invoked "
                    "another way." % basename
                )
    except Exception:
        return problems
    return problems


def check(settings: dict, files, module_sources: dict | None = None) -> list[str]:
    """PURE self-consistency check. Returns a list of human-readable problems.

    Args:
      settings: the parsed settings.json (a dict). A non-dict or the sentinel
        {"__parse_error__": ...} is itself reported as a problem.
      files: a collection (set/list/frozenset) of absolute paths KNOWN TO EXIST.
        Membership is the existence oracle, so this function stays pure and the
        real filesystem is injected only by main(). A None/non-collection is
        treated as "nothing exists".
      module_sources: optional ``{absolute_path: source_text}`` for every
        on-disk hooks/*.py and hooks/*.sh file — the raw material the GUARD
        WIRING check (spec item 4) needs. ``None`` (the default, and every
        pre-existing caller) SKIPS that check entirely — fully backward
        compatible; only main()'s real invocation supplies it.

    Empty list == fully consistent. The order of problems is deterministic:
    settings-shape problems, then per-event hook problems (in wired order),
    then guard-wiring problems, then allowlist problems.

    Never raises: any unexpected shape yields a problem string, not an exception.
    """
    problems: list[str] = []
    command_script_refs: list[str] = []

    # Normalize the existence oracle to a set of strings.
    try:
        existing = set(files) if files else set()
    except Exception:
        existing = set()

    # ---- settings.json shape -------------------------------------------------
    if not isinstance(settings, dict):
        problems.append("settings.json did not parse as a JSON object")
        return problems
    if "__parse_error__" in settings:
        problems.append("settings.json failed to parse: %s" % settings["__parse_error__"])
        return problems

    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        problems.append("settings.json 'hooks' is not an object")
        return problems

    # ---- every wired hook -> existing script --------------------------------
    for event, matchers in hooks.items():
        if not isinstance(matchers, list):
            problems.append("hooks.%s is not a list of matcher objects" % event)
            continue
        for m_idx, matcher in enumerate(matchers):
            if not isinstance(matcher, dict):
                problems.append("hooks.%s[%d] is not an object" % (event, m_idx))
                continue
            entries = matcher.get("hooks", [])
            if not isinstance(entries, list):
                problems.append("hooks.%s[%d].hooks is not a list" % (event, m_idx))
                continue
            for h_idx, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    problems.append(
                        "hooks.%s[%d].hooks[%d] is not an object" % (event, m_idx, h_idx)
                    )
                    continue
                command = entry.get("command", "")
                if not isinstance(command, str) or not command:
                    problems.append(
                        "hooks.%s[%d].hooks[%d] has no command string" % (event, m_idx, h_idx)
                    )
                    continue
                refs = extract_script_refs(command)
                command_script_refs.extend(refs)
                for ref in refs:
                    if ref not in existing:
                        problems.append("hooks.%s references missing script: %s" % (event, ref))

    # ---- guard wiring: every PreToolUse-guard-shaped module is reachable -----
    if isinstance(module_sources, dict):
        wired = wired_module_paths(command_script_refs, module_sources)
        problems.extend(guard_wiring_problems(module_sources, wired))

    # ---- allowlist.json parses and has required keys -------------------------
    allowlist = settings.get("__allowlist__", None)
    if allowlist is None:
        problems.append("allowlist.json is absent")
    elif isinstance(allowlist, dict) and "__parse_error__" in allowlist:
        problems.append("allowlist.json failed to parse: %s" % allowlist["__parse_error__"])
    elif not isinstance(allowlist, dict):
        problems.append("allowlist.json did not parse as a JSON object")
    else:
        for key in REQUIRED_ALLOWLIST_KEYS:
            if key not in allowlist:
                problems.append("allowlist.json missing required key: %s" % key)

    return problems


# ---------------------------------------------------------------------------
# Filesystem / IO adapters — kept OUT of check() so the decision stays pure.
# ---------------------------------------------------------------------------


def _load_json(path: str):
    """Read+parse a JSON file. Returns the object, None if absent, or the
    sentinel {"__parse_error__": <msg>} on a decode/read failure. Never raises.
    """
    try:
        if not os.path.isfile(path):
            return None
    except Exception:
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception as exc:  # unreadable or malformed JSON
        return {"__parse_error__": str(exc)}


def _settings_path() -> str:
    return os.path.join(_lib.CLAUDE_DIR, "settings.json")


def _allowlist_path() -> str:
    return os.path.join(_lib.CLAUDE_DIR, "live-testing", "allowlist.json")


def _scripts_dir() -> str:
    return os.path.join(_lib.CLAUDE_DIR, "scripts")


def _module_hooks_dir() -> str:
    return os.path.join(_lib.CLAUDE_DIR, "hooks")


def _existing_script_files() -> set:
    """Enumerate the real on-disk script files check() may reference.

    Returns the set of absolute paths for every *.sh under ~/.claude/scripts
    AND every *.py / *.sh under ~/.claude/hooks (the hooks dir carries its own
    bash dispatchers too — bash_gate.sh, post_bash_gate.sh — wired directly by
    settings.json; omitting them here previously made this checker itself
    report them as dangling references on every real run, a false positive
    fixed 2026-08-03). This is the existence oracle passed to the pure
    check(). Never raises: an unreadable dir yields whatever was walkable.
    """
    found: set = set()
    for base, exts in ((_scripts_dir(), (".sh",)), (_module_hooks_dir(), (".py", ".sh"))):
        try:
            for name in os.listdir(base):
                if name.endswith(exts):
                    found.add(os.path.join(base, name))
        except Exception:
            continue
    return found


def _hook_module_sources() -> dict:
    """Read the full text of every hooks/*.py and hooks/*.sh file, keyed by
    absolute path — the raw material :func:`wired_module_paths` /
    :func:`guard_wiring_problems` need (script refs inside a .sh dispatcher's
    own body, python imports inside a .py module's own body). This is the
    `module_sources` oracle passed to the pure check(). Never raises: an
    unreadable dir yields {}; an unreadable individual file is simply absent
    from the map (a dead end for the closure walk, not a crash).
    """
    sources: dict = {}
    base = _module_hooks_dir()
    try:
        names = os.listdir(base)
    except Exception:
        return sources
    for name in names:
        if not name.endswith((".py", ".sh")):
            continue
        path = os.path.join(base, name)
        try:
            with open(path, encoding="utf-8") as fh:
                sources[path] = fh.read()
        except Exception:
            continue
    return sources


def _gather(settings_path: str, allowlist_path: str) -> dict:
    """Load settings.json and fold the parsed allowlist under __allowlist__.

    check() takes a single `settings` dict, so we stash the allowlist result on
    it under a reserved key. Returns a dict safe to hand to check() (a non-dict
    settings body is wrapped so check() can report it).
    """
    settings = _load_json(settings_path)
    allowlist = _load_json(allowlist_path)
    # _load_json yields a dict for a real object AND for the {"__parse_error__":..}
    # sentinel; both fold the allowlist in and let check() report any shape/parse
    # problem uniformly.
    if isinstance(settings, dict):
        # Don't mutate a shared object across calls; shallow copy is enough since
        # we only add one top-level key.
        merged = dict(settings)
        merged["__allowlist__"] = allowlist
        return merged
    # settings absent (None) or valid-JSON-but-not-an-object (e.g. a list): wrap
    # so check() reports the shape problem but still sees the allowlist.
    if settings is None:
        return {"__parse_error__": "settings.json absent", "__allowlist__": allowlist}
    return {
        "__parse_error__": "settings.json is not an object",
        "__allowlist__": allowlist,
    }


def _summary(problems: list[str]) -> str:
    """Human-readable one-shot summary of the self-check for the block reason."""
    head = "%s: %d self-consistency problem(s):" % (HOOK_NAME, len(problems))
    body = "\n".join("  - %s" % p for p in problems)
    return head + "\n" + body


def main() -> int:
    """Thin adapter: read event, run the pure check, log/emit, exit 0.

    LOG-ONLY unless enforcing(): under enforce a Stop *block* is emitted so the
    agent is told to fix runtime drift before finishing. Deny/block is JSON; the
    exit code is ALWAYS 0. CSA_DISABLE_HOOKS master-off short-circuits.
    """
    try:
        if _lib.disabled():
            return 0

        ev = _lib.read_event()
        where = _lib.cwd(ev)

        merged = _gather(_settings_path(), _allowlist_path())
        files = _existing_script_files()
        module_sources = _hook_module_sources()
        problems = check(merged, files, module_sources)

        if not problems:
            _lib.log(HOOK_NAME, "ok", cwd=where)
            return 0

        enforce = _lib.enforcing(where)
        decision = "block" if enforce else "would-block"
        _lib.log(
            HOOK_NAME,
            decision,
            cwd=where,
            problem_count=len(problems),
            problems=problems,
        )
        if enforce:
            _lib.emit_stop_block(_summary(problems))
        return 0
    except Exception:
        # A crashing self-check must never wedge the agent: degrade OPEN.
        try:
            _lib.log(HOOK_NAME, "error")
        except Exception:
            pass
        return 0


if __name__ == "__main__":  # pragma: no cover - process entrypoint
    sys.exit(main())
