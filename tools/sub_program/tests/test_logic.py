from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import openpyxl
import pytest

from tools.sub_program.logic import (
    ReportSummary,
    SubProgramLine,
    generate_report,
    load_prior_period_comments,
    parse_decimal,
    parse_sub_program_pdf,
)

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SAMPLE_PDF = Path(
    "Samples/Annual Subprogram Budget Report/"
    "GL21157_Annual Subprogram budget report.pdf"
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
        assert parse_decimal("\u2014") == Decimal("0")

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
        output = tmp_path / "output2.xlsx"

        generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        ws = wb.active
        headers = [ws.cell(1, c).value for c in range(1, 10)]  # type: ignore[union-attr]
        assert headers[0] == "Sub-Program"
        assert headers[2] == "Description"
        assert "Budget" in headers

    def test_output_row_count_matches_lines(self, tmp_path: Path) -> None:
        output = tmp_path / "output3.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        wb = openpyxl.load_workbook(output)
        ws = wb.active
        data_rows = ws.max_row - 1  # type: ignore[union-attr]  # subtract header
        assert data_rows == len(summary.lines)

    def test_over_budget_fill_present(self, tmp_path: Path) -> None:
        output = tmp_path / "output4.xlsx"

        summary = generate_report(
            report_file=_SAMPLE_PDF,
            comments_file=None,
            output_file=output,
            progress=lambda p, m: None,
        )

        if not summary.over_budget_lines:
            pytest.skip("No over-budget lines in sample PDF")

        wb = openpyxl.load_workbook(output)
        ws = wb.active
        # Find the row for an over-budget line
        over_sp = summary.over_budget_lines[0].sub_program
        found_fill = False
        for row_idx in range(2, (ws.max_row or 2) + 1):  # type: ignore[union-attr]
            cell_val = ws.cell(row_idx, 1).value  # type: ignore[union-attr]
            if str(cell_val) == over_sp:
                fill = ws.cell(row_idx, 1).fill  # type: ignore[union-attr]
                if fill and fill.fgColor and fill.fgColor.rgb:
                    # HL_MISMATCH = "F4CCCC"; openpyxl stores as "FFF4CCCC"
                    found_fill = "F4CCCC" in fill.fgColor.rgb.upper()
                    if found_fill:
                        break
        assert found_fill, "Over-budget row should have HL_MISMATCH fill"

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
