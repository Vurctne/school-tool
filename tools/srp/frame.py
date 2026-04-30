from __future__ import annotations

import traceback
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from toolkit.base_tool import (
    FileInput,
    LogLine,
    ProgressFn,
    ToolResult,
)
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY
from toolkit.user_errors import friendly_error
from tools.srp import logic
from tools.srp.logic import SrpSummary

# ---------------------------------------------------------------------------
# Help text
# ---------------------------------------------------------------------------

_HELP_TEXT = f"""SRP Comparison

This tool compares a school's SRP (Student Resource Package) budget across \
any two to four versions -- Indicative, Confirmed, 1st Revised, and \
2nd Revised -- and produces an XLSX workbook that highlights every line \
that has changed.

Provide any 2 (or more, up to 4) SRP versions for comparison. The tool \
joins them line-by-line on (Ref, Description) and shows what changed between \
each adjacent pair of provided versions.

The output workbook is ready for review by your principal or school \
business manager without any manual formatting.


WHAT THIS TOOL DOES

  1. Reads whichever SRP Budget Details PDFs you supply (at least two). \
You do not need all four versions -- any combination works: \
Indicative + 1st Revised, Confirmed + 2nd Revised, or any other pairing.
  2. Joins the reports line-by-line on (Ref, Description) and preserves \
the first-provided version's source order so the output matches your \
original SRP layout.
  3. Classifies each line as:
       unchanged  -- amount did not change across all provided versions
       changed    -- value differs between at least one adjacent pair \
(green if net increase, pink if net decrease)
       new        -- line is absent from the first version but appears later
       removed    -- line is present in the first version only
  4. Writes the formatted comparison workbook next to the first provided \
SRP file.


HOW TO USE THIS TOOL

  1. Fill in any two (or more) of the four input slots below.
  2. Indicative SRP (optional) -- the Indicative SRP Budget Details PDF \
from the DoE portal.
  3. Confirmed SRP (optional) -- the Confirmed SRP Budget Details PDF.
  4. 1st Revised SRP (optional) -- if a revised budget has been issued.
  5. 2nd Revised SRP (optional) -- a second revision for four-way comparison.
  6. Click "Generate comparison". A progress bar will appear while the \
tool runs. Do not open or modify the input files while the tool is running.
  7. When complete, click "Open output folder" to view the workbook.

Note: if fewer than two files are provided the tool will show an error \
asking you to add more.


IMPORTANT NOTES

  * The join key is (Ref, Description) -- not Ref alone. Some Ref numbers \
(e.g. Ref 15 for Integration Students) appear more than once with \
different descriptions; these are compared independently.
  * Row order in the output matches the first provided SRP PDF order. Lines \
that appear only in later versions are appended at the end.
  * The "Equity Reform Implementation Statement" line has no discrete Ref \
number in the PDF and is excluded from the comparison.
  * This is a free tool -- no licence is required.
  * Pink rows (#{HL_MISMATCH}): decreased or removed allocations.
  * Green rows (#{HL_SOURCE_ONLY}): increased or new allocations.


SUPPORT

  This tool -- feedback and questions:   Vurctne@gmail.com

Please send feedback to Vurctne@gmail.com
"""

# ---------------------------------------------------------------------------
# Row highlight colours (without leading #, as required by openpyxl fills)
# ---------------------------------------------------------------------------

_DECREASED_BG = "#" + HL_MISMATCH  # pink -- decreased / removed
_INCREASED_BG = "#" + HL_SOURCE_ONLY  # green -- increased / new

# ---------------------------------------------------------------------------
# Category sets used to map SrpLine.category -> background colour
# ---------------------------------------------------------------------------

_DECREASED_CATS: frozenset[str] = frozenset({"removed"})
_INCREASED_CATS: frozenset[str] = frozenset({"new"})


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
    # No requires_feature -- this is a free tool

    inputs: list[Any] = [
        FileInput(
            key="indicative_pdf",
            label="Indicative SRP (optional)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        FileInput(
            key="confirmed_pdf",
            label="Confirmed SRP (optional)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        FileInput(
            key="revised1_pdf",
            label="1st Revised SRP (optional)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
        FileInput(
            key="revised2_pdf",
            label="2nd Revised SRP (optional)",
            filetypes=[("PDF", "*.pdf"), ("All files", "*.*")],
        ),
    ]
    # output picker removed -- path is auto-derived next to the first provided file.
    output = None

    # instance state for "Open output folder"
    _last_output_path: Path | None = None

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        try:

            def _opt(key: str) -> Path | None:
                raw = paths.get(key) or ""
                return Path(raw) if str(raw).strip() else None

            ind = _opt("indicative_pdf")
            conf = _opt("confirmed_pdf")
            rev1 = _opt("revised1_pdf")
            rev2 = _opt("revised2_pdf")

            # Build the ordered list of provided versions (canonical order)
            provided: list[tuple[str, Path]] = [
                (label, p)
                for label, p in [
                    ("Indicative", ind),
                    ("Confirmed", conf),
                    ("1st Revised", rev1),
                    ("2nd Revised", rev2),
                ]
                if p is not None
            ]

            if len(provided) < 2:
                n = len(provided)
                noun = "s" if n != 1 else ""
                return ToolResult(
                    status="error",
                    banner_level="danger",
                    banner_text=("Please pick at least 2 SRP PDFs before comparing."),
                    log_lines=[
                        LogLine("WHAT WENT WRONG", tag="heading"),
                        LogLine(
                            f"You picked {n} file{noun}, but the comparison needs at least 2.",
                            tag="danger",
                        ),
                        LogLine("HOW TO FIX IT", tag="heading"),
                        LogLine(
                            "Click any two of the four file pickers above "
                            "(Indicative, Confirmed, 1st Revised, 2nd Revised) "
                            "and select the corresponding PDFs, then run again.",
                            tag="muted",
                        ),
                    ],
                    output_path=None,
                )

            # Auto-derive output path next to the FIRST provided file
            first_path = provided[0][1]
            ts = datetime.now().strftime("%Y%m%d_%H%M")
            year = _guess_year(first_path.stem)
            output_file = first_path.with_name(f"SRP_Compare_{year}_{ts}.xlsx")

            summary: SrpSummary = logic.generate_srp_comparison(
                output_file=output_file,
                progress=progress,
                indicative_pdf=ind,
                confirmed_pdf=conf,
                revised1_pdf=rev1,
                revised2_pdf=rev2,
            )

            # Record output path for "Open output folder"
            self._last_output_path = output_file

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result(self, summary: SrpSummary) -> ToolResult:
        from decimal import Decimal

        counts = summary.counts
        n_total = len(summary.lines)
        n_versions = len(summary.version_labels)

        n_unchanged = counts.get("unchanged", 0)
        n_changed = counts.get("changed", 0)
        n_new = counts.get("new", 0)
        n_removed = counts.get("removed", 0)

        net_variance = summary.total_last - summary.total_first

        if n_versions == 1:
            version_range = summary.version_labels[0]
        else:
            version_range = f"{summary.version_labels[0]}" + "→" + f"{summary.version_labels[-1]}"

        v_noun = "versions" if n_versions != 1 else "version"
        banner_text = (
            f"{n_total} lines compared ({n_versions} {v_noun}). "
            f"{n_changed} changed / {n_new} new / {n_removed} removed. "
            f"Net variance ({version_range}): {_fmt_dollar(net_variance)}"
        )

        any_reduced = (n_removed + (n_changed if net_variance < Decimal("0") else 0)) > 0
        any_increased = (n_new + (n_changed if net_variance > Decimal("0") else 0)) > 0

        if any_reduced:
            status: str = "warning"
            banner_level: str = "warning"
        elif any_increased or n_changed > 0:
            status = "success"
            banner_level = "ok"
        else:
            status = "success"
            banner_level = "ok"

        log_summary = (
            f"{n_total} lines | {n_unchanged} unchanged | "
            f"{n_changed} changed | {n_new} new | {n_removed} removed"
        )

        log_lines: list[LogLine] = [
            LogLine("SRP COMPARISON", tag="heading"),
            LogLine(
                log_summary,
                tag="ok" if not any_reduced else "warning",
            ),
            LogLine(
                f"First version total: {_fmt_dollar(summary.total_first)} | "
                f"Last version total: {_fmt_dollar(summary.total_last)} | "
                f"Net variance: {_fmt_dollar(net_variance)}",
                tag="ok" if net_variance >= Decimal("0") else "warning",
            ),
            LogLine(f"Output: {summary.output_path}", tag="muted"),
        ]

        metrics: list[tuple[str, str, str | None]] = [
            (f"{summary.version_labels[0]} total", _fmt_dollar(summary.total_first), None),
            (f"{summary.version_labels[-1]} total", _fmt_dollar(summary.total_last), None),
            (
                "Net variance",
                _fmt_dollar(net_variance),
                "ok" if net_variance >= Decimal("0") else "warning",
            ),
            (
                "Lines changed",
                str(n_changed + n_new + n_removed),
                None,
            ),
        ]

        # Build table columns dynamically based on provided versions
        table_columns: list[dict[str, Any]] = [
            {"key": "ref", "label": "Ref", "width": 50, "mono": True},
            {"key": "section", "label": "Section", "width": 180},
            {"key": "description", "label": "Description"},
        ]

        # One column per version
        slot_key_map = {
            "Indicative": "indicative",
            "Confirmed": "confirmed",
            "1st Revised": "revised1",
            "2nd Revised": "revised2",
        }
        for lbl in summary.version_labels:
            col_key = slot_key_map.get(lbl, lbl.lower().replace(" ", "_"))
            table_columns.append(
                {
                    "key": col_key,
                    "label": lbl,
                    "width": 110,
                    "align": "right",
                    "mono": True,
                }
            )

        # One variance column per adjacent pair
        for i in range(len(summary.version_labels) - 1):
            var_key = f"var_{i}_{i + 1}"
            a_lbl = summary.version_labels[i]
            b_lbl = summary.version_labels[i + 1]
            var_label = f"Var {a_lbl}\u2192{b_lbl}"
            table_columns.append(
                {
                    "key": var_key,
                    "label": var_label,
                    "width": 130,
                    "align": "right",
                    "mono": True,
                }
            )

        table_columns += [
            {"key": "pct", "label": "%", "width": 70, "align": "right", "mono": True},
            {"key": "category", "label": "Category", "width": 100},
        ]

        table_rows: list[dict[str, Any]] = []
        for ln in summary.lines:
            if ln.category in _DECREASED_CATS:
                bg: str | None = _DECREASED_BG
            elif ln.category in _INCREASED_CATS:
                bg = _INCREASED_BG
            elif ln.category == "changed":
                if ln.variance is not None and ln.variance > Decimal("0"):
                    bg = _INCREASED_BG
                elif ln.variance is not None and ln.variance < Decimal("0"):
                    bg = _DECREASED_BG
                else:
                    bg = None
            else:
                bg = None

            row: dict[str, Any] = {
                "ref": str(ln.ref),
                "section": ln.section,
                "description": ln.description,
                "pct": _fmt_pct(ln.pct),
                "category": ln.category,
                "_bg": bg,
            }

            # Per-version values
            for lbl in summary.version_labels:
                col_key = slot_key_map.get(lbl, lbl.lower().replace(" ", "_"))
                val = (
                    getattr(ln, col_key, None)
                    if col_key in ("indicative", "confirmed", "revised1", "revised2")
                    else None
                )
                row[col_key] = _fmt_dollar(val)

            # Adjacent variances
            for i, (_lbl, v) in enumerate(ln.adjacent_variances):
                row[f"var_{i}_{i + 1}"] = _fmt_dollar(v)

            # Legacy convenience keys for existing tests that check "variance"
            row["variance"] = _fmt_dollar(ln.variance)
            # Legacy slot keys (always set even if version not provided)
            row["indicative"] = _fmt_dollar(ln.indicative)
            row["confirmed"] = _fmt_dollar(ln.confirmed)

            table_rows.append(row)

        return ToolResult(
            status=status,  # type: ignore[arg-type]
            banner_level=banner_level,  # type: ignore[arg-type]
            banner_text=banner_text,
            metrics=metrics,
            log_lines=log_lines,
            table_columns=table_columns,
            table_rows=table_rows,
            output_path=summary.output_path,
        )

    # ------------------------------------------------------------------
    # Open output folder secondary action
    # ------------------------------------------------------------------

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return [("Open output folder", self._open_output_folder)]

    def _open_output_folder(self) -> None:
        import tkinter.messagebox as messagebox

        from toolkit.files import open_output_folder

        if self._last_output_path is None:
            messagebox.showinfo(
                "No output yet",
                "Run 'Generate comparison' first, then open the output folder.",
            )
            return
        open_output_folder(self._last_output_path)

    def preview_update(self, key: str, value: float | str) -> None:
        """No live-preview inputs on this tool; always returns None."""
        return None

    def clear(self) -> None:
        """Reset per-run state."""
        self._last_output_path = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _guess_year(stem: str) -> str:
    """Try to extract a 4-digit year from a filename stem; fall back to 'Unknown'."""
    import re

    m = re.search(r"\b(20\d{2})\b", stem)
    return m.group(1) if m else "Unknown"
