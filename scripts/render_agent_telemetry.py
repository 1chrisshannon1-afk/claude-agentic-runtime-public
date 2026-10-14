#!/usr/bin/env python3
"""Agent-telemetry dashboard renderer -- Phase 4 of the agent-telemetry plan.

Reads `hooks/agent_telemetry.py`'s collected metrics (Phase 1) plus
`hooks/churn_report.py`'s friction and convergence metrics, and emits ONE
self-contained HTML file. This module RENDERS; it computes no metric of its
own that another module already owns.

    python3 ~/.claude/scripts/render_agent_telemetry.py --open

=============================================================================
STOP CONDITION (plan §7.3)
=============================================================================

    DONE when the verdict line + all five tiles render correctly with
    declared denominators -- tile 3 in its v1 `contests/day` form. Every
    panel beyond that requires a named question the operator actually asked.

Do not add panels to this page without that named question. The plan's own
reader obligation: after 30 days, if the dashboard has not informed a
decision, CUT panels rather than add them. AA-0084 (a 393 KB unlinked
duplicate dashboard with no generator) is live proof this runtime already
produces unread status surfaces.

=============================================================================
WHAT THIS FILE DELIBERATELY DOES NOT DO
=============================================================================

1. IT COMPUTES NO METRIC THAT ALREADY EXISTS (plan §1.4: extend, never fork).
   Friction (tile 3) is `churn_report.churn_and_contested_by_day()`.
   Convergence (tile 4) is `churn_report.review_round_convergence()`.
   Everything else is `agent_telemetry.collect_all()`. This module imports
   all three; a fork would drift from the surface it duplicates, and the
   inventory already found two independent implementations of
   denials-by-reason. There must not be a third of anything.

2. IT NEVER PLOTS `tokens_total` (plan §1.3). Every panel declares its
   `source`, and `assert_no_tokens_total_headline()` is called over the full
   panel list BEFORE any HTML is written -- so this is a mechanical refusal,
   not a promise. See `PANELS`.

3. IT NEVER RENDERS A BARE PERCENTAGE. Every rate on the page carries the
   denominator it was computed over, because a percentage without one is
   unfalsifiable. `pct()` takes the denominator as a required argument for
   exactly this reason.

4. IT NEVER SILENTLY PRICES AN UNPRICEABLE ROW AT $0. `spend_usd()` excludes
   them and counts them by refusal reason; this page renders that exclusion
   as visible text next to every dollar figure, plus the price-table version.

5. NO EXTERNAL RESOURCE, EVER. All CSS and JS inline, no CDN, no webfont, no
   image host. Charts are hand-rolled inline SVG (`<rect>`/`<polyline>`/
   `<text>`), so the page renders offline and with JS disabled. `--verify`
   greps the output for `http://`/`https://` in resource position and FAILS
   the build if any appears.

=============================================================================
CHART RULES (plan §7.4, and the reasons behind them)
=============================================================================

* Zero-based axes on every bar chart. A truncated axis makes a 3% difference
  look like a 3x one.
* Stacked BAR for spend-over-time, never stacked area: an area chart's
  moving baseline makes every series except the bottom one unreadable.
* Max 4 model bands; the remainder collapses into an explicit `other` band,
  never dropped.
* No dual-axis charts, no pie charts, no gauges (plan §8).
* `unattributed` is ALWAYS its own visible bar, never hidden and never
  folded into a neighbour.

Tile 5 (cache) is a BINARY STATE, never a percentage, and this is
deliberate (plan §7.1): a rendered cache-hit-rate number is trivially
Goodharted by never changing a prompt. The state answers the operator's
actual question -- "did something bust the prefix, and whose prompt was it"
-- and names the agent type. The rate itself lives in the Layer-4 health
panel as a diagnostic figure.
"""

from __future__ import annotations

import argparse
import datetime
import html
import os
import sqlite3
import statistics
import subprocess
import sys
from typing import Any, Mapping, Sequence

_HOOKS_DIR = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

import agent_telemetry as at  # noqa: E402
import churn_report as cr  # noqa: E402

DEFAULT_OUT = os.path.join(
    os.path.expanduser("~"), ".claude", "telemetry", "agent_telemetry.html"
)

# Cache tile threshold: an agent type sitting this many percentage points
# below the peer median reads as "prefix invalidated". A TRIPWIRE, not a
# target.
CACHE_DROP_PP = 10.0

# Fleet-level floor. Below this, the prefix is considered broken regardless
# of any per-agent movement.
CACHE_FLOOR = 0.90

# Minimum rows before an agent type may TRIP the tile.
#
# `cache_detail(min_rows=5)` already refuses to publish a RATE below 5 rows,
# but 5 is far too thin to raise an alarm on: measured live, the worst-rate
# agent type was `browser-ops` at n=6, and a 12pp gap off six rows is noise.
# Firing there is the same defect the collector guards against by suppressing
# p99 below n=100 -- "one data point wearing a statistical costume" -- and a
# tripwire that cries wolf on noise trains the operator to ignore it, which
# costs more than not having the tile. An agent type below this floor is
# still RATED in the health panel; it just cannot raise the alarm alone.
CACHE_ALARM_MIN_ROWS = 30

MAX_MODEL_BANDS = 4

# ---------------------------------------------------------------------------
# SUBSCRIPTION ECONOMICS (added 2026-09-06, operator finding).
#
# The operator runs SIX Claude Max seats at $200/mo each -- $1,200/mo FIXED,
# not metered API billing. The console shows only "percent of quota used,"
# no dollars, no credits. Marginal cost per call is therefore effectively
# ZERO, and every dollar figure this page renders is an API-EQUIVALENT
# VALUE -- what the same usage would cost on metered billing -- never money
# actually spent. This constant is DECLARED (configuration the operator told
# this runtime, not something measured from any ledger), exactly like
# `agent_telemetry.PRICE_TABLE_VERSION` is declared rather than derived; if
# the seat count or price ever changes, this is the one place to update it
# (no second copy of this number exists anywhere else in the runtime as of
# this writing -- checked `~/.claude/knowledge/` and `hooks/`; the only other
# mention is prose in `cost_strategist_primer.md`, not a value any code
# reads).
# ---------------------------------------------------------------------------
CLAUDE_MAX_SEATS = 6
CLAUDE_MAX_SEAT_MONTHLY_USD = 200.0
CLAUDE_MAX_FIXED_MONTHLY_USD = CLAUDE_MAX_SEATS * CLAUDE_MAX_SEAT_MONTHLY_USD  # $1,200/mo


# ---------------------------------------------------------------------------
# Small formatting helpers. Every one of these carries a denominator or a
# provenance -- there is no bare-number formatter in this module on purpose.
# ---------------------------------------------------------------------------


def esc(text: object) -> str:
    return html.escape(str(text), quote=True)


def usd(amount: float) -> str:
    if amount >= 1000:
        return f"${amount:,.0f}"
    if amount >= 10:
        return f"${amount:,.2f}"
    return f"${amount:.3f}"


def pct(numerator: float, denominator: float, digits: int = 1) -> str:
    """Percentage WITH its denominator. The denominator is required.

    A bare percentage is unfalsifiable -- "97%" could be 97 of 100 or 970,000
    of 1,000,000, and those two carry completely different confidence. The
    plan calls a denominator-less percentage a defect, so this function
    cannot produce one.
    """
    if not denominator:
        return "n/a (denominator 0)"
    return f"{100.0 * numerator / denominator:.{digits}f}% of {int(denominator):,}"


def num(value: object) -> str:
    if isinstance(value, bool) or value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}"
    return str(value)


def vget(container: object, *path: str, default: object = None) -> object:
    """Read a possibly-Value-wrapped field out of the collector's JSON form.

    `collect_all()` returns live `Value` objects; `--json` returns their
    `{value, provenance, source}` dict form. This renderer accepts either, so
    it works against a live call and against a saved snapshot identically.
    """
    cur: object = container
    for key in path:
        if isinstance(cur, at.Value):
            cur = cur.to_dict()
        if not isinstance(cur, Mapping):
            return default
        if key not in cur:
            return default
        cur = cur[key]
    if isinstance(cur, at.Value):
        cur = cur.to_dict()
    if isinstance(cur, Mapping) and set(cur.keys()) >= {"value", "provenance", "source"}:
        return cur.get("value", default)
    return cur if cur is not None else default


def vprov(container: object, *path: str) -> str:
    """The provenance string of a wrapped value, or '' when not wrapped."""
    cur: object = container
    for key in path:
        if isinstance(cur, at.Value):
            cur = cur.to_dict()
        if not isinstance(cur, Mapping) or key not in cur:
            return ""
        cur = cur[key]
    if isinstance(cur, at.Value):
        cur = cur.to_dict()
    if isinstance(cur, Mapping):
        return str(cur.get("provenance", ""))
    return ""


def day_seq(days: int, end: datetime.date) -> list[str]:
    return [(end - datetime.timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]


# ---------------------------------------------------------------------------
# Inline SVG primitives. Hand-rolled per plan §7.4 -- vendoring a charting
# library to satisfy three chart types on a static page is a dependency this
# page does not need, and no CDN is permitted anyway.
# ---------------------------------------------------------------------------


def sparkline(values: Sequence[float], width: int = 132, height: int = 30) -> str:
    """A bare trend shape. No axis, no label -- it sits beside a number that
    already carries the units, and adding a second scale would imply a
    precision a 130px shape does not have."""
    pts = [float(v) for v in values if isinstance(v, (int, float))]
    if len(pts) < 2:
        return (
            f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" '
            f'height="{height}" role="img" aria-label="not enough points">'
            f'<text x="2" y="{height - 10}" class="sparkempty">n&lt;2</text></svg>'
        )
    lo, hi = min(pts), max(pts)
    span = (hi - lo) or 1.0
    step = width / (len(pts) - 1)
    coords = []
    for i, v in enumerate(pts):
        x = i * step
        y = height - 3 - ((v - lo) / span) * (height - 6)
        coords.append(f"{x:.1f},{y:.1f}")
    last_x, last_y = coords[-1].split(",")
    label = f"{len(pts)} points, {lo:,.4g} to {hi:,.4g}"
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" width="{width}" height="{height}" '
        f'role="img" aria-label="{esc(label)}">'
        f'<title>{esc(label)}</title>'
        f'<polyline points="{" ".join(coords)}" fill="none" stroke="currentColor" '
        f'stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2.2" fill="currentColor"/>'
        f"</svg>"
    )


def ranked_bar_chart(
    rows: Sequence[tuple[str, float]],
    unit: str,
    highlight: str | None = None,
    fmt=None,
    titles: Mapping[str, str] | None = None,
) -> str:
    """Ranked horizontal bars on a ZERO-BASED scale.

    Zero-based is not a style choice: a bar chart's length IS its value, so a
    truncated baseline misstates every comparison on the chart. `highlight`
    marks a bar that must remain visually distinct (used for the explicit
    `unattributed` bar, which the plan forbids hiding). `titles` maps a
    displayed label to its FULL untruncated text for the hover tooltip, so
    shortening a label for width never destroys the information behind it.
    """
    if not rows:
        return '<p class="empty">No data in window.</p>'
    fmt = fmt or (lambda v: num(v))
    titles = titles or {}
    top = max(v for _, v in rows) or 1.0
    out = ['<div class="rank">']
    for label, value in rows:
        width = max(0.4, 100.0 * float(value) / top)  # zero-based: 0 -> 0 width
        cls = "bar hl" if (highlight and label == highlight) else "bar"
        full = titles.get(label, label)
        out.append(
            f'<div class="rankrow"><span class="ranklabel" title="{esc(full)}">{esc(label)}</span>'
            f'<span class="barwrap"><span class="{cls}" style="width:{width:.2f}%">'
            f'<span class="sr">{esc(fmt(value))} {esc(unit)}</span></span></span>'
            f'<span class="rankval">{esc(fmt(value))}</span></div>'
        )
    out.append("</div>")
    return "".join(out)


def stacked_bar_chart(
    days: Sequence[str],
    series: Sequence[tuple[str, list[float]]],
    fmt=None,
) -> str:
    """Stacked BAR (never stacked area) on a zero-based y-axis.

    Stacked area is rejected by the plan: every series above the bottom one
    sits on a moving baseline, so its shape encodes the sum of everything
    below it rather than its own movement. Discrete bars have no baseline
    to move.
    """
    fmt = fmt or usd
    if not days or not series:
        return '<p class="empty">No data in window.</p>'
    totals = [sum(s[1][i] for s in series) for i in range(len(days))]
    top = max(totals) or 1.0
    w, h = 760, 210
    pad_l, pad_b, pad_t = 54, 44, 10
    plot_h = h - pad_b - pad_t
    plot_w = w - pad_l - 8
    slot = plot_w / max(1, len(days))
    bar_w = min(46.0, slot * 0.68)

    parts = [
        f'<svg class="chart" viewBox="0 0 {w} {h}" width="100%" height="{h}" role="img" '
        f'aria-label="Spend per day by model family, stacked bars, zero-based axis">'
    ]
    # Zero-based gridlines, labelled.
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = pad_t + plot_h - frac * plot_h
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{w - 8}" y2="{y:.1f}" class="grid"/>'
            f'<text x="{pad_l - 6}" y="{y + 3.5:.1f}" class="axis" text-anchor="end">'
            f"{esc(fmt(top * frac))}</text>"
        )
    for i, day in enumerate(days):
        x = pad_l + i * slot + (slot - bar_w) / 2
        y_cursor = pad_t + plot_h
        for band_i, (name, values) in enumerate(series):
            value = values[i]
            if value <= 0:
                continue
            bh = (value / top) * plot_h
            y_cursor -= bh
            parts.append(
                f'<rect x="{x:.1f}" y="{y_cursor:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                f'class="band b{band_i}"><title>{esc(day)} · {esc(name)} · '
                f"{esc(fmt(value))}</title></rect>"
            )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{h - pad_b + 15}" class="axis" '
            f'text-anchor="middle" transform="rotate(-40 {x + bar_w / 2:.1f} {h - pad_b + 15})">'
            f"{esc(day[5:])}</text>"
        )
    parts.append(
        f'<line x1="{pad_l}" y1="{pad_t + plot_h}" x2="{w - 8}" y2="{pad_t + plot_h}" '
        f'class="axisline"/>'
    )
    parts.append("</svg>")
    legend = " ".join(
        f'<span class="key"><i class="sw b{i}"></i>{esc(name)}</span>'
        for i, (name, _) in enumerate(series)
    )
    return "".join(parts) + f'<div class="legend">{legend}</div>'


# ---------------------------------------------------------------------------
# Data assembly. Each function returns a small dict the template renders --
# no HTML is built here, and no metric is computed that a module already owns.
# ---------------------------------------------------------------------------


def load_metrics(
    ledger: str | None,
    projects_root: str | None,
    days: int,
    include_transcripts: bool,
    ingest: bool = True,
) -> dict[str, Any]:
    """Pull every input from its owning module. Nothing is recomputed here.

    `ingest` defaults to True because THIS module's own render is the moment
    freshness matters -- ccdash is an incremental scanner nothing runs
    automatically, and a stale store silently understates every figure.

    An EMBEDDING caller passes `ingest=False`. Generating a document is a read;
    it should not trigger a SQLite write as a side effect, and the scan costs
    ~14s against a live store. The Operator Hub's generator does exactly this
    (it calls the panel 37 times across its own test suite).
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    tel = at.collect_all(
        ledger_path=ledger,
        projects_root=projects_root,
        include_transcripts=include_transcripts,
        # Refresh ccdash before reading. It is an INCREMENTAL scanner nothing
        # runs automatically; measured 2026-09-05 it was 2 days stale and
        # missing 45% of the 7-day window, silently understating every figure
        # on this page. A render is exactly the moment freshness matters --
        # but an embedding caller passes ingest=False (see the docstring).
        ingest=ingest,
    )

    friction: dict[str, Any] = {"error": None}
    convergence: dict[str, Any] = {"error": None}
    try:
        entries, _ = cr.read_jsonl(cr.LEDGER_ENFORCEMENT_LOG)
        # Metric 3 -- the authoritative contest definition. `contested-paths`
        # is a REASON under decision `would-block`, not a decision of its own;
        # re-deriving that here is exactly the fork the plan forbids.
        friction = cr.churn_and_contested_by_day(entries, days, now)
    except Exception as exc:  # pragma: no cover - degradation path
        friction = {"error": f"{type(exc).__name__}: {exc}"}
    try:
        with open(cr.LEDGER_LAST_REVIEWED, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        convergence = cr.review_round_convergence(lines, entries, days, now)
    except Exception as exc:  # pragma: no cover - degradation path
        convergence = {"error": f"{type(exc).__name__}: {exc}"}

    # Raw rows, re-read once, so a windowed metric can be computed over the
    # SAME rows the collector saw rather than mixing a lifetime subtotal into
    # a windowed headline. Read failures degrade to "split unavailable".
    try:
        raw_rows, _ = at.read_ledger(ledger or at.default_ledger_path())
    except Exception:  # pragma: no cover - degradation path
        raw_rows = None

    # ccdash-backed metrics, WINDOWED to this page's own `days` -- unlike
    # `tel["ccdash_*"]` above (which `collect_all()` computes lifetime, for
    # the --json CLI consumer), every ccdash panel on THIS page must share
    # the same `days` window as every other tile or a reader has no way to
    # tell a lifetime figure from a 7-day one sitting next to it. Computed
    # here rather than inside `collect_all()` because `days` is a rendering
    # concern the collector does not otherwise take a parameter for.
    since_iso = (now - datetime.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        ccdash_token_split_windowed = at.ccdash_token_split(since_iso=since_iso)
    except Exception as exc:  # pragma: no cover - degradation path
        ccdash_token_split_windowed = {"ccdash_available": False, "reason": f"{type(exc).__name__}: {exc}"}
    try:
        ccdash_cache_ttl_windowed = at.ccdash_cache_ttl_split(since_iso=since_iso)
    except Exception as exc:  # pragma: no cover - degradation path
        ccdash_cache_ttl_windowed = {"ccdash_available": False, "reason": f"{type(exc).__name__}: {exc}"}
    try:
        ccdash_spend_windowed = at.ccdash_spend_by_model(since_iso=since_iso)
    except Exception as exc:  # pragma: no cover - degradation path
        ccdash_spend_windowed = {"ccdash_available": False, "reason": f"{type(exc).__name__}: {exc}"}
    # ACCOUNT CAPACITY IS DELIBERATELY *NOT* SHARED WITH THIS PAGE'S `days`
    # PARAMETER (corrected 2026-09-06, operator-verified finding).
    #
    # Every other ccdash panel above windows to `days` because they are
    # ACTIVITY questions ("what happened recently") with no natural period
    # of their own. Account capacity is different: Claude Max quota resets
    # MONTHLY, so the billing period -- not whatever `days` this page was
    # asked to render -- is the correct denominator for "am I load-balancing
    # across paid capacity." A 7-day slice of a monthly cycle is not a
    # smaller version of the same picture; it is a DIFFERENT one that can
    # disagree with the 30-day one in direction, not just in magnitude.
    #
    # MEASURED, same deduped query, same moment (2026-09-06): the 7-day
    # window showed account 1 at 81.6% with four accounts flagged idle; the
    # 30-day (one full billing-period) window showed a genuinely BALANCED
    # 35.1/18.8/15.3/11.8/10.4/8.6 split with ZERO idle accounts. A tile
    # windowed to 7 days alone would have reported "one account carries
    # everything, the rest sit idle" -- false at the billing-period level,
    # which is the level a capacity decision actually needs. So this page
    # computes BOTH windows unconditionally and shows both, explicitly
    # labeled, rather than picking one -- the disagreement between them IS
    # the finding (see `account_balance_tile()`).
    # Imported, NOT re-declared: a second copy of this policy fact is how the
    # collector and the page drift apart (review blocker 2 -- the renderer had
    # its own literal 30 while the collector had BILLING_PERIOD_DAYS).
    billing_since_iso = (now - datetime.timedelta(days=at.BILLING_PERIOD_DAYS)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    try:
        account_capacity_30d = at.account_capacity(since_iso=billing_since_iso)
    except Exception as exc:  # pragma: no cover - degradation path
        account_capacity_30d = {"ccdash_available": False, "reason": f"{type(exc).__name__}: {exc}"}
    try:
        # The page's own `days` window too (usually 7) -- shown ALONGSIDE
        # the 30-day figure, never instead of it, specifically so a burst on
        # the short window is visible as a burst rather than mistaken for a
        # structural imbalance (requirement 3).
        account_capacity_recent = (
            account_capacity_30d
            if days == at.BILLING_PERIOD_DAYS
            else at.account_capacity(since_iso=since_iso)
        )
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, at.PartitionError) as exc:
        # NARROW, deliberately. A bare `except Exception` here laundered a
        # NameError -- a one-word typo from deleting a duplicated constant --
        # into "ccdash unavailable", so the operator saw a DATA problem where
        # there was a CODE problem, and the recent-window panel silently died
        # on every render while the suite stayed green. Data/IO failures still
        # degrade; a programming error now surfaces as itself.
        account_capacity_recent = {"ccdash_available": False, "reason": f"{type(exc).__name__}: {exc}"}

    return {
        "telemetry": tel,
        "friction": friction,
        "convergence": convergence,
        "rows": raw_rows,
        "days": days,
        "now": now,
        "ccdash_token_split": ccdash_token_split_windowed,
        "ccdash_cache_ttl_split": ccdash_cache_ttl_windowed,
        "ccdash_spend_by_model": ccdash_spend_windowed,
        # TWO windows, both always computed -- see the comment above. `_30d`
        # is the PRIMARY (billing-period) figure; `_recent` is the page's own
        # `days` window (usually 7d) for "what is happening right now."
        "account_capacity_30d": account_capacity_30d,
        "account_capacity_recent": account_capacity_recent,
        "account_capacity_recent_days": days,
        # `quality_outcomes` (tel["quality_outcomes"]) is deliberately NOT
        # re-windowed here: it is a bounded, small corpus of loop rounds (19
        # cycle files total, not a rolling ~11-day ledger), so "the last N
        # days" has no natural meaning against it the way it does for
        # spend.jsonl/ccdash -- the whole convergence trend IS the point.
    }


def leverage_tile(ccdash_spend: Mapping[str, Any], days: int) -> dict[str, Any]:
    """Tile -- LEVERAGE, replacing "Spend" as the headline dollar tile.

    THE RE-FRAME (2026-09-06, operator finding): six Claude Max seats cost
    $1,200/mo FIXED, not metered API billing -- the console shows only
    "percent of quota used," never a dollar figure. Marginal cost per call
    is therefore effectively ZERO, so presenting a dollar total as "spend"
    implies a variable cost that does not exist. This tile states the same
    dollar figure the old spend tile would have, but reframed as what that
    usage would have cost on METERED billing, set against the real fixed
    cost -- "83x return on $1,200/mo" rather than "$23,250 spent."

    SOURCE: `ccdash_spend_by_model` (COMPLETE data), never `spend_usd`
    (spend.jsonl-sourced, only ~50% priced) -- the same choice
    `chart_ccdash_spend_by_model` already makes and for the same reason:
    presenting the api-equivalent VALUE headline off a half-priced source
    would understate leverage by roughly 2x.

    Dollars stay VISIBLE (never hidden -- the operator's own directive was
    "dollars stay visible but explicitly labeled") but every occurrence in
    this tile's own text is qualified as "what this would cost on metered
    API," never as money spent.
    """
    if not ccdash_spend.get("ccdash_available"):
        return {"error": ccdash_spend.get("reason", "ccdash unavailable")}
    total = vget(ccdash_spend, "total_usd")
    if not isinstance(total, (int, float)):
        return {"error": "no priced ccdash rows in window"}
    n = int(vget(ccdash_spend, "n", default=0))
    rows_seen = int(ccdash_spend.get("rows_seen", n))
    fixed_cost = CLAUDE_MAX_FIXED_MONTHLY_USD
    # The fixed cost is a MONTHLY figure; the window may not be exactly 30
    # days, so the ratio is computed against the fixed cost PRORATED to the
    # window length -- comparing a 7-day api-equivalent value against a full
    # month's fixed cost would understate leverage by roughly 4x for no
    # reason connected to the underlying economics.
    prorated_fixed_cost = fixed_cost * (days / 30.0)
    ratio = (float(total) / prorated_fixed_cost) if prorated_fixed_cost > 0 else None
    return {
        "error": None,
        "value": f"{ratio:,.0f}x" if ratio is not None else "n/a",
        "raw": float(total),
        "delta": (
            f"{usd(float(total))} in metered-API-equivalent value over {days} days, "
            f"against {usd(prorated_fixed_cost)} of this window's share of the "
            f"${fixed_cost:,.0f}/mo fixed subscription cost"
        ),
        "direction": "flat",
        "spark": [],
        "denominator": (
            f"{pct(n, rows_seen)} priced ccdash usage records over {days} days"
        ),
        "api_equivalent_usd": float(total),
        "fixed_cost_usd": fixed_cost,
        "prorated_fixed_cost_usd": prorated_fixed_cost,
        "seats": CLAUDE_MAX_SEATS,
        "seat_monthly_usd": CLAUDE_MAX_SEAT_MONTHLY_USD,
        "ratio": ratio,
    }


def account_balance_tile(
    account_capacity_30d: Mapping[str, Any],
    account_capacity_recent: Mapping[str, Any],
    recent_days: int,
) -> dict[str, Any]:
    """Tile -- ACCOUNT BALANCE: is any account at risk of exhausting its
    MONTHLY quota before the reset, while others still have headroom.

    RE-FRAMED 2026-09-06 (operator-verified correction). The prior version
    of this tile read a 7-day-only share as "one account carries everything,
    the rest sit idle" and recommended routing work off the idle accounts.
    That premise was FALSE at the billing-period level: Claude Max quota
    resets MONTHLY, and measured over a full 30-day window the SAME six
    accounts run a genuinely BALANCED 35/19/15/12/10/9 split with zero idle
    accounts -- the 7-day figure was a recent burst on one account, not a
    structural pattern. Reporting "idle capacity" off a 7-day slice of a
    30-day cycle was exactly the windowing hazard that produces a
    confident, false answer.

    THE CORRECTED QUESTION is rate-of-consumption against a monthly cap, not
    idleness: is any account's RECENT share running meaningfully hotter
    than its own 30-day baseline share (a real early-warning signal for a
    quota-exhaustion risk), rather than "is any account below some fixed
    floor" (which is not a risk at all if quota resets monthly and every
    account gets used across the month, as measured here).

    BOTH windows are ALWAYS shown, explicitly, because they disagree and the
    disagreement itself is the finding (requirement 3) -- this function
    never picks one window and hides the other.
    """
    if not account_capacity_30d.get("ccdash_available"):
        return {"error": account_capacity_30d.get("reason", "ccdash unavailable")}
    accounts_30d = account_capacity_30d.get("accounts") or {}
    if not accounts_30d:
        return {"error": "no attributed accounts in the 30-day window"}
    ranked_30d = sorted(
        accounts_30d.items(), key=lambda kv: -float(vget(kv[1], "share_of_attributed_calls", default=0.0))
    )
    accounts_recent = (
        account_capacity_recent.get("accounts") or {}
        if account_capacity_recent.get("ccdash_available")
        else {}
    )
    ranked_recent = sorted(
        accounts_recent.items(), key=lambda kv: -float(vget(kv[1], "share_of_attributed_calls", default=0.0))
    )

    busiest_30d_email, busiest_30d_bucket = ranked_30d[0]
    busiest_30d_share = float(vget(busiest_30d_bucket, "share_of_attributed_calls", default=0.0))

    # THE RISK SIGNAL: an account whose RECENT share sits well above its OWN
    # 30-day baseline share is the one worth watching -- it is burning quota
    # faster than its month-to-date pace, which is the actual precursor to
    # exhausting a monthly cap early. A fixed multiplier over the account's
    # OWN baseline (never a fixed absolute floor) is what makes this a
    # rate-of-consumption question rather than a repaint of the old
    # idle-capacity framing under a new name.
    # SELECT BY ACCELERATION, NOT BY SIZE.
    #
    # This loop used to pick the account with the LARGEST recent share and
    # never consult the baseline in the selection at all -- while the docstring
    # and the operator-facing hint both promised "recent share well above its
    # OWN 30-day baseline." Those are different questions and they pick
    # different accounts. Worked example (baseline 55/5/40, recent 45/45/10):
    # the old code named a@x, which COOLED from 55% to 45%, and never mentioned
    # b@x, which went 5% -> 45% (9x its own pace) -- exactly the
    # quota-exhaustion precursor this tile exists to catch. It survived two
    # review rounds only because on today's live data the largest account also
    # happens to be the fastest-accelerating one.
    #
    # An account with no baseline (new, or absent from the 30-day window) has
    # no pace to outrun, so it cannot be ranked by ratio and is skipped here
    # rather than being handed an infinite one.
    hottest_email: str | None = None
    hottest_recent_share = 0.0
    hottest_baseline_share = 0.0
    hottest_ratio = 0.0
    if accounts_recent:
        for email, bucket in accounts_recent.items():
            recent_share = float(vget(bucket, "share_of_attributed_calls", default=0.0))
            baseline_share = float(
                vget(accounts_30d.get(email, {}), "share_of_attributed_calls", default=0.0)
            )
            if baseline_share <= 0:
                continue
            ratio = recent_share / baseline_share
            if hottest_email is None or ratio > hottest_ratio:
                hottest_email = email
                hottest_recent_share = recent_share
                hottest_baseline_share = baseline_share
                hottest_ratio = ratio

    # Flagged only when the hottest account's RECENT share both dominates
    # (>50% of recent attributed calls) AND clearly outruns its own 30-day
    # baseline (at least 1.5x) -- a burst worth watching, never "unused
    # capacity." An account whose recent share simply matches its own
    # month-to-date pace (the common, healthy case measured here) never
    # flags, no matter how uneven the six shares look on a short window.
    # DERIVE the spread word; never assert it. An earlier version hardcoded
    # "balanced" as a string literal, which is the SAME defect as the original
    # "idle" bug with its sign flipped: an unconditional verdict asserted over
    # data that does not support it. On a synthetic 90/10 split it still read
    # "balanced", and on live data it could print "balanced" beside its own
    # running-hot warning. The collector already computes the real answer --
    # use it.
    quiet_30d = int(
        vget(account_capacity_30d.get("imbalance", {}), "quiet_account_count", default=0) or 0
    )
    # THESE BANDS HAVE NO PUBLISHED BASIS. They are DISPLAY bands -- they pick
    # an adjective that sits directly beside the raw share and the account
    # count, so a reader who disagrees can overrule the word from the visible
    # number. That is what makes an unpublished threshold safe HERE, and it is
    # the distinction from the "idle" bug: that threshold drove a RECOMMENDATION
    # (consolidate seats); these only label a display. 0.60/0.45 read as "clear
    # majority" / "approaching majority" against a six-account fleet whose even
    # share is ~16.7%. The quiet-present clause is NOT invented -- it inherits
    # ACCOUNT_QUIET_RELATIVE_SHARE from the collector, and correctly dominates
    # the numeric bands (0.50/0.47/0.03 is concentrated, not merely uneven).
    if busiest_30d_share >= 0.60 or (quiet_30d and len(ranked_30d) > 1):
        spread_word = "concentrated"
    elif busiest_30d_share >= 0.45:
        spread_word = "uneven"
    else:
        spread_word = "balanced"

    # Gate on the ACCELERATION ratio (the thing selected on), plus a floor so a
    # tiny account tripling from 1% to 3% does not read as a quota risk.
    running_hot = (
        hottest_email is not None
        and hottest_ratio >= 1.5
        and hottest_recent_share > 0.25
    )

    # TWO SHORT LINES, never one run-on sentence (operator complaint
    # 2026-09-06: "fix the account and wrapping on this" -- the prior
    # single-string delta wrapped mid-email across four lines inside the
    # tile). Account labels are shortened to their local part ("3@") --
    # unambiguous within this single-domain fleet, and the full emails
    # remain one click away in the tile's own ranked table below. Both
    # windows are STILL always shown (requirement 3), one per line.
    def _short(email: str) -> str:
        # SINGLE-DOMAIN ASSUMPTION: every fleet account shares one domain
        # (info@/1@..5@ @example.com), so the local part alone is
        # unambiguous. A second domain would render two different accounts
        # identically here -- the full emails in the ranked table below are
        # the disambiguator if that ever happens.
        return email.split("@", 1)[0] + "@"

    line_30d = (
        f"30d: {spread_word} across {len(ranked_30d)} accounts · "
        f"busiest {_short(busiest_30d_email)} {100.0 * busiest_30d_share:.0f}%"
        + (f" · {quiet_30d} quiet" if quiet_30d else "")
    )
    if hottest_email:
        line_recent = (
            f"{recent_days}d: {_short(hottest_email)} {100.0 * hottest_recent_share:.0f}% "
            f"vs {100.0 * hottest_baseline_share:.0f}% baseline"
            + (" — running hot" if running_hot else "")
        )
    else:
        line_recent = f"{recent_days}d: no attributed recent data"

    return {
        "error": None,
        "value": f"{100.0 * busiest_30d_share:.0f}%",
        "delta": f"{line_30d}; {line_recent}",
        "delta_lines": [line_30d, line_recent],
        "direction": "up" if running_hot else "flat",
        "spark": [],
        "flagged": running_hot,
        "running_hot_account": hottest_email if running_hot else None,
        "spread_word": spread_word,
        "quiet_30d": quiet_30d,
        "ranked_30d": ranked_30d,
        "ranked_recent": ranked_recent,
        "recent_days": recent_days,
        "recent_available": bool(accounts_recent),
        "n_30d": int(account_capacity_30d.get("n", 0)),
        "n_recent": int(account_capacity_recent.get("n", 0)) if accounts_recent else 0,
    }


def quality_tile(quality: Mapping[str, Any]) -> dict[str, Any]:
    """Tile -- QUALITY: dissent rate + convergence direction.

    Dollars and dispatch counts describe VOLUME; this is the only tile on
    the page that describes whether the work produced was any GOOD. Source:
    `agent_telemetry.quality_outcomes()`, itself reading the estimate-engine
    loop's own recorded CONCUR/DISSENT verdicts -- never re-derived here.
    """
    if not quality.get("cycle_telemetry_available"):
        return {"error": quality.get("reason", "cycle telemetry unavailable")}
    verdicts = quality.get("verdicts") or {}
    rate = vget(verdicts, "dissent_rate")
    if not isinstance(rate, (int, float)):
        return {"error": "no CONCUR/DISSENT verdicts recorded"}
    total = int(vget(verdicts, "total", default=0))
    dissent_n = int(vget(verdicts, "dissent", default=0))
    series = vget(quality, "convergence_by_round", default=[]) or []
    # Direction: compare the LAST round's rate against the mean of every
    # round before it, mirroring `friction_tile`'s own "last point vs the
    # mean of the rest" idiom -- never just first-vs-last, which a single
    # noisy final round could misrepresent.
    direction = "flat"
    if len(series) >= 2:
        last = float(series[-1]["dissent_rate"])
        # POOL numerators and denominators; never average per-round RATES.
        # An unweighted mean over buckets whose n ranges 16..212 lets a
        # 16-verdict round count as heavily as a 212-verdict one -- measured,
        # that overstated the prior baseline by 7.7pp (0.2455 unweighted vs
        # 0.1680 pooled). This module's own docstring rule 5 forbids exactly
        # this ("never average pre-aggregated per-bucket" figures), and the
        # rule applies to rates for the same reason it applies to percentiles.
        prior_n = sum(int(r.get("n", 0)) for r in series[:-1])
        prior_dissents = sum(
            float(r["dissent_rate"]) * int(r.get("n", 0)) for r in series[:-1]
        )
        prior_mean = (prior_dissents / prior_n) if prior_n else 0.0
        direction = "down" if last < prior_mean - 0.02 else ("up" if last > prior_mean + 0.02 else "flat")
    spark = [float(r["dissent_rate"]) for r in series]
    return {
        "error": None,
        "value": f"{100.0 * float(rate):.0f}%",
        "delta": f"{dissent_n:,} dissents of {total:,} verdicts across {int(vget(quality, 'cycles_read', default=0))} loop rounds",
        "direction": direction,
        "spark": spark,
        "rate": float(rate),
        "total": total,
        "dissent_n": dissent_n,
        "series": series,
        "by_trade": vget(quality, "dissent_rate_by_trade", default={}) or {},
        "excluded_thin": vget(quality, "dissent_rate_by_trade_excluded_thin", default={}) or {},
    }


def dispatch_tile(
    tel: Mapping[str, Any],
    days: int,
    today: datetime.date,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Tile 2 -- dispatches, split declared vs unattributed.

    The split is the point: `(missing)` agent_type rows and the client's
    generic buckets are not personas, and folding them into a named agent
    would invent attribution the ledger does not carry.

    DENOMINATOR CARE: `dispatch_counts()` reports its split over the WHOLE
    ledger (~11 days), while this tile's headline is the 7-day window. Using
    the collector's lifetime split here produced a subtotal LARGER than the
    headline it was splitting (measured: 3,806 "declared" under a 3,225
    headline) -- a cross-partition mix, and exactly the silent denominator
    swap the plan forbids. So the split is recomputed over the SAME windowed
    rows as the headline, reusing the collector's own `prepare_rows` and
    `normalize_agent_type` rather than reimplementing either. When raw rows
    are unavailable the split is reported as unavailable, never mixed.
    """
    disp = tel.get("dispatch_counts", {})
    if disp.get("error"):
        return {"error": disp["error"]}
    by_day = vget(disp, "by_day", default={}) or {}
    cur_days = day_seq(days, today)
    cur_set = set(cur_days)
    cur = sum(int(by_day.get(d, 0)) for d in cur_days)
    prior = sum(int(by_day.get(d, 0)) for d in day_seq(days, today - datetime.timedelta(days=days)))

    declared = generic = missing = None
    total = cur
    if rows is not None:
        kept, _ = at.prepare_rows(list(rows), at.BASIS_ACTIVITY)
        windowed = [r for r in kept if at.day_of(r.get("ts")) in cur_set]
        total = len(windowed)
        declared = generic = missing = 0
        for row in windowed:
            name, prov = at.normalize_agent_type(row.get("agent_type"))
            if prov == at.UNATTRIBUTABLE:
                missing += 1
            elif name in at.GENERIC_AGENT_TYPES:
                generic += 1
            else:
                declared += 1
    delta = "no prior window"
    if prior:
        delta = f"{100.0 * (cur - prior) / prior:+.0f}% vs prior {days}d ({prior:,})"
    return {
        "error": None,
        "value": f"{cur:,}",
        "delta": delta,
        "direction": "up" if cur > prior else ("down" if cur < prior else "flat"),
        "spark": [float(by_day.get(d, 0)) for d in cur_days],
        "declared": declared,
        "generic": generic,
        "missing": missing,
        "total": total,
        "windowed_split": declared is not None,
        "declared_pct": pct(declared, total) if declared is not None else "unavailable",
        "top": list((vget(disp, "by_agent_type", default={}) or {}).items())[:6],
    }


def convergence_tile(conv: Mapping[str, Any]) -> dict[str, Any]:
    """Tile 4 -- median rounds per boundary + % clean at round 1.

    `rounds_histogram` is keyed by each chain's MAX round
    (`churn_report.py:1242`), so a chain whose max is 1 is one that never
    needed a fix round -- that is the clean-round-1 numerator. The median is
    taken over chains, and the chain count is printed as the denominator.
    """
    if conv.get("error"):
        return {"error": conv["error"]}
    hist = {int(k): int(v) for k, v in (conv.get("rounds_histogram") or {}).items()}
    chains = int(conv.get("chains_total", 0))
    if not hist or not chains:
        return {"error": "no review chains in window"}
    expanded: list[int] = []
    for rounds, count in sorted(hist.items()):
        expanded.extend([rounds] * count)
    median = statistics.median(expanded)
    clean1 = hist.get(1, 0)
    return {
        "error": None,
        "value": f"{median:.0f}",
        "delta": f"{pct(clean1, chains)} clean at round 1",
        "direction": "flat",
        "spark": [float(hist.get(r, 0)) for r in range(1, max(hist) + 1)],
        "chains": chains,
        "hist": sorted(hist.items()),
        "clean1": clean1,
        "warm_refusals": int(conv.get("warm_cap_refusals", 0)),
        "small_n": bool(conv.get("small_n")),
        "warm_rows": int(conv.get("warm_rows_total", 0)),
    }


def cache_tile(tel: Mapping[str, Any]) -> dict[str, Any]:
    """Tile 5 -- BINARY STATE, never a percentage (plan §7.1).

    Renders exactly one of two states, and when invalidated it NAMES the
    agent type whose prefix moved -- which is the operator's actual question
    ("what busted the cache"), and is why `cache_detail()` computes per
    agent type rather than fleet-wide. There is deliberately no number on
    this tile to optimize: a rendered hit-rate KPI is Goodharted by simply
    never changing a prompt again. The rate itself is a diagnostic figure in
    the Layer-4 health panel.
    """
    detail = tel.get("cache_detail", {})
    if detail.get("error"):
        return {"error": detail["error"]}
    rates = vget(detail, "by_agent_type", default={}) or {}
    fleet = vget(tel.get("token_buckets", {}), "cache_hit_rate")
    rated = [(name, float(d["hit_rate"]), int(d["n"])) for name, d in rates.items()]
    rated.sort(key=lambda t: t[1])

    if not rated or not isinstance(fleet, (int, float)):
        return {"error": "no cacheable rows in window"}

    # Baseline = the median agent type's rate. An agent sitting a long way
    # below its peers is the localizing signal; a fleet-wide average cannot
    # tell you WHOSE prompt moved, which is the whole question.
    #
    # Only agent types with enough rows may TRIP the alarm (see
    # CACHE_ALARM_MIN_ROWS). The median is still taken over every rated type
    # so the baseline reflects the real fleet, but a thin type cannot raise
    # the alarm by itself.
    baseline = statistics.median([r for _, r, _ in rated])
    eligible = [t for t in rated if t[2] >= CACHE_ALARM_MIN_ROWS]
    thin = len(rated) - len(eligible)

    worst = eligible[0] if eligible else None
    drop_pp = ((baseline - worst[1]) * 100.0) if worst else 0.0

    fleet_broken = fleet < CACHE_FLOOR
    agent_broken = bool(worst) and drop_pp >= CACHE_DROP_PP
    invalidated = fleet_broken or agent_broken

    if agent_broken:
        state = "prefix invalidated"
        detail_txt = f"−{drop_pp:.0f}pp vs peer median ({worst[0]}, n={worst[2]:,} rows)"
    elif fleet_broken:
        state = "prefix invalidated"
        detail_txt = f"fleet hit rate below the {CACHE_FLOOR:.0%} floor"
    else:
        state = "cache prefix stable"
        detail_txt = (
            f"no agent type with at least {CACHE_ALARM_MIN_ROWS} rows sits "
            f"{CACHE_DROP_PP:.0f}pp below the peer median "
            f"({len(eligible)} of {len(rated)} types eligible to alarm)"
        )
    return {
        "error": None,
        "state": state,
        "invalidated": invalidated,
        "agent": worst[0] if worst else None,
        "detail": detail_txt,
        "rated": rated,
        "eligible": len(eligible),
        "thin": thin,
        "baseline": baseline,
        "fleet_rate": fleet,
        "n": int(vget(detail, "n", default=0)),
        "sparse": vget(detail, "sparse_agent_types", default={}) or {},
        "ttl_note": vget(detail, "ttl_split") or at.unattributable("").source,
        "ttl_prov": vprov(detail, "ttl_split"),
        "min_rows": int(vget(detail, "min_rows_for_rate", default=5)),
    }


def subagent_share_tile(ccdash_token_split: Mapping[str, Any]) -> dict[str, Any]:
    """Tile -- subagent vs main-thread token share, from ccdash's COMPLETE data.

    This is a headline-grade fact spend.jsonl could never show: it has no
    is_sidechain-equivalent field, and 52.5% of its rows carry no model at
    all. ccdash's `is_sidechain` is populated on every row unconditionally
    (parsed straight off the transcript's own `isSidechain` field), so this
    tile has no excluded population to disclaim the way a join-dependent
    metric would -- it either has ccdash or it does not.
    """
    if not ccdash_token_split.get("ccdash_available"):
        return {"error": ccdash_token_split.get("reason", "ccdash unavailable")}
    share = vget(ccdash_token_split, "subagent_token_share")
    if not isinstance(share, (int, float)):
        return {"error": "no tokens in window"}
    n = int(vget(ccdash_token_split, "n", default=0))
    sub_tokens = int(vget(ccdash_token_split, "subagent_tokens", default=0))
    main_tokens = int(vget(ccdash_token_split, "main_thread_tokens", default=0))
    return {
        "error": None,
        "value": f"{100.0 * float(share):.0f}%",
        "delta": f"sub-agent tokens: {pct(sub_tokens, sub_tokens + main_tokens)}",
        "direction": "flat",
        "spark": [],
        "n": n,
        "sub_tokens": sub_tokens,
        "main_tokens": main_tokens,
    }


def verdict(
    tel: Mapping[str, Any],
    tiles: Mapping[str, Any],
    days: int,
) -> dict[str, Any]:
    """Layer 1 -- ONE plain-English line, computed from leaf data.

    NO JARGON. The operator's complaint about the existing loop dashboard was
    verbatim that it "has, like, jargon at the top". So: no `join_state`, no
    `partition`, no `p95`, no `provenance`, no metric names. Every clause
    here is a full English sentence a non-engineer can act on, and the
    numbers are the same ones the tiles below show -- never a separately
    computed headline that can drift from its own detail.
    """
    health = tel.get("ledger_health", {})
    n_rows = int(vget(health, "n", default=0))
    join_rate = vget(health, "join_rate", default=0.0)
    joined = int((vget(health, "join_state_mix", default={}) or {}).get("joined", 0))

    signals: list[tuple[str, bool]] = []
    parts: list[str] = []

    # THE RE-FRAME (2026-09-06): "spend" is no longer a signal in its own
    # right -- there is no established budget threshold, and the operator's
    # own finding is that a dollar total alone answers the wrong question
    # for a fixed-cost subscription fleet. "leverage" and "account_balance"
    # replace it: leverage states the same api-equivalent dollars but as a
    # ratio against the fixed $1,200/mo cost, and account_balance asks
    # whether any account is running hot enough against its own MONTHLY
    # baseline to risk exhausting quota before the reset -- a rate-of-
    # consumption question, corrected 2026-09-06 from an earlier "idle
    # capacity" framing that a 7-day-only window had gotten backwards (see
    # `account_balance_tile()`'s own docstring for the measured correction).
    if not tiles["leverage"].get("error"):
        parts.append(
            f"{tiles['leverage']['value']} return on the fixed ${CLAUDE_MAX_FIXED_MONTHLY_USD:,.0f}/mo "
            f"subscription over the last {days} days"
        )
        # Leverage has no established "good" ratio -- ANY ratio above 1x
        # means the subscription is paying for itself, and there is no
        # meaningful upper bound. It is never a health signal on its own.
    if not tiles["account_balance"].get("error"):
        parts.append(
            f"the busiest account carries {tiles['account_balance']['value']} of the billing period"
        )
        signals.append(("account_balance", not tiles["account_balance"]["flagged"]))
    if not tiles["dispatch"].get("error"):
        parts.append(f"{tiles['dispatch']['value']} agent runs")
        signals.append(("dispatches", True))
    if not tiles["convergence"].get("error"):
        parts.append(f"code review usually settles in {tiles['convergence']['value']} rounds")
        signals.append(("convergence", float(tiles["convergence"]["value"]) <= 3))
    if not tiles["cache"].get("error"):
        signals.append(("cache", not tiles["cache"]["invalidated"]))
    if not tiles["quality"].get("error"):
        parts.append(f"trades dissented on {tiles['quality']['value']} of estimate-engine verdicts")
        signals.append(("quality", tiles["quality"]["direction"] != "up"))

    ok = sum(1 for _, good in signals if good)
    total_signals = len(signals)

    # A dashboard that cannot read its own data must never report good news.
    # With no rows there is nothing to be healthy ABOUT, and "All good" over an
    # empty ledger is the most misleading line this page could print -- it
    # reads as "checked, fine" when the truth is "could not check". Broken
    # panels are counted before any verdict is reached.
    broken = [name for name in ("leverage", "account_balance", "dispatch", "convergence", "cache", "quality")
              if tiles[name].get("error")]
    if n_rows == 0:
        headline = "No data"
    elif len(broken) >= 3:
        headline = "Can't tell"
    elif tiles["cache"].get("invalidated") or tiles["account_balance"].get("flagged"):
        headline = "Needs a look"
    elif ok == total_signals:
        headline = "All good"
    elif ok >= total_signals - 1:
        headline = "Mostly fine"
    else:
        headline = "Needs a look"

    if n_rows == 0:
        trust = (
            "No usage records were found at all, so nothing on this page has been "
            "measured. This is a problem with reading the data, not a quiet week."
        )
        parts = ["Nothing could be measured"] if not parts else parts
    else:
        trust = (
            f"About {100.0 * float(join_rate):.0f} out of every 100 records are complete "
            f"({joined:,} of {n_rows:,}); the rest are missing some detail, so a few "
            f"panels below say so rather than guess."
        )
    if broken and n_rows:
        trust += (
            f" {len(broken)} of 6 panels could not be worked out and say so instead "
            f"of showing a number."
        )

    # THE SIX-ACCOUNT / $1,200-A-MONTH FRAMING, MADE EXPLICIT (2026-09-06,
    # operator finding). A reader must not be able to mistake any dollar
    # figure on this page for a bill: this fleet runs on SIX Claude Max
    # seats at $200/mo each, a fixed subscription cost, not metered API
    # billing -- the console shows only "percent of quota used," never a
    # dollar figure. Every dollar shown anywhere on this page is therefore
    # an api-EQUIVALENT value (what the same usage would cost on metered
    # billing), never money actually spent.
    trust += (
        f" This fleet runs on {CLAUDE_MAX_SEATS} Claude Max seats at "
        f"${CLAUDE_MAX_SEAT_MONTHLY_USD:,.0f}/mo each — ${CLAUDE_MAX_FIXED_MONTHLY_USD:,.0f}/mo "
        f"FIXED, not metered API billing. Every dollar figure on this page is what the "
        f"same usage would cost on METERED billing, never money actually spent."
    )

    # PRICING COVERAGE, stated up front rather than buried (2026-09-05).
    # The join rate above describes attribution completeness; it says nothing
    # about how much SPEND is priced, and those diverge badly: coverage was
    # measured at 49% while the join rate read much healthier. A dollar total
    # computed over half the rows, presented without that caveat beside it,
    # reads as the whole bill and is not. Unpriceable rows are EXCLUDED, never
    # priced at $0 -- so the real figure is always higher, never lower.
    cov = vget(tel.get("spend_usd", {}), "pricing_coverage")
    if isinstance(cov, (int, float)) and 0.0 <= float(cov) < 0.95:
        unp = vget(tel.get("spend_usd", {}), "unpriceable", "rows")
        unp_txt = f"{int(unp):,} rows" if isinstance(unp, (int, float)) else "some rows"
        # SCOPE THIS CAVEAT TO THE SOURCE IT DESCRIBES (2026-09-05).
        #
        # This coverage figure is about the ROSTER LEDGER (spend.jsonl), which
        # is the only source that knows agent_type. It is NOT true of the
        # complete-data panels below, which come from ccdash and price ~100%
        # of rows. Stating a bare "only 50% could be priced" above a section
        # whose numbers ARE complete makes a reader distrust the good figures
        # and mistrust the whole page -- the opposite of the honesty this line
        # exists to provide. Name the source, and say which panels it binds.
        trust += (
            f" Note on the two data sources: the ROSTER LEDGER (which is what knows agent "
            f"TYPE) could price only {100.0 * float(cov):.0f}% of its records ({unp_txt} carry "
            f"no model name), so any per-agent-type dollar figure is a FLOOR, not a bill. The "
            f"complete-data panels further down do not have this limitation — they read every "
            f"recorded call and price essentially all of it. Where the two disagree, the "
            f"complete-data panels are the ones to trust."
        )
    return {
        "headline": headline,
        "sentence": "; ".join(parts) + ".",
        "trust": trust,
        "ok": ok,
        "signals": total_signals,
        "cache_state": tiles["cache"].get("state", ""),
        "invalidated": bool(tiles["cache"].get("invalidated")) or bool(tiles["account_balance"].get("flagged")),
    }


def chart_spend_by_model(tel: Mapping[str, Any], days: int, today: datetime.date) -> str:
    """Chart 1 -- stacked bar, <=4 model bands plus an explicit `other`.

    The collector gives a per-day total and a per-family total but not the
    cross-product, so each family's daily series is apportioned by that
    family's share of priced spend. That is an APPROXIMATION and the page
    says so beneath the chart -- an unlabelled approximation would be exactly
    the laundering this project exists to prevent.
    """
    spend = tel.get("spend_usd", {})
    if spend.get("error"):
        return f'<p class="empty">Not renderable: {esc(spend["error"])}</p>'
    by_day = vget(spend, "by_day", default={}) or {}
    by_family = vget(spend, "by_model_family", default={}) or {}
    if not by_day or not by_family:
        return '<p class="empty">No priced spend in window.</p>'
    days_list = day_seq(days, today)
    families = sorted(by_family.items(), key=lambda kv: -float(kv[1]))
    head = families[:MAX_MODEL_BANDS]
    tail = families[MAX_MODEL_BANDS:]
    grand = sum(float(v) for _, v in families) or 1.0
    series: list[tuple[str, list[float]]] = []
    for name, total in head:
        share = float(total) / grand
        series.append((name, [float(by_day.get(d, 0.0)) * share for d in days_list]))
    if tail:
        share = sum(float(v) for _, v in tail) / grand
        series.append(("other", [float(by_day.get(d, 0.0)) * share for d in days_list]))
    return stacked_bar_chart(days_list, series)


def chart_contested(friction: Mapping[str, Any]) -> str:
    """Chart 2 -- ranked bar, zero-based.

    The ledger's `contested-paths` rows carry `overlap_paths` (a LIST), while
    `churn-flagged` rows carry a single `path`; `churn_report` therefore only
    ranks paths for churn-flagged, and this chart renders exactly that,
    labelled for what it is rather than mislabelled as contests.
    """
    if friction.get("error"):
        return f'<p class="empty">Not renderable: {esc(friction["error"])}</p>'
    rows = [(r["path"], float(r["count"])) for r in friction.get("top_churn_paths", [])]
    if not rows:
        return '<p class="empty">No churn-flagged paths in window.</p>'

    def shorten(path: str, limit: int = 40) -> str:
        """Elide the MIDDLE, never the tail.

        Truncating the end drops the filename -- the only part that
        distinguishes one path from another. Live data produced two separate
        rows both rendering as `TESTING_AND_HARNESSES...`, which is a label
        that identifies nothing. Keeping head and tail keeps them distinct.
        """
        name = path.rsplit("/", 1)[-1]
        if len(path) <= limit:
            return path
        if len(name) >= limit - 3:
            return "…" + name[-(limit - 1) :]
        head = limit - len(name) - 3
        return f"{path[:head]}…/{name}"

    shortened = [(shorten(p), c) for p, c in rows]
    titles = {shorten(p): p for p, _ in rows}
    return ranked_bar_chart(shortened, "flags", fmt=lambda v: f"{int(v):,}", titles=titles)


def chart_spend_by_flow(tel: Mapping[str, Any]) -> str:
    """Chart 3 -- ranked bar with an EXPLICIT `unattributed` bar.

    Flow here is agent type: the ledger has no flow field, and the plan's
    Phase 3 flow attribution has not landed. The unpriceable rows get their
    own visible bar rather than vanishing -- hiding them would make the
    priced total look like the whole of spend when it covers roughly half
    the rows.
    """
    spend = tel.get("spend_usd", {})
    if spend.get("error"):
        return f'<p class="empty">Not renderable: {esc(spend["error"])}</p>'
    by_type = vget(spend, "by_agent_type", default={}) or {}
    rows = [(k, float(v)) for k, v in list(by_type.items())[:9]]
    unpriceable = int(vget(spend, "unpriceable", "rows", default=0))
    if unpriceable:
        rows.append((f"unattributed ({unpriceable:,} rows, no price)", 0.0))
    if not rows:
        return '<p class="empty">No priced spend in window.</p>'
    return ranked_bar_chart(
        rows,
        "USD",
        highlight=f"unattributed ({unpriceable:,} rows, no price)",
        fmt=usd,
    )


def chart_ccdash_spend_by_model(ccdash_spend: Mapping[str, Any]) -> str:
    """Chart -- ranked bar, per-model spend from ccdash's COMPLETE data.

    This is the panel that corrects `chart_spend_by_flow`'s understated
    picture: spend.jsonl's by_model_family chart only ever sees the ~48% of
    rows a hook managed to price, and Fable's dispatches are disproportionately
    the under-captured half (measured 2026-09-05: spend.jsonl shows Fable at
    ~2% of spend; ccdash shows it at ~32% over the same window). Ranked,
    zero-based, same chart primitive as every other ranked bar on this page --
    no new chart type introduced for one panel.
    """
    if not ccdash_spend.get("ccdash_available"):
        return f'<p class="empty">ccdash unavailable: {esc(ccdash_spend.get("reason", "unknown"))}</p>'
    by_model = vget(ccdash_spend, "by_model", default={}) or {}
    if not by_model:
        return '<p class="empty">No priced ccdash rows in window.</p>'
    rows = [(k, float(v)) for k, v in list(by_model.items())[:9]]
    unpriceable = int(vget(ccdash_spend, "unpriceable", "rows", default=0))
    if unpriceable:
        rows.append((f"unpriced ({unpriceable:,} rows)", 0.0))
    return ranked_bar_chart(
        rows,
        "USD",
        highlight=f"unpriced ({unpriceable:,} rows)" if unpriceable else None,
        fmt=usd,
    )


def chart_account_capacity(account_capacity: Mapping[str, Any]) -> str:
    """Chart -- ranked bar, calls per account for ONE window.

    Ranked, zero-based, same primitive as every other ranked bar on this
    page. Rendered TWICE by the caller (once per window -- 30d and recent)
    since 2026-09-06's correction: the two windows can disagree in shape,
    not just magnitude, so a single merged chart would hide exactly the
    disagreement the page now exists to surface.
    """
    if not account_capacity.get("ccdash_available"):
        return f'<p class="empty">Not renderable: {esc(account_capacity.get("reason", "unknown"))}</p>'
    accounts = account_capacity.get("accounts") or {}
    if not accounts:
        return '<p class="empty">No attributed accounts in window.</p>'
    rows = [(email, float(vget(acct, "calls", default=0))) for email, acct in accounts.items()]
    rows.sort(key=lambda kv: -kv[1])
    return ranked_bar_chart(rows, "calls", fmt=lambda v: f"{int(v):,}")


def chart_quality_by_trade(quality: Mapping[str, Any]) -> str:
    """Chart -- ranked bar, dissent rate per trade (rated trades only).

    Ranked HIGH-to-low so the trade specialists dissenting most often --
    the ones worth reading the underlying findings for -- sit at the top.
    Trades with too few verdicts to rate (see `DISSENT_RATE_MIN_VERDICTS`)
    are never plotted here; they are named separately in the card's own
    note rather than silently dropped.
    """
    if not quality.get("cycle_telemetry_available"):
        return f'<p class="empty">Not renderable: {esc(quality.get("reason", "unknown"))}</p>'
    by_trade = vget(quality, "dissent_rate_by_trade", default={}) or {}
    if not by_trade:
        return '<p class="empty">No trade carried enough verdicts to rate.</p>'
    # Each value is `{"n": int, "dissent_rate": Value(...)}` -- `vget` unwraps
    # the Value regardless of whether `quality` arrived live (agent_telemetry
    # Value objects) or via --json (plain {value, provenance, source} dicts).
    rows = [(trade, float(vget(d, "dissent_rate", default=0.0))) for trade, d in by_trade.items()]
    rows.sort(key=lambda kv: -kv[1])
    return ranked_bar_chart(rows, "dissent rate", fmt=lambda v: f"{100.0 * v:.0f}%")


def table_cost_vs_quality(cvq: Mapping[str, Any]) -> str:
    """Table -- the cost/quality JOIN: is a trade expensive AND not earning it.

    THE GAP THIS CLOSES: cost and quality otherwise render as two panels
    that share no axis, so a reader can see what an agent type costs, and
    separately that dissent is falling fleet-wide, but never whether a
    GIVEN trade is expensive AND not earning it. Sorted by $/verdict
    DESCENDING -- the expensive-and-wrong agents are the point, so they sit
    at the top rather than requiring a reader to re-sort.

    An unjoined trade (real quality figures, no ledger cost match) is
    rendered in its own row with an explicit "unjoined" cell -- never
    dropped, and never rendered as $0, mirroring every other unpriceable-row
    rule on this page.
    """
    if not cvq.get("renderable"):
        return f'<p class="empty">Not renderable: {esc(cvq.get("reason", "unknown"))}</p>'
    rows = cvq.get("rows") or {}
    if not rows:
        return '<p class="empty">No rated trade joined to a ledger cost.</p>'

    def sort_key(item: tuple[str, Mapping[str, Any]]) -> float:
        upv = vget(item[1], "usd_per_verdict")
        # Unjoined trades (usd_per_verdict is None/unattributable) sort to
        # the BOTTOM, never the top -- an absent number is not "cheap", and
        # letting it sort as 0 would visually rank an unmeasured trade
        # alongside the genuinely cheapest one.
        return float(upv) if isinstance(upv, (int, float)) else float("-inf")

    ordered = sorted(rows.items(), key=sort_key, reverse=True)
    body_rows = []
    for trade, detail in ordered:
        verdicts = int(vget(detail, "verdicts", default=0))
        dissent_n = int(vget(detail, "dissent_count", default=0))
        dissent_rate = vget(detail, "dissent_rate")
        usd_total = vget(detail, "api_equivalent_usd")
        upv = vget(detail, "usd_per_verdict")
        resolved = vget(detail, "resolved_agent_type")
        if isinstance(usd_total, (int, float)) and isinstance(upv, (int, float)):
            cost_cell = usd(float(usd_total))
            upv_cell = usd(float(upv))
        else:
            cost_cell = '<span class="muted">unjoined</span>'
            upv_cell = '<span class="muted">unjoined</span>'
        dissent_pct = f"{100.0 * float(dissent_rate):.0f}%" if isinstance(dissent_rate, (int, float)) else "n/a"
        agent_type_cell = esc(resolved) if isinstance(resolved, str) else '<span class="muted">no ledger match</span>'
        body_rows.append(
            f"<tr><td>{esc(trade)}</td>"
            f"<td class='n'>{verdicts:,}</td>"
            f"<td class='n'>{esc(dissent_pct)} ({dissent_n:,} of {verdicts:,})</td>"
            f"<td class='n'>{cost_cell}</td>"
            f"<td class='n'>{upv_cell}</td>"
            f"<td>{agent_type_cell}</td></tr>"
        )
    unjoined = vget(cvq, "unjoined_trades", default=[]) or []
    header = (
        "<table><thead><tr><th>Trade</th><th class='n'>Verdicts</th>"
        "<th class='n'>Dissent rate</th><th class='n'>Cost (api-equivalent)</th>"
        "<th class='n'>$/verdict</th><th>Resolved ledger agent_type</th></tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody></table>"
    )
    note = (
        f"Sorted by $/verdict, descending — the expensive-and-wrong agents are the point. "
        f"{len(unjoined)} trade(s) resolved to no ledger agent_type and show as "
        f"<code>unjoined</code> rather than $0: {', '.join(sorted(unjoined)) if unjoined else 'none'}."
    )
    return header + f'<p class="note">{note}</p>'


# ---------------------------------------------------------------------------
# Panel declarations -- the mechanical anti-metric backstop (plan §1.3).
# Every plotted panel declares the field it plots. `agent_telemetry
# .assert_no_tokens_total_headline()` is run over this list before any HTML
# is emitted, so plotting the anti-metric raises instead of rendering.
# ---------------------------------------------------------------------------

PANELS: list[dict[str, str]] = [
    {"id": "tile-leverage", "source": "ccdash_spend_by_model.total_usd (api-equivalent value, not spend)"},
    {"id": "tile-account-balance", "source": "account_capacity.imbalance.quiet_account_count + accounts.*.share_of_attributed_calls"},
    {"id": "tile-dispatch", "source": "dispatch_counts.by_day"},
    {"id": "tile-convergence", "source": "last_reviewed:rounds_histogram"},
    {"id": "tile-cache", "source": "cache_detail.by_agent_type (state, not rate)"},
    {"id": "tile-quality", "source": "quality_outcomes.verdicts.dissent_rate"},
    {"id": "chart-spend-model", "source": "spend_usd.by_day x by_model_family"},
    {"id": "chart-contested", "source": "enforcement:churn-flagged top paths"},
    {"id": "chart-flow", "source": "spend_usd.by_agent_type"},
    {"id": "panel-health", "source": "ledger_health.join_state_mix"},
    {"id": "panel-ccdash-spend", "source": "ccdash_spend_by_model.by_model (complete ccdash data)"},
    {"id": "chart-ccdash-model", "source": "ccdash_spend_by_model.by_model"},
    {"id": "panel-subagent-share", "source": "ccdash_token_split.subagent_token_share"},
    {"id": "panel-cache-ttl", "source": "ccdash_cache_ttl_split.writes_5m_tokens / writes_1h_tokens"},
    {"id": "panel-agent-type-join", "source": "ccdash_agent_type_join.by_agent_type_usd"},
    {"id": "chart-account-capacity", "source": "account_capacity.accounts.*.calls"},
    {"id": "chart-quality-by-trade", "source": "quality_outcomes.dissent_rate_by_trade"},
    {"id": "table-cost-vs-quality", "source": "cost_vs_quality.rows.*.usd_per_verdict"},
]


CSS = """
:root{
  --bg:#f6f7f9; --card:#fff; --ink:#12161c; --muted:#5a6472; --line:#dfe3e9;
  --good:#0f7b4f; --warn:#a35b00; --bad:#b4232a; --accent:#1f4f8f;
  --b0:#1f4f8f; --b1:#3f8ea8; --b2:#7a9b46; --b3:#b07d2b; --b4:#8a6a94;
}
@media (prefers-color-scheme:dark){
  :root{
    --bg:#11141a; --card:#191d25; --ink:#e8ecf2; --muted:#9aa5b4; --line:#2b323d;
    --good:#4cc48a; --warn:#e0a24a; --bad:#ef6d72; --accent:#7fb0ee;
    --b0:#7fb0ee; --b1:#67c3d8; --b2:#a8cd6c; --b3:#e0b45f; --b4:#c2a3cd;
  }
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;}
.wrap{max-width:1160px;margin:0 auto;padding:28px 20px 60px}
h1{font-size:20px;margin:0 0 4px}
h2{font-size:15px;letter-spacing:.02em;text-transform:uppercase;color:var(--muted);
  margin:34px 0 12px;font-weight:600}
h3{font-size:14px;margin:0 0 8px}
.sub{color:var(--muted);font-size:13px;margin:0 0 22px}
.verdict{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--good);
  border-radius:12px;padding:20px 22px;margin-bottom:8px}
.verdict.warn{border-left-color:var(--warn)}
.verdict.bad{border-left-color:var(--bad)}
.vhead{font-size:26px;font-weight:700;letter-spacing:-.01em;margin:0 0 6px}
.vsent{font-size:17px;line-height:1.5;margin:0 0 10px}
.vtrust{font-size:13px;color:var(--muted);margin:0}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(212px,1fr));gap:14px;margin-top:16px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:15px 16px;
  display:flex;flex-direction:column;gap:6px}
.tlabel{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600}
.tval{font-size:29px;font-weight:700;letter-spacing:-.02em;line-height:1.05}
.tval.state{font-size:19px;line-height:1.25}
.tdelta{font-size:13px;color:var(--muted);overflow-wrap:anywhere}
.tdelta.up{color:var(--warn)} .tdelta.down{color:var(--good)}
.muted{color:var(--muted)}
.thint{font-size:11.5px;color:var(--muted);margin-top:4px}
.thint summary{cursor:help;user-select:none;color:var(--accent);font-weight:600;
  text-decoration:underline dotted;text-underline-offset:2px}
.thint summary:hover{color:var(--ink)}
.thint p{margin:6px 0 0;line-height:1.5;color:var(--muted)}
.tdenom{font-size:11.5px;color:var(--muted);border-top:1px dashed var(--line);padding-top:7px;margin-top:auto}
/* Long identifiers (price-table version, paths) must wrap inside their tile
   rather than run past its edge. */
.tdenom code{overflow-wrap:anywhere;word-break:break-word}
/* Sparkline sits directly under the delta line, not floated into the gap
   left by tiles with differing text heights -- `margin-top:auto` on .tdenom
   already pushes the denominator to the bottom, so the spark must not also
   stretch. */
.spark{color:var(--accent);display:block;margin:2px 0 8px;flex:0 0 auto}
.sparkempty{font-size:9px;fill:var(--muted)}
.ok{color:var(--good);font-weight:700} .alert{color:var(--bad);font-weight:700}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:18px 20px;margin-bottom:16px}
.chart{display:block;max-width:100%;overflow:visible}
.grid line,.grid{stroke:var(--line);stroke-width:1}
line.grid{stroke:var(--line);stroke-dasharray:2 3}
line.axisline{stroke:var(--muted);stroke-width:1}
text.axis{font-size:10px;fill:var(--muted)}
.band.b0{fill:var(--b0)} .band.b1{fill:var(--b1)} .band.b2{fill:var(--b2)}
.band.b3{fill:var(--b3)} .band.b4{fill:var(--b4)}
.legend{margin-top:8px;font-size:12px;color:var(--muted)}
.key{margin-right:14px;display:inline-flex;align-items:center;gap:5px}
.sw{width:11px;height:11px;border-radius:2px;display:inline-block}
.sw.b0{background:var(--b0)} .sw.b1{background:var(--b1)} .sw.b2{background:var(--b2)}
.sw.b3{background:var(--b3)} .sw.b4{background:var(--b4)}
.rank{display:flex;flex-direction:column;gap:6px}
.rankrow{display:grid;grid-template-columns:190px 1fr 84px;gap:10px;align-items:center;font-size:13px}
.ranklabel{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--muted)}
.barwrap{background:var(--line);border-radius:3px;height:15px;overflow:hidden}
.bar{display:block;height:100%;background:var(--accent);border-radius:3px}
.bar.hl{background:repeating-linear-gradient(45deg,var(--muted),var(--muted) 4px,transparent 4px,transparent 8px);
  border:1px solid var(--muted)}
.rankval{text-align:right;font-variant-numeric:tabular-nums;font-size:12.5px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--line)}
th{color:var(--muted);font-weight:600;font-size:11.5px;text-transform:uppercase;letter-spacing:.04em}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.note{font-size:12px;color:var(--muted);margin:10px 0 0}
.empty{color:var(--muted);font-size:13px;font-style:italic}
.pill{display:inline-block;font-size:11px;padding:2px 8px;border-radius:99px;
  border:1px solid var(--line);color:var(--muted);margin-right:6px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
footer{margin-top:34px;font-size:12px;color:var(--muted);border-top:1px solid var(--line);padding-top:14px}
@media print{body{background:#fff}.card,.tile,.verdict{break-inside:avoid;border-color:#bbb}}
"""


# ---------------------------------------------------------------------------
# INTERPRETATION HINTS -- "is this number good or bad?"
#
# Operator, 2026-09-05: "I don't know if a hit rate of 83% is bad or not. So
# possibly have hints on hover or flags or something."
#
# A dashboard that shows a number without saying what good looks like makes
# the reader do the interpretation, which is the work the dashboard exists to
# do. Each hint states the direction that is good, a threshold where one
# genuinely exists, and -- critically -- says so plainly when NO threshold has
# been established rather than inventing one. An invented threshold is worse
# than none: it manufactures false alarms and false comfort, and it becomes a
# target (Goodhart) the moment someone optimizes against it.
#
# Provenance of each threshold is stated in the text itself: "measured here",
# "contract rule", or "no established threshold".
# ---------------------------------------------------------------------------
HINTS: dict[str, str] = {
    "spend": (
        "Direction: lower is better only at equal output — spend is not waste, it is work. "
        "There is NO established budget threshold for this fleet, so no red line is drawn. "
        "What to actually look for: a step change with no matching change in work done, or "
        "one agent type dominating the by-agent chart below without a reason you can name. "
        "Read it against the by-model chart: an opus share that grows while sonnet-suitable "
        "work is unchanged is the classic drift, and it is what this tile is for."
    ),
    "dispatch": (
        "Direction: neither up nor down is inherently good — this is a workload measure, not "
        "a score. It exists to give every other tile a denominator. The number that matters "
        "is the declared/unattributed split: unattributed means the ledger could not tell "
        "which agent ran, so any per-agent figure on this page is computed over the declared "
        "share only. A rising unattributed share degrades the whole page, and that is the "
        "failure this tile is here to expose."
    ),
    "friction": (
        "Direction: LOWER IS BETTER, and this one has a real target — zero. Every collision "
        "is one agent blocked by another on the same files: wasted wall-clock, and the "
        "clobbering the worktree work exists to stop. No formal threshold is established, but "
        "a sustained rise means sessions are contending for the same paths and should be "
        "partitioned by file or moved into worktrees. A day at zero is genuinely good news."
    ),
    "convergence": (
        "Direction: LOWER IS BETTER. This is review rounds per commit boundary. 1.0 means "
        "review found nothing to fix on the first pass. The operating contract caps warm "
        "(in-context) re-reviews at 2 consecutive rounds before a cold dispatch is required, "
        "so 3+ rounds on one boundary is a contract-level signal, not just a slow day. "
        "Caution: a very low number is NOT automatically good — it can equally mean review "
        "is too shallow to find anything. Read it with the warm-cap refusal count beside it."
    ),
    "cache": (
        "This is deliberately a STATE, not a percentage — there is no good/bad number here, "
        "which is the honest answer to 'is 83% bad?'. A cache hit rate has no universal "
        "target: it depends entirely on how much of a prompt is stable prefix, so 83% may be "
        "excellent for one agent type and poor for another. What IS meaningful is a DROP: a "
        "prefix that was stable and stopped being stable means something changed a system "
        "prompt or tool list and every later call now pays full input price. That is why this "
        "tile alarms on a fall against each agent type's own recent baseline and names the "
        "agent responsible, instead of showing a fleet number to optimize."
    ),
    "subagent_share": (
        "Direction: neither up nor down is inherently good — this describes HOW the fleet "
        "spends, not whether it should. There is no established target share. What it is "
        "for: a high share here means most token spend happens inside DISPATCHED sub-agents, "
        "not the interactive main thread — so a strategy that only tunes the main assistant's "
        "prompt is optimizing the smaller share of real spend. A rising share over time means "
        "more work is being delegated to sub-agents; read it together with the spend-by-model "
        "chart below to see whether that delegation is landing on cheaper or more expensive "
        "models. Sourced from ccdash, which has no excluded population here (unlike most of "
        "this page) — is_sidechain is populated on every usage record."
    ),
    "leverage": (
        "Direction: HIGHER is better, and there is no ceiling — this fleet runs on six Claude "
        "Max seats at a FIXED $1,200/mo, not metered API billing, so this ratio is api-equivalent "
        "value (what the same usage would cost on metered billing) divided by the fixed "
        "subscription cost for this window. No established target exists because the marginal "
        "cost of one more call is effectively zero — the number to watch is not this ratio "
        "itself but the Account balance tile beside it: high leverage concentrated on one "
        "account nearing its quota cap is a real constraint even though the fixed bill is the "
        "same either way. IMPORTANT LIMITATION: this ratio scales with VOLUME, not with value "
        "delivered — a runaway loop burning tokens on worthless output pushes it UP, and the "
        "number looks better. It is also a counterfactual: nobody would run this volume at "
        "metered rates, so the dollar figure is not forgone spend. Read it next to the Quality "
        "tile, which is the only thing on this page that says whether the work was any good; "
        "leverage alone can rise while quality falls."
    ),
    "account_balance": (
        "CORRECTED 2026-09-06 — this tile used to read as an idle-capacity warning; that "
        "framing was measured FALSE and has been removed. The real question is rate of "
        "consumption against a MONTHLY quota cap, not idleness: Claude Max resets monthly, and "
        "measured over a full 30-day billing period this fleet's six accounts run a genuinely "
        "BALANCED share (35/19/15/12/10/9, zero idle) — a 7-day-only reading of the SAME "
        "accounts showed one at 82% and looked alarming, and that was a recent burst, not a "
        "structural pattern. READ THE 30-DAY FIGURE for any capacity decision; read the 7-day "
        "figure only for \"what is happening right now,\" never as evidence anything is broken. "
        "This tile flags ONLY when an account's recent share both dominates (>50%) AND clearly "
        "outruns its OWN 30-day baseline (≥1.5x) — a genuine early-warning sign that account "
        "could exhaust its monthly quota before the reset, never a bare 'below some floor' "
        "idleness check. SCOPE LIMIT: this data sees only Claude Code transcripts on this "
        "machine — the console's quota also reflects claude.ai web and Desktop usage this page "
        "cannot see, so these percentages are 'share of Claude Code work,' not 'share of quota "
        "consumed,' and will not match the console's own number."
    ),
    "quality": (
        "Direction: LOWER dissent rate is better, with real caution attached. This is the rate "
        "at which a trade specialist DISAGREED with another agent's estimate-line judgment in "
        "the self-correcting loop — it is the only tile on this page that measures whether the "
        "work produced was any good, as opposed to how much of it happened or what it would "
        "cost. A falling trend across rounds (shown by the direction arrow and sparkline) is the "
        "loop converging — measured live, round 8 ran ~32% dissent and round 18 ran ~4%. A rate "
        "of exactly 0% across many rounds is NOT automatically good: it can mean review is too "
        "shallow to find anything, the same caution the Review rounds tile already carries. "
        "Trades with too few verdicts to rate (under 10) are excluded rather than "
        "shown off a handful of samples."
    ),
    "cost_vs_quality": (
        "This is the JOIN the two tiles above cannot show on their own: cost and quality read "
        "as separate panels, so a reader can see what a trade costs, and separately that "
        "dissent is falling, but never whether a GIVEN trade is expensive AND not earning it. "
        "There is NO established threshold for $/verdict — say that plainly rather than "
        "inventing one. Read high $/verdict together with dissent rate: high $/verdict + high "
        "dissent is a real candidate to re-pin, re-prompt, or replace — you are paying more for "
        "work that is disagreed with more often. High $/verdict + LOW dissent may simply be an "
        "agent doing genuinely harder work (more context, longer reasoning), not a problem — "
        "cost alone never tells you which. THE CONFOUND: dissent rate is not a pure quality "
        "measure on its own — a GC reconciling judgments ACROSS every trade SHOULD dissent more "
        "than a single-lane specialist simply because it sees more surface area to disagree "
        "with, so a high number here is a prompt to go read the underlying findings, never a "
        "verdict by itself. WINDOW MISMATCH: quality is computed over ALL recorded loop cycles "
        "(a small, bounded corpus); cost is computed over whatever spend.jsonl currently "
        "retains (rolls off at ~11 days) — $/verdict divides a lifetime figure by a rolling "
        "recent one, so it is never a rate over one shared period."
    ),
}


def render_html(data: Mapping[str, Any], body_only: bool = False) -> str:
    """Render the dashboard.

    `body_only=True` returns the BODY markup with no doctype/html/head/body
    wrapper, so the Operator Hub can INLINE this dashboard as a tab panel
    instead of linking out to a standalone file (operator directive
    2026-09-05: consolidate every section into the hub, "not to just link to
    external documents"). Both forms render from the same body string, so
    the embedded panel can never drift from the standalone page. A fragment
    carries no <style> of its own -- the host supplies it once via
    `scoped_css()`.
    """
    tel = data["telemetry"]
    days = int(data["days"])
    now: datetime.datetime = data["now"]
    today = now.date()

    # THE HEADLINE SIX (2026-09-06 re-frame). "Spend" and "Collisions per
    # day" were dropped from the headline grid to make room for the two
    # tiles the operator's finding actually asked for (Account balance,
    # Quality) without exceeding ~6 scannable tiles:
    #   - "Spend" is REPLACED by "Leverage": a fixed-cost subscription fleet
    #     has no meaningful spend threshold, and the same api-equivalent
    #     dollar figure is more actionable framed as a ratio against the
    #     $1,200/mo fixed cost (see leverage_tile()).
    #   - "Collisions per day" (friction) is CUT: its own HINTS text already
    #     states "no formal threshold is established," making it the
    #     weakest-earning tile of the original six, and multi-agent
    #     collision detail remains fully available in the "Most-churned
    #     paths" chart further down the page -- nothing it showed is lost,
    #     only demoted from the headline grid.
    # "Sub-agent token share" stays cut from the headline grid for the same
    # reason it already was before this change (see its own comment below).
    account_capacity_30d = data.get("account_capacity_30d", {"ccdash_available": False})
    account_capacity_recent = data.get("account_capacity_recent", {"ccdash_available": False})
    account_capacity_recent_days = int(data.get("account_capacity_recent_days", days))
    # READ the collector's own honesty fields rather than restating them in
    # hand-written page prose (review blocker 2). Duplicated prose can silently
    # diverge from the data -- the collector could start warning while the page
    # keeps reassuring. Fall back to the module constant only when the panel
    # itself is unavailable, so the scope limit is never simply absent.
    _cap_imbalance = account_capacity_30d.get("imbalance", {}) or {}
    # The chart caption REUSES the tile's derived verdict rather than asserting
    # its own. An earlier version hardcoded "a genuinely BALANCED spread across
    # all six seats" here -- true today, false the moment the fleet changes, and
    # it would have sat directly under a chart the tile was calling
    # "concentrated". Same defect as the tile's original hardcoded word, just
    # relocated into prose.
    _spread_word_30d = "unavailable"
    _ranked_30d_for_caption: list = []
    _capacity_scope_note = _cap_imbalance.get("scope_note") or at.ACCOUNT_SHARE_SCOPE_NOTE
    _recent_window_warning = (
        (account_capacity_recent.get("imbalance", {}) or {}).get("window_warning")
        if account_capacity_recent.get("ccdash_available")
        else None
    )
    quality = tel.get("quality_outcomes", {"cycle_telemetry_available": False})
    _series_gaps = vget(quality, "series_gaps", default=[]) or []
    # A number absent because a round was RENUMBERED is not the same as one
    # absent because a record was LOST. Flagging both as "missing" overstates
    # the problem and teaches a reader to ignore the field.
    _gaps_never_ran = [
        g for g in (vget(quality, "series_gaps_never_ran", default=[]) or []) if g in _series_gaps
    ]
    cvq = tel.get("cost_vs_quality", {"renderable": False, "reason": "not computed"})
    tiles = {
        "leverage": leverage_tile(data.get("ccdash_spend_by_model", {"ccdash_available": False}), days),
        "account_balance": account_balance_tile(
            account_capacity_30d, account_capacity_recent, account_capacity_recent_days
        ),
        "dispatch": dispatch_tile(tel, days, today, data.get("rows")),
        "convergence": convergence_tile(data["convergence"]),
        "cache": cache_tile(tel),
        "quality": quality_tile(quality),
    }
    # Caption verdict comes FROM the tile, never restated.
    _ab = tiles.get("account_balance") or {}
    if not _ab.get("error"):
        _spread_word_30d = _ab.get("spread_word", "unavailable")
        _ranked_30d_for_caption = _ab.get("ranked_30d", []) or []

    # `subagent_share` is deliberately NOT added to `tiles` above: `verdict()`
    # iterates specific named keys to compute its health-signal count, and
    # this tile is informational (no established good/bad direction, see
    # HINTS["subagent_share"]) rather than a health signal -- folding it in
    # would silently change what "ok == total_signals" means without anyone
    # having decided that on purpose. It is cut from the headline GRID (see
    # the comment above `tiles`) but still rendered as its own card further
    # down the page (see the "Where the money went" section) -- never
    # silently dropped from the page entirely.
    subagent = subagent_share_tile(data.get("ccdash_token_split", {"ccdash_available": False}))
    # MECHANICAL backstop, not a promise: raises if any panel plots the
    # anti-metric. Runs before a single byte of HTML is produced.
    at.assert_no_tokens_total_headline(PANELS)

    v = verdict(tel, tiles, days)
    health = tel.get("ledger_health", {})

    def tile_html(
        label: str,
        t: Mapping[str, Any],
        denom: str,
        extra: str = "",
        state: bool = False,
        hint: str = "",
    ) -> str:
        # `hint` answers "is this number good or bad?" -- the operator's own
        # question (2026-09-05): "I don't know if a hit rate of 83% is bad or
        # not." A number with no interpretation is not actionable, so every
        # tile carries a plain-English reading of what good and bad look
        # like, on hover AND in a click-to-open <details> (hover alone is
        # invisible on touch devices and to keyboard users).
        hint_html = ""
        title_attr = ""
        if hint:
            title_attr = f' title="{esc(hint)}"'
            hint_html = (
                f'<details class="thint"><summary>What counts as good?</summary>'
                f"<p>{esc(hint)}</p></details>"
            )
        if t.get("error"):
            return (
                f'<div class="tile"{title_attr}><span class="tlabel">{esc(label)}</span>'
                f'<span class="tval state">Not renderable</span>'
                f'<span class="tdelta">{esc(t["error"])}</span>'
                f"{hint_html}"
                f'<span class="tdenom">A panel with no denominator refuses to render '
                f"rather than show a number computed from nothing.</span></div>"
            )
        val_cls = "tval state" if state else "tval"
        spark = sparkline(t.get("spark", [])) if t.get("spark") else ""
        # A tile may supply `delta_lines` (a list of short lines, each
        # escaped individually and joined with <br>) instead of one long
        # `delta` string -- built for the account-balance tile, whose
        # single-sentence delta wrapped illegibly (operator complaint
        # 2026-09-06). `delta` remains the plain-text fallback/join.
        delta_lines = t.get("delta_lines")
        if delta_lines:
            delta_html = "<br>".join(esc(line) for line in delta_lines)
        else:
            delta_html = esc(t.get("delta", ""))
        return (
            f'<div class="tile"{title_attr}><span class="tlabel">{esc(label)}</span>'
            f'<span class="{val_cls}">{t["value_html"]}</span>'
            f'<span class="tdelta {esc(t.get("direction", ""))}">{delta_html}</span>'
            f"{spark}{extra}{hint_html}"
            f'<span class="tdenom">{denom}</span></div>'
        )

    # --- tile 1: leverage (REPLACES spend as the headline dollar tile) -----
    lev = tiles["leverage"]
    if not lev.get("error"):
        lev["value_html"] = esc(lev["value"])
        lev_denom = (
            f"{esc(lev['denominator'])}.<br>"
            f"<b>Dollars are api-equivalent VALUE, never money spent</b> — this fleet "
            f"runs on {CLAUDE_MAX_SEATS} Claude Max seats at "
            f"${CLAUDE_MAX_SEAT_MONTHLY_USD:,.0f}/mo each "
            f"(${CLAUDE_MAX_FIXED_MONTHLY_USD:,.0f}/mo FIXED, not metered API billing). "
            f"Source: <code>ccdash:usage_events</code> (complete data, priced through "
            f"<code>ccdash.pricing.compute_cost_usd</code>)."
        )
    else:
        lev_denom = ""

    # --- tile: account balance (the ACTIONABLE tile) ------------------------
    #
    # BOTH WINDOWS, ALWAYS, SIDE BY SIDE (requirement 3): the 30-day
    # (billing-period) share is the PRIMARY figure -- Claude Max quota
    # resets monthly, so that is the correct denominator for a capacity
    # question -- and the recent (page `days`, usually 7d) share sits next
    # to it so a burst on the short window reads as exactly that, never as
    # a structural imbalance the 30-day figure would contradict.
    ab = tiles["account_balance"]
    if not ab.get("error"):
        cls = "alert" if ab["flagged"] else "ok"
        mark = "&#9888; " if ab["flagged"] else "&#10003; "
        ab["value_html"] = f'<span class="{cls}">{mark}{esc(ab["value"])}</span>'
        recent_by_email = dict(ab["ranked_recent"]) if ab.get("recent_available") else {}
        ranked_rows = "".join(
            (
                f"<tr><td>{esc(email)}</td>"
                f"<td class='n'>{esc(pct(int(vget(acct, 'calls', default=0)), max(1, ab['n_30d'])))}</td>"
                + (
                    f"<td class='n'>{esc(pct(int(vget(recent_by_email[email], 'calls', default=0)), max(1, ab['n_recent'])))}</td>"
                    if email in recent_by_email
                    else "<td class='n'>&mdash;</td>"
                )
                + "</tr>"
            )
            for email, acct in ab["ranked_30d"][:8]
        )
        ab_denom = (
            f"<b>30d is the billing period this page treats as authoritative for capacity</b> -- "
            f"Claude Max quota resets monthly, so a 7-day slice of that cycle is a different "
            f"picture, not a smaller version of the same one. "
            f"Denominators: {ab['n_30d']:,} attributed calls (30d), "
            f"{ab['n_recent']:,} attributed calls ({ab['recent_days']}d).<br>"
            f"<table style='margin-top:6px'><thead><tr><th>Account</th>"
            f"<th class=\"n\">Share (30d, billing period)</th>"
            f"<th class=\"n\">Share ({esc(ab['recent_days'])}d, recent)</th></tr></thead>"
            f"<tbody>{ranked_rows}</tbody></table>"
            f"<b>Scope limit:</b> this data sees ONLY Claude Code transcripts on this machine. "
            f"The console's own quota display also reflects claude.ai web and Desktop usage, "
            f"which this page CANNOT see -- so every percentage above is \"share of Claude Code "
            f"work,\" not \"share of quota consumed,\" and will not match the console."
        )
    else:
        ab_denom = ""

    # --- tile: quality (dissent rate + convergence direction) --------------
    q = tiles["quality"]
    if not q.get("error"):
        q["value_html"] = esc(q["value"])
        thin = q.get("excluded_thin") or {}
        q_denom = (
            f"{esc(q['delta'])}.<br>"
            f"{len(thin)} trade(s) excluded from the per-trade rate for carrying fewer than "
            f"{at.DISSENT_RATE_MIN_VERDICTS} verdicts.<br>"
            f"Source: <code>{esc(vget(tel.get('quality_outcomes', {}), 'source', default='cycle_telemetry'))}</code>."
        )
    else:
        q_denom = ""

    # --- tile 2: dispatches ------------------------------------------------
    d = tiles["dispatch"]
    if not d.get("error"):
        d["value_html"] = esc(d["value"])
        if d["windowed_split"]:
            d_denom = (
                f"{d['declared']:,} named agents · {d['generic']:,} generic bucket · "
                f"{d['missing']:,} no agent name.<br>Named: {esc(d['declared_pct'])} "
                f"runs in this same {days}-day window (the split and the headline "
                f"share one denominator)."
            )
        else:
            d_denom = (
                "Declared/unattributed split unavailable: the raw ledger could not be "
                "re-read, and the collector's split covers the whole ledger rather than "
                "this window. Showing it here would put a subtotal under a headline it "
                "does not belong to."
            )
    else:
        d_denom = ""

    # --- friction: CUT from the headline grid entirely (2026-09-06, see the
    # comment above `tiles = {...}` for why). The former `friction_tile()`
    # wrapper was deleted (it had no other caller); the raw metric it wrapped
    # (`churn_report.churn_and_contested_by_day()`, reached via
    # `data['friction']`) is UNCHANGED and still drives the "Most-churned
    # paths" chart card further down via `chart_contested()`.

    # --- tile 4: convergence ----------------------------------------------
    c = tiles["convergence"]
    if not c.get("error"):
        c["value_html"] = esc(c["value"]) + '<span style="font-size:14px;font-weight:500"> rounds</span>'
        c_denom = (
            f"Median over {c['chains']:,} review chains; {c['clean1']:,} needed no fix round.<br>"
            f"Warm-cap refusals: {c['warm_refusals']:,}."
            + (
                f' <span class="pill">warm n={c["warm_rows"]}, not yet interpretable</span>'
                if c["small_n"]
                else ""
            )
        )
    else:
        c_denom = ""

    # --- tile 5: cache (BINARY STATE) --------------------------------------
    k = tiles["cache"]
    if not k.get("error"):
        cls = "alert" if k["invalidated"] else "ok"
        mark = "&#9888; " if k["invalidated"] else "&#10003; "
        k["value_html"] = f'<span class="{cls}">{mark}{esc(k["state"])}</span>'
        k["delta"] = k["detail"]
        k["spark"] = []
        k_denom = (
            f"State only — deliberately no percentage to optimize. "
            f"Judged over {k['n']:,} rows carrying token counts; "
            f"{len(k['rated'])} agent types rated (at least {k['min_rows']} rows each), "
            f"of which {k['eligible']} have the {CACHE_ALARM_MIN_ROWS}+ rows needed to "
            f"raise this alarm — {k['thin']} are too thin to trip it on their own.<br>"
            f"The fleet rate itself is a diagnostic figure in the health panel below."
        )
    else:
        k_denom = ""

    # --- tile 6: subagent token share (ccdash COMPLETE data) ---------------
    sub = subagent
    if not sub.get("error"):
        sub["value_html"] = esc(sub["value"])
        sub_denom = (
            f"{sub['sub_tokens']:,} sub-agent tokens vs {sub['main_tokens']:,} main-thread "
            f"tokens, over {sub['n']:,} ccdash usage records in this same {days}-day window.<br>"
            f"Source: <code>ccdash:usage_events</code> — every row carries "
            f"<code>is_sidechain</code>, so there is no excluded population here."
        )
    else:
        sub_denom = ""

    vcls = "verdict"
    if v["headline"] in ("Needs a look", "No data", "Can't tell") or v["invalidated"]:
        vcls = "verdict bad"
    elif v["headline"] == "Mostly fine":
        vcls = "verdict warn"

    # --- Layer 4: ledger health -------------------------------------------
    mix = vget(health, "join_state_mix", default={}) or {}
    n_all = int(vget(health, "n", default=0))
    health_rows = "".join(
        f"<tr><td>{esc(state)}</td><td class='n'>{count:,}</td>"
        f"<td class='n'>{esc(pct(count, n_all))}</td></tr>"
        for state, count in sorted(mix.items(), key=lambda kv: -kv[1])
    )
    window = vget(health, "window", default={}) or {}
    cache_rate = vget(tel.get("token_buckets", {}), "cache_hit_rate")
    cache_rate_txt = (
        f"{100.0 * float(cache_rate):.2f}% over {int(vget(tel.get('token_buckets', {}), 'n', default=0)):,} rows"
        if isinstance(cache_rate, (int, float))
        else "unattributable"
    )
    buckets = vget(tel.get("token_buckets", {}), "buckets", default={}) or {}
    bucket_rows = "".join(
        f"<tr><td>{esc(name)}</td><td class='n'>{int(vget(buckets, name, default=0)):,}</td></tr>"
        for name in ("input", "output", "cache_read", "cache_creation")
    )

    per_agent_cache = ""
    if not k.get("error"):
        per_agent_cache = "".join(
            f"<tr><td>{esc(name)}</td><td class='n'>{100.0 * rate:.2f}%</td>"
            f"<td class='n'>{n:,}</td></tr>"
            for name, rate, n in k["rated"][:12]
        )

    # --- ccdash: complete spend by model (recovers Fable's real share) -----
    ccdash_spend = data.get("ccdash_spend_by_model", {"ccdash_available": False})
    if ccdash_spend.get("ccdash_available"):
        ccdash_total = float(vget(ccdash_spend, "total_usd", default=0.0) or 0.0)
        ccdash_n = int(vget(ccdash_spend, "n", default=0))
        ccdash_seen = int(ccdash_spend.get("rows_seen", ccdash_n))
        ccdash_unpriceable = int(vget(ccdash_spend, "unpriceable", "rows", default=0))
        ccdash_spend_note = (
            f"Priced {usd(ccdash_total)} from {esc(pct(ccdash_n, ccdash_seen))} ccdash usage "
            f"records in this {days}-day window — a COMPLETE source (ccdash parses "
            f"<code>message.usage</code> off every transcript record directly; it has no "
            f"model-missing gap the way spend.jsonl does). "
            f"{ccdash_unpriceable:,} rows carry a model ccdash's pricing table does not "
            f"recognize and are excluded, never counted as $0."
        )
    else:
        ccdash_spend_note = f"ccdash unavailable: {esc(ccdash_spend.get('reason', 'unknown'))}"

    # --- ccdash: cache write TTL split (5m vs 1h) ---------------------------
    ccdash_ttl = data.get("ccdash_cache_ttl_split", {"ccdash_available": False})
    if ccdash_ttl.get("ccdash_available"):
        w5 = int(vget(ccdash_ttl, "writes_5m_tokens", default=0))
        w1h = int(vget(ccdash_ttl, "writes_1h_tokens", default=0))
        ttl_note = (
            f"5-minute TTL writes: {w5:,} tokens · 1-hour TTL writes: {w1h:,} tokens "
            f"({esc(pct(w1h, w5 + w1h))} of writes are 1-hour). "
            f"Source: <code>ccdash:usage_events</code> (ephemeral_5m_tokens / "
            f"ephemeral_1h_tokens are separate columns, parsed directly off the "
            f"transcript's own cache_creation block) — this split is NOT unattributable "
            f"when ccdash is available; spend.jsonl alone cannot make it because it "
            f"collapses both TTLs into one cache_creation bucket."
        )
    else:
        ttl_note = (
            f"ccdash unavailable ({esc(ccdash_ttl.get('reason', 'unknown'))}): falling back to "
            f"spend.jsonl, which collapses 5-minute and 1-hour cache writes into one bucket "
            f"and cannot split them — <b>unattributable</b> from that source alone."
        )

    # --- ccdash JOIN spend.jsonl: per-agent-type spend from COMPLETE tokens
    join_raw = tel.get("ccdash_agent_type_join", {})
    _join_total_usd = 0.0
    if not join_raw.get("ccdash_available"):
        join_note = f"ccdash unavailable: {esc(join_raw.get('reason', 'unknown'))}"
        join_rows_html = ""
    elif join_raw.get("error"):
        join_note = esc(join_raw["error"])
        join_rows_html = ""
    else:
        reliable = bool(join_raw.get("reliable"))
        by_type_usd = vget(join_raw, "by_agent_type_usd", default={}) or {}
        by_tm = vget(join_raw, "by_agent_type_model_usd", default={}) or {}
        calls_bt = vget(join_raw, "calls_by_agent_type", default={}) or {}
        _tot = sum(float(x) for x in by_type_usd.values()) or 0.0
        _join_total_usd = _tot
        # THE DECISION TABLE (2026-09-05). Spend alone cannot answer the
        # question an operator actually asks -- "which agent should move to a
        # cheaper model" -- because $6k on opus and $6k on high-volume sonnet
        # call for opposite actions. So each row carries its dominant model
        # and that model's share, turning a cost report into a decision aid.
        join_rows_html = ""
        for name, vraw in list(by_type_usd.items())[:14]:
            vf = float(vraw)
            mm = by_tm.get(name) or {}
            if mm:
                top_model, top_v = max(mm.items(), key=lambda kv: float(kv[1]))
                mshare = 100.0 * float(top_v) / vf if vf else 0.0
                model_cell = (
                    f"{esc(str(top_model).replace('claude-', ''))} "
                    f"<span class='muted'>({mshare:.0f}%)</span>"
                )
            else:
                model_cell = "<span class='muted'>unattributable</span>"
            n_calls = int(calls_bt.get(name, 0) or 0)
            join_rows_html += (
                f"<tr><td>{esc(name)}</td>"
                f"<td class='n'>{usd(vf)}</td>"
                f"<td class='n'>{(100.0 * vf / _tot) if _tot else 0.0:.1f}%</td>"
                f"<td class='n'>{n_calls:,}</td>"
                f"<td>{model_cell}</td></tr>"
            )
        join_note = (
            f"{'RELIABLE' if reliable else 'LOW CONFIDENCE'}: {esc(pct(int(vget(join_raw, 'n', default=0)), int(vget(join_raw, 'total_ccdash_rows_in_window', default=0))))} "
            f"of ccdash rows in spend.jsonl's own {esc(num(vget(health, 'retention_horizon_days')))}-day "
            f"retention window matched a ledger <code>agent_id</code> carrying a real "
            f"<code>agent_type</code>. This is the highest-value join available (complete "
            f"money + tokens, joined to the roster name spend.jsonl alone can name) — but it "
            f"is bounded by spend.jsonl's own retention, not by anything about the join "
            f"itself, and reads near-zero outside that window."
        )

    body = f"""
<h1>Agent Fleet Telemetry</h1>
<p class="sub">Generated {esc(now.strftime('%Y-%m-%d %H:%M UTC'))} ·
window: last {days} days · data: <code>{esc(tel.get('ledger_path', ''))}</code></p>

<div class="{vcls}">
  <p class="vhead">{esc(v['headline'])}</p>
  <p class="vsent">{esc(v['sentence'])}</p>
  <p class="vtrust">{esc(v['trust'])}</p>
</div>

<div class="grid">
{tile_html("Leverage", lev, lev_denom, hint=HINTS["leverage"])}
{tile_html("Account balance", ab, ab_denom, hint=HINTS["account_balance"])}
{tile_html("Agent runs", d, d_denom, hint=HINTS["dispatch"])}
{tile_html("Review rounds", c, c_denom, hint=HINTS["convergence"])}
{tile_html("Cache prefix", k, k_denom, state=True, hint=HINTS["cache"])}
{tile_html("Estimate-engine quality", q, q_denom, hint=HINTS["quality"])}
</div>
<p class="note">Two tiles from the prior layout are no longer in this headline grid but remain fully
computed and available via <code>agent_telemetry.py --json</code>: <b>Spend</b> (replaced by
Leverage above — a fixed-cost subscription fleet has no meaningful spend threshold) and
<b>Collisions per day</b> (its own detail remains visible in the "Most-churned paths" chart
further down this page).</p>

<h2>Where the money went</h2>
<div class="card">
  <h3>Spend per day by model family</h3>
  {chart_spend_by_model(tel, days, today)}
  <p class="note">Zero-based axis, stacked bars (never stacked area — a moving
  baseline hides every series but the bottom one). Up to {MAX_MODEL_BANDS} families;
  any remainder is an explicit <code>other</code> band, never dropped.
  <b>Approximation disclosed:</b> the ledger gives a per-day total and a per-family
  total but not the cross-product, so each family's daily slice is apportioned by its
  share of priced spend. Daily totals are exact; the split within a day is estimated.</p>
</div>

<div class="card">
  <h3>Spend by agent type, with unattributed shown</h3>
  {chart_spend_by_flow(tel)}
  <p class="note">Ranked, zero-based. The hatched <code>unattributed</code> bar is the
  rows that carry no usable price — shown at zero dollars because their cost is
  genuinely unknown, not because it is zero. Hiding them would make the priced total
  look like all of spend when it covers about half the rows.</p>
</div>

<div class="card">
  <h3>Spend by model — COMPLETE data (source: ccdash, not spend.jsonl)</h3>
  {chart_ccdash_spend_by_model(ccdash_spend)}
  <p class="note">{ccdash_spend_note}<br>
  <b>Read this chart, not the one above, when comparing model shares.</b> The
  spend.jsonl-sourced chart above only ever sees the rows a hook managed to price
  (roughly half); this one is priced from every usage record ccdash parsed off the
  transcripts directly, so a model whose dispatches the hook under-captures — Fable is
  the measured example — shows its real share here instead of a fraction of it.</p>
</div>

<div class="card">
  <h3>Spend by agent type — joined from COMPLETE ccdash tokens</h3>
  {f'<table><thead><tr><th>Agent type</th><th class="n">USD</th><th class="n">Share</th><th class="n">Calls</th><th>Dominant model</th></tr></thead><tbody>{join_rows_html}</tbody></table>' if join_rows_html else '<p class="empty">Not renderable.</p>'}
  <p class="note"><b>How to read this as a decision:</b> a type whose spend is
  concentrated in an expensive model is a candidate to re-pin to a cheaper one; the
  same spend spread over a cheap model at high call volume is not — it is simply doing
  a lot of work, and re-pinning it would save little while costing quality. Compare the
  Share and Dominant-model columns together, never Share alone. Share is of joined,
  priced spend in this window ({esc(usd(_join_total_usd))}), NOT of the fleet total —
  work that never joined to a roster name is excluded from this table and reported
  above it.</p>
  <p class="note">{join_note}</p>
</div>

<div class="card">
  <h3>Sub-agent vs main-thread token share (complete ccdash data)</h3>
  {f'<p style="font-size:29px;font-weight:700;margin:4px 0">{sub["value_html"]}</p>' if not sub.get('error') else '<p class="empty">Not renderable.</p>'}
  <p class="note">{sub_denom if not sub.get('error') else esc(sub.get('error', ''))}</p>
  <p class="note">{esc(HINTS["subagent_share"])}</p>
</div>

<h2>Where the capacity went</h2>
<div class="card">
  {f'<p class="note" style="margin-top:0"><b>Window caution (from the collector, not restated here):</b> {esc(_recent_window_warning)}</p>' if _recent_window_warning else ''}
  <h3>Calls per account — 30 days (billing period, the authoritative window)</h3>
  {chart_account_capacity(account_capacity_30d)}
  <p class="note">Ranked, zero-based. <b>Corrected 2026-09-06:</b> Claude Max quota resets
  monthly, so this 30-day window — not a shorter slice of it — is the right denominator for a
  capacity question. Measured here: a <b>{esc(_spread_word_30d)}</b> spread across
  {len(_ranked_30d_for_caption)} seats. Source:
  <code>ccdash:usage_events JOIN session_accounts</code> — {esc(pct(int(vget(account_capacity_30d, 'n', default=0)), int(vget(account_capacity_30d, 'total_rows_seen', default=0))))}
  of usage records in this window joined to a real account email
  ({int(vget(account_capacity_30d, 'unattributed_rows', default=0)):,} did not and are excluded from
  every account's share, never folded into one).</p>
</div>

<div class="card">
  <h3>Calls per account — {account_capacity_recent_days} days (recent — "what is happening right now" only)</h3>
  {chart_account_capacity(account_capacity_recent)}
  <p class="note"><b>Do not read this chart as a capacity verdict on its own.</b> A short window
  over a monthly quota cycle can look completely different from the 30-day figure above without
  anything being wrong — measured live, this fleet's 7-day share concentrated at 82% on one
  account while its 30-day share for the SAME six accounts was a balanced 35/19/15/12/10/9. Use
  this chart only to see a recent burst; use the 30-day chart above for any capacity decision.</p>
  <p class="note"><b>Scope limit:</b> both charts on this page see only Claude Code transcripts
  on this machine. The console's own quota display also reflects claude.ai web and Desktop
  usage, which this data cannot see — {esc(_capacity_scope_note)}</p>
</div>

<h2>Is the work any good?</h2>
<div class="card">
  <p class="note" style="margin-top:0"><b>Read the source before the trend.</b> These counts come
  from CYCLE-LOG telemetry, which is DERIVED. The estimate loop's own
  <code>reviewed_scenarios</code> ledger is authoritative — it is review-gated, schema-validated,
  and what the exit contract actually reads. A round the loop failed to self-log is simply ABSENT
  here while present there, so a gap in the series is not a quiet round.{f" <b>Round numbers absent from this series: {', '.join(str(g) for g in _series_gaps)}</b> — of these, {', '.join(str(g) for g in _gaps_never_ran)} never ran at all (verified against the authoritative ledger, which holds no rows for them either; the early rounds were renumbered, so nothing is lost)." if _series_gaps else ""}
  Round 18&prime; is also absent (28 dissents / 198 verdicts per the ledger) because the loop
  skipped its self-log that night. <b>Do not read across a corpus change:</b> 18&prime; expanded
  the corpus 16&rarr;18 scenarios, judging the addition family first-class for the first time, so
  its rate is not comparable to the rounds before it — the same rule the scorer applies across a
  metric_version change. The convergence story on the STABLE corpus is 29.3% (rounds &le;8)
  &rarr; 10.8% (&ge;15) &rarr; 4.0% (round 18); 18&prime; is an expansion point, not a
  regression.</p>
  <h3>Estimate-engine loop: dissent rate by trade specialist</h3>
  {chart_quality_by_trade(quality)}
  <p class="note">Ranked high to low — the trades dissenting most often are the ones whose
  underlying findings are most worth reading. Excluded from this chart for carrying fewer
  than {at.DISSENT_RATE_MIN_VERDICTS} verdicts (too few to rate off a handful of samples):
  {', '.join(sorted((vget(quality, 'dissent_rate_by_trade_excluded_thin', default={}) or {}).keys())) or 'none'}.
  Findings by outcome: {esc(', '.join(f'{k}: {v:,}' for k, v in (vget(quality, 'findings', 'by_consolidator_decision', default={}) or {}).items())) or 'none recorded'}.</p>
</div>

<div class="card">
  <h3>Cost vs. quality, by trade — is a trade expensive AND not earning it?</h3>
  {table_cost_vs_quality(cvq)}
  <p class="note">{esc(HINTS["cost_vs_quality"])}</p>
</div>

<div class="card">
  <h3>Most-churned paths</h3>
  {chart_contested(data['friction'])}
  <p class="note">Ranked, zero-based. These are <code>churn-flagged</code> paths (a path
  committed repeatedly without a clean review). Path-level ranking is not available for
  contests themselves: those rows carry a list of overlapping paths rather than a single
  path, so ranking them would require a per-row choice the ledger does not support.</p>
</div>

<h2>Can you trust these numbers?</h2>
<div class="card">
  <h3>Ledger health</h3>
  <p class="note" style="margin-top:0">{esc(vget(health, 'confidence_clause', default=''))}</p>
  <table><thead><tr><th>Record state</th><th class="n">Rows</th><th class="n">Share</th></tr></thead>
  <tbody>{health_rows}</tbody></table>
  <p class="note">
  Window: {esc(window.get('oldest', '?'))} &rarr; {esc(window.get('newest', '?'))}
  ({esc(num(vget(health, 'retention_horizon_days')))} days on disk).
  {esc(vget(health, 'retention_warning', default=''))}<br>
  Unreleased claims: {int(vget(health, 'unreleased_rows', default=0)):,} ·
  late: {int(vget(health, 'late_rows', default=0)):,} ·
  duplicate agent-id groups: {int(vget(health, 'duplicate_agent_id_groups', default=0)):,} ·
  priceable before collapse: {esc(num(vget(health, 'pricing_coverage_raw')))}.</p>
</div>

<div class="card">
  <h3>Token buckets and cache detail</h3>
  <p class="note" style="margin-top:0">Fleet cache hit rate: <b>{esc(cache_rate_txt)}</b>
  — a diagnostic figure here, deliberately not a tile, because a visible cache-rate
  target is met by never changing a prompt again.</p>
  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px">
    <div><table><thead><tr><th>Bucket</th><th class="n">Tokens</th></tr></thead>
    <tbody>{bucket_rows}</tbody></table>
    <p class="note">The four buckets are reported separately on purpose. Their sum
    (<code>tokens_total</code>) is not shown anywhere on this page: roughly 97% of it is
    re-counted cache reads, so it overstates both cost and context by a large multiple.
    The renderer refuses mechanically, not by convention.</p></div>
    <div><table><thead><tr><th>Agent type</th><th class="n">Hit rate</th><th class="n">Rows</th></tr></thead>
    <tbody>{per_agent_cache}</tbody></table>
    <p class="note">Lowest first. Types with fewer than
    {esc(num(k.get('min_rows', 5)))} rows are excluded from rating
    ({len(k.get('sparse', {})) if not k.get('error') else 0} of them) rather than
    given a headline rate off a handful of samples.
    Cache TTL split (5-minute vs 1-hour writes): {ttl_note}</p></div>
  </div>
</div>

<footer>
Generated by <code>~/.claude/scripts/render_agent_telemetry.py</code> from
<code>hooks/agent_telemetry.py</code> (metrics) and <code>hooks/churn_report.py</code>
(friction, convergence). Self-contained: no external stylesheet, script, font, or image.
Re-run the generator to refresh; do not hand-edit this file.<br>
Deferred by design (computed and available via <code>agent_telemetry.py --json</code>,
but not shown here): latency percentiles, denials-by-reason series, cost-per-dispatch
histogram, per-agent sparkline table, call-graph tree, top-10 expensive dispatches.
Adding any of them to this page requires a specific question that someone actually asked.
</footer>
"""
    # A CONDITIONAL f-string placeholder that resolves to "" still leaves its
    # own source-line indentation behind (found 2026-09-06 by
    # exampleapp-c3: the trim-trailing-whitespace pre-commit hook was
    # rewriting the built page on every regen that hit one of these, forcing
    # an extra record-review/commit cycle each time). Two known instances
    # were fixed at their source line; this is the backstop so a THIRD one
    # -- and every future one, in a 2,300-line template with dozens of these
    # conditionals -- can never reach the page. Never trims real content:
    # only whitespace strictly AFTER the last non-whitespace character on
    # each line, which HTML already treats as insignificant.
    body = "\n".join(line.rstrip() for line in body.splitlines())
    if body_only:
        return body
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agent Fleet Telemetry</title>
<meta name="description" content="Agent fleet telemetry: spend, dispatches, friction, review convergence, cache state, and ledger trustworthiness.">
<style>{CSS}</style></head>
<body><div class="wrap">
{body}
</div></body></html>
"""


def scoped_css(scope: str = ".agent-telemetry", drop_print: bool = True) -> str:
    """This module's CSS with every rule confined to `scope`.

    An embedded fragment must not restyle its host. This module's selectors
    are deliberately generic (h1/h2/p/code/table/footer, .card/.grid/.tile/
    .note), which is correct for a standalone page and would wreck the hub
    if injected raw. At-rule preludes (@media/@keyframes) are never
    prefixed -- doing so produces invalid CSS that browsers drop silently.
    """
    def scope_selector(sel: str) -> str:
        parts = []
        for p in sel.split(","):
            p = " ".join(p.split())
            if not p:
                continue
            # `:root`/`html`/`body` carry the custom-property definitions.
            # Prefixing them yields `.agent-telemetry :root`, which matches
            # NOTHING -- every var() would resolve to nothing and the panel
            # would render unstyled. Retarget them onto the scope element so
            # the variables still cascade to the fragment, and only there.
            if p in (":root", "html", "body"):
                parts.append(scope)
            elif p.startswith(scope):
                parts.append(p)
            else:
                parts.append(f"{scope} {p}")
        return ", ".join(parts)

    def walk(css: str) -> str:
        # Brace-aware, because a naive `}`-split cannot represent a nested
        # at-rule: `@media {...}` would swallow its first inner rule into
        # the prelude and leave the braces unbalanced.
        out: list[str] = []
        i, n = 0, len(css)
        while i < n:
            brace = css.find("{", i)
            if brace == -1:
                break
            prelude = " ".join(css[i:brace].split())
            depth, j = 1, brace + 1
            while j < n and depth:
                if css[j] == "{":
                    depth += 1
                elif css[j] == "}":
                    depth -= 1
                j += 1
            inner = css[brace + 1 : j - 1]
            if prelude.startswith("@"):
                # `@media print` is a PAGE-LEVEL concern that belongs to the
                # host document, not to an embedded fragment. Emitting a
                # second one into a host page is a real defect, not cosmetic:
                # the hub's own falsifiability guard
                # (test_print_css_is_not_vacuous_against_a_missing_media_print_block)
                # strips the first print block and asserts none remain, and a
                # surviving second block silently defeats that guard. The
                # rules dropped here are `background:#fff` (the host already
                # sets it) and `break-inside:avoid` on our cards -- worth
                # having on the standalone page, not worth defeating a host's
                # guard for. The standalone page keeps its block
                # (`drop_print=False`).
                if drop_print and prelude.rstrip("{ ").strip() == "@media print":
                    i = j
                    continue
                # Keep the at-rule prelude verbatim; scope the rules INSIDE
                # it by recursing. @keyframes is the exception -- its inner
                # blocks are percentage stops, not selectors.
                body = inner if prelude.startswith("@keyframes") else walk(inner)
                out.append(f"{prelude}{{{body}}}")
            elif prelude:
                out.append(f"{scope_selector(prelude)}{{{' '.join(inner.split())}}}")
            i = j
        return "\n".join(out)

    return walk(CSS)


# ---------------------------------------------------------------------------
# Self-containment verification. This is a BUILD GATE, not a lint: an
# external resource in this page violates an absolute operator rule, so the
# generator fails rather than writes one.
# ---------------------------------------------------------------------------

_RESOURCE_ATTRS = ("src=", "href=", "url(", "@import", "srcset=", "data-src=")


def find_external_resources(markup: str) -> list[str]:
    """Return every place the page would load something off this machine.

    Deliberately NOT a bare grep for `http`: the page legitimately contains
    the word in prose and in a comment. This looks for a scheme in RESOURCE
    position -- immediately after src=/href=/url(/@import/srcset -- which is
    the only way markup can actually cause a network fetch, plus any
    protocol-relative `//host` form.
    """
    hits: list[str] = []
    low = markup.lower()
    for attr in _RESOURCE_ATTRS:
        start = 0
        while True:
            i = low.find(attr, start)
            if i < 0:
                break
            tail = low[i + len(attr) : i + len(attr) + 12].lstrip("\"' ")
            if tail.startswith(("http://", "https://", "//")):
                hits.append(markup[i : i + 90])
            start = i + len(attr)
    for tag in ("<script", "<link", "<iframe", "<img", "<video", "<audio", "<embed", "<object"):
        start = 0
        while True:
            i = low.find(tag, start)
            if i < 0:
                break
            chunk = low[i : i + 300]
            if "http://" in chunk or "https://" in chunk:
                hits.append(markup[i : i + 90])
            start = i + len(tag)
    return hits


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="render_agent_telemetry.py",
        description="Render the self-contained agent-telemetry dashboard (plan §7.1).",
    )
    p.add_argument("--out", default=DEFAULT_OUT, help=f"output HTML path (default: {DEFAULT_OUT})")
    p.add_argument("--days", type=int, default=7, help="window in days (default: 7)")
    p.add_argument("--ledger", default=None, help="path to spend.jsonl")
    p.add_argument("--projects-root", default=None, help="path to ~/.claude/projects")
    p.add_argument(
        "--transcripts",
        action="store_true",
        help="also collect transcript-derived metrics (slow; not used by the v1 page)",
    )
    p.add_argument("--open", action="store_true", help="open the rendered file in the browser")
    p.add_argument(
        "--verify",
        action="store_true",
        help="fail if the output references any external resource (always run in CI)",
    )
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    started = datetime.datetime.now()

    data = load_metrics(args.ledger, args.projects_root, args.days, args.transcripts)
    markup = render_html(data)

    external = find_external_resources(markup)
    if external:
        sys.stderr.write("REFUSING TO WRITE: external resource references found:\n")
        for hit in external[:10]:
            sys.stderr.write(f"  {hit}\n")
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(markup)

    elapsed = (datetime.datetime.now() - started).total_seconds()
    size_kb = os.path.getsize(args.out) / 1024.0
    print(f"wrote {args.out}  ({size_kb:.1f} KB, {elapsed:.1f}s, no external resources)")

    if args.verify:
        with open(args.out, "r", encoding="utf-8") as fh:
            again = find_external_resources(fh.read())
        if again:
            sys.stderr.write("VERIFY FAILED: external resources in written file\n")
            return 2
        print("verify: self-contained OK")

    if args.open:
        subprocess.run(["open", args.out], check=False)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
