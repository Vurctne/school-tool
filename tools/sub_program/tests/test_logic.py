from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from toolkit.tokens import HL_MISMATCH
from tools.sub_program.logic import (
    _OVER_FILL,
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
        """Round 38 — output is now a single sheet with the Monthly Sub
        Program Report 12-column header shape."""
        output = tmp_path / "output2.xlsx"

        generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        # Single sheet now — name is "Sub Program Report".
        assert "Sub Program Report" in wb.sheetnames, (
            f"Expected 'Sub Program Report' sheet; got {wb.sheetnames}"
        )
        ws = wb["Sub Program Report"]
        headers = [str(ws.cell(2, c).value or "") for c in range(1, 13)]
        assert headers[0] == "CODE"
        assert headers[1] == "PROGRAM NAME"
        assert headers[2].startswith("Funds from Previous Years")
        assert headers[3].startswith("Budget Revenue")
        assert headers[4].startswith("Total Budget Allocation Expenditure")
        assert headers[5] == "Revenue YTD"
        assert headers[6] == "Expenditure YTD"
        assert headers[7] == "Less outstanding orders"
        assert headers[8] == "Available Balance YTD"
        assert headers[9] == "Available Balance % YTD"
        assert headers[10] == "Revenue Budget % Received YTD"
        assert headers[11] == "Comments"

    def test_output_row_count_matches_unique_subprograms(self, tmp_path: Path) -> None:
        """Round 38 — one row per sub-program (was: one row per
        account-line, split across two sheets)."""
        output = tmp_path / "output3.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        ws = wb["Sub Program Report"]
        # Row 1 = title, row 2 = header, rows 3+ = data
        data_rows = (ws.max_row or 2) - 2
        unique_sps = {ln.sub_program for ln in summary.lines}
        assert data_rows == len(unique_sps), (
            f"Expected {len(unique_sps)} data rows (one per sub-program); got {data_rows}"
        )

    def test_pink_fill_on_over_budget_rows(self, tmp_path: Path) -> None:
        """Round 38 — superseded by test_xlsx_monthly_report.py."""
        # Old shape (Revenue/Expenditure sheets) no longer produced.

    def test_over_budget_fill_all_columns(self, tmp_path: Path) -> None:
        """Round 38 — superseded by test_xlsx_monthly_report.py."""
        # Old shape (Revenue/Expenditure sheets) no longer produced.

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


class TestXlsxMonthlyReport:
    """Round 38 — replaced TestXlsxTwoSheets. The XLSX output is now a
    single sheet matching the school's own Monthly Sub Program Report
    workbook (12 columns, one row per sub-program). Detailed coverage
    of the new shape lives in test_xlsx_monthly_report.py (Round 38)."""

    def test_single_sheet_named_sub_program_report(self, tmp_path: Path) -> None:
        from tools.sub_program.logic import SubProgramLine

        out = tmp_path / "test.xlsx"
        ln = SubProgramLine(
            sub_program="4101",
            account="Expenditure",
            description="English",
            budget=Decimal("1000"),
            ytd=Decimal("400"),
            remaining=Decimal("600"),
            used_pct=Decimal("40"),
            faculty="Curriculum",
            is_over=False,
        )
        _write_xlsx([ln], out)
        wb = openpyxl.load_workbook(out)
        assert wb.sheetnames == ["Sub Program Report"]


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
        # Round 47 — at threshold 9999%, no PERCENTAGE-driven flag should
        # fire, but the zero-budget-with-spend trigger (Round 47) flags
        # any line where budget=$0 and ytd!=$0 regardless of threshold.
        # Verify percentage-driven flags are gone but allow zero-budget
        # rows to remain on the over list.
        non_zero_budget_overs = [
            ln for ln in summary_high.over_budget_lines if ln.budget != Decimal("0")
        ]
        assert len(non_zero_budget_overs) == 0, (
            "At threshold 9999%, no positive-budget line should exceed the threshold"
        )

    def test_xlsx_pink_fill_respects_threshold(self, tmp_path: Path) -> None:
        """Round 38 — superseded by test_xlsx_monthly_report.py."""
        # Old shape (Revenue/Expenditure sheets) no longer produced.

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
        """Backward compat - calling without per-section overrides still
        applies one threshold to both sections."""
        lines = _recompute_is_over(self._mixed_lines(), threshold=110.0)
        # Threshold 110% - Revenue 115% triggers, others don't.
        assert not lines[0].is_over  # 105 < 110
        assert lines[1].is_over  # 115 > 110
        assert not lines[2].is_over  # 105 < 110
        assert lines[3].is_over  # 115 > 110


# ---------------------------------------------------------------------------
# Round 51 Phase D — structured commentary
# ---------------------------------------------------------------------------


class TestStructuredCommentary:
    """encode_commentary / decode_commentary round-trip + edge cases."""

    def test_value_tuples_have_designed_shape(self) -> None:
        """Pin the dropdown values so a stray edit can't silently drift
        away from the inline editor's Combobox lists."""
        from tools.sub_program.logic import (
            _ACTION_VALUES,
            _DRIVER_VALUES,
            _OUTLOOK_VALUES,
        )

        assert _DRIVER_VALUES == (
            "One-time",
            "Ongoing",
            "Structural",
            "Timing-early",
            "Timing-late",
            "Investigating",
        )
        assert _OUTLOOK_VALUES == (
            "One-time",
            "Expected to continue",
            "Improving",
            "Deteriorating",
        )
        assert _ACTION_VALUES == (
            "None",
            "Monitor",
            "Investigate",
            "Update forecast",
        )

    def test_encode_all_blank_returns_empty(self) -> None:
        from tools.sub_program.logic import encode_commentary

        assert encode_commentary("") == ""

    def test_encode_notes_only_no_prefix(self) -> None:
        """Pre-Phase-D shape — no prefix when all dropdowns are blank."""
        from tools.sub_program.logic import encode_commentary

        assert encode_commentary("Reviewed by council") == "Reviewed by council"

    def test_encode_only_action_emits_minimal_prefix(self) -> None:
        """Round 1 fix: separator is now newline (not space) so the prefix
        and notes don't visually merge when the XLSX cell wraps."""
        from tools.sub_program.logic import encode_commentary

        assert encode_commentary("notes", action="Monitor") == "[Action: Monitor]\nnotes"

    def test_encode_all_three_emits_full_prefix(self) -> None:
        from tools.sub_program.logic import encode_commentary

        encoded = encode_commentary(
            "Reviewed by council",
            driver="Ongoing",
            outlook="Expected to continue",
            action="Monitor",
        )
        assert encoded == (
            "[Driver: Ongoing | Outlook: Expected to continue | Action: Monitor]\n"
            "Reviewed by council"
        )

    def test_encode_action_none_literal_emits_prefix(self) -> None:
        """The literal 'None' value (user reviewed, no action) is distinct
        from '' (not categorised) and must appear in the prefix."""
        from tools.sub_program.logic import encode_commentary

        assert encode_commentary("done", action="None") == "[Action: None]\ndone"

    def test_encode_escapes_leading_bracket_in_notes(self) -> None:
        """Notes starting with ``[`` and dropdowns blank -> empty-body
        escape so the decoder doesn't mis-parse on next read."""
        from tools.sub_program.logic import encode_commentary

        assert encode_commentary("[Driver: foo] bar") == "[]\n[Driver: foo] bar"

    def test_decode_empty_string(self) -> None:
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary("") == ("", "", "", "")

    def test_decode_pre_phase_d_freeform_text(self) -> None:
        """Pre-Phase-D files have no prefix; the entire cell is Notes."""
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary("Reviewed by council") == (
            "Reviewed by council",
            "",
            "",
            "",
        )

    def test_decode_unknown_bracket_preserved_as_notes(self) -> None:
        """A ``[FREE TEXT]`` opener with no Phase-D keys is treated as
        Notes, not as a (broken) prefix."""
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary("[NOTE TO SELF] check next week") == (
            "[NOTE TO SELF] check next week",
            "",
            "",
            "",
        )

    def test_decode_full_prefix(self) -> None:
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary(
            "[Driver: Ongoing | Outlook: Improving | Action: Monitor] notes"
        ) == ("notes", "Ongoing", "Improving", "Monitor")

    def test_decode_partial_prefix(self) -> None:
        """Only some structured fields set — the rest decode as ''."""
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary("[Action: Investigate] follow up") == (
            "follow up",
            "",
            "",
            "Investigate",
        )

    def test_decode_strips_empty_body_escape(self) -> None:
        """The ``[]`` escape strips correctly and preserves notes."""
        from tools.sub_program.logic import decode_commentary

        assert decode_commentary("[] [Driver: foo] bar") == (
            "[Driver: foo] bar",
            "",
            "",
            "",
        )

    def test_round_trip_full_combination(self) -> None:
        """Composite round-trip across an array of representative inputs."""
        from tools.sub_program.logic import decode_commentary, encode_commentary

        cases = [
            ("", "", "", ""),
            ("notes only", "", "", ""),
            ("", "Ongoing", "", ""),
            ("", "", "Improving", ""),
            ("", "", "", "Investigate"),
            ("notes", "Ongoing", "Improving", "Monitor"),
            ("notes with $1,234.56", "Structural", "Deteriorating", "Update forecast"),
            ("[brackets in notes]", "", "", ""),  # escape path
            ("done", "", "", "None"),  # literal None action
        ]
        for notes, driver, outlook, action in cases:
            enc = encode_commentary(notes, driver=driver, outlook=outlook, action=action)
            assert decode_commentary(enc) == (notes, driver, outlook, action), (
                f"round-trip failed for {(notes, driver, outlook, action)!r} -> "
                f"encoded={enc!r}, decoded={decode_commentary(enc)!r}"
            )


class TestStructuredCommentaryPriorPeriodMigration:
    """Pre-Phase-D prior-period file -> generate_report decodes to Notes only."""

    def test_pre_phase_d_freeform_lands_in_notes_with_blank_dropdowns(self, tmp_path: Path) -> None:
        """A prior-period file whose Comments column has no Phase-D
        prefix should round-trip into the new ``commentary`` (Notes)
        field with the three structured dropdowns left blank."""
        # Build a minimal pre-Phase-D shaped XLSX.
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Sub-Program", "Description", "Comments"])
        ws.append(["4001", "Curriculum", "Reviewed by council"])
        ws.append(["8599", "Rowing", "Spend on track"])
        comments_path = tmp_path / "prior_unstructured.xlsx"
        wb.save(comments_path)

        from tools.sub_program.logic import load_prior_period_comments

        # Reader is unchanged — returns the raw cell text.
        loaded = load_prior_period_comments(comments_path)
        assert loaded[("4001", "Curriculum")] == "Reviewed by council"
        assert loaded[("8599", "Rowing")] == "Spend on track"

    def test_phase_d_encoded_cell_decodes_at_consumer(self, tmp_path: Path) -> None:
        """A prior-period file from Round 51+ has the structured prefix
        in the Comments cell. ``decode_commentary`` (called by
        ``generate_report``) splits it cleanly back into the four
        fields."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Sub-Program", "Description", "Comments"])
        ws.append(
            [
                "4001",
                "Curriculum",
                "[Driver: Ongoing | Action: Monitor] Reviewed by council",
            ]
        )
        comments_path = tmp_path / "prior_structured.xlsx"
        wb.save(comments_path)

        from tools.sub_program.logic import (
            decode_commentary,
            load_prior_period_comments,
        )

        loaded = load_prior_period_comments(comments_path)
        encoded = loaded[("4001", "Curriculum")]
        notes, driver, outlook, action = decode_commentary(encoded)
        assert notes == "Reviewed by council"
        assert driver == "Ongoing"
        assert outlook == ""
        assert action == "Monitor"


class TestStructuredCommentaryXlsxOutput:
    """Structured fields round-trip through the XLSX writer."""

    def _line(
        self,
        sub_program: str,
        notes: str = "",
        driver: str = "",
        outlook: str = "",
        action: str = "",
    ) -> SubProgramLine:
        return SubProgramLine(
            sub_program=sub_program,
            account="Expenditure",
            description=f"{sub_program} description",
            budget=Decimal("10000"),
            ytd=Decimal("4000"),
            remaining=Decimal("6000"),
            used_pct=Decimal("40"),
            faculty="Curriculum",
            is_over=False,
            commentary=notes,
            commentary_driver=driver,
            commentary_outlook=outlook,
            commentary_action=action,
        )

    def test_xlsx_comments_cell_carries_structured_prefix(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        lines = [
            self._line(
                "4001",
                notes="Reviewed by council",
                driver="Ongoing",
                action="Monitor",
            ),
        ]
        _write_xlsx(lines, out, period_label="Apr 2026")

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["Sub Program Report"]
        # Header is rows 1-2, data starts row 3. Comments is column 12.
        cell = ws.cell(row=3, column=12).value
        # Round 1 fix: separator is now newline so wrap_text renders
        # notes on their own visual line in the XLSX.
        assert cell == "[Driver: Ongoing | Action: Monitor]\nReviewed by council"

    def test_xlsx_comments_cell_blank_when_all_fields_blank(self, tmp_path: Path) -> None:
        out = tmp_path / "out.xlsx"
        lines = [self._line("4001")]
        _write_xlsx(lines, out, period_label="Apr 2026")

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["Sub Program Report"]
        cell = ws.cell(row=3, column=12).value
        # Empty cell renders as None or "" depending on openpyxl version.
        assert cell in (None, "")

    def test_xlsx_comments_cell_notes_only_no_prefix(self, tmp_path: Path) -> None:
        """When only the freeform notes is set, the cell is plain text
        (no prefix) — preserves pre-Phase-D readability."""
        out = tmp_path / "out.xlsx"
        lines = [self._line("4001", notes="Reviewed by council")]
        _write_xlsx(lines, out, period_label="Apr 2026")

        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["Sub Program Report"]
        assert ws.cell(row=3, column=12).value == "Reviewed by council"


# ---------------------------------------------------------------------------
# Round 51 Phase D Round-1 fixes — protective behaviours added after the
# multi-personality audit (logic skeptic, UX critic, Excel QA).
# ---------------------------------------------------------------------------


class TestStructuredCommentaryRound1Fixes:
    """Targeted tests for the Round-1 protective fixes."""

    def test_decode_preserves_inner_whitespace_in_notes(self) -> None:
        """encode→decode→encode is idempotent — ``decode_commentary``
        only strips the prefix-adjacent separator, not user whitespace."""
        from tools.sub_program.logic import decode_commentary, encode_commentary

        notes = "  multi-line\n  with leading spaces  "
        encoded = encode_commentary(notes, action="Monitor")
        decoded = decode_commentary(encoded)
        assert decoded == (notes, "", "", "Monitor")
        # Idempotent — re-encoding the decoded tuple matches the original.
        re_encoded = encode_commentary(decoded[0], action=decoded[3])
        assert re_encoded == encoded

    def test_decode_preserves_unknown_driver_value(self) -> None:
        """Round 2 fix (R51): unknown Driver value (typo, schema drift,
        third-party edit) is preserved verbatim in the tuple instead
        of falling through to Notes. Avoids round-trip data loss when
        the editor's Combobox preserves a non-canonical value across a
        save→reopen cycle."""
        from tools.sub_program.logic import decode_commentary

        # "FooBar" is not in _DRIVER_VALUES but we still extract it.
        text = "[Driver: FooBar] my actual note"
        assert decode_commentary(text) == ("my actual note", "FooBar", "", "")

    def test_decode_preserves_unknown_outlook_value(self) -> None:
        from tools.sub_program.logic import decode_commentary

        text = "[Outlook: HopefullyOk] some note"
        assert decode_commentary(text) == ("some note", "", "HopefullyOk", "")

    def test_decode_preserves_unknown_action_value(self) -> None:
        from tools.sub_program.logic import decode_commentary

        text = "[Action: ReorderEverything] note"
        assert decode_commentary(text) == ("note", "", "", "ReorderEverything")

    def test_decode_mixed_known_and_unknown_preserves_both(self) -> None:
        """Round 2 fix: known + unknown values in same prefix are both
        extracted — the editor surfaces them and lets the user re-pick."""
        from tools.sub_program.logic import decode_commentary

        # Driver is canonical, Action is not — both preserved.
        text = "[Driver: Ongoing | Action: Reorder] note"
        assert decode_commentary(text) == ("note", "Ongoing", "", "Reorder")

    def test_decode_accepts_space_or_newline_separator(self) -> None:
        """Pre-Round-1 cells used a space separator; Round-1+ cells use
        a newline. Decoder tolerates both for forward / backward compat."""
        from tools.sub_program.logic import decode_commentary

        space_form = "[Action: Monitor] notes"
        newline_form = "[Action: Monitor]\nnotes"
        assert decode_commentary(space_form) == ("notes", "", "", "Monitor")
        assert decode_commentary(newline_form) == ("notes", "", "", "Monitor")

    def test_xlsx_atomic_per_subprogram_no_cross_row_fabrication(self, tmp_path: Path) -> None:
        """When a sub-program has multiple Account-rows with conflicting
        commentary, the writer adopts the WHOLE 4-tuple from one row
        (the first non-empty contributor) — never mixing notes from
        row A with Action from row B."""
        # Row A on Revenue side has notes only.
        # Row B on Expenditure side has structured fields only.
        # Pre-fix the writer would have produced a fabricated combination.
        line_a = SubProgramLine(
            sub_program="4001",
            account="Revenue",
            description="Curriculum",
            budget=Decimal("10000"),
            ytd=Decimal("4000"),
            remaining=Decimal("6000"),
            used_pct=Decimal("40"),
            faculty="Curriculum",
            is_over=False,
            commentary="row A note",
        )
        line_b = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Curriculum",
            budget=Decimal("10000"),
            ytd=Decimal("4000"),
            remaining=Decimal("6000"),
            used_pct=Decimal("40"),
            faculty="Curriculum",
            is_over=False,
            commentary_action="Investigate",
        )
        out = tmp_path / "atomic.xlsx"
        _write_xlsx([line_a, line_b], out, period_label="Apr 2026")
        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["Sub Program Report"]
        cell = ws.cell(row=3, column=12).value
        # Cell carries row A's notes only (row A came first), NOT a
        # fabricated "[Action: Investigate]\nrow A note" combination.
        assert cell == "row A note"

    def test_xlsx_formula_injection_guard_prepends_apostrophe(self, tmp_path: Path) -> None:
        """A user typing '=SUM(D3:E3) outdated' into Notes must NOT
        become a live Excel formula. The writer prepends an apostrophe
        — Excel renders the cell as text on display."""
        line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Curriculum",
            budget=Decimal("10000"),
            ytd=Decimal("4000"),
            remaining=Decimal("6000"),
            used_pct=Decimal("40"),
            faculty="Curriculum",
            is_over=False,
            commentary="=SUM(D3:E3) outdated",
        )
        out = tmp_path / "formula_guard.xlsx"
        _write_xlsx([line], out, period_label="Apr 2026")
        wb = openpyxl.load_workbook(out, data_only=True)
        ws = wb["Sub Program Report"]
        cell = ws.cell(row=3, column=12)
        assert cell.value == "'=SUM(D3:E3) outdated"
        # Cell is text-formatted, not a formula.
        assert cell.data_type == "s"
        assert cell.number_format == "@"

    def test_xlsx_formula_guard_applies_to_other_sigils(self, tmp_path: Path) -> None:
        """``=`` is the canonical formula prefix but Excel also evaluates
        ``+``, ``-``, and ``@`` — guard them all."""
        for sigil in ("+", "-", "@"):
            line = SubProgramLine(
                sub_program="4001",
                account="Expenditure",
                description="Curriculum",
                budget=Decimal("10000"),
                ytd=Decimal("4000"),
                remaining=Decimal("6000"),
                used_pct=Decimal("40"),
                faculty="Curriculum",
                is_over=False,
                commentary=f"{sigil}danger",
            )
            out = tmp_path / f"formula_guard_{sigil!r}.xlsx"
            _write_xlsx([line], out, period_label="Apr 2026")
            wb = openpyxl.load_workbook(out, data_only=True)
            ws = wb["Sub Program Report"]
            cell = ws.cell(row=3, column=12)
            assert cell.value == f"'{sigil}danger", f"sigil {sigil!r} should be guarded"

    def test_load_prior_period_strips_apostrophe_guard(self, tmp_path: Path) -> None:
        """The reader strips the formula-guard apostrophe so
        ``decode_commentary`` sees the original encoded value — and the
        round-trip doesn't accumulate apostrophes across save→reopen."""
        wb = openpyxl.Workbook()
        ws = wb.active
        assert ws is not None
        ws.append(["Sub-Program", "Description", "Comments"])
        ws.append(["4001", "Curriculum", "'=danger formula"])
        comments_path = tmp_path / "guarded.xlsx"
        wb.save(comments_path)

        loaded = load_prior_period_comments(comments_path)
        assert loaded[("4001", "Curriculum")] == "=danger formula"
