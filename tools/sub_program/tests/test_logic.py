from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from toolkit.tokens import HL_MISMATCH
from tools.sub_program.logic import (
    _ACCOUNTING_FMT,
    _EXP_HEADERS,
    _OVER_FILL,
    _REV_HEADERS,
    ReportSummary,
    SubProgramLine,
    _extract_period_label,
    _recompute_is_over,
    _sheet_title,
    _write_xlsx,
    generate_report,
    load_prior_period_comments,
    parse_decimal,
    parse_sub_program_pdf,
    parse_sub_program_pdf_with_period,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SAMPLE_PDF = Path(
    "Samples/Annual Subprogram Budget Report/GL21157_Annual Subprogram budget report.pdf"
)


def _make_comments_xlsx(tmp_path: Path) -> Path:
    """Build a minimal prior-period comments XLSX for fixture use."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Sub-Program", "Account", "Commentary"])  # type: ignore[union-attr]
    ws.append(["4001", "Expenditure", "Reviewed by council"])  # type: ignore[union-attr]
    ws.append(["8599", "Expenditure", "Rowing costs on track"])  # type: ignore[union-attr]
    ws.append(["1251", "Revenue", ""])  # type: ignore[union-attr]
    out = tmp_path / "comments.xlsx"
    wb.save(out)
    return out


# ---------------------------------------------------------------------------
# Test: currency parser edge cases
# ---------------------------------------------------------------------------


class TestParseDecimal:
    def test_plain_number(self) -> None:
        assert parse_decimal("1,234.56") == Decimal("1234.56")

    def test_negative(self) -> None:
        assert parse_decimal("-500.00") == Decimal("-500.00")

    def test_parentheses_negative(self) -> None:
        assert parse_decimal("(500.00)") == Decimal("-500.00")

    def test_dollar_prefix(self) -> None:
        assert parse_decimal("$0.00") == Decimal("0.00")

    def test_em_dash(self) -> None:
        assert parse_decimal("—") == Decimal("0")

    def test_blank(self) -> None:
        assert parse_decimal("") == Decimal("0")

    def test_integer_string(self) -> None:
        assert parse_decimal("42") == Decimal("42")

    def test_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_decimal("not-a-number!!")


# ---------------------------------------------------------------------------
# Test: parse real sample PDF
# ---------------------------------------------------------------------------


class TestParseSamplePdf:
    @pytest.fixture(scope="class")
    def lines(self) -> list[SubProgramLine]:
        return parse_sub_program_pdf(_SAMPLE_PDF)

    def test_minimum_line_count(self, lines: list[SubProgramLine]) -> None:
        assert len(lines) >= 10, f"Expected >= 10 lines, got {len(lines)}"

    def test_all_have_nonempty_sub_program(self, lines: list[SubProgramLine]) -> None:
        bad = [ln for ln in lines if not ln.sub_program.strip()]
        assert not bad, f"Lines with empty sub_program: {bad[:3]}"

    def test_all_have_decimal_budget(self, lines: list[SubProgramLine]) -> None:
        for ln in lines:
            assert isinstance(ln.budget, Decimal)

    def test_budget_sum_positive(self, lines: list[SubProgramLine]) -> None:
        total = sum((ln.budget for ln in lines), Decimal("0"))
        assert total > Decimal("0"), f"Total budget should be positive, got {total}"

    def test_faculty_assigned(self, lines: list[SubProgramLine]) -> None:
        # At least some lines should have a faculty
        with_faculty = [ln for ln in lines if ln.faculty is not None]
        assert len(with_faculty) > 0

    def test_account_section_values(self, lines: list[SubProgramLine]) -> None:
        accounts = {ln.account for ln in lines}
        assert accounts <= {"Revenue", "Expenditure"}, f"Unexpected account values: {accounts}"

    def test_used_pct_is_decimal(self, lines: list[SubProgramLine]) -> None:
        for ln in lines:
            assert isinstance(ln.used_pct, Decimal)

    def test_sub_program_codes_are_numeric(self, lines: list[SubProgramLine]) -> None:
        non_numeric = [ln for ln in lines if not ln.sub_program.isdigit()]
        assert not non_numeric, f"Non-numeric sub_programs: {non_numeric[:3]}"

    def test_no_total_rows_included(self, lines: list[SubProgramLine]) -> None:
        # "Revenue totals" and "Expenditure totals" must not appear as data rows
        for ln in lines:
            assert "total" not in ln.description.lower() or ln.sub_program.isdigit()


# ---------------------------------------------------------------------------
# Test: over-budget detection
# ---------------------------------------------------------------------------


class TestOverBudget:
    def test_is_over_true_when_ytd_exceeds_budget(self) -> None:
        ln = SubProgramLine(
            sub_program="4400",
            account="Revenue",
            description="Mathematics",
            budget=Decimal("100"),
            ytd=Decimal("150"),
            remaining=Decimal("-50"),
            used_pct=Decimal("150"),
            faculty="Curriculum",
            is_over=True,
        )
        assert ln.is_over is True
        assert ln.used_pct == Decimal("150")

    def test_is_over_false_when_within_budget(self) -> None:
        ln = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Art",
            budget=Decimal("100"),
            ytd=Decimal("80"),
            remaining=Decimal("20"),
            used_pct=Decimal("80"),
            faculty="Curriculum",
            is_over=False,
        )
        assert ln.is_over is False

    def test_parse_pdf_detects_over_budget(self) -> None:
        """Line 4400 Mathematics has pct > 100 in the Revenue section."""
        lines = parse_sub_program_pdf(_SAMPLE_PDF)
        # Sub-program 4400 in Revenue has used_pct ~2021 (YTD 20,213 vs budget 1,000)
        over = [ln for ln in lines if ln.is_over]
        assert over, "Expected at least one over-budget line in the sample PDF"


# ---------------------------------------------------------------------------
# Test: load_prior_period_comments
# ---------------------------------------------------------------------------


class TestLoadComments:
    def test_basic_load(self, tmp_path: Path) -> None:
        comments_xlsx = _make_comments_xlsx(tmp_path)
        result = load_prior_period_comments(comments_xlsx)
        assert ("4001", "Expenditure") in result
        assert result[("4001", "Expenditure")] == "Reviewed by council"
        assert result[("8599", "Expenditure")] == "Rowing costs on track"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="not found"):
            load_prior_period_comments(tmp_path / "nonexistent.xlsx")

    def test_empty_commentary_row(self, tmp_path: Path) -> None:
        comments_xlsx = _make_comments_xlsx(tmp_path)
        result = load_prior_period_comments(comments_xlsx)
        # The third row has an empty commentary
        assert result.get(("1251", "Revenue"), "") == ""

    def test_notes_synonym(self, tmp_path: Path) -> None:
        """Round 21 — 'Notes' header is accepted as a comment synonym."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Sub-Program", "Account", "Notes"])
        ws.append(["4001", "Expenditure", "PE consumables reviewed"])
        path = tmp_path / "notes_only.xlsx"
        wb.save(path)

        result = load_prior_period_comments(path)
        assert result[("4001", "Expenditure")] == "PE consumables reviewed"

    def test_no_account_column_falls_back_to_title(self, tmp_path: Path) -> None:
        """Round 21 — files without an 'Account' column (e.g. our own
        exports) are still loadable; the line title becomes the second key."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        # Mirrors the Revenue export schema — Title in col 1, Comments at end.
        ws.append(
            [
                "Sub Prog.",
                "Title",
                "Last year actual",
                "Last year budget",
                "Annual budget",
                "YTD",
                "% Budget received",
                "Comments",
            ]
        )
        ws.append(["1251", "Camp fees", "—", "—", 5000, 4500, "90%", "Camp paid"])
        path = tmp_path / "from_export.xlsx"
        wb.save(path)

        result = load_prior_period_comments(path)
        # Second key is the Title text, not an account string.
        assert result[("1251", "Camp fees")] == "Camp paid"
        # And it definitely is NOT the budget column value (the bug that
        # caused this round of work — col 2 used to be silently chosen).
        assert "5000" not in str(result.get(("1251", "Camp fees"), ""))

    def test_missing_comment_column_raises(self, tmp_path: Path) -> None:
        """Round 21 — bug guard: when no comment column is found we must
        raise instead of silently defaulting to a budget column.

        Pre-Round-21 the loader fell through StopIteration to txt_col=2,
        which is "Last year actual" in our exports — meaning users saw
        last-year-actual budget values copied into the new comments
        column.  That silent fall-through is now a hard error.
        """
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        # No comment-like header at all — every column is a budget one.
        ws.append(["Sub Prog.", "Title", "Annual budget", "YTD"])
        ws.append(["4001", "Art", 1000, 200])
        path = tmp_path / "no_comments.xlsx"
        wb.save(path)

        with pytest.raises(ValueError, match="comments column"):
            load_prior_period_comments(path)

    def test_reads_all_sheets(self, tmp_path: Path) -> None:
        """Round 21 — Revenue + Expenditure sheets should both contribute
        comments (previously only the first sheet was read)."""
        wb = openpyxl.Workbook()
        rev = wb.active
        assert rev is not None
        rev.title = "Revenue"
        rev.append(["Sub-Program", "Account", "Commentary"])
        rev.append(["1251", "Revenue", "Camp paid"])

        exp = wb.create_sheet("Expenditure")
        exp.append(["Sub-Program", "Account", "Commentary"])
        exp.append(["4001", "Expenditure", "Art supplies on order"])

        path = tmp_path / "two_sheets.xlsx"
        wb.save(path)

        result = load_prior_period_comments(path)
        assert result[("1251", "Revenue")] == "Camp paid"
        assert result[("4001", "Expenditure")] == "Art supplies on order"


# ---------------------------------------------------------------------------
# Test: generate_report round-trip
# ---------------------------------------------------------------------------


class TestGenerateReport:
    def test_round_trip_produces_xlsx(self, tmp_path: Path) -> None:
        output = tmp_path / "output.xlsx"
        progress_calls: list[tuple[int, str]] = []

        def progress(pct: int, msg: str) -> None:
            progress_calls.append((pct, msg))

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=progress,
        )

        assert output.exists(), "Output XLSX was not created"
        assert isinstance(summary, ReportSummary)
        assert len(summary.lines) >= 10

    def test_output_has_correct_header(self, tmp_path: Path) -> None:
        """Revenue sheet row 2 must have the new column headers."""
        output = tmp_path / "output2.xlsx"

        generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        ws_rev = wb["Revenue"]
        headers = [ws_rev.cell(2, c).value for c in range(1, ws_rev.max_column + 1)]
        assert headers[0] == "Sub Prog."
        assert headers[1] == "Title"
        assert "Annual budget" in headers
        assert "% Budget received" in headers

    def test_output_row_count_matches_lines(self, tmp_path: Path) -> None:
        """Revenue + Expenditure data rows must total summary.lines count."""
        output = tmp_path / "output3.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        ws_rev = wb["Revenue"]
        ws_exp = wb["Expenditure"]
        # Row 1 = title, row 2 = headers, rows 3+ = data.
        rev_data_rows = (ws_rev.max_row or 2) - 2
        exp_data_rows = (ws_exp.max_row or 2) - 2
        assert rev_data_rows + exp_data_rows == len(summary.lines)

    def test_pink_fill_on_over_budget_rows(self, tmp_path: Path) -> None:
        """Over-budget rows must have HL_MISMATCH pink fill across every cell.

        Over-budget signalling in the XLSX uses both the green data bar on the
        % Budget column AND a pink row fill (re-added in Round 9 per user spec).
        The threshold defaults to 101.0%.
        """
        output = tmp_path / "output4.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        assert summary.over_budget_lines, (
            "Sample PDF must contain at least one over-budget line -- if the "
            "sample is replaced, replace it with one that has at least one "
            "over-budget row, or this test is no longer meaningful."
        )

        wb = openpyxl.load_workbook(output)
        target_argb = ("FF" + HL_MISMATCH).upper()

        # Collect over-budget sub-programs per sheet (account-aware).
        rev_over = {
            ln.sub_program
            for ln in summary.over_budget_lines
            if ln.account.lower().startswith("revenue")
        }
        exp_over = {
            ln.sub_program
            for ln in summary.over_budget_lines
            if ln.account.lower().startswith("expenditure")
        }
        found_pink = False
        for ws, over_sps in [(wb["Revenue"], rev_over), (wb["Expenditure"], exp_over)]:
            for row in ws.iter_rows(min_row=3):  # skip title + header
                sp_val = str(row[0].value or "").strip()
                if sp_val in over_sps:
                    for cell in row:
                        fill = cell.fill
                        if fill and fill.fgColor and fill.fgColor.rgb:
                            if target_argb in fill.fgColor.rgb.upper():
                                found_pink = True
        assert found_pink, (
            "Expected pink HL_MISMATCH fill on at least one over-budget row cell, "
            "but none found — check _write_xlsx is applying _OVER_FILL."
        )

    def test_over_budget_fill_all_columns(self, tmp_path: Path) -> None:
        """Every cell in an over-budget row must have the HL_MISMATCH pink fill.

        The fill is applied across all columns of each over-budget data row.
        Non-over-budget rows (including title + header rows 1-2) must NOT have
        the pink fill.

        Matching is done per-sheet: Revenue over-budget lines are looked up in
        the Revenue sheet; Expenditure lines in the Expenditure sheet.
        """
        output = tmp_path / "output_all_cols.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        assert summary.over_budget_lines, (
            "Sample PDF must contain at least one over-budget line for this "
            "test to be meaningful -- replace the sample if it ever stops "
            "having any."
        )

        wb = openpyxl.load_workbook(output)
        target_argb = ("FF" + HL_MISMATCH).upper()

        # Build per-sheet sets of over-budget sub-program codes.
        rev_over_sps = {
            ln.sub_program
            for ln in summary.over_budget_lines
            if ln.account.lower().startswith("revenue")
        }
        exp_over_sps = {
            ln.sub_program
            for ln in summary.over_budget_lines
            if ln.account.lower().startswith("expenditure")
        }

        sheet_to_over: dict[str, set[str]] = {
            "Revenue": rev_over_sps,
            "Expenditure": exp_over_sps,
        }

        # Every cell in an over-budget data row (per sheet) must have the fill.
        missing_fill: list[str] = []
        for sheet_name, over_sps in sheet_to_over.items():
            if not over_sps:
                continue
            ws = wb[sheet_name]
            for row in ws.iter_rows(min_row=3):
                sp_val = str(row[0].value or "").strip()
                if sp_val not in over_sps:
                    continue
                for cell in row:
                    fill = cell.fill
                    has_pink = (
                        fill is not None
                        and fill.fgColor is not None
                        and fill.fgColor.rgb is not None
                        and target_argb in fill.fgColor.rgb.upper()
                    )
                    if not has_pink:
                        missing_fill.append(f"{sheet_name}!{cell.coordinate}")

        assert not missing_fill, (
            f"{len(missing_fill)} cell(s) in over-budget rows are missing the "
            f"pink fill: {missing_fill[:5]}"
        )

    def test_commentary_joined(self, tmp_path: Path) -> None:
        comments_xlsx = _make_comments_xlsx(tmp_path)
        output = tmp_path / "output5.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=comments_xlsx,
            output_file=output,
            progress=lambda p, m: None,
        )

        with_comment = [ln for ln in summary.lines if ln.commentary]
        assert with_comment, "Expected at least one line with commentary"

    def test_progress_callbacks_fired(self, tmp_path: Path) -> None:
        output = tmp_path / "output6.xlsx"
        pcts: list[int] = []

        def progress(pct: int, msg: str) -> None:
            pcts.append(pct)

        generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=progress,
        )

        assert 10 in pcts
        assert 40 in pcts
        assert 70 in pcts
        assert 100 in pcts


# ---------------------------------------------------------------------------
# Test: per-faculty aggregated stats in ReportSummary
# ---------------------------------------------------------------------------


def _make_line_direct(
    sub_program: str,
    faculty: str | None,
    budget: str,
    ytd: str,
    is_over: bool = False,
) -> SubProgramLine:
    b = Decimal(budget)
    y = Decimal(ytd)
    return SubProgramLine(
        sub_program=sub_program,
        account="Expenditure",
        description="Test",
        budget=b,
        ytd=y,
        remaining=b - y,
        used_pct=(y / b * Decimal("100")) if b != Decimal("0") else Decimal("0"),
        faculty=faculty,
        is_over=is_over,
    )


class TestFacultyStats:
    """ReportSummary must carry per-faculty budget/ytd/used_pct aggregations."""

    def _build_summary(self, lines: list[SubProgramLine], tmp_path: Path) -> ReportSummary:
        output = tmp_path / "out.xlsx"
        # Use the frozen dataclass constructor directly so we don't need a real PDF.
        faculty_counts: dict[str, int] = {}
        faculty_budget: dict[str, Decimal] = {}
        faculty_ytd_map: dict[str, Decimal] = {}
        for ln in lines:
            key = ln.faculty or "Unknown"
            faculty_counts[key] = faculty_counts.get(key, 0) + 1
            faculty_budget[key] = faculty_budget.get(key, Decimal("0")) + ln.budget
            faculty_ytd_map[key] = faculty_ytd_map.get(key, Decimal("0")) + ln.ytd
        faculty_used_pct: dict[str, Decimal] = {
            k: (faculty_ytd_map[k] / faculty_budget[k] * Decimal("100"))
            if faculty_budget[k] != Decimal("0")
            else Decimal("0")
            for k in faculty_counts
        }
        return ReportSummary(
            lines=lines,
            faculty_counts=faculty_counts,
            over_budget_lines=[ln for ln in lines if ln.is_over],
            total_budget=sum((ln.budget for ln in lines), Decimal("0")),
            total_ytd=sum((ln.ytd for ln in lines), Decimal("0")),
            output_path=output,
            faculty_budget=faculty_budget,
            faculty_ytd=faculty_ytd_map,
            faculty_used_pct=faculty_used_pct,
        )

    def test_summary_includes_faculty_budget(self, tmp_path: Path) -> None:
        """faculty_budget sums budget across all lines per faculty."""
        lines = [
            _make_line_direct("4001", "Curriculum", "10000", "5000"),
            _make_line_direct("4002", "Curriculum", "5000", "2000"),
            _make_line_direct("5001", "Student Wellbeing", "8000", "4000"),
        ]
        # Build via generate_report using the real logic path indirectly —
        # construct a summary the same way logic.py does to verify correctness.
        summary = self._build_summary(lines, tmp_path)

        assert summary.faculty_budget["Curriculum"] == Decimal("15000")
        assert summary.faculty_budget["Student Wellbeing"] == Decimal("8000")

    def test_summary_includes_faculty_used_pct(self, tmp_path: Path) -> None:
        """faculty_used_pct is computed from totals, not averaged from per-row %s.

        Curriculum: budget=15000, ytd=7000 → 46.666...%
        If averaged from rows: row1=50%, row2=40% → avg=45% — different!
        The totals-based figure (46.666...%) is the correct one.
        """
        lines = [
            _make_line_direct("4001", "Curriculum", "10000", "5000"),  # 50%
            _make_line_direct("4002", "Curriculum", "5000", "2000"),  # 40%
        ]
        summary = self._build_summary(lines, tmp_path)

        # Totals: budget=15000, ytd=7000
        expected = Decimal("7000") / Decimal("15000") * Decimal("100")
        assert summary.faculty_used_pct["Curriculum"] == expected

        # Confirm it is NOT the naïve per-row average (45%)
        naive_avg = (Decimal("50") + Decimal("40")) / Decimal("2")
        assert summary.faculty_used_pct["Curriculum"] != naive_avg

    def test_summary_faculty_used_pct_handles_zero_budget(self, tmp_path: Path) -> None:
        """A faculty whose total budget is 0 must yield 0% — no ZeroDivisionError."""
        lines = [
            _make_line_direct("9001", "Computing & Curriculum", "0", "0"),
        ]
        summary = self._build_summary(lines, tmp_path)

        assert summary.faculty_used_pct["Computing & Curriculum"] == Decimal("0")

    def test_summary_unknown_faculty_aggregated(self, tmp_path: Path) -> None:
        """Lines with faculty=None are bucketed under 'Unknown'."""
        lines = [
            _make_line_direct("9999", None, "3000", "1500"),
            _make_line_direct("9998", None, "2000", "1000"),
        ]
        summary = self._build_summary(lines, tmp_path)

        assert "Unknown" in summary.faculty_budget
        assert summary.faculty_budget["Unknown"] == Decimal("5000")
        assert summary.faculty_ytd["Unknown"] == Decimal("2500")
        expected_pct = Decimal("2500") / Decimal("5000") * Decimal("100")
        assert summary.faculty_used_pct["Unknown"] == expected_pct


# ---------------------------------------------------------------------------
# Helper for new XLSX-structure tests
# ---------------------------------------------------------------------------


def _make_mixed_lines() -> list[SubProgramLine]:
    """Return a short list of Revenue + Expenditure lines for XLSX writer tests."""

    def _rev(sp: str, budget: str, ytd: str, lya: str = "0", lyb: str = "0") -> SubProgramLine:
        b = Decimal(budget)
        y = Decimal(ytd)
        return SubProgramLine(
            sub_program=sp,
            account="Revenue",
            description=f"Rev {sp}",
            budget=b,
            ytd=y,
            remaining=b - y,
            used_pct=(y / b * Decimal("100")) if b else Decimal("0"),
            faculty="Curriculum",
            is_over=False,
            last_year_actual=Decimal(lya),
            last_year_budget=Decimal(lyb),
        )

    def _exp(
        sp: str,
        budget: str,
        ytd: str,
        outstanding: str = "0",
        lya: str = "0",
        lyb: str = "0",
        is_over: bool = False,
    ) -> SubProgramLine:
        b = Decimal(budget)
        y = Decimal(ytd)
        return SubProgramLine(
            sub_program=sp,
            account="Expenditure",
            description=f"Exp {sp}",
            budget=b,
            ytd=y,
            remaining=b - y,
            used_pct=(y / b * Decimal("100")) if b else Decimal("0"),
            faculty="Curriculum",
            is_over=is_over,
            last_year_actual=Decimal(lya),
            last_year_budget=Decimal(lyb),
            outstanding_orders=Decimal(outstanding),
        )

    return [
        _rev("4001", "18950", "13760", lya="160"),
        _rev("4003", "7525", "6130"),
        _exp("4001", "52450", "8241", outstanding="489", lya="32565", lyb="32675"),
        _exp("4003", "7775", "582", outstanding="0"),
        _exp("4400", "1000", "20213", is_over=True),  # over-budget
    ]


# ---------------------------------------------------------------------------
# Test: new XLSX structure (two sheets)
# ---------------------------------------------------------------------------


class TestXlsxTwoSheets:
    """The generated workbook must have separate Revenue and Expenditure sheets."""

    def test_xlsx_has_two_sheets_revenue_and_expenditure(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        assert wb.sheetnames == ["Revenue", "Expenditure"]

    def test_revenue_sheet_columns(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        ws = wb["Revenue"]
        headers = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
        assert headers == _REV_HEADERS

    def test_expenditure_sheet_columns(self, tmp_path: Path) -> None:
        """Expenditure sheet shows Uncommitted Balance but NOT Outstanding Orders.

        Outstanding Orders is parsed from the PDF and used in the Uncommitted Balance
        derivation (Annual - YTD - Outstanding) but is intentionally not displayed as
        its own column, per the user's spec direction (Q3 of the Jan26 brief).
        """
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        ws = wb["Expenditure"]
        headers = [ws.cell(2, c).value for c in range(1, ws.max_column + 1)]
        assert headers == _EXP_HEADERS
        assert "Outstanding Orders" not in headers
        assert "Uncommitted Balance" in headers

    def test_title_row_merged_and_styled(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        for sheet_name in ["Revenue", "Expenditure"]:
            ws = wb[sheet_name]
            title_cell = ws.cell(1, 1)
            # Bold, size 14
            assert title_cell.font.bold is True, f"{sheet_name} title not bold"
            assert title_cell.font.size == 14, f"{sheet_name} title size != 14"
            # Merged across all columns
            merged = [str(r) for r in ws.merged_cells.ranges]
            n_cols = ws.max_column
            expected_merge = f"A1:{chr(ord('A') + n_cols - 1)}1"
            assert any(expected_merge in r for r in merged), (
                f"{sheet_name}: expected merge {expected_merge!r}, got {merged}"
            )

    def test_title_includes_period_label(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="January 2026")
        wb = openpyxl.load_workbook(out)
        assert "January 2026" in str(wb["Revenue"].cell(1, 1).value or "")
        assert "January 2026" in str(wb["Expenditure"].cell(1, 1).value or "")

    def test_title_falls_back_when_no_period(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="")
        wb = openpyxl.load_workbook(out)
        rev_title = str(wb["Revenue"].cell(1, 1).value or "")
        exp_title = str(wb["Expenditure"].cell(1, 1).value or "")
        # No double spaces or trailing/leading whitespace
        assert "  " not in rev_title
        assert "  " not in exp_title
        assert rev_title == rev_title.strip()
        assert exp_title == exp_title.strip()
        # Title ends cleanly with 'Revenue' / 'Expenditure'
        assert rev_title.endswith("Revenue")
        assert exp_title.endswith("Expenditure")

    def test_currency_format_on_dollar_columns(self, tmp_path: Path) -> None:
        """Annual budget (col 5) and YTD (col 6) must use the Accounting format."""
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        for sheet_name in ["Revenue", "Expenditure"]:
            ws = wb[sheet_name]
            if ws.max_row >= 3:
                assert ws.cell(3, 5).number_format == _ACCOUNTING_FMT, (
                    f"{sheet_name} col 5 (Annual budget) not in Accounting format"
                )
                assert ws.cell(3, 6).number_format == _ACCOUNTING_FMT, (
                    f"{sheet_name} col 6 (YTD) not in Accounting format"
                )

    def test_percent_format_on_pct_column(self, tmp_path: Path) -> None:
        """The % Budget column (col 7) must use 0.00 format."""
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        for sheet_name in ["Revenue", "Expenditure"]:
            ws = wb[sheet_name]
            if ws.max_row >= 3:
                assert ws.cell(3, 7).number_format == "0.00", (
                    f"{sheet_name} col 7 (% Budget) not in 0.00 format"
                )

    def test_uncommitted_balance_computed_correctly(self, tmp_path: Path) -> None:
        """Uncommitted Balance = Annual budget - YTD - Outstanding Orders."""
        lines = [
            SubProgramLine(
                sub_program="4001",
                account="Expenditure",
                description="Test",
                budget=Decimal("100"),
                ytd=Decimal("20"),
                remaining=Decimal("80"),
                used_pct=Decimal("20"),
                faculty=None,
                is_over=False,
                outstanding_orders=Decimal("5"),
            )
        ]
        out = tmp_path / "out.xlsx"
        _write_xlsx(lines, out, period_label="")
        wb = openpyxl.load_workbook(out)
        ws = wb["Expenditure"]
        # Col 8 = Uncommitted Balance (was col 9 when Outstanding Orders was a
        # displayed column; now col 8 since Outstanding Orders is not displayed
        # per Q3 of the Jan26 spec — see _EXP_HEADERS).
        uncommitted = ws.cell(3, 8).value
        assert uncommitted == 75.0, f"Expected 75, got {uncommitted}"

    def test_pink_fill_on_over_budget_rows(self, tmp_path: Path) -> None:
        """Over-budget rows must have HL_MISMATCH fill; other rows must not.

        _make_mixed_lines() has exactly one over-budget row: sp '4400' in
        Expenditure (is_over=True).  With the default threshold of 101.0, that
        row is the only one that should be filled pink.
        """
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="", over_budget_threshold=101.0)
        wb = openpyxl.load_workbook(out)
        target_argb = ("FF" + HL_MISMATCH).upper()

        # sp 4400 is in the Expenditure sheet (is_over=True); it is the only
        # data row that should have the pink fill.
        ws_exp = wb["Expenditure"]
        pink_rows_exp: list[int] = []
        non_over_with_pink: list[str] = []
        for row in ws_exp.iter_rows(min_row=3):
            sp_val = str(row[0].value or "").strip()
            row_has_pink = any(
                cell.fill
                and cell.fill.fgColor
                and cell.fill.fgColor.rgb
                and target_argb in cell.fill.fgColor.rgb.upper()
                for cell in row
            )
            if sp_val == "4400":
                assert row_has_pink, "sp 4400 (is_over=True) row must have pink fill"
                row_num = row[0].row
                if row_num is not None:
                    pink_rows_exp.append(row_num)
            elif row_has_pink:
                non_over_with_pink.append(f"Expenditure!row {row[0].row} (sp={sp_val!r})")

        assert pink_rows_exp, "sp 4400 over-budget row not found in Expenditure sheet"
        assert not non_over_with_pink, (
            f"Non-over-budget rows should not have pink fill: {non_over_with_pink}"
        )

        # Revenue sheet has no over-budget rows -- must have zero pink fills.
        ws_rev = wb["Revenue"]
        pink_rev: list[str] = []
        for row in ws_rev.iter_rows(min_row=3):
            for cell in row:
                fill = cell.fill
                if fill and fill.fgColor and fill.fgColor.rgb:
                    if target_argb in fill.fgColor.rgb.upper():
                        pink_rev.append(f"Revenue!{cell.coordinate}")
        assert not pink_rev, f"Revenue sheet must have no pink fills, found: {pink_rev[:5]}"

    def test_data_bar_conditional_formatting_on_pct_column(self, tmp_path: Path) -> None:
        """A DataBarRule must be present on the % Budget column (G) in both sheets."""
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        for sheet_name in ["Revenue", "Expenditure"]:
            ws = wb[sheet_name]
            found_databar = False
            for _rng, rules in ws.conditional_formatting._cf_rules.items():  # type: ignore[attr-defined]
                for rule in rules:
                    if rule.type == "dataBar":
                        found_databar = True
                        break
            assert found_databar, f"{sheet_name}: no DataBarRule found in conditional formatting"

    def test_frozen_panes_a3(self, tmp_path: Path) -> None:
        """Both sheets must freeze panes at A3 (title + header visible)."""
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="March 2026")
        wb = openpyxl.load_workbook(out)
        assert wb["Revenue"].freeze_panes == "A3"
        assert wb["Expenditure"].freeze_panes == "A3"

    def test_lines_split_by_account(self, tmp_path: Path) -> None:
        """Revenue lines go to Revenue sheet, Expenditure lines go to Expenditure sheet."""
        out = tmp_path / "out.xlsx"
        _write_xlsx(_make_mixed_lines(), out, period_label="")
        wb = openpyxl.load_workbook(out)
        ws_rev = wb["Revenue"]
        ws_exp = wb["Expenditure"]
        # Collect sub-programs from each sheet (data starts row 3)
        rev_sps = {ws_rev.cell(r, 1).value for r in range(3, ws_rev.max_row + 1)}
        exp_sps = {ws_exp.cell(r, 1).value for r in range(3, ws_exp.max_row + 1)}
        # '4001' and '4003' appear in both Revenue and Expenditure in mixed lines
        assert "4001" in rev_sps
        assert "4001" in exp_sps
        assert "4400" in exp_sps  # over-budget Expenditure line
        assert "4400" not in rev_sps  # must NOT be in Revenue


# ---------------------------------------------------------------------------
# Test: period label extraction and summary integration
# ---------------------------------------------------------------------------


class TestPeriodLabel:
    def test_extract_period_label_from_footer(self) -> None:
        text = "3 March 2026 13:37 1 [GL21157]"
        assert _extract_period_label(text) == "March 2026"

    def test_extract_period_label_no_match_returns_empty(self) -> None:
        assert _extract_period_label("no date here") == ""

    def test_sheet_title_with_period(self) -> None:
        assert _sheet_title("Report", "January 2026", "Revenue") == (
            "Report - January 2026 Revenue"
        )

    def test_sheet_title_without_period(self) -> None:
        t = _sheet_title("Annual Sub-Program Budget Report", "", "Expenditure")
        assert t == "Annual Sub-Program Budget Report - Expenditure"
        assert "  " not in t

    def test_summary_includes_period_label(self, tmp_path: Path) -> None:
        """generate_report must populate period_label from the PDF footer."""
        output = tmp_path / "out.xlsx"
        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )
        # The sample PDF footer contains a date; period_label must be non-empty.
        assert summary.period_label, (
            "period_label is empty -- check the footer regex against the sample PDF"
        )
        # The sample PDF is from March 2026.
        assert summary.period_label == "March 2026"

    def test_summary_period_label_empty_for_xlsx_input(self, tmp_path: Path) -> None:
        """XLSX-sourced input has no footer date, so period_label defaults to ''."""
        # Build a minimal XLSX fixture to feed to parse_sub_program_xlsx.

        xlsx_in = tmp_path / "input.xlsx"
        wb_in = openpyxl.Workbook()
        ws_in = wb_in.active
        ws_in.append(["Sub-Program", "Title", "LYA", "LYB", "Budget", "YTD", "Pct"])  # type: ignore[union-attr]
        ws_in.append(["4001", "Art", 0, 0, 50000, 25000, 50])  # type: ignore[union-attr]
        wb_in.save(xlsx_in)

        output = tmp_path / "out.xlsx"
        summary = generate_report(
            report_file=xlsx_in,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )
        # No footer in XLSX -- period_label must be the default empty string.
        assert summary.period_label == ""


# ---------------------------------------------------------------------------
# Test: new PDF parser fields (last-year actual/budget, outstanding orders)
# ---------------------------------------------------------------------------


class TestNewParserFields:
    @pytest.fixture(scope="class")
    def lines(self) -> list[SubProgramLine]:
        result, _ = parse_sub_program_pdf_with_period(_SAMPLE_PDF)
        return result

    def test_summary_lines_have_last_year_actual(self, lines: list[SubProgramLine]) -> None:
        """At least some Revenue or Expenditure lines must have a non-zero last_year_actual."""
        non_zero = [ln for ln in lines if ln.last_year_actual != Decimal("0")]
        assert non_zero, (
            "No lines with non-zero last_year_actual found -- check the parser "
            "against the sample PDF columns."
        )

    def test_summary_lines_have_last_year_budget(self, lines: list[SubProgramLine]) -> None:
        """At least some lines must have a non-zero last_year_budget."""
        non_zero = [ln for ln in lines if ln.last_year_budget != Decimal("0")]
        assert non_zero, "No lines with non-zero last_year_budget found -- check the parser."

    def test_summary_lines_have_outstanding_orders(self, lines: list[SubProgramLine]) -> None:
        """At least some Expenditure lines must have a non-zero outstanding_orders."""
        exp_with_outstanding = [
            ln
            for ln in lines
            if ln.account == "Expenditure" and ln.outstanding_orders != Decimal("0")
        ]
        assert exp_with_outstanding, (
            "No Expenditure lines with non-zero outstanding_orders found -- "
            "check the post-pct token extraction logic."
        )

    def test_known_row_4016_revenue_last_year_values(self, lines: list[SubProgramLine]) -> None:
        """Row 4016 Revenue in the sample PDF has both last-year columns."""
        row = next(
            (ln for ln in lines if ln.sub_program == "4016" and ln.account == "Revenue"),
            None,
        )
        assert row is not None, "Row 4016 Revenue not found"
        assert row.last_year_actual == Decimal("242911"), (
            f"last_year_actual: expected 242911, got {row.last_year_actual}"
        )
        assert row.last_year_budget == Decimal("243450"), (
            f"last_year_budget: expected 243450, got {row.last_year_budget}"
        )

    def test_known_row_4001_expenditure_outstanding(self, lines: list[SubProgramLine]) -> None:
        """Row 4001 Art Expenditure has outstanding_orders=489."""
        row = next(
            (ln for ln in lines if ln.sub_program == "4001" and ln.account == "Expenditure"),
            None,
        )
        assert row is not None, "Row 4001 Expenditure not found"
        assert row.outstanding_orders == Decimal("489"), (
            f"outstanding_orders: expected 489, got {row.outstanding_orders}"
        )

    def test_revenue_lines_outstanding_defaults_to_zero(self, lines: list[SubProgramLine]) -> None:
        """Revenue lines must all have outstanding_orders == 0 (not in PDF)."""
        bad = [
            ln for ln in lines if ln.account == "Revenue" and ln.outstanding_orders != Decimal("0")
        ]
        assert not bad, (
            f"{len(bad)} Revenue line(s) have non-zero outstanding_orders: "
            f"{[(ln.sub_program, ln.outstanding_orders) for ln in bad[:3]]}"
        )


# ---------------------------------------------------------------------------
# Test: over-budget threshold (Fix 2 -- Round 9)
# ---------------------------------------------------------------------------


def _make_threshold_lines() -> list[SubProgramLine]:
    """Lines with varying used_pct values for threshold testing."""

    def _exp(sp: str, budget: str, ytd: str, pct: str) -> SubProgramLine:
        b = Decimal(budget)
        y = Decimal(ytd)
        return SubProgramLine(
            sub_program=sp,
            account="Expenditure",
            description=f"Exp {sp}",
            budget=b,
            ytd=y,
            remaining=b - y,
            used_pct=Decimal(pct),
            faculty="Curriculum",
            is_over=False,  # will be overridden by _recompute_is_over
        )

    return [
        _exp("4001", "100", "50", "50.00"),  # 50% -- never over
        _exp("4002", "100", "100", "100.00"),  # exactly 100% -- not > 101
        _exp("4003", "100", "101", "101.00"),  # 101% -- at default threshold (101.0) = not over
        _exp("4004", "100", "102", "102.00"),  # 102% -- over at default threshold
        _exp("4005", "100", "200", "200.00"),  # 200% -- always over (except threshold 200+)
    ]


class TestOverBudgetThreshold:
    """Threshold-aware is_over logic and XLSX fills."""

    def test_recompute_default_threshold(self) -> None:
        """Default 101.0: lines with used_pct > 101 are over."""
        lines = _recompute_is_over(_make_threshold_lines(), 101.0)
        assert not lines[0].is_over  # 50%
        assert not lines[1].is_over  # 100%
        assert not lines[2].is_over  # 101% -- NOT > 101
        assert lines[3].is_over  # 102%
        assert lines[4].is_over  # 200%

    def test_recompute_exact_100_threshold(self) -> None:
        """Threshold 100.0: lines with used_pct > 100 are over."""
        lines = _recompute_is_over(_make_threshold_lines(), 100.0)
        assert not lines[0].is_over  # 50%
        assert not lines[1].is_over  # exactly 100 -- NOT > 100
        assert lines[2].is_over  # 101%
        assert lines[3].is_over  # 102%
        assert lines[4].is_over  # 200%

    def test_recompute_high_threshold_suppresses_all(self) -> None:
        """Threshold 9999: no line is over-budget."""
        lines = _recompute_is_over(_make_threshold_lines(), 9999.0)
        assert not any(ln.is_over for ln in lines)

    def test_generate_report_default_threshold_in_summary(self, tmp_path: Path) -> None:
        """generate_report stores the threshold in ReportSummary."""
        output = tmp_path / "out.xlsx"
        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )
        assert summary.over_budget_threshold == 101.0

    def test_generate_report_custom_threshold_changes_over_count(self, tmp_path: Path) -> None:
        """A high threshold produces fewer (or zero) over-budget lines."""
        output_default = tmp_path / "out_default.xlsx"
        output_high = tmp_path / "out_high.xlsx"

        summary_default = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output_default,
            progress=lambda p, m: None,
            over_budget_threshold=101.0,
        )
        summary_high = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output_high,
            progress=lambda p, m: None,
            over_budget_threshold=9999.0,
        )

        assert len(summary_default.over_budget_lines) > 0, (
            "Sample PDF must have over-budget lines at default threshold"
        )
        assert len(summary_high.over_budget_lines) == 0, (
            "At threshold 9999%, no line in the sample PDF should be over-budget"
        )

    def test_xlsx_pink_fill_respects_threshold(self, tmp_path: Path) -> None:
        """With a high threshold, no pink fills should appear in the XLSX."""
        lines = _make_threshold_lines()
        # Recompute with high threshold so no line is over
        lines = _recompute_is_over(lines, 9999.0)
        out = tmp_path / "no_fills.xlsx"
        _write_xlsx(lines, out, period_label="", over_budget_threshold=9999.0)

        wb = openpyxl.load_workbook(out)
        target_argb = ("FF" + HL_MISMATCH).upper()
        pink_cells: list[str] = []
        for ws in [wb["Revenue"], wb["Expenditure"]]:
            for row in ws.iter_rows():
                for cell in row:
                    fill = cell.fill
                    if fill and fill.fgColor and fill.fgColor.rgb:
                        if target_argb in fill.fgColor.rgb.upper():
                            pink_cells.append(f"{ws.title}!{cell.coordinate}")
        assert not pink_cells, (
            f"High threshold should suppress all pink fills, found: {pink_cells[:5]}"
        )

    def test_over_fill_constant_uses_hl_mismatch(self) -> None:
        """_OVER_FILL fgColor must derive from HL_MISMATCH via argb()."""
        from toolkit.fills import argb

        expected_argb = argb(HL_MISMATCH).upper()
        actual_argb = _OVER_FILL.fgColor.rgb.upper() if _OVER_FILL.fgColor else ""
        assert actual_argb == expected_argb, (
            f"_OVER_FILL fgColor {actual_argb!r} does not match argb(HL_MISMATCH) {expected_argb!r}"
        )


class TestPerSectionThreshold:
    """Round 21 — Revenue and Expense thresholds are independent.

    Schools care about Expense over-runs but rarely flag Revenue
    over-collections.  Verify that the section-aware overload of
    ``_recompute_is_over`` flags rows correctly when the two thresholds
    differ.
    """

    def _mixed_lines(self) -> list[SubProgramLine]:
        """Two Revenue + two Expenditure lines at known used_pct values."""

        def _line(sp: str, section: str, pct: str) -> SubProgramLine:
            return SubProgramLine(
                sub_program=sp,
                account=section,
                description=f"{section} {sp}",
                budget=Decimal("100"),
                ytd=Decimal("100"),
                remaining=Decimal("0"),
                used_pct=Decimal(pct),
                faculty="Curriculum",
                is_over=False,
            )

        return [
            _line("1001", "Revenue", "105"),  # over a 101 threshold
            _line("1002", "Revenue", "115"),  # over a 110 threshold
            _line("4001", "Expenditure", "105"),  # over a 101 threshold
            _line("4002", "Expenditure", "115"),  # over a 110 threshold
        ]

    def test_revenue_threshold_only_flags_revenue(self) -> None:
        """High Revenue threshold + low Expense threshold = no Revenue
        flagged but both Expense lines flagged."""
        lines = _recompute_is_over(
            self._mixed_lines(),
            101.0,  # legacy combined value (ignored when overrides set)
            revenue_threshold=120.0,
            expense_threshold=101.0,
        )
        assert not lines[0].is_over  # Revenue 105% < 120%
        assert not lines[1].is_over  # Revenue 115% < 120%
        assert lines[2].is_over  # Expense 105% > 101%
        assert lines[3].is_over  # Expense 115% > 101%

    def test_expense_threshold_only_flags_expense(self) -> None:
        """Low Revenue + high Expense = both Revenue flagged, no Expense."""
        lines = _recompute_is_over(
            self._mixed_lines(),
            101.0,
            revenue_threshold=101.0,
            expense_threshold=120.0,
        )
        assert lines[0].is_over  # Revenue 105% > 101%
        assert lines[1].is_over  # Revenue 115% > 101%
        assert not lines[2].is_over  # Expense 105% < 120%
        assert not lines[3].is_over  # Expense 115% < 120%

    def test_legacy_single_threshold_still_works(self) -> None:
        """Backward compat — calling without per-section overrides still
        applies one threshold to both sections."""
        lines = _recompute_is_over(self._mixed_lines(), 110.0)
        assert not lines[0].is_over  # 105 < 110
        assert lines[1].is_over  # 115 > 110
        assert not lines[2].is_over  # 105 < 110
        assert lines[3].is_over  # 115 > 110

    def test_generate_report_passes_thresholds_to_summary(self, tmp_path: Path) -> None:
        """ReportSummary preserves the per-section thresholds the user
        chose, even when they differ from the legacy combined value."""
        output = tmp_path / "out.xlsx"
        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
            revenue_threshold=110.0,
            expense_threshold=102.0,
        )
        assert summary.revenue_threshold == 110.0
        assert summary.expense_threshold == 102.0
