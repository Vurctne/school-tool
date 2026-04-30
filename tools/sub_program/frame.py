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


_HELP_TEXT = f"""Sub-Program Budget Report

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
pink highlight (#{HL_MISMATCH}).
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
  • Over-budget rows are highlighted #{HL_MISMATCH} (pink/red). Colour is never \
the sole signal: the Used % column will exceed 100 for these rows.
  • This is a paid tool. An active licence for your school is required. \
Licence fee: $550 + GST per school per year (Seller: ZXW Investment Pty Ltd).
  • Commentary entered via "Edit commentary..." survives the session and \
is written into the output workbook as a Commentary column.


SUPPORT

  This tool — feedback and questions:   Vurctne@gmail.com

Please send feedback to Vurctne@gmail.com
"""

# ---------------------------------------------------------------------------
# Over-budget highlight (without leading #, as required by openpyxl fills)
# ---------------------------------------------------------------------------

_OVER_BG = "#" + HL_MISMATCH

# ---------------------------------------------------------------------------
# Table column schema
# ---------------------------------------------------------------------------

_TABLE_COLUMNS: list[dict[str, Any]] = [
    {"key": "sub_program", "label": "Sub-program", "width": 90, "mono": True},
    {"key": "account", "label": "Account", "width": 80, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "budget", "label": "Budget", "width": 90, "align": "right", "mono": True},
    {"key": "ytd", "label": "YTD", "width": 90, "align": "right", "mono": True},
    {"key": "remaining", "label": "Remaining", "width": 90, "align": "right", "mono": True},
    {"key": "used_pct", "label": "Used %", "width": 70, "align": "right", "mono": True},
]


def _fmt_dollar(value: Decimal) -> str:
    """Format a Decimal as a dollar string with two decimal places."""
    return f"${value:,.2f}"


def _fmt_pct(value: Decimal) -> str:
    """Format a Decimal as a percentage string with one decimal place."""
    return f"{value:.1f}%"


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

            # 3. Delegate to logic — parse only, no XLSX write.
            summary: ReportSummary = logic.generate_report(
                report_file=report_file,
                comments_file=comments_file,
                output_file=output_file,
                progress=progress,
                over_budget_threshold=over_budget_threshold,
                revenue_threshold=revenue_threshold,
                expense_threshold=expense_threshold,
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
        new_lines = logic._recompute_is_over(
            self._cached_summary.lines,
            self._cached_threshold,
            revenue_threshold=self._cached_revenue_threshold,
            expense_threshold=self._cached_expense_threshold,
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

        # Show export success banner via the shell's banner frame.
        # We drive this through the shell by updating the banner widget directly,
        # following the same pattern as master_budget post-success message.
        try:
            import tkinter as tk

            root = getattr(tk, "_default_root", None)
            if root is not None:
                # Walk widget tree to find the banner_frame for this tool.
                # The simplest approach: emit a success ToolResult via a dummy
                # call — but that would wipe the table. Instead just update the
                # banner widget in-place if it exists.
                pass
        except Exception:  # pragma: no cover
            pass

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
            over_part = f" 1 line over budget ({threshold_label}): {ob.sub_program}/{ob.account}."
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
        table_rows: list[dict[str, Any]] = []
        for ln in summary.lines:
            table_rows.append(
                {
                    "sub_program": ln.sub_program,
                    "account": ln.account,
                    "description": ln.description,
                    "budget": _fmt_dollar(ln.budget),
                    "ytd": _fmt_dollar(ln.ytd),
                    "remaining": _fmt_dollar(ln.remaining),
                    "used_pct": _fmt_pct(ln.used_pct),
                    "_faculty": ln.faculty or "Unknown",
                    "_over": ln.is_over,  # threshold-aware flag set by logic.py
                    "_bg": _OVER_BG if ln.is_over else None,  # legacy fallback path
                }
            )

        # ------------------------------------------------------------------
        # Side rail — per-faculty used-% summary
        # ------------------------------------------------------------------
        side_rail: list[RailItem] = []
        # Sort faculties alphabetically; "Unknown" always last.
        faculty_keys = sorted(
            summary.faculty_used_pct.keys(),
            key=lambda k: (k == "Unknown", k),
        )
        for fac in faculty_keys:
            used = summary.faculty_used_pct[fac]
            value = f"{int(used)} %"
            over_budget_in_faculty = any(
                ln.is_over and (ln.faculty or "Unknown") == fac for ln in summary.lines
            )
            side_rail.append(
                RailItem(
                    label=fac,
                    value=value,
                    filter_key=fac,  # opaque token; Agent I wires filter on this
                    highlight=over_budget_in_faculty,
                )
            )

        # ------------------------------------------------------------------
        # TableSpec — new render path (row_style + on_row_click)
        # ------------------------------------------------------------------
        def _row_style(row: dict[str, Any]) -> dict[str, str]:
            """Over-budget rows: pink bg + danger fg per ADR-0015 §6.

            Uses the ``_over`` boolean flag set by logic.generate_report so the
            threshold is applied consistently in both the in-app table and the
            XLSX export.  The flag is threshold-aware (is_over = used_pct >
            threshold), so raising/lowering the threshold is automatically
            reflected here without changing the formatting code.
            """
            if row.get("_over"):
                return {
                    "background": _OVER_BG,
                    "foreground": tokens.DANGER_FG,
                }
            return {}

        table_spec = TableSpec(
            columns=_TABLE_COLUMNS,
            rows=table_rows,
            row_style=_row_style,
            on_row_click=None,  # Agent I wires click-to-filter
        )

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            metrics=[],
            log_lines=log_lines,
            table_columns=_TABLE_COLUMNS,  # legacy path — KEEP as transitional safety net
            table_rows=table_rows,  # legacy path — KEEP as transitional safety net
            side_rail=side_rail,  # NEW
            table=table_spec,  # NEW
            output_path=summary.output_path,
        )

    # ------------------------------------------------------------------
    # Secondary actions
    # ------------------------------------------------------------------

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        # Design order: Edit commentary…, Export to Excel, Open output folder.
        # (Primary "Generate report" button is first — rendered by the shell.)
        return [
            ("Edit commentary...", self._edit_commentary),
            ("Export to Excel", self._export_xlsx),
            ("Open output folder", self._open_output_folder),
        ]

    def _open_output_folder(self) -> None:
        """Open the OS file explorer at the last output path. No-op until first run."""
        from toolkit.files import open_output_folder

        if self._last_output_path is None:
            try:
                import tkinter.messagebox as mb

                mb.showinfo(
                    "Open output folder",
                    "Run the report once first — then this will open the folder "
                    "containing the generated workbook.",
                )
            except Exception:  # pragma: no cover
                pass
            return

        open_output_folder(self._last_output_path)

    def _edit_commentary(self) -> None:
        """Open the CommentaryDialog primitive over the last successful run's
        sub-programs. Results are stashed in-memory; the next Generate report
        run will merge them into the output workbook.
        """
        try:
            import tkinter as tk
            import tkinter.messagebox as mb

            from toolkit.primitives import CommentaryDialog
        except Exception:  # pragma: no cover - Tk absent in CI
            return

        # Need a live Tk root. The shell creates the root; tk._default_root
        # is the implicit top-level Tk, which is the correct parent.
        root = getattr(tk, "_default_root", None)
        if root is None:
            return

        if self._last_summary is None:
            mb.showinfo(
                "Edit commentary",
                "Run the report once first — then you can edit commentary "
                "for any of its sub-programs.",
            )
            return

        sub_programs = sorted({ln.sub_program for ln in self._last_summary.lines})

        # Preload with any existing commentary (prior-period join + earlier edits).
        initial: dict[str, str] = {}
        for ln in self._last_summary.lines:
            if ln.commentary and ln.sub_program not in initial:
                initial[ln.sub_program] = ln.commentary
        if self._commentary_overrides:
            initial.update(self._commentary_overrides)

        result = CommentaryDialog(root, sub_programs, initial)
        if result is not None:
            self._commentary_overrides = result
            mb.showinfo(
                "Edit commentary",
                f"Saved commentary for {len(result)} sub-program(s). "
                "Click Generate report to write the updates to the output "
                "workbook.",
            )

    # ------------------------------------------------------------------
    # Clear (shell-level button)
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Reset Sub-Program session state.

        The shell handles UI resets (file pickers, banner, log, table, rail).
        We reset the per-instance caches so the next run starts fresh.
        """
        self._last_summary = None
        self._commentary_overrides = None
        self._last_output_path = None
        self._cached_summary = None
        self._cached_threshold = 101.0
        self._cached_revenue_threshold = 101.0
        self._cached_expense_threshold = 101.0

    def _merge_commentary_overrides(self, summary: ReportSummary) -> ReportSummary:
        """Apply ``self._commentary_overrides`` on top of the parsed summary.

        Overrides take precedence over whatever was in the prior-period
        comments file — the user has typed fresh text in the editor.
        """
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
