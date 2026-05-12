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
    RangeInput,
    TableSpec,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH
from toolkit.user_errors import friendly_error
from tools.sub_program import logic
from tools.sub_program.logic import (
    _ACTION_VALUES,
    _DRIVER_VALUES,
    _OUTLOOK_VALUES,
    ReportSummary,
    SubProgramLine,
)

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------


_HELP_TEXT = """Sub-Program Budget Report

This tool reformats the CASES21 Annual Sub-Program Budget Report \
(GL21157 export) into a School Council-ready XLSX workbook. It optionally \
joins in prior-period commentary and flags lines that need attention \
with a pink highlight and a Status pill.

The output workbook is ready for distribution to your principal or school \
council without any manual formatting.


WHAT THIS TOOL DOES

  1. Reads the CASES21 GL21157 Annual Sub-Program Budget Report — as a PDF \
(primary) or XLSX export if your version of CASES21 supports it.
  2. Optionally reads a prior-period XLSX produced by this tool. The \
Commentary column carries forward; the Funds from Previous Years \
column rolls forward into the carry-forward field automatically.
  3. Flags every line whose Expenditure or Revenue YTD crosses the \
matching threshold with a pink highlight + a plain-English Status pill \
(Slightly over / Significant overspend / Investigate urgently / Spent \
without budget / Revenue over budget).
  4. Writes the formatted workbook with two sheets: the full Sub Program \
Report, and a Watchlist sheet that filters to only the sub-programs \
flagged for attention.


HOW TO USE THIS TOOL

  1. Sub-Program report — click Browse and select the CASES21 GL21157 PDF \
(or XLSX). This is the only required file.
  2. Prior-period comments (optional) — click Browse and select last \
month's XLSX produced by this tool. If you have no prior file, leave \
this blank.
  3. Revenue / Expense over-budget thresholds (%) — optional. Default is \
101.0% on both. Rows whose YTD crosses the matching threshold are \
flagged. Raise above 100 for a small tolerance; set high (e.g. 120) to \
narrow the Watchlist to large overruns.
  4. Ignore amounts under ($) — dollar floor for the materiality check. \
A variance below this amount is treated as chart-of-accounts noise and \
stays off the Watchlist. Default $100.
  5. Click "Generate report". A progress bar will appear while the \
tool runs; the formatted XLSX is written automatically beside the \
source PDF when it finishes. Do not open or modify the input files \
while the tool is running.
  6. When complete, review the rows on the Watchlist sheet (and the \
pink-shaded rows on the main sheet) — these are the lines that crossed \
the threshold AND meet the dollar materiality floor.


IMPORTANT NOTES

  • The output workbook is formatted for School Council submission — \
no further formatting is needed.
  • Pink rows are also flagged with a Status pill (col C) and a \
non-blank Comments cell. Colour is never the sole signal.
  • The Status pill and the Watchlist tab use the same filter. If a row \
appears on the in-app Watchlist tab, the same row is pink-shaded in the \
exported XLSX and appears on the XLSX Watchlist sheet.


SUPPORT

  This tool — feedback and questions:   feedback@schooltool.com.au

Please send feedback to feedback@schooltool.com.au
"""

# ---------------------------------------------------------------------------
# Over-budget highlight — Tk format (with leading "#") for the in-app
# treeview row tag. openpyxl fills use a separate constant elsewhere
# (logic._OVER_FILL) since openpyxl wants the 6-char hex without "#".
# ---------------------------------------------------------------------------

_OVER_BG = "#" + HL_MISMATCH

# ---------------------------------------------------------------------------
# Table column schema
# ---------------------------------------------------------------------------

# Round 45 Phase A — variance-first columns.
# Round 56 — pacing column dropped along with all pacing-based
# judgements. Variance $ + Var % carry the over-budget signal.
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
]

# Round 46 Phase B — Watchlist columns. Same shape as the headline
# tabs plus a "Why" column. Round 56: pacing column dropped; the
# Watchlist filter is now strictly over-budget (Status non-OK), so
# the only "Why" values are over-budget triggers.
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
    {"key": "why", "label": "Issue", "width": 130, "mono": False},
]


# Round 56 — _PACING_WATCH_THRESHOLD constant dropped (no pacing).


# Round 64 — Preview tab columns. Mirrors the XLSX "Sub Program Report"
# sheet (13 cols) so the user can see what the export will look like
# without opening Excel. One row per sub-program, both Revenue and
# Expenditure aggregated.
# Round 66 — column order matches the new XLSX layout: percent
# columns moved between Program name and Status. So the Preview
# tab tracks the export exactly.
_PREVIEW_COLUMNS: list[dict[str, Any]] = [
    {"key": "code", "label": "CODE", "width": 60, "mono": True},
    {"key": "name", "label": "Program name"},
    {"key": "avail_pct", "label": "Avail %", "width": 70, "align": "right", "mono": True},
    {"key": "rev_pct", "label": "Rev %", "width": 70, "align": "right", "mono": True},
    {"key": "status", "label": "Status", "width": 130, "mono": False},
    {"key": "funds", "label": "Funds prev. yrs", "width": 100, "align": "right", "mono": True},
    {"key": "budget_rev", "label": "Budget Rev", "width": 100, "align": "right", "mono": True},
    {"key": "budget_exp", "label": "Budget Exp", "width": 100, "align": "right", "mono": True},
    {"key": "rev_ytd", "label": "Rev YTD", "width": 100, "align": "right", "mono": True},
    {"key": "exp_ytd", "label": "Exp YTD", "width": 100, "align": "right", "mono": True},
    {"key": "orders", "label": "Orders", "width": 100, "align": "right", "mono": True},
    {"key": "avail", "label": "Avail Bal YTD", "width": 110, "align": "right", "mono": True},
    {"key": "comments", "label": "Comments", "width": 180},
]


def _watchlist_why(line: Any) -> str:
    """Return the short trigger label for a watchlist row.

    Round 56: Watchlist now contains only over-budget rows (Status
    non-OK). The "Why" column reduces to "Over budget" for materially-
    over rows and an empty string for the marginal cases (which won't
    appear on the Watchlist anyway since the filter is strict).
    """
    if bool(line.is_over) and bool(line.is_material):
        return "Over budget"
    if bool(line.is_over):
        return "Over budget (small)"
    return ""


# Round 55 — Summary tab dropped (was the read-down "card" tab from
# Round 49). Status pill (col 3) + Trend column (col 4) on the
# Watchlist tab now carry the same call-to-attention signal at the
# row level, without a separate summary card.


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

# Round 55 — Bridge waterfall (Round 50 Phase C) dropped per user
# direction. The school-net waterfall view is no longer a primary
# in-app concern; the OUTPUT XLSX's Sub Program Report sheet carries
# the per-program signals (Status + Trend) which are sufficient at
# the row level. School-level net comparisons can be reconstructed
# from the Summary footer if needed in a future round.


def _fmt_dollar(value: Decimal) -> str:
    """Format a Decimal as a dollar string with two decimal places."""
    return f"${value:,.2f}"


def _fmt_dollar_short(value: Decimal) -> str:
    """Round 64 — compact dollar format for the Preview tab.

    Matches the XLSX ``_ACCOUNTING_FMT`` integer renderings: zero
    renders as a centred dash so an all-zero column doesn't read as
    a wall of "$0" noise; negative values prefix the U+2212 minus
    sign. The Preview tab packs 13 columns into the visible area so
    each numeric cell needs to be terse.
    """
    if value == 0:
        return "—"
    if value < 0:
        return f"{_MINUS}${(-value):,.0f}"
    return f"${value:,.0f}"


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


# Round 56 — _fmt_pacing dropped along with the pacing field.


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

    # Round 55 UI simplification — start with the log panel collapsed.
    # The shell (toolkit.shell._build_tool_view) reads this attribute
    # and initialises the Hide/Show log toggle in the collapsed state
    # when True. Default behaviour (False) keeps the panel expanded as
    # before for tools that don't opt in.
    log_default_collapsed = True

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
        # attention with "$18,000 over the IT budget" rows.
        # Round 48 — label rewritten in plain English. The literal
        # term "materiality threshold" is finance jargon that means
        # nothing to a school business officer; "ignore amounts
        # under" describes what the input actually does.
        # Round 58 — default lowered $5,000 → $100 per user feedback.
        # The earlier $5K default suppressed too many "interesting"
        # mid-range overruns (e.g. a $3K stationery overspend that a
        # business manager would want flagged). $100 is closer to the
        # $500 hard noise floor that compute_status_pill enforces
        # internally so the slider's effect is more predictable.
        NumberInput(
            key="materiality_dollar",
            label="Ignore amounts under ($)",
            min_value=0.0,
            max_value=1_000_000.0,
            decimals=0,
            width=10,
            default=100.0,
        ),
    ]
    # No output file picker — output path is auto-derived beside the source PDF.
    output = None

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    # Per-instance state — initialised lazily on first use to keep __init__() free.
    _last_summary: ReportSummary | None = None
    # Round 51 Phase D — per-sub-program override for the 4-tuple
    # (notes, driver, outlook, action). Pre-Phase-D the value was a
    # single string (the freeform commentary); now it's a 4-tuple so
    # the inline editor's three Comboboxes round-trip cleanly without
    # needing to encode/decode through the XLSX prefix on every save.
    _commentary_overrides: dict[str, tuple[str, str, str, str]] | None = None
    _last_output_path: Path | None = None

    # Slider-preview state. Populated by run() (which also writes
    # the XLSX) and consumed by preview_update() to re-paint the
    # in-app tabs when the user drags a threshold slider without
    # re-running the parser. Round 69 removed the _export_xlsx
    # consumer along with the secondary button.
    _cached_summary: ReportSummary | None = None
    _cached_threshold: float = 101.0  # legacy combined value (mirrors expense)
    # Round 21 — per-section thresholds.
    _cached_revenue_threshold: float = 101.0
    _cached_expense_threshold: float = 101.0
    # Round 45 Phase A — dollar materiality. Round 56 dropped
    # _cached_calendar_pct (no pacing). Round 58 lowered default
    # 5000 → 100 to match the new NumberInput default.
    _cached_materiality_dollar: int = 100

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:
            # 1. Resolve paths.
            report_file = Path(paths["report_file"])

            raw_comments = paths.get("comments_file")
            comments_file: Path | None = Path(raw_comments) if raw_comments else None

            # Auto-derive output path beside the source PDF (no file picker).
            # Round 69 — the file IS written here as part of Generate
            # report; pre-R69 it was a two-step flow (Generate then
            # Export to Excel button), which added friction and meant
            # users sometimes wondered where the file went.
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

            # Round 45 Phase A — materiality dollar floor. Round 58
            # lowered default $5,000 → $100 to match the NumberInput.
            # Used when the user clears the box; coerce to int
            # (NumberField is decimals=0 but emits a string).
            raw_mat = paths.get("materiality_dollar")
            if raw_mat in (None, ""):
                materiality_dollar = 100
            else:
                try:
                    materiality_dollar = int(float(str(raw_mat)))
                except (TypeError, ValueError):
                    materiality_dollar = 100

            # 3. Delegate to logic — parse + write XLSX in one step.
            # Round 69: write_xlsx=True so Generate report is a single
            # click instead of a two-stage Generate-then-Export flow.
            summary: ReportSummary = logic.generate_report(
                report_file=report_file,
                comments_file=comments_file,
                output_file=output_file,
                progress=progress,
                over_budget_threshold=over_budget_threshold,
                revenue_threshold=revenue_threshold,
                expense_threshold=expense_threshold,
                materiality_dollar=materiality_dollar,
                write_xlsx=True,
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

            # Stash for slider preview (re-paint without re-parsing).
            self._cached_summary = summary
            self._cached_threshold = over_budget_threshold
            self._cached_revenue_threshold = revenue_threshold
            self._cached_expense_threshold = expense_threshold
            self._cached_materiality_dollar = materiality_dollar

            # Round 69: the file is already on disk, so Open output
            # folder works straight after Generate report.
            self._last_output_path = output_file

            # 4. Build ToolResult — no preview suffix since the file is
            # already written. Threshold sliders still trigger a fresh
            # write on every change via preview_update().
            return self._build_result(summary, preview=False)

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
        # Round 45 Phase A — also re-derive variance + materiality so the
        # slider preview shows the same fields the post-Run table does.
        # Round 56 — pacing dropped along with calendar_pct.
        new_lines = logic._recompute_is_over(
            self._cached_summary.lines,
            self._cached_threshold,
            revenue_threshold=self._cached_revenue_threshold,
            expense_threshold=self._cached_expense_threshold,
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

    # Round 69 — _export_xlsx method removed. Generate report now
    # writes the workbook in a single step (see run() above), and
    # the secondary "Export to Excel" button is gone from
    # secondary_actions. The file appears on disk as soon as the
    # progress bar finishes; Open output folder works straight away.

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, summary: ReportSummary, *, preview: bool = False) -> ToolResult:
        n_lines = len(summary.lines)
        n_faculties = len(summary.faculty_counts)
        # Round 62 — banner / log counts use the SAME filter as the
        # in-app Watchlist tab (is_over + is_material) so the two
        # numbers reconcile. Pre-R62 the banner counted every is_over
        # line (including immaterial ones below the $ floor) while
        # the Watchlist label counted only material ones, producing
        # confusing pairs like "7 lines over budget" + "Watchlist (6)".
        over = [ln for ln in summary.lines if ln.is_over and ln.is_material]
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
            # Round 69 — preview mode is now reserved for live slider
            # previews (preview_update); the initial Generate report
            # call writes the file and lands in non-preview mode.
            # The slider-tune suffix still makes sense for the live
            # preview path; the user can re-click Generate report to
            # re-write the file at the new threshold.
            banner_text = (
                base_banner
                + over_part
                + " Drag the threshold slider to tune; re-click Generate report to re-save."
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
                    # Round 45 Phase A — variance replaces remaining +
                    # used_pct as the headline numerics. Round 56 dropped
                    # the pacing column along with all pacing computation.
                    "variance_amount": _fmt_signed_dollar(ln.variance_amount),
                    "variance_pct": _fmt_signed_pct(ln.variance_pct),
                    "_faculty": ln.faculty or "Unknown",
                    "_over": ln.is_over,  # threshold-aware flag set by logic.py
                    "_material": ln.is_material,  # below-floor lines render muted
                    "_bg": _OVER_BG if ln.is_over else None,  # legacy fallback path
                    "_is_comment_row": False,
                    "_data_row_idx": idx,
                }
            )
            # Round 22a / Round 51 Phase D — interleave a comment sub-row
            # whenever this line has any commentary content (notes OR any
            # of the structured triplet fields).  The sub-row inherits
            # the parent's faculty filter key + over flag so faculty
            # filtering and over-budget pink fills don't visually orphan
            # the comment from its data row.  Numeric columns are blanked;
            # the description column holds the speech-bubble glyph + an
            # optional ``[Action: <value>]`` tag (when set) + the freeform
            # notes paragraph.  Driver / Outlook are not shown inline —
            # the editor surfaces them when the user opens the row.
            has_any_commentary = bool(
                ln.commentary
                or ln.commentary_driver
                or ln.commentary_outlook
                or ln.commentary_action
            )
            if has_any_commentary:
                # Build the inline display. The default surface is the
                # Action tag (the most action-relevant) plus the notes
                # paragraph. Round 1 fix (R51): when Action is blank
                # but Driver / Outlook is set, fall back to one of those
                # so the speech-bubble row never looks empty — without
                # that fallback a user who set only Driver=Ongoing
                # would see "   💬  " (nothing) until they reopened the
                # editor.
                parts: list[str] = []
                if ln.commentary_action:
                    parts.append(f"[Action: {ln.commentary_action}]")
                elif ln.commentary_driver:
                    parts.append(f"[Driver: {ln.commentary_driver}]")
                elif ln.commentary_outlook:
                    parts.append(f"[Outlook: {ln.commentary_outlook}]")
                if ln.commentary:
                    parts.append(ln.commentary)
                inline_text = " ".join(parts) if parts else ""
                table_rows.append(
                    {
                        "sub_program": "",
                        "account": "",
                        "description": f"   💬  {inline_text}",
                        "budget": "",
                        "ytd": "",
                        "variance_amount": "",
                        "variance_pct": "",
                        "_faculty": ln.faculty or "Unknown",
                        "_over": ln.is_over,
                        "_material": ln.is_material,
                        "_bg": None,  # let _row_style handle the muted styling
                        "_is_comment_row": True,
                        "_data_row_idx": idx,
                    }
                )

        # Round 55 UI simplification: faculty rail dropped per user
        # direction. The rail's "contribution to variance" signal is
        # now subsumed by the Status pill + Trend column on each row,
        # both of which surface the high-impact lines without needing
        # a separate left rail. Saves 220px of horizontal space and
        # one cognitive layer for the non-finance reader.

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

        # Round 64 — Preview tab uses a simpler row-style that ONLY
        # paints pink for sub-programs on the Watchlist (matches the
        # XLSX pink-fill condition exactly: see logic.py's
        # ``sps_on_watchlist`` set, which fires when any line of the
        # sub-program is is_over+is_material). Preview rows are per-
        # sub-program (not per-line) so the row's _on_watchlist flag
        # is set by the build step rather than re-derived here.
        def _preview_row_style(row: dict[str, Any]) -> dict[str, Any]:
            if bool(row.get("_on_watchlist")):
                return {"background": _OVER_BG, "foreground": tokens.DANGER_FG}
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

        # Round 55 — Combined view (Round 22b/23/24) and its
        # _build_combined_rows / _combined_row_style helpers were
        # consumed by the Bridge tab in Round 50, then both dropped in
        # Round 55. The aggregated subsidy / surplus totals were only
        # used as labels on the (now-deleted) Combined / Bridge tab.

        # ------------------------------------------------------------------
        # Round 46 Phase B — Watchlist tab
        # ------------------------------------------------------------------
        # Pre-filter the summary lines to over-budget rows that meet the
        # dollar materiality floor, sort by absolute variance descending,
        # and render with the signed-variance columns plus a "Why" column.
        # Round 56 — pacing trigger dropped per user direction; the
        # Watchlist is now strictly an over-budget list.
        #
        # Watchlist rows skip the comment sub-row interleaving used in
        # the Revenue / Expense tabs — the goal here is "tell me which
        # lines need attention right now", not "show me everything with
        # commentary attached". Click-to-edit still works through the
        # existing _on_row_click hook (clicking a watchlist row opens
        # the same inline comment editor).
        watchlist_lines = [ln for ln in summary.lines if ln.is_over and ln.is_material]
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

        # ------------------------------------------------------------------
        # Round 64 — Preview tab: per-sub-program aggregated view that
        # mirrors the XLSX Sub Program Report sheet layout, so the
        # user can see exactly what the export will look like without
        # opening Excel. Aggregates Revenue + Expenditure account-rows
        # of the same sub-program into one row, matching the writer's
        # per-sub-program shape.
        preview_rows = self._build_preview_rows(summary)
        preview_label = f"Preview ({len(preview_rows)})"

        # Round 55 UI simplification: Summary tab (Round 49) and Bridge
        # tab (Round 50) dropped per user direction. Status pill (col 3)
        # + Trend column (col 4) now carry the "what should I look at"
        # signal at the row level — the Summary card is redundant.
        # Bridge waterfall is similarly visualised at the school-net
        # level via the OUTPUT XLSX's Sub Program Report sheet.
        # Watchlist is now the default (index 0); Revenue / Expense
        # remain as detail tabs. Round 64 added Preview as the
        # rightmost tab — surfaces the per-sub-program aggregated
        # view (the XLSX export layout) without having to open Excel.
        table_tabs: list[tuple[str, TableSpec]] = [
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
                preview_label,
                TableSpec(
                    columns=_PREVIEW_COLUMNS,
                    rows=preview_rows,
                    row_style=_preview_row_style,
                    on_row_click=_on_row_click,
                ),
            ),
        ]

        # ------------------------------------------------------------------
        # Round 45 Phase A — metric-card strip
        # ------------------------------------------------------------------
        # Round 56 — Pacing card and Watchlist card dropped along with
        # all pacing-based judgements. The Watchlist tab itself still
        # carries the over-budget count in its tab label
        # (e.g. "Watchlist (3)"), so a separate card is redundant.
        # The faculty count is also dropped from the Sub-programs card
        # per user direction — the Faculty rail is gone (Round 55) so
        # there's no in-app navigator that would benefit from a faculty
        # tally on the headline strip.
        metric_cards: list[tuple[str, str, str | None]] = [
            (
                "Sub-programs",
                f"{n_lines}",
                "neutral",
            ),
            (
                "YTD spend",
                f"{ytd_pct}%",
                "neutral",
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
            # Round 55 — faculty rail dropped; pass None so the shell
            # skips rendering the 220px left column entirely.
            side_rail=None,
            table=table_spec,  # fallback for any path that hasn't learned tabs yet
            table_tabs=table_tabs,  # Round 22b — preferred render path
            output_path=summary.output_path,
        )

    # ------------------------------------------------------------------
    # Secondary actions
    # ------------------------------------------------------------------

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        # Round 69 — "Export to Excel" removed; the workbook is now
        # written as part of Generate report. Open output folder is
        # the only secondary action left.
        return [
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

    def _build_preview_rows(self, summary: ReportSummary) -> list[dict[str, Any]]:
        """Round 64 — build the per-sub-program Preview rows.

        Aggregates Revenue + Expenditure account-rows of the same
        sub-program into one row, mirroring the XLSX Sub Program
        Report sheet's layout (one row per sub-program with Status
        pill + Revenue / Expenditure totals + Outstanding orders +
        derived Available Balance YTD + percent columns + Comments).

        Sub-programs whose Status pill is non-OK OR whose lines are
        on the Watchlist set the ``_on_watchlist`` flag so the
        ``_preview_row_style`` function paints them pink — same
        condition as the XLSX pink fill.
        """
        from tools.sub_program.logic import compute_status_pill, render_commentary_prose

        # Aggregate per sub-program.
        rev_b: dict[str, Decimal] = {}
        rev_y: dict[str, Decimal] = {}
        exp_b: dict[str, Decimal] = {}
        exp_y: dict[str, Decimal] = {}
        orders: dict[str, Decimal] = {}
        desc: dict[str, str] = {}
        commentary: dict[str, tuple[str, str, str, str]] = {}
        sps_on_watchlist: set[str] = set()
        materiality = summary.materiality_dollar if summary.materiality_dollar else 100
        mat_dec = Decimal(str(materiality))
        for ln in summary.lines:
            sp = ln.sub_program
            kind = ln.account.lower()
            if kind.startswith("revenue"):
                rev_b[sp] = rev_b.get(sp, Decimal("0")) + ln.budget
                rev_y[sp] = rev_y.get(sp, Decimal("0")) + ln.ytd
            elif kind.startswith("expenditure"):
                exp_b[sp] = exp_b.get(sp, Decimal("0")) + ln.budget
                exp_y[sp] = exp_y.get(sp, Decimal("0")) + ln.ytd
                if ln.outstanding_orders:
                    orders[sp] = orders.get(sp, Decimal("0")) + ln.outstanding_orders
            if ln.description and sp not in desc:
                desc[sp] = ln.description
            if sp not in commentary and (
                ln.commentary
                or ln.commentary_driver
                or ln.commentary_outlook
                or ln.commentary_action
            ):
                commentary[sp] = (
                    ln.commentary,
                    ln.commentary_driver,
                    ln.commentary_outlook,
                    ln.commentary_action,
                )
            # Match the XLSX writer's per-line is_over+is_material
            # aggregation so the Preview tab's pink fill agrees with
            # the XLSX pink fill exactly.
            is_material_now = abs(ln.ytd - ln.budget) >= mat_dec
            if ln.is_over and is_material_now:
                sps_on_watchlist.add(sp)

        sub_programs = sorted(set(rev_b) | set(exp_b))
        funds = summary.prior_funds or {}
        rev_th = summary.revenue_threshold or 101.0
        exp_th = summary.expense_threshold or 101.0

        rows: list[dict[str, Any]] = []
        for sp in sub_programs:
            rb = rev_b.get(sp, Decimal("0"))
            ry = rev_y.get(sp, Decimal("0"))
            eb = exp_b.get(sp, Decimal("0"))
            ey = exp_y.get(sp, Decimal("0"))
            oo = orders.get(sp, Decimal("0"))
            f = funds.get(sp, Decimal("0"))
            avail = f + ry - ey - oo
            avail_pct = (avail / eb) if eb != 0 else Decimal("0")
            rev_pct = (ry / rb) if rb != 0 else Decimal("0")
            status = compute_status_pill(
                annual_exp_budget=eb,
                exp_ytd=ey,
                annual_rev_budget=rb,
                rev_ytd=ry,
                revenue_threshold=float(rev_th),
                expense_threshold=float(exp_th),
                materiality_dollar=int(materiality),
            )
            c_notes, c_driver, c_outlook, c_action = commentary.get(sp, ("", "", "", ""))
            comments_text = render_commentary_prose(
                notes=c_notes,
                driver=c_driver,
                outlook=c_outlook,
                action=c_action,
            )
            rows.append(
                {
                    "code": sp,
                    "name": desc.get(sp, ""),
                    "status": status,
                    "funds": _fmt_dollar_short(f),
                    "budget_rev": _fmt_dollar_short(rb),
                    "budget_exp": _fmt_dollar_short(eb),
                    "rev_ytd": _fmt_dollar_short(ry),
                    "exp_ytd": _fmt_dollar_short(ey),
                    "orders": _fmt_dollar_short(oo),
                    "avail": _fmt_dollar_short(avail),
                    "avail_pct": f"{float(avail_pct) * 100:.1f}%" if eb else "",
                    "rev_pct": f"{float(rev_pct) * 100:.1f}%" if rb else "",
                    "comments": comments_text,
                    "sub_program": sp,
                    "description": desc.get(sp, ""),
                    "_on_watchlist": sp in sps_on_watchlist,
                    "_is_comment_row": False,
                }
            )
        return rows

    def _open_inline_comment_editor(self, row: dict[str, Any]) -> None:
        """Round 22a / Round 51 Phase D — inline comment editor.

        Phase D adds three ``ttk.Combobox(state="readonly")`` widgets
        stacked above the existing ``tk.Text`` Notes widget. The four
        fields are saved as a 4-tuple in ``_commentary_overrides``;
        :func:`encode_commentary` only runs at XLSX-write time.
        """
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

        # Preload the four fields from the in-memory override (if any)
        # or, failing that, from the cached summary's first matching
        # line. Matches the pre-Phase-D ordering: override > cached.
        notes_init = ""
        driver_init = ""
        outlook_init = ""
        action_init = ""
        if self._commentary_overrides and sub_program in self._commentary_overrides:
            notes_init, driver_init, outlook_init, action_init = self._commentary_overrides[
                sub_program
            ]
        else:
            for ln in self._cached_summary.lines:
                if ln.sub_program == sub_program and (
                    ln.commentary
                    or ln.commentary_driver
                    or ln.commentary_outlook
                    or ln.commentary_action
                ):
                    notes_init = ln.commentary
                    driver_init = ln.commentary_driver
                    outlook_init = ln.commentary_outlook
                    action_init = ln.commentary_action
                    break

        description = str(row.get("description") or "").strip()
        account = str(row.get("account") or "").strip()
        title = f"Comment - {sub_program} {description} ({account})".strip()

        win = tk.Toplevel(root)
        win.title(title)
        # Larger than pre-Phase-D (520×240) to accommodate the three
        # Combobox rows above the Notes editor without crushing them.
        win.geometry("560x360")
        win.minsize(420, 300)
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

        # ----- Structured-triplet form -----
        # Combobox values include "" as the first option so the user
        # can clear a previously-set value; the readonly state stops
        # them typing in arbitrary strings that won't round-trip.
        form = tk.Frame(win)
        form.pack(side="top", fill="x", padx=tokens.SP_3, pady=(0, tokens.SP_2))

        def _add_combobox_row(
            row_idx: int, label_text: str, values: tuple[str, ...], initial: str
        ) -> ttk.Combobox:
            tk.Label(
                form,
                text=label_text,
                font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13),
                anchor="w",
                width=10,
            ).grid(row=row_idx, column=0, sticky="w", padx=(0, tokens.SP_2), pady=tokens.SP_1)
            # Round 1 fix (R51): if the initial value is non-empty but
            # NOT in the canonical values tuple (e.g. a future value
            # written by a newer version of the tool, or a value
            # surviving a tuple change), include it once in the
            # dropdown for this editor session so the user can see
            # AND keep their existing categorisation. Without this
            # the Combobox would silently zero the field on open and
            # destroy the value on Save. ``decode_commentary``'s
            # unknown-value validation usually catches drift first,
            # but this is the second line of defence.
            value_list: tuple[str, ...] = ("",) + values
            if initial and initial not in value_list:
                value_list = value_list + (initial,)
            cb = ttk.Combobox(
                form,
                values=value_list,
                state="readonly",
                font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13),
            )
            cb.set(initial)
            cb.grid(row=row_idx, column=1, sticky="ew", pady=tokens.SP_1)
            form.grid_columnconfigure(1, weight=1)
            return cb

        driver_cb = _add_combobox_row(0, "Driver:", _DRIVER_VALUES, driver_init)
        outlook_cb = _add_combobox_row(1, "Outlook:", _OUTLOOK_VALUES, outlook_init)
        action_cb = _add_combobox_row(2, "Action:", _ACTION_VALUES, action_init)

        # ----- Notes paragraph -----
        tk.Label(
            win,
            text="Notes:",
            font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13),
            anchor="w",
            padx=tokens.SP_3,
        ).pack(side="top", fill="x")

        text = tk.Text(
            win,
            wrap="word",
            font=tkfont.Font(family=tokens.FONT_SANS_PRIMARY, size=tokens.FS_13),
            height=5,
        )
        text.pack(side="top", fill="both", expand=True, padx=tokens.SP_3, pady=(0, tokens.SP_2))
        if notes_init:
            text.insert("1.0", notes_init)
        text.focus_set()

        # Round 2 fix (R51): bind Tab to advance focus from the Notes
        # Text widget instead of inserting a literal tab character.
        # Without this, a keyboard-only user typing in Notes can't
        # reach Save — Tk's default ``Text`` Tab handler inserts
        # whitespace and the focus never leaves the widget.
        def _advance_tab_focus(_event: Any) -> str:
            nxt = text.tk_focusNext()
            if nxt is not None:
                nxt.focus()
            return "break"

        text.bind("<Tab>", _advance_tab_focus)

        footer = tk.Frame(win)
        footer.pack(side="bottom", fill="x", padx=tokens.SP_3, pady=tokens.SP_2)

        def _do_save() -> None:
            new_notes = text.get("1.0", "end").strip()
            new_driver = driver_cb.get().strip()
            new_outlook = outlook_cb.get().strip()
            new_action = action_cb.get().strip()
            if self._commentary_overrides is None:
                self._commentary_overrides = {}
            if new_notes or new_driver or new_outlook or new_action:
                self._commentary_overrides[sub_program] = (
                    new_notes,
                    new_driver,
                    new_outlook,
                    new_action,
                )
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
        self._cached_materiality_dollar = 100

    def _merge_commentary_overrides(self, summary: ReportSummary) -> ReportSummary:
        """Round 51 Phase D — apply the 4-tuple override per sub-program.

        Each override is ``(notes, driver, outlook, action)``. When a
        sub-program isn't in the override dict the line is returned
        unchanged.

        Round 1 fix (R51): re-derive ``over_budget_lines`` from the
        updated ``lines`` so downstream consumers (banner copy, exports,
        secondary tabs) see the freshly-edited commentary on the
        over-budget subset, not stale references to the pre-merge
        ``SubProgramLine`` instances.
        """
        if not self._commentary_overrides:
            return summary
        from dataclasses import replace

        updated_lines: list[SubProgramLine] = []
        for ln in summary.lines:
            override = self._commentary_overrides.get(ln.sub_program)
            if override is None:
                updated_lines.append(ln)
                continue
            notes, driver, outlook, action = override
            updated_lines.append(
                replace(
                    ln,
                    commentary=notes,
                    commentary_driver=driver,
                    commentary_outlook=outlook,
                    commentary_action=action,
                )
            )
        # Re-derive over_budget_lines so it points at the updated objects.
        updated_over = [ln for ln in updated_lines if ln.is_over]
        return replace(summary, lines=updated_lines, over_budget_lines=updated_over)
