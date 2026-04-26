from __future__ import annotations

import traceback
from datetime import datetime
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    FileInput,
    LogLine,
    OutputSpec,
    ProgressFn,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from tools.srp import logic
from tools.srp.logic import SrpSummary

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP_TEXT = f"""SRP Comparison

This tool compares a school's Indicative SRP (Student Resource Package) \
budget with the Confirmed SRP and produces an XLSX workbook that highlights \
every line that has changed — new allocations, removed allocations, \
increases, and decreases.

The output workbook is ready for review by your principal or school \
business manager without any manual formatting.


WHAT THIS TOOL DOES

  1. Reads the Indicative SRP Budget Details PDF (exported from the DoE \
portal before confirmed enrolment data is available).
  2. Reads the Confirmed SRP Budget Details PDF (exported after confirmed \
enrolment data is locked in).
  3. Joins the two reports line-by-line on (Ref, Description) so that \
items sharing a Ref number but different descriptions are compared \
independently.
  4. Classifies each line as:
       unchanged        — amount did not change
       increased        — Confirmed amount is higher  (green #{HL_SOURCE_ONLY})
       decreased        — Confirmed amount is lower   (pink #{HL_MISMATCH})
       new in Confirmed — line exists only in Confirmed (green #{HL_SOURCE_ONLY})
       removed          — line exists only in Indicative (pink #{HL_MISMATCH})
  5. Writes the formatted comparison workbook to your chosen path.


HOW TO USE THIS TOOL

  1. Indicative SRP — click Browse and select the Indicative SRP Budget \
Details PDF downloaded from the DoE portal.
  2. Confirmed SRP — click Browse and select the Confirmed SRP Budget \
Details PDF.
  3. Output workbook — click Browse to choose where the comparison \
workbook will be saved.
  4. Click "Generate comparison". A progress bar will appear while the \
tool runs. Do not open or modify the input files while the tool is running.
  5. When complete, review rows highlighted pink (#{HL_MISMATCH}) — these \
lines have decreased or been removed from the Confirmed budget. Green rows \
(#{HL_SOURCE_ONLY}) indicate increases or new allocations.


IMPORTANT NOTES

  • The join key is (Ref, Description) — not Ref alone. Some Ref numbers \
(e.g. Ref 15 for Integration Students) appear more than once with \
different descriptions; these are compared independently.
  • The "Equity Reform Implementation Statement" line has no discrete Ref \
number in the PDF and is excluded from the comparison.
  • This is a free tool — no licence is required.


SUPPORT

  This tool — feedback and questions:   Vurctne@gmail.com

Please send feedback to Vurctne@gmail.com
"""

# ---------------------------------------------------------------------------
# Row highlight colours (without leading #, as required by openpyxl fills)
# ---------------------------------------------------------------------------

_DECREASED_BG = "#" + HL_MISMATCH  # pink — decreased / removed
_INCREASED_BG = "#" + HL_SOURCE_ONLY  # green — increased / new_in_confirmed

# ---------------------------------------------------------------------------
# Table column schema
# ---------------------------------------------------------------------------

_TABLE_COLUMNS: list[dict[str, Any]] = [
    {"key": "ref", "label": "Ref", "width": 50, "mono": True},
    {"key": "section", "label": "Section", "width": 180},
    {"key": "description", "label": "Description"},
    {"key": "indicative", "label": "Indicative", "width": 110, "align": "right", "mono": True},
    {"key": "confirmed", "label": "Confirmed", "width": 110, "align": "right", "mono": True},
    {"key": "variance", "label": "Variance", "width": 110, "align": "right", "mono": True},
    {"key": "pct", "label": "%", "width": 70, "align": "right", "mono": True},
    {"key": "category", "label": "Category", "width": 120},
]


def _fmt_dollar(value: object) -> str:
    from decimal import Decimal

    if value is None:
        return ""
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return f"${d:,.2f}"


def _fmt_pct(value: object) -> str:
    from decimal import Decimal

    if value is None:
        return ""
    d = value if isinstance(value, Decimal) else Decimal(str(value))
    return f"{d:,.2f}%"


class SrpComparisonTool:
    id = "srp"
    group = "Budget"
    label = "SRP Comparison"
    short = "SR"
    order = 20
    primary_button = "Generate comparison"
    pdf_template = None
    pdf_body = None
    help_text = _HELP_TEXT
    # No requires_feature — this is a free tool

    inputs: list[Any] = [
        FileInput(
            key="indicative_pdf",
            label="Indicative SRP",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        FileInput(
            key="confirmed_pdf",
            label="Confirmed SRP",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
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
            indicative_pdf = Path(paths["indicative_pdf"])
            confirmed_pdf = Path(paths["confirmed_pdf"])

            raw_output = paths.get("output_file")
            if raw_output:
                output_file = Path(raw_output)
            else:
                ts = datetime.now().strftime("%Y%m%d_%H%M")
                # Derive year from the indicative filename if parseable
                year = _guess_year(indicative_pdf.stem)
                output_file = indicative_pdf.with_name(f"SRP_Compare_{year}_{ts}.xlsx")

            summary: SrpSummary = logic.generate_srp_comparison(
                indicative_pdf=indicative_pdf,
                confirmed_pdf=confirmed_pdf,
                output_file=output_file,
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

    def _build_result(self, summary: SrpSummary) -> ToolResult:
        from decimal import Decimal

        counts = summary.counts
        n_total = len(summary.lines)
        n_increased = counts.get("increased", 0)
        n_decreased = counts.get("decreased", 0)
        n_new = counts.get("new_in_confirmed", 0)
        n_removed = counts.get("removed", 0)
        n_unchanged = counts.get("unchanged", 0)

        net_variance = summary.total_confirmed - summary.total_indicative

        # Banner text
        banner_text = (
            f"{n_total} lines compared. "
            f"{n_increased} increased / {n_decreased} decreased / "
            f"{n_new} new in Confirmed / {n_removed} removed. "
            f"Net variance: {_fmt_dollar(net_variance)}"
        )

        if n_decreased + n_removed > 0:
            status: str = "warning"
            banner_level: str = "warning"
        elif n_increased + n_new > 0:
            status = "success"
            banner_level = "ok"
        else:
            status = "success"
            banner_level = "ok"

        # Log lines
        log_lines: list[LogLine] = [
            LogLine("SRP COMPARISON", tag="heading"),
            LogLine(
                f"{n_total} lines | {n_unchanged} unchanged | "
                f"{n_increased} increased | {n_decreased} decreased | "
                f"{n_new} new in Confirmed | {n_removed} removed",
                tag="ok" if (n_decreased + n_removed == 0) else "warning",
            ),
            LogLine(
                f"Indicative total: {_fmt_dollar(summary.total_indicative)} | "
                f"Confirmed total: {_fmt_dollar(summary.total_confirmed)} | "
                f"Net variance: {_fmt_dollar(net_variance)}",
                tag="ok" if net_variance >= Decimal("0") else "warning",
            ),
            LogLine(f"Output: {summary.output_path}", tag="muted"),
        ]

        # Metrics: (label, value, tone)
        metrics: list[tuple[str, str, str | None]] = [
            ("Indicative total", _fmt_dollar(summary.total_indicative), None),
            ("Confirmed total", _fmt_dollar(summary.total_confirmed), None),
            (
                "Net variance",
                _fmt_dollar(net_variance),
                "ok" if net_variance >= Decimal("0") else "warning",
            ),
            ("Lines changed", str(n_increased + n_decreased + n_new + n_removed), None),
        ]

        # Table rows
        table_rows: list[dict[str, Any]] = []
        for ln in summary.lines:
            if ln.category in {"decreased", "removed"}:
                bg: str | None = _DECREASED_BG
            elif ln.category in {"increased", "new_in_confirmed"}:
                bg = _INCREASED_BG
            else:
                bg = None

            table_rows.append(
                {
                    "ref": str(ln.ref),
                    "section": ln.section,
                    "description": ln.description,
                    "indicative": _fmt_dollar(ln.indicative),
                    "confirmed": _fmt_dollar(ln.confirmed),
                    "variance": _fmt_dollar(ln.variance),
                    "pct": _fmt_pct(ln.pct),
                    "category": ln.category,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guess_year(stem: str) -> str:
    """Try to extract a 4-digit year from a filename stem; fall back to 'Unknown'."""
    import re

    m = re.search(r"\b(20\d{2})\b", stem)
    return m.group(1) if m else "Unknown"
