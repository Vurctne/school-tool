from __future__ import annotations

import traceback
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolkit import tokens
from toolkit.base_tool import (
    FileInput,
    LogLine,
    NumberInput,
    ProgressFn,
    RailItem,
    RangeInput,
    TableSpec,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH
from toolkit.user_errors import friendly_error
from tools.sub_program import logic
from tools.sub_program.logic import ReportSummary

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


_HELP_TEXT = """Sub-Program Budget Report

This tool reformats the CASES21 Annual Sub-Program Budget Report \
(GL21157 export) into a School Council-ready XLSX workbook. It optionally \
joins in prior-period commentary, flags over-budget lines with a pink \
highlight, and groups sub-programs by faculty in a left-hand rail so you \
can navigate straight to the area you need.

The output workbook is ready for distribution to your principal or school \
council without any manual formatting.


WHAT THIS TOOL DOES

  1. Reads the CASES21 GL21157 Annual Sub-Program Budget Report — as a PDF \
(primary) or XLSX export if your version of CASES21 supports it.
  2. Optionally reads a prior-period commentary XLSX and joins the \
Commentary column into the output. If omitted, the Commentary column is \
blank.
  3. Flags every line where YTD spend exceeds the annual budget with a \
pink highlight.
  4. Summarises totals across all sub-programs, grouped by faculty.
  5. Writes the formatted output workbook to your chosen path.


HOW TO USE THIS TOOL

  1. Sub-Program report — click Browse and select the CASES21 GL21157 PDF \
(or XLSX). This is the only required file.
  2. Prior-period comments (optional) — click Browse and select the \
commentary XLSX from your previous reporting period. If you have no \
commentary file, leave this blank and the tool will run without it.
  3. Over-budget threshold (%) — optional. Default is 101.0%. Rows where \
YTD spend exceeds this percentage of the annual budget are flagged pink. \
Raise above 100 for a small tolerance; set very high (e.g. 9999) to \
suppress all highlights.
  4. Click "Generate report". A progress bar will appear while the tool \
runs. Do not open or modify the input files while the tool is running.
  5. When complete, review any rows highlighted pink — these lines have \
exceeded your threshold percentage and require attention before the report is \
submitted.

The faculty rail on the left of the result table lets you jump directly \
to sub-programs belonging to a particular faculty.


IMPORTANT NOTES

  • The output workbook is formatted for School Council submission — \
no further formatting is needed.
  • Over-budget rows are highlighted in pink. Colour is never the sole \
signal: the Variance $ column shows a positive amount and the Var % \
column shows a value above 0.
  • Commentary entered via "Edit commentary..." survives the session and \
is written into the output workbook as a Commentary column.


SUPPORT

  This tool — feedback and questions:   feedback@schooltool.com.au

Please send feedback to feedback@schooltool.com.au
"""

# ---------------------------------------------------------------------------
# Over-budget highlight (without leading #, as required by openpyxl fills)
# ---------------------------------------------------------------------------

_OVER_BG = "#" + HL_MISMATCH

# ---------------------------------------------------------------------------
# Table column schema
# ---------------------------------------------------------------------------

# Round 45 Phase A — variance-first columns.
#
# Replaces the prior Budget/YTD/Remaining/Used % shape with the
# variance-analysis-aligned shape: signed Variance $ and Var % as
# headline, with Pacing as the early-warning multiplier (Used % ÷
# Calendar %; 1.00 = on pace, >1.00 = ahead of calendar). Remaining
# and Used % drop off the headline view (they're derivable; Used %
# is still kept on the dataclass for the legacy XLSX export).
_TABLE_COLUMNS: list[dict[str, Any]] = [
    {"key": "sub_program", "label": "Sub-program", "width": 90, "mono": True},
    {"key": "account", "label": "Account", "width": 80, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "budget", "label": "Budget", "width": 90, "align": "right", "mono": True},
    {"key": "ytd", "label": "YTD", "width": 90, "align": "right", "mono": True},
    {
        "key": "variance_amount",
        "label": "Variance $",
        "width": 100,
        "align": "right",
        "mono": True,
    },
    {"key": "variance_pct", "label": "Var %", "width": 70, "align": "right", "mono": True},
    # Round 48 — column header in plain English. Values render as
    # ``+4%`` / ``−10%`` / ``On track`` / ``Unknown`` rather than the
    # multiplier ``1.04``.
    {"key": "pacing", "label": "Spending pace", "width": 100, "align": "right", "mono": True},
]

# Round 46 Phase B — Watchlist columns. Same shape as the headline tabs
# plus a "Why" column at the right that names which trigger flagged the
# row:
#
#   "Over $ + pace"  — line is over budget AND above the dollar
#                       materiality floor AND pacing >= 1.10
#   "Over $"         — over budget AND above the materiality floor
#                       (pacing < 1.10 — they're on calendar but the
#                       dollar damage is already material)
#   "Pace"           — pacing >= 1.10 (10%+ ahead of calendar) but
#                       not yet over budget — early warning
#
# Sort: |variance_amount| descending so the dollar-largest concerns
# bubble to the top. Materiality and pacing thresholds come from the
# corresponding inputs (defaults: $5,000 / 1.10).
_WATCHLIST_COLUMNS: list[dict[str, Any]] = [
    {"key": "sub_program", "label": "Sub-program", "width": 90, "mono": True},
    {"key": "account", "label": "Account", "width": 80, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "budget", "label": "Budget", "width": 90, "align": "right", "mono": True},
    {"key": "ytd", "label": "YTD", "width": 90, "align": "right", "mono": True},
    {
        "key": "variance_amount",
        "label": "Variance $",
        "width": 100,
        "align": "right",
        "mono": True,
    },
    {"key": "variance_pct", "label": "Var %", "width": 70, "align": "right", "mono": True},
    {"key": "pacing", "label": "Spending pace", "width": 100, "align": "right", "mono": True},
    # Round 48 — "Issue" reads as plain English; "Why" was a
    # finance-style abbreviation that left users guessing.
    {"key": "why", "label": "Issue", "width": 130, "mono": False},
]


# Pacing threshold above which a line is flagged "ahead of pace".
# 1.10 = 10% ahead of calendar. Tuned to match the macro-level
# "danger" tone in the metric strip (also 1.10).
_PACING_WATCH_THRESHOLD = 1.10


def _watchlist_why(line: Any) -> str:
    """Return the short trigger label for a watchlist row.

    The Watchlist tab includes a line if it's over budget AND meets the
    dollar materiality floor (``is_over AND is_material``), OR if it's
    pacing >= 1.10 (≥10% ahead of calendar). The "Why" column names
    which trigger fired so the user can scan the right column and
    understand why each line earned its place on the list.

    Returns "" if no trigger fires (defensive — caller should not
    include such rows in the Watchlist).
    """
    over_money = bool(line.is_over) and bool(line.is_material)
    ahead_pace = float(line.pacing) >= _PACING_WATCH_THRESHOLD
    # Round 47 — wording: "$" alone reads as decorative currency rather
    # than the trigger label, so spell it out. Width-checked against
    # the column's 110 px allocation.
    # Round 48 — wording targets a non-finance reader. "Spending too
    # fast" replaces "Ahead of pace" because users with no finance
    # background read "ahead" as positive ("ahead of schedule = good").
    if over_money and ahead_pace:
        return "Over budget; spending too fast"
    if over_money:
        return "Over budget"
    if ahead_pace:
        return "Spending too fast"
    return ""


# Round 49 Phase B.3 — Summary tab columns.
#
# A plain-English read-down view designed for users with no finance
# background. Two columns: a "what" label on the left, the value on
# the right. Renders as a borderless table that reads like a card.
# Sentence-style content, e.g.:
#
#   Period            April 2026
#   Sub-programs      47 across 9 faculties
#   Spent so far      32% of annual budget
#   Spending pace     +4% (slightly ahead)
#                     [blank row as visual breather]
#   Need attention    5 sub-programs
#   IT general        Over budget by $18,000
#   Library books     Over budget by $8,400
#   ...
#
# This is the new first tab so a school business officer who's never
# run the tool lands on a one-screen summary instead of a four-tab
# data dashboard. Power users click to Watchlist / Revenue / Expense
# / Bridge for detail.
_SUMMARY_COLUMNS: list[dict[str, Any]] = [
    {"key": "label", "label": "", "width": 180, "mono": False},
    {"key": "value", "label": "", "width": 320, "mono": False},
]


# Round 22b — Combined view shows per-sub-program subsidy magnitude.
# Round 24 — Combined view headline: Net YTD per sub-program.
#
# Positive Net YTD = surplus (Revenue YTD > Expense YTD; sub-program
#   over-collecting at this point in the year).
# Negative Net YTD = subsidy (Expense YTD > Revenue YTD; school is
#   currently funding the gap from general funds).
#
# We also surface the YTD sides individually so the user can see the
# scale, plus the budgeted net for context (is YTD trend tracking the
# annual plan?).  The pre-Round-24 unicode "Budget shape" column was
# removed — visually noisy for a 7-column table and the row colour
# tint already conveys direction.
_COMBINED_COLUMNS: list[dict[str, Any]] = [
    {"key": "sub_program", "label": "Sub-program", "width": 90, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "revenue_ytd", "label": "Revenue YTD", "width": 110, "align": "right", "mono": True},
    {"key": "expense_ytd", "label": "Expense YTD", "width": 110, "align": "right", "mono": True},
    {"key": "net_ytd", "label": "Net YTD", "width": 120, "align": "right", "mono": True},
    {
        "key": "net_budget",
        "label": "Annual budget net",
        "width": 130,
        "align": "right",
        "mono": True,
    },
]

# Round 50 Phase C — Bridge waterfall columns.
#
# Replaces Combined as the "money story" view. Reads top-to-bottom from
# Annual budget net through each faculty driver to YTD net, with a
# text-art magnitude bar so the visual waterfall feel comes through
# in a Tk Treeview without needing a Canvas-based widget.
#
# Bar palette is full-block (██) plus light shade (░░) only — those
# two glyphs render in every monospace font including DejaVu Sans Mono
# (CI fallback when Cascadia Mono isn't bundled). The eighth-block
# characters (▏▎▍▌▋▊▉) read better but lose width parity on font
# fallback; deferred per the Round 50 sparring partner's risk note.
_BRIDGE_COLUMNS: list[dict[str, Any]] = [
    {"key": "step", "label": "Step", "width": 200, "mono": False},
    {"key": "amount", "label": "Amount", "width": 110, "align": "right", "mono": True},
    {"key": "cumulative", "label": "Cumulative", "width": 110, "align": "right", "mono": True},
    {"key": "magnitude", "label": "Magnitude", "width": 220, "mono": True},
]

# Round 50 — Bridge bar palette. Full block + light shade.
_BRIDGE_FULL = "█"
_BRIDGE_SHADE = "░"
# Maximum bar width (in characters) — clamped so very narrow Magnitude
# columns still render.
_BRIDGE_BAR_WIDTH = 18
# When more than this many faculties contribute, fold the smallest into
# "Other faculties (n)" per the variance-analysis skill's "5–8 drivers
# max" rule. The fold preserves reconciliation (Σ folded = single
# Other amount).
_BRIDGE_MAX_DRIVERS = 6


def _build_bridge_rows(
    lines: list[Any],
) -> tuple[list[dict[str, Any]], Decimal, Decimal, Decimal]:
    """Build Bridge waterfall rows from the per-line data.

    Decomposes Annual budget net → YTD net by faculty contribution.
    Each faculty's "driver amount" is its YTD net change vs the
    annual-budget net for that faculty:

        driver = (revenue_ytd - expense_ytd) - (revenue_budget - expense_budget)
               = (rev_ytd - rev_budget) - (exp_ytd - exp_budget)

    A positive driver means the faculty improved on plan (over-collected
    or under-spent); negative means it weakened (under-collected or
    over-spent).

    Returns ``(rows, start_value, end_value, max_abs)``:
    * ``rows`` — list of dicts ready for the Bridge ``TableSpec``.
    * ``start_value`` — Annual budget net (Σ rev_b − Σ exp_b).
    * ``end_value`` — YTD net (Σ rev_y − Σ exp_y).
    * ``max_abs`` — for the bar-scale denominator, useful for tests.

    Reconciliation: ``start_value + Σ driver_amounts == end_value`` —
    holds even when "Other faculties" rolls up the smallest drivers.
    """
    # Aggregate per faculty (mirrors _build_combined_rows but keyed by
    # faculty rather than sub_program).
    rev_b: dict[str, Decimal] = {}
    exp_b: dict[str, Decimal] = {}
    rev_y: dict[str, Decimal] = {}
    exp_y: dict[str, Decimal] = {}
    for ln in lines:
        fac = ln.faculty or "Unknown"
        kind = ln.account.lower()
        if kind.startswith("revenue"):
            rev_b[fac] = rev_b.get(fac, Decimal("0")) + ln.budget
            rev_y[fac] = rev_y.get(fac, Decimal("0")) + ln.ytd
        elif kind.startswith("expenditure"):
            exp_b[fac] = exp_b.get(fac, Decimal("0")) + ln.budget
            exp_y[fac] = exp_y.get(fac, Decimal("0")) + ln.ytd

    # Annual budget net + YTD net at the school level.
    start_value = sum(rev_b.values(), Decimal("0")) - sum(exp_b.values(), Decimal("0"))
    end_value = sum(rev_y.values(), Decimal("0")) - sum(exp_y.values(), Decimal("0"))

    # Per-faculty driver amount (signed).
    # Round 50 fix #2 — include faculties that appear only in YTD maps
    # too. A new program that started spending mid-year has YTD but no
    # budget; excluding it breaks the reconciliation invariant.
    faculties = sorted(set(rev_b) | set(exp_b) | set(rev_y) | set(exp_y))
    raw_drivers: list[tuple[str, Decimal]] = []
    for fac in faculties:
        rb = rev_b.get(fac, Decimal("0"))
        ry = rev_y.get(fac, Decimal("0"))
        eb = exp_b.get(fac, Decimal("0"))
        ey = exp_y.get(fac, Decimal("0"))
        driver = (ry - rb) - (ey - eb)
        if driver != Decimal("0"):
            raw_drivers.append((fac, driver))

    # Sort by absolute magnitude descending so the biggest drivers render
    # first; this is also what the variance-analysis skill recommends.
    raw_drivers.sort(key=lambda t: -abs(t[1]))

    # Fold smallest drivers into "Other faculties (n)" once we exceed
    # the brief's 5-8 driver guideline. The threshold _BRIDGE_MAX_DRIVERS
    # is intentionally inclusive — at exactly 6 drivers we still show all
    # 6, but at 7+ we fold.
    drivers: list[tuple[str, Decimal]]
    if len(raw_drivers) > _BRIDGE_MAX_DRIVERS:
        kept = raw_drivers[: _BRIDGE_MAX_DRIVERS - 1]
        folded = raw_drivers[_BRIDGE_MAX_DRIVERS - 1 :]
        other_amount = sum((amt for _, amt in folded), Decimal("0"))
        kept.append((f"Other faculties ({len(folded)})", other_amount))
        drivers = kept
    else:
        drivers = raw_drivers

    # Bar scale: max absolute amount across start, drivers, and end.
    max_abs = max(
        [abs(start_value), abs(end_value)] + [abs(amt) for _, amt in drivers],
        default=Decimal("0"),
    )

    def _bar(amount: Decimal) -> str:
        """Text-art magnitude bar — full block + light shade track.

        Length scales linearly with |amount| / max_abs * BAR_WIDTH.
        The bar fills the leading portion with full-block characters
        (`█`) and pads the tail with light shade (`░`) so the column
        width is consistent across rows and the row's relative size
        is visually obvious — Round 50 fix #1 wired the shade track.

        Returns "" when there's no scale (zero data) or the amount
        itself is zero.
        """
        if max_abs == Decimal("0") or amount == Decimal("0"):
            return ""
        scale = abs(amount) / max_abs
        n = max(1, int(scale * Decimal(_BRIDGE_BAR_WIDTH)))
        n = min(n, _BRIDGE_BAR_WIDTH)
        return _BRIDGE_FULL * n + _BRIDGE_SHADE * (_BRIDGE_BAR_WIDTH - n)

    rows: list[dict[str, Any]] = []

    # Top: Annual budget net (full bar — represents the starting position).
    rows.append(
        {
            "step": "Annual budget net",
            "amount": "",  # no signed amount — this is the baseline
            "cumulative": _fmt_signed_dollar(start_value),
            "magnitude": _bar(start_value),
            "_kind": "anchor",
        }
    )

    # Drivers in order of descending |amount|, with running cumulative.
    cumulative = start_value
    for label, amt in drivers:
        cumulative = cumulative + amt
        rows.append(
            {
                "step": f"  {label}",
                "amount": _fmt_signed_dollar(amt),
                "cumulative": _fmt_signed_dollar(cumulative),
                "magnitude": _bar(amt),
                "_kind": "driver",
                "_signed": int(amt > 0) - int(amt < 0),  # +1 / 0 / -1
            }
        )

    # Bottom: YTD net (full bar — actual current position).
    rows.append(
        {
            "step": "YTD net",
            "amount": "",
            "cumulative": _fmt_signed_dollar(end_value),
            "magnitude": _bar(end_value),
            "_kind": "anchor",
        }
    )

    return rows, start_value, end_value, max_abs


def _build_combined_rows(
    lines: list[Any],
) -> tuple[list[dict[str, Any]], Decimal, Decimal]:
    """Aggregate Revenue + Expenditure YTD per sub-program for Combined view.

    Round 24 — switched the headline from budget-based subsidy/surplus
    to a YTD comparison.  Schools care about "is this sub-program in
    the red right now?", not "is the annual budget in the red on
    paper".  YTD captures actual performance to date.

    For each sub-program:

    * ``Revenue YTD`` and ``Expense YTD`` — actual amounts incurred
      so far.
    * ``Net YTD = Revenue YTD - Expense YTD``.  Positive = surplus
      (over-collecting / under-spending); negative = subsidy (school
      currently funding the gap).
    * ``Annual budget net = Revenue budget - Expense budget`` — the
      planned full-year position, for context.

    Returns ``(rows, total_ytd_subsidy, total_ytd_surplus)``.  Sort:
    largest YTD subsidy first (biggest current deficit), then
    largest YTD surplus, then sub-program code.

    Row tint via ``_subsidised`` (blue) / ``_surplus`` (green) flags
    keyed off the YTD net direction.
    """
    rev_b: dict[str, Decimal] = {}
    exp_b: dict[str, Decimal] = {}
    rev_y: dict[str, Decimal] = {}
    exp_y: dict[str, Decimal] = {}
    desc: dict[str, str] = {}
    faculty: dict[str, str] = {}

    for ln in lines:
        sp = ln.sub_program
        if ln.account.lower().startswith("revenue"):
            rev_b[sp] = rev_b.get(sp, Decimal("0")) + ln.budget
            rev_y[sp] = rev_y.get(sp, Decimal("0")) + ln.ytd
        elif ln.account.lower().startswith("expenditure"):
            exp_b[sp] = exp_b.get(sp, Decimal("0")) + ln.budget
            exp_y[sp] = exp_y.get(sp, Decimal("0")) + ln.ytd
        if ln.description and sp not in desc:
            desc[sp] = ln.description
        if ln.faculty and sp not in faculty:
            faculty[sp] = ln.faculty

    sub_programs = sorted(set(rev_b.keys()) | set(exp_b.keys()))

    # Per-row tuple: (sub_program, rev_ytd, exp_ytd, net_ytd, net_budget, description)
    aggregated: list[tuple[str, Decimal, Decimal, Decimal, Decimal, str]] = []
    total_ytd_subsidy = Decimal("0")  # sum of |net_ytd| where net_ytd < 0
    total_ytd_surplus = Decimal("0")  # sum of net_ytd where net_ytd > 0
    for sp in sub_programs:
        ry = rev_y.get(sp, Decimal("0"))
        ey = exp_y.get(sp, Decimal("0"))
        rb = rev_b.get(sp, Decimal("0"))
        eb = exp_b.get(sp, Decimal("0"))
        net_ytd = ry - ey
        net_budget = rb - eb
        if net_ytd < 0:
            total_ytd_subsidy += -net_ytd
        elif net_ytd > 0:
            total_ytd_surplus += net_ytd
        aggregated.append((sp, ry, ey, net_ytd, net_budget, desc.get(sp, "")))

    # Sort: biggest YTD subsidy first (most-negative net_ytd), then
    # biggest YTD surplus (most-positive), then sub-program code.
    aggregated.sort(key=lambda t: (t[3], -t[3], t[0]))

    def _fmt_signed(value: Decimal) -> str:
        """Dollar string with sign + direction marker.  ↑ = surplus,
        ↓ = subsidy (school subsidising), em-dash = exactly zero."""
        if value > 0:
            return _fmt_dollar(value) + " ↑"
        if value < 0:
            return _fmt_dollar(-value) + " ↓"
        return "—"

    rows: list[dict[str, Any]] = []
    for sp, ry, ey, net_ytd, net_budget, description in aggregated:
        rows.append(
            {
                "sub_program": sp,
                "description": description,
                "revenue_ytd": _fmt_dollar(ry),
                "expense_ytd": _fmt_dollar(ey),
                "net_ytd": _fmt_signed(net_ytd),
                "net_budget": _fmt_signed(net_budget),
                "_faculty": faculty.get(sp, "Unknown"),
                "_subsidised": net_ytd < 0,  # blue row tint
                "_surplus": net_ytd > 0,  # green row tint
                # Round 25 — raw decimals so the shell can recompute the
                # Combined tab title totals after a faculty filter
                # narrows the visible rows.
                "_net_ytd_raw": net_ytd,
                "_net_budget_raw": net_budget,
            }
        )
    return rows, total_ytd_subsidy, total_ytd_surplus


def _fmt_dollar(value: Decimal) -> str:
    """Format a Decimal as a dollar string with two decimal places."""
    return f"${value:,.2f}"


def _fmt_pct(value: Decimal) -> str:
    """Format a Decimal as a percentage string with one decimal place."""
    return f"{value:.1f}%"


# Round 45 Phase A — signed variance + pacing formatters.
#
# These follow the design-handoff numerics contract: U+2212 minus (not
# hyphen), comma thousands, sentence-case "$" prefix with no space, banker's
# rounding implicit via Decimal. The "+" sign is shown explicitly on
# positive variance so the user can scan a column of mixed signs and
# tell direction at a glance — the same convention the project's
# Combined view uses for Net YTD ↑/↓ today.
_MINUS = "−"  # U+2212 mathematical minus, per the numerics contract


def _fmt_signed_dollar(value: Decimal) -> str:
    """Format a signed Decimal dollars with explicit + or U+2212 minus."""
    if value > 0:
        return f"+${value:,.0f}"
    if value < 0:
        return f"{_MINUS}${(-value):,.0f}"
    return "$0"


def _fmt_signed_pct(value: Decimal) -> str:
    """Format a signed Decimal percent with explicit sign and 1 decimal."""
    if value > 0:
        return f"+{value:.1f}%"
    if value < 0:
        return f"{_MINUS}{(-value):.1f}%"
    return "0.0%"


def _fmt_pacing(value: Decimal) -> str:
    """Format pacing as a plain-English relative-percent.

    Pacing is the multiplier ``used_pct / calendar_pct``. Round 48
    converts the bare multiplier (e.g. ``1.04``, ``2.41``) into a
    signed relative-percent vs the calendar (``+4%``, ``+141%``) so a
    school business officer with no finance background reads it as
    "spending 4% faster than expected" without needing to be told
    that 1.0 means on-pace. Below-pace shows ``−X%`` with U+2212.

    Special cases:
    * value == 0 → "Unknown" (calendar_pct couldn't be inferred from
      the period label; pacing has no denominator).
    * value == 1.00 → "On track" — exact agreement with the calendar
      is rare enough to deserve a verbal confirmation rather than
      "+0%".
    """
    if value == 0:
        return "Unknown"
    diff_pct = (value - Decimal("1")) * Decimal("100")
    if diff_pct == 0:
        return "On track"
    sign = "+" if diff_pct > 0 else _MINUS
    return f"{sign}{abs(diff_pct):.0f}%"


class SubProgramBudgetReportTool:
    id = "sub-program"
    group = "Budget"
    label = "Sub-Program Budget Report"
    short = "SP"
    order = 30
    primary_button = "Generate report"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    # TEMPORARY: free-tier launch (Round 15). Restore to "sub_program" when paid
    # tier resumes — see docs/03_ROADMAP.md and handoff/round15_*.md.
    requires_feature = None

    inputs: list[Any] = [
        FileInput(
            key="report_file",
            label="Sub-Program report",
            filetypes=[
                ("CASES21 GL21157 report", "*.pdf *.xlsx"),
                ("All files", "*.*"),
            ],
        ),
        FileInput(
            key="comments_file",
            label="Prior-period comments (optional)",
            filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
        ),
        # Round 21 — split a single Over-budget threshold into separate
        # Revenue and Expense sliders.  Schools care about Expense
        # over-runs (the "watch this" case) but rarely flag Revenue
        # over-collections, so each section gets its own tolerance now.
        RangeInput(
            key="revenue_threshold",
            label="Revenue over-budget threshold (%)",
            min_value=100.0,
            max_value=120.0,
            default=101.0,
            step=1.0,
            live=True,
            numeric_box=True,
        ),
        RangeInput(
            key="expense_threshold",
            label="Expense over-budget threshold (%)",
            min_value=100.0,
            max_value=120.0,
            default=101.0,
            step=1.0,
            live=True,
            numeric_box=True,
            # Round 22e — pack on the same row as the Revenue threshold
            # above, side-by-side, instead of stacking vertically.
            inline_with_previous=True,
        ),
        # Round 45 Phase A — dollar materiality floor. Variances under
        # this dollar threshold render muted in the table even when
        # they exceed the percentage threshold above. This stops the
        # "$50 over a $30 stationery budget" rows from competing for
        # attention with "$18,000 over the IT budget" rows. Default
        # $5,000 — a typical sub-program-line scale at Vic schools.
        # Round 48 — label rewritten in plain English. The literal
        # term "materiality threshold" is finance jargon that means
        # nothing to a school business officer; "ignore amounts
        # under" describes what the input actually does.
        NumberInput(
            key="materiality_dollar",
            label="Ignore amounts under ($)",
            min_value=0.0,
            max_value=1_000_000.0,
            decimals=0,
            width=10,
            default=5000.0,
        ),
    ]
    # No output file picker — output path is auto-derived beside the source PDF.
    output = None

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    # Per-instance state — initialised lazily on first use to keep __init__() free.
    _last_summary: ReportSummary | None = None
    _commentary_overrides: dict[str, str] | None = None
    _last_output_path: Path | None = None

    # Two-phase preview-then-export state.
    # Populated by run(); consumed by preview_update() and _export_xlsx().
    _cached_summary: ReportSummary | None = None
    _cached_threshold: float = 101.0  # legacy combined value (mirrors expense)
    # Round 21 — per-section thresholds.
    _cached_revenue_threshold: float = 101.0
    _cached_expense_threshold: float = 101.0
    # Round 45 Phase A — dollar materiality + cached calendar pct.
    _cached_materiality_dollar: int = 5000
    _cached_calendar_pct: float = 0.0

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:
            # 1. Resolve paths.
            report_file = Path(paths["report_file"])

            raw_comments = paths.get("comments_file")
            comments_file: Path | None = Path(raw_comments) if raw_comments else None

            # Auto-derive output path beside the source PDF (no file picker).
            # Path is stashed for _export_xlsx(); not written here.
            from datetime import datetime

            ts = datetime.now().strftime("%Y%m%d_%H%M")
            stem = report_file.stem
            output_file = report_file.with_name(f"Annual_SubProgram_{stem}_AUTO_{ts}.xlsx")

            # 2. Read thresholds — default 101.0 if missing or blank.
            # Round 21 — Revenue and Expense are now independent.  We also
            # accept the legacy ``over_budget_threshold`` key as a fallback
            # so any code still referencing the old name keeps working.

            def _resolve_threshold(key: str, *fallbacks: str) -> float:
                for k in (key, *fallbacks):
                    raw = paths.get(k)
                    if raw not in (None, "", "0"):
                        try:
                            return float(str(raw))
                        except (TypeError, ValueError):
                            continue
                return 101.0

            revenue_threshold = _resolve_threshold("revenue_threshold", "over_budget_threshold")
            expense_threshold = _resolve_threshold("expense_threshold", "over_budget_threshold")
            # Combined value used by ReportSummary.over_budget_threshold for
            # backward-compat callers; pick Expense because that's the one
            # users actually act on.
            over_budget_threshold = expense_threshold

            # Round 45 Phase A — materiality dollar floor.  Default $5,000
            # if the user clears the box; coerce to int (NumberField is
            # decimals=0 but emits a string).
            raw_mat = paths.get("materiality_dollar")
            if raw_mat in (None, ""):
                materiality_dollar = 5000
            else:
                try:
                    materiality_dollar = int(float(str(raw_mat)))
                except (TypeError, ValueError):
                    materiality_dollar = 5000

            # 3. Delegate to logic — parse only, no XLSX write.
            summary: ReportSummary = logic.generate_report(
                report_file=report_file,
                comments_file=comments_file,
                output_file=output_file,
                progress=progress,
                over_budget_threshold=over_budget_threshold,
                revenue_threshold=revenue_threshold,
                expense_threshold=expense_threshold,
                materiality_dollar=materiality_dollar,
                write_xlsx=False,
            )

            # Apply any in-memory commentary overrides from the Edit commentary
            # dialog (kept between runs so the user can iterate without losing
            # their edits). TODO: write the overrides into the output workbook
            # — currently they're session-only until the logic.generate_report
            # API grows an ``overrides`` parameter.
            if self._commentary_overrides:
                summary = self._merge_commentary_overrides(summary)

            # Stash for the Edit commentary dialog so it knows the sub-program
            # IDs and existing commentary to preload.
            self._last_summary = summary

            # Stash for two-phase preview + export.
            self._cached_summary = summary
            self._cached_threshold = over_budget_threshold
            self._cached_revenue_threshold = revenue_threshold
            self._cached_expense_threshold = expense_threshold
            self._cached_materiality_dollar = materiality_dollar
            self._cached_calendar_pct = summary.calendar_pct

            # _last_output_path not set here — set when Export is called.

            # 4. Build ToolResult in preview mode.
            return self._build_result(summary, preview=True)

        except Exception as exc:
            tb = traceback.format_exc()
            fe = friendly_error(exc)
            return ToolResult(
                status="error",
                banner_level="danger",
                banner_text=fe.banner,
                log_lines=[
                    LogLine("WHAT WENT WRONG", tag="heading"),
                    LogLine(fe.message, tag="danger"),
                    LogLine("HOW TO FIX IT", tag="heading"),
                    LogLine(fe.advice, tag="muted"),
                    LogLine("TECHNICAL DETAIL (for support)", tag="heading"),
                    LogLine(fe.technical, tag="muted"),
                    LogLine(tb, tag="muted"),
                ],
                output_path=None,
            )

    # ------------------------------------------------------------------
    # preview_update — live slider drag
    # ------------------------------------------------------------------

    def preview_update(self, key: str, value: float | str) -> ToolResult | None:
        """Re-emit the result panel with a new threshold without re-parsing.

        Called by the shell (debounced ~100 ms) when either the
        ``revenue_threshold`` or ``expense_threshold`` slider changes.
        Round 21 — sliders are independent, so a change to one only
        re-flags rows in that section.

        If no summary is cached (user hasn't run Generate report yet),
        returns None so the panel is left unchanged.
        """
        # Accept legacy ``over_budget_threshold`` as an alias for
        # ``expense_threshold`` so older callers (and tests) keep working
        # without forcing every site to migrate at once.
        if key == "over_budget_threshold":
            key = "expense_threshold"
        if key not in ("revenue_threshold", "expense_threshold"):
            return None
        if self._cached_summary is None:
            return None

        try:
            new_value = float(value)
        except (TypeError, ValueError):
            new_value = 101.0

        if key == "revenue_threshold":
            self._cached_revenue_threshold = new_value
        else:
            self._cached_expense_threshold = new_value
            # Mirror into the legacy combined value so downstream code
            # that still reads .over_budget_threshold gets the
            # Expense value (the one users actually act on).
            self._cached_threshold = new_value

        from dataclasses import replace

        # Recompute is_over flags using the per-section thresholds.
        # Round 45 Phase A — also re-derive variance + pacing + materiality
        # so the slider preview shows the same fields the post-Run table
        # does.  Calendar pct is stable (extracted from the period label
        # at parse time) so we reuse the cached value.
        new_lines = logic._recompute_is_over(
            self._cached_summary.lines,
            self._cached_threshold,
            revenue_threshold=self._cached_revenue_threshold,
            expense_threshold=self._cached_expense_threshold,
            calendar_pct=self._cached_calendar_pct,
            materiality_dollar=self._cached_materiality_dollar,
        )
        new_over = [ln for ln in new_lines if ln.is_over]
        new_summary = replace(
            self._cached_summary,
            lines=new_lines,
            over_budget_lines=new_over,
            over_budget_threshold=self._cached_threshold,
            revenue_threshold=self._cached_revenue_threshold,
            expense_threshold=self._cached_expense_threshold,
        )

        self._cached_summary = new_summary

        return self._build_result(new_summary, preview=False)

    # ------------------------------------------------------------------
    # _export_xlsx — secondary action
    # ------------------------------------------------------------------

    def _export_xlsx(self) -> None:
        """Write the XLSX workbook using the current cached summary + threshold.

        Shows a messagebox if the user clicks Export before running Generate
        report.  Derives output path next to the source PDF (same as run()).

        Round 26 — pops a yes/no/cancel dialog asking whether to include
        the Combined sheet (Revenue + Expense aggregated per sub-program
        with Net YTD).  Yes → all 3 sheets; No → Rev/Exp only;
        Cancel → no export.
        """
        if self._cached_summary is None:
            try:
                import tkinter.messagebox as mb

                mb.showinfo(
                    "Export to Excel",
                    "Run Generate report first, then click Export to Excel.",
                )
            except Exception:  # pragma: no cover
                pass
            return

        summary = self._cached_summary
        threshold = self._cached_threshold

        # Round 38 — Excel output is now a single sheet matching the
        # school's own "Monthly Sub Program Report" workbook (12 columns
        # per sub-program).  The earlier yes/no/cancel dialog about
        # whether to include a Combined sheet is gone — the new shape
        # is itself the combined view, so the dialog is redundant.

        # Re-derive output path (same logic as run(); uses output_path already
        # stashed in summary from generate_report).
        output_path = summary.output_path

        try:
            logic._write_xlsx(
                lines=summary.lines,
                output_file=output_path,
                period_label=summary.period_label,
                over_budget_threshold=threshold,
            )
        except Exception as exc:
            try:
                import tkinter.messagebox as mb

                mb.showerror(
                    "Export to Excel",
                    f"Export failed: {exc}",
                )
            except Exception:  # pragma: no cover
                pass
            return

        self._last_output_path = output_path

        # Round 39 — removed dead try/except that was a placeholder for
        # an in-place banner update never implemented.  The mb.showinfo
        # below is the actual success notification the user sees.
        try:
            import tkinter.messagebox as mb

            mb.showinfo(
                "Export to Excel",
                f"Exported to:\n{output_path}\n\nClick Open output folder to view in Explorer.",
            )
        except Exception:  # pragma: no cover
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, summary: ReportSummary, *, preview: bool = False) -> ToolResult:
        n_lines = len(summary.lines)
        n_faculties = len(summary.faculty_counts)
        over = summary.over_budget_lines
        n_over = len(over)
        rev_th = summary.revenue_threshold
        exp_th = summary.expense_threshold

        # Percentage of annual budget spent YTD.
        if summary.total_budget and summary.total_budget != Decimal("0"):
            ytd_pct = int(
                (summary.total_ytd / summary.total_budget * Decimal("100")).to_integral_value()
            )
        else:
            ytd_pct = 0

        # Threshold label for banner / log.
        # Round 21 — when Revenue and Expense thresholds match, keep the
        # old single ">X%" display so existing screenshots / docs stay
        # accurate.  When they differ, show both as
        # "(Rev >X%, Exp >Y%)" so the user can see which side flagged
        # which row.
        # Round 47 — display uses ≥ to match the underlying logic
        # (`used_pct > section_th` flags strictly above; visually we
        # round up since users think in whole-percent buckets). The
        # change makes the label match what people see in screenshots
        # of the actual flagged rows, which sit at exactly the threshold
        # value or above.
        if rev_th == exp_th:
            threshold_label = f">{exp_th:g}%"
        else:
            threshold_label = f"Rev >{rev_th:g}%, Exp >{exp_th:g}%"

        # Banner text.
        base_banner = (
            f"{n_lines} sub-programs across {n_faculties} facult"
            + ("y" if n_faculties == 1 else "ies")
            + f". YTD spend {ytd_pct}% of annual."
        )
        if n_over == 0:
            over_part = f" No lines over budget ({threshold_label})."
            status: str = "success"
            banner_level: str = "ok"
        elif n_over == 1:
            ob = over[0]
            # Round 22a — name the line so the user sees "4400 Photography
            # (Revenue) — over by $19,213" rather than the cryptic
            # "4400/Revenue" form.  Description first, account suffix in
            # parentheses for context.
            over_by = ob.ytd - ob.budget
            desc = ob.description.strip() or "(no description)"
            over_part = (
                f" 1 line over budget ({threshold_label}): "
                f"{ob.sub_program} {desc} ({ob.account}) — over by ${over_by:,.2f}."
            )
            status = "warning"
            banner_level = "warning"
        else:
            over_part = f" {n_over} lines over budget ({threshold_label})."
            status = "warning"
            banner_level = "warning"

        if preview:
            banner_text = (
                base_banner
                + over_part
                + " Drag the threshold slider to tune; click Export to Excel when done."
            )
        else:
            banner_text = base_banner + over_part

        # Log lines.
        log_lines: list[LogLine] = [
            LogLine("SUB-PROGRAM BUDGET REPORT", tag="heading"),
            LogLine(
                f"{n_lines} sub-programs | {n_faculties} facult"
                + ("y" if n_faculties == 1 else "ies")
                + f" | YTD {ytd_pct}% of annual budget | threshold {threshold_label}",
                tag="ok" if n_over == 0 else "warning",
            ),
        ]
        if over:
            log_lines.append(
                LogLine(
                    f"Over-budget lines ({n_over}, used_pct {threshold_label}):",
                    tag="heading",
                )
            )
            for ln in over:
                over_by = ln.ytd - ln.budget
                log_lines.append(
                    LogLine(
                        f"  {ln.sub_program}/{ln.account} — over by ${over_by:,.2f}",
                        tag="danger",
                    )
                )
        if not preview:
            log_lines.append(LogLine(f"Output: {summary.output_path}", tag="muted"))

        # Table rows.
        # _over: bool — carries threshold-aware is_over so _row_style (below)
        #   doesn't need to re-derive the threshold; decouples formatting from
        #   the threshold value.
        # _faculty: str — opaque filter key for the side-rail click-to-filter.
        # _bg: hex | None — legacy fallback path kept as transitional safety net.
        # _is_comment_row: bool — Round 22a sub-row marker (italic muted display).
        # _data_row_idx: int — for comment sub-rows, the index of the parent
        #   data row in summary.lines so click-to-edit can resolve back.
        table_rows: list[dict[str, Any]] = []
        for idx, ln in enumerate(summary.lines):
            table_rows.append(
                {
                    "sub_program": ln.sub_program,
                    "account": ln.account,
                    "description": ln.description,
                    "budget": _fmt_dollar(ln.budget),
                    "ytd": _fmt_dollar(ln.ytd),
                    # Round 45 Phase A — variance + pacing replace
                    # remaining + used_pct as the headline numerics.
                    "variance_amount": _fmt_signed_dollar(ln.variance_amount),
                    "variance_pct": _fmt_signed_pct(ln.variance_pct),
                    "pacing": _fmt_pacing(ln.pacing),
                    "_faculty": ln.faculty or "Unknown",
                    "_over": ln.is_over,  # threshold-aware flag set by logic.py
                    "_material": ln.is_material,  # below-floor lines render muted
                    "_bg": _OVER_BG if ln.is_over else None,  # legacy fallback path
                    "_is_comment_row": False,
                    "_data_row_idx": idx,
                }
            )
            # Round 22a — interleave a comment sub-row whenever this line
            # has a non-empty commentary.  The sub-row inherits the
            # parent's faculty filter key + over flag so faculty filtering
            # and over-budget pink fills don't visually orphan the comment
            # from its data row.  Numeric columns are blanked; the
            # description column holds the comment text prefixed with a
            # speech-bubble glyph so the sub-row is unmistakable at a glance.
            if ln.commentary:
                table_rows.append(
                    {
                        "sub_program": "",
                        "account": "",
                        "description": f"   💬  {ln.commentary}",
                        "budget": "",
                        "ytd": "",
                        "variance_amount": "",
                        "variance_pct": "",
                        "pacing": "",
                        "_faculty": ln.faculty or "Unknown",
                        "_over": ln.is_over,
                        "_material": ln.is_material,
                        "_bg": None,  # let _row_style handle the muted styling
                        "_is_comment_row": True,
                        "_data_row_idx": idx,
                    }
                )

        # ------------------------------------------------------------------
        # Side rail — per-faculty contribution-to-variance summary
        # ------------------------------------------------------------------
        # Round 46 Phase B — replaced the old "used %" badge with each
        # faculty's share of the school's total dollar variance:
        #
        #     contribution[fac] = Σ |variance_amount|_fac
        #                       ÷ Σ |variance_amount|_all_faculties × 100
        #
        # Why the change: a faculty at 95% used and a faculty at 110% used
        # look roughly the same in a "used %" rail, but if the first is a
        # $200k program and the second is a $5k program, the first dwarfs
        # the second in real-world impact. Contribution puts the biggest
        # impacts at the top of the rail automatically (sort: contribution
        # descending). The data-bar tint stays green / amber / red, just
        # re-keyed to magnitude — high contribution = louder visual.
        from decimal import Decimal as _Decimal

        faculty_var_abs: dict[str, _Decimal] = {}
        total_var_abs = _Decimal("0")
        for ln in summary.lines:
            fac = ln.faculty or "Unknown"
            v = abs(ln.variance_amount)
            faculty_var_abs[fac] = faculty_var_abs.get(fac, _Decimal("0")) + v
            total_var_abs += v

        # Compute per-faculty contribution %, default to 0 when total is 0
        # (no variance anywhere — a school perfectly on budget; rare but
        # mathematically possible).
        contribution_pct: dict[str, _Decimal] = {}
        for fac, var_abs in faculty_var_abs.items():
            if total_var_abs > 0:
                contribution_pct[fac] = (var_abs / total_var_abs) * _Decimal("100")
            else:
                contribution_pct[fac] = _Decimal("0")

        # Sort: contribution desc, then "Unknown" last as a tiebreaker, then
        # alphabetical. This puts the worst offenders at the top of the rail.
        faculty_keys = sorted(
            faculty_var_abs.keys(),
            key=lambda k: (-float(contribution_pct[k]), k == "Unknown", k),
        )

        side_rail: list[RailItem] = []
        for fac in faculty_keys:
            pct = contribution_pct[fac]
            # Round 47 — drop the stray space; matches every other %
            # render in the file (_fmt_pct, _fmt_signed_pct, threshold_label).
            value = f"{int(pct)}%"
            over_budget_in_faculty = any(
                ln.is_over and (ln.faculty or "Unknown") == fac for ln in summary.lines
            )
            side_rail.append(
                RailItem(
                    label=fac,
                    value=value,
                    filter_key=fac,  # opaque token; Agent I wires filter on this
                    highlight=over_budget_in_faculty,
                    # Round 46 — bar magnitude now reflects contribution,
                    # not used %. Same SelectableList green/amber/red bands.
                    value_pct=float(pct),
                )
            )

        # ------------------------------------------------------------------
        # TableSpec — new render path (row_style + on_row_click)
        # ------------------------------------------------------------------
        def _row_style(row: dict[str, Any]) -> dict[str, Any]:
            """Per-row Tk Treeview options.

            * Over-budget rows (per the threshold-aware ``_over`` flag from
              logic.generate_report) get the pink HL_MISMATCH background +
              danger foreground per ADR-0015 §6.
            * Round 22a — comment sub-rows render with the muted FG_2 token
              and an italic Sans variant so they read as annotations
              attached to their parent data row, not as standalone data.
              Comment sub-rows under an over-budget line keep the pink
              background so the visual grouping is preserved.
            """
            is_over = bool(row.get("_over"))
            is_comment = bool(row.get("_is_comment_row"))

            if is_comment:
                # Italic + muted; pink bg only when the parent line is over.
                style: dict[str, Any] = {
                    "foreground": tokens.FG_2,
                    "font": (tokens.FONT_SANS_PRIMARY, tokens.FS_12, "italic"),
                }
                if is_over:
                    style["background"] = _OVER_BG
                return style

            if is_over:
                # Round 45 Phase A — over-budget but below dollar
                # materiality renders pink with muted FG, not the
                # full-strength danger FG, so the "$50 over a $30
                # stationery budget" rows don't compete for attention
                # with the genuine large variances.
                if not row.get("_material", True):
                    return {
                        "background": _OVER_BG,
                        "foreground": tokens.FG_2,
                    }
                return {
                    "background": _OVER_BG,
                    "foreground": tokens.DANGER_FG,
                }
            return {}

        # Round 22a — clicking a data row pops a small inline editor for
        # that line's commentary.  Comment sub-rows are skipped (clicks
        # roll up to their parent in a later iteration if needed).
        def _on_row_click(row: dict[str, Any]) -> None:
            if row.get("_is_comment_row"):
                return
            self._open_inline_comment_editor(row)

        table_spec = TableSpec(
            columns=_TABLE_COLUMNS,
            rows=table_rows,
            row_style=_row_style,
            on_row_click=_on_row_click,
        )

        # ------------------------------------------------------------------
        # Round 22b — split the dashboard into Revenue / Expense / Combined
        # tabs.  ``table_spec`` above is kept as the fallback (legacy
        # callers).  table_tabs is the new render path the shell prefers.
        # ------------------------------------------------------------------
        revenue_rows = [
            r
            for r in table_rows
            if str(r.get("account", "")).lower().startswith("revenue")
            or (
                r.get("_is_comment_row")
                and any(
                    str(prev.get("account", "")).lower().startswith("revenue")
                    for prev in table_rows[: table_rows.index(r)][-1:]
                )
            )
        ]
        expense_rows = [
            r
            for r in table_rows
            if str(r.get("account", "")).lower().startswith("expenditure")
            or (
                r.get("_is_comment_row")
                and any(
                    str(prev.get("account", "")).lower().startswith("expenditure")
                    for prev in table_rows[: table_rows.index(r)][-1:]
                )
            )
        ]

        # Build Combined-view aggregated rows + totals.
        combined_rows, total_subsidy, total_surplus = _build_combined_rows(summary.lines)

        # Round 23 — Combined view colour semantics:
        # * Subsidy (Exp > Rev) — school filling the gap → soft BLUE
        #   from canonical INFO_BG token.
        # * Surplus (Rev > Exp) — sub-program over-collecting → soft GREEN
        #   from canonical HL_SOURCE_ONLY token (already used as "source-
        #   only inserted row" green elsewhere in the toolkit).
        # Both colours come from existing tokens so the drift guard
        # ``test_no_rogue_hex_in_tool_strings`` stays happy.
        subsidy_bg = tokens.INFO_BG
        surplus_bg = "#" + tokens.HL_SOURCE_ONLY

        def _combined_row_style(row: dict[str, Any]) -> dict[str, Any]:
            if row.get("_subsidised"):
                return {"background": subsidy_bg}
            if row.get("_surplus"):
                return {"background": surplus_bg}
            return {}

        # ------------------------------------------------------------------
        # Round 46 Phase B — Watchlist tab
        # ------------------------------------------------------------------
        # Pre-filter the summary lines to those that meet at least one
        # watchlist trigger (over-budget AND material, OR pacing >= 1.10),
        # sort by absolute variance descending, and render with the
        # signed-variance / pacing columns plus a "Why" column.
        #
        # Watchlist rows skip the comment sub-row interleaving used in
        # the Revenue / Expense tabs — the goal here is "tell me which
        # lines need attention right now", not "show me everything with
        # commentary attached". Click-to-edit still works through the
        # existing _on_row_click hook (clicking a watchlist row opens
        # the same inline comment editor).
        watchlist_lines = [
            ln
            for ln in summary.lines
            if (ln.is_over and ln.is_material) or float(ln.pacing) >= _PACING_WATCH_THRESHOLD
        ]
        # Sort: |variance_amount| desc, then sub_program for stable order.
        watchlist_lines.sort(
            key=lambda ln: (-abs(ln.variance_amount), ln.sub_program),
        )

        watchlist_rows: list[dict[str, Any]] = []
        for idx, ln in enumerate(watchlist_lines):
            # Reuse the same _faculty / _over / _material flags so the
            # row_style + faculty filter logic that already work on the
            # Revenue / Expense tabs apply unchanged.
            watchlist_rows.append(
                {
                    "sub_program": ln.sub_program,
                    "account": ln.account,
                    "description": ln.description,
                    "budget": _fmt_dollar(ln.budget),
                    "ytd": _fmt_dollar(ln.ytd),
                    "variance_amount": _fmt_signed_dollar(ln.variance_amount),
                    "variance_pct": _fmt_signed_pct(ln.variance_pct),
                    "pacing": _fmt_pacing(ln.pacing),
                    "why": _watchlist_why(ln),
                    "_faculty": ln.faculty or "Unknown",
                    "_over": ln.is_over,
                    "_material": ln.is_material,
                    "_bg": _OVER_BG if ln.is_over else None,
                    "_is_comment_row": False,
                    # _data_row_idx points back into watchlist_lines so
                    # an inline comment edit on this row resolves the
                    # right SubProgramLine via sub_program / account
                    # match in _open_inline_comment_editor.
                    "_data_row_idx": idx,
                }
            )

        # Round 47 — empty Watchlist gets a reassuring suffix so the
        # user lands on "Watchlist · all clear" instead of an empty
        # table that looks broken.
        if watchlist_rows:
            watchlist_label = f"Watchlist ({len(watchlist_rows)})"
        else:
            watchlist_label = "Watchlist · all clear"

        n_revenue = sum(1 for ln in summary.lines if ln.account.lower().startswith("revenue"))
        n_expense = sum(1 for ln in summary.lines if ln.account.lower().startswith("expenditure"))
        revenue_label = f"Revenue ({n_revenue})"
        expense_label = f"Expense ({n_expense})"
        # Round 24 — Combined tab title shows YTD totals (not budget).
        # ``total_subsidy`` and ``total_surplus`` come from
        # _build_combined_rows and are now keyed off net YTD direction.
        combined_parts: list[str] = []
        if total_subsidy > 0:
            combined_parts.append(f"YTD subsidy ${total_subsidy:,.0f}")
        if total_surplus > 0:
            combined_parts.append(f"YTD surplus ${total_surplus:,.0f}")
        # Round 50 Phase C — Combined replaced by Bridge below.
        # combined_parts retained as a diagnostic; Bridge label below
        # supersedes the old Combined label.
        _ = combined_parts

        # ------------------------------------------------------------------
        # Round 50 Phase C — Bridge waterfall
        # ------------------------------------------------------------------
        # Replaces Combined as the "money story" tab. Renders top-down
        # from Annual budget net → faculty drivers (each signed) → YTD
        # net, with a text-art Magnitude column showing relative bar
        # length per row.
        bridge_rows, bridge_start, bridge_end, _bridge_max_abs = _build_bridge_rows(summary.lines)
        # Round 50 fix #6 — round before branching so a sub-dollar
        # change (e.g. Decimal("0.4")) renders as "on plan" rather
        # than "+$0".
        bridge_change = (bridge_end - bridge_start).quantize(Decimal("1"))
        if bridge_change > 0:
            bridge_label = f"Bridge · +${bridge_change:,.0f}"
        elif bridge_change < 0:
            bridge_label = f"Bridge · {_MINUS}${abs(bridge_change):,.0f}"
        else:
            bridge_label = "Bridge · on plan"

        def _bridge_row_style(row: dict[str, Any]) -> dict[str, Any]:
            """Bridge row tinting:
            * anchor rows (Annual budget net / YTD net) — bold, subtle bg
            * positive driver rows — green-tinted text
            * negative driver rows — red-tinted text
            """
            kind = row.get("_kind")
            if kind == "anchor":
                return {
                    "font": (tokens.FONT_SANS_PRIMARY, tokens.FS_13, "bold"),
                    "background": tokens.INFO_BG,
                }
            if kind == "driver":
                signed = row.get("_signed", 0)
                if signed > 0:
                    return {"foreground": tokens.OK_FG}
                if signed < 0:
                    return {"foreground": tokens.DANGER_FG}
            return {}

        # ------------------------------------------------------------------
        # Round 49 Phase B.3 — Summary tab
        # ------------------------------------------------------------------
        # The new first tab. A plain-English read-down view a school
        # business officer can scan in 10 seconds without finance
        # background. Two-column TableSpec: "what" on the left, "value"
        # on the right.
        if summary.calendar_pct > 0:
            macro_pacing_summary = float(ytd_pct) / summary.calendar_pct
            diff_pct_summary = (macro_pacing_summary - 1.0) * 100
            if abs(diff_pct_summary) < 0.5:
                pace_phrase = "On track"
            elif diff_pct_summary > 0:
                if diff_pct_summary >= 10:
                    pace_phrase = f"+{diff_pct_summary:.0f}% (well ahead)"
                else:
                    pace_phrase = f"+{diff_pct_summary:.0f}% (slightly ahead)"
            else:
                if abs(diff_pct_summary) >= 10:
                    pace_phrase = f"{_MINUS}{abs(diff_pct_summary):.0f}% (well behind)"
                else:
                    pace_phrase = f"{_MINUS}{abs(diff_pct_summary):.0f}% (slightly behind)"
        else:
            pace_phrase = "Unknown (period not detected)"

        summary_rows: list[dict[str, Any]] = [
            {"label": "Period", "value": summary.period_label or "Unknown"},
            {
                "label": "Sub-programs",
                "value": f"{n_lines} across {n_faculties} facult"
                + ("y" if n_faculties == 1 else "ies"),
            },
            {"label": "Spent so far", "value": f"{ytd_pct}% of annual budget"},
            {"label": "Spending pace", "value": pace_phrase},
            # Blank breather row before the attention list.
            {"label": "", "value": ""},
        ]

        if watchlist_lines:
            count_phrase = (
                "1 sub-program needs attention"
                if len(watchlist_lines) == 1
                else f"{len(watchlist_lines)} sub-programs need attention"
            )
            summary_rows.append(
                {
                    "label": "Need attention",
                    "value": count_phrase,
                    "_section_header": True,
                }
            )
            # Top 5 by absolute variance — the rest are still on the
            # Watchlist tab. Keep the summary card readable in one screen.
            for ln in watchlist_lines[:5]:
                desc = (ln.description or "").strip() or ln.sub_program
                if ln.is_over and ln.is_material:
                    over_by = ln.ytd - ln.budget
                    detail = f"Over budget by ${over_by:,.0f}"
                elif ln.is_over:
                    detail = "Slightly over budget"
                else:
                    detail = "Spending too fast"
                summary_rows.append({"label": f"  {desc}", "value": detail, "_attention_row": True})
            if len(watchlist_lines) > 5:
                summary_rows.append(
                    {
                        "label": f"  + {len(watchlist_lines) - 5} more",
                        "value": "(see Watchlist tab)",
                        "_attention_row": True,
                    }
                )
        else:
            summary_rows.append(
                {
                    "label": "Need attention",
                    "value": "All clear — no sub-programs flagged",
                    "_section_header": True,
                }
            )

        summary_label = "Summary"

        def _summary_row_style(row: dict[str, Any]) -> dict[str, Any]:
            """Borderless card-like styling: bold section headers, indented
            attention rows, plain rows for the headline facts."""
            if row.get("_section_header"):
                return {"font": (tokens.FONT_SANS_PRIMARY, tokens.FS_13, "bold")}
            return {}

        # Round 46 Phase B — Watchlist sits at index 1 so users still
        # land on actionable content if they skip the Summary tab. The
        # remaining tabs (Revenue / Expense / Combined) keep their
        # familiar order from prior rounds.
        table_tabs: list[tuple[str, TableSpec]] = [
            (
                summary_label,
                TableSpec(
                    columns=_SUMMARY_COLUMNS,
                    rows=summary_rows,
                    row_style=_summary_row_style,
                    on_row_click=None,
                ),
            ),
            (
                watchlist_label,
                TableSpec(
                    columns=_WATCHLIST_COLUMNS,
                    rows=watchlist_rows,
                    row_style=_row_style,
                    on_row_click=_on_row_click,
                ),
            ),
            (
                revenue_label,
                TableSpec(
                    columns=_TABLE_COLUMNS,
                    rows=revenue_rows,
                    row_style=_row_style,
                    on_row_click=_on_row_click,
                ),
            ),
            (
                expense_label,
                TableSpec(
                    columns=_TABLE_COLUMNS,
                    rows=expense_rows,
                    row_style=_row_style,
                    on_row_click=_on_row_click,
                ),
            ),
            (
                bridge_label,
                TableSpec(
                    columns=_BRIDGE_COLUMNS,
                    rows=bridge_rows,
                    row_style=_bridge_row_style,
                    on_row_click=None,
                ),
            ),
        ]

        # ------------------------------------------------------------------
        # Round 45 Phase A — metric-card strip
        # ------------------------------------------------------------------
        # Four cards summarising the run at a glance, rendered by the shell
        # via toolkit.primitives.Metric (label / big number / tone).
        #
        # 1. Sub-programs across faculties — scope of the run.
        # 2. YTD spend % of annual — how far through the budget envelope.
        # 3. Pacing — Σ used_pct / Σ calendar_pct, weighted by budget. The
        #    only macro-level early-warning signal in the report; tone is
        #    "warn" when 1.10 ≥ pacing > 1.00 ("slight ahead"), "danger"
        #    when pacing > 1.10, "ok" otherwise.
        # 4. Watchlist — count of lines that are over-threshold AND meet
        #    the dollar materiality floor. Below-materiality over-budget
        #    rows are excluded from the count by design (#4 in the brief);
        #    they still appear in the table but render muted, not danger.
        material_over = [ln for ln in summary.lines if ln.is_over and ln.is_material]
        watchlist_count = len(material_over)

        if summary.calendar_pct > 0:
            macro_pacing = float(ytd_pct) / summary.calendar_pct
        else:
            macro_pacing = 0.0
        # Round 48 — show the metric strip in the same plain-English
        # language as the Spending pace column: "+4%" / "−10%" /
        # "On track" / "Unknown".
        if macro_pacing == 0:
            pacing_value = "Unknown"
        else:
            diff = (macro_pacing - 1.0) * 100
            if abs(diff) < 0.5:
                pacing_value = "On track"
            else:
                pacing_value = f"+{diff:.0f}%" if diff > 0 else f"{_MINUS}{abs(diff):.0f}%"
        if macro_pacing == 0:
            pacing_tone: str = "neutral"
        elif macro_pacing > 1.10:
            pacing_tone = "danger"
        elif macro_pacing > 1.00:
            pacing_tone = "warn"
        else:
            pacing_tone = "ok"

        watchlist_tone: str = "ok" if watchlist_count == 0 else "danger"

        metric_cards: list[tuple[str, str, str | None]] = [
            (
                "Sub-programs",
                f"{n_lines} · {n_faculties} fac",
                "neutral",
            ),
            (
                "YTD spend",
                f"{ytd_pct}%",
                "neutral",
            ),
            (
                "Pacing",
                pacing_value,
                pacing_tone,
            ),
            (
                "Watchlist",
                str(watchlist_count),
                watchlist_tone,
            ),
        ]

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            metrics=metric_cards,
            log_lines=log_lines,
            table_columns=_TABLE_COLUMNS,  # legacy path — KEEP as transitional safety net
            table_rows=table_rows,  # legacy path — KEEP as transitional safety net
            side_rail=side_rail,
            table=table_spec,  # fallback for any path that hasn't learned tabs yet
            table_tabs=table_tabs,  # Round 22b — preferred render path
            output_path=summary.output_path,
        )

    # ------------------------------------------------------------------
    # Secondary actions
    # ------------------------------------------------------------------

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return [
            ("Export to Excel", self._export_xlsx),
            ("Open output folder", self._open_output_folder),
        ]

    def _open_output_folder(self) -> None:
        """Open the OS file explorer at the last output path."""
        from toolkit.files import open_output_folder

        if self._last_output_path is None:
            try:
                import tkinter.messagebox as mb

                mb.showinfo(
                    "Open output folder",
                    "Run the report once first - then this will open the folder "
                    "containing the generated workbook.",
                )
            except Exception:  # pragma: no cover
                pass
            return

        open_output_folder(self._last_output_path)

    def _open_inline_comment_editor(self, row: dict[str, Any]) -> None:
        """Round 22a - open a small inline comment editor for one table row."""
        try:
            import tkinter as tk
            from tkinter import font as tkfont
            from tkinter import ttk
        except Exception:  # pragma: no cover - Tk absent in CI
            return

        root = getattr(tk, "_default_root", None)
        if root is None or self._cached_summary is None:
            return

        sub_program = str(row.get("sub_program") or "").strip()
        if not sub_program:
            return

        current: str = ""
        if self._commentary_overrides and sub_program in self._commentary_overrides:
            current = self._commentary_overrides[sub_program]
        else:
            for ln in self._cached_summary.lines:
                if ln.sub_program == sub_program and ln.commentary:
                    current = ln.commentary
                    break

        description = str(row.get("description") or "").strip()
        account = str(row.get("account") or "").strip()
        title = f"Comment - {sub_program} {description} ({account})".strip()

        win = tk.Toplevel(root)
        win.title(title)
        win.geometry("520x240")
        win.minsize(380, 180)
        win.transient(root)
        win.grab_set()

        tk.Label(
            win,
            text=title,
            font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13, weight="bold"),
            anchor="w",
            padx=tokens.SP_3,
            pady=tokens.SP_2,
        ).pack(side="top", fill="x")

        text = tk.Text(
            win,
            wrap="word",
            font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13),
            height=6,
        )
        text.pack(side="top", fill="both", expand=True, padx=tokens.SP_3, pady=(0, tokens.SP_2))
        if current:
            text.insert("1.0", current)
        text.focus_set()

        footer = tk.Frame(win)
        footer.pack(side="bottom", fill="x", padx=tokens.SP_3, pady=tokens.SP_2)

        def _do_save() -> None:
            new_text = text.get("1.0", "end").strip()
            if self._commentary_overrides is None:
                self._commentary_overrides = {}
            if new_text:
                self._commentary_overrides[sub_program] = new_text
            else:
                self._commentary_overrides.pop(sub_program, None)
            win.destroy()
            self._refresh_after_comment_edit()

        ttk.Button(footer, text="Cancel", command=win.destroy).pack(side="right")
        ttk.Button(footer, text="Save", command=_do_save, style="Accent.TButton").pack(
            side="right", padx=(0, tokens.SP_2)
        )

        win.update_idletasks()
        try:
            x = root.winfo_rootx() + (root.winfo_width() - win.winfo_width()) // 2
            y = root.winfo_rooty() + (root.winfo_height() - win.winfo_height()) // 2
            win.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass

    def _refresh_after_comment_edit(self) -> None:
        if self._cached_summary is None:
            return
        merged = self._merge_commentary_overrides(self._cached_summary)
        self._cached_summary = merged
        self._last_summary = merged

        try:
            import tkinter as tk
        except Exception:  # pragma: no cover - Tk absent in CI
            return
        root = getattr(tk, "_default_root", None)
        if root is None:
            return

        result = self._build_result(merged, preview=True)

        from collections import deque

        queue: deque[Any] = deque([root])
        while queue:
            w = queue.popleft()
            render = getattr(w, "_render_result", None)
            if callable(render):
                render(self.id, result)
                return
            try:
                queue.extend(w.winfo_children())
            except Exception:  # noqa: BLE001
                continue

    def clear(self) -> None:
        """Reset Sub-Program session state."""
        self._last_summary = None
        self._commentary_overrides = None
        self._last_output_path = None
        self._cached_summary = None
        self._cached_threshold = 101.0
        self._cached_revenue_threshold = 101.0
        self._cached_expense_threshold = 101.0
        self._cached_materiality_dollar = 5000
        self._cached_calendar_pct = 0.0

    def _merge_commentary_overrides(self, summary: ReportSummary) -> ReportSummary:
        if not self._commentary_overrides:
            return summary
        from dataclasses import replace

        updated_lines = [
            replace(
                ln,
                commentary=self._commentary_overrides.get(ln.sub_program, ln.commentary),
            )
            for ln in summary.lines
        ]
        return replace(summary, lines=updated_lines)
