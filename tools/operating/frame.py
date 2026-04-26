from __future__ import annotations

import traceback
from decimal import Decimal
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    CurrencyInput,
    FileInput,
    LogLine,
    NumberInput,
    OutputSpec,
    ProgressFn,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from tools.operating import logic
from tools.operating.logic import OpStatSummary

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP_TEXT = f"""Operating Statement

This tool compares two CASES21 GL21150 Operating Statement Detailed PDFs
(a prior period and a current period) and produces an XLSX workbook showing
the movement in YTD Actual values for every GL account.

Rows where the movement exceeds either your dollar threshold or your percentage
threshold are highlighted: green (#{HL_SOURCE_ONLY}) for favourable movements
and pink/red (#{HL_MISMATCH}) for adverse movements.


WHAT THIS TOOL DOES

  1. Reads both GL21150 PDFs and extracts the YTD Actual value for every
     GL account code found.
  2. Computes the Movement (current YTD - prior YTD) and the percentage
     change for each account.
  3. Flags rows where abs(Movement) >= $ threshold OR abs(%) >= % threshold.
  4. Highlights flagged rows green (#{HL_SOURCE_ONLY}) for favourable movement and
     pink/red (#{HL_MISMATCH}) for adverse movement. Colour is never the sole
     signal - the Movement and % columns carry the same information.
  5. Writes the formatted output workbook to your chosen path.


HIGHLIGHT SEMANTICS

  * Green (#{HL_SOURCE_ONLY}) - Favourable: revenue up or expenditure down.
  * Pink/red (#{HL_MISMATCH}) - Adverse: revenue down or expenditure up.
  * No fill - Movement is zero, or below both thresholds.


HOW TO USE THIS TOOL

  1. Current period (PDF) - click Browse and select the GL21150 PDF for the
     most recent period.
  2. Prior period (PDF) - click Browse and select the GL21150 PDF for the
     earlier period you want to compare against.
  3. $ threshold - enter the minimum dollar movement that warrants highlighting
     (default $5,000 if left blank).
  4. % threshold - enter the minimum percentage movement that warrants
     highlighting (default 10% if left blank). Either threshold exceeded
     triggers highlighting.
  5. Output workbook - click Browse to choose where the output will be saved.
  6. Click "Generate comparison". A progress bar will appear while the tool
     runs. Do not open or modify the input files while the tool is running.


IMPORTANT NOTES

  * Only YTD Actual values are compared. Month and budget columns are not
    included in the output.
  * Accounts present in only one period are included with the absent period
    shown as zero.
  * This is a paid tool. Activating this tool for your school requires a
    paid licence - see User -> Service in the app.


SUPPORT

  This tool - feedback and questions:   Vurctne@gmail.com
"""

# ---------------------------------------------------------------------------
# Table column schema
# ---------------------------------------------------------------------------

_TABLE_COLUMNS: list[dict[str, Any]] = [
    {"key": "gl_code", "label": "Account", "width": 80, "mono": True},
    {"key": "description", "label": "Description"},
    {"key": "section", "label": "Section", "width": 130},
    {"key": "subsection", "label": "Sub-section", "width": 130},
    {"key": "ytd_prior", "label": "YTD Prior", "width": 100, "align": "right", "mono": True},
    {"key": "ytd_current", "label": "YTD Current", "width": 100, "align": "right", "mono": True},
    {"key": "movement", "label": "Movement", "width": 100, "align": "right", "mono": True},
    {"key": "pct", "label": "%", "width": 70, "align": "right", "mono": True},
]

_FAVOURABLE_BG = "#" + HL_SOURCE_ONLY
_ADVERSE_BG = "#" + HL_MISMATCH


def _fmt_dollar(value: Decimal | None) -> str:
    if value is None:
        return "—"
    # U+2212 minus for negative values
    if value < Decimal("0"):
        return f"−${abs(value):,.2f}"
    return f"${value:,.2f}"


def _fmt_pct(value: Decimal | None) -> str:
    if value is None:
        return "—"
    if value < Decimal("0"):
        return f"−{abs(value):.1f}%"
    return f"{value:.1f}%"


class OperatingStatementTool:
    id = "operating"
    group = "Reconciliation"
    label = "Operating Statement"
    short = "OS"
    order = 20
    primary_button = "Generate comparison"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    requires_feature = "operating"

    inputs: list[Any] = [
        FileInput(
            key="current_file",
            label="Current period (PDF)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        FileInput(
            key="prior_file",
            label="Prior period (PDF)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        CurrencyInput(key="threshold_dollars", label="$ threshold"),
        NumberInput(
            key="threshold_pct",
            label="% threshold",
            min_value=0,
            max_value=1000,
            decimals=0,
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

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:
            current_file = Path(paths["current_file"])
            prior_file = Path(paths["prior_file"])

            raw_dollars = paths.get("threshold_dollars")
            threshold_dollars = Decimal(str(raw_dollars)) if raw_dollars else Decimal("5000")
            if threshold_dollars <= Decimal("0"):
                threshold_dollars = Decimal("5000")

            raw_pct = paths.get("threshold_pct")
            threshold_pct = int(raw_pct) if raw_pct else 10
            if threshold_pct <= 0:
                threshold_pct = 10

            raw_output = paths.get("output_file")
            if raw_output:
                output_file = Path(raw_output)
            else:
                from datetime import datetime

                ts = datetime.now().strftime("%Y%m%d_%H%M")
                output_file = current_file.with_name(f"OpStat_Compare_{ts}.xlsx")

            summary: OpStatSummary = logic.generate_opstat_comparison(
                current_file=current_file,
                prior_file=prior_file,
                output_file=output_file,
                threshold_dollars=threshold_dollars,
                threshold_pct=threshold_pct,
                progress=progress,
            )

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

    def _build_result(self, summary: OpStatSummary) -> ToolResult:
        lines = summary.lines
        n_lines = len(lines)
        n_flagged = sum(1 for ln in lines if ln.exceeds_threshold)
        n_favourable = sum(1 for ln in lines if ln.exceeds_threshold and ln.is_favourable is True)
        n_adverse = sum(1 for ln in lines if ln.exceeds_threshold and ln.is_favourable is False)

        # Format summary deltas for banner
        rev_mov = summary.revenue_movement
        exp_mov = summary.expenditure_movement
        op_mov = summary.operating_result_movement

        def _signed_dollar(v: Decimal) -> str:
            if v >= Decimal("0"):
                return f"+${v:,.0f}"
            return f"−${abs(v):,.0f}"

        def _signed_pct(num: Decimal, denom: Decimal) -> str:
            if denom == Decimal("0"):
                return ""
            pct = num / denom * Decimal("100")
            if pct >= Decimal("0"):
                return f" (+{pct:.1f}%)"
            return f" (−{abs(pct):.1f}%)"

        # We don't have totals by section in the summary but we have the lines
        _zero = Decimal("0")
        rev_prior: Decimal = sum(
            ((ln.ytd_prior or _zero) for ln in lines if ln.section == "REVENUE"), _zero
        )
        exp_prior: Decimal = sum(
            ((ln.ytd_prior or _zero) for ln in lines if ln.section == "EXPENDITURE"), _zero
        )

        rev_pct_str = _signed_pct(rev_mov, rev_prior)
        exp_pct_str = _signed_pct(exp_mov, exp_prior)

        banner_text = (
            f"Completed. Revenue {_signed_dollar(rev_mov)}{rev_pct_str}. "
            f"Expenditure {_signed_dollar(exp_mov)}{exp_pct_str}. "
            f"Operating result {_signed_dollar(op_mov)}."
        )

        if n_adverse == 0:
            status: str = "success"
            banner_level: str = "ok"
        else:
            status = "warning"
            banner_level = "warning"

        # Metrics row
        op_tone: str | None = "ok" if op_mov >= Decimal("0") else "danger"
        metrics: list[tuple[str, str, str | None]] = [
            ("Revenue movement", _signed_dollar(rev_mov), None),
            ("Expenditure movement", _signed_dollar(exp_mov), None),
            ("Operating result movement", _signed_dollar(op_mov), op_tone),
        ]

        # Log lines
        log_lines: list[LogLine] = [
            LogLine("OPERATING STATEMENT COMPARISON", tag="heading"),
            LogLine(
                f"Period: {summary.period_prior} — {summary.period_current}",
                tag="muted",
            ),
            LogLine(
                f"{n_lines} accounts | {n_flagged} flagged "
                f"({n_favourable} favourable, {n_adverse} adverse)",
                tag="ok" if n_adverse == 0 else "warning",
            ),
            LogLine(f"Output: {summary.output_path}", tag="muted"),
        ]

        # Table rows
        table_rows: list[dict[str, Any]] = []
        for ln in lines:
            if ln.exceeds_threshold and ln.is_favourable is True:
                bg: str | None = _FAVOURABLE_BG
            elif ln.exceeds_threshold and ln.is_favourable is False:
                bg = _ADVERSE_BG
            else:
                bg = None

            table_rows.append(
                {
                    "gl_code": str(ln.gl_code).zfill(5),
                    "description": ln.description,
                    "section": ln.section,
                    "subsection": ln.subsection,
                    "ytd_prior": _fmt_dollar(ln.ytd_prior),
                    "ytd_current": _fmt_dollar(ln.ytd_current),
                    "movement": _fmt_dollar(ln.movement),
                    "pct": _fmt_pct(ln.pct),
                    "_bg": bg,
                }
            )

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            metrics=metrics,
            log_lines=log_lines,
            table_columns=_TABLE_COLUMNS,
            table_rows=table_rows,
            output_path=summary.output_path,
        )

    def secondary_actions(self) -> list[tuple[str, object]]:
        return []
