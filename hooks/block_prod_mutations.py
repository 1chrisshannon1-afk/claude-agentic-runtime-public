#!/usr/bin/env python3
"""block_prod_mutations — PreToolUse hook: fail-closed guard on prod network calls.

Ports the PROVEN decision core of ``~/.claude/live-testing/prod_proxy.py`` into a
Claude Code hook. When an agent drives a browser (MCP Playwright slot) or issues a
network request via a tool, this hook inspects the (method, url, body) and applies
a DEFAULT-DENY policy read from ``~/.claude/live-testing/allowlist.json``:

GOVERNING INVARIANT (fix-round-7, 2026-09-11, stated once here and enforced
throughout the module — see the WHATWG section above ``_host_of`` for the
full mechanism): for every URL this hook evaluates, its own notion of
(host, path) must agree with the browser's — and where it cannot be sure the
two agree, it denies rather than guesses. Six rounds (host case, default
port, path dot-segments, an encoded slash, a non-default port, and a
backslash) each relocated the SAME underlying mechanism — this hook decides
using Python's ``urllib.parse.urlsplit`` while the request is actually
issued and routed by a WHATWG/Chromium URL parser, and the two disagree on
inputs neither one rejects outright — by patching one spelling axis at a
time. Fix-round-7 replaces the mechanism itself: every URL is pre-normalized
to WHATWG rules (``_whatwg_pre_normalize``) before ``urlsplit`` ever sees
it, and a URL this hook cannot confidently canonicalize at all now DENIES a
non-idempotent request outright (``_decide``'s safety net) rather than
falling through to R0-R4's allow branch — a guard that cannot understand a
URL must not permit a write through it. Fix-round-8 (2026-09-11) closed one
precise gap in that same safety net: a C0 control (0x00-0x1F minus
tab/LF/CR) or 0x7F DEL surviving into the HOST or PORT component used to
still parse "confidently" through ``urlsplit`` (a clean-looking hostname
came back) even though a real WHATWG/Node parse of the identical string is
a hard failure there — see ``_authority_has_forbidden_control`` and the
WHATWG section's ``_C0_OR_DEL_RE`` note for the live-verified ground truth
(including why PATH/QUERY/FRAGMENT/USERINFO positions are deliberately
exempt — WHATWG percent-encodes those in place rather than rejecting them).
Fix-round-9 (2026-09-11, independent-reviewer finding) extended the SAME
invariant to the HOST axis itself: a percent-encoded dot
(``app.example%2ecom``) or an IDNA-mappable non-ASCII label
(``app.example。com``, the fullwidth ideographic full stop) both
resolve to ``app.example.com`` under a real WHATWG/Node ``URL``
parse (live-verified), but ``urlsplit`` returned the un-normalized string
unchanged, which let ``_is_tenant_scoped_host`` (R2) see a spelling it
didn't recognize as one of THIS RUNTIME'S OWN hosts and skip the off-tenant
guard entirely for a request that a browser would actually route to our
own production app. ``_host_of`` now applies ``_idna_normalize_host``
(percent-decode + per-label IDNA ToASCII) after ``urlsplit`` so its
returned hostname agrees with the browser's; a hostname that cannot be
confidently normalized degrades to the raw ``urlsplit`` hostname rather
than being trusted un-normalized. Fix-round-9 also closed a secondary gap
in the same area: the IPv6 loopback (``::1`` / ``[::1]``) was missing from
``_TENANT_SCOPED_HOST_SUFFIXES`` and, independently, was being mangled by
``_is_tenant_scoped_host``'s own defensive ``:port``-stripping logic
(which mistook the address's own colons for a port separator) — both are
fixed in the same round; see that function's docstring.

  R0  Idempotent reads (GET / HEAD) to an allowlisted host are ALLOWED.
  R1  Non-idempotent methods (POST/PUT/PATCH/DELETE) whose URL matches any
      ``denied_action_patterns`` (Stripe / comms providers / admin) are DENIED.
      Both the URL and each pattern are canonicalized before matching
      (WHATWG pre-normalized — backslash-to-slash for special schemes,
      leading/trailing C0-control-or-space stripped, tab/newline/CR stripped
      — then scheme/host lowercased, PORT DROPPED ENTIRELY, path lowercased,
      percent-decoded, dot-segments resolved, duplicate slashes collapsed —
      ``_whatwg_pre_normalize`` / ``_normalize_url_for_pattern_match`` /
      ``_canonical_origin_and_path`` / ``_canonicalize_path``, fix-round-3
      through fix-round-7) so a denied pattern cannot be bypassed by
      host/path case, ANY port spelling (default or non-default — fix-round-6
      closed the non-default-port gap by making this side use the SAME
      port-insensitive canonicalization as R4's own host-allowlist check,
      see ``_canonical_origin_and_path``'s docstring), ``//``/``/./``/``/../``
      path spelling, percent-encoding a path segment (e.g. ``/%61pi/`` for
      ``/api/``), a backslash-for-forward-slash spelling, or embedded/
      surrounding tab/newline/CR/space/C0-control characters
      (fix-round-7).
  R2  Any request to one of THIS RUNTIME'S OWN PRODUCT APP HOSTS (see
      ``_TENANT_SCOPED_HOST_SUFFIXES``) whose URL carries a company/tenant id
      that is NOT in ``allowed_company_tenants`` is DENIED (off-tenant guard).
      A third-party host is never scoped by this rule — see the 2026-09-11
      LinkedIn false-positive note on ``_is_tenant_scoped_host``. The host is
      IDNA/percent-decode normalized before this scoping check (fix-round-9)
      so a spelling-obfuscated reference to one of our own hosts cannot skip
      the guard — see ``_idna_normalize_host``.
  R3  Non-idempotent methods to a comms endpoint whose recipient (parsed from
      body/URL) is NOT in ``test_recipients`` (or has no recipient at all) are
      DENIED. An idempotent GET/HEAD to a comms-shaped path carries no side
      effect and is not gated by this rule (falls through to R0/R4).
  R4  Otherwise ALLOW if the host is allowlisted. Non-idempotent methods to a
      non-allowlisted host are DENIED (default-deny); an idempotent GET/HEAD
      that reaches here is ALLOWED (and logged) since it has no side effect.
  R5  INTERACTION-CLASS PLAYWRIGHT TOOLS CARRY NO URL (added 2026-09-10, D0b;
      "interaction-class" REDEFINED 2026-09-28 as an ALLOWLIST inversion,
      GH #5151 — see ``_READ_ONLY_HOST_SAFE_ACTIONS``'s own module comment
      for the full rationale and the real-tool-name enumeration it is built
      from). Most Playwright MCP tools — ``browser_click`` / ``_type`` /
      ``_fill_form`` / ``_press_key`` / ``_select_option`` / ``_file_upload``
      / ``_drag`` / ``_drop`` / ``_handle_dialog`` / ``_evaluate`` /
      ``_run_code_unsafe``, and any tool name this module does not
      specifically recognize as read-only-safe — act on whatever page is
      currently loaded in a slot, so R0-R4 above (all URL-keyed) never see
      them at all — a click on a live production admin page is invisible to
      every rule above. A small, explicit ALLOWLIST of verified read-only
      tool names (``_READ_ONLY_HOST_SAFE_ACTIONS`` — navigate/back/forward,
      snapshot, screenshot, wait_for, console_messages, network_requests,
      close, resize, and ``browser_tabs`` only with a confirmed
      ``action: "list"``) is the ONLY carve-out; everything else, including
      an unrecognized/future tool name, is treated as an interaction by
      construction — this is a deliberate reversal of the ORIGINAL
      denylist-by-name design, which let an unenumerated tool name fall
      through as "not an interaction" and reach an unconditional allow. R5
      tracks, PER SLOT (parsed from the tool name:
      ``mcp__playwright-NN__*``, ``mcp__playwright-admin-csa__*``,
      ``mcp__playwright-auth__*``), the HOST of that slot's last
      ``browser_navigate`` URL (state: ``~/.claude/.enforcement/
      slot_hosts.json``, atomic write, TTL 4h, tolerant of a missing/corrupt
      file — treated as "no host recorded"). An interaction-class tool is
      DENIED when the slot's recorded host is listed in the new
      ``read_only_hosts`` allowlist key, OR when NO host is recorded at all
      (fail-closed: the only cost of a false deny here is one more
      ``browser_navigate``, which R5 itself never denies). R5 intercepts in
      ``decide_event`` BEFORE the ``no-url`` early return (interaction-class
      tools carry no URL, so a rule keyed only on "is there a URL" would never
      reach them), and ``main()``'s own ``if not url: return 0`` pass-through
      is likewise conditioned so an R5 deny is never dropped there.
      ``browser_navigate`` itself is NEVER denied by R5 (denying the one tool
      that establishes the recorded host would make the fail-closed default
      unrecoverable) — it always records the new host and falls through to
      R0-R4 for its own URL. The host record is cleared by
      ``browser_pool.py``'s ``cmd_release`` (a slot's next lease starts with
      no recorded host) and — PROBED, see below — by a delivered
      ``browser_close`` event. Route-level SPA navigation (an in-page
      ``pushState``/hash change with no new ``browser_navigate`` call) does
      NOT clear or update the record; that is deliberate host-level, not
      route-level, tracking.

      KNOWN RESIDUAL, ACCEPTED (M3, 2026-09-10 review): CROSS-ORIGIN
      navigation-BY-CLICK is a real gap R5 does not detect. A click, a
      redirect, an OAuth bounce, or a ``target=_blank`` open that lands the
      slot on a different origin (e.g. a link from staging onto
      app.example.com) leaves the recorded host at whatever the
      last real ``browser_navigate`` call set — every subsequent interaction
      on the new, unrecorded-origin page is judged against the STALE host
      until the TTL expires or a fresh ``browser_navigate`` runs. The
      compensating controls, both already in force and NOT new: (1) the
      live-testing audit plan's operator-instruction-only (O-I)
      navigation-only procedure for anything on a production host, and (2)
      the ``*/admin/*`` entry in ``denied_action_patterns``, which still
      denies any URL-carrying admin mutation regardless of what R5 believes
      the recorded host is. Tracked follow-up: refresh the recorded host
      from ``browser_snapshot``/``browser_take_screenshot`` tool results via
      a ``PostToolUse`` companion hook, so a same-call page inspection can
      correct a stale record without waiting on the next explicit navigate —
      tracked on #5323.

      PROBE RESULT (2026-09-10): does the ``PreToolUse`` matcher
      (``mcp__playwright.*``, a regex) deliver a ``browser_close`` event to
      this hook? YES, mechanically — the matcher is not tool-specific, it
      matches every ``mcp__playwright*`` tool name, and ``browser_close`` is
      a real, granted tool (see ``agents/browser-ops.md``'s enumerated grant)
      on exactly the same footing as ``browser_navigate``/``browser_click``.
      What is UNVERIFIED (no live MCP session available to this change) is
      that the real ``@playwright/mcp`` server actually names its close call
      ``browser_close`` at runtime exactly as granted — believed true (it is
      the same string used to grant the tool) but not observed firing
      end-to-end. The clear-on-close code path is implemented; treat it as
      UNVERIFIED-BY-EXECUTION until a live probe confirms it, and rely on the
      TTL / release-on-``cmd_release`` clears (both verified by test) as the
      backstops if it does not.

      SESSION-BANNER EXEMPTION (added 2026-09-28, operator directive: every
      session must mark its own Playwright tabs with a colored, named banner
      so a human can tell which session controls which slot; hardened the
      same day per trust-architect review). R5 otherwise denies
      ``browser_evaluate`` outright on a read-only-host slot, with no way
      for an agent to write even a harmless cosmetic identification banner
      onto a prod tab. A NARROW, single-snippet carve-out allows exactly ONE
      canonical, fixed-CSS DOM-injection snippet (only the banner TEXT and
      background COLOR vary) and nothing else — see the constants/functions
      just above ``r5_decision`` (``_SESSION_BANNER_RE``,
      ``_match_session_banner_snippet``, ``_is_exempt_session_banner_call``)
      and ``live-testing/allowlist_README.md``'s "Session-banner exemption"
      section (under ``read_only_hosts``) for the full character-class/
      canonical-CSS rules. It is scoped to ``browser_evaluate`` only (never
      ``browser_run_code_unsafe`` — see ``_is_exempt_session_banner_call``'s
      own docstring for why that tool gets no exemption regardless of
      payload), requires *tool_input*'s key set to be a SUBSET of
      ``{"function"}`` (an allowlist, not a denylist of
      ``target``/``element``/``ref`` — any other key, known or not, fails
      closed), and never bypasses R5's separate "no recorded navigate host"
      fail-closed deny.

      RETIRED (2026-09-28, operator directive, cold round-3 review): a
      SECOND exemption briefly existed on this same read-only-host deny
      branch — the "interactive-path-prefix" exemption, scoped to
      ``browser_type``, gated by a per-slot arm file — to let an agent send
      one chat message to othercompany's Ada assistant on an otherwise
      read-only production host. It was REMOVED entirely (arm files, the
      arming/consume state machine, its allowlist key, its tests, and its
      docs): the analytics need it served (OtherApp #135) was met another
      way, and its own residual risk was judged not worth carrying. Only
      the session-banner exemption above remains.

Structure (per the hook-system contract):
  * ``policy_decision(method, url, body)`` — the PURE decision function, ported
    verbatim from prod_proxy.py (the only place rules live). No I/O.
  * ``decide_event(ev, allowlist)`` — pure adapter: pulls (method, url, body)
    out of a hook event and returns (should_block, method, url, reason). Also
    runs R5 (see above) via the pure ``r5_decision`` function, consulting only
    the ``slot_hosts`` mapping it is given (no I/O of its own).
  * ``main()`` — thin shell: read event, decide, LOG always, emit a deny ONLY
    when enforcing() and not disabled(); always exit 0 (deny is via JSON). The
    R5 state I/O (reading/writing ``slot_hosts.json``) lives here / in the
    small adapter functions below it, never inside ``r5_decision`` itself.

Master-off: ``CSA_DISABLE_HOOKS=1`` (via ``_lib.disabled()``) short-circuits to a
no-op. LOG-ONLY unless ``_lib.enforcing()`` — in log-only mode a would-be deny is
recorded to the decision log but the tool call is NOT blocked.

Every decision also appends one JSONL line to
``~/.claude/.enforcement/prod_actions.jsonl`` (ts, method, url, allow, reason),
matching prod_proxy.py's audit trail. R5 denies are logged the same way as
R0-R4 (both the structured decision log and, when a URL happens to also be
present, the prod_actions audit trail).
"""

from __future__ import annotations

import fnmatch
import ipaddress
import json
import os
import re
import sys
import time
from typing import Optional, Tuple
from urllib.parse import parse_qs, unquote, urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402  (import after sys.path shim)

# ---------------------------------------------------------------------------
# Constants (mirrors prod_proxy.py). Paths are computed from _lib.CLAUDE_DIR at
# call time (not import time) so the hermetic test sandbox — which monkeypatches
# _lib.CLAUDE_DIR — is honored.
# ---------------------------------------------------------------------------

HOOK_NAME = "block_prod_mutations"


def _allowlist_path() -> str:
    """Absolute path to ``live-testing/allowlist.json`` under the live CLAUDE_DIR."""
    return os.path.join(_lib.CLAUDE_DIR, "live-testing", "allowlist.json")


def _actions_log_path() -> str:
    """Absolute path to ``prod_actions.jsonl`` under the live enforcement dir."""
    return os.path.join(_lib.CLAUDE_DIR, ".enforcement", "prod_actions.jsonl")


def slot_hosts_path() -> str:
    """Absolute path to R5's ``slot_hosts.json`` under the live enforcement dir.

    Same lane as ``prod_actions.jsonl`` (``~/.claude/.enforcement/``) — public
    (no leading underscore) so ``browser_pool.py``'s ``cmd_release`` can import
    and clear the same file this module writes, without duplicating the path.

    Holds ``host``/``ts`` per slot — the interactive-path-prefix exemption
    (and its per-slot arm file, ``arm_<slot>``) that briefly extended this
    module was REMOVED 2026-09-28 (operator directive, cold round-3 review —
    its purpose was met another way and it was not worth its residual risk);
    this file's shape and this function are otherwise unaffected.
    """
    return os.path.join(_lib.CLAUDE_DIR, ".enforcement", "slot_hosts.json")


_IDEMPOTENT_METHODS = frozenset({"GET", "HEAD"})
_NON_IDEMPOTENT_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# Keywords that identify a denied pattern as a comms (email/SMS/voice) endpoint.
_COMMS_KEYWORDS = ("twilio", "sendgrid", "mailgun", "vapi", "ringcentral")

# URL path fragments that mark an *app-hosted* comms endpoint (the browser calls
# the app's own API, which then talks to a provider server-side).
_APP_COMMS_PATH_KEYWORDS = (
    "/send-email",
    "/send-sms",
    "/send_message",
    "/send-message",
    "/sms",
    "/email/send",
    "/messages",
    "/notify",
    "/invite",
    "/voice/call",
    "/place-call",
)

# URL path shapes that carry a company/tenant id. Lowercase-only by design —
# ``_extract_tenant_ids`` lowercases the path before matching (fix-round-11,
# 2026-09-11), so these never need an uppercase/mixed-case variant of their
# own; do not add one.
_TENANT_URL_PATTERNS = (
    re.compile(r"/companies/([A-Za-z0-9_-]+)"),
    re.compile(r"/company/([A-Za-z0-9_-]+)"),
    re.compile(r"/c/([A-Za-z0-9_-]+)"),
    re.compile(r"/tenants?/([A-Za-z0-9_-]+)"),
)
# Query-param names that carry a company/tenant id. Canonical spellings only
# (including the camelCase variants a real frontend might send) —
# ``_extract_tenant_ids`` case-folds the query string's own keys before
# looking these up (fix-round-11, 2026-09-11), so ``?COMPANY_ID=...`` and
# ``?CompanyId=...`` are both found without a matching entry here.
_TENANT_QUERY_KEYS = (
    "company",
    "company_id",
    "companyId",
    "tenant",
    "tenant_id",
    "tenantId",
)

# Hosts (bare, no scheme/port) R2's tenant guard applies to: THIS RUNTIME'S
# OWN two product app bases (ExampleApp AI, OtherApp) plus local-dev
# loopback spellings. ``~/.claude/knowledge/repo_registry.json`` was checked
# first (per this fix's own instructions) and carries no product-app-host
# key at all — only ``repos.<slug>.root`` (a filesystem path) — so there is
# nothing to derive this list FROM; it is pinned here instead, cross-checked
# against the live ``allowed_origins``/``read_only_hosts`` entries in
# ``live-testing/allowlist.json`` (every ``*.example.com`` and
# ``*.otherapp.example`` origin listed there is a suffix match on one of these
# two bases).
#
# 2026-09-11 LinkedIn false positive: ``browser_navigate`` to
# ``https://www.linkedin.com/company/setup/new/`` was DENIED with "tenant
# 'setup' not in allowed_company_tenants" because the generic
# ``/company/<slug>`` pattern above matches ANY host's path shape, and R2
# used to run unconditionally. LinkedIn (``/company/<slug>``), Crunchbase
# (``/organization/<slug>``), and G2 (``/products/<slug>``) all have URL
# shapes that coincidentally look tenant-scoped but carry no ExampleApp
# AI / OtherApp tenant boundary at all — R2 must only ever fire on OUR OWN
# app hosts. See ``_is_tenant_scoped_host``.
#
# 2026-09-11 fix-round-9 secondary gap (independent-reviewer finding,
# same round as the IDNA/percent-decode host-normalization fix): the IPv4
# loopback spellings above were covered, but the IPv6 loopback (``::1``,
# as ``_host_of``/``urlsplit`` return it after stripping the ``[...]``
# brackets — see ``_is_tenant_scoped_host``'s own bracket-aware compare)
# was not, so local-dev served over IPv6 loopback was silently un-scoped
# by R2 while every other loopback spelling was gated. Added as an EXACT
# entry (never a suffix match — ``"::1"`` as a dotted-suffix check would
# wrongly match any host ending in the literal substring ``::1``, which
# cannot occur for a real hostname but is not a comparison this list's
# existing suffix-match loop should be trusted to short-circuit safely for
# a non-dotted address family).
#
# 2026-09-11 fix-round-10 BLOCKER (independent-reviewer finding): the
# comment above claims this list was cross-checked against every live
# ``allowed_origins``/``read_only_hosts`` entry in
# ``live-testing/allowlist.json`` -- that check was real but incomplete. It
# enumerated only the two dotted bases (``example.com``,
# ``otherapp.example``) and never noticed that OtherApp is ALSO served from two
# Firebase/Google-hosted app hosts that carry no ``.otherapp.example`` suffix
# at all: ``otherapp-prod.firebaseapp.com`` (a declared PRODUCTION
# ``read_only_hosts`` entry -- allowlist.json's own PHI-tenant, othercompany,
# is reachable through it) and ``otherapp-staging.web.app`` (an
# ``allowed_origins`` entry). Because both hosts are themselves
# R4-allowlisted, R4's default-deny provided no backstop once R2 stopped
# scoping them -- an off-tenant request to either host was fully ALLOWED
# (live-verified pre-fix-round-10: ``_decide('POST',
# 'https://otherapp-prod.firebaseapp.com/company/co-EVILTENANT/patients',
# ...)`` returned an unconditional allow). Added as EXACT entries below
# (never a ``firebaseapp.com``/``web.app`` suffix -- either suffix would
# wrongly scope every unrelated Firebase/Google-hosted site on the
# internet, which is not this list's job). See
# ``test_r10_read_only_hosts_are_all_tenant_scoped`` for the mechanical guard
# added the same round so a future host added to
# ``live-testing/allowlist.json``'s ``read_only_hosts`` without a matching
# entry here fails a test rather than silently reopening this same gap.
#
# 2026-09-11 fix-round-10 MAJOR (independent-reviewer finding, same round):
# once ``_idna_normalize_host`` began
# canonicalizing IP literals (see ``_canonicalize_ip_literal``), the
# IPv4-mapped IPv6 loopback (``::ffff:127.0.0.1``, e.g. as spelled
# ``[::ffff:127.0.0.1]`` in a URL) canonicalizes to a STRING DIFFERENT from
# the compressed pure-IPv6 loopback ``::1`` already listed above — it is a
# genuinely distinct textual loopback alias, not a duplicate, so it needs
# its own exact entry rather than being expected to match ``::1``.
_TENANT_SCOPED_HOST_SUFFIXES = (
    "example.com",
    "otherapp.example",
    "otherapp-prod.firebaseapp.com",
    "otherapp-staging.web.app",
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
    "::ffff:127.0.0.1",
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# E.164-ish: '+' then 8-15 digits.
_PHONE_RE = re.compile(r"\+\d{8,15}")

# Hook-event fields that may carry a URL (across browser / fetch-style tools).
_URL_KEYS = ("url", "URL", "href", "link", "address", "target")
# Hook-event fields that may carry a request body / payload.
_BODY_KEYS = ("body", "data", "payload", "postData", "post_data", "content", "json")
# Hook-event fields that may carry an HTTP method.
_METHOD_KEYS = ("method", "httpMethod", "http_method", "verb")


# ---------------------------------------------------------------------------
# R5 constants — interaction-class Playwright tools carry no URL.
# ---------------------------------------------------------------------------

# Tool-name shape: mcp__<slot>__<action>, e.g. "mcp__playwright-07__browser_click",
# "mcp__playwright-admin-csa__browser_navigate", "mcp__playwright-auth__browser_type".
#
# The bare "playwright" prefix match (m7, 2026-09-10 review) is DELIBERATE
# and fail-closed BY CONSTRUCTION for any future playwright-prefixed server:
# a not-yet-existing slot name (e.g. a hypothetical "playwright-admin-otherapp")
# is picked up by this same pattern with no code change required, so R5 keeps
# covering it from day one rather than silently exempting it until someone
# remembers to widen a narrower regex. Do NOT narrow this pattern to an
# enumerated slot list — the bare `mcp__playwright__` server, `-adhoc`,
# `-auth`, and `-admin-csa` must all keep matching (see
# test_playwright_tool_re_matches_every_slot_shape).
_PLAYWRIGHT_TOOL_RE = re.compile(r"^mcp__(playwright[A-Za-z0-9-]*)__(\w+)$")

# The action that establishes (and refreshes) a slot's recorded host. Never
# denied by R5 itself — see module docstring.
_NAVIGATE_ACTION = "browser_navigate"

# The action that (probed, see docstring) may clear a slot's recorded host.
_CLOSE_ACTION = "browser_close"

# History navigation actions (cold round-3 review, 2026-09-28): neither
# carries a URL this hook could record, but BOTH change what page is loaded
# in the slot — so the slot's recorded host is INVALIDATED (cleared) rather
# than left describing a page the browser may have already left. See
# `_main_impl`'s own `invalidates_host` handling.
_NAVIGATE_BACK_ACTION = "browser_navigate_back"
_NAVIGATE_FORWARD_ACTION = "browser_navigate_forward"

# ---------------------------------------------------------------------------
# R5 ALLOWLIST of read-only-host-safe actions (Agency GH #5151, 2026-09-28 —
# INVERTS the former `_INTERACTION_ACTIONS` denylist-by-name). See the module
# docstring's R5 section for the full rationale; summary: a denylist of
# "interaction" tool names can only ever cover names someone thought to
# enumerate — a future/unknown Playwright MCP tool name (or one this list's
# author simply missed) silently fell through `r5_decision` as "not an
# interaction" and reached R0-R4 unconditionally allowed, since none of these
# tools carry a URL for R0-R4 to gate at all. Inverting to an ALLOWLIST of
# verified read-only-safe actions means an unrecognized name is DENIED
# (treated as an interaction) by construction, never silently passed through.
#
# ENUMERATED AGAINST THE REAL, INSTALLED `@playwright/mcp` 0.0.76 DEPENDENCY
# TREE (`playwright-core@1.61.0-alpha-1781023400000`, the exact version
# `npm view @playwright/mcp@0.0.76` reports as its own dependency — verified
# by reading `packages/playwright-core/src/tools/backend/tools.ts`'s
# `filteredTools()` and every tool module it assembles from, in that
# package's own bundled `coreBundle.js`; NOT guessed, NOT taken from `--help`
# text, which lists CLI flags, not MCP tool names). `filteredTools()` itself
# proves which tools are actually reachable in THIS runtime's pool slots:
# `tool.capability.startsWith("core")` is unconditionally included; every
# other capability (`storage`, `network`, `network-request`/`pdf`/`vision`/
# `devtools`/`testing`/`config`) requires an explicit `--caps` CLI flag that
# `browser_pool.py`'s `_server_entry_numbered` never passes (its args are
# `-y @playwright/mcp@<ver> --isolated --browser chrome --output-dir <dir>
# [--storage-state <jar>]`, nothing else) — so only the 32 `core`/
# `core-input`/`core-navigation`/`core-tabs`-capability tools are ever
# reachable from a pool slot; the other 45 (cookie/localStorage/
# sessionStorage read-write, mouse-by-coordinate "vision" tools, PDF export,
# devtools tracing/video/highlight, `browser_verify_*` testing assertions,
# `browser_get_config`) are structurally unreachable here and are not
# enumerated in either set below — see this change's own dispatch report for
# the full 77-name capability table this classification was built from.
#
# READ-ONLY-HOST-SAFE (this set): never mutates page content or navigates to
# agent-uncontrolled state in a way R5's read-only-host policy needs to gate.
#   * browser_navigate            — R5 never denies this action at all (see
#     module docstring); the host RE-RECORD in `_main_impl` still applies
#     unconditionally regardless of this set's membership.
#   * browser_navigate_back / browser_navigate_forward — page-history
#     navigation only; no page-content mutation the agent directly controls.
#   * browser_snapshot / browser_take_screenshot — pure reads of current
#     page state.
#   * browser_wait_for            — a passive wait (its own real `type` is
#     `"assertion"`, not `"action"`).
#   * browser_console_messages    — reads the console log; does not clear it
#     (`browser_console_clear` is NOT in this set — see below).
#   * browser_network_requests    — reads the network log; does not mutate
#     network state (`browser_network_request`, the SINGULAR detail-lookup
#     tool, is likewise a pure read but is deliberately NOT included below —
#     seen used far less often in practice and narrower to add later with its
#     own review than to include on an assumption; treated as an interaction
#     for now, fail-closed, per this allowlist's own default-deny posture).
#   * browser_close               — closes the page/context; R5 never denies
#     this either way (see `_CLOSE_ACTION` handling in `_main_impl`, which
#     also clears the slot's recorded host), included here so a FUTURE code
#     path that starts consulting this set for `browser_close` fails safe
#     rather than open by omission.
#   * browser_resize              — resizes the browser window; no page-
#     content mutation.
#   * browser_tabs with `tool_input["action"] == "list"` ONLY — this is a
#     SINGLE tool name covering four real operations (`list`/`new`/`close`/
#     `select`, an enum on its OWN `action` field, confirmed in the real
#     schema), so the tool NAME ALONE is ambiguous; `_is_read_only_host_safe_call`
#     below inspects `tool_input` to resolve this, and anything other than a
#     confirmed `"list"` (including a missing/malformed `tool_input`) is
#     treated as an interaction, fail-closed.
_READ_ONLY_HOST_SAFE_ACTIONS = frozenset(
    {
        "browser_navigate",
        "browser_navigate_back",
        "browser_navigate_forward",
        "browser_snapshot",
        "browser_take_screenshot",
        "browser_wait_for",
        "browser_console_messages",
        "browser_network_requests",
        "browser_close",
        "browser_resize",
        "browser_tabs",
    }
)

# The one action whose read-only-safety additionally depends on tool_input
# (see _READ_ONLY_HOST_SAFE_ACTIONS's own comment on browser_tabs above).
_TABS_ACTION = "browser_tabs"
_TABS_SAFE_SUBACTION = "list"
_TABS_NEW_SUBACTION = "new"
# tabs "select" switches the active tab to a DIFFERENT already-open tab,
# which may be on a completely different page than the one this slot's
# recorded host describes — cold round-3 review (2026-09-28) requires this
# to INVALIDATE the slot's recorded host (see `_main_impl`), the same as
# navigate_back/navigate_forward.
_TABS_SELECT_SUBACTION = "select"
# tabs "close" closes the CURRENT tab, after which an ADJACENT already-open
# tab becomes current (round-4 review, 2026-09-28) — exactly the same
# "the slot's recorded host may no longer describe the loaded page" shape as
# "select", so it invalidates the host identically.
_TABS_CLOSE_SUBACTION = "close"


def _tabs_new_url(action: str, tool_input: Optional[dict]) -> str:
    """Return the URL a ``browser_tabs`` ``action: "new"`` call would
    navigate its new tab to, or ``""`` if *action* is not
    ``browser_tabs``/``tool_input`` carries no genuine ``url`` string
    (cold round-3 blocker B1, 2026-09-28).

    THE BUG THIS CLOSES: ``browser_tabs`` is READ-ONLY-HOST-SAFE under GH
    #5151's allowlist only for ``action: "list"``; ``action: "new"`` (with an
    optional ``url`` to open in the new tab) is correctly classified as an
    INTERACTION — but R5's read-only-host check only ever gates the
    INTERACTION on the basis of the SLOT's recorded host, never the URL the
    new tab is actually being pointed at. On a slot whose recorded host is
    NOT itself read-only (or has no host recorded at all, in the allow
    direction that matters here), R5 allows the ``browser_tabs`` interaction
    outright, and ``decide_event`` used to return immediately on any R5
    verdict — so R0-R4 (the off-tenant guard, the admin/Stripe/comms
    denied-pattern check, the origin allowlist) never ran against the
    tab-new URL at all. An off-tenant ``app.otherapp.example/c/othertenant/...``,
    an admin path, or a Stripe endpoint opened via ``browser_tabs new`` was
    silently ALLOWED where the identical URL via any other tool (or via
    ``browser_navigate`` itself) would have been correctly denied by R0-R4.

    Deliberately reads ONLY the literal ``"url"`` key — NEVER
    ``extract_request``'s broader ``_URL_KEYS`` alias set, which includes
    ``"target"``. ``target`` is a REAL, different field on OTHER tools
    (``browser_type``/``browser_click``/etc.'s element-reference/selector
    string — verified against the real, installed ``@playwright/mcp`` 0.0.76
    dependency tree; see this change's own dispatch report for the
    verification trail, since the module-level writeup that originally
    hosted it was removed along with the mechanism it supported) — feeding
    an element ref string into URL parsing here would be a category error,
    not merely imprecise, so this function is deliberately narrower than the
    general-purpose ``_first_str(ti, _URL_KEYS)`` used elsewhere. Pure; never
    raises. Non-dict *tool_input*, a non-``"new"`` sub-action, or a
    non-string/empty ``url`` all return ``""``.
    """
    if action != _TABS_ACTION:
        return ""
    if not isinstance(tool_input, dict):
        return ""
    if tool_input.get("action") != _TABS_NEW_SUBACTION:
        return ""
    url = tool_input.get("url")
    return url if isinstance(url, str) and url else ""


def _is_read_only_host_safe_call(action: str, tool_input: Optional[dict]) -> bool:
    """True iff *action* (with *tool_input*, for the one ambiguous case) is
    classified read-only-host-safe under R5's ALLOWLIST (GH #5151).

    Every action not in ``_READ_ONLY_HOST_SAFE_ACTIONS`` at all is denied by
    construction — an unrecognized/future tool name is NEVER read-only-safe.
    ``browser_tabs`` is the one name in the set requiring an ADDITIONAL
    check: its own ``tool_input["action"]`` must be the string ``"list"``
    exactly, or this returns ``False`` (fail-closed on a missing, malformed,
    or non-``"list"`` sub-action — ``"new"``/``"close"``/``"select"`` all
    mutate the browsing context and must be treated as interactions on a
    read-only host). Pure; never raises.
    """
    if action not in _READ_ONLY_HOST_SAFE_ACTIONS:
        return False
    if action != _TABS_ACTION:
        return True
    return isinstance(tool_input, dict) and tool_input.get("action") == _TABS_SAFE_SUBACTION

# TTL for a recorded slot host: 4 hours (seconds).
_SLOT_HOST_TTL_SECONDS = 4 * 60 * 60


# ---------------------------------------------------------------------------
# R5 session-banner exemption (added 2026-09-28, operator directive: every
# session must mark its own Playwright tabs so a human can tell which
# session controls which slot; hardened 2026-09-28 per trust-architect
# review of the same file — see items below). R5 denies `browser_evaluate`
# outright on a read-only-host slot (see `r5_decision` above) with no way
# for an agent to even write a harmless, cosmetic identification banner onto
# a prod tab. This is a NARROW, single-snippet carve-out, not a loosening of
# R5 itself: it allows exactly ONE canonical, parameterized DOM-injection
# snippet (below) and nothing else — any other statement, any
# DOM/cookie/storage/network read, or any deviation in the two filled-in
# slots (banner text, background color) still denies exactly as before.
#
# THE CANONICAL SNIPPET (single documented home — also reproduced verbatim in
# `live-testing/allowlist_README.md`'s "Session-banner exemption" section;
# never hand-retyped a third time anywhere. An agent fills in <TEXT> and
# <COLOR> and calls `browser_evaluate` with the result as its zero-arg
# `function` argument, with NO other key in the same `tool_input`):
#
#   () => { const id='__session_banner'; document.getElementById(id)?.remove();
#   const b=document.createElement('div'); b.id=id; b.textContent='<TEXT>';
#   b.style.cssText='position:fixed;bottom:0;left:0;right:0;height:28px;
#   max-height:28px;overflow:hidden;background:<COLOR>;color:#fff;
#   padding:4px 8px;z-index:2147483647;font:12px monospace;
#   pointer-events:none;'; document.body.appendChild(b); return true; }
#
# <TEXT> — the session/slot identification label — is restricted to
# `_SESSION_BANNER_TEXT_RE` (alphanumerics, space, and a narrow punctuation
# set; no quote/backslash/backtick, so it can never terminate the JS string
# literal early or inject a new statement).
#
# <COLOR> — the banner's background color, the ONLY part of the inline style
# an agent may vary — is restricted to `_SESSION_BANNER_COLOR_RE` (a bare
# `#rgb`/`#rrggbb` hex triplet only; no `rgba(...)`, no named color, no
# `url(...)`, no function call of any kind — a hex literal cannot itself
# carry CSS injection). Trust-architect finding (2026-09-28): the prior
# design let an agent supply the ENTIRE `cssText` value, gated only by a
# character-class-plus-forbidden-substring check, which (a) never required
# `pointer-events:none` (a click-through banner is essential so the banner
# itself can never intercept or redirect a real interaction on the page
# underneath it — an agent-controlled overlay that DOES receive pointer
# events on a production page is a real UI-redressing/clickjacking-shaped
# risk even in a "cosmetic" feature) and (b) never bounded the banner's
# height/position (an agent-chosen `top`, `inset`, or large `height` value
# could cover arbitrary page content, not just present a slim identification
# strip). The fix is to make the WHOLE `cssText` value a fixed, canonical
# literal — every property except the single `<COLOR>` slot is now baked
# into the scaffold regex itself (`_SESSION_BANNER_RE` below), so there is no
# character class or forbidden-substring list to bypass for any property
# other than the color: `pointer-events:none`, `bottom:0`, and a
# `height:28px` / `max-height:28px` cap are structurally guaranteed, not
# merely encouraged by a character class.
#
# The whole snippet is matched as ONE exact, whitespace-normalized string via
# `_SESSION_BANNER_RE` — the literal scaffold text (including the entire CSS
# block, `<COLOR>` excepted) is matched verbatim (no wildcard gaps anywhere
# except the two named capture groups), so appending a trailing statement
# (`;fetch(...)`), substituting a DOM/cookie/storage read for the literal
# `'<TEXT>'` string, or altering ANY CSS property (not just color) all fail
# the whole-string match outright, before the per-slot TEXT/COLOR
# character-class checks are even consulted.
_SESSION_BANNER_TEXT_RE = re.compile(r"^[A-Za-z0-9 ._()#·:/-]{1,120}$")
# Bare #rgb or #rrggbb hex triplet only -- see the module comment above for
# why a color-only slot (never a full cssText) closes the pointer-events/
# height gap trust-architect found. Case-insensitive on the hex digits.
_SESSION_BANNER_COLOR_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

# The fixed, canonical inline-style literal -- every property is baked into
# the scaffold; ONLY the background color varies (see module comment above).
# Structurally guarantees pointer-events:none (click-through, never
# intercepts a real page interaction) and a bounded 28px strip anchored to
# the viewport bottom (bottom:0, both height and max-height capped at 28px)
# so the banner can never be resized/repositioned to cover arbitrary page
# content. `{color}` is the ONE substitution point -- `_SESSION_BANNER_RE`
# below is BUILT FROM this literal (via `re.escape` + a substituted named
# group for `{color}`) rather than hand-duplicating the CSS string a second
# time in regex form, so the two can never drift out of sync with each other.
_SESSION_BANNER_CSS_LITERAL = (
    "position:fixed;bottom:0;left:0;right:0;height:28px;max-height:28px;"
    "overflow:hidden;background:{color};color:#fff;padding:4px 8px;"
    "z-index:2147483647;font:12px monospace;pointer-events:none;"
)

# Structural scaffold, whitespace-normalized (any run of whitespace in the
# submitted `function` string is collapsed to a single space before this
# regex is applied — see `_normalize_whitespace`, which runs BEFORE this
# regex is matched, so every check below (including the TEXT/COLOR character
# classes applied afterward in `_match_session_banner_snippet`) operates on
# the NORMALIZED string, never the raw submitted text) so cosmetic
# formatting differences (extra spaces, a trailing newline) don't defeat an
# otherwise exact match. `(?P<text>...)` / `(?P<color>...)` are matched
# permissively here (any run of non-quote characters) — the STRICT
# character-class checks run separately, after this structural match
# succeeds, in `_match_session_banner_snippet`. Uses `\Z` (absolute end of
# string) rather than `$` (end of string OR just before a trailing newline)
# so a submitted snippet with a trailing newline that survived
# normalization — it cannot, since `_normalize_whitespace` strips ends, but
# this closes the gap structurally rather than relying on that other
# function's behavior — can never slip past the terminal `}` check.
#
# The CSS portion of this pattern is generated from `_SESSION_BANNER_CSS_LITERAL`
# (escaped, with its one `{color}` substitution point replaced by the
# `(?P<color>[^;']*)` capture group) rather than retyped by hand, so the
# literal and the pattern can never silently diverge.
_SESSION_BANNER_CSS_RE_FRAGMENT = re.escape(
    _SESSION_BANNER_CSS_LITERAL.format(color="\0")
).replace(re.escape("\0"), r"(?P<color>[^;']*)")
_SESSION_BANNER_RE = re.compile(
    r"\A\(\)\s*=>\s*\{\s*"
    r"const\s+id='__session_banner';\s*"
    r"document\.getElementById\(id\)\?\.remove\(\);\s*"
    r"const\s+b=document\.createElement\('div'\);\s*"
    r"b\.id=id;\s*"
    r"b\.textContent='(?P<text>[^']*)';\s*"
    r"b\.style\.cssText='" + _SESSION_BANNER_CSS_RE_FRAGMENT + r"';\s*"
    r"document\.body\.appendChild\(b\);\s*"
    r"return\s+true;\s*"
    r"\}\Z"
)

_WHITESPACE_RUN_RE = re.compile(r"\s+")


def _normalize_whitespace(s: str) -> str:
    """Collapse any run of whitespace in *s* to a single space and strip the
    ends. Pure; never raises on a string input.

    Applied to a submitted `browser_evaluate` `function` string BEFORE the
    session-banner structural match (`_SESSION_BANNER_RE.fullmatch`) runs, so
    an agent's own incidental formatting (extra spaces around an operator, a
    trailing newline) doesn't defeat an otherwise-exact match. Corrected
    2026-09-28 (trust-architect review): an earlier version of this
    docstring claimed the TEXT/COLOR character-class checks run against
    "their own un-normalized captured text" — that was never true: the
    capture groups matched by `_SESSION_BANNER_RE.fullmatch(normalized)` in
    `_match_session_banner_snippet` are substrings OF the already-normalized
    string, so `text`/`color` are themselves normalized (any internal
    whitespace run already collapsed to one space) by the time
    `_SESSION_BANNER_TEXT_RE`/`_SESSION_BANNER_COLOR_RE` see them. This is
    harmless in practice (neither character class treats a single space
    differently from a run of spaces — the TEXT class explicitly permits a
    literal space, and the COLOR class permits none at all, so a
    whitespace-containing color is rejected by the class either way), but
    the docstring's claim about WHERE normalization happens was simply
    wrong and is corrected here rather than left to mislead a future reader.
    """
    return _WHITESPACE_RUN_RE.sub(" ", s).strip()


def _session_banner_color_is_safe(color: str) -> bool:
    """True if *color* is a safe ``<COLOR>`` fill-in for the session banner.

    Requires a bare ``#rgb``/``#rrggbb`` hex triplet
    (`_SESSION_BANNER_COLOR_RE`) — nothing else. Replaces a former free-form
    `cssText` character-class-plus-forbidden-substring check (deleted —
    trust-architect non-blocking finding, 2026-09-28) now that the entire
    inline style is a fixed literal (`_SESSION_BANNER_CSS_LITERAL`) with
    color as its only variable — a hex triplet cannot itself carry a CSS
    function call, a `url(...)` reference, or any other injection shape, so
    there is no forbidden-substring list to maintain for this slot at all.
    """
    return bool(_SESSION_BANNER_COLOR_RE.match(color))


def _match_session_banner_snippet(function_src: object) -> bool:
    """True if *function_src* is EXACTLY the canonical session-banner
    snippet (see the module-level block above this function) with a
    conforming `<TEXT>` and `<COLOR>` fill-in. False for anything else,
    including the canonical snippet plus any extra statement, any
    DOM/cookie/storage/network read substituted into either slot, any
    alteration to the fixed CSS properties (`pointer-events:none`,
    `bottom:0`, the height cap, etc. — only `<COLOR>` is a free slot), or a
    filled-in slot that violates its own character-class rule. Pure; never
    raises. Non-string input is False.

    Uses ``fullmatch`` (trust-architect finding, 2026-09-28) rather than
    ``match`` — the pattern itself is already anchored with `\\A`/`\\Z`
    (belt-and-suspenders against a future edit that loosens the anchors
    without noticing `match` no longer enforces the tail), but `fullmatch`
    is the correct API for "the ENTIRE string must match", not `match` with
    manually-authored anchors.
    """
    if not isinstance(function_src, str) or not function_src:
        return False
    normalized = _normalize_whitespace(function_src)
    m = _SESSION_BANNER_RE.fullmatch(normalized)
    if not m:
        return False
    text = m.group("text")
    color = m.group("color")
    if not _SESSION_BANNER_TEXT_RE.match(text):
        return False
    return _session_banner_color_is_safe(color)


# ---------------------------------------------------------------------------
# Allowlist loader (fail-closed on any error -> empty dict -> deny-all).
# ---------------------------------------------------------------------------


def load_allowlist() -> dict:
    """Load ``allowlist.json``; return {} on any read/parse error (fail-closed).

    An unreadable policy denies everything rather than opening the lane.
    """
    try:
        with open(_allowlist_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Actions audit log — append-only JSONL, best-effort (never raises).
# ---------------------------------------------------------------------------


def log_action(method: str, url: str, allow: bool, reason: str) -> None:
    """Append one decision line to ``prod_actions.jsonl`` (append-only, 0600).

    Best-effort: logging must never raise into the decision path.
    """
    path = _actions_log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
        entry = {
            "ts": time.time(),
            "method": method,
            "url": url,
            "allow": allow,
            "reason": reason,
        }
        line = json.dumps(entry, sort_keys=True) + "\n"
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        fd = os.open(path, flags, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# R5 state I/O — per-slot last-navigated host, atomic write, fail-closed on
# any read error (a missing/corrupt file reads back as "no host recorded").
# ---------------------------------------------------------------------------


def read_slot_hosts() -> dict:
    """Load ``slot_hosts.json``; return {} on any read/parse error.

    A missing or corrupt state file is treated identically to "no slot has a
    recorded host" — R5's own fail-closed default (deny when no host is
    recorded) means this degrades to the safe outcome, never an open one.
    """
    try:
        with open(slot_hosts_path(), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_slot_hosts(data: dict) -> None:
    """Atomically write ``slot_hosts.json`` (mode 0600). Best-effort.

    Uses a tmp-file + os.replace so a concurrent reader (another PreToolUse
    invocation, possibly a different session) never observes a partially
    written file — same discipline as ``browser_pool.atomic_write_json``.
    Never raises: a write failure here must not break the decision path.

    Two concurrent writers can still lose an update (this is a plain
    read-modify-write, not a locked read-modify-write): a lost update
    degrades to R5's own fail-closed deny (no host, or a stale host,
    recorded for the clobbered slot), recovered by one ``browser_navigate`` —
    a lock is deliberately not taken here because that failure mode is safe
    (m6, 2026-09-10 review).
    """
    path = slot_hosts_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True, mode=0o700)
        tmp = f"{path}.tmp.{os.getpid()}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        fd = os.open(tmp, flags, 0o600)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, sort_keys=True)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            return
        os.replace(tmp, path)
    except OSError:
        pass


def record_navigate_host(slot: str, url: str) -> None:
    """Record *slot*'s newly-navigated (host, path), keyed by slot name.

    Called by ``_main_impl`` ONLY AFTER ``decide_event`` has ALLOWED a
    ``browser_navigate``, or a ``browser_tabs action:"new"`` call that
    carries a ``url`` (cold round-3 blocker B1, 2026-09-28 — see
    ``_tabs_new_url``'s own docstring), which establishes a new page exactly
    like a real navigate does. Recording AFTER the decision (cold round-4
    blocker B1, 2026-09-28 — corrected from the original "record before
    deciding" placement) means a DENIED navigate/tabs-new never overwrites
    the slot's host with the denied destination — see ``_main_impl``'s own
    comment block for the full defect this closes. Overwrites any prior HOST
    entry for the same slot; an in-page SPA route change with no new
    ``browser_navigate``/``browser_tabs new`` call leaves the host record
    untouched (host-level tracking is the point, not route-level).

    PATH IS NOW ALSO RECORDED (2026-09-29, cold review HIGH #3/B2 hardening —
    NOT yet approved by any review; see the module docstring's own section
    above ``_interactive_host_config`` for the two-round rejection history):
    ``interactive_production_hosts`` (see ``r5_decision``'s own section)
    grants interaction on an otherwise-read-only host only for a specific
    tenant's allowlisted path — this requires knowing not just the
    HOST but the PATH the slot actually navigated to. The path is
    canonicalized via ``_canonical_origin_and_path`` (the SAME WHATWG-
    consistent canonicalizer R0-R4 already use for host/path matching,
    fix-round-6 through fix-round-15) rather than a fresh ad-hoc parse, so
    this never disagrees with what R0-R4 already decided about the same URL.
    An unparseable URL records an empty path (``""``), which
    ``_extract_tenant_from_path`` and the interactive-host gate both treat as
    "no tenant" — fail-closed, never a guess.

    Best-effort; a write failure here degrades to "no host/path recorded" on
    the NEXT read, which is R5's own fail-closed default, never a crash.
    """
    host = _normalize_host(_host_of(url))
    if not slot or not host:
        return
    canon = _canonical_origin_and_path(url)
    path = canon[1] if canon is not None else ""
    data = read_slot_hosts()
    data[slot] = {"host": host, "path": path, "ts": time.time()}
    _write_slot_hosts(data)


def clear_slot_host(slot: str) -> None:
    """Remove *slot*'s recorded host entry, if any. Best-effort, never raises.

    Called on a delivered ``browser_close`` event (see docstring PROBE
    RESULT) and by ``browser_pool.py``'s ``cmd_release`` (its own test) so a
    freshly (re)claimed slot never inherits a stale host recorded by a prior
    lease-holder.
    """
    data = read_slot_hosts()
    if slot in data:
        del data[slot]
        _write_slot_hosts(data)


def clear_slot_path(slot: str) -> None:
    """Remove *slot*'s recorded PATH (keeping its HOST/``ts``), if any.

    2026-09-29, cold review B3/B2 hardening — the FALLBACK mechanism for
    "refresh the recorded path after every interaction": ``@playwright/mcp``
    0.0.76's own tool responses DO include the live page URL in their result
    TEXT (``- Page URL: <url>``, confirmed live in
    ``playwright-core/lib/coreBundle.js``'s ``renderTabMarkdown``) and a
    ``PostToolUse`` hook CAN read that text (confirmed by this runtime's own
    ``redact_browser_phi.py``, which already parses a ``tool_response``
    envelope) — but a ``PostToolUse`` hook in this runtime NEVER blocks
    (every one, including ``redact_browser_phi.py`` and
    ``posttooluse_bash.py``, always exits 0; there is no
    ``emit_pretooluse_deny``-equivalent for ``PostToolUse``). By the time a
    ``PostToolUse`` refresh could run, the interaction it would be
    "correcting" has ALREADY executed — so refreshing there can only narrow
    the NEXT call's exposure, never gate the call that just happened. That
    makes a same-call, page-URL-based re-check structurally unavailable, not
    merely unbuilt.

    THE FALLBACK (what actually gates): after ANY interaction-class call is
    ALLOWED under ``interactive_production_hosts`` (see ``r5_decision`` and
    ``_main_impl``'s own call site), the slot's recorded PATH is cleared
    immediately — the HOST stays (the browser is still on the same host), so
    a subsequent read-only-safe call (``browser_snapshot`` etc.) is
    unaffected, but the NEXT interaction-class call has no path to extract a
    tenant from (``_extract_tenant_from_path("")`` returns ``""``) and is
    therefore denied fail-closed, forcing a fresh ``browser_navigate`` before
    any further interaction. This bounds a click-triggered SPA navigation (or
    a redirect) to AT MOST one interaction on the page it silently landed on,
    down from "every subsequent interaction on this slot until the next
    explicit navigate" — the SAME class of residual R5's own module
    docstring already accepts at the host level (a cross-origin
    navigation-by-click is not detected without a fresh navigate); this
    closes it one level tighter, at the path level, for interactive hosts
    specifically, but does not eliminate it: a single click that ALSO
    happens to land the page on a DIFFERENT in-tenant, non-denied path is not
    itself caught (only the NEXT interaction after it is gated, by requiring
    a fresh navigate) — see ``allowlist_README.md``'s
    ``interactive_production_hosts`` section for the documented residual in
    full.

    Best-effort; a write failure here degrades to "no path recorded" on the
    next read, which is the fail-closed direction, never a crash. Safe to
    call on a slot with no entry at all (no-op).
    """
    data = read_slot_hosts()
    entry = data.get(slot)
    if isinstance(entry, dict) and "path" in entry:
        entry = dict(entry)
        entry["path"] = ""
        data[slot] = entry
        _write_slot_hosts(data)


def _parse_playwright_tool(tool_name: str) -> Tuple[str, str]:
    """Split a Playwright MCP tool name into (slot, action); ("", "") if it
    doesn't match the ``mcp__<slot>__<action>`` shape. Pure; never raises.
    """
    if not isinstance(tool_name, str):
        return "", ""
    m = _PLAYWRIGHT_TOOL_RE.match(tool_name)
    if not m:
        return "", ""
    return m.group(1), m.group(2)


def _slot_host_is_fresh(record: object, now: float) -> Optional[str]:
    """Return the recorded host string if *record* is a well-formed, non-
    expired entry; None otherwise (missing, malformed, or TTL-expired — both
    treated identically to "no host recorded" per R5's fail-closed default).
    The returned host is normalized (B1) so a state-file entry written by an
    OLDER, pre-normalization version of this module (e.g. a stored
    trailing-dot or mixed-case host) still compares correctly against a
    normalized ``read_only_hosts`` entry. Pure; never raises.
    """
    if not isinstance(record, dict):
        return None
    host = record.get("host")
    ts = record.get("ts")
    if not isinstance(host, str) or not host:
        return None
    if not isinstance(ts, (int, float)):
        return None
    if now - ts > _SLOT_HOST_TTL_SECONDS:
        return None
    normalized = _normalize_host(host)
    return normalized or None


def _slot_record_is_fresh(record: object, now: float) -> Optional[Tuple[str, str]]:
    """Return ``(host, path)`` if *record* is a well-formed, non-expired
    entry; ``None`` otherwise. Same freshness/shape rules as
    ``_slot_host_is_fresh`` (missing, malformed, or TTL-expired all read as
    "nothing recorded" — fail-closed), extended to also surface ``path``.

    ``path`` defaults to ``""`` for a record written before this field
    existed (a pre-2026-09-29 state-file entry carrying only ``host``/``ts``)
    — this is treated by every caller as "no path recorded", which is itself
    fail-closed for the interactive-host gate (see ``r5_decision``): an old
    entry with no path never grants interaction on a host newly added to
    ``interactive_production_hosts`` until a fresh ``browser_navigate``
    records a real path. Pure; never raises.
    """
    if not isinstance(record, dict):
        return None
    host = record.get("host")
    ts = record.get("ts")
    if not isinstance(host, str) or not host:
        return None
    if not isinstance(ts, (int, float)):
        return None
    if now - ts > _SLOT_HOST_TTL_SECONDS:
        return None
    normalized = _normalize_host(host)
    if not normalized:
        return None
    path = record.get("path")
    if not isinstance(path, str):
        path = ""
    return normalized, path


# Extracts the tenant segment immediately after "/c/" -- the ONLY tenant-path
# shape `interactive_production_hosts` recognizes (coordinator's own spec:
# "tenant = the segment after /c/"). Deliberately narrower than R2's own
# `_TENANT_URL_PATTERNS` (which also matches `/company/`, `/companies/`,
# `/tenant(s)/` for the OFF-TENANT guard's broader purpose) -- granting
# INTERACTION is a strictly higher-stakes operation than R2's read-vs-write
# tenant check, so this gate recognizes only the one real SPA route shape
# (`/c/:slug`, see agency/src/App.jsx) actually used for the Company
# Coordinator app, never a speculative alias.
_INTERACTIVE_TENANT_PATH_RE = re.compile(r"^/c/([A-Za-z0-9_-]+)(?:/|$)")


def _extract_tenant_from_path(path: str) -> str:
    """Return the lowercase tenant slug immediately after ``/c/`` in *path*,
    or ``""`` if *path* does not match that shape at all. Pure; never raises.

    Only ever consulted by the ``interactive_production_hosts`` gate (see
    ``r5_decision``) -- an empty return is fail-closed there (no tenant means
    no interactive-host match, which falls through to the ordinary
    read-only-host deny).
    """
    if not isinstance(path, str) or not path:
        return ""
    m = _INTERACTIVE_TENANT_PATH_RE.match(path)
    if not m:
        return ""
    return m.group(1).lower()


def _path_under_any_prefix(path: str, prefixes) -> bool:
    """True iff *path* is exactly one of *prefixes*, or a sub-path of one
    (``/developer`` matches ``/developer`` and ``/developer/settings`` but
    never ``/developer-extra``). Case-insensitive (paths here are already
    lowercased by ``_canonical_origin_and_path``, but this is defensive).
    Pure; never raises. A malformed (non-iterable, non-string-entry)
    *prefixes* is treated as containing no prefixes at all -- the caller's
    own fail-closed default (deny) is what actually protects a path in that
    case, not this helper silently matching everything.

    Used by the ``interactive_production_hosts`` ALLOWLIST (2026-09-29 cold
    review, HIGH #3 — see ``_path_is_allowed``) only for a config that
    explicitly opts a whole sub-tree in via ``allowed_path_prefixes``; the
    real, checked-in config for ``app.otherapp.example`` uses none today (every
    route it opens is a single leaf page, exact-matched via
    ``allowed_paths``) but the mechanism stays general for a future need.
    """
    if not isinstance(path, str) or not path:
        return False
    try:
        prefix_list = [p for p in prefixes if isinstance(p, str) and p]
    except TypeError:
        return False
    p = path.lower()
    for prefix in prefix_list:
        pref = prefix.lower().rstrip("/")
        if not pref:
            continue
        if p == pref or p.startswith(pref + "/"):
            return True
    return False


def _path_matches_exactly(path: str, exact_paths) -> bool:
    """True iff *path* is EXACTLY (never a sub-path of) one of *exact_paths*.

    THE PRIMARY MATCH MODE for ``interactive_production_hosts`` (2026-09-29
    cold review, HIGH #3 — rebuilt from a denylist to an ALLOWLIST: a page is
    interactive only if its path is named here). Case-insensitive, trailing
    slash normalized (``/c/othercompany/team/ada`` and
    ``/c/othercompany/team/ada/`` are the same path). Pure; never raises. A
    malformed (non-iterable, non-string-entry) *exact_paths* is treated as
    containing no paths at all — fail-closed (nothing is allowed), never a
    crash and never "everything matches."
    """
    if not isinstance(path, str) or not path:
        return False
    try:
        exact_list = [p for p in exact_paths if isinstance(p, str) and p]
    except TypeError:
        return False
    p = path.lower().rstrip("/") or "/"
    return any(p == e.lower().rstrip("/") or (p == "/" and e.lower().rstrip("/") == "") for e in exact_list)


def _path_is_allowed(path: str, cfg: dict) -> bool:
    """True iff *path* is explicitly opted in by *cfg* — an EXACT match in
    ``cfg["allowed_paths"]`` OR a prefix match in
    ``cfg["allowed_path_prefixes"]`` (2026-09-29 cold review, HIGH #3: "a
    substring/prefix DENYLIST cannot secure a whole app's route surface;
    replace it with an ALLOWLIST of exact paths, plus a prefix only where
    needed"). Everything NOT named here denies by default — this is the
    single fail-closed gate for every route this module does not
    specifically recognize, including the bare ``/c/:slug/team`` redirect,
    every ``/settings/*`` page, integrations, staff, and access-requests.
    Malformed or absent config keys degrade to an empty list (no match),
    never a crash and never an implicit allow. Pure; never raises.
    """
    if not isinstance(cfg, dict):
        return False
    exact = cfg.get("allowed_paths")
    if _path_matches_exactly(path, exact if isinstance(exact, list) else []):
        return True
    prefixes = cfg.get("allowed_path_prefixes")
    return _path_under_any_prefix(path, prefixes if isinstance(prefixes, list) else [])


def _interactive_host_config(allowlist: dict, host: str) -> Optional[dict]:
    """Return the ``interactive_production_hosts[host]`` config dict for
    *host*, or ``None`` if the key is absent, malformed, or has no entry for
    this host. Pure; never raises.

    Defensively validated the same way ``read_only_hosts`` is (B2 lineage):
    a non-dict top-level value, or a non-dict per-host value, is treated as
    "no interactive config for this host" -- the caller's ordinary
    read-only-host deny is the fail-closed backstop, never a crash and never
    a silent allow-everything on a malformed config.
    """
    raw = allowlist.get("interactive_production_hosts")
    if not isinstance(raw, dict):
        return None
    cfg = raw.get(host)
    if not isinstance(cfg, dict):
        return None
    return cfg


# Actions NEVER granted interaction by `interactive_production_hosts`,
# regardless of tenant/path -- B1/MEDIUM #4 hardening (2026-09-28/29 rounds).
#   * `browser_run_code_unsafe` — arbitrary Node-context code execution, not
#     sandboxed to the page the way `browser_evaluate`'s `function` argument
#     is; already denied on every OTHER read-only host by construction (not a
#     member of `_READ_ONLY_HOST_SAFE_ACTIONS`), this closes the same gap for
#     a host this key would otherwise open.
#   * `browser_file_upload` (MEDIUM #4, 2026-09-29 cold review) — sets a real
#     OS file-picker's selection; on an authenticated PHI-adjacent page this
#     is a live upload path this hook has no way to inspect the CONTENT of
#     before it leaves the agent's control.
#   * `browser_drag` (MEDIUM #4) — drag-and-drop can itself be a file-upload
#     surface (many upload widgets accept a dropped file with no separate
#     file-picker dialog at all) and is otherwise a broad, hard-to-audit
#     interaction; denied outright rather than assumed safe.
_NEVER_INTERACTIVE_ACTIONS = frozenset(
    {"browser_run_code_unsafe", "browser_file_upload", "browser_drag"}
)


def r5_decision(
    tool_name: str,
    slot_hosts: dict,
    allowlist: dict,
    now: Optional[float] = None,
    tool_input: Optional[dict] = None,
) -> Optional[Tuple[bool, str, bool]]:
    """R5's PURE decision. No I/O — *slot_hosts* is handed in by the caller.

    Returns None when R5 has no opinion — the tool name doesn't even parse as
    a Playwright call (``_parse_playwright_tool`` fails), OR it parses AND is
    classified READ-ONLY-HOST-SAFE (GH #5151 — ``_is_read_only_host_safe_call``,
    an ALLOWLIST of verified-safe action names, inverted from the former
    ``_INTERACTION_ACTIONS`` denylist). Returns ``(allow, reason,
    path_consumed)`` for EVERY OTHER Playwright call — this is now a
    default-deny-to-R5's-opinion
    classification: an unrecognized/future tool name is NOT read-only-safe by
    construction, so it falls into this branch and is treated as an
    interaction, never silently passed through unclassified the way a
    denylist-by-name would. An interaction-class tool is denied when the
    slot's recorded, non-expired host is listed in ``read_only_hosts``, or
    when no such host is recorded at all (fail-closed — see module
    docstring). ``now`` defaults to ``time.time()``; a caller may pass an
    explicit value for deterministic TTL tests.

    ``path_consumed`` (LOW #5, 2026-09-29 cold review — replaces an earlier
    round's reason-STRING matching, e.g. ``"interactive_production_hosts
    interaction" in reason``, which coupled a real decision to a human-
    readable message never meant to be machine-parsed): ``True`` iff this
    ALLOW came from the ``interactive_production_hosts`` tenant/path
    allowlist branch specifically — the ONE case where the caller
    (``_main_impl``) must consume the slot's recorded PATH afterward (see
    ``clear_slot_path``) so the next interaction requires a fresh
    ``browser_navigate``. ``False`` for every other outcome, including the
    session-banner exemption's own allow (writing the banner does not
    "spend" a navigated path — an agent may write it once, then still
    interact with the page it describes) and every deny.

    SESSION-BANNER EXEMPTION (added 2026-09-28, operator directive — see the
    block above ``_SESSION_BANNER_RE``): when *action* is exactly
    ``browser_evaluate`` and *tool_input*'s key set is a SUBSET of
    ``{"function"}`` (an allowlist — any other key at all, recognized or
    not, fails this check; see ``_is_exempt_session_banner_call``'s own
    docstring for why this is an allowlist rather than a denylist of
    ``target``/``element``/``ref``) carrying a ``function`` argument that is
    a byte-exact (whitespace-normalized) match for the canonical
    session-banner snippet with a conforming TEXT/COLOR fill-in, R5 allows it
    even when the recorded host is read-only. This exemption fires ONLY in
    the read-only-host deny branch below, never the no-recorded-host branch
    above it — writing an identification banner still requires a real
    navigated page; it does not relax the fail-closed "no host recorded"
    default. Not applicable to any tool but ``browser_evaluate`` — that tool
    is never assumed to take the same ``{function}`` argument shape, so it
    gets no exemption regardless of its payload (see
    ``_is_exempt_session_banner_call``'s own docstring).

    ``read_only_hosts`` is defensively validated (B2, 2026-09-10): a
    malformed policy value (anything other than a list — e.g. ``null`` from a
    hand-edited allowlist, or a bare string) is treated as a MALFORMED POLICY
    and R5 DENIES every interaction-class call outright, fail-closed,
    mirroring ``load_allowlist``'s own deny-all precedent for an unreadable
    allowlist file. A well-formed list containing non-string entries simply
    ignores those entries rather than failing the whole policy. Every
    surviving entry (and the recorded host it's compared against) is run
    through ``_normalize_host`` (B1) so case/trailing-dot differences never
    cause a false allow.

    ``allowlist`` itself is ALSO checked for "unreadable/incomplete" (m1,
    2026-09-10 review): an empty dict (``load_allowlist()``'s own fail-closed
    return for an unreadable/corrupt/missing policy file — see its
    docstring) or a dict that never had a ``"read_only_hosts"`` key written
    at all denies every interaction-class call outright, for the identical
    reason R0-R4 already deny-all on the same input — R5 must not be the one
    rule that fails OPEN when every other rule fails CLOSED. An explicitly
    present ``"read_only_hosts": []`` is a *valid*, deliberate "nothing is
    read-only" policy and is NOT this branch — it is a well-formed empty
    list, handled by the normal (non-malformed) path below exactly like any
    other well-formed list.

    RETIRED MECHANISM, SUPERSEDED (2026-09-28 retirement; 2026-09-29
    ``interactive_production_hosts`` supersedes it): an "interactive-path-
    prefix" exemption briefly extended this branch — scoped to
    ``browser_type``, gated by a per-slot arm file a matching
    ``browser_navigate`` would set — to let an agent send one chat message
    to othercompany's Ada assistant on an otherwise read-only production host.
    It was REMOVED entirely on 2026-09-28 (arm files, the arming/consume
    state machine, its allowlist key, its tests, and its docs): the
    analytics need it served (OtherApp #135) was met another way, and the
    mechanism's own residual risk (documented in its own removal-time
    review) was judged not worth carrying.

    ``interactive_production_hosts`` (2026-09-29; REJECTED once by a cold
    review, rebuilt per its two blockers and four other findings, NOT yet
    re-approved by any review — see the block above
    ``_interactive_host_config`` for the schema and the full rejection
    history) is a DIFFERENT, more general mechanism that happens to cover the
    same shape of need the retired exemption served, and is NOT a revival of
    the retired arm-file mechanism itself (no per-slot arming, no
    consume-on-use state, no ``browser_type``-only scoping): a read-only host
    listed as a KEY in this allowlist dict is re-opened for interaction —
    except ``browser_run_code_unsafe``/``browser_file_upload``/
    ``browser_drag``, always denied (B1/MEDIUM #4), and every
    ``browser_evaluate`` OTHER than the exact session-banner snippet, always
    denied (B1: a source denylist cannot secure arbitrary JS — see
    ``_NEVER_INTERACTIVE_ACTIONS``'s own comment and the ``browser_evaluate``
    branch below) — scoped to a listed tenant AND a path the config
    explicitly ALLOWLISTS (``_path_is_allowed`` — HIGH #3: a denylist of
    sensitive routes was rejected because it fails open on every route
    nobody thought to enumerate; the tenant and path are both read from the
    slot's own RECORDED navigate state, never from the current call's
    arguments). This check fires ONLY once the host is already confirmed
    read-only (the branch above) and ONLY after the session-banner exemption
    has already been checked and missed. A host with NO entry in
    ``interactive_production_hosts`` behaves exactly as before this change
    (plain read-only deny, no exemption). See ``allowlist_README.md``'s
    ``interactive_production_hosts`` section for the schema, the derived
    Agency route list, and the documented residuals (a mid-interaction
    cross-origin/cross-route navigation-by-click is not detected without a
    fresh ``browser_navigate`` — the SAME class of residual R5's own module
    docstring already documents for the host-level case, now also true at
    the path level; and the approvals-panel server-side-control residual —
    see the README section for both in full).
    """
    slot, action = _parse_playwright_tool(tool_name)
    if not slot or _is_read_only_host_safe_call(action, tool_input):
        return None
    if now is None:
        now = time.time()
    if not allowlist or "read_only_hosts" not in allowlist:
        return False, (
            f"deny: R5 interaction {action!r} on slot {slot!r}: "
            "R5 unreadable/incomplete policy (fail-closed)"
        ), False
    raw_read_only_hosts = allowlist.get("read_only_hosts", [])
    if not isinstance(raw_read_only_hosts, list):
        return False, (
            f"deny: R5 interaction {action!r} on slot {slot!r}: "
            "R5 malformed read_only_hosts (fail-closed)"
        ), False
    read_only_hosts = {_normalize_host(h) for h in raw_read_only_hosts if isinstance(h, str)}
    record = slot_hosts.get(slot) if isinstance(slot_hosts, dict) else None
    fresh = _slot_record_is_fresh(record, now)
    if fresh is None:
        return False, (
            f"deny: R5 interaction {action!r} on slot {slot!r} with no recorded "
            "navigate host (fail-closed)"
        ), False
    host, path = fresh
    if host in read_only_hosts:
        if _is_exempt_session_banner_call(action, tool_input):
            return True, (
                f"allow: R5 session-banner interaction {action!r} on slot {slot!r} "
                f"host {host!r} (read-only, exempt canonical banner snippet)"
            ), False
        # interactive_production_hosts (2026-09-29, cold review rebuild after
        # a REJECTED first attempt — see the module docstring's dedicated
        # section above _interactive_host_config for the full history): a
        # read-only host MAY be narrowly re-opened for interaction, scoped to
        # a listed tenant AND an explicitly ALLOWLISTED path
        # (`_path_is_allowed` — HIGH #3: a denylist of sensitive routes was
        # rejected because it fails open on every route nobody thought to
        # enumerate; an allowlist of the few routes actually needed fails
        # closed on everything else by construction). This is consulted ONLY
        # here (the host is genuinely read-only) — it never widens anything
        # for a host that is NOT in read_only_hosts at all, and it NEVER
        # re-opens `browser_run_code_unsafe`/`browser_file_upload`/
        # `browser_drag` (B1/MEDIUM #4: always denied on an interactive host)
        # or ANY `browser_evaluate` other than the exact session-banner
        # snippet already checked above (B1: a substring/pattern denylist
        # cannot secure arbitrary JS — verified bypasses included
        # `window['fe'+'tch']`, `atob`, `new Image().src`,
        # `requestSubmit()`, `a.click()`, `history.pushState` — so
        # `browser_evaluate` on an interactive host is now allow-only-the-
        # banner, never a scanned-and-otherwise-allowed general case).
        cfg = _interactive_host_config(allowlist, host)
        if cfg is not None:
            if action in _NEVER_INTERACTIVE_ACTIONS:
                return False, (
                    f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} "
                    "is never permitted on an interactive_production_hosts entry "
                    "(B1/MEDIUM #4 hardening)"
                ), False
            if action == "browser_evaluate":
                # Already known NOT the session-banner exemption (checked
                # above and missed) — B1: no scan-and-allow path exists for
                # ANY other browser_evaluate call on an interactive host.
                return False, (
                    f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} "
                    "is not the exact session-banner snippet -- every other "
                    "browser_evaluate is denied on an interactive_production_hosts "
                    "entry (B1 hardening: a source denylist cannot secure "
                    "arbitrary JS)"
                ), False
            tenant = _extract_tenant_from_path(path)
            raw_tenants = cfg.get("tenants")
            tenants = {
                t.lower() for t in raw_tenants if isinstance(t, str)
            } if isinstance(raw_tenants, list) else set()
            if not tenant:
                return False, (
                    f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} "
                    f"recorded path {path!r} carries no recognized /c/<tenant> "
                    "segment (interactive_production_hosts fail-closed)"
                ), False
            if tenant not in tenants:
                return False, (
                    f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} "
                    f"tenant {tenant!r} not in interactive_production_hosts tenants"
                ), False
            if not _path_is_allowed(path, cfg):
                return False, (
                    f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} "
                    f"path {path!r} is not in interactive_production_hosts' "
                    "allowlist (HIGH #3: deny-by-default on every path not "
                    "explicitly named)"
                ), False
            return True, (
                f"allow: R5 interactive_production_hosts interaction {action!r} on slot "
                f"{slot!r} host {host!r} tenant {tenant!r} path {path!r}"
            ), True
        return False, f"deny: R5 interaction {action!r} on slot {slot!r} host {host!r} is read-only", False
    return True, f"allow: R5 interaction {action!r} on slot {slot!r} host {host!r} not read-only", False


# The ONLY key set a zero-arg, page-global `browser_evaluate` call is allowed
# to carry for the session-banner exemption. Trust-architect finding
# (2026-09-28 review): the prior check denylisted `target`/`element`/`ref`
# specifically, so an UNRECOGNIZED key (e.g. `filename`, or any future MCP
# Playwright option this module doesn't yet know about) passed the check
# silently — a denylist can only ever cover the keys someone thought to name.
# Checking `set(tool_input) <= _SESSION_BANNER_ALLOWED_KEYS` instead is an
# ALLOWLIST: any key at all beyond `function` fails closed, not just the
# three this module happened to enumerate.
_SESSION_BANNER_ALLOWED_KEYS = frozenset({"function"})


def _is_exempt_session_banner_call(action: str, tool_input: Optional[dict]) -> bool:
    """True iff this call is the narrow, exempted session-banner snippet.

    Requires ALL of: *action* is exactly ``browser_evaluate`` (never
    ``browser_run_code_unsafe`` — this exemption is scoped to
    ``browser_evaluate``'s own ``{function}`` argument shape only; a
    different, broader tool is never assumed to take the same shape, so it
    gets no exemption regardless of its payload); *tool_input* is a dict
    whose key set is a SUBSET of ``_SESSION_BANNER_ALLOWED_KEYS`` (an
    ALLOWLIST, not a denylist of known target-scoping keys — any additional
    key at all, recognized or not, fails this check); and its ``function``
    argument is an exact (whitespace-normalized) match for the canonical
    session-banner snippet with a conforming TEXT/CSS fill-in
    (`_match_session_banner_snippet`). Pure; never raises. Any
    malformed/missing input is simply not exempt (returns False), which lets
    the caller's existing fail-closed deny stand.
    """
    if action != "browser_evaluate":
        return False
    if not isinstance(tool_input, dict):
        return False
    if not set(tool_input) <= _SESSION_BANNER_ALLOWED_KEYS:
        return False
    function_src = tool_input.get("function")
    return _match_session_banner_snippet(function_src)


# ---------------------------------------------------------------------------
# WHATWG pre-normalization (fix-round-7, 2026-09-11) — THE CLASS FIX.
#
# Every prior round (3 through 6) patched ONE axis of a single, recurring
# mechanism: this hook decides using Python's ``urllib.parse.urlsplit``
# (an RFC-3986-ish parser), while the request is actually issued and ROUTED
# by a WHATWG/Chromium URL parser (the real browser, and the admin-staging
# container's own ``new URL(...)`` request parsing) — and the two parsers
# disagree on inputs neither one rejects outright. Six relocations so far:
# host case, default port, path dot-segments, an encoded slash (%2f),
# a non-default port, and now a backslash. Patching backslash alone would
# guarantee a seventh.
#
# THE GOVERNING INVARIANT (stated once, applied everywhere ``policy_decision``
# reads a URL's host or path): for every URL this hook evaluates, its notion
# of (host, path) must agree with the browser's — and where it cannot be
# SURE the two agree, it denies rather than guesses.
#
# Because no WHATWG-conformant parser is importable here without adding a
# pip dependency to a security hook (checked: this Python build's stdlib
# exposes only ``urllib.parse``, which is not WHATWG; no vendored WHATWG
# helper exists anywhere under ``~/.claude/hooks`` or ``~/.claude/live-testing``
# — see this round's Prior-art note in the fix-round-7 changelog entry in
# ``allowlist_README.md``), this hook instead PRE-NORMALIZES the raw URL
# STRING to WHATWG rules before ``urlsplit`` ever sees it. Each rule below is
# named, cited against what WHATWG actually specifies (the URL Standard,
# https://url.spec.whatwg.org/), cross-checked against Node's real ``URL``
# parser (the fixture regenerated by ``tests/whatwg_url_fixture.py`` --
# https://url.spec.whatwg.org/, cross-checked live against Node's real
# ``URL`` parser via ``tests/whatwg_url_fixture.py``), and separately unit-
# tested in ``tests/test_block_prod_mutations.py``.
# ---------------------------------------------------------------------------

# Schemes for which the WHATWG URL Standard's "basic URL parser" treats a
# backslash ('\') identically to a forward slash ('/') as a path/authority
# separator (https://url.spec.whatwg.org/#special-scheme -- the "special
# scheme" table). Python's urlsplit NEVER does this for any scheme -- a
# backslash is just an ordinary path character to it, so a backslash-heavy
# URL that a real browser would treat as multiple path segments (or route
# the authority/path boundary through) instead gets swallowed into whatever
# component urlsplit happens to be parsing when it hits the backslash
# (usually netloc, since urlsplit's authority-matching regex does not stop
# at '\'). Every scheme this hook's policy ever allowlists or denies is one
# of these five, so restricting the swap to them (rather than applying it
# unconditionally) matches WHATWG's own scheme-conditioned behavior exactly.
_WHATWG_SPECIAL_SCHEMES = frozenset({"http", "https", "ws", "wss", "ftp", "file"})

# C0 control range (0x00-0x1F) plus the ASCII space (0x20). WHATWG's URL
# parser strips any LEADING or TRAILING run of these code points from the
# input before parsing begins (https://url.spec.whatwg.org/#url-parsing,
# step 1: "Remove any leading and trailing C0 control or space from input").
# Python's urlsplit does NOT do this for trailing characters -- a trailing
# space (or a trailing DEL/other C0) survives into the parsed path verbatim
# (verified: urlsplit("https://h/api/x   ").path == "/api/x   ", not
# "/api/x") -- so a denied-pattern glob written without a trailing-space
# variant silently misses a request whose real (WHATWG-parsed) path the
# server would still route to the denied endpoint.
_C0_OR_SPACE = "".join(chr(c) for c in range(0x00, 0x21))

# WHATWG additionally strips ALL tab (0x09) and newline (0x0A, 0x0D)
# characters from EVERYWHERE in the input, not just the ends
# (https://url.spec.whatwg.org/#url-parsing, step 2: "Remove all ASCII tab
# or newline from input"). Python's urlsplit already coincidentally strips
# these (CPython's own ``_UNSAFE_URL_BYTES_TO_REMOVE`` predates and mirrors
# this WHATWG step for '\t'/'\r'/'\n' specifically) -- verified above,
# non-regression-tested below -- but the rule is implemented explicitly here
# too, deliberately redundant with urlsplit's own behavior, so this
# module's pre-normalization step does not silently DEPEND on an
# undocumented CPython implementation detail that could change across
# Python versions; it is the single place this invariant is asserted and
# owned.
_TAB_OR_NEWLINE_RE = re.compile("[\t\n\r]")

# Fix-round-8 (2026-09-11, live-hook-confirmed gap after the round-7 fuzz):
# tab/LF/CR are removed EVERYWHERE (above) and a leading/trailing run of
# C0-or-space is stripped (above), but the remaining 29 C0 controls
# (0x00-0x08, 0x0B, 0x0C, 0x0E-0x1F) plus 0x7F DEL, when they occur INSIDE
# the string (not just at the ends), used to survive pre-normalization
# untouched and land in front of urlsplit -- which parses right past them
# with a confident-looking result (see this constant's docstring below for
# what WHATWG/Node's real ``URL`` parser does instead).
#
# GROUND TRUTH, verified live against Node v20 (2026-09-11) rather than
# assumed from the spec text alone -- see the WHATWG host-parser
# (https://url.spec.whatwg.org/#host-parsing) and port-parsing
# (https://url.spec.whatwg.org/#port-state) steps, and their own catalog of
# "forbidden host code points" (which includes every C0 control and 0x7F):
#   * HOST position  -- any of these code points anywhere in the host
#     component is a hard parse FAILURE ("Invalid URL"), not a strip.
#   * PORT position  -- the port state only accepts ASCII digits; any of
#     these code points there is likewise a hard parse FAILURE.
#   * USERINFO (username/password) position -- NOT a failure: WHATWG
#     percent-encodes it in place (verified:
#     ``new URL("https://us\x01er:p@host/x")`` succeeds, ``username`` comes
#     back ``"us%01er"``). This module never inspects userinfo for
#     anything, so no change is needed there -- noted only so a future
#     reader does not assume the whole authority is control-hostile.
#   * PATH / QUERY / FRAGMENT position -- NOT a failure: WHATWG
#     percent-encodes the byte in place and parses normally (verified:
#     ``new URL("https://host/api\x1f/x").pathname === "/api%1F/x"``). This
#     hook's own ``_canonicalize_path`` already treats path bytes
#     permissively (percent-decode/re-escape), which is consistent with
#     this -- a control character in the PATH is not a divergence from the
#     browser's own successful parse, so it is deliberately NOT a
#     parse-failure signal here; it is left to whatever pattern/prefix
#     matching already applies to the path.
#
# So the fix is narrow and targeted at HOST and PORT specifically (see
# ``_authority_has_forbidden_control``), never the whole authority/URL --
# widening it to also fail on a userinfo or path control character would
# make this hook MORE aggressive than the real parser (the same class of
# self-inflicted divergence fix-round-5's docstring warns about), not more
# correct.
_C0_OR_DEL_RE = re.compile("[\x00-\x1f\x7f]")


def _whatwg_pre_normalize(url: str) -> Optional[str]:
    """Pre-normalize *url* to WHATWG ``basic URL parser`` rules BEFORE
    ``urlsplit`` ever sees it, closing the recurring host/path-parser
    divergence documented in the block above this function.

    Returns the pre-normalized string, or ``None`` when the input cannot be
    confidently pre-normalized at all (not a string, or empty after
    stripping) -- callers treat ``None`` as "cannot be sure this parses like
    the browser" and take the fail-closed path (see ``_canonical_origin_and_path``
    and ``_decide``'s final safety net).

    Rules applied, in WHATWG's own order (https://url.spec.whatwg.org/#url-parsing):
      1. Strip a leading/trailing run of C0-control-or-space from the WHOLE
         string (step 1 of the spec's basic URL parser).
      2. Strip every tab/newline/carriage-return ANYWHERE in the string
         (step 2) -- redundant with urlsplit's own behavior but asserted
         here explicitly (see ``_TAB_OR_NEWLINE_RE``'s docstring).
      3. For a "special scheme" (http/https/ws/wss/ftp/file -- see
         ``_WHATWG_SPECIAL_SCHEMES``), replace every backslash with a
         forward slash. WHATWG's path-state and special-authority-slashes-
         state machinery treats '\\' as a '/' for these schemes
         (https://url.spec.whatwg.org/#special-scheme); Python's urlsplit
         never does, for any scheme, which is exactly the fix-round-7
         headline bug (a backslash-containing tail folds into netloc
         instead of being seen as a path separator at all).
    The scheme sniff for step 3 is a plain literal-prefix check against
    ``_WHATWG_SPECIAL_SCHEMES`` (case-insensitive, allowing leading
    whitespace already stripped by step 1) rather than a full parse -- this
    function runs BEFORE urlsplit precisely so it must not itself depend on
    urlsplit succeeding.
    """
    if not isinstance(url, str):
        return None
    stripped = url.strip(_C0_OR_SPACE)
    if not stripped:
        return None
    stripped = _TAB_OR_NEWLINE_RE.sub("", stripped)
    if not stripped:
        return None
    scheme_match = re.match(r"^([A-Za-z][A-Za-z0-9+.\-]*):", stripped)
    if scheme_match and scheme_match.group(1).lower() in _WHATWG_SPECIAL_SCHEMES:
        scheme_len = scheme_match.end()
        stripped = stripped[:scheme_len] + stripped[scheme_len:].replace("\\", "/")
    return stripped


# ---------------------------------------------------------------------------
# Pattern / URL helpers (pure — ported verbatim from prod_proxy.py).
# ---------------------------------------------------------------------------


def _whatwg_ipv4_number(part: str) -> Optional[int]:
    """Mirror the WHATWG URL "IPv4 number parser": *part* is a single
    dot-separated segment of a candidate IPv4 host. Returns its integer
    value, or ``None`` if *part* is not a valid WHATWG IPv4 number (an
    empty segment, or one containing a character outside the radix implied
    by its own prefix).

    WHATWG accepts THREE radixes per segment, selected by prefix — decimal
    (no prefix), hex (``0x``/``0X``), and octal (a leading ``0`` with no
    ``x``) — which is why ``2130706433`` (decimal), ``0x7f000001`` (hex),
    and ``0177.0.0.1`` (octal first octet) all resolve to the same address
    a real browser routes to ``127.0.0.1``, none of which
    ``ipaddress.ip_address`` (stdlib, decimal-and-dotted-quad only) accepts
    at all. Live-verified against Node v20 ``new URL(...).hostname``,
    2026-09-11 fix-round-10.
    """
    if part == "":
        return None
    radix = 10
    if len(part) >= 2 and part[0] == "0" and part[1] in ("x", "X"):
        part = part[2:]
        radix = 16
    elif len(part) >= 2 and part[0] == "0":
        part = part[1:]
        radix = 8
    if part == "":
        # A bare "0" or "0x" with nothing after the prefix is valid (value 0).
        return 0
    digits = "0123456789abcdef" if radix == 16 else ("01234567" if radix == 8 else "0123456789")
    if any(ch not in digits for ch in part.lower()):
        return None
    try:
        return int(part, radix)
    except ValueError:
        return None


def _whatwg_ipv4_parse(host: str) -> Optional[str]:
    """Mirror the WHATWG URL IPv4 parser: if *host* is a valid WHATWG IPv4
    address spelling (dotted-quad, dotted-shorthand with 1-3 parts, pure
    decimal, hex, or octal — any mix of those per segment, matching the
    real algorithm), return its canonical dotted-quad string
    (``"127.0.0.1"``). Returns ``None`` for anything that is not a valid
    WHATWG IPv4 spelling at all (including every ordinary DNS domain —
    a non-digit character in the final segment or too many segments always
    yields ``None`` here, so this is safe to attempt unconditionally on any
    hostname without a separate "looks like an IP" pre-check).

    Deliberately narrower than the full WHATWG algorithm in one respect:
    the spec HARD-ERRORS (rejects the whole URL) for a host like ``"a.1"``
    (ends in a number, but an earlier segment fails to parse as one), where
    this function returns ``None`` instead — a caller here only needs "is
    this confidently one of our own loopback aliases", so falling through
    to treat ``"a.1"`` as an ordinary (non-IP) hostname is safe: it is not
    one of our tenant-scoped hosts either way, and never converts a deny
    into an allow.

    Live-verified against Node v20 ``new URL(...).hostname``, 2026-09-11
    fix-round-10, including the 32-bit-overflow reject (``4294967296`` and
    ``999999999999`` -> ``None`` here / hard error in Node) and the
    wraparound accept at the boundary (``4294967295`` -> ``255.255.255.255``
    in both).
    """
    parts = host.split(".")
    if parts and parts[-1] == "":
        if len(parts) == 1:
            return None
        parts = parts[:-1]
    if not parts or len(parts) > 4:
        return None
    numbers: list[int] = []
    for part in parts:
        n = _whatwg_ipv4_number(part)
        if n is None:
            return None
        numbers.append(n)
    if any(n > 255 for n in numbers[:-1]):
        return None
    if numbers[-1] >= 256 ** (5 - len(numbers)):
        return None
    ipv4 = numbers[-1]
    for i, n in enumerate(numbers[:-1]):
        ipv4 += n * (256 ** (3 - i))
    if ipv4 > 0xFFFFFFFF:
        return None
    return ".".join(str((ipv4 >> (8 * (3 - i))) & 0xFF) for i in range(4))


def _canonicalize_ip_literal(hostname: str) -> Optional[str]:
    """If *hostname* is an IP literal under ANY spelling a real WHATWG/
    browser URL parser accepts (IPv4 dotted-quad/shorthand/decimal/hex/
    octal, or a bracket-stripped IPv6 literal in any RFC 5952 form),
    return its canonical string form; otherwise ``None`` (not an IP
    literal at all — the caller falls through to ordinary domain
    handling).

    2026-09-11 fix-round-10 (independent-reviewer MAJOR finding): prior to
    this, ``_idna_normalize_host`` canonicalized DNS-label spellings
    (percent-decode + IDNA) but performed no IP-literal canonicalization at
    all, so a non-canonical loopback spelling (``127.1``, ``2130706433``,
    ``0x7f000001``, ``[0:0:0:0:0:0:0:1]``, ``[::ffff:127.0.0.1]``) read as
    an unrecognized third-party host to ``_is_tenant_scoped_host`` even
    though a real browser resolves every one of them to a loopback address
    already listed in ``_TENANT_SCOPED_HOST_SUFFIXES`` — the exact same
    "our own notion of the host must agree with the browser's" gap the
    module's governing invariant exists to close, on the address-literal
    axis rather than the DNS-label axis. Live-verified against Node v20,
    2026-09-11.

    The returned IPv6 form need not be textually IDENTICAL to WHATWG's own
    canonical spelling (Python's ``ipaddress.IPv6Address.compressed``
    renders an IPv4-mapped address as ``::ffff:127.0.0.1``, dotted-quad,
    where WHATWG's own algorithm would print ``::ffff:7f00:1``, hex) — both
    are internally CONSISTENT (every spelling of the same address collapses
    to the identical string under this function), which is all a
    suffix/equality comparison against a fixed allowlist needs; this
    function's contract is "same address -> same string here", never
    "identical to WHATWG's own preferred spelling".
    """
    if not hostname:
        return None
    if ":" in hostname:
        # IPv6 literal (urlsplit / _is_tenant_scoped_host both hand this
        # function a bracket-stripped form) or something with a stray
        # colon that isn't a valid address at all.
        try:
            return ipaddress.IPv6Address(hostname).compressed
        except ValueError:
            return None
    ipv4 = _whatwg_ipv4_parse(hostname)
    if ipv4 is not None:
        return ipv4
    return None


def _idna_normalize_host(hostname: str) -> Optional[str]:
    """Normalize *hostname* (already lowercased, ``urlsplit``-extracted) to
    the same string a real WHATWG/browser host parser would produce, or
    ``None`` when this cannot be done confidently.

    Fix-round-9 (2026-09-11, independent-reviewer finding): ``urlsplit``
    returns a confident-looking hostname for a percent-encoded dot
    (``app.example%2ecom``) or an IDNA-mappable non-ASCII label
    (the fullwidth ideographic full stop ``app.example。com``)
    WITHOUT ever decoding/mapping it — Python's host parser is purely
    syntactic here, unlike WHATWG's, which percent-decodes and applies IDNA
    ToASCII/nameprep to every label before comparing hosts. Both spellings
    are live-verified (Node v20 ``new URL(...).hostname``, 2026-09-11) to
    resolve to ``app.example.com`` — OUR OWN app host — while this
    hook's un-normalized ``_host_of``/``_canonical_origin_and_path`` saw a
    DIFFERENT string, so ``_is_tenant_scoped_host`` returned False and R2's
    off-tenant guard silently never ran against an off-tenant id headed at
    our own production app. This is exactly the module's own governing
    invariant (see the module docstring) applied to a host axis no prior
    fix round touched: host normalization, not just host case/port/control-
    character handling.

    Per-label percent-decode + ``str.encode("idna")`` (the stdlib's ToASCII
    codec) mirrors WHATWG's own per-label IDNA mapping closely enough for
    this hook's purposes — a label that fails to encode (an malformed
    IDNA label, e.g. a bare ``--`` or an over-long label) makes this
    function return ``None`` (fail-closed: the caller must not trust a
    hostname it could not confidently reproduce) rather than passing the
    un-normalized label through, which would silently re-open the same gap
    for whatever spelling tripped the encode failure. An empty *hostname* or
    an empty label spelled by consecutive dots (``a..b.com``) also returns
    the ORIGINAL string unchanged for that label (WHATWG treats an empty
    domain label as valid in some contexts and this hook has no host-scoped
    rule that depends on rejecting it) — see the fixture-backed test suite
    for the exact matrix this was checked against.

    IPv6 literals (bracketed, e.g. ``[::1]``, or the bare ``::1`` this
    module's own ``_is_tenant_scoped_host``/``record_navigate_host`` may see
    after ``urlsplit`` strips brackets) contain no ``.``-separated labels a
    real hostname would have, so per-label IDNA encoding would be a no-op on
    them (``"::1".encode("idna")`` raises — colons are not valid in an IDNA
    label). Fix-round-10 (2026-09-11, independent-reviewer MAJOR finding)
    replaced the prior "pass an IPv6-shaped hostname through UNCHANGED"
    behavior with a real canonicalization via ``_canonicalize_ip_literal``:
    an un-normalized alias (``0:0:0:0:0:0:0:1``, ``::ffff:127.0.0.1``) used
    to read as a spelling ``_is_tenant_scoped_host`` did not recognize even
    though a real browser resolves it to a loopback address already in
    ``_TENANT_SCOPED_HOST_SUFFIXES``. The same call also now canonicalizes
    a non-canonical IPv4 LITERAL spelling (``127.1``, ``2130706433``,
    ``0x7f000001``) that ``urlsplit`` parses as a bare hostname (no
    ``.``-separated IDNA labels to reject it) but which a real browser
    resolves to ``127.0.0.1``. Any hostname that ``_canonicalize_ip_literal``
    does not recognize as an IP literal at all (an ordinary DNS name, or a
    malformed one) falls through to the pre-existing percent-decode/IDNA
    path below unchanged — this is purely additive, never a behavior change
    for a non-IP-literal hostname. A control character reaching this point
    has already been rejected upstream by ``_authority_has_forbidden_control``,
    so a bare ``:`` surviving to here is always a literal IPv6 address
    component, never an attacker-controlled label.
    """
    if not hostname:
        return None
    ip_literal = _canonicalize_ip_literal(hostname)
    if ip_literal is not None:
        return ip_literal
    if ":" in hostname:
        # IPv6-shaped but not a value _canonicalize_ip_literal could parse
        # (e.g. a malformed literal) — pass through unchanged rather than
        # failing closed, matching this function's existing degrade
        # contract for input it cannot confidently normalize.
        return hostname
    try:
        decoded = unquote(hostname)
    except Exception:
        return None
    if not decoded:
        return None
    labels = decoded.split(".")
    normalized: list[str] = []
    for label in labels:
        if label == "":
            normalized.append(label)
            continue
        try:
            normalized.append(label.encode("idna").decode("ascii"))
        except UnicodeError:
            return None
        except Exception:
            return None
    return ".".join(normalized).lower()


def _host_of(url: str) -> str:
    """Return the lowercase, WHATWG-host-normalized hostname of *url* (``''``
    if unparseable).

    Pre-normalizes to WHATWG rules first (fix-round-7) — see the block above
    this module's WHATWG section for why. Falls back to parsing the RAW url
    if pre-normalization degrades it to ``None`` (an all-control/empty
    string) so this narrow helper's existing degrade-to-'' contract for a
    genuinely empty/garbage url is unchanged; callers that need the
    fail-closed treatment for an unparseable URL go through
    ``_canonical_origin_and_path`` instead, which propagates ``None``.

    Fix-round-9 (2026-09-11): the raw ``urlsplit`` hostname is additionally
    run through ``_idna_normalize_host`` (percent-decode + per-label IDNA
    ToASCII) so a percent-encoded or IDNA-mappable spelling of one of THIS
    RUNTIME'S OWN hosts is recognized as that host rather than as an
    unrecognized third-party one — see that function's docstring for the
    live-verified vector this closes. A hostname that fails to normalize
    confidently degrades to the RAW (un-normalized, still-lowercased)
    ``urlsplit`` hostname here (this function's existing ``''``-on-failure
    contract is preserved for genuinely unparseable input; the caller that
    needs the stricter fail-closed-to-None treatment for a host that could
    not be confidently normalized is ``_canonical_origin_and_path`` /
    ``_origin_pattern_matches``, both updated in the same round).
    """
    pre = _whatwg_pre_normalize(url)
    try:
        raw_host = (urlsplit(pre if pre is not None else url).hostname or "").lower()
    except ValueError:
        return ""
    if not raw_host:
        return ""
    normalized = _idna_normalize_host(raw_host)
    return normalized if normalized is not None else raw_host


def _normalize_host(host: str) -> str:
    """Normalize a hostname for comparison: lowercase, strip whitespace, and
    strip a single trailing '.' (a syntactically-valid FQDN root-label
    terminator that DNS treats as identical to the bare name but that a naive
    string-equality check against ``read_only_hosts`` would not — B1, 2026-09-10).

    Applied on BOTH sides of every R5 host comparison: when a host is
    recorded (``record_navigate_host``), when a state file is read back
    (``read_slot_hosts`` -- covers a record written by an older, pre-
    normalization version of this module), and to every ``read_only_hosts``
    allowlist entry at comparison time (covers a mixed-case allowlist entry).
    Pure; never raises. Non-string input returns ''.
    """
    if not isinstance(host, str):
        return ""
    h = host.strip().lower()
    if h.endswith(".") and len(h) > 1:
        h = h[:-1]
    return h


def _safe_port(split) -> Optional[int]:
    """*split*.port, or None on an out-of-range/unparseable port literal.

    Fix-round-6 (2026-09-11, #5392 closure): ``SplitResult.port`` raises
    ``ValueError`` for a syntactically-present-but-out-of-range port (e.g.
    ``:99999``). Every caller in this module that touches ``.port`` goes
    through this wrapper now, so a bad port degrades to "no port" instead of
    propagating an uncaught exception out of ``policy_decision`` — F5's fix
    is generalized here rather than left as a single try/except local to
    ``_normalize_url_for_pattern_match`` (fix-round-5 fixed that one call
    site and explicitly left ``_host_allowlisted``/``_origin_pattern_matches``
    unguarded, tracked as #5392; this round closes it because the new shared
    canonicalizer below is used by BOTH the R4 allow side and the pattern-deny
    side, so a single guard here now covers both instead of leaving one side
    exception-prone).
    """
    try:
        return split.port
    except ValueError:
        return None


def _authority_has_forbidden_control(split) -> bool:
    """True if *split* (an already-successful ``urlsplit`` result) carries a
    C0 control (0x00-0x1F) or 0x7F DEL in its HOST or PORT component.

    Fix-round-8 (2026-09-11): see ``_C0_OR_DEL_RE``'s docstring for the
    live-verified WHATWG/Node ground truth this mirrors -- a control
    character here is exactly the case where ``urlsplit`` parses "fine" but
    a real browser/fetch caller's URL constructor would reject the string
    outright, so this hook must not trust its own confident-looking parse.

    Checked component-by-component rather than over the whole ``netloc``
    string, deliberately: a control character in USERINFO (the
    ``user:pass@`` prefix urlsplit strips out of ``.hostname``) does NOT
    fail a real parse (WHATWG percent-encodes it) -- see ``_C0_OR_DEL_RE``'s
    docstring -- so scanning the raw ``netloc`` would over-deny a spelling a
    browser accepts, which is the same "hook is MORE aggressive than the
    server" defect class fix-round-5 fixed in the other direction.

    The HOST check uses ``split.hostname`` (already userinfo-stripped and
    bracket-stripped for IPv6, exactly the substring WHATWG's own host
    parser validates). The PORT check cannot use ``split.port`` (a control
    character there makes ``int()`` raise ``ValueError`` for the WRONG
    reason -- indistinguishable from a merely out-of-range numeric port,
    which ``_safe_port`` deliberately degrades to "no port" rather than
    denying, per fix-round-6/#5392) -- so it re-derives the raw port
    LITERAL directly from ``netloc`` (the substring after the last ``:``
    that is after the last ``@``, mirroring how ``SplitResult.port`` itself
    locates it) and scans that substring instead.
    """
    hostname = split.hostname or ""
    if _C0_OR_DEL_RE.search(hostname):
        return True
    netloc = split.netloc or ""
    authority = netloc.rsplit("@", 1)[-1]  # drop "user:pass@" if present
    if ":" in authority:
        port_literal = authority.rsplit(":", 1)[-1]
        if _C0_OR_DEL_RE.search(port_literal):
            return True
    return False


def _canonical_origin_and_path(url: str) -> Optional[Tuple[str, str, str, str]]:
    """Canonicalize *url* into (origin, path, query, fragment) for BOTH R4's
    allowlist check and the ``denied_action_patterns`` deny check, fixing the
    asymmetry that let ``POST https://admin-staging.example.com
    :8443/api/v2/inputs/process`` (and any other non-default-port spelling)
    reach R4's allow branch unmatched by a host-scoped denied pattern
    (fix-round-6, 2026-09-11, independent-verifier fuzz finding).

    Fix-round-3 through fix-round-5 each normalized ONE side of this
    comparison (the pattern-match side, via ``_normalize_url_for_pattern_match``
    / ``_canonicalize_path``) while R4's own ``_host_allowlisted`` /
    ``_origin_pattern_matches`` kept a SEPARATE, more permissive normalization
    (host on ANY port, via its own bare + ``:port`` candidate pair). The two
    normalizations agreed on case/default-port/path-structure but diverged
    exactly on a non-default port: R4 admits it (candidate list includes the
    ``:port`` form), the pattern side preserved it in the string being
    globbed against a port-less pattern (``.../api/*``), so the port never
    matched and the request fell through to R4's allow.

    THE FIX IS SYMMETRY, NOT ANOTHER AXIS: this single helper is now the one
    place both sides read from. The port is DROPPED ENTIRELY for matching
    purposes on both sides — R4 already treats the host as allowlisted
    regardless of port (the deployed container answers on 443 only, but a
    port-qualified URL still reaches the same server), so making the pattern
    side ALSO port-insensitive is what closes the asymmetry; making R4
    port-strict instead would be the wrong direction (see fix-round-6 dispatch
    instruction).

    Returns None for an unparseable/no-host URL (mirrors ``_host_of``'s own
    ``''`` degrade and ``_normalize_url_for_pattern_match``'s original-url
    fallback) so callers can fall back to their own prior behavior for that
    edge case; a bad PORT (out of range, e.g. ``:99999``) does NOT return
    None — it degrades to "no port" via ``_safe_port`` and canonicalization
    proceeds normally (F5 continuation, #5392): ``policy_decision`` must
    return a decision, never raise, for this input.

    Fix-round-7 (2026-09-11): *url* is pre-normalized to WHATWG rules
    (``_whatwg_pre_normalize``) BEFORE ``urlsplit`` sees it — see that
    function's docstring and the WHATWG section above ``_host_of``. When
    pre-normalization itself cannot produce a confident string (not a
    string, or empty/all-control after stripping), this now returns None
    the same as an unparseable URL — the module-wide fail-closed invariant:
    where this hook cannot be sure it parses (host, path) the way the
    browser does, it must not guess.

    Fix-round-8 (2026-09-11): a C0 control (0x00-0x1F) or 0x7F DEL surviving
    into the HOST or PORT component (``_authority_has_forbidden_control``)
    ALSO returns None here now, for the same reason — ``urlsplit`` parses
    such a string "successfully" (a confident-looking hostname comes back),
    but a real WHATWG/Node ``URL`` parse of the identical string fails
    outright (live-verified; see ``_C0_OR_DEL_RE``'s docstring), so trusting
    ``urlsplit``'s answer here would be a guess, not a confirmed parse.

    Scope note (fix-round-13, 2026-09-12): this function's "confidently
    parseable" invariant covers case/default-port/non-default-port/path-
    structure/control-character confidence (the R1/R4 case/port/path axis,
    used by both R4's ``_host_allowlisted`` and R1/R3's
    ``denied_action_patterns`` matching) — it deliberately does NOT apply
    ``_idna_normalize_host``'s percent-decode/IDNA-mapping normalization.
    That axis is scoped to ``_host_of`` alone, which feeds ONLY R2's
    ``_is_tenant_scoped_host`` off-tenant guard; R1/R4 have no tenant-id
    concept and gain nothing from IDNA-mapping a host they only compare
    against origin-pattern globs. Extending IDNA normalization to this
    function (and ``_origin_pattern_matches``) would be a separate, real
    change to R1/R4's own host-comparison semantics, not a documentation
    fix — left out of this round; see ``_host_of``'s docstring for the
    axis this function does NOT cover.
    """
    pre = _whatwg_pre_normalize(url)
    if pre is None:
        return None
    try:
        split = urlsplit(pre)
    except ValueError:
        return None
    host = (split.hostname or "").lower()
    if not host:
        return None
    if _authority_has_forbidden_control(split):
        return None
    scheme = (split.scheme or "").lower()
    # Port is intentionally NOT part of the origin below -- see docstring.
    _safe_port(split)  # computed only to normalize a bad-port URL without raising
    origin = f"{scheme}://{host}"
    path = _canonicalize_path(split.path or "").lower()
    return origin, path, split.query or "", split.fragment or ""


def _origin_pattern_matches(origin_pattern: str, url: str) -> bool:
    """True if *url*'s scheme+host matches an ``allowed_origins`` entry.

    Fix-round-7 (2026-09-11): pre-normalized to WHATWG rules first (same
    rationale as ``_canonical_origin_and_path`` — this function must agree
    with that one on what the host actually is, since R4's allow decision
    (``_host_allowlisted``, which calls this) and R1/R3's deny decision
    (which reads ``_canonical_origin_and_path`` via
    ``_normalize_url_for_pattern_match``) must never diverge on the SAME
    url's host). A url that fails pre-normalization (``None``) has no
    confident host at all and returns False — R4 must never ADMIT a host it
    cannot confidently parse; that is the fail-closed direction for the
    allow side (the deny side's own fail-closed net lives in ``_decide``,
    see the module docstring's governing-invariant paragraph).

    Fix-round-8 (2026-09-11): a C0/DEL control surviving into HOST or PORT
    (``_authority_has_forbidden_control``) likewise returns False here, in
    lockstep with ``_canonical_origin_and_path``'s same-round change — the
    two functions must never diverge on whether a given url's authority is
    confidently parseable (see that function's fix-round-8 note).

    Scope note (fix-round-13, 2026-09-12): deliberately does not apply
    ``_idna_normalize_host`` — see ``_canonical_origin_and_path``'s own
    scope note for why that axis is confined to ``_host_of``/R2 and does
    not extend to this R4 host-allowlist comparison.
    """
    pre = _whatwg_pre_normalize(url)
    if pre is None:
        return False
    try:
        split = urlsplit(pre)
    except ValueError:
        return False
    host = (split.hostname or "").lower()
    if not host:
        return False
    if _authority_has_forbidden_control(split):
        return False
    scheme = (split.scheme or "").lower()
    port = _safe_port(split)
    candidates = [f"{scheme}://{host}"]
    if port is not None:
        candidates.append(f"{scheme}://{host}:{port}")
    for cand in candidates:
        if fnmatch.fnmatch(cand, origin_pattern):
            return True
    return False


def _host_allowlisted(url: str, allowlist: dict) -> bool:
    """True if *url*'s origin matches any ``allowed_origins`` entry."""
    for origin_pattern in allowlist.get("allowed_origins", []):
        if _origin_pattern_matches(origin_pattern, url):
            return True
    return False


def _whatwg_resolve_dot_segments(path: str) -> str:
    """Resolve ``.``/``..`` dot-segments in *path* using WHATWG path-state
    popping semantics, where an EMPTY segment produced by a duplicate slash
    (``//``) is itself a real, poppable segment -- it is not collapsed away
    before dot-segment resolution runs. ``path`` must already be absolute
    (start with ``/``); a non-absolute *path* is returned unchanged.

    Fix-round-15 (2026-09-12, round-8 review BLOCKER): ``_canonicalize_path``
    used to collapse duplicate slashes with a regex BEFORE handing the result
    to ``posixpath.normpath`` for dot-segment resolution. ``normpath``
    resolves ``..`` by popping the last *non-empty* segment off its stack
    (POSIX/filesystem semantics, where ``//`` is not a distinct path
    component at all), so collapsing ``//`` to ``/`` first made
    ``/admin//..`` normalize the same as ``/admin/..`` -- popping the REAL
    ``admin`` segment and resolving to ``/``. A real WHATWG/Node ``URL``
    parse of the identical path (the hook's own governing invariant: never
    be MORE aggressive than the server that actually receives the request)
    treats the empty segment between the two slashes as its own path
    component, so ``..`` pops THAT instead and the browser sends
    ``/admin/`` -- still matching a ``*/admin/*`` denied pattern. Resolving
    first (this function) makes the hook agree with the browser: ``..``
    pops whatever segment (empty or not) is actually adjacent to it, exactly
    as the WHATWG path state machine specifies
    (https://url.spec.whatwg.org/#path-state, the "double-dot path segment"
    branch, which pops from the buffer's segment list unconditionally).

    Any duplicate slashes REMAINING after dot-segment resolution (i.e. not
    involved in a ``..`` pop, such as ``/a/b//c``) are still collapsed by the
    caller, unconditionally, AFTER this function runs -- that direction is
    safe (it can only make the hook MORE likely to match a denied pattern,
    never less), unlike collapsing before resolution.

    Pure; never raises. Deliberately mirrors ``_canonicalize_path``'s own
    "percent-decode PER SEGMENT, never treat a decoded ``%2f`` as a
    separator" invariant by operating purely on segments split at literal
    (already-decoded-and-reescaped) ``/`` characters -- callers are
    responsible for that decoding before calling this function, exactly as
    ``_canonicalize_path`` already does.
    """
    if not path.startswith("/"):
        return path
    segments = path.split("/")[1:]  # drop the leading "" from the initial "/"
    stack: list[str] = []
    for seg in segments:
        if seg == "..":
            if stack:
                stack.pop()
        elif seg == ".":
            continue
        else:
            stack.append(seg)
    return "/" + "/".join(stack)


def _canonicalize_path(path: str) -> str:
    """Percent-decode, resolve dot-segments, and collapse duplicate slashes.

    Fix-round-4 (2026-09-11 trust-architect B1): ``_normalize_url_for_pattern_match``
    used to lowercase the path but never touch its STRUCTURE, so a host-scoped
    ``denied_action_patterns`` entry (e.g.
    ``https://admin-staging.example.com/api/*``) was bypassable for a
    denied non-idempotent request by any of: a leading double slash
    (``//api/v1/x``), a ``.`` segment (``/./api/v1/x``), a ``..`` segment
    (``/a/../api/v1/x``), or percent-encoded path characters
    (``/%61pi/v1/x`` decodes to ``/api/v1/x``) — all of which R4's own
    ``_host_allowlisted`` still allowlists (it only inspects scheme+host, never
    the path), so the request reached R4 and was ALLOWED despite matching the
    *intent* of the denied pattern. ``/health/`` and ``/health?x=1`` were a
    second variant of the same gap against the bare (non-glob) ``.../health``
    entry specifically — see the ``/health*`` glob fix in ``allowlist.json``.

    Fix-round-5 (2026-09-11 trust-architect warm review, B2): fix-round-4's
    whole-path ``unquote(path)`` decoded a percent-encoded ``/`` (``%2f`` /
    ``%2F``) into a REAL path separator, which then participated in
    dot-segment resolution exactly like a literal ``/`` — so
    ``/api/v1%2f..%2f..%2fout`` decoded to ``/api/v1/../../out``, resolved to
    ``/out``, and no longer matched the ``.../api/*`` denied pattern at all.
    That is a bypass in the OPPOSITE direction from fix-round-4's fix: this
    hook's own server (see ``_normalize_url_for_pattern_match``'s docstring)
    parses the URL with WHATWG/Node ``URL`` semantics and never decodes
    ``%2f`` into a path-separating ``/`` — it keeps the pathname
    ``/api/v1%2f..%2f..%2fout`` intact, sees it still ``startswith('/api')``,
    and proxies it through. Relocating the SAME request from "reaches the
    denied pattern" (HEAD / fix-round-3) to "resolves away from it" (fix-round-4)
    is exactly the class of defect this module's own governing principle
    exists to rule out: **the hook's canonicalization must never be MORE
    aggressive than the server's** — wherever the hook resolves something the
    server does not, it is judging a different request than the one actually
    sent, and every such divergence is a potential bypass in one direction or
    the other.

    The fix decodes PER SEGMENT rather than on the whole path: the path is
    split on its literal (still-encoded) ``/`` characters first, each
    resulting segment is percent-decoded independently (so an encoded
    ``%2e%2e`` still becomes a real ``..`` and still participates in
    dot-segment resolution — fix-round-4's win is preserved), and any ``/``
    that decoding produces *within* a segment (from ``%2f``/``%2F``) is
    immediately re-escaped back to a canonical lowercase ``%2f`` before the
    segments are rejoined — so a percent-encoded slash can never be mistaken
    for a path boundary and can never itself create or erase a ``..``
    resolution opportunity, matching the server's own behavior of never
    treating it as a separator.

    Fix-round-15 (2026-09-12, round-8 review BLOCKER): dot-segments are now
    resolved by ``_whatwg_resolve_dot_segments`` (WHATWG segment-popping
    semantics, where an empty segment produced by ``//`` is itself poppable)
    BEFORE any duplicate-slash collapsing happens — previously duplicate
    slashes were collapsed with a regex FIRST, then handed to
    ``posixpath.normpath`` for dot-segment resolution; ``normpath`` pops the
    last *non-empty* segment (POSIX/filesystem semantics, where ``//`` is not
    its own path component), so ``/admin//..`` collapsed to ``/admin/..``
    and normalized to ``/`` — popping the REAL ``admin`` segment where a
    real WHATWG/Node ``URL`` parse of the identical path pops the EMPTY
    segment between the two slashes instead and resolves to ``/admin/``
    (still matching a ``*/admin/*`` denied pattern). See
    ``_whatwg_resolve_dot_segments``'s own docstring for the full divergence
    this closes. Duplicate slashes REMAINING once dot-segments are resolved
    (e.g. ``/a/b//c``, which involves no ``..`` at all) are still collapsed
    by a regex afterward — collapsing is only unsafe when it happens BEFORE
    ``..`` resolution; collapsing what's left AFTER resolution can only make
    a request MORE likely to match a denied pattern, the safe direction. A
    trailing slash is stripped (except for the bare root ``/``) so
    ``/health`` and ``/health/`` compare equal — deliberate: every current
    ``denied_action_patterns`` entry is written without a trailing slash, and
    a request path differing only by one should not evade it. An empty path
    (a bare origin URL with no path at all) is returned unchanged. Pure;
    never raises (a decode/normalize error simply falls back to the original
    path via ``unquote``'s own permissive behavior).
    """
    if not path:
        return path
    raw_segments = path.split("/")
    decoded_segments = [unquote(seg) for seg in raw_segments]
    # A %2f/%2F decoded to a literal "/" inside a segment must never become a
    # new path boundary or feed dot-segment resolution -- re-escape it back
    # to its canonical (lowercase) percent-encoded form before rejoining.
    safe_segments = [seg.replace("/", "%2f") for seg in decoded_segments]
    decoded = "/".join(safe_segments)
    resolved = _whatwg_resolve_dot_segments(decoded) if decoded.startswith("/") else decoded
    normalized = re.sub(r"/{2,}", "/", resolved)
    if not normalized.startswith("/"):
        normalized = "/" + normalized
    if normalized != "/" and normalized.endswith("/"):
        normalized = normalized.rstrip("/")
    return normalized


def _normalize_url_for_pattern_match(url: str) -> str:
    """Normalize *url* for ``denied_action_patterns`` matching (R1/R3, fix-round-3;
    path canonicalization added fix-round-4, 2026-09-11 trust-architect B1; PORT
    dropped entirely, not just default-port-stripped, fix-round-6, 2026-09-11).

    Delegates to ``_canonical_origin_and_path`` — the ONE shared canonicalizer
    also used by R4's ``_host_allowlisted``/``_origin_pattern_matches`` path
    (see that helper's own docstring for the full asymmetry history: fix-round-3
    through fix-round-5 each closed a case/default-port/path-structure/encoded-
    slash gap on THIS side only, while R4 kept a separately-computed, more
    permissive normalization that always admits a host on ANY port — the two
    normalizations diverged exactly on a non-default port, which is what let
    ``POST https://admin-staging.example.com:8443/api/v2/inputs/process``
    reach R4's allow branch unmatched by the port-less ``.../api/*`` pattern).

    Fix-round-6 makes this function's OWN normalization port-insensitive too
    (previously it stripped only the scheme's *default* port and preserved any
    other) — the port is dropped from the comparand entirely, on both sides,
    which is what makes "R4 admits this host" and "does a pattern match this
    URL" agree for every port spelling rather than just the default one.

    Query string and fragment are preserved verbatim (never lowercased, never
    canonicalized) — a denied pattern is host/path-scoped in every entry in the
    live policy today, and query values (e.g. a tenant id) are case-sensitive
    data, not part of the URL's structural addressing the way scheme/host/path
    are. Malformed input, or a URL with no parseable host at all (``urlsplit``
    raising, or an opaque/bare-path string), returns the original *url*
    lowercased so the caller's ``fnmatch`` still gets a best-effort comparison
    (a path-only pattern like ``*/admin/*`` still needs case-insensitivity)
    rather than an empty string that could spuriously match a bare ``*``.

    Fix-round-5 (2026-09-11 trust-architect warm review, F5), generalized in
    fix-round-6: an out-of-range port literal (e.g. ``:99999``) must never
    raise here. ``_canonical_origin_and_path`` handles this via the shared
    ``_safe_port`` guard now (rather than a local try/except around
    ``split.port``), so a bad port degrades to "port ignored" and
    canonicalization proceeds normally — this function no longer needs its own
    port-specific guard at all, since the port is dropped unconditionally.
    """
    canon = _canonical_origin_and_path(url)
    if canon is None:
        return url.lower()
    origin, path, query, fragment = canon
    rebuilt = f"{origin}{path}"
    if query:
        rebuilt += f"?{query}"
    if fragment:
        rebuilt += f"#{fragment}"
    return rebuilt


def _url_matches_any_pattern(url: str, patterns: list[str]) -> bool:
    """True if *url* matches any of the glob-style *patterns*.

    Handles full-glob patterns (``https://*.stripe.com/*``), bare trailing-``/*``
    prefixes, and path-only ``*/admin/*`` fragments.

    Both *url* and each pattern are compared via ``_normalize_url_for_pattern_match``
    / a plain ``.lower()`` respectively (fix-round-3, 2026-09-11 trust-architect
    review): matching used to run ``fnmatch.fnmatch`` against the RAW url with no
    normalization at all, so a host-scoped denied pattern was bypassable by an
    explicit default port, host-case, or path-case variant that R4's own
    ``_host_allowlisted`` would still allowlist unchanged (see
    ``_normalize_url_for_pattern_match``'s docstring). Every pattern in the live
    policy is already lowercase (pinned by
    ``test_denied_action_patterns_are_already_lowercase``), so lowercasing the
    pattern here is a no-op for every existing entry and changes no prior
    behavior — it only closes the case-sensitivity gap for future entries.
    ``fnmatch.fnmatchcase`` (not the platform-normalizing ``fnmatch.fnmatch``) is
    used deliberately: both operands are already explicitly lowercased above, so
    matching must not ALSO apply the OS's own case-folding rules (case-preserving
    filesystems on macOS/Windows behave differently from Linux) on top of that —
    ``fnmatchcase`` makes the comparison's case sensitivity fully explicit and
    platform-independent.

    Fix-round-12 (2026-09-12, independent-reviewer finding, round-5 review
    BLOCKER 1): ``_canonicalize_path`` deliberately strips a TERMINAL trailing
    slash so ``/health`` and ``/health/`` compare equal against the bare
    (non-glob) ``.../health*`` pattern (fix-round-4; see that function's own
    docstring and ``test_canonicalize_path_resolves_dot_segments_and_duplicate_slashes``
    — this stripping is pinned behavior and must not be undone). But the
    glob-prefixed ``*/…/*`` fallback below reads ``normalized_url`` as a
    SUBSTRING space, where a stripped trailing slash silently removes the
    very ``/`` that a directory-shaped denied pattern (``*/admin/*``) needs
    to see: a request whose path resolves to EXACTLY ``.../admin`` (either
    because the browser sent ``.../admin`` with no trailing slash at all, or
    because the browser sent ``.../admin/`` and this hook's own path
    canonicalizer strips it) never contains the literal substring ``/admin/``
    — so ``POST https://admin.example.com/api/v1/admin/`` and
    ``POST https://api-admin.example.com/admin`` both fell through
    ``*/admin/*`` entirely and reached R4's allow branch (13 DENY(HEAD)->ALLOW
    regressions measured across the ``admin.example.com`` /
    ``api-admin.example.com`` / ``admin-staging.example.com``
    / ``app.example.com`` / ``api.example.com`` host set).

    THE FIX IS NARROW, MATCHING-SIDE ONLY (never re-touching
    ``_canonicalize_path`` itself, which stays exactly as fix-round-4/5 left
    it — reopening that function's own trailing-slash behavior would
    reintroduce the ``/health`` vs ``/health/`` spelling-divergence class
    fix-round-4 closed), and SCOPED to only the ``*/…/*`` glob-prefixed
    fallback (see that branch's own comment for why the OTHER, literal-prefix
    ``/*`` fallback needs no equivalent change — every live pattern's literal
    prefix never itself ends in ``/``, so the same trick would be dead code
    there): the substring check is tried against BOTH ``normalized_url`` AND
    ``normalized_url`` with a single trailing ``/`` appended
    (``normalized_url_as_dir``) — i.e. a path this hook canonicalized to end
    in a bare terminal segment is ALSO evaluated as though that segment were
    a directory, which is exactly how a real server's own route table treats
    ``/admin`` and ``/admin/`` for a prefix-style route. This is deliberately
    NOT done for the PRIMARY ``fnmatch.fnmatchcase`` match above (a full-glob
    pattern like ``https://*.stripe.com/*`` already requires ≥1 character
    after its own trailing ``/`` by construction, same as fix-round-4's F2
    finding on the bare-prefix fallback — appending a synthetic slash there
    would only ever matter for a pattern shape the fallbacks below already
    cover) and is safe to do unconditionally here because it can only ever
    make the fallback MATCH a case it previously missed, never make it stop
    matching a case it already caught (appending a character to the end of
    a string being searched for a substring cannot remove an existing hit).

    Fix-round-13 (2026-09-12, independent-verifier fuzz finding, round-6
    review BLOCKER): fix-round-12's own implementation built
    ``normalized_url_as_dir`` by appending ``"/"`` to the FULLY REBUILT
    ``normalized_url`` string (origin + path + query + fragment), so for any
    url carrying a query string or fragment the appended slash landed AFTER
    the query/fragment instead of after the path — ``.../admin/?x=1``,
    never ``.../admin/?x=1/`` in a shape the ``*/admin/*`` substring check
    could ever see. The trailing-segment-with-suffix case therefore never
    matched at all (27 additional DENY(HEAD)->ALLOW POST regressions,
    measured across the same host set as the round-12 finding, for
    ``?x=1`` / ``#f`` / ``?a=b&c=d`` suffixes on bare, trailing-slash, and
    nested ``.../admin`` paths). The fix derives the directory variant from
    the CANONICAL PATH, not the rebuilt comparand string: re-canonicalize
    *url* via ``_canonical_origin_and_path`` to get ``(origin, path, query,
    fragment)`` directly, insert the synthetic ``/`` right after ``path``
    (before query/fragment are ever reattached), and fall back to the
    round-12 whole-string append only when canonicalization itself fails
    (mirrors ``_normalize_url_for_pattern_match``'s own degrade-to-original
    behavior for an unparseable url) — a case where ``normalized_url`` is
    already just ``url.lower()`` with no query/fragment structure to
    preserve anyway.

    Fix-round-14 (2026-09-12, round-7 review BLOCKER): a terminal path
    segment carrying an RFC-3986 path-parameter suffix (a literal ``;``, e.g.
    ``/admin;x``, ``/admin;a=b``, or the percent-encoded ``/admin%3bx`` --
    already decoded to a literal ``;`` by ``_canonicalize_path`` by the time
    ``path`` is read here) never equals the bare directory segment
    (``admin``), so neither ``normalized_url`` nor ``normalized_url_as_dir``
    ever contained the pattern's own ``/admin/`` substring for that shape --
    27 of a 280-URL matrix wrongly ALLOWED. VERIFIED before treating this as
    a real bypass (never on the reviewer's say-so alone, per this module's
    own governing invariant): neither a real WHATWG/Node ``URL`` parse
    (``new URL("https://h/admin;x").pathname`` live-checked: ``"/admin;x"``,
    unchanged -- WHATWG does not recognize ``;`` as a path-parameter
    delimiter at all) NOR this stack's real router (Werkzeug's
    ``Map.match()`` live-checked against a ``/admin`` rule: ``/admin;x``
    404s, is NEVER routed to the ``/admin`` handler) treats ``;x`` as
    separable from ``admin`` -- so stripping ``;...`` in
    ``_canonicalize_path`` itself (matching the review's literal wording)
    would have made this hook's canonicalization MORE aggressive than both
    the browser and the real server it fronts, exactly the class of
    self-inflicted divergence fix-round-5's docstring warns against, and
    would newly misjudge a genuinely distinct, harmless literal path
    (e.g. ``/api/v1/customers;foo``, which 404s today and is not an
    ``/api/v1/customers`` request) as if it were the bare segment.

    The correct fix is MATCHING-SIDE ONLY, same discipline as fix-round-12:
    ``_canonicalize_path`` is untouched. A ``;``-suffixed terminal segment is
    never a route this backend actually serves (confirmed above), so for the
    sole purpose of deriving the directory-fallback comparand it is safe --
    strictly more conservative, never a new false-positive risk against any
    URL a real request could actually reach -- to ALSO strip a trailing
    ``;...`` matrix-parameter suffix from the path's terminal segment before
    appending the synthetic ``/``. This can only ever make the fallback
    match a case it previously missed (identical reasoning to why appending
    the synthetic slash itself is unconditionally safe, see above): a path
    with no ``;`` in its terminal segment is completely unaffected.
    """
    normalized_url = _normalize_url_for_pattern_match(url)
    canon = _canonical_origin_and_path(url)
    if canon is not None:
        origin, path, query, fragment = canon
        # Strip a trailing RFC-3986 path-parameter suffix (";...") from the
        # terminal segment only -- e.g. "/admin;x" -> "/admin",
        # "/api/v1/admin;a=b" -> "/api/v1/admin". A ";" anywhere else in the
        # path (not in the last segment) is left alone; this only feeds the
        # directory-fallback comparand below, never _canonicalize_path.
        last_slash = path.rfind("/")
        terminal = path[last_slash + 1 :]
        semi = terminal.find(";")
        if semi != -1:
            path_sans_params = path[: last_slash + 1] + terminal[:semi]
        else:
            path_sans_params = path
        normalized_url_as_dir = f"{origin}{path}/"
        normalized_url_as_dir_sans_params = f"{origin}{path_sans_params}/"
        if query:
            normalized_url_as_dir += f"?{query}"
            normalized_url_as_dir_sans_params += f"?{query}"
        if fragment:
            normalized_url_as_dir += f"#{fragment}"
            normalized_url_as_dir_sans_params += f"#{fragment}"
    else:
        normalized_url_as_dir = normalized_url + "/"
        normalized_url_as_dir_sans_params = normalized_url_as_dir
    for pat in patterns:
        normalized_pat = pat.lower()
        if fnmatch.fnmatchcase(normalized_url, normalized_pat):
            return True
        # Defensive fallbacks (ported from prod_proxy.py): on this Python/OS
        # fnmatch's ``*`` already crosses ``/`` and matches newlines, so these
        # subsume-by-R214 branches are belt-and-suspenders for platforms whose
        # fnmatch is stricter. Kept for parity with the proven source. Normalized
        # the same way as the primary match above (fix-round-3) so these
        # fallbacks cannot themselves become a normalization-bypass path.
        #
        # NOT actually subsumed on this platform (fix-round-4, F2, 2026-09-11
        # trust-architect review): a bare ``.../api`` (no trailing slash)
        # against a ``.../api/*`` pattern is DENIED only via this fallback —
        # ``fnmatch.fnmatchcase`` requires at least one character after the
        # trailing ``/`` for a ``/*`` pattern to match, so the primary match
        # above misses the bare-prefix case entirely. This branch is
        # load-bearing, not defensive-only; the ``no cover`` pragma below it
        # was therefore false and is removed (see the paired
        # ``test_bare_prefix_without_trailing_slash_is_denied_by_fallback``
        # test). Fix-round-12 (2026-09-12) considered ALSO trying
        # ``normalized_url_as_dir`` here (mirroring the second fallback
        # below), but every live ``.../*``-suffixed pattern's own literal
        # prefix (``normalized_pat[:-2]``) never itself ends in ``/`` — the
        # only way appending a trailing ``/`` to ``normalized_url`` could
        # newly satisfy ``str.startswith(prefix)`` here is if ``prefix``
        # equals ``normalized_url + "/"`` exactly, which requires a pattern
        # shaped ``.../seg//*`` (a literal double slash before the glob) —
        # not a shape any current or plausible future ``denied_action_patterns``
        # entry uses. Adding that check would be genuinely DEAD code for
        # this policy, so it was deliberately left out of this branch — the
        # actual bug (BLOCKER 1) lived entirely in the second, glob-prefixed
        # fallback below, which is where the real fix and its tests live.
        if normalized_pat.endswith("/*") and normalized_url.startswith(
            normalized_pat[:-2]
        ):
            return True
        # The second fallback (``*/…/*``) used to be fully subsumed by
        # ``fnmatchcase`` on this platform (hence its own now-removed
        # ``pragma: no cover``) EXCEPT for exactly the fix-round-12 gap this
        # round closes: a request resolving to precisely the denied
        # directory segment itself (``.../admin``, bare or with the trailing
        # slash ``_canonicalize_path`` strips) never contains the pattern's
        # own ``/admin/`` middle substring, so it fell through this branch
        # and reached R4's allow. Trying the substring check against BOTH
        # ``normalized_url`` and ``normalized_url_as_dir`` (the same url with
        # a single trailing ``/`` appended) closes that gap without ever
        # weakening the branch: appending a character to the string being
        # searched can only ever ADD a match it didn't already have, never
        # remove one — see this function's own docstring for the fuller
        # fix-round-12 rationale. This branch is genuinely live again (not
        # dead/defensive-only) for this exact terminal-segment shape, which
        # is why its ``pragma: no cover`` is removed rather than kept.
        #
        # Fix-round-14 (2026-09-12): ALSO try
        # ``normalized_url_as_dir_sans_params`` (the terminal segment with
        # any trailing ``;...`` path-parameter suffix stripped before the
        # synthetic ``/`` is appended — see this function's own docstring).
        # Same safety argument as the round-12 addition: this only ever adds
        # a match for a ``;``-suffixed terminal segment, and is a no-op
        # (identical to ``normalized_url_as_dir``) for every url whose
        # terminal segment carries no ``;`` at all.
        if normalized_pat.startswith("*/") and normalized_pat.endswith("/*"):
            middle = normalized_pat[1:-1]  # e.g. "/admin/"
            if (
                middle in normalized_url
                or middle in normalized_url_as_dir
                or middle in normalized_url_as_dir_sans_params
            ):
                return True
    return False


def _comms_patterns(allowlist: dict) -> list[str]:
    """The subset of denied_action_patterns that are comms endpoints."""
    return [
        p
        for p in allowlist.get("denied_action_patterns", [])
        if any(kw in p.lower() for kw in _COMMS_KEYWORDS)
    ]


def _is_app_comms_endpoint(url: str) -> bool:
    """True if *url*'s path looks like an app-hosted comms endpoint.

    Fix-round-7: pre-normalized to WHATWG rules first (so a backslash/control-
    char-laden url's path is recovered the same way every other rule in this
    module now sees it), and the whole call is guarded against ``urlsplit``
    raising (e.g. an unparseable IPv6-shaped authority — ``ValueError:
    Invalid IPv6 URL``, a pre-existing unguarded call site this round also
    closes) — degrades to False (not detected as an app-comms path) rather
    than propagating an exception out of ``policy_decision``, matching this
    module's "must return a decision, never raise" invariant (see
    ``_safe_port``'s docstring for the precedent).
    """
    pre = _whatwg_pre_normalize(url)
    if pre is None:
        return False
    try:
        path = unquote(urlsplit(pre).path).lower()
    except ValueError:
        return False
    return any(kw in path for kw in _APP_COMMS_PATH_KEYWORDS)


def _is_tenant_scoped_host(host: str) -> bool:
    """True if *host* is one of THIS RUNTIME'S OWN product app hosts — the
    only hosts R2's tenant guard (see ``_TENANT_SCOPED_HOST_SUFFIXES``) is
    meant to police.

    *host* is expected already normalized by ``_host_of`` (lowercase); this
    additionally strips a trailing '.' (FQDN root-label terminator) and any
    ``:port`` suffix defensively, so a caller passing a raw netloc-shaped
    string still compares correctly. Pure; never raises.

    An EMPTY or otherwise unparseable host (``_host_of`` degrades to ``''``
    for a URL it cannot confidently parse) returns True — fail-closed,
    matching this module's "cannot be sure -> take the safer, MORE-checked
    path" governing invariant (see the module docstring): R2 keeps
    extracting/gating tenant ids exactly as it did before this fix rather
    than silently exempting a host it failed to identify at all.

    2026-09-11: added after ``https://www.linkedin.com/company/setup/new/``
    was denied as an off-tenant request — LinkedIn is a third-party host with
    no ExampleApp AI / OtherApp tenant boundary, so R2 must never apply
    to it. See ``_TENANT_SCOPED_HOST_SUFFIXES``'s docstring for the full
    incident and the two product bases this guards.
    """
    if not isinstance(host, str) or not host:
        return True
    h = host.strip().lower()
    if h.startswith("[") and h.endswith("]"):
        # A caller-supplied bracketed IPv6 literal (``_host_of`` itself never
        # produces one -- see below -- but this function is documented as
        # accepting "a raw netloc-shaped string" defensively too).
        h = h[1:-1]
    if h.endswith(".") and len(h) > 1:
        h = h[:-1]
    # Strip a trailing ":port" defensively -- but ONLY when *h* is not
    # itself a bare IPv6 literal (brackets, if any, were already stripped
    # above). ``_host_of`` (via ``urlsplit``/``SplitResult.hostname``)
    # always returns an IPv6 host WITHOUT its brackets (e.g. ``"::1"`` for
    # ``http://[::1]:8000/...``) -- a bare ``"::1"`` has a ``:`` and, before
    # this fix, was not recognized as IPv6-shaped at this point, so it got
    # rpartitioned into ``candidate="::" , port="1"`` (since "1" is
    # all-digit) and silently mangled into a non-matching string
    # (fix-round-9, 2026-09-11, independent-reviewer secondary finding --
    # this is what made the ``"::1"`` entry added to
    # ``_TENANT_SCOPED_HOST_SUFFIXES`` this same round fail to match on its
    # own until this was also fixed). A host containing 2+ colons is
    # unambiguously an IPv6 literal (a real DNS hostname or a bracket-
    # stripped IPv6 literal never contains more than one bare ``:port``
    # separator), so it is never treated as host:port here.
    if h.count(":") == 1:
        candidate, _, port = h.rpartition(":")
        if port.isdigit():
            h = candidate
    if not h:
        return True
    for suffix in _TENANT_SCOPED_HOST_SUFFIXES:
        if h == suffix or h.endswith("." + suffix):
            return True
    return False


def _extract_tenant_ids(url: str) -> list[str]:
    """Every company/tenant id referenced by *url* (path + query); [] if none.

    Fix-round-7: pre-normalized to WHATWG rules first, and guarded against
    ``urlsplit`` raising (same rationale and precedent as
    ``_is_app_comms_endpoint`` above) — degrades to [] (no tenant id found)
    rather than propagating an exception. [] is the safe degrade for THIS
    rule specifically: R2 only denies when a tenant id is FOUND and it is
    off-allowlist; finding none is indistinguishable from "no tenant-shaped
    segment in this url" either way, and any non-idempotent request this
    permissive here would still face the R1 pattern check and the R4
    allowlist check (plus fix-round-7's new safety net) downstream.

    Fix-round-11 (2026-09-11, independent-reviewer finding): case-folds both
    the PATH matched against ``_TENANT_URL_PATTERNS`` and the QUERY key
    lookup against ``_TENANT_QUERY_KEYS`` before matching -- neither used to
    happen, so ``/COMPANY/co-EVILTENANT/estimates``, ``/Companies/...``,
    ``/TENANT/...``, and ``?COMPANY_ID=...`` all skipped R2's tenant guard
    entirely (the lowercase-only regexes in ``_TENANT_URL_PATTERNS`` never
    matched an uppercase path segment, and ``parse_qs`` is itself
    case-sensitive, so an exact-case ``_TENANT_QUERY_KEYS`` lookup missed a
    same-key-different-case query param) while the plain lowercase spelling
    of the identical URL correctly denied. This mirrors how R1's own
    ``_canonical_origin_and_path`` case-folds via
    ``_canonicalize_path(...).lower()`` -- the SAME governing invariant (this
    hook's notion of a URL's identity must not be sensitive to a spelling
    axis the browser itself is insensitive to) applies to tenant-id
    extraction. Every extracted tenant id is ALSO lowercased before being
    returned: ``allowed_company_tenants`` in ``allowlist.json`` are
    themselves lowercase ``co-...``/plain-word ids (e.g. ``co-3e543a1b...``,
    ``othercompany``), and the call site (``_decide``'s R2 block) does a plain
    ``tid not in allowed_tenants`` membership check with no case-folding of
    its own -- so tenant ids compare CASE-INSENSITIVELY end to end, by
    design: an allowlisted tenant id referenced with mixed/upper case in a
    URL (e.g. ``/COMPANY/<allowed tenant, uppercased>/x``) must still be
    recognized as the same tenant and ALLOWED, not spuriously denied as an
    unrecognized off-allowlist spelling.
    """
    found: list[str] = []
    pre = _whatwg_pre_normalize(url)
    if pre is None:
        return found
    try:
        split = urlsplit(pre)
    except ValueError:
        return found
    path = unquote(split.path).lower()
    for pat in _TENANT_URL_PATTERNS:
        for m in pat.finditer(path):
            found.append(m.group(1).lower())
    if split.query:
        qs = parse_qs(split.query)
        qs_folded: dict[str, list[str]] = {}
        for key, vals in qs.items():
            qs_folded.setdefault(key.lower(), []).extend(vals)
        for key in _TENANT_QUERY_KEYS:
            for val in qs_folded.get(key.lower(), []):
                if val:
                    found.append(val.lower())
    return found


def _extract_recipients(url: str, body: str) -> Tuple[list[str], list[str]]:
    """Parse candidate recipient emails and phones from a comms URL + body.

    Percent-decodes both (form bodies encode '+' as %2B). Returns (emails, phones).
    """
    haystack = f"{unquote(url)} {unquote(body)}"
    emails = list(dict.fromkeys(_EMAIL_RE.findall(haystack)))
    phones = list(dict.fromkeys(_PHONE_RE.findall(haystack)))
    return emails, phones


# ---------------------------------------------------------------------------
# Core policy decision (pure — the only place rules live).
# ---------------------------------------------------------------------------


def policy_decision(
    method: str,
    url: str,
    body: Optional[str] = None,
    *,
    allowlist: Optional[dict] = None,
) -> Tuple[bool, str]:
    """Decide whether a single request may proceed. FAIL-CLOSED, no I/O.

    Returns (allow, reason). ``allowlist`` defaults to the on-disk policy.

    Fix-round-12 (2026-09-12, round-5 review NON-BLOCKING 2): this function's
    own docstring says "FAIL-CLOSED", but a MALFORMED on-disk (or caller-
    supplied) ``allowlist`` -- ``allowed_origins``/``denied_action_patterns``/
    ``allowed_company_tenants`` set to ``None`` instead of a list, a list
    containing a ``None`` entry, or a non-string entry -- used to raise
    ``TypeError``/``AttributeError`` straight out of this call (e.g.
    ``for origin_pattern in allowlist.get("allowed_origins", [])`` iterating
    ``None``, or ``pat.lower()`` on a ``None``/int pattern), contradicting
    that invariant: a hook that CRASHES on bad policy input stops gating
    every subsequent request in the same process, which is the opposite of
    fail-closed. Every malformed shape above is now caught here and turned
    into an explicit, fail-closed DENY with a reason naming the malformed
    field -- never a bare exception escaping this boundary. This is
    deliberately the OUTERMOST public entry point (not scattered into every
    helper) so every internal helper keeps assuming a well-formed policy
    dict, matching every other function in this module's existing "well-
    formed input -> no need for its own defensive checks" convention; only
    the one function whose docstring makes the "never raise" promise pays
    the cost of enforcing it.
    """
    if allowlist is None:
        allowlist = load_allowlist()
    try:
        _validate_allowlist_shape(allowlist)
    except (TypeError, AttributeError) as exc:
        return False, f"deny: malformed allowlist policy ({exc}) -- fail-closed"
    # Strip before upper: a whitespace-padded "POST " must normalize to POST,
    # never slip past every method-gated rule as an unrecognized token
    # (fix-round-2 blocker, 2026-09-03 review).
    method_u = (method or "").strip().upper()
    body_s = body or ""
    try:
        return _decide(method_u, url or "", body_s, allowlist)
    except (TypeError, AttributeError) as exc:
        return False, f"deny: malformed allowlist policy ({exc}) -- fail-closed"


_ALLOWLIST_STRING_LIST_KEYS = (
    "allowed_origins",
    "denied_action_patterns",
    "allowed_company_tenants",
    "read_only_hosts",
)


def _validate_allowlist_shape(allowlist: dict) -> None:
    """Raise ``TypeError``/``AttributeError`` if *allowlist* is shaped in a
    way this module's own iteration/``.lower()``/``fnmatch`` calls would
    later raise on -- so ``policy_decision`` can catch it ONCE, up front,
    and turn it into a named fail-closed DENY reason instead of an opaque
    crash from deep inside whichever rule happened to touch the bad field
    first (fix-round-12, NON-BLOCKING 2).

    Checks the four list-of-strings policy keys every rule in this module
    iterates directly (``allowed_origins``, ``denied_action_patterns``,
    ``allowed_company_tenants``, ``read_only_hosts``): each, if present,
    must be a list/tuple of strings, never ``None`` and never containing a
    ``None``/non-string entry. ``test_recipients`` is deliberately NOT
    covered here -- ``_decide``'s R3 branch already degrades a missing/
    malformed ``test_recipients`` shape to "no test recipients configured"
    via plain ``dict.get`` calls with list defaults, never iterating a
    caller-supplied non-list, so it cannot raise the way the four keys
    above can. A key that is simply ABSENT is fine (every call site already
    uses ``allowlist.get(key, [])``); only a PRESENT-but-wrong-shaped value
    raises here.
    """
    if not isinstance(allowlist, dict):
        raise TypeError(f"allowlist must be a dict, got {type(allowlist).__name__}")
    for key in _ALLOWLIST_STRING_LIST_KEYS:
        if key not in allowlist:
            continue
        value = allowlist[key]
        if value is None:
            raise TypeError(f"{key!r} must be a list of strings, got None")
        if not isinstance(value, (list, tuple)):
            raise TypeError(
                f"{key!r} must be a list of strings, got {type(value).__name__}"
            )
        for entry in value:
            if not isinstance(entry, str):
                raise TypeError(
                    f"{key!r} entries must all be strings, found "
                    f"{type(entry).__name__} entry"
                )


def _decide(method_u: str, url: str, body_s: str, allowlist: dict) -> Tuple[bool, str]:
    """Pure rule engine (no logging). See module docstring for rule order.

    Fix-round-7 (2026-09-11) safety net, checked FIRST, before R1: a
    non-idempotent method whose url this hook cannot confidently
    pre-normalize/canonicalize to WHATWG rules (``_canonical_origin_and_path``
    returning None — an unparseable authority, a control character
    ``_whatwg_pre_normalize`` cannot strip its way past, or any other input
    that trips an exception in the canonicalization path) is DENIED outright
    rather than falling through to R0-R4. This is the documented default for
    "the canonicalizer cannot produce a confident parse" (see the module
    docstring's governing invariant): a guard that cannot understand a URL
    must not permit a write through it. An idempotent GET/HEAD to the same
    unparseable url is UNAFFECTED by this branch (falls through exactly as
    before, to whatever host `_host_of`'s own permissive fallback recovers,
    or the final default-deny-except-idempotent-reads tail below) — R0's own
    "reads are safe" rationale still holds even when the hook cannot fully
    canonicalize the url, since a read has no side effect to get wrong.
    """
    if method_u not in _IDEMPOTENT_METHODS and _canonical_origin_and_path(url) is None:
        return False, (
            f"deny: {method_u or '<missing method>'} to an unparseable/unconfident url "
            "(fail-closed: canonicalizer could not confidently parse this URL)"
        )

    denied_patterns: list[str] = allowlist.get("denied_action_patterns", [])
    allowed_tenants: list[str] = allowlist.get("allowed_company_tenants", [])
    host = _host_of(url)

    # R1: any method that is not a known-idempotent read (GET/HEAD) hitting a
    # denied (billing/comms/admin) pattern. Gated on NOT-idempotent rather than
    # membership in _NON_IDEMPOTENT_METHODS deliberately: the two sets do not
    # partition the method space, and an unrecognized token (OPTIONS, CONNECT,
    # TRACE, empty, garbage) must fall on the DENY side of every rule, never
    # slip between the sets (fix-round-2 blocker, 2026-09-03 review).
    if method_u not in _IDEMPOTENT_METHODS and _url_matches_any_pattern(url, denied_patterns):
        return False, f"deny: non-idempotent {method_u or '<missing>'} to denied_action_pattern"

    # R2: off-tenant guard — any tenant id in the URL must be allowlisted.
    # Scoped to THIS RUNTIME'S OWN product app hosts only (2026-09-11 fix):
    # a third-party host whose URL shape happens to contain a tenant-looking
    # path segment (LinkedIn's /company/<slug>, Crunchbase's
    # /organization/<slug>, G2's /products/<slug>) carries no
    # ExampleApp AI / OtherApp tenant boundary at all, so R2 must never
    # run against it — see _is_tenant_scoped_host / _TENANT_SCOPED_HOST_SUFFIXES.
    if _is_tenant_scoped_host(host):
        for tid in _extract_tenant_ids(url):
            if tid not in allowed_tenants:
                return False, f"deny: tenant {tid!r} not in allowed_company_tenants"

    # R3: any method that is not a known-idempotent read to a comms endpoint —
    # recipient must be a test_recipient. Idempotent reads (GET/HEAD) to a
    # comms-shaped path carry no side effect, so they fall through to the
    # R0/R4 host check instead. Same NOT-idempotent polarity as R1: an
    # unrecognized method to a comms path is treated as a potential send.
    if method_u not in _IDEMPOTENT_METHODS and (
        _url_matches_any_pattern(url, _comms_patterns(allowlist)) or _is_app_comms_endpoint(url)
    ):
        test_recipients = allowlist.get("test_recipients", {})
        test_emails = set(test_recipients.get("emails", []))
        test_phones = set(test_recipients.get("phones", []))
        emails, phones = _extract_recipients(url, body_s)
        if not emails and not phones:
            return False, "deny: comms endpoint with no parseable recipient"
        for email in emails:
            if email not in test_emails:
                return False, f"deny: comms to non-test recipient {email!r}"
        for phone in phones:
            if phone not in test_phones:
                return False, f"deny: comms to non-test recipient {phone!r}"
        # All parsed recipients are test recipients — fall through to host check.

    # R0 / R4: allow reads & non-idempotent methods on an allowlisted host.
    if _host_allowlisted(url, allowlist):
        if method_u in _IDEMPOTENT_METHODS:
            return True, f"allow: idempotent {method_u} to allowlisted host {host}"
        return True, f"allow: {method_u} to allowlisted host {host} (no denied pattern)"

    # Default-deny: everything except a known-idempotent read (GET/HEAD) to an
    # off-allowlist host is denied outright. The safe-read carve-out is a
    # POSITIVE membership check in _IDEMPOTENT_METHODS — an unrecognized or
    # missing method must land on the deny side, never be mislabeled an
    # "idempotent read" (fix-round-2 blocker, 2026-09-03 review). A genuine
    # GET/HEAD that reached here (no denied pattern, no off-tenant id, no bad
    # recipient) carries no side effect — allowed, logged for the audit trail.
    if method_u in _IDEMPOTENT_METHODS:
        return True, (
            f"allow: idempotent {method_u} to non-allowlisted host {host!r} (default-deny read)"
        )
    return False, (
        f"deny: {method_u or '<missing method>'} to host {host!r} not in allowed_origins "
        "(default-deny)"
    )


# ---------------------------------------------------------------------------
# Event adapter (pure) — pull (method, url, body) out of a hook event.
# ---------------------------------------------------------------------------


def _first_str(d: dict, keys: tuple[str, ...]) -> str:
    """First value in *d* under any of *keys* that is a non-empty string."""
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return ""


def extract_request(ev: dict) -> Tuple[str, str, str]:
    """Pull (method, url, body) from a hook event. Pure; never raises.

    Looks in ``tool_input`` for url/method/body under a range of key aliases so
    the same hook covers MCP Playwright browser tools and any fetch-style tool.
    When no method is given it defaults to GET — the safest read baseline; a real
    mutation tool carries an explicit method (or a URL caught by a deny pattern).
    """
    if not isinstance(ev, dict):
        return "", "", ""
    ti = ev.get("tool_input")
    if not isinstance(ti, dict):
        ti = {}

    url = _first_str(ti, _URL_KEYS)
    method = _first_str(ti, _METHOD_KEYS)

    body = ""
    for k in _BODY_KEYS:
        v = ti.get(k)
        if isinstance(v, str) and v:
            body = v
            break
        if isinstance(v, (dict, list)) and v:
            try:
                body = json.dumps(v)
            except (TypeError, ValueError):
                body = ""
            break

    if not method:
        method = "GET"
    return method.upper(), url, body


def decide_event(
    ev: dict,
    allowlist: dict,
    slot_hosts: Optional[dict] = None,
) -> Tuple[bool, str, str, str]:
    """Pure decision for a hook event. No I/O — *slot_hosts* is handed in by
    the caller (``main()`` reads it off disk; a test passes a literal dict).

    R5 (interaction-class Playwright tools with no URL of their own) is
    checked FIRST, before the ``no-url`` early return below — a rule keyed
    only on "is there a URL" would never reach a tool that never carries one.
    R5 has no opinion on any non-Playwright-interaction tool call (including
    ``browser_navigate`` itself), in which case this falls through to R0-R4
    exactly as before.

    Returns (should_block, method, url, reason). Outside of an R5 verdict,
    ``should_block`` is True only when a URL is present AND the policy denies
    it. Events carrying no URL AND no R5 verdict (the tool is not a network
    call this hook governs) are a pass-through no-op (should_block=False,
    reason "no-url").

    ``r5_decision``'s own third return element (``path_consumed``, LOW #5) is
    read here (as ``_path_consumed``) but deliberately NOT threaded through
    this function's own 4-tuple return — widening this signature would touch
    every one of this test suite's hundreds of existing ``decide_event``
    call sites for a value only ONE caller (``_main_impl``) actually needs.
    ``_main_impl`` calls ``r5_decision`` a second time, directly, to obtain
    the flag structurally rather than by parsing this function's ``reason``
    string — see its own comment for why.

    ``browser_tabs action:"new"`` CARRIES A REAL URL DESPITE BEING AN
    R5-GOVERNED INTERACTION (cold round-3 blocker B1, 2026-09-28 — see
    ``_tabs_new_url``'s own docstring for the full bug this closes): an R5
    ALLOW verdict on this specific call shape does NOT short-circuit the way
    every other R5 verdict does. Instead, R0-R4 (``policy_decision``) ALSO
    runs against that URL, and the two checks are ANDed — DENY wins if
    EITHER one denies. An R5 DENY verdict (the slot's recorded host IS
    read-only) still short-circuits exactly as before; there is no reason
    to additionally consult R0-R4 once R5 has already denied. This is
    deliberately scoped to ONLY the verified ``browser_tabs new`` shape —
    ``_tabs_new_url`` reads the literal ``"url"`` key alone, never the
    broader ``_URL_KEYS`` alias set (which includes ``"target"``, a
    genuinely different field — an element reference — on other tools);
    extending this combined-check treatment to any other R5-governed call
    shape is a separate, deliberate change, not an accidental side effect of
    this fix.
    """
    tool_name = _lib.tool_name(ev) if isinstance(ev, dict) else ""
    ti = ev.get("tool_input") if isinstance(ev, dict) else None
    ti = ti if isinstance(ti, dict) else None
    slot, action = _parse_playwright_tool(tool_name)
    r5 = r5_decision(
        tool_name,
        slot_hosts if slot_hosts is not None else {},
        allowlist,
        tool_input=ti,
    )
    if r5 is not None:
        allow, reason, _path_consumed = r5
        if not allow:
            return True, "", "", reason
        tabs_url = _tabs_new_url(action, ti)
        if not tabs_url:
            return False, "", "", reason
        r0r4_allow, r0r4_reason = policy_decision("GET", tabs_url, "", allowlist=allowlist)
        if not r0r4_allow:
            return True, "GET", tabs_url, (
                f"deny: R0-R4 on browser_tabs new URL {tabs_url!r} "
                f"(R5 said {reason!r}): {r0r4_reason}"
            )
        return False, "GET", tabs_url, f"{reason}; R0-R4 also allowed {tabs_url!r}: {r0r4_reason}"

    method, url, body = extract_request(ev)
    if not url:
        return False, method, "", "no-url"
    allow, reason = policy_decision(method, url, body, allowlist=allowlist)
    return (not allow), method, url, reason


# ---------------------------------------------------------------------------
# Thin main() — read, decide, log always, emit deny only when enforcing.
# ---------------------------------------------------------------------------


def main() -> int:
    """Hook entrypoint. Always returns 0 (deny is signalled via JSON, not exit).

    Wraps ``_main_impl`` in a catch-all so a bug or malformed-input crash
    anywhere in the decision path (B2, 2026-09-10) degrades to a DENY under
    enforcement rather than an uncaught exception propagating out of the
    hook process with no deny object emitted — the fail-OPEN shape a crash
    would otherwise produce. Log-only mode logs a ``would_deny`` instead of
    blocking, exactly like a normal would-be deny.

    ``ev`` is read BEFORE the ``try`` (m3, 2026-09-10 review) so the recovery
    path below can resolve enforcement against the EVENT's own cwd
    (``_lib.enforcing(_lib.cwd(ev))``), exactly like the normal path in
    ``_main_impl`` — a bare ``_lib.enforcing()`` call resolves against the
    hook PROCESS's cwd instead, which is the wrong repo whenever the event
    fired from a different one. Reading the event itself is assumed safe
    (``_lib.read_event`` already degrades to ``{}`` on any parse error); if
    that assumption is ever wrong, the recovery body's own inner catch-all
    below still stops the exception from escaping uncaught.
    """
    ev: dict = {}
    try:
        ev = _lib.read_event()
        return _main_impl(ev)
    except Exception as exc:  # noqa: BLE001 - deliberate catch-all, see docstring
        return _recover_from_hook_error(exc, ev)


def _recover_from_hook_error(exc: Exception, ev: dict) -> int:
    """The catch-all recovery body for ``main()``.

    Wrapped in its OWN ``try/except`` (m2, 2026-09-10 review): every call
    here (``_lib.disabled``, ``_lib.enforcing``, ``_lib.log``,
    ``_lib.emit_pretooluse_deny``) is otherwise unprotected, so a bug in ANY
    of them would let the original exception (or a new one) escape with no
    deny object ever emitted — the exact fail-OPEN shape this whole catch-all
    exists to prevent. On any failure here, fall back to printing a LITERAL
    deny object (the same shape ``_lib.emit_pretooluse_deny`` produces) and
    return 0 — this fallback must never depend on anything that can raise.
    """
    reason = f"hook-error: {type(exc).__name__} (fail-closed)"
    try:
        try:
            _lib.log(HOOK_NAME, "hook-error", error=str(exc), error_type=type(exc).__name__)
        except Exception:  # pragma: no cover - logging must never mask the deny
            pass
        if _lib.disabled():
            return 0
        enforce = _lib.enforcing(_lib.cwd(ev))
        if enforce:
            _lib.log(HOOK_NAME, "deny", reason=reason)
            _lib.emit_pretooluse_deny(f"[{HOOK_NAME}] blocked prod mutation: {reason}")
        else:
            _lib.log(HOOK_NAME, "log-only", reason=reason, would_deny=True)
        return 0
    except Exception:  # noqa: BLE001 - the fallback of last resort, see docstring
        msg = f"[{HOOK_NAME}] blocked prod mutation: {reason}"
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": msg,
                    },
                    "systemMessage": msg,
                }
            )
        )
        return 0


def _main_impl(ev: dict) -> int:
    """The real hook body — see ``main``'s docstring for the crash wrapper.

    ``ev`` is read by ``main()`` (not here) so the catch-all recovery path
    (m3, 2026-09-10 review) has the event available to resolve enforcement
    against its cwd even when everything below this point raises.
    """
    # Master OFF — a disabled hook is a total no-op.
    if _lib.disabled():
        return 0

    allowlist = load_allowlist()
    tool_name = _lib.tool_name(ev)
    slot, action = _parse_playwright_tool(tool_name)
    ti = ev.get("tool_input") if isinstance(ev, dict) else None
    ti = ti if isinstance(ti, dict) else None

    # R5 state I/O lives here (the thin shell / small adapter), never inside
    # the pure r5_decision function.
    #
    # cold round-4 blocker B1 (2026-09-28): a host-setting call (a plain
    # ``browser_navigate``, or a ``browser_tabs action:"new"`` carrying a
    # ``url`` — cold round-3 blocker B1) used to have its NEW host recorded
    # BEFORE ``decide_event`` ran — so even when R0-R4 went on to DENY that
    # URL (off-tenant, admin, Stripe, ...), the slot's recorded host had
    # ALREADY been overwritten to the denied destination. A SUBSEQUENT
    # interaction (e.g. ``browser_evaluate``) was then judged against that
    # wrongly-recorded host instead of the real, still-loaded prior page —
    # a denied navigate to staging left a production slot's record reading
    # "staging", so a later ``document.cookie`` read on the STILL-LOADED
    # production page sailed through as "not read-only" / staging-scoped.
    # This predated round 4 for plain ``browser_navigate`` (it was never
    # actually round-3-B1-specific) and was newly introduced for
    # ``browser_tabs new`` by round 3's own fix.
    #
    # FIX: the host is now recorded ONLY AFTER ``decide_event`` has decided.
    # An ALLOWED navigate/tabs-new records the new host (the browser actually
    # went there). A DENIED navigate/tabs-new CLEARS the host instead of
    # leaving the OLD value standing — the coordinator's own instruction:
    # "with deny, also clear, since the old page is still loaded under an
    # unknown state" (an agent that attempted an off-tenant/admin/Stripe
    # navigate is itself a signal not to keep trusting whatever the slot
    # last legitimately recorded). This mirrors R5's own "no host recorded"
    # fail-closed default — the next interaction on this slot is denied
    # until a fresh, ALLOWED navigate re-establishes a real host.
    #
    # ``browser_close`` still clears immediately (before the decision) — R5
    # never denies it either way (see module docstring), and closing the
    # page always ends this slot's session on it regardless of any decision.
    #
    # cold round-3 review (2026-09-28), CORRECTED round-4 (2026-09-28):
    # ``browser_navigate_back``, ``browser_navigate_forward``, and
    # ``browser_tabs action:"select"``/``"close"`` (round-4 addition: an
    # adjacent tab becomes current on close, exactly like select) all change
    # what page is loaded in the slot WITHOUT going through
    # ``record_navigate_host`` (none carries a URL this hook could record).
    # These must clear the slot's host to invalidate it — but round-4 found
    # that clearing BEFORE the decision (round-3's original placement) wrongly
    # denies the call ITSELF: all four of these actions are NOT
    # read-only-host-safe (only ``tabs list`` is), so R5 treats them as
    # interactions requiring a recorded host — clearing the record first
    # made R5 see "no host recorded" and deny the very call meant to move to
    # a DIFFERENT already-open tab/history entry, which is not itself a
    # read of the CURRENT (still-loaded) page's content. The clear now
    # happens AFTER the decision: the call runs against the CURRENT (still
    # accurate) host record, and — regardless of whether R5 allowed or
    # denied it — the record is THEN invalidated, so the NEXT interaction on
    # this slot fails closed until a fresh navigate re-establishes a host.
    tabs_new_url = _tabs_new_url(action, ti)
    tabs_subaction = ti.get("action") if isinstance(ti, dict) else None
    is_host_setting = slot and (action == _NAVIGATE_ACTION or tabs_new_url)
    invalidates_after = slot and (
        action in (_NAVIGATE_BACK_ACTION, _NAVIGATE_FORWARD_ACTION)
        or (action == _TABS_ACTION and tabs_subaction in (_TABS_SELECT_SUBACTION, _TABS_CLOSE_SUBACTION))
    )
    if slot and action == _CLOSE_ACTION:
        clear_slot_host(slot)

    slot_hosts = read_slot_hosts()
    should_block, method, url, reason = decide_event(ev, allowlist, slot_hosts)

    # LOW #5 (2026-09-29 cold review): whether this call consumed the slot's
    # recorded PATH is read STRUCTURALLY from r5_decision's own third return
    # element, never by matching a substring in decide_event's human-readable
    # `reason` string (the prior round's approach, which coupled a real
    # decision to a message never meant to be machine-parsed). r5_decision is
    # PURE and deterministic given the same (tool_name, slot_hosts,
    # allowlist, tool_input) — calling it a second time here, directly,
    # reproduces the exact same verdict decide_event already computed
    # (confirmed by `should_block`/`path_consumed` agreeing below) without
    # widening decide_event's own 4-tuple return, which every other caller in
    # this test suite still relies on.
    r5_repeat = r5_decision(tool_name, slot_hosts, allowlist, tool_input=ti)
    path_consumed = bool(r5_repeat is not None and not should_block and r5_repeat[2])

    if is_host_setting:
        if should_block:
            clear_slot_host(slot)
        else:
            nav_url = tabs_new_url if tabs_new_url else extract_request(ev)[1]
            record_navigate_host(slot, nav_url)
    elif invalidates_after:
        clear_slot_host(slot)
    elif slot and path_consumed:
        # 2026-09-29, cold review B3/B2 hardening fallback (see
        # clear_slot_path's own docstring for why a same-call page-URL
        # re-check is structurally unavailable via PostToolUse): an
        # interaction-class call just ALLOWED under
        # interactive_production_hosts consumes the slot's recorded PATH —
        # the very next interaction-class call on this slot requires a fresh
        # browser_navigate to re-establish a path, bounding how far a single
        # click-triggered navigation can silently ride on a stale path.
        clear_slot_path(slot)

    # Pass-through: not a governed network call AND no R5 verdict. R5 fires
    # with no URL at all (interaction-class tools carry none), so gating this
    # early-return on `should_block` too (not just `url`) is what keeps an R5
    # deny from being silently dropped here. An R5 ALLOW verdict (the
    # session-banner exemption, or a plain "not read-only" allow) used to hit
    # this SAME early return with no url and should_block=False, so it was
    # NEVER logged at all — reaching `log_action`/`_lib.log` below now
    # requires only that this be a genuinely ungoverned call (no URL, no R5
    # opinion of ANY kind); an R5 verdict's `reason` string always starts
    # with "allow:"/"deny:" (see r5_decision), which is what distinguishes
    # "R5 had an opinion" from "this call carries no URL and R5 never looked
    # at it" here.
    r5_had_an_opinion = reason.startswith("allow:") or reason.startswith("deny:")
    if not url and not should_block and not r5_had_an_opinion:
        return 0

    # Always append to the prod_actions audit trail (allow == not should_block).
    # An R5 verdict carries no URL; log_action still records the decision
    # (empty url/method fields) so the audit trail has a row for it too.
    log_action(method, url, not should_block, reason)

    if not should_block:
        _lib.log(HOOK_NAME, "allow", method=method, url=url, reason=reason)
        return 0

    enforce = _lib.enforcing(_lib.cwd(ev))
    if enforce:
        _lib.log(HOOK_NAME, "deny", method=method, url=url, reason=reason)
        _lib.emit_pretooluse_deny(f"[{HOOK_NAME}] blocked prod mutation: {reason}")
    else:
        # LOG-ONLY: record the would-be deny but do NOT block the tool call.
        _lib.log(HOOK_NAME, "log-only", method=method, url=url, reason=reason, would_deny=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())  # pragma: no cover
