"""Tests for tools/sub_program/frame.py — BaseTool conformance + run() paths."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import FileInput, OutputSpec
from tools.sub_program.frame import SubProgramBudgetReportTool
from tools.sub_program.logic import ReportSummary, SubProgramLine

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _noop_progress(pct: int, msg: str) -> None:
    pass


def _make_line(
    sub_program: str = "4001",
    account: str = "Expenditure",
    description: str = "Test line",
    budget: str = "10000",
    ytd: str = "5000",
    is_over: bool = False,
    faculty: str | None = "Curriculum",
) -> SubProgramLine:
    b = Decimal(budget)
    y = Decimal(ytd)
    return SubProgramLine(
        sub_program=sub_program,
        account=account,
        description=description,
        budget=b,
        ytd=y,
        remaining=b - y,
        used_pct=Decimal("50.0"),
        faculty=faculty,
        is_over=is_over,
    )


def _make_summary(
    lines: list[SubProgramLine] | None = None,
    over_budget_lines: list[SubProgramLine] | None = None,
    output_path: Path | None = None,
) -> ReportSummary:
    if lines is None:
        lines = [_make_line("4001"), _make_line("5001", faculty="Student Wellbeing")]
    if over_budget_lines is None:
        over_budget_lines = []
    if output_path is None:
        output_path = Path("/tmp/output.xlsx")
    faculty_counts: dict[str, int] = {}
    for ln in lines:
        key = ln.faculty or "Unknown"
        faculty_counts[key] = faculty_counts.get(key, 0) + 1
    total_budget = sum((ln.budget for ln in lines), Decimal("0"))
    total_ytd = sum((ln.ytd for ln in lines), Decimal("0"))
    return ReportSummary(
        lines=lines,
        faculty_counts=faculty_counts,
        over_budget_lines=over_budget_lines,
        total_budget=total_budget,
        total_ytd=total_ytd,
        output_path=output_path,
    )


# ---------------------------------------------------------------------------
# 1. Structural conformance
# ---------------------------------------------------------------------------


class TestStructuralConformance:
    """Tool class must expose all BaseTool attributes + methods."""

    def test_id(self) -> None:
        assert SubProgramBudgetReportTool.id == "sub-program"

    def test_group(self) -> None:
        assert SubProgramBudgetReportTool.group == "Budget"

    def test_label(self) -> None:
        assert SubProgramBudgetReportTool.label == "Sub-Program Budget Report"

    def test_short(self) -> None:
        assert SubProgramBudgetReportTool.short == "SP"

    def test_order(self) -> None:
        assert isinstance(SubProgramBudgetReportTool.order, int)

    def test_primary_button(self) -> None:
        assert SubProgramBudgetReportTool.primary_button == "Generate report"

    def test_has_run(self) -> None:
        tool = SubProgramBudgetReportTool()
        assert callable(tool.run)

    def test_has_secondary_actions(self) -> None:
        tool = SubProgramBudgetReportTool()
        actions = tool.secondary_actions()
        assert isinstance(actions, list)

    def test_has_help_text(self) -> None:
        assert isinstance(SubProgramBudgetReportTool.help_text, str)

    def test_pdf_template_none(self) -> None:
        assert SubProgramBudgetReportTool.pdf_template is None

    def test_pdf_body_none(self) -> None:
        assert SubProgramBudgetReportTool.pdf_body is None


# ---------------------------------------------------------------------------
# 2. Inputs
# ---------------------------------------------------------------------------


class TestInputs:
    def test_inputs_has_two_items(self) -> None:
        assert len(SubProgramBudgetReportTool.inputs) == 2

    def test_first_input_is_file(self) -> None:
        fi = SubProgramBudgetReportTool.inputs[0]
        assert isinstance(fi, FileInput)
        assert fi.key == "report_file"

    def test_second_input_is_optional_labelled(self) -> None:
        fi = SubProgramBudgetReportTool.inputs[1]
        assert isinstance(fi, FileInput)
        assert fi.key == "comments_file"
        # "optional" must appear somewhere in the label (case-insensitive)
        assert "optional" in fi.label.lower()

    def test_output_suffix_xlsx(self) -> None:
        assert SubProgramBudgetReportTool.output is not None
        assert isinstance(SubProgramBudgetReportTool.output, OutputSpec)
        assert SubProgramBudgetReportTool.output.suffix == ".xlsx"


# ---------------------------------------------------------------------------
# 3. run() — happy path
# ---------------------------------------------------------------------------


class TestRunHappyPath:
    def test_success_status(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "success"

    def test_table_rows_populated(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        lines = [_make_line("4001"), _make_line("5001", faculty="Student Wellbeing")]
        summary = _make_summary(lines=lines)
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        assert len(result.table_rows) == 2

    def test_table_columns_present(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        assert keys == [
            "sub_program",
            "account",
            "description",
            "budget",
            "ytd",
            "remaining",
            "used_pct",
        ]

    def test_output_path_set(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(out),
                },
                _noop_progress,
            )
        assert result.output_path == out


# ---------------------------------------------------------------------------
# 4. run() — warning path (over-budget line)
# ---------------------------------------------------------------------------


class TestRunWarningPath:
    def test_warning_status(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        over_line = _make_line(
            sub_program="4001",
            budget="5000",
            ytd="7000",
            is_over=True,
        )
        summary = _make_summary(
            lines=[over_line],
            over_budget_lines=[over_line],
        )
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "warning"

    def test_over_budget_row_has_bg(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        over_line = _make_line(
            sub_program="4001",
            budget="5000",
            ytd="7000",
            is_over=True,
        )
        summary = _make_summary(
            lines=[over_line],
            over_budget_lines=[over_line],
        )
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        row = result.table_rows[0]
        assert row["_bg"] is not None
        assert "F4CCCC" in row["_bg"]

    def test_non_over_budget_row_has_no_bg(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        normal_line = _make_line("5001", is_over=False)
        over_line = _make_line("4001", budget="5000", ytd="7000", is_over=True)
        summary = _make_summary(
            lines=[normal_line, over_line],
            over_budget_lines=[over_line],
        )
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        assert result.table_rows[0]["_bg"] is None  # normal line
        assert result.table_rows[1]["_bg"] is not None  # over-budget line


# ---------------------------------------------------------------------------
# 5. run() — error path
# ---------------------------------------------------------------------------


class TestRunErrorPath:
    def test_error_status(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        with patch(
            "tools.sub_program.frame.logic.generate_report",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "missing.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.status == "error"

    def test_error_banner_level_danger(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        with patch(
            "tools.sub_program.frame.logic.generate_report",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "missing.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert result.banner_level == "danger"

    def test_error_log_lines_include_exc_type(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        with patch(
            "tools.sub_program.frame.logic.generate_report",
            side_effect=ValueError("bad file"),
        ):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "missing.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        combined = " ".join(ll.text for ll in result.log_lines)
        assert "ValueError" in combined


# ---------------------------------------------------------------------------
# 6. run() — missing comments_file key
# ---------------------------------------------------------------------------


class TestRunMissingCommentsFile:
    def test_missing_key_passes_none_to_logic(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(
            report_file: Path,
            comments_file: Path | None,
            output_file: Path,
            progress: Any,
        ) -> ReportSummary:
            captured["comments_file"] = comments_file
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "output_file": str(tmp_path / "out.xlsx"),
                    # comments_file key deliberately absent
                },
                _noop_progress,
            )
        assert captured["comments_file"] is None
        assert result.status == "success"

    def test_empty_string_comments_file_treated_as_none(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(
            report_file: Path,
            comments_file: Path | None,
            output_file: Path,
            progress: Any,
        ) -> ReportSummary:
            captured["comments_file"] = comments_file
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "comments_file": "",  # empty string = not supplied
                    "output_file": str(tmp_path / "out.xlsx"),
                },
                _noop_progress,
            )
        assert captured["comments_file"] is None
        assert result.status == "success"


# ---------------------------------------------------------------------------
# 7. Help text content
# ---------------------------------------------------------------------------


class TestHelpText:
    def test_help_text_non_empty(self) -> None:
        assert len(SubProgramBudgetReportTool.help_text) > 100

    def test_help_text_mentions_sub_program(self) -> None:
        assert "Sub-Program" in SubProgramBudgetReportTool.help_text

    def test_help_text_mentions_cases21(self) -> None:
        assert "CASES21" in SubProgramBudgetReportTool.help_text

    def test_help_text_mentions_faculty(self) -> None:
        ht = SubProgramBudgetReportTool.help_text.lower()
        assert "faculty" in ht


# ---------------------------------------------------------------------------
# 8. Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_tool_registered(self) -> None:
        # Importing tools.sub_program fires the register() call.
        import tools.sub_program  # noqa: F401
        from toolkit.registry import _registered

        registered_ids = [cls.id for cls in _registered]
        assert SubProgramBudgetReportTool.id in registered_ids

    def test_all_tools_includes_sub_program(self) -> None:
        from toolkit.registry import all_tools

        ids = [t.id for t in all_tools()]
        assert "sub-program" in ids
