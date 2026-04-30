from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    FileInput,
    LogLine,
    ProgressFn,
    ToolResult,
)
from toolkit.tokens import HL_EDITED, HL_MISMATCH, HL_SOURCE_ONLY
from toolkit.user_errors import friendly_error
from tools.master_budget import logic
from tools.master_budget.logic import ImportSummary, suggest_output_name

_HELP_TEXT = f"""Master Budget Compass Autofill

This tool imports a Compass Expense Sub-Program export into your school's \
Master Budget macro-enabled workbook. It matches account codes between the \
two files, writes the imported figures into the correct cells, and saves an \
annotated output workbook—all without opening Excel manually. The name \
"Compass Autofill" reflects exactly what it does: it autofills the Master \
Budget template from the Compass export.

The output workbook is byte-equivalent to the one produced by the original \
Master Budget Automation Tool v1.0.2. Macro bindings and button assignments \
are preserved.


HOW IT WORKS

  1. The tool reads the Compass Expense Sub-Program XLSX export, extracting \
sub-program codes (columns) and account codes (rows).
  2. It reads the Master Budget XLSM template to learn which account codes and \
sub-program codes it contains.
  3. Matched rows and columns receive the imported dollar figures from the \
Compass file.
  4. Unmatched items are flagged with highlight colours so you can review them \
before submitting to your principal or school council.
  5. The annotated workbook is saved to your chosen output path with macros \
and button bindings intact.


HIGHLIGHT COLOURS IN THE OUTPUT WORKBOOK

  Pink / red  (#{HL_MISMATCH}) — Mismatch row or column. An account code or \
sub-program code is present in the Master Budget template but was not found \
in the Compass export. The imported value for that cell is blank. Review \
whether the code has been removed or renamed in Compass.

  Green  (#{HL_SOURCE_ONLY}) — Source-only row or column. An account code or \
sub-program code appears in the Compass export but has no matching row or \
column in the Master Budget template. The tool has inserted a new row or \
column into the output workbook for this code. Review whether it should be \
added to your Master Budget permanently.

  Yellow  (#{HL_EDITED}) — Edited cell (user convention). Cells you have \
manually adjusted in a previous version of the workbook may carry this \
colour. The tool does not apply or remove this highlight; it is preserved \
from the template as-is.

If the output opens with no highlighted cells, all account codes and \
sub-program codes matched perfectly between the two files.


WORKED EXAMPLE

Suppose your Compass export contains sub-program 1234 but your Master Budget \
template does not. The tool inserts a new column for 1234, populates it with \
figures from the export, and highlights that column green so you know to \
review it. Conversely, if your template has account code 71000 but the \
Compass export does not, the tool leaves that row blank and highlights it \
pink.


USING THIS TOOL

  1. Expense Sub-Program file — click Browse and select the Compass Expense \
Sub-Program XLSX export for the period you are loading.
  2. Master Budget template — click Browse and select your school's Master \
Budget XLSM workbook (the macro-enabled template, not a previous output).
  3. Output workbook — click Browse to choose where the annotated output \
will be saved, or click "Create suggested output name" to have the tool \
generate a timestamped file name in the same folder as the template.
  4. Click "Generate budget workbook". A progress bar will appear while the \
tool runs. Do not open or modify either input file while the tool is running.
  5. When complete, a banner will show either a success message or a warning \
listing the number of mismatch items. Open the output workbook and review \
any highlighted rows or columns before distributing.

The tool runs on a background thread—the window remains responsive \
throughout.


SUPPORT

  This tool — feedback and questions:   Vurctne@gmail.com

Please send feedback to Vurctne@gmail.com
"""


class MasterBudgetTool:
    id = "master-budget"
    group = "Budget"
    label = "Master Budget Compass Autofill"
    short = "MB"
    order = 10
    primary_button = "Generate budget workbook"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    requires_feature = None

    inputs: list[Any] = [
        FileInput(
            key="expense_file",
            label="Expense Sub-Program file",
            filetypes=[
                # Default to CSV (what Compass currently ships). "All files" is
                # the escape hatch for anyone on an older XLSX export.
                ("CSV file", "*.csv"),
                ("All files", "*.*"),
            ],
        ),
        FileInput(
            key="master_file",
            label="Master Budget template",
            filetypes=[
                # Macro-enabled workbook is the only real target; macros matter
                # and are preserved on write. "All files" as fallback.
                ("Macro-enabled workbook", "*.xlsm"),
                ("All files", "*.*"),
            ],
        ),
    ]
    # Output workbook is always auto-computed from the Master Budget template
    # path (same folder, ``<stem>_AUTO_<timestamp>.xlsm`` filename). The user
    # never picks it -- keeps the workflow to two clicks: pick Compass export,
    # pick Master Budget, press Generate.
    output = None

    # Per-instance state -- the "Open output folder" secondary action reads
    # this to know where the last successful run wrote its file.
    _last_output_path: Path | None = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:
            expense_file = Path(paths["expense_file"])
            master_file = Path(paths["master_file"])

            # Always write to a fresh copy alongside the Master Budget template.
            output_file = Path(suggest_output_name(master_file))

            summary: ImportSummary = logic.import_expense_sub_program(
                expense_file=expense_file,
                master_file=master_file,
                output_file=output_file,
                progress=progress,
            )

            self._last_output_path = summary.output_path
            return self._build_result(summary)

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

    def _build_result(self, summary: ImportSummary) -> ToolResult:
        has_issues = bool(
            summary.mismatch_account_codes
            or summary.mismatch_subprogram_codes
            or summary.source_only_account_codes
            or summary.source_only_subprogram_codes
        )
        mismatch_count = (
            len(summary.mismatch_account_codes)
            + len(summary.mismatch_subprogram_codes)
            + len(summary.source_only_account_codes)
            + len(summary.source_only_subprogram_codes)
        )

        # Output filename (not the full path) goes in the banner so the user
        # can see at a glance what was written.
        out_name = summary.output_path.name

        if has_issues:
            status: str = "warning"
            banner_level: str = "warning"
            banner_text = (
                f"Completed with {mismatch_count} mismatch item(s). "
                f"Output saved as {out_name} (same folder as the template). "
                "Highlighted rows and columns need review."
            )
        else:
            status = "success"
            banner_level = "ok"
            banner_text = (
                f"Import complete. {summary.matched_rows} rows matched, "
                f"{summary.matched_cells} cells updated. "
                f"Output saved as {out_name} (same folder as the template)."
            )

        log_lines: list[LogLine] = [
            LogLine("IMPORT SUMMARY", tag="heading"),
            LogLine(
                f"Matched rows: {summary.matched_rows}  |  Matched cells: {summary.matched_cells}",
                tag="ok" if not has_issues else "warning",
            ),
        ]

        if summary.mismatch_account_codes:
            log_lines.append(
                LogLine(
                    f"Mismatch rows ({len(summary.mismatch_account_codes)}) — "
                    "account codes in Master Budget but not in Compass export:",
                    tag="heading",
                )
            )
            for code in summary.mismatch_account_codes:
                log_lines.append(LogLine(f"  {code}", tag="danger"))

        if summary.mismatch_subprogram_codes:
            log_lines.append(
                LogLine(
                    f"Mismatch columns ({len(summary.mismatch_subprogram_codes)}) — "
                    "sub-program codes in Master Budget but not in Compass export:",
                    tag="heading",
                )
            )
            for code in summary.mismatch_subprogram_codes:
                log_lines.append(LogLine(f"  {code}", tag="danger"))

        if summary.source_only_account_codes:
            log_lines.append(
                LogLine(
                    f"Source-only rows ({len(summary.source_only_account_codes)}) — "
                    "account codes in Compass export but not in Master Budget:",
                    tag="heading",
                )
            )
            for code in summary.source_only_account_codes:
                log_lines.append(LogLine(f"  {code}", tag="extra"))

        if summary.source_only_subprogram_codes:
            log_lines.append(
                LogLine(
                    f"Source-only columns ({len(summary.source_only_subprogram_codes)}) — "
                    "sub-program codes in Compass export but not in Master Budget:",
                    tag="heading",
                )
            )
            for code in summary.source_only_subprogram_codes:
                log_lines.append(LogLine(f"  {code}", tag="extra"))

        log_lines.append(LogLine(f"Output: {summary.output_path}", tag="muted"))

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            log_lines=log_lines,
            output_path=summary.output_path,
        )

    def clear(self) -> None:
        """Reset Master Budget session state.

        The shell handles UI resets (file pickers, banner, log, table).
        We reset the per-instance cache so the next run starts fresh.
        """
        self._last_output_path = None

    def preview_update(self, key: str, value: float | str) -> None:
        """No live-preview inputs on this tool; always returns None."""
        return None

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        # Output naming is automatic, so the old "Create suggested output name"
        # button is gone. "Open output folder" is the one useful action after
        # a successful run -- it opens Explorer (Windows) / Finder (macOS) /
        # xdg-open (Linux) at the folder, selecting the generated file.
        return [("Open output folder", self._open_output_folder)]

    def _open_output_folder(self) -> None:
        """Open the output folder with the generated workbook highlighted."""
        from toolkit.files import open_output_folder

        # Tk may be absent in CI -- guard the messagebox import so this method
        # stays callable (headless unit tests exercise it too).
        try:
            import tkinter.messagebox as mb
        except ImportError:  # pragma: no cover -- Tk absent (CI)
            mb = None  # type: ignore[assignment]

        path = self._last_output_path
        if path is None:
            if mb is not None:
                try:
                    mb.showinfo(
                        "Open output folder",
                        "No output file yet. Click Generate budget workbook first.",
                    )
                except Exception:  # pragma: no cover -- Tk absent (CI)
                    pass
            return

        open_output_folder(path)
