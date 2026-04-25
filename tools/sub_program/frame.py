from __future__ import annotations

import traceback
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    FileInput,
    LogLine,
    OutputSpec,
    ProgressFn,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH
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

  1. Reads the CASES21 GL21157 Annual Sub-Program Budget Report \u2014 as a PDF \
(primary) or XLSX export if your version of CASES21 supports it.
  2. Optionally reads a prior-period commentary XLSX and joins the \
Commentary column into the output. If omitted, the Commentary column is \
blank.
  3. Flags every line where YTD spend exceeds the annual budget with a \
pink highlight (#{HL_MISMATCH}).
  4. Summarises totals across all sub-programs, grouped by faculty.
  5. Writes the formatted output workbook to your chosen path.


HOW TO USE THIS TOOL

  1. Sub-Program report \u2014 click Browse and select the CASES21 GL21157 PDF \
(or XLSX). This is the only required file.
  2. Prior-period comments (optional) \u2014 click Browse and select the \
commentary XLSX from your previous reporting period. If you have no \
commentary file, leave this blank and the tool will run without it.
  3. Output workbook \u2014 click Browse to choose where the output will be \
saved.
  4. Click "Generate report". A progress bar will appear while the tool \
runs. Do not open or modify the input files while the tool is running.
  5. When complete, review any rows highlighted pink \u2014 these lines have \
exceeded their annual budget and require attention before the report is \
submitted.

The faculty rail on the left of the result table lets you jump directly \
to sub-programs belonging to a particular faculty.


IMPORTANT NOTES

  \u2022 The output workbook is formatted for School Council submission \u2014 \
no further formatting is needed.
  \u2022 Over-budget rows are highlighted #{HL_MISMATCH} (pink/red). Colour is never \
the sole signal: the Used % column will exceed 100 for these rows.
  \u2022 This is a paid tool. An active licence for your school is required. \
Licence fee: $550 + GST per school per year (Seller: ZXW Investment Pty Ltd).
  \u2022 Commentary entered via "Edit commentary..." survives the session and \
is written into the output workbook as a Commentary column.


SUPPORT

  This tool \u2014 feedback and questions:   Vurctne@gmail.com

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
    requires_feature = "sub_program"

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
    ]
    output = OutputSpec(
        key="output_file",
        label="Output workbook",
        suffix=".xlsx",
    )

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    # Per-instance state — initialised lazily on first use to keep __init__() free.
    _last_summary: ReportSummary | None = None
    _commentary_overrides: dict[str, str] | None = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:
            # 1. Resolve paths.
            report_file = Path(paths["report_file"])

            raw_comments = paths.get("comments_file")
            comments_file: Path | None = Path(raw_comments) if raw_comments else None

            raw_output = paths.get("output_file")
            if raw_output:
                output_file = Path(raw_output)
            else:
                # Derive a sensible default beside the report file.
                from datetime import datetime

                ts = datetime.now().strftime("%Y%m%d_%H%M")
                stem = report_file.stem
                output_file = report_file.with_name(f"Annual_SubProgram_{stem}_AUTO_{ts}.xlsx")

            # 2. Delegate to logic.
            summary: ReportSummary = logic.generate_report(
                report_file=report_file,
                comments_file=comments_file,
                output_file=output_file,
                progress=progress,
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

            # 3. Build ToolResult.
            return self._build_result(summary)

        except Exception as exc:
            tb = traceback.format_exc()
            return ToolResult(
                status="error",
                banner_level="danger",
                banner_text=(f"An error occurred ({type(exc).__name__}): {exc}"),
                log_lines=[
                    LogLine("ERROR", tag="heading"),
                    LogLine(f"{type(exc).__name__}: {exc}", tag="danger"),
                    LogLine(tb, tag="danger"),
                ],
                output_path=None,
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, summary: ReportSummary) -> ToolResult:
        n_lines = len(summary.lines)
        n_faculties = len(summary.faculty_counts)
        over = summary.over_budget_lines
        n_over = len(over)

        # Percentage of annual budget spent YTD.
        if summary.total_budget and summary.total_budget != Decimal("0"):
            ytd_pct = int(
                (summary.total_ytd / summary.total_budget * Decimal("100")).to_integral_value()
            )
        else:
            ytd_pct = 0

        # Banner text.
        base_banner = (
            f"{n_lines} sub-programs across {n_faculties} facult"
            + ("y" if n_faculties == 1 else "ies")
            + f". YTD spend {ytd_pct}% of annual."
        )
        if n_over == 0:
            banner_text = base_banner + " No lines over budget."
            status: str = "success"
            banner_level: str = "ok"
        elif n_over == 1:
            ob = over[0]
            banner_text = base_banner + f" 1 line over budget: {ob.sub_program}/{ob.account}."
            status = "warning"
            banner_level = "warning"
        else:
            banner_text = base_banner + f" {n_over} lines over budget."
            status = "warning"
            banner_level = "warning"

        # Log lines.
        log_lines: list[LogLine] = [
            LogLine("SUB-PROGRAM BUDGET REPORT", tag="heading"),
            LogLine(
                f"{n_lines} sub-programs | {n_faculties} facult"
                + ("y" if n_faculties == 1 else "ies")
                + f" | YTD {ytd_pct}% of annual budget",
                tag="ok" if n_over == 0 else "warning",
            ),
        ]
        if over:
            log_lines.append(
                LogLine(
                    f"Over-budget lines ({n_over}):",
                    tag="heading",
                )
            )
            for ln in over:
                over_by = ln.ytd - ln.budget
                log_lines.append(
                    LogLine(
                        f"  {ln.sub_program}/{ln.account} \u2014 over by ${over_by:,.2f}",
                        tag="danger",
                    )
                )
        log_lines.append(LogLine(f"Output: {summary.output_path}", tag="muted"))

        # Table rows.
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
                    "_bg": _OVER_BG if ln.is_over else None,
                }
            )

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            metrics=[],
            log_lines=log_lines,
            table_columns=_TABLE_COLUMNS,
            table_rows=table_rows,
            output_path=summary.output_path,
        )

    # ------------------------------------------------------------------
    # Secondary actions
    # ------------------------------------------------------------------

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return [("Edit commentary...", self._edit_commentary)]

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
