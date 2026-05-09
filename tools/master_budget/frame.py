from __future__ import annotations

import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    FileInput,
    LogLine,
    ProgressFn,
    TableSpec,
    ToolResult,
)
from toolkit.tokens import HL_EDITED, HL_MISMATCH, HL_SOURCE_ONLY
from toolkit.user_errors import friendly_error
from tools.master_budget import logic
from tools.master_budget.logic import (
    CompareSummary,
    ImportSummary,
    suggest_compare_output_name,
    suggest_output_name,
)

_HELP_TEXT = f"""Master Budget Compass Autofill — two actions, two buttons

This tool exposes two independent actions:

  • GENERATE BUDGET WORKBOOK — Pick a Compass Expense Sub-Program export \
plus your Master Budget template (the second field). Click \
"Generate budget workbook". The tool matches account codes, writes \
imported figures into the correct cells, and saves an annotated output \
workbook next to the template.

  • COMPARE TWO BUDGETS — Pick two Master Budget XLSM files: one in the \
"Master Budget template" field (treated as Master Budget A) and one in \
the "Master Budget B" field. Click "Compare two budgets". The tool reads \
three target metrics per sub-program from each file and shows only the \
sub-programs whose values differ. Click "Export comparison Excel" \
afterwards to save the diff as an XLSX.

The compared metrics are read from rows labelled \
"Total Estimated Revenue", "Total Proposed Expenditure Current Year", and \
"Total Estimated Funds Held future years" in the Master sheet. The tool \
falls back to substring / fuzzy matching when those labels aren't a perfect \
case match, so minor template variations still work.

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

  This tool — feedback and questions:   feedback@schooltool.com.au

Please send feedback to feedback@schooltool.com.au
"""


def _fmt_money(value: float | None) -> str:
    """Format a dollar value with thousands separators and 2dp.

    ``None`` renders as em-dash. The minus sign uses U+2212 (per design
    handoff numerics contract: "negative is red AND has a minus").
    """
    if value is None:
        return "—"
    if value == 0:
        return "$0.00"
    if value < 0:
        return f"−${-value:,.2f}"
    return f"${value:,.2f}"


def _fmt_delta(a: float | None, b: float | None) -> str:
    """Format a signed delta (B − A) with ↑ / ↓ direction marker.

    ``None`` for either side or zero delta renders as em-dash.
    """
    if a is None or b is None:
        return "—"
    delta = b - a
    if delta == 0:
        return "—"
    if delta > 0:
        return f"${delta:,.2f} ↑"
    return f"${-delta:,.2f} ↓"


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
            label="Compass Expense file (used by Generate budget workbook)",
            filetypes=[
                # Default to CSV (what Compass currently ships). "All files" is
                # the escape hatch for anyone on an older XLSX export.
                ("CSV file", "*.csv"),
                ("All files", "*.*"),
            ],
        ),
        FileInput(
            key="master_file",
            label="Master Budget template (Generate) — or Master Budget A (Compare)",
            filetypes=[
                # Macro-enabled workbook is the only real target; macros matter
                # and are preserved on write. "All files" as fallback.
                ("Macro-enabled workbook", "*.xlsm"),
                ("All files", "*.*"),
            ],
        ),
        FileInput(
            key="master_file_b",
            label="Master Budget B (used by Compare two budgets)",
            filetypes=[
                ("Macro-enabled workbook", "*.xlsm"),
                ("Excel workbook", "*.xlsx"),
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
    # Last successful Compare run — populated by ``_run_compare`` and read
    # by the "Export comparison Excel" secondary action so the user can
    # save the diff XLSX after seeing the in-app table.
    _last_compare_summary: CompareSummary | None = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        """Primary action — Autofill mode only.

        Round 28 — Compare runs through ``alt_run_buttons`` instead of
        being dispatched from this method, so each mode has its own
        button: "Generate budget workbook" (this method) and "Compare
        two budgets" (``run_compare``).
        """
        master_a_raw = paths.get("master_file")
        expense_raw = paths.get("expense_file")

        if not expense_raw or not master_a_raw:
            return self._error_result(
                Exception(
                    "Generate budget workbook requires both the Compass "
                    "Expense file and the Master Budget template. Pick "
                    "both files and try again. (To compare two master "
                    "budgets instead, click 'Compare two budgets'.)"
                ),
            )
        return self._run_autofill(Path(expense_raw), Path(master_a_raw), progress)

    def run_compare(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        """Alt primary action — Compare two Master Budget files.

        Wired via ``alt_run_buttons``. Reads ``master_file`` (treated as
        Master Budget A) and ``master_file_b`` from the input cache;
        errors clearly if either is missing.
        """
        master_a_raw = paths.get("master_file")
        master_b_raw = paths.get("master_file_b")

        if not master_a_raw or not master_b_raw:
            return self._error_result(
                Exception(
                    "Compare two budgets needs both Master Budget files "
                    "filled in: pick Master Budget A (the 'Master Budget "
                    "template' field) and Master Budget B (the third "
                    "field), then click Compare again."
                ),
            )
        return self._run_compare(Path(master_a_raw), Path(master_b_raw), progress)

    def alt_run_buttons(
        self,
    ) -> list[tuple[str, Callable[[dict[str, Any], ProgressFn], ToolResult]]]:
        """Round 28 — expose ``Compare two budgets`` as a primary-style button
        next to ``Generate budget workbook``."""
        return [("Compare two budgets", self.run_compare)]

    def _run_autofill(
        self,
        expense_file: Path,
        master_file: Path,
        progress: ProgressFn,
    ) -> ToolResult:
        try:
            # Always write to a fresh copy alongside the Master Budget template.
            output_file = Path(suggest_output_name(master_file))

            summary: ImportSummary = logic.import_expense_sub_program(
                expense_file=expense_file,
                master_file=master_file,
                output_file=output_file,
                progress=progress,
            )

            self._last_output_path = summary.output_path
            self._last_compare_summary = None  # Autofill clears any prior compare.
            return self._build_result(summary)

        except Exception as exc:
            return self._error_result(exc)

    def _run_compare(
        self,
        file_a: Path,
        file_b: Path,
        progress: ProgressFn,
    ) -> ToolResult:
        try:
            summary = logic.compare_master_budgets(file_a, file_b, progress)
            self._last_compare_summary = summary
            self._last_output_path = None  # Compare doesn't auto-write a file.
            return self._build_compare_result(summary)
        except Exception as exc:
            return self._error_result(exc)

    def _error_result(self, exc: Exception) -> ToolResult:
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

    def _build_compare_result(self, summary: CompareSummary) -> ToolResult:
        """Build a ToolResult for Compare mode.

        Renders an in-app TableSpec with one row per differing sub-program.
        ``only_in_a`` / ``only_in_b`` rows get a pink HL_MISMATCH tint.
        Pure-diff rows have no tint; the Δ columns carry the signed delta
        with ↑ / ↓ direction markers, mirroring the Sub-Program Combined
        view styling.
        """
        n_diff = len(summary.rows)
        n_only_a = len(summary.only_in_a)
        n_only_b = len(summary.only_in_b)

        if n_diff == 0:
            status: str = "success"
            banner_level: str = "ok"
            banner_text = (
                f"No differences found across {summary.file_a_path.name} "
                f"and {summary.file_b_path.name} for the three target metrics."
            )
        else:
            status = "warning"
            banner_level = "warning"
            banner_text = (
                f"Found {n_diff} sub-program difference(s) between "
                f"{summary.file_a_path.name} and {summary.file_b_path.name}. "
                "Click 'Export comparison Excel' below to save as XLSX."
            )

        log_lines: list[LogLine] = [
            LogLine("COMPARE SUMMARY", tag="heading"),
            LogLine(
                f"Differences: {n_diff}  |  Only in A: {n_only_a}  |  Only in B: {n_only_b}",
                tag="ok" if n_diff == 0 else "warning",
            ),
        ]

        # Surface label-match outcomes — flag any "missing" or "fuzzy"
        # so the user knows which target values may have used a fallback.
        for label_key, target in (
            ("revenue", "Total Estimated Revenue"),
            ("expenditure", "Total Proposed Expenditure Current Year"),
            ("funds_held", "Total Estimated Funds Held future years"),
        ):
            for which, label_match in (("A", summary.label_match_a), ("B", summary.label_match_b)):
                matched_label, kind = label_match.get(label_key, ("", "missing"))
                if kind == "exact":
                    continue
                if kind == "missing":
                    log_lines.append(
                        LogLine(
                            f"File {which}: '{target}' not found — values treated as blank",
                            tag="warning",
                        )
                    )
                else:
                    log_lines.append(
                        LogLine(
                            f"File {which}: '{target}' matched via {kind} → '{matched_label}'",
                            tag="muted",
                        )
                    )

        if summary.only_in_a:
            log_lines.append(
                LogLine(
                    f"Sub-programs only in A ({n_only_a}):",
                    tag="heading",
                )
            )
            for code in summary.only_in_a:
                log_lines.append(LogLine(f"  {code}", tag="extra"))
        if summary.only_in_b:
            log_lines.append(
                LogLine(
                    f"Sub-programs only in B ({n_only_b}):",
                    tag="heading",
                )
            )
            for code in summary.only_in_b:
                log_lines.append(LogLine(f"  {code}", tag="extra"))

        columns: list[dict[str, Any]] = [
            {"key": "sub_program", "label": "Sub-program", "width": 95, "mono": True},
            {"key": "description", "label": "Description"},
            {
                "key": "a_revenue",
                "label": "Revenue A",
                "width": 105,
                "align": "right",
                "mono": True,
            },
            {
                "key": "b_revenue",
                "label": "Revenue B",
                "width": 105,
                "align": "right",
                "mono": True,
            },
            {
                "key": "delta_revenue",
                "label": "Δ Revenue",
                "width": 115,
                "align": "right",
                "mono": True,
            },
            {
                "key": "a_expense",
                "label": "Expense A",
                "width": 105,
                "align": "right",
                "mono": True,
            },
            {
                "key": "b_expense",
                "label": "Expense B",
                "width": 105,
                "align": "right",
                "mono": True,
            },
            {
                "key": "delta_expense",
                "label": "Δ Expense",
                "width": 115,
                "align": "right",
                "mono": True,
            },
            {"key": "a_funds", "label": "Funds A", "width": 105, "align": "right", "mono": True},
            {"key": "b_funds", "label": "Funds B", "width": 105, "align": "right", "mono": True},
            {
                "key": "delta_funds",
                "label": "Δ Funds",
                "width": 115,
                "align": "right",
                "mono": True,
            },
        ]

        rows: list[dict[str, Any]] = []
        for r in summary.rows:
            rows.append(
                {
                    "sub_program": r.sub_program,
                    "description": r.description,
                    "a_revenue": _fmt_money(r.a_revenue),
                    "b_revenue": _fmt_money(r.b_revenue),
                    "delta_revenue": _fmt_delta(r.a_revenue, r.b_revenue),
                    "a_expense": _fmt_money(r.a_expenditure),
                    "b_expense": _fmt_money(r.b_expenditure),
                    "delta_expense": _fmt_delta(r.a_expenditure, r.b_expenditure),
                    "a_funds": _fmt_money(r.a_funds_held),
                    "b_funds": _fmt_money(r.b_funds_held),
                    "delta_funds": _fmt_delta(r.a_funds_held, r.b_funds_held),
                    "_only_in": r.only_in,
                }
            )

        def _row_style(row: dict[str, Any]) -> dict[str, Any]:
            if row.get("_only_in") in {"A", "B"}:
                return {"background": "#" + HL_MISMATCH}
            return {}

        table = TableSpec(columns=columns, rows=rows, row_style=_row_style)

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            log_lines=log_lines,
            table=table,
            output_path=None,
        )

    def clear(self) -> None:
        """Reset Master Budget session state.

        The shell handles UI resets (file pickers, banner, log, table).
        We reset the per-instance cache so the next run starts fresh.
        """
        self._last_output_path = None
        self._last_compare_summary = None

    def preview_update(self, key: str, value: float | str) -> None:
        """No live-preview inputs on this tool; always returns None."""
        return None

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        # Output naming is automatic, so the old "Create suggested output name"
        # button is gone. "Open output folder" is the one useful action after
        # a successful run -- it opens Explorer (Windows) / Finder (macOS) /
        # xdg-open (Linux) at the folder, selecting the generated file.
        # "Export comparison Excel" appears alongside it; it is a no-op
        # until a successful Compare run has populated _last_compare_summary.
        return [
            ("Open output folder", self._open_output_folder),
            ("Export comparison Excel", self._export_compare_xlsx),
        ]

    def _export_compare_xlsx(self) -> None:
        """Save the last successful Compare run as an XLSX."""
        try:
            import tkinter.messagebox as mb
            from tkinter import filedialog
        except ImportError:  # pragma: no cover -- Tk absent (CI)
            return

        summary = self._last_compare_summary
        if summary is None:
            try:
                mb.showinfo(
                    "Export comparison Excel",
                    "No Compare run yet. Pick Master Budget A and B, "
                    "leave the Compass file blank, and click Generate first.",
                )
            except Exception:  # pragma: no cover
                pass
            return

        suggested = suggest_compare_output_name(summary.file_a_path)
        try:
            target = filedialog.asksaveasfilename(
                title="Save comparison Excel",
                initialfile=Path(suggested).name,
                initialdir=str(Path(suggested).parent),
                defaultextension=".xlsx",
                filetypes=[("Excel workbook", "*.xlsx"), ("All files", "*.*")],
            )
        except Exception:  # pragma: no cover -- Tk absent (CI)
            return

        if not target:
            return

        try:
            new_summary = logic.write_compare_xlsx(summary, Path(target))
        except Exception as exc:  # pragma: no cover -- guarded UX path
            try:
                mb.showerror("Export comparison Excel", str(exc))
            except Exception:
                pass
            return

        self._last_compare_summary = new_summary
        self._last_output_path = new_summary.output_path
        try:
            mb.showinfo(
                "Export comparison Excel",
                f"Saved as {Path(target).name} in the same folder as Master Budget A.",
            )
        except Exception:  # pragma: no cover
            pass

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
