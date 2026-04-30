from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
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

# Pink row fill for over-budget rows in the XLSX output.
# Uses argb() from toolkit.fills to derive the correct openpyxl ARGB literal
# from the canonical HL_MISMATCH token — same approach as master_budget/logic.py.
_OVER_FILL = PatternFill(fill_type="solid", fgColor=argb(HL_MISMATCH))

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

_DASH_RE = re.compile(r"^[—–\-]{1,2}$")  # em-dash, en-dash, hyphen alone


def parse_decimal(raw: str) -> Decimal:
    """Convert a CASES21 currency string to Decimal.

    Handles: ``"1,234.56"``, ``"$1,234.56"``, ``"-500.00"``, ``"(500.00)"``,
    ``"$0.00"``, ``"—"`` (em-dash = zero), blank strings.
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
    account: str  # section tag: "Revenue" | "Expenditure"
    description: str
    budget: Decimal
    ytd: Decimal
    remaining: Decimal
    used_pct: Decimal  # 0..100+
    faculty: str | None
    is_over: bool
    commentary: str = ""
    # New fields -- default to zero so existing callers remain valid.
    last_year_actual: Decimal = Decimal("0")
    last_year_budget: Decimal = Decimal("0")
    outstanding_orders: Decimal = Decimal("0")


@dataclass(frozen=True)
class ReportSummary:
    lines: list[SubProgramLine]
    faculty_counts: dict[str, int]
    over_budget_lines: list[SubProgramLine]
    total_budget: Decimal
    total_ytd: Decimal
    output_path: Path
    faculty_budget: dict[str, Decimal] = field(default_factory=dict)
    faculty_ytd: dict[str, Decimal] = field(default_factory=dict)
    faculty_used_pct: dict[str, Decimal] = field(default_factory=dict)
    period_label: str = ""  # e.g. "March 2026" -- extracted from the PDF footer
    over_budget_threshold: float = 101.0  # threshold used for is_over computation
    # Round 21 — separate Revenue / Expense thresholds.  When the user does
    # not split them explicitly, both fields mirror over_budget_threshold
    # (set in generate_report) so existing callers stay valid.
    revenue_threshold: float = 101.0
    expense_threshold: float = 101.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Header patterns that mark the start of a section
_REVENUE_HDR = re.compile(r"Revenue Recurrent", re.IGNORECASE)
_EXPENDITURE_HDR = re.compile(r"Expenditure Recurrent", re.IGNORECASE)

# Lines we must skip
_SKIP_RE = re.compile(
    r"^("
    r"\d{4}:\w"  # school header e.g. "8819:Melbourne"
    r"|General Ledger"
    r"|Annual Sub Program"
    r"|From Sub Program"
    r"|Revenue Recurrent"
    r"|Expenditure Recurrent"
    r"|Sub Prog\."  # column header
    r"|Revenue totals"
    r"|Expenditure totals"
    r"|\d+ \w+ \d{4}"  # date footer e.g. "3 March 2026"
    r"|\d+ \[GL"  # page/number footer e.g. "1 [GL21157]"
    r")",
    re.IGNORECASE,
)

# Matches a whitespace-delimited field that is a standalone numeric token:
# optional leading minus/dollar, digits with commas, optional decimal part;
# OR a parenthesised value like (500.00).
_NUM_PART_RE = re.compile(r"^[\-\$]?[\d,]+(\.\d+)?$|^\([\d,]+(\.\d+)?\)$")


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

    Column layout varies: some rows omit early columns when zero (particularly
    last-year columns), and YTD is omitted when it is zero (pct then shows 0.00).

    Strategy
    --------
    1. Locate the % token (has a decimal point, 0 <= value <= 9999) by scanning
       right-to-left; this is always present.
    2. ``pre`` = tokens before %; ``post`` = tokens after %.
    3. budget = pre[-2], ytd = pre[-1]  (if len(pre) >= 2; existing logic).
    4. last_year_budget = pre[-3] if len(pre) >= 3 else zero.
    5. last_year_actual  = pre[-4] if len(pre) >= 4 else zero.
    6. outstanding_orders (Expenditure only): post[0] if len(post) >= 2; zero
       if post has only one token (that token is then Uncommitted Balance).
    """
    pct = Decimal("0")
    budget = Decimal("0")
    ytd = Decimal("0")
    last_year_actual = Decimal("0")
    last_year_budget = Decimal("0")
    outstanding_orders = Decimal("0")

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
        post = tokens[pct_idx + 1 :]
    else:
        pre = tokens
        post = []

    # From pre: last = YTD, second-last = Annual budget (if >= 2 tokens)
    if len(pre) >= 2:
        ytd = parse_decimal(pre[-1])
        budget = parse_decimal(pre[-2])
    elif len(pre) == 1:
        # Only one token before %: treat as YTD; budget is zero
        ytd = parse_decimal(pre[-1])
        budget = Decimal("0")
    # else: both remain 0

    # Last-year columns sit immediately before Annual budget in pre.
    if len(pre) >= 3:
        last_year_budget = parse_decimal(pre[-3])
    if len(pre) >= 4:
        last_year_actual = parse_decimal(pre[-4])

    # Outstanding orders: only meaningful for Expenditure rows.
    # When present it is the FIRST token after %; the second (if any) is
    # Uncommitted Balance (derived, not stored).  When outstanding is zero the
    # PDF omits it entirely, leaving only Uncommitted Balance in post.
    if section == "Expenditure" and len(post) >= 2:
        outstanding_orders = parse_decimal(post[0])

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
        last_year_actual=last_year_actual,
        last_year_budget=last_year_budget,
        outstanding_orders=outstanding_orders,
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


# Regex to extract the print-date footer: "3 March 2026 13:37 1 [GL21157]"
# Capture group 1: "Month YYYY" string used as the period label.
_FOOTER_DATE_RE = re.compile(
    r"\d{1,2}\s+([A-Z][a-z]+\s+\d{4})\s+\d{2}:\d{2}\s+\d+\s+\[GL",
    re.IGNORECASE,
)


def _extract_period_label(text: str) -> str:
    """Return 'Month YYYY' from the GL21157 page-footer date, or '' if not found.

    The footer format is: ``3 March 2026 13:37 1 [GL21157]``
    This function extracts ``March 2026`` from that pattern.
    """
    m = _FOOTER_DATE_RE.search(text)
    if m:
        return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Public API -- parse from PDF
# ---------------------------------------------------------------------------


def parse_sub_program_pdf(pdf_path: Path) -> list[SubProgramLine]:
    """Parse a CASES21 GL21157 Annual Sub-Program Budget Report PDF.

    Returns a list of :class:`SubProgramLine` objects, one per data row.
    Skips header/footer rows and total rows.

    Raises :class:`ValueError` if the file appears empty or unrecognised.
    """
    lines, _period = _parse_sub_program_pdf_internal(pdf_path)
    return lines


def parse_sub_program_pdf_with_period(pdf_path: Path) -> tuple[list[SubProgramLine], str]:
    """Parse a GL21157 PDF and return ``(lines, period_label)``.

    ``period_label`` is a string like ``"March 2026"`` extracted from the
    footer date; it is ``""`` if detection fails.
    """
    return _parse_sub_program_pdf_internal(pdf_path)


def _parse_sub_program_pdf_internal(
    pdf_path: Path,
) -> tuple[list[SubProgramLine], str]:
    """Internal implementation shared by the two public PDF parsers."""
    if not pdf_path.exists():
        raise ValueError(f"File not found: {pdf_path}")

    lines: list[SubProgramLine] = []
    section = "Revenue"  # default; updated per-page
    period_label = ""

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

                    # Extract period label from footer (first match wins).
                    if not period_label:
                        period_label = _extract_period_label(text)

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

    return lines, period_label


# ---------------------------------------------------------------------------
# Public API -- parse from XLSX (fallback)
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
# Public API -- prior-period comments
# ---------------------------------------------------------------------------


def load_prior_period_comments(xlsx_path: Path) -> dict[tuple[str, str], str]:
    """Load per-row commentary from a prior-period comments XLSX.

    Reads every worksheet in the workbook (Revenue + Expenditure sheets in
    a typical export both carry comments), and returns
    ``{(sub_program, second_key): commentary_text}``.  The second key is
    either the account code (if an "Account" header is found) or the
    line title / description (if not).  This keeps the join robust against
    files exported by this tool itself, which intentionally drops the raw
    Account column from the published workbook.

    Bug fixed in Round 21
    ---------------------
    Earlier versions silently defaulted to ``txt_col = 2`` when no
    "comments" header was found.  Column 2 in our own export is
    "Last year actual" — a dollar amount — so users saw last-year-actual
    values copied into the new report's comments column.  We now raise a
    descriptive ValueError instead, listing the headers we did find so
    the user can rename the column in their source file.

    Accepted comment-column synonyms: comment, comments, commentary,
    note, notes, remark, remarks, memo.

    Accepted account-column synonyms: account, account code, gl, gl code.
    If none match, the line title / description column is used as the
    secondary join key.
    """
    if not xlsx_path.exists():
        raise ValueError(f"Comments file not found: {xlsx_path}")

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        # Walk EVERY sheet — exports of this tool produce Revenue and
        # Expenditure as separate sheets and both carry comments.
        per_sheet_rows: list[list[list[Any]]] = [
            [list(r) for r in wb[name].iter_rows(values_only=True)] for name in wb.sheetnames
        ]
    finally:
        wb.close()

    result: dict[tuple[str, str], str] = {}

    # Track whether ANY sheet had a usable header.  If none did, we raise
    # at the end — silent fall-through used to copy budget data into the
    # comments column.
    found_any_comment_col = False
    seen_headers: list[str] = []

    for sheet_rows in per_sheet_rows:
        if not sheet_rows:
            continue
        header = [
            str(c).strip().lower().replace("_", " ") if c is not None else "" for c in sheet_rows[0]
        ]
        seen_headers.extend(h for h in header if h)

        # --- Sub-program column -------------------------------------------------
        sp_col: int | None = None
        for i, h in enumerate(header):
            # "sub prog" matches "Sub Prog." and "Sub-Program" (after the
            # underscore-to-space normalisation above).
            if "sub" in h and ("prog" in h or "program" in h):
                sp_col = i
                break
        if sp_col is None:
            sp_col = 0  # safe fallback — first column is almost always sub-program

        # --- Comment column (synonyms) ------------------------------------------
        comment_synonyms = (
            "comment",
            "commentary",
            "note",
            "remark",
            "memo",
        )
        txt_col: int | None = None
        for i, h in enumerate(header):
            if any(syn in h for syn in comment_synonyms):
                txt_col = i
                break
        if txt_col is None:
            # No comment column on THIS sheet — skip it; we'll raise at the
            # bottom only if NO sheet had one.
            continue
        found_any_comment_col = True

        # --- Account column (synonyms) ------------------------------------------
        # Exported workbooks intentionally drop the raw Account column, so
        # if no "account" header is found we fall back to the Title /
        # Description column (col 1).  This matches our own exports
        # without forcing the user to hand-edit headers.
        acc_synonyms = ("account", " gl", "gl code", "code")
        sec_col: int | None = None
        for i, h in enumerate(header):
            if any(syn in h for syn in acc_synonyms):
                sec_col = i
                break
        if sec_col is None:
            # Fall back to Title / Description column — same column used
            # as the second join key when generating the new report.
            sec_col = 1

        # --- Walk rows ----------------------------------------------------------
        for row in sheet_rows[1:]:
            if not row:
                continue
            sp = str(row[sp_col]).strip() if sp_col < len(row) and row[sp_col] is not None else ""
            sec = (
                str(row[sec_col]).strip() if sec_col < len(row) and row[sec_col] is not None else ""
            )
            txt = (
                str(row[txt_col]).strip() if txt_col < len(row) and row[txt_col] is not None else ""
            )
            # Skip rows that are clearly not data — sub-program codes are
            # purely numeric.  This stops "Total" / blank header artefacts
            # from polluting the dict.
            if not sp or not sp.isdigit():
                continue
            if sp or sec:
                # If two sheets disagree on the same key, the later one
                # wins — matches the visual reading order in the workbook.
                result[(sp, sec)] = txt

    if not found_any_comment_col:
        seen = ", ".join(sorted(set(h for h in seen_headers if h))) or "(none)"
        raise ValueError(
            "Could not find a comments column in the prior-period file. "
            "Looked for any header containing one of: "
            f"{', '.join(comment_synonyms)}. "
            f"Headers we found: {seen}. "
            "Rename your comments column to 'Comments' (or one of the "
            "synonyms above) and try again."
        )

    return result


# ---------------------------------------------------------------------------
# XLSX output writer
# ---------------------------------------------------------------------------

# Excel Accounting format -- matches the Jan26 reference file exactly.
_ACCOUNTING_FMT = '_-"$"* #,##0_-;\\-"$"* #,##0_-;_-"$"* "-"??_-;_-@_-'
_PERCENT_FMT = "0.00"
_TITLE_FONT = Font(bold=True, size=14)
# Green data bar colour -- matches Jan26 reference (#63C384 with full alpha).
_DATA_BAR_COLOR = "FF63C384"

# Revenue sheet: 8 columns -- no Outstanding Orders column.
_REV_HEADERS = [
    "Sub Prog.",
    "Title",
    "Last year actual",
    "Last year budget",
    "Annual budget",
    "YTD",
    "% Budget received",
    "Comments",
]
_REV_WIDTHS = [10, 43, 13, 14, 17, 15, 13, 60]

# Expenditure sheet: 9 columns -- Outstanding Orders is parsed from the PDF
# and used in the Uncommitted Balance computation (Annual - YTD - Outstanding)
# but NOT displayed as its own column, per user's Q3 spec direction.
_EXP_HEADERS = [
    "Sub Prog.",
    "Title",
    "Last year actual",
    "Last year budget",
    "Annual budget",
    "YTD",
    "% Budget Expended",
    "Uncommitted Balance",
    "Comments",
]
_EXP_WIDTHS = [10, 43, 13, 14, 17, 15, 14, 18, 60]


def _recompute_is_over(
    lines: list[SubProgramLine],
    threshold: float,
    *,
    revenue_threshold: float | None = None,
    expense_threshold: float | None = None,
) -> list[SubProgramLine]:
    """Return new SubProgramLine list with is_over recomputed.

    By default both Revenue and Expenditure rows use the same ``threshold``,
    which preserves backward compatibility with all earlier callers.
    Round 21 added the optional ``revenue_threshold`` / ``expense_threshold``
    keyword-only parameters.  When supplied, a Revenue line is flagged as
    over-budget if ``used_pct > revenue_threshold`` and an Expenditure line
    if ``used_pct > expense_threshold``.  This lets users tolerate a
    different "noise" margin on income lines (where over-collecting is
    usually fine) versus expenditure lines (where over-running matters).

    A line is over-budget when its used_pct exceeds the relevant threshold
    (default 101.0).  This replaces the raw ``ytd > budget`` check done by
    the parser so the user-supplied value is honoured in both the XLSX
    fills and the in-app table highlights.
    """
    from dataclasses import replace as _replace

    rev_th = revenue_threshold if revenue_threshold is not None else threshold
    exp_th = expense_threshold if expense_threshold is not None else threshold

    result: list[SubProgramLine] = []
    for ln in lines:
        # Pick the threshold by section.  Account values are always
        # "Revenue" or "Expenditure" (or close variants) — we lower-case
        # and compare prefixes to be tolerant of typos.
        is_revenue = ln.account.lower().startswith("revenue")
        section_th = rev_th if is_revenue else exp_th
        new_is_over = float(ln.used_pct) > section_th
        if new_is_over != ln.is_over:
            ln = _replace(ln, is_over=new_is_over)
        result.append(ln)
    return result


def _write_sheet(
    ws: Any,
    title: str,
    headers: list[str],
    widths: list[int],
    lines: list[SubProgramLine],
    is_revenue: bool,
) -> None:
    """Populate a single Revenue or Expenditure worksheet."""
    from openpyxl.formatting.rule import DataBarRule
    from openpyxl.worksheet.worksheet import Worksheet

    assert isinstance(ws, Worksheet)
    n_cols = len(headers)

    # Row 1: merged title -- bold, size 14, centred.
    title_cell = ws.cell(row=1, column=1, value=title)
    title_cell.font = _TITLE_FONT
    title_cell.alignment = Alignment(horizontal="center")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n_cols)

    # Row 2: column headers.
    for col_idx, header in enumerate(headers, start=1):
        ws.cell(row=2, column=col_idx, value=header).alignment = Alignment(
            horizontal="left", wrap_text=True
        )

    # Freeze panes so title + header row both stay visible.
    ws.freeze_panes = "A3"

    # Column widths.
    for col_idx, width in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = width

    # Data rows start at row 3.
    percent_col = 7
    for row_idx, line in enumerate(lines, start=3):
        if is_revenue:
            row_values: list[Any] = [
                line.sub_program,
                line.description,
                float(line.last_year_actual),
                float(line.last_year_budget),
                float(line.budget),
                float(line.ytd),
                float(line.used_pct),
                line.commentary,
            ]
            # Accounting format on Annual budget (col 5) and YTD (col 6).
            currency_cols = {5, 6}
        else:
            # Uncommitted Balance = Annual budget - YTD - Outstanding Orders.
            # Outstanding Orders is parsed from the PDF but not surfaced as a
            # column (per user spec Q3); it only contributes to this derivation.
            uncommitted = line.budget - line.ytd - line.outstanding_orders
            row_values = [
                line.sub_program,
                line.description,
                float(line.last_year_actual),
                float(line.last_year_budget),
                float(line.budget),
                float(line.ytd),
                float(line.used_pct),
                float(uncommitted),
                line.commentary,
            ]
            # Accounting format on Annual budget (col 5), YTD (col 6).
            currency_cols = {5, 6}

        for col_idx, val in enumerate(row_values, start=1):
            c = ws.cell(row=row_idx, column=col_idx, value=val)
            if col_idx in currency_cols:
                c.number_format = _ACCOUNTING_FMT
            elif col_idx == percent_col:
                c.number_format = _PERCENT_FMT
            # Pink row fill for over-budget rows (threshold-aware is_over).
            if line.is_over:
                c.fill = _OVER_FILL

    # Conditional formatting on the % Budget column (G = col 7).
    if lines:
        last_data_row = 2 + len(lines)
        pct_col_letter = get_column_letter(percent_col)
        rng = f"{pct_col_letter}3:{pct_col_letter}{last_data_row}"

        # Data bar: green, 0--110 (matches Revenue sheet in Jan26 reference).
        ws.conditional_formatting.add(
            rng,
            DataBarRule(  # type: ignore[no-untyped-call]
                start_type="num",
                start_value=0,
                end_type="num",
                end_value=110,
                color=_DATA_BAR_COLOR,
                showValue=True,
            ),
        )


def _sheet_title(base: str, period_label: str, suffix: str) -> str:
    """Compose a sheet title, gracefully omitting the period when absent."""
    if period_label:
        return f"{base} - {period_label} {suffix}"
    return f"{base} - {suffix}"


def _write_xlsx(
    lines: list[SubProgramLine],
    output_file: Path,
    period_label: str = "",
    over_budget_threshold: float = 101.0,
) -> None:
    """Write the report to an XLSX with separate Revenue and Expenditure sheets.

    Rows where ``line.is_over`` is True (i.e. ``used_pct > over_budget_threshold``)
    receive a pink HL_MISMATCH row fill (``_OVER_FILL``) across every cell.
    The data bar conditional formatting on the % Budget column is independent
    of the threshold and always applied.
    """
    from openpyxl import Workbook

    wb = Workbook()
    # Remove the default sheet openpyxl creates.
    default_ws = wb.active
    if default_ws is not None:
        wb.remove(default_ws)

    revenue_lines = [ln for ln in lines if ln.account.lower().startswith("revenue")]
    expenditure_lines = [ln for ln in lines if ln.account.lower().startswith("expenditure")]

    base = "Annual Sub-Program Budget Report"

    rev_ws = wb.create_sheet("Revenue")
    _write_sheet(
        ws=rev_ws,
        title=_sheet_title(base, period_label, "Revenue"),
        headers=_REV_HEADERS,
        widths=_REV_WIDTHS,
        lines=revenue_lines,
        is_revenue=True,
    )

    exp_ws = wb.create_sheet("Expenditure")
    _write_sheet(
        ws=exp_ws,
        title=_sheet_title(base, period_label, "Expenditure"),
        headers=_EXP_HEADERS,
        widths=_EXP_WIDTHS,
        lines=expenditure_lines,
        is_revenue=False,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_file)


# ---------------------------------------------------------------------------
# Public API -- generate_report
# ---------------------------------------------------------------------------


def generate_report(
    report_file: Path,
    comments_file: Path | None,
    output_file: Path,
    progress: ProgressFn,
    over_budget_threshold: float = 101.0,
    write_xlsx: bool = True,
    *,
    revenue_threshold: float | None = None,
    expense_threshold: float | None = None,
) -> ReportSummary:
    """Orchestrate parse + comment join + optional XLSX write.

    Parameters
    ----------
    report_file:
        CASES21 GL21157 PDF (or XLSX fallback).
    comments_file:
        Optional prior-period commentary workbook.
    output_file:
        Destination ``.xlsx`` path (used only when ``write_xlsx=True``).
    progress:
        Callback ``(percent: int, message: str) -> None``.
    over_budget_threshold:
        Combined threshold applied to BOTH Revenue and Expenditure when
        the per-section overrides below are not supplied.  Kept for
        backward compatibility with all earlier callers.
    revenue_threshold, expense_threshold:
        Round 21 — optional per-section thresholds.  When supplied they
        override ``over_budget_threshold`` for that section.  Schools
        often want a different tolerance on Revenue (over-collecting
        is rarely a problem) than on Expenditure (over-running is the
        whole point of the report).
    write_xlsx:
        When True (default), write the XLSX workbook to ``output_file``.
        Pass False to skip the write step (e.g. for the preview-then-export
        two-phase flow in Sub-Program tool v2).
    """
    rev_th = revenue_threshold if revenue_threshold is not None else over_budget_threshold
    exp_th = expense_threshold if expense_threshold is not None else over_budget_threshold
    progress(10, "Reading PDF…")

    period_label = ""
    suffix = report_file.suffix.lower()
    if suffix == ".pdf":
        lines, period_label = parse_sub_program_pdf_with_period(report_file)
    elif suffix in {".xlsx", ".xlsm"}:
        lines = parse_sub_program_xlsx(report_file)
    else:
        raise ValueError(
            f"Unsupported report file format: {suffix!r}. Please supply a .pdf or .xlsx file."
        )

    progress(40, "Joining commentary…")

    comments: dict[tuple[str, str], str] = {}
    if comments_file is not None:
        comments = load_prior_period_comments(comments_file)

    # Attach commentary and finalise lines.
    #
    # Round 21 fix — the prior-period file might have been keyed on
    # account code OR on title/description, depending on which columns
    # the user's file carried.  Try account first (canonical, used by
    # CASES21 raw exports), then fall back to description (used by our
    # own exports because we drop the raw account column).
    final_lines: list[SubProgramLine] = []
    for ln in lines:
        commentary = comments.get((ln.sub_program, ln.account), "")
        if not commentary:
            commentary = comments.get((ln.sub_program, ln.description), "")
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
                last_year_actual=ln.last_year_actual,
                last_year_budget=ln.last_year_budget,
                outstanding_orders=ln.outstanding_orders,
            )
        final_lines.append(ln)

    # Apply threshold: recompute is_over using used_pct > threshold so the
    # user-supplied value is respected in both the XLSX fills and the in-app
    # table highlights.  The parser sets a preliminary is_over based on
    # ytd > budget; this call replaces it with the threshold-aware version.
    # Round 21 — pass per-section thresholds so Revenue and Expenditure
    # rows are flagged independently.
    final_lines = _recompute_is_over(
        final_lines,
        over_budget_threshold,
        revenue_threshold=rev_th,
        expense_threshold=exp_th,
    )

    if write_xlsx:
        progress(70, "Writing workbook…")
        _write_xlsx(
            final_lines,
            output_file,
            period_label=period_label,
            over_budget_threshold=over_budget_threshold,
        )
    else:
        progress(70, "Preparing preview…")

    # Build summary
    faculty_counts: dict[str, int] = {}
    faculty_budget: dict[str, Decimal] = {}
    faculty_ytd: dict[str, Decimal] = {}
    for ln in final_lines:
        key = ln.faculty or "Unknown"
        faculty_counts[key] = faculty_counts.get(key, 0) + 1
        faculty_budget[key] = faculty_budget.get(key, Decimal("0")) + ln.budget
        faculty_ytd[key] = faculty_ytd.get(key, Decimal("0")) + ln.ytd

    # Per-faculty used %, computed from totals (NOT averaged from row %s).
    faculty_used_pct: dict[str, Decimal] = {
        k: (faculty_ytd[k] / faculty_budget[k] * Decimal("100"))
        if faculty_budget[k] != Decimal("0")
        else Decimal("0")
        for k in faculty_counts
    }

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
        faculty_budget=faculty_budget,
        faculty_ytd=faculty_ytd,
        faculty_used_pct=faculty_used_pct,
        period_label=period_label,
        over_budget_threshold=over_budget_threshold,
        revenue_threshold=rev_th,
        expense_threshold=exp_th,
    )
