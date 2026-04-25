from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import openpyxl
import pdfplumber
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from toolkit.base_tool import ProgressFn
from toolkit.fills import argb
from toolkit.tokens import HL_MISMATCH

# ---------------------------------------------------------------------------
# Faculty inference
# ---------------------------------------------------------------------------
# Sub-program codes are numeric (e.g. 4001, 8599).
# Faculties are inferred from the leading digit(s) as visible in the PDF.
# The CASES21 GL21157 export groups rows by Revenue / Expenditure sections
# rather than by faculty, so we derive faculty from the code prefix.

_FACULTY_MAP: dict[str, str] = {
    "1": "Design & Technology",
    "4": "Curriculum",
    "5": "Student Wellbeing",
    "6": "Facilities",
    "7": "Administration",
    "8": "Programs & Camps",
    "9": "Computing & Curriculum",
}


def _infer_faculty(sub_program: str) -> str | None:
    """Return a faculty label from the first digit of *sub_program*."""
    code = sub_program.strip()
    if code and code[0].isdigit():
        return _FACULTY_MAP.get(code[0])
    return None


# ---------------------------------------------------------------------------
# Currency parsing
# ---------------------------------------------------------------------------

_DASH_RE = re.compile(r"^[\u2014\u2013\-]{1,2}$")  # em-dash, en-dash, hyphen alone


def parse_decimal(raw: str) -> Decimal:
    """Convert a CASES21 currency string to Decimal.

    Handles: ``"1,234.56"``, ``"$1,234.56"``, ``"-500.00"``, ``"(500.00)"``,
    ``"$0.00"``, ``"\u2014"`` (em-dash = zero), blank strings.
    Returns ``Decimal("0")`` for empty / dash inputs.
    """
    text = raw.strip() if raw else ""

    if not text or _DASH_RE.match(text):
        return Decimal("0")

    # parentheses -> negative  e.g. "(500.00)" -> "-500.00"
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]

    # strip leading $
    text = text.lstrip("$").strip()

    # remove thousands separators
    text = text.replace(",", "")

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse {raw!r} as a decimal: {exc}") from exc


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubProgramLine:
    sub_program: str
    account: str       # section tag: "Revenue" | "Expenditure"
    description: str
    budget: Decimal
    ytd: Decimal
    remaining: Decimal
    used_pct: Decimal  # 0..100+
    faculty: str | None
    is_over: bool
    commentary: str = ""


@dataclass(frozen=True)
class ReportSummary:
    lines: list[SubProgramLine]
    faculty_counts: dict[str, int]
    over_budget_lines: list[SubProgramLine]
    total_budget: Decimal
    total_ytd: Decimal
    output_path: Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Header patterns that mark the start of a section
_REVENUE_HDR = re.compile(r"Revenue Recurrent", re.IGNORECASE)
_EXPENDITURE_HDR = re.compile(r"Expenditure Recurrent", re.IGNORECASE)

# Lines we must skip
_SKIP_RE = re.compile(
    r"^("
    r"\d{4}:\w"           # school header e.g. "8819:Melbourne"
    r"|General Ledger"
    r"|Annual Sub Program"
    r"|From Sub Program"
    r"|Revenue Recurrent"
    r"|Expenditure Recurrent"
    r"|Sub Prog\."        # column header
    r"|Revenue totals"
    r"|Expenditure totals"
    r"|\d+ \w+ \d{4}"     # date footer e.g. "3 March 2026"
    r"|\d+ \[GL"          # page/number footer e.g. "1 [GL21157]"
    r")",
    re.IGNORECASE,
)

# Matches a whitespace-delimited field that is a standalone numeric token:
# optional leading minus/dollar, digits with commas, optional decimal part;
# OR a parenthesised value like (500.00).
_NUM_PART_RE = re.compile(
    r"^[\-\$]?[\d,]+(\.\d+)?$|^\([\d,]+(\.\d+)?\)$"
)


def _parse_numeric_tokens_from_parts(parts: list[str]) -> list[str]:
    """Filter *parts* to only those that look like numeric tokens."""
    return [p for p in parts if _NUM_PART_RE.match(p)]


def _build_line(
    sub_prog: str,
    title: str,
    tokens: list[str],
    section: str,
) -> SubProgramLine:
    """Build a SubProgramLine from the numeric tokens on a data row.

    Revenue rows:
        Last year actual | Last year budget | Annual budget | YTD | % Budget received
    Expenditure rows:
        Last year actual | Last year budget | Annual budget | YTD | % | Outstanding | Uncommitted

    We only need: Annual budget, YTD, remaining, used_pct.
    The column layout varies (some rows omit early columns when zero).
    Strategy: locate the % token (has a decimal point, value 0..9999),
    then budget = token[-2] before % and ytd = token[-1] before %.
    """
    pct = Decimal("0")
    budget = Decimal("0")
    ytd = Decimal("0")

    if not tokens:
        remaining = budget - ytd
        faculty = _infer_faculty(sub_prog)
        is_over = ytd > budget if budget != 0 else False
        return SubProgramLine(
            sub_program=sub_prog,
            account=section,
            description=title.strip(),
            budget=budget,
            ytd=ytd,
            remaining=remaining,
            used_pct=pct,
            faculty=faculty,
            is_over=is_over,
        )

    # Locate % token: scan right-to-left for a value with a dot and value <= 9999
    pct_idx: int | None = None
    for idx in range(len(tokens) - 1, -1, -1):
        raw = tokens[idx].replace(",", "")
        if "." in raw:
            try:
                v = Decimal(raw)
                if Decimal("0") <= v <= Decimal("9999"):
                    pct_idx = idx
                    break
            except InvalidOperation:
                pass

    if pct_idx is not None:
        pct = parse_decimal(tokens[pct_idx])
        pre = tokens[:pct_idx]
    else:
        pre = tokens

    # From pre: last = YTD, second-last = Annual budget (if >= 2 tokens)
    if len(pre) >= 2:
        ytd = parse_decimal(pre[-1])
        budget = parse_decimal(pre[-2])
    elif len(pre) == 1:
        # Only one token before %: treat as YTD; budget is zero
        ytd = parse_decimal(pre[-1])
        budget = Decimal("0")
    # else: both remain 0

    remaining = budget - ytd
    faculty = _infer_faculty(sub_prog)
    is_over = bool(ytd > budget) if budget != Decimal("0") else False

    return SubProgramLine(
        sub_program=sub_prog,
        account=section,
        description=title.strip(),
        budget=budget,
        ytd=ytd,
        remaining=remaining,
        used_pct=pct,
        faculty=faculty,
        is_over=is_over,
    )


def _parse_text_lines(text: str, section: str) -> list[SubProgramLine]:
    """Parse data rows from a page's extracted text given its current section."""
    results: list[SubProgramLine] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _SKIP_RE.match(line):
            continue

        # Data row must start with a 4-digit sub-program code
        m = re.match(r"^(\d{4})\s+(.*)", line)
        if not m:
            continue

        sub_prog = m.group(1)
        rest = m.group(2).strip()

        # Split title from numerics using whitespace-delimited tokens.
        # Scan left-to-right; first part that looks like a standalone number
        # marks the boundary between title text and numeric columns.
        parts = rest.split()
        title_parts: list[str] = []
        numeric_start_idx = len(parts)
        for pi, part in enumerate(parts):
            if _NUM_PART_RE.match(part):
                numeric_start_idx = pi
                break
            title_parts.append(part)

        title = " ".join(title_parts)
        numeric_parts = parts[numeric_start_idx:]
        tokens = _parse_numeric_tokens_from_parts(numeric_parts)

        results.append(_build_line(sub_prog, title, tokens, section))

    return results


# ---------------------------------------------------------------------------
# Public API — parse from PDF
# ---------------------------------------------------------------------------


def parse_sub_program_pdf(pdf_path: Path) -> list[SubProgramLine]:
    """Parse a CASES21 GL21157 Annual Sub-Program Budget Report PDF.

    Returns a list of :class:`SubProgramLine` objects, one per data row.
    Skips header/footer rows and total rows.

    Raises :class:`ValueError` if the file appears empty or unrecognised.
    """
    if not pdf_path.exists():
        raise ValueError(f"File not found: {pdf_path}")

    lines: list[SubProgramLine] = []
    section = "Revenue"  # default; updated per-page

    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                raise ValueError(
                    "Sub-Program Report PDF appears empty or unrecognised; "
                    "check the file is a CASES21 GL21157 export"
                )

            for page in pdf.pages:
                # Try tables first; fall back to text
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row and row[0]:
                                cell0 = str(row[0]).strip()
                                if _REVENUE_HDR.search(cell0):
                                    section = "Revenue"
                                elif _EXPENDITURE_HDR.search(cell0):
                                    section = "Expenditure"
                else:
                    text = page.extract_text() or ""
                    # Update section from page headers
                    if _REVENUE_HDR.search(text):
                        section = "Revenue"
                    if _EXPENDITURE_HDR.search(text):
                        section = "Expenditure"

                    page_lines = _parse_text_lines(text, section)
                    lines.extend(page_lines)

    except OSError as exc:
        raise ValueError(
            "Sub-Program Report PDF appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        ) from exc

    if not lines:
        raise ValueError(
            "Sub-Program Report PDF appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    return lines


# ---------------------------------------------------------------------------
# Public API — parse from XLSX (fallback)
# ---------------------------------------------------------------------------


def _get_cell(row: Sequence[Any], idx: int) -> Decimal:
    """Safely extract a Decimal from a row at *idx*."""
    if idx < len(row) and row[idx] is not None:
        raw = str(row[idx]).strip()
        try:
            return parse_decimal(raw)
        except ValueError:
            return Decimal("0")
    return Decimal("0")


def parse_sub_program_xlsx(xlsx_path: Path) -> list[SubProgramLine]:
    """Fallback parser: read a CASES21 XLSX export of the sub-program report.

    Expects columns in order: Sub-Program, Title, [Last year actual],
    [Last year budget], Annual budget, YTD, % Budget [, Outstanding, Uncommitted].
    The first row is treated as a header.
    """
    if not xlsx_path.exists():
        raise ValueError(f"File not found: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        rows: list[Any] = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if len(rows) < 2:
        raise ValueError(
            "Sub-Program Report XLSX appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    lines: list[SubProgramLine] = []
    section = "Expenditure"

    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        sub_prog = str(row[0]).strip()
        if not sub_prog.isdigit():
            continue

        title = str(row[1]).strip() if len(row) > 1 and row[1] is not None else ""

        budget = _get_cell(row, 4)
        ytd = _get_cell(row, 5)
        pct = _get_cell(row, 6)
        remaining = budget - ytd
        faculty = _infer_faculty(sub_prog)
        is_over = bool(ytd > budget) if budget != Decimal("0") else False

        lines.append(
            SubProgramLine(
                sub_program=sub_prog,
                account=section,
                description=title,
                budget=budget,
                ytd=ytd,
                remaining=remaining,
                used_pct=pct,
                faculty=faculty,
                is_over=is_over,
            )
        )

    if not lines:
        raise ValueError(
            "Sub-Program Report XLSX appears empty or unrecognised; "
            "check the file is a CASES21 GL21157 export"
        )

    return lines


# ---------------------------------------------------------------------------
# Public API — prior-period comments
# ---------------------------------------------------------------------------


def load_prior_period_comments(xlsx_path: Path) -> dict[tuple[str, str], str]:
    """Load per-row commentary from a prior-period comments XLSX.

    The workbook must have columns: Sub-Program | Account | Commentary
    (or Sub_Program | Account | Commentary - case-insensitive, underscores
    treated as spaces).  Returns ``{(sub_program, account): commentary_text}``.
    """
    if not xlsx_path.exists():
        raise ValueError(f"Comments file not found: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        ws = wb[wb.sheetnames[0]]
        all_rows: list[Any] = [list(r) for r in ws.iter_rows(values_only=True)]
    finally:
        wb.close()

    if not all_rows:
        return {}

    # Detect header columns
    header = [
        str(c).strip().lower().replace("_", " ") if c is not None else ""
        for c in all_rows[0]
    ]

    try:
        sp_col = next(i for i, h in enumerate(header) if "sub" in h and "prog" in h)
    except StopIteration:
        sp_col = 0

    try:
        acc_col = next(i for i, h in enumerate(header) if "account" in h)
    except StopIteration:
        acc_col = 1

    try:
        txt_col = next(i for i, h in enumerate(header) if "comment" in h)
    except StopIteration:
        txt_col = 2

    result: dict[tuple[str, str], str] = {}
    for row in all_rows[1:]:
        if not row:
            continue
        sp = (
            str(row[sp_col]).strip()
            if sp_col < len(row) and row[sp_col] is not None
            else ""
        )
        acc = (
            str(row[acc_col]).strip()
            if acc_col < len(row) and row[acc_col] is not None
            else ""
        )
        txt = (
            str(row[txt_col]).strip()
            if txt_col < len(row) and row[txt_col] is not None
            else ""
        )
        if sp or acc:
            result[(sp, acc)] = txt

    return result


# ---------------------------------------------------------------------------
# XLSX output writer
# ---------------------------------------------------------------------------

_HEADERS = [
    "Sub-Program",
    "Account",
    "Description",
    "Budget",
    "YTD",
    "Remaining",
    "Used %",
    "Faculty",
    "Commentary",
]

_COL_WIDTHS = [14, 14, 40, 16, 16, 16, 12, 24, 40]

_OVER_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_MISMATCH))


def _write_xlsx(
    lines: list[SubProgramLine],
    output_file: Path,
) -> None:
    """Write all lines to a new XLSX workbook."""
    from openpyxl import Workbook
    from openpyxl.worksheet.worksheet import Worksheet

    wb = Workbook()
    active = wb.active
    assert isinstance(active, Worksheet)
    ws: Worksheet = active
    ws.title = "Sub-Program Budget"

    # Header row
    for col_idx, header in enumerate(_HEADERS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    # Freeze header row
    ws.freeze_panes = "A2"

    # Data rows
    for row_idx, line in enumerate(lines, start=2):
        values: list[Any] = [
            line.sub_program,
            line.account,
            line.description,
            float(line.budget),
            float(line.ytd),
            float(line.remaining),
            float(line.used_pct),
            line.faculty or "",
            line.commentary,
        ]
        fill = _OVER_FILL if line.is_over else None
        for col_idx, val in enumerate(values, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            if fill is not None:
                cell.fill = fill

    # Column widths
    for col_idx, width in enumerate(_COL_WIDTHS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)


# ---------------------------------------------------------------------------
# Public API — generate_report
# ---------------------------------------------------------------------------


def generate_report(
    report_file: Path,
    comments_file: Path | None,
    output_file: Path,
    progress: ProgressFn,
) -> ReportSummary:
    """Orchestrate parse + comment join + XLSX write.

    Parameters
    ----------
    report_file:
        CASES21 GL21157 PDF (or XLSX fallback).
    comments_file:
        Optional prior-period commentary workbook.
    output_file:
        Destination ``.xlsx`` path.
    progress:
        Callback ``(percent: int, message: str) -> None``.
    """
    progress(10, "Reading PDF\u2026")

    suffix = report_file.suffix.lower()
    if suffix == ".pdf":
        lines = parse_sub_program_pdf(report_file)
    elif suffix in {".xlsx", ".xlsm"}:
        lines = parse_sub_program_xlsx(report_file)
    else:
        raise ValueError(
            f"Unsupported report file format: {suffix!r}. "
            "Please supply a .pdf or .xlsx file."
        )

    progress(40, "Joining commentary\u2026")

    comments: dict[tuple[str, str], str] = {}
    if comments_file is not None:
        comments = load_prior_period_comments(comments_file)

    # Attach commentary and finalise lines
    final_lines: list[SubProgramLine] = []
    for ln in lines:
        commentary = comments.get((ln.sub_program, ln.account), "")
        if commentary != ln.commentary:
            ln = SubProgramLine(
                sub_program=ln.sub_program,
                account=ln.account,
                description=ln.description,
                budget=ln.budget,
                ytd=ln.ytd,
                remaining=ln.remaining,
                used_pct=ln.used_pct,
                faculty=ln.faculty,
                is_over=ln.is_over,
                commentary=commentary,
            )
        final_lines.append(ln)

    progress(70, "Writing workbook\u2026")

    _write_xlsx(final_lines, output_file)

    # Build summary
    faculty_counts: dict[str, int] = {}
    for ln in final_lines:
        key = ln.faculty or "Unknown"
        faculty_counts[key] = faculty_counts.get(key, 0) + 1

    over_budget = [ln for ln in final_lines if ln.is_over]
    total_budget = sum((ln.budget for ln in final_lines), Decimal("0"))
    total_ytd = sum((ln.ytd for ln in final_lines), Decimal("0"))

    progress(100, "Done.")

    return ReportSummary(
        lines=final_lines,
        faculty_counts=faculty_counts,
        over_budget_lines=over_budget,
        total_budget=total_budget,
        total_ytd=total_ytd,
        output_path=output_file,
    )
