"""Tests for tools/sub_program/frame.py — BaseTool conformance + run() paths."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import FileInput, RangeInput
from toolkit.tokens import HL_MISMATCH
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
    # Round 62 — derive is_material so synthetic test lines that opt
    # into is_over (a "fail this row" probe) also satisfy the
    # is_over+is_material Watchlist filter without each caller having
    # to set it manually. Tests that need a specifically immaterial
    # is_over row should set fields on the returned dataclass via
    # dataclasses.replace.
    is_material = abs(b - y) >= Decimal("100")
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
        is_material=is_material,
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
    faculty_budget: dict[str, Decimal] = {}
    faculty_ytd: dict[str, Decimal] = {}
    for ln in lines:
        key = ln.faculty or "Unknown"
        faculty_counts[key] = faculty_counts.get(key, 0) + 1
        faculty_budget[key] = faculty_budget.get(key, Decimal("0")) + ln.budget
        faculty_ytd[key] = faculty_ytd.get(key, Decimal("0")) + ln.ytd
    faculty_used_pct: dict[str, Decimal] = {
        k: (faculty_ytd[k] / faculty_budget[k] * Decimal("100"))
        if faculty_budget[k] != Decimal("0")
        else Decimal("0")
        for k in faculty_counts
    }
    total_budget = sum((ln.budget for ln in lines), Decimal("0"))
    total_ytd = sum((ln.ytd for ln in lines), Decimal("0"))
    return ReportSummary(
        lines=lines,
        faculty_counts=faculty_counts,
        over_budget_lines=over_budget_lines,
        total_budget=total_budget,
        total_ytd=total_ytd,
        output_path=output_path,
        faculty_budget=faculty_budget,
        faculty_ytd=faculty_ytd,
        faculty_used_pct=faculty_used_pct,
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

    def test_requires_feature_is_none_round_15(self) -> None:
        """Round 15 temporary free-tier setting: requires_feature must be None.

        Restore to "sub_program" when paid tier resumes — see CLAUDE.md Round 15
        and docs/03_ROADMAP.md.
        """
        assert SubProgramBudgetReportTool.requires_feature is None


# ---------------------------------------------------------------------------
# 2. Inputs
# ---------------------------------------------------------------------------


class TestInputs:
    def test_inputs_has_five_items(self) -> None:
        """Round 45 Phase A — five inputs: report file, optional comments
        file, Revenue threshold, Expense threshold, materiality dollar.
        """
        assert len(SubProgramBudgetReportTool.inputs) == 5

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

    def test_third_input_is_revenue_threshold(self) -> None:
        """Round 21 — third input is the Revenue over-budget threshold."""
        ri = SubProgramBudgetReportTool.inputs[2]
        assert isinstance(ri, RangeInput)
        assert ri.key == "revenue_threshold"
        assert ri.default == 101.0
        assert ri.live is True
        assert "revenue" in ri.label.lower()

    def test_fourth_input_is_expense_threshold(self) -> None:
        """Round 21 — fourth input is the Expense over-budget threshold."""
        ri = SubProgramBudgetReportTool.inputs[3]
        assert isinstance(ri, RangeInput)
        assert ri.key == "expense_threshold"
        assert ri.default == 101.0
        assert ri.live is True
        assert "expense" in ri.label.lower()

    def test_output_is_none(self) -> None:
        """No output file picker — path is auto-derived beside the source PDF."""
        assert SubProgramBudgetReportTool.output is None


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
                    # no output_file — path is auto-derived
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
                },
                _noop_progress,
            )
        assert result.table_columns is not None
        keys = [col["key"] for col in result.table_columns]
        # Round 45 Phase A — variance replaces remaining + used_pct as
        # the headline numerics. Round 56 dropped the pacing column.
        assert keys == [
            "sub_program",
            "account",
            "description",
            "budget",
            "ytd",
            "variance_amount",
            "variance_pct",
        ]

    def test_output_path_set(self, tmp_path: Path) -> None:
        tool = SubProgramBudgetReportTool()
        out = tmp_path / "out.xlsx"
        summary = _make_summary(output_path=out)
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                },
                _noop_progress,
            )
        assert result.output_path == out

    def test_output_path_auto_derived(self, tmp_path: Path) -> None:
        """When output_file is not supplied, run() auto-derives the path from report_file."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["output_file"] = kwargs.get("output_file")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                },
                _noop_progress,
            )
        out = captured.get("output_file")
        assert out is not None
        name = str(out)
        assert "Annual_SubProgram_" in name
        assert name.endswith(".xlsx")


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
                },
                _noop_progress,
            )
        assert result.table_rows is not None
        row = result.table_rows[0]
        assert row["_bg"] is not None
        assert HL_MISMATCH in row["_bg"]

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

        def fake_generate(**kwargs: Any) -> ReportSummary:
            captured["comments_file"] = kwargs.get("comments_file")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
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

        def fake_generate(**kwargs: Any) -> ReportSummary:
            captured["comments_file"] = kwargs.get("comments_file")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            result = tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "comments_file": "",  # empty string = not supplied
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

    def test_help_text_mentions_watchlist(self) -> None:
        # Round 62 — help text rewritten. Faculty rail was dropped in
        # Round 55; the new copy describes the Watchlist tab + Status
        # pill instead.
        ht = SubProgramBudgetReportTool.help_text.lower()
        assert "watchlist" in ht
        assert "status pill" in ht


# ---------------------------------------------------------------------------
# 8. Registry
# ----------------------------------------


# ---------------------------------------------------------------------------
# 9. clear() resets session state
# ---------------------------------------------------------------------------


class TestClearResetsState:
    def test_clear_method_resets_state(self, tmp_path: Path) -> None:
        """After populating all three session-state attributes, clear() must
        set them back to None."""
        from decimal import Decimal

        from tools.sub_program.logic import ReportSummary

        tool = SubProgramBudgetReportTool()

        summary = ReportSummary(
            lines=[],
            faculty_counts={},
            over_budget_lines=[],
            total_budget=Decimal("0"),
            total_ytd=Decimal("0"),
            output_path=tmp_path / "output.xlsx",
            faculty_budget={},
            faculty_ytd={},
            faculty_used_pct={},
        )
        tool._last_summary = summary
        # Round 51 Phase D — override is now a 4-tuple
        # (notes, driver, outlook, action).
        tool._commentary_overrides = {"4001": ("A note", "", "", "")}
        tool._last_output_path = tmp_path / "output.xlsx"

        tool.clear()

        assert tool._last_summary is None
        assert tool._commentary_overrides is None
        assert tool._last_output_path is None


# ---------------------------------------------------------------------------
# 10. Threshold input — new NumberInput (Fix 2)
# ---------------------------------------------------------------------------


class TestThresholdInput:
    """The over_budget_threshold NumberInput must be wired correctly into run()."""

    def test_default_threshold_is_101(self, tmp_path: Path) -> None:
        """When no threshold is supplied, generate_report receives 101.0."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["threshold"] = kwargs.get("over_budget_threshold")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run({"report_file": str(tmp_path / "report.pdf")}, _noop_progress)
        assert captured["threshold"] == 101.0

    def test_custom_threshold_passed_to_logic(self, tmp_path: Path) -> None:
        """User-supplied threshold is forwarded to generate_report."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["threshold"] = kwargs.get("over_budget_threshold")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "over_budget_threshold": "115.0",
                },
                _noop_progress,
            )
        assert captured["threshold"] == 115.0

    def test_threshold_in_banner_text(self, tmp_path: Path) -> None:
        """Banner text must mention the threshold percentage."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {"report_file": str(tmp_path / "report.pdf")},
                _noop_progress,
            )
        # Default threshold 101% must appear in banner
        assert "101" in result.banner_text

    def test_zero_threshold_string_defaults_to_101(self, tmp_path: Path) -> None:
        """A threshold value of exactly '0' (falsy) defaults to 101.0."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["threshold"] = kwargs.get("over_budget_threshold")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "over_budget_threshold": "0",
                },
                _noop_progress,
            )
        assert captured["threshold"] == 101.0

    def test_over_row_style_uses_over_flag(self, tmp_path: Path) -> None:
        """_row_style returns pink background only when _over is True."""
        tool = SubProgramBudgetReportTool()
        over_line = _make_line("4001", budget="5000", ytd="7000", is_over=True)
        normal_line = _make_line("5001", budget="5000", ytd="2000", is_over=False)
        summary = _make_summary(
            lines=[over_line, normal_line],
            over_budget_lines=[over_line],
        )
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {"report_file": str(tmp_path / "report.pdf")},
                _noop_progress,
            )
        assert result.table is not None
        row_style = result.table.row_style
        assert row_style is not None
        # Over-budget row must get pink background
        assert result.table_rows is not None
        over_row = result.table_rows[0]
        normal_row = result.table_rows[1]
        assert over_row.get("_over") is True
        assert normal_row.get("_over") is False
        over_style = row_style(over_row)
        normal_style = row_style(normal_row)
        assert over_style.get("background") is not None and HL_MISMATCH in over_style.get(
            "background", ""
        )
        assert normal_style == {}


# ---------------------------------------------------------------------------
# 11. Two-phase preview + export
# ---------------------------------------------------------------------------


class TestTwoPhasePreviewExport:
    """Tests for the threshold slider + deferred export workflow."""

    def test_run_caches_summary_and_threshold(self, tmp_path: Path) -> None:
        """After run(), _cached_summary is populated and _cached_threshold matches input."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "over_budget_threshold": "115.0",
                },
                _noop_progress,
            )
        assert tool._cached_summary is not None
        assert tool._cached_threshold == 115.0

    def test_run_does_not_write_xlsx(self, tmp_path: Path) -> None:
        """run() must not write any XLSX — _last_output_path stays None."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            tool.run(
                {"report_file": str(tmp_path / "report.pdf")},
                _noop_progress,
            )
        # No XLSX written; _last_output_path only set by _export_xlsx.
        assert tool._last_output_path is None

    def test_run_generate_report_called_with_write_xlsx_false(self, tmp_path: Path) -> None:
        """run() must call generate_report with write_xlsx=False."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["write_xlsx"] = kwargs.get("write_xlsx")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run(
                {"report_file": str(tmp_path / "report.pdf")},
                _noop_progress,
            )
        assert captured["write_xlsx"] is False

    def test_run_banner_contains_preview_hint(self, tmp_path: Path) -> None:
        """Preview mode banner must mention the Export to Excel hint."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        with patch("tools.sub_program.frame.logic.generate_report", return_value=summary):
            result = tool.run(
                {"report_file": str(tmp_path / "report.pdf")},
                _noop_progress,
            )
        assert "Export to Excel" in result.banner_text

    def test_preview_update_returns_new_tool_result(self, tmp_path: Path) -> None:
        """preview_update returns a ToolResult when summary is cached."""
        tool = SubProgramBudgetReportTool()
        # used_pct is 50 in _make_line; set is_over False but we want pct > threshold
        from decimal import Decimal

        over_line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Test",
            budget=Decimal("5000"),
            ytd=Decimal("5200"),
            remaining=Decimal("-200"),
            used_pct=Decimal("104.0"),
            faculty="Curriculum",
            is_over=False,  # parser's naive flag; preview will recompute
        )
        normal_line = _make_line("5001", is_over=False)
        summary = _make_summary(lines=[over_line, normal_line])
        tool._cached_summary = summary
        tool._cached_threshold = 101.0

        result = tool.preview_update("over_budget_threshold", 50.0)

        assert result is not None
        # With threshold=50, over_line (used_pct=104) should be flagged over.
        assert result.table_rows is not None
        over_row = result.table_rows[0]
        assert over_row.get("_over") is True

    def test_preview_update_threshold_low_marks_all_over(self) -> None:
        """Very low threshold flags all lines as over-budget."""
        tool = SubProgramBudgetReportTool()
        from decimal import Decimal

        lines = [
            SubProgramLine(
                sub_program="4001",
                account="Expenditure",
                description="A",
                budget=Decimal("1000"),
                ytd=Decimal("500"),
                remaining=Decimal("500"),
                used_pct=Decimal("50.0"),
                faculty="Curriculum",
                is_over=False,
            ),
            SubProgramLine(
                sub_program="5001",
                account="Expenditure",
                description="B",
                budget=Decimal("2000"),
                ytd=Decimal("1800"),
                remaining=Decimal("200"),
                used_pct=Decimal("90.0"),
                faculty="Wellbeing",
                is_over=False,
            ),
        ]
        summary = _make_summary(lines=lines)
        tool._cached_summary = summary
        tool._cached_threshold = 101.0

        # Threshold=0 -> all lines (50% and 90%) exceed 0.
        result = tool.preview_update("over_budget_threshold", 0.0)
        assert result is not None
        assert result.table_rows is not None
        assert all(row["_over"] for row in result.table_rows)

        # Threshold=9999 -> no lines exceed it.
        result2 = tool.preview_update("over_budget_threshold", 9999.0)
        assert result2 is not None
        assert result2.table_rows is not None
        assert all(not row["_over"] for row in result2.table_rows)

    def test_preview_update_returns_none_when_no_cached_summary(self) -> None:
        """preview_update returns None when no summary has been cached (no run yet)."""
        tool = SubProgramBudgetReportTool()
        assert tool._cached_summary is None
        result = tool.preview_update("over_budget_threshold", 80.0)
        assert result is None

    def test_preview_update_ignores_unknown_key(self) -> None:
        """preview_update returns None for an unrecognised input key."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        tool._cached_summary = summary
        result = tool.preview_update("some_other_key", 50.0)
        assert result is None

    def test_export_xlsx_writes_file(self, tmp_path: Path) -> None:
        """After run(), _export_xlsx writes the XLSX and sets _last_output_path."""
        import sys
        import types
        from unittest.mock import MagicMock

        tool = SubProgramBudgetReportTool()
        lines = [_make_line("4001")]
        out_path = tmp_path / "output.xlsx"
        summary = _make_summary(lines=lines, output_path=out_path)
        tool._cached_summary = summary
        tool._cached_threshold = 101.0

        # Inject a stub tkinter.messagebox so the local `import` inside
        # _export_xlsx succeeds even when tkinter is absent (Linux CI).
        mb_stub = types.ModuleType("tkinter.messagebox")
        mb_stub.showinfo = MagicMock()  # type: ignore[attr-defined]
        mb_stub.showerror = MagicMock()  # type: ignore[attr-defined]

        tk_stub = sys.modules.get("tkinter")
        existing_mb = sys.modules.get("tkinter.messagebox")
        if tk_stub is None:
            tk_stub = types.ModuleType("tkinter")
            sys.modules["tkinter"] = tk_stub
        sys.modules["tkinter.messagebox"] = mb_stub

        try:
            with patch("tools.sub_program.frame.logic._write_xlsx") as mock_write:
                tool._export_xlsx()
        finally:
            if existing_mb is None:
                sys.modules.pop("tkinter.messagebox", None)

        mock_write.assert_called_once()
        call_kwargs = mock_write.call_args
        assert call_kwargs is not None
        assert tool._last_output_path == out_path

    def test_export_xlsx_without_run_shows_info(self) -> None:
        """_export_xlsx without a prior run shows a messagebox and does not write."""
        import sys
        import types
        from unittest.mock import MagicMock

        tool = SubProgramBudgetReportTool()
        assert tool._cached_summary is None

        # Inject a stub tkinter.messagebox so the local `import` inside
        # _export_xlsx succeeds even when tkinter is absent (Linux CI).
        mb_stub = types.ModuleType("tkinter.messagebox")
        mock_info = MagicMock()
        mb_stub.showinfo = mock_info  # type: ignore[attr-defined]
        mb_stub.showerror = MagicMock()  # type: ignore[attr-defined]

        tk_stub = sys.modules.get("tkinter")
        existing_mb = sys.modules.get("tkinter.messagebox")
        if tk_stub is None:
            tk_stub = types.ModuleType("tkinter")
            sys.modules["tkinter"] = tk_stub
        sys.modules["tkinter.messagebox"] = mb_stub

        try:
            with patch("tools.sub_program.frame.logic._write_xlsx") as mock_write:
                tool._export_xlsx()
        finally:
            if existing_mb is None:
                sys.modules.pop("tkinter.messagebox", None)

        mock_write.assert_not_called()
        mock_info.assert_called_once()

    def test_secondary_actions_no_edit_commentary_button(self) -> None:
        """Round 22a — 'Edit commentary...' button is removed.

        Commentary is now edited inline by clicking any row in the
        dashboard table (the row's ``on_row_click`` opens a small
        single-row editor).  The bulk-modal action is gone.
        """
        tool = SubProgramBudgetReportTool()
        actions = tool.secondary_actions()
        labels = [label for label, _ in actions]
        assert labels == ["Export to Excel", "Open output folder"]
        assert "Edit commentary..." not in labels

    def test_clear_resets_cached_summary_and_threshold(self) -> None:
        """clear() must reset _cached_summary to None and _cached_threshold to 101.0."""
        tool = SubProgramBudgetReportTool()
        tool._cached_summary = _make_summary()
        tool._cached_threshold = 55.0

        tool.clear()

        assert tool._cached_summary is None
        assert tool._cached_threshold == 101.0

    def test_run_uses_actual_threshold_value_not_clamped(self, tmp_path: Path) -> None:
        """run() must receive and cache the actual threshold value, even above slider max.

        The shell passes actual_var.get() (unclamped) via _input_cache.  Verify that
        a threshold of 200.0 (above the slider max of 120) is stored as-is.
        """
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        captured: dict[str, Any] = {}

        def fake_generate(**kwargs: Any) -> Any:
            captured["threshold"] = kwargs.get("over_budget_threshold")
            return summary

        with patch("tools.sub_program.frame.logic.generate_report", side_effect=fake_generate):
            tool.run(
                {
                    "report_file": str(tmp_path / "report.pdf"),
                    "over_budget_threshold": 200.0,
                },
                _noop_progress,
            )

        assert captured["threshold"] == 200.0, (
            f"Expected threshold 200.0 but got {captured['threshold']!r} — "
            "run() must not clamp the actual_var value"
        )
        assert tool._cached_threshold == 200.0

    def test_preview_update_with_above_range_value(self) -> None:
        """preview_update with threshold=200 recomputes is_over correctly.

        A line with used_pct=104% is NOT over-budget at threshold=200, so the
        result should have _over=False for that row.
        """
        from decimal import Decimal

        tool = SubProgramBudgetReportTool()
        over_line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Test",
            budget=Decimal("5000"),
            ytd=Decimal("5200"),
            remaining=Decimal("-200"),
            used_pct=Decimal("104.0"),
            faculty="Curriculum",
            is_over=True,
        )
        summary = _make_summary(lines=[over_line], over_budget_lines=[over_line])
        tool._cached_summary = summary
        tool._cached_threshold = 101.0

        # With threshold=200, used_pct=104 is below the threshold → not over.
        result = tool.preview_update("expense_threshold", 200.0)
        assert result is not None
        assert result.table_rows is not None
        row = result.table_rows[0]
        assert row.get("_over") is False, (
            "used_pct=104% should NOT be flagged over-budget at threshold=200"
        )
        assert tool._cached_threshold == 200.0


# ---------------------------------------------------------------------------
# Round 22a — inline commentary editor + comment sub-rows
# ---------------------------------------------------------------------------


class TestRound22aInlineCommentary:
    """Click-to-edit replaces the bulk Edit commentary modal.

    Verifies the visible behaviour of the new design without spinning up
    Tk (the inline editor itself uses Toplevel which would need a live
    display).  We test that:
    * "Edit commentary..." button is gone from the secondary action row.
    * Lines with non-empty ``commentary`` produce a "comment sub-row" in
      the rendered ``table_rows`` immediately after the parent data row.
    * Comment sub-rows carry the ``_is_comment_row`` flag and a description
      prefixed with the speech-bubble glyph.
    * Lines without commentary do NOT produce a sub-row.
    * The comment sub-row inherits the parent line's faculty + over flag
      so the existing rail filter and pink-fill paths keep grouping
      working visually.
    """

    def _line_with_commentary(
        self,
        sub_program: str,
        commentary: str,
        is_over: bool = False,
        commentary_driver: str = "",
        commentary_outlook: str = "",
        commentary_action: str = "",
    ) -> SubProgramLine:
        return SubProgramLine(
            sub_program=sub_program,
            account="Revenue",
            description=f"{sub_program} description",
            budget=Decimal("1000"),
            ytd=Decimal("500"),
            remaining=Decimal("500"),
            used_pct=Decimal("50"),
            faculty="Curriculum",
            is_over=is_over,
            commentary=commentary,
            commentary_driver=commentary_driver,
            commentary_outlook=commentary_outlook,
            commentary_action=commentary_action,
        )

    def test_comment_subrow_inserted_after_parent_with_commentary(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = self._line_with_commentary("4400", "Reviewed by council")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        # 1 data row + 1 sub-row = 2 entries.
        assert len(result.table_rows) == 2

        data_row, sub_row = result.table_rows
        assert data_row["sub_program"] == "4400"
        assert data_row.get("_is_comment_row") is False

        assert sub_row.get("_is_comment_row") is True
        # Speech-bubble + commentary text in the description column.
        assert "💬" in sub_row["description"]
        assert "Reviewed by council" in sub_row["description"]
        # Numeric columns blanked so the sub-row isn't read as data.
        # Round 45 Phase A — used_pct + remaining replaced by variance
        # on the headline. Round 56 dropped the pacing column entirely;
        # comment sub-rows blank all the remaining numeric columns.
        assert sub_row["budget"] == ""
        assert sub_row["ytd"] == ""
        assert sub_row["variance_amount"] == ""
        assert sub_row["variance_pct"] == ""
        # Faculty inheritance — keeps the rail filter grouping intact.
        assert sub_row["_faculty"] == "Curriculum"

    def test_no_subrow_for_line_without_commentary(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = self._line_with_commentary("4001", "")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        # Only the data row — no sub-row when commentary is empty.
        assert len(result.table_rows) == 1
        assert result.table_rows[0].get("_is_comment_row") is False

    def test_subrow_inherits_over_budget_flag(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = self._line_with_commentary("4400", "Looking into it", is_over=True)
        summary = _make_summary(lines=[line], over_budget_lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        sub_row = result.table_rows[1]
        # Inherits _over so the pink fill spans data + comment rows.
        assert sub_row.get("_over") is True

    def test_table_spec_has_on_row_click(self) -> None:
        """Round 22a — the dashboard table now wires a click handler."""
        tool = SubProgramBudgetReportTool()
        summary = _make_summary()
        result = tool._build_result(summary, preview=False)

        assert result.table is not None
        assert result.table.on_row_click is not None
        assert callable(result.table.on_row_click)

    def test_on_row_click_skips_comment_subrows(self) -> None:
        """Click handler must NOT pop the editor for comment sub-rows."""
        tool = SubProgramBudgetReportTool()
        line = self._line_with_commentary("4400", "Reviewed by council")
        summary = _make_summary(lines=[line])
        tool._cached_summary = summary  # required by the editor's guard
        result = tool._build_result(summary, preview=False)

        assert result.table is not None
        on_click = result.table.on_row_click
        assert on_click is not None

        # Synthetic click on the comment sub-row — should be a silent no-op.
        # (If the editor were opened we'd hit a Tk error since there's no
        # default root, so the test indirectly verifies early-return too.)
        on_click({"_is_comment_row": True, "sub_program": ""})

    def test_banner_names_the_single_over_line(self) -> None:
        """Round 22a — the banner now reads '4400 Photography (Revenue)
        — over by $X' rather than the cryptic '4400/Revenue' form.
        Round 62 — banner counts is_over+is_material; set the flag
        explicitly here since this synthetic line bypasses the
        recompute path."""
        tool = SubProgramBudgetReportTool()
        line = SubProgramLine(
            sub_program="4400",
            account="Revenue",
            description="Photography",
            budget=Decimal("4400"),
            ytd=Decimal("23613"),
            remaining=Decimal("-19213"),
            used_pct=Decimal("536.66"),
            faculty="Curriculum",
            is_over=True,
            is_material=True,
        )
        summary = _make_summary(lines=[line], over_budget_lines=[line])
        result = tool._build_result(summary, preview=False)

        # Description appears verbatim in the banner copy.
        assert "Photography" in result.banner_text
        assert "4400" in result.banner_text
        assert "Revenue" in result.banner_text
        assert "$19,213" in result.banner_text


# ---------------------------------------------------------------------------
# Round 22b — view tabs + Combined subsidy viz
# ---------------------------------------------------------------------------


class TestRound22bViewTabs:
    """Result now carries three tabs (Revenue / Expense / Combined).

    Revenue and Expense tabs are filtered slices of the main table_rows
    list (so click-to-edit + over-budget styling carry across).  The
    Combined tab is a synthetic per-sub-program aggregate that surfaces
    school-subsidised lines (Expense > Revenue) at the top, with a
    unicode bar in the 'Budget shape' column showing the
    Revenue-vs-subsidy split.
    """

    def _line(
        self,
        sp: str,
        account: str,
        budget: str,
        description: str = "",
    ) -> SubProgramLine:
        b = Decimal(budget)
        return SubProgramLine(
            sub_program=sp,
            account=account,
            description=description or f"{account} {sp}",
            budget=b,
            ytd=b / 2,
            remaining=b / 2,
            used_pct=Decimal("50"),
            faculty="Curriculum",
            is_over=False,
        )

    def test_result_has_four_tabs(self) -> None:
        """Round 64 — Preview tab added at index 3 showing the XLSX
        Sub Program Report layout. Watchlist=0, Revenue=1, Expense=2,
        Preview=3. Pre-R64 there were 3 tabs (Round 55 simplification
        dropped Summary + Bridge).
        """
        tool = SubProgramBudgetReportTool()
        lines = [
            self._line("1251", "Revenue", "1000"),
            self._line("4001", "Expenditure", "5000"),
        ]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)

        assert result.table_tabs is not None
        assert len(result.table_tabs) == 4

        labels = [label for label, _ in result.table_tabs]
        assert "Watchlist" in labels[0]  # default landing
        assert "Revenue" in labels[1]
        assert "Expense" in labels[2]
        assert "Preview" in labels[3]
        # Summary and Bridge no longer in any tab label.
        for lbl in labels:
            assert "Summary" not in lbl
            assert "Bridge" not in lbl

    def test_preview_tab_has_xlsx_layout(self) -> None:
        """Round 64 — Preview tab columns match the XLSX Sub Program
        Report sheet: CODE, Program name, Status, Funds, Budget Rev,
        Budget Exp, Rev YTD, Exp YTD, Orders, Avail Bal YTD, Avail %,
        Rev %, Comments (13 columns)."""
        tool = SubProgramBudgetReportTool()
        lines = [
            self._line("1251", "Revenue", "1000"),
            self._line("4001", "Expenditure", "5000"),
        ]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)

        assert result.table_tabs is not None
        preview_label, preview_spec = result.table_tabs[3]
        assert "Preview" in preview_label
        col_keys = [c["key"] for c in preview_spec.columns]
        assert col_keys == [
            "code",
            "name",
            "status",
            "funds",
            "budget_rev",
            "budget_exp",
            "rev_ytd",
            "exp_ytd",
            "orders",
            "avail",
            "avail_pct",
            "rev_pct",
            "comments",
        ]
        # One row per sub-program (1251 + 4001 = 2 rows).
        assert len(preview_spec.rows) == 2
        codes = sorted(r["code"] for r in preview_spec.rows)
        assert codes == ["1251", "4001"]

    def test_revenue_tab_only_revenue_rows(self) -> None:
        tool = SubProgramBudgetReportTool()
        lines = [
            self._line("1251", "Revenue", "1000"),
            self._line("4001", "Expenditure", "5000"),
            self._line("1320", "Revenue", "2000"),
        ]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)
        assert result.table_tabs is not None

        # Round 55 — Watchlist at 0, Revenue at 1.
        rev_label, rev_spec = result.table_tabs[1]
        assert "Revenue" in rev_label
        # All rows in the Revenue tab must be Revenue (no Expenditure leakage).
        for row in rev_spec.rows:
            if row.get("_is_comment_row"):
                continue
            assert row["account"] == "Revenue"
        # Both Revenue lines present.
        sub_programs = {r["sub_program"] for r in rev_spec.rows if not r.get("_is_comment_row")}
        assert sub_programs == {"1251", "1320"}

    def test_expense_tab_only_expense_rows(self) -> None:
        tool = SubProgramBudgetReportTool()
        lines = [
            self._line("1251", "Revenue", "1000"),
            self._line("4001", "Expenditure", "5000"),
        ]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)
        assert result.table_tabs is not None

        # Round 55 — Expense now at index 2 (after Watchlist + Revenue).
        exp_label, exp_spec = result.table_tabs[2]
        assert "Expense" in exp_label
        for row in exp_spec.rows:
            if row.get("_is_comment_row"):
                continue
            assert row["account"] == "Expenditure"

    def test_watchlist_is_default_tab(self) -> None:
        """Round 55: Watchlist is index 0 so users land on the
        actionable view rather than the legacy Summary card."""
        tool = SubProgramBudgetReportTool()
        lines = [self._line("4001", "Expenditure", "5000")]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)
        assert result.table_tabs is not None
        first_label, _ = result.table_tabs[0]
        assert "Watchlist" in first_label

    def test_no_side_rail(self) -> None:
        """Round 55: faculty rail dropped — side_rail is None."""
        tool = SubProgramBudgetReportTool()
        lines = [self._line("4001", "Expenditure", "5000")]
        summary = _make_summary(lines=lines)
        result = tool._build_result(summary, preview=False)
        assert result.side_rail is None

    def test_log_default_collapsed_attribute(self) -> None:
        """Round 55: tool opts in to the shell's collapsed-log default
        via ``log_default_collapsed = True`` class attribute."""
        assert SubProgramBudgetReportTool.log_default_collapsed is True


# ---------------------------------------------------------------------------
# Round 51 Phase D — structured commentary inline display
# ---------------------------------------------------------------------------


class TestStructuredCommentaryInlineDisplay:
    """The sub-row description carries the speech-bubble glyph + an
    optional ``[Action: <value>]`` tag (when set) + the freeform notes.
    Driver / Outlook are not shown inline — they live in the editor.
    """

    def _line_full(
        self,
        sub_program: str = "4400",
        notes: str = "",
        driver: str = "",
        outlook: str = "",
        action: str = "",
        is_over: bool = False,
    ) -> SubProgramLine:
        return SubProgramLine(
            sub_program=sub_program,
            account="Revenue",
            description=f"{sub_program} description",
            budget=Decimal("1000"),
            ytd=Decimal("500"),
            remaining=Decimal("500"),
            used_pct=Decimal("50"),
            faculty="Curriculum",
            is_over=is_over,
            commentary=notes,
            commentary_driver=driver,
            commentary_outlook=outlook,
            commentary_action=action,
        )

    def test_action_tag_inline_when_action_set(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = self._line_full(notes="Reviewed by council", action="Investigate")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        # 1 data row + 1 sub-row.
        assert len(result.table_rows) == 2
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  [Action: Investigate] Reviewed by council"

    def test_no_action_tag_when_action_blank(self) -> None:
        """Empty action ('' = not categorised) suppresses the tag —
        keeps the inline view tight when only Notes is set."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(notes="Reviewed by council")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        assert len(result.table_rows) == 2
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  Reviewed by council"

    def test_action_none_literal_renders_inline(self) -> None:
        """Literal 'None' Action (user reviewed, no action) is distinct
        from '' (not categorised) — it still gets the inline tag."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(notes="all good", action="None")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  [Action: None] all good"

    def test_subrow_appears_for_dropdown_only_no_notes(self) -> None:
        """Setting only a structured field (e.g. Driver) without Notes
        should still surface the speech bubble — otherwise the user
        loses sight of the categorisation."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(driver="Ongoing")  # no notes, no action
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        # 1 data row + 1 sub-row — categorisation alone is enough to
        # surface the row.
        assert len(result.table_rows) == 2

    def test_subrow_falls_back_to_driver_when_no_action(self) -> None:
        """Round 1 fix: when Action is blank but Driver is set, the
        speech bubble surfaces ``[Driver: X]`` so the row never looks
        empty. Without this the categorisation is invisible until the
        user reopens the editor."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(driver="Ongoing")  # no notes, no action
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  [Driver: Ongoing]"

    def test_subrow_falls_back_to_outlook_when_no_action_or_driver(self) -> None:
        """Final fallback in the chain — when only Outlook is set, it
        surfaces inline so the row isn't empty."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(outlook="Improving")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  [Outlook: Improving]"

    def test_subrow_action_takes_priority_over_driver(self) -> None:
        """When BOTH Action and Driver are set, the inline tag shows
        Action (the most action-relevant) — Driver is only the
        fallback. The user can see the categorisation in the editor."""
        tool = SubProgramBudgetReportTool()
        line = self._line_full(driver="Ongoing", action="Investigate")
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        sub_row = result.table_rows[1]
        assert sub_row["description"] == "   💬  [Action: Investigate]"

    def test_no_subrow_when_all_four_fields_blank(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = self._line_full()  # everything blank
        summary = _make_summary(lines=[line])
        result = tool._build_result(summary, preview=False)

        assert result.table_rows is not None
        # Only the data row — no sub-row when nothing is categorised.
        assert len(result.table_rows) == 1


class TestStructuredCommentaryOverrideMerge:
    """The 4-tuple override applies through ``_merge_commentary_overrides``."""

    def test_merge_applies_full_tuple(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Curriculum",
            budget=Decimal("1000"),
            ytd=Decimal("500"),
            remaining=Decimal("500"),
            used_pct=Decimal("50"),
            faculty="Curriculum",
            is_over=False,
        )
        summary = _make_summary(lines=[line])
        tool._commentary_overrides = {
            "4001": ("new notes", "Ongoing", "Improving", "Monitor"),
        }
        merged = tool._merge_commentary_overrides(summary)
        ln = merged.lines[0]
        assert ln.commentary == "new notes"
        assert ln.commentary_driver == "Ongoing"
        assert ln.commentary_outlook == "Improving"
        assert ln.commentary_action == "Monitor"

    def test_merge_skips_lines_without_override(self) -> None:
        tool = SubProgramBudgetReportTool()
        line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Curriculum",
            budget=Decimal("1000"),
            ytd=Decimal("500"),
            remaining=Decimal("500"),
            used_pct=Decimal("50"),
            faculty="Curriculum",
            is_over=False,
            commentary="existing",
            commentary_action="Monitor",
        )
        summary = _make_summary(lines=[line])
        tool._commentary_overrides = {"DIFFERENT_SP": ("x", "x", "x", "x")}
        merged = tool._merge_commentary_overrides(summary)
        ln = merged.lines[0]
        assert ln.commentary == "existing"
        assert ln.commentary_action == "Monitor"

    def test_merge_refreshes_over_budget_lines(self) -> None:
        """Round 1 fix: ``over_budget_lines`` is re-derived from the
        updated ``lines`` so downstream consumers (banner copy, exports)
        see freshly-edited commentary on the over-budget subset, not
        stale references to the pre-merge instances."""
        tool = SubProgramBudgetReportTool()
        # An over-budget line — should be in over_budget_lines before
        # AND after the merge, but its commentary must be updated.
        line = SubProgramLine(
            sub_program="4001",
            account="Expenditure",
            description="Curriculum",
            budget=Decimal("1000"),
            ytd=Decimal("1500"),  # over
            remaining=Decimal("-500"),
            used_pct=Decimal("150"),
            faculty="Curriculum",
            is_over=True,
            commentary="",  # no commentary pre-merge
        )
        summary = _make_summary(lines=[line], over_budget_lines=[line])
        tool._commentary_overrides = {
            "4001": ("now reviewed", "Ongoing", "", "Investigate"),
        }
        merged = tool._merge_commentary_overrides(summary)
        # over_budget_lines points at the UPDATED instance, not the stale one.
        assert len(merged.over_budget_lines) == 1
        ob = merged.over_budget_lines[0]
        assert ob.commentary == "now reviewed"
        assert ob.commentary_driver == "Ongoing"
        assert ob.commentary_action == "Investigate"
