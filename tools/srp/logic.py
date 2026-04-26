from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal

import pdfplumber
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from toolkit.base_tool import ProgressFn
from toolkit.fills import argb
from toolkit.tokens import HL_MISMATCH, HL_SOURCE_ONLY

# ---------------------------------------------------------------------------
# Currency parsing  (re-uses the same rules as tools.sub_program.logic)
# ---------------------------------------------------------------------------

_DASH_RE = re.compile(r"^[—–\-]{1,2}$")


def parse_decimal(raw: str) -> Decimal:
    """Convert an SRP currency string to Decimal.

    Handles: ``"$1,234.56"``, ``"1,234.56"``, ``"$0.00"``, ``"—"``, blank.
    Returns ``Decimal("0")`` for empty / dash inputs.
    """
    text = raw.strip() if raw else ""
    if not text or _DASH_RE.match(text):
        return Decimal("0")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    text = text.lstrip("$").strip()
    text = text.replace(",", "")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse {raw!r} as a decimal: {exc}") from exc


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SrpLine:
    ref: int
    section: str
    description: str
    indicative: Decimal | None  # None for new_in_confirmed
    confirmed: Decimal | None  # None for removed
    variance: Decimal | None  # confirmed - indicative; None if either is None
    pct: Decimal | None
    category: Literal["unchanged", "increased", "decreased", "new_in_confirmed", "removed"]


@dataclass(frozen=True)
class SrpSummary:
    lines: list[SrpLine]
    total_indicative: Decimal
    total_confirmed: Decimal
    counts: dict[str, int]  # by category
    output_path: Path


# ---------------------------------------------------------------------------
# Skip / header patterns
# ---------------------------------------------------------------------------

# Metadata / header patterns at the top of each page to skip
_SKIP_ABOVE_RE = re.compile(
    r"^("
    r"Department of Education"
    r"|Student Resource Package"
    r"|Host School"
    r"|Budget Type"
    r"|School\s.+SFO Index"
    r"|Type Secondary"
    r"|Secondary Students"
    r"|Equity \(Social Disadvantage\) Students"
    r"|Primary Level"
    r"|Policy and Advisory"
    r"|Ref\s+Students"
    r")",
    re.IGNORECASE,
)

# Sub-total lines: start with $ (no description)
_SUBTOTAL_RE = re.compile(r"^\$[\d,]+\.\d{2}")

# Grand total line
_GRAND_TOTAL_RE = re.compile(r"^TOTAL STUDENT RESOURCE PACKAGE", re.IGNORECASE)

# Page footer: date/BudgetID/Page
_FOOTER_RE = re.compile(r"^\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}")

# The 'Equity Reform Implementation Statement' line: no Ref integer, appears
# after the last table on page 1, treated as a section-level carry-over.
# We skip it because it has no discrete Ref integer.
_EQUITY_REFORM_RE = re.compile(r"^Equity Reform Implementation Statement", re.IGNORECASE)


def _is_section_header(line: str) -> bool:
    """Return True if *line* is a section-header (plain label, no ref number)."""
    if _SKIP_ABOVE_RE.match(line):
        return False
    if _SUBTOTAL_RE.match(line):
        return False
    if _GRAND_TOTAL_RE.match(line):
        return False
    if _FOOTER_RE.match(line):
        return False
    if _EQUITY_REFORM_RE.match(line):
        return False
    # A section header has no embedded ref-like digit sequence surrounded by spaces
    # and does not contain a $ sign (it's pure label text).
    if "$" in line:
        return False
    return True


# ---------------------------------------------------------------------------
# PDF parser
# ---------------------------------------------------------------------------


def parse_srp_pdf(pdf_path: Path) -> dict[tuple[int, str], tuple[str, Decimal]]:
    """Parse a VIC DoE SRP Budget Details PDF.

    Returns a mapping ``{(ref, description): (section, total_amount)}``.

    Uses ``pdfplumber.extract_tables()`` as the primary extraction path —
    section headers are read from the text immediately above each table.
    The ``Equity Reform Implementation Statement`` row (no discrete Ref integer)
    is skipped.  The ``VDSS:`` rows that carry "Statement" in the rate column
    are valid data rows (they have a real integer Ref) and are included.

    Raises :class:`ValueError` if the file is absent or yields no data rows.
    """
    if not pdf_path.exists():
        raise ValueError(f"File not found: {pdf_path}")

    result: dict[tuple[int, str], tuple[str, Decimal]] = {}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise ValueError(
                    "SRP PDF appears empty or unrecognised; "
                    "check the file is a VIC DoE SRP Budget Details export"
                )

            for page in pdf.pages:
                found_tables = page.find_tables()

                for t_idx, found_table in enumerate(found_tables):
                    # --- Derive section header from text above this table ---
                    prev_bottom = found_tables[t_idx - 1].bbox[3] if t_idx > 0 else 0.0
                    above_crop = page.crop((0.0, prev_bottom, page.width, found_table.bbox[1]))
                    above_text = above_crop.extract_text() or ""

                    section = _extract_section_header(above_text)

                    # --- Parse data rows ---
                    for row in found_table.extract():
                        if not row or not row[0]:
                            continue
                        desc = row[0].strip()
                        ref_raw = row[1].strip() if len(row) > 1 and row[1] else ""

                        # Only numeric Ref values are data rows
                        if not ref_raw.isdigit():
                            continue

                        ref = int(ref_raw)
                        # Total is always the last column
                        total_raw = row[-1].strip() if row[-1] else "$0.00"
                        try:
                            total = parse_decimal(total_raw)
                        except ValueError:
                            total = Decimal("0")

                        key = (ref, desc)
                        # Later pages / duplicate keys: keep first occurrence
                        # (both PDFs list each line exactly once)
                        if key not in result:
                            result[key] = (section, total)

    except OSError as exc:
        raise ValueError(
            "SRP PDF appears empty or unrecognised; "
            "check the file is a VIC DoE SRP Budget Details export"
        ) from exc

    if not result:
        raise ValueError(
            "SRP PDF appears empty or unrecognised; "
            "check the file is a VIC DoE SRP Budget Details export"
        )

    return result


def _extract_section_header(above_text: str) -> str:
    """Return the last plausible section-header line from *above_text*.

    Works backwards through the lines so the closest heading wins.
    Falls back to ``"Unknown"`` if nothing qualifiable is found.
    """
    for line in reversed(above_text.splitlines()):
        stripped = line.strip()
        if not stripped:
            continue
        if _is_section_header(stripped):
            return stripped
    return "Unknown"


# ---------------------------------------------------------------------------
# Diff / compare
# ---------------------------------------------------------------------------


def compare_srp(
    indicative: dict[tuple[int, str], tuple[str, Decimal]],
    confirmed: dict[tuple[int, str], tuple[str, Decimal]],
) -> list[SrpLine]:
    """Diff two parsed SRP dicts and return a list of :class:`SrpLine` objects.

    Join key: ``(ref, description)`` — NOT ref alone (Ref 15 is reused for
    multiple integration-student levels).

    Categories:
    * ``unchanged``        — both present, totals equal (within 1 cent)
    * ``increased``        — both present, confirmed > indicative
    * ``decreased``        — both present, confirmed < indicative
    * ``new_in_confirmed`` — confirmed only
    * ``removed``          — indicative only
    """
    all_keys = set(indicative) | set(confirmed)
    lines: list[SrpLine] = []

    for key in sorted(all_keys, key=lambda k: (k[0], k[1])):
        ref, desc = key
        ind_entry = indicative.get(key)
        conf_entry = confirmed.get(key)

        ind_section = ind_entry[0] if ind_entry is not None else ""
        conf_section = conf_entry[0] if conf_entry is not None else ""
        section = ind_section or conf_section

        ind_val: Decimal | None = ind_entry[1] if ind_entry is not None else None
        conf_val: Decimal | None = conf_entry[1] if conf_entry is not None else None

        if ind_val is not None and conf_val is not None:
            variance = conf_val - ind_val
            # Percentage: variance / indicative * 100; guard zero-division
            if ind_val != Decimal("0"):
                pct = (variance / ind_val * Decimal("100")).quantize(Decimal("0.01"))
            else:
                pct = Decimal("0")

            # "Equal within 1 cent" tolerance
            if abs(variance) < Decimal("0.01"):
                category: Literal[
                    "unchanged", "increased", "decreased", "new_in_confirmed", "removed"
                ] = "unchanged"
            elif conf_val > ind_val:
                category = "increased"
            else:
                category = "decreased"
        elif ind_val is None:
            # new in confirmed
            variance = None
            pct = None
            category = "new_in_confirmed"
        else:
            # removed
            variance = None
            pct = None
            category = "removed"

        lines.append(
            SrpLine(
                ref=ref,
                section=section,
                description=desc,
                indicative=ind_val,
                confirmed=conf_val,
                variance=variance,
                pct=pct,
                category=category,
            )
        )

    return lines


# ---------------------------------------------------------------------------
# XLSX writer
# ---------------------------------------------------------------------------

_HEADERS = ["Ref", "Section", "Description", "Indicative", "Confirmed", "Variance", "%", "Category"]

_COL_WIDTHS = [8, 36, 44, 18, 18, 18, 10, 18]

_MISMATCH_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_MISMATCH))
_SOURCE_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_SOURCE_ONLY))

_DECREASED_CATS: frozenset[str] = frozenset({"decreased", "removed"})
_INCREASED_CATS: frozenset[str] = frozenset({"increased", "new_in_confirmed"})


def _fmt_dollar(value: Decimal) -> str:
    return f"${value:,.2f}"


def _fmt_pct(value: Decimal) -> str:
    return f"{value:,.2f}%"


def _write_xlsx(lines: list[SrpLine], output_file: Path) -> None:
    """Write *lines* to a new XLSX workbook at *output_file*."""
    from openpyxl import Workbook
    from openpyxl.worksheet.worksheet import Worksheet

    wb = Workbook()
    active = wb.active
    assert isinstance(active, Worksheet)
    ws: Worksheet = active
    ws.title = "SRP Comparison"

    # Header row
    for col_idx, header in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    ws.freeze_panes = "A2"

    # Data rows
    for row_idx, ln in enumerate(lines, start=2):
        ind_str = _fmt_dollar(ln.indicative) if ln.indicative is not None else ""
        conf_str = _fmt_dollar(ln.confirmed) if ln.confirmed is not None else ""
        var_str = _fmt_dollar(ln.variance) if ln.variance is not None else ""
        pct_str = _fmt_pct(ln.pct) if ln.pct is not None else ""

        values: list[str | int] = [
            ln.ref,
            ln.section,
            ln.description,
            ind_str,
            conf_str,
            var_str,
            pct_str,
            ln.category,
        ]

        # Choose fill
        if ln.category in _DECREASED_CATS:
            fill: PatternFill | None = _MISMATCH_FILL
        elif ln.category in _INCREASED_CATS:
            fill = _SOURCE_FILL
        else:
            fill = None

        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            if fill is not None:
                cell.fill = fill

    for col_idx, width in enumerate(_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def generate_srp_comparison(
    indicative_pdf: Path,
    confirmed_pdf: Path,
    output_file: Path,
    progress: ProgressFn,
) -> SrpSummary:
    """Parse both SRP PDFs, diff them, write an XLSX, and return :class:`SrpSummary`.

    Parameters
    ----------
    indicative_pdf:
        Path to the Indicative SRP PDF.
    confirmed_pdf:
        Path to the Confirmed SRP PDF.
    output_file:
        Destination ``.xlsx`` path.
    progress:
        Callback ``(percent: int, message: str) -> None``.
    """
    progress(10, "Reading Indicative SRP…")
    indicative = parse_srp_pdf(indicative_pdf)

    progress(30, "Reading Confirmed SRP…")
    confirmed = parse_srp_pdf(confirmed_pdf)

    progress(55, "Comparing line by line…")
    lines = compare_srp(indicative, confirmed)

    progress(75, "Writing workbook…")
    _write_xlsx(lines, output_file)

    # Aggregate totals and counts
    total_indicative = sum((v for (_, v) in indicative.values()), Decimal("0"))
    total_confirmed = sum((v for (_, v) in confirmed.values()), Decimal("0"))

    counts: dict[str, int] = {}
    for ln in lines:
        counts[ln.category] = counts.get(ln.category, 0) + 1

    progress(100, "Done.")

    return SrpSummary(
        lines=lines,
        total_indicative=total_indicative,
        total_confirmed=total_confirmed,
        counts=counts,
        output_path=output_file,
    )
