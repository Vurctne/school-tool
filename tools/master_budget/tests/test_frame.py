"""Tests for MasterBudgetTool frame (tools/master_budget/frame.py).

All logic.import_expense_sub_program calls are mocked so no real xlsx
fixtures are required.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

from toolkit.base_tool import FileInput, ToolResult
from tools.master_budget.frame import MasterBudgetTool
from tools.master_budget.logic import ImportSummary

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _noop_progress(pct: int, msg: str) -> None:
    pass


def _make_summary(
    *,
    mismatch_codes: list[str] | None = None,
    source_only_codes: list[str] | None = None,
    matched_rows: int = 5,
    matched_cells: int = 20,
) -> ImportSummary:
    return ImportSummary(
        matched_rows=matched_rows,
        matched_cells=matched_cells,
        mismatch_codes=mismatch_codes or [],
        source_only_codes=source_only_codes or [],
        output_path=Path("/tmp/output.xlsm"),
    )


def _run_with_mock_summary(summary: ImportSummary) -> ToolResult:
    """Run the tool with import_expense_sub_program mocked to return *summary*."""
    tool = MasterBudgetTool()
    paths: dict[str, Any] = {
        "expense_file": Path("/tmp/expense.xlsx"),
        "master_file": Path("/tmp/master.xlsm"),
        "output_file": Path("/tmp/output.xlsm"),
    }
    with patch(
        "tools.master_budget.frame.logic.import_expense_sub_program",
        return_value=summary,
    ):
        return tool.run(paths, _noop_progress)


# ---------------------------------------------------------------------------
# Structural conformance
# ---------------------------------------------------------------------------


class TestStructure:
    def test_has_required_class_attributes(self) -> None:
        tool = MasterBudgetTool()
        assert tool.id == "master-budget"
        assert tool.group == "Budget"
        assert tool.label == "Master Budget Compass Autofill"
        assert tool.short == "MB"
        assert tool.order == 10
        assert tool.primary_button == "Generate budget workbook"
        assert tool.pdf_template is None
        assert tool.pdf_body is None

    def test_has_run_method(self) -> None:
        tool = MasterBudgetTool()
        assert callable(tool.run)

    def test_has_secondary_actions_method(self) -> None:
        tool = MasterBudgetTool()
        assert callable(tool.secondary_actions)

    def test_help_text_exists_and_non_empty(self) -> None:
        tool = MasterBudgetTool()
        assert isinstance(tool.help_text, str)
        assert len(tool.help_text.strip()) > 0

    def test_inputs_declares_two_file_inputs(self) -> None:
        tool = MasterBudgetTool()
        assert len(tool.inputs) == 2
        for inp in tool.inputs:
            assert isinstance(inp, FileInput)

    def test_input_keys(self) -> None:
        tool = MasterBudgetTool()
        keys = [inp.key for inp in tool.inputs]
        assert "expense_file" in keys
        assert "master_file" in keys

    def test_output_is_auto_computed(self) -> None:
        """Output path is derived from the master_file input inside ``run()`` —
        no OutputSpec is declared, so the shell doesn't render an output picker.
        """
        tool = MasterBudgetTool()
        assert tool.output is None


# ---------------------------------------------------------------------------
# secondary_actions
# ---------------------------------------------------------------------------


class TestSecondaryActions:
    def test_returns_open_output_folder_action(self) -> None:
        """Single secondary action: Open output folder, which reveals the
        most recently generated workbook in Explorer/Finder/xdg-open."""
        tool = MasterBudgetTool()
        actions = tool.secondary_actions()
        assert len(actions) == 1
        label, cb = actions[0]
        assert label == "Open output folder"
        assert callable(cb)

    def test_open_output_folder_handles_no_prior_run(self) -> None:
        """Clicking the button before any Generate run must not raise — it
        shows an info dialog (or silently no-ops in headless environments)."""
        tool = MasterBudgetTool()
        _, cb = tool.secondary_actions()[0]
        tool._last_output_path = None
        cb()  # must not raise


# ---------------------------------------------------------------------------
# run() — success path
# ---------------------------------------------------------------------------


class TestRunSuccess:
    def test_status_success_when_no_mismatches(self) -> None:
        summary = _make_summary()
        result = _run_with_mock_summary(summary)
        assert result.status == "success"

    def test_banner_level_ok_when_no_mismatches(self) -> None:
        summary = _make_summary()
        result = _run_with_mock_summary(summary)
        assert result.banner_level == "ok"

    def test_banner_text_contains_row_and_cell_counts(self) -> None:
        summary = _make_summary(matched_rows=7, matched_cells=42)
        result = _run_with_mock_summary(summary)
        assert "7" in result.banner_text
        assert "42" in result.banner_text

    def test_output_path_propagated(self) -> None:
        summary = _make_summary()
        result = _run_with_mock_summary(summary)
        assert result.output_path == Path("/tmp/output.xlsm")

    def test_log_lines_populated(self) -> None:
        summary = _make_summary()
        result = _run_with_mock_summary(summary)
        assert len(result.log_lines) > 0


# ---------------------------------------------------------------------------
# run() — warning path (mismatches present)
# ---------------------------------------------------------------------------


class TestRunWarning:
    def test_status_warning_when_mismatch_codes(self) -> None:
        summary = _make_summary(mismatch_codes=["71000", "72000"])
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_banner_level_warning_when_mismatch_codes(self) -> None:
        summary = _make_summary(mismatch_codes=["71000"])
        result = _run_with_mock_summary(summary)
        assert result.banner_level == "warning"

    def test_banner_text_mentions_mismatch_count(self) -> None:
        summary = _make_summary(mismatch_codes=["71000", "72000", "73000"])
        result = _run_with_mock_summary(summary)
        assert "3" in result.banner_text

    def test_status_warning_when_source_only_codes(self) -> None:
        summary = _make_summary(source_only_codes=["80000"])
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_status_warning_when_both_code_lists_non_empty(self) -> None:
        summary = _make_summary(
            mismatch_codes=["71000"],
            source_only_codes=["80000"],
        )
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_mismatch_codes_appear_in_log(self) -> None:
        summary = _make_summary(mismatch_codes=["71000"])
        result = _run_with_mock_summary(summary)
        all_text = " ".join(ll.text for ll in result.log_lines)
        assert "71000" in all_text

    def test_source_only_codes_appear_in_log(self) -> None:
        summary = _make_summary(source_only_codes=["80000"])
        result = _run_with_mock_summary(summary)
        all_text = " ".join(ll.text for ll in result.log_lines)
        assert "80000" in all_text


# ---------------------------------------------------------------------------
# run() — error path (logic raises)
# ---------------------------------------------------------------------------


class TestRunError:
    def test_status_error_when_logic_raises(self) -> None:
        tool = MasterBudgetTool()
        paths: dict[str, Any] = {
            "expense_file": Path("/tmp/expense.xlsx"),
            "master_file": Path("/tmp/master.xlsm"),
            "output_file": Path("/tmp/output.xlsm"),
        }
        with patch(
            "tools.master_budget.frame.logic.import_expense_sub_program",
            side_effect=RuntimeError("corrupted file"),
        ):
            result = tool.run(paths, _noop_progress)

        assert result.status == "error"

    def test_banner_level_danger_when_logic_raises(self) -> None:
        tool = MasterBudgetTool()
        paths: dict[str, Any] = {
            "expense_file": Path("/tmp/expense.xlsx"),
            "master_file": Path("/tmp/master.xlsm"),
            "output_file": Path("/tmp/output.xlsm"),
        }
        with patch(
            "tools.master_budget.frame.logic.import_expense_sub_program",
            side_effect=ValueError("bad input"),
        ):
            result = tool.run(paths, _noop_progress)

        assert result.banner_level == "danger"

    def test_traceback_appears_in_log_lines_on_error(self) -> None:
        tool = MasterBudgetTool()
        paths: dict[str, Any] = {
            "expense_file": Path("/tmp/expense.xlsx"),
            "master_file": Path("/tmp/master.xlsm"),
            "output_file": Path("/tmp/output.xlsm"),
        }
        with patch(
            "tools.master_budget.frame.logic.import_expense_sub_program",
            side_effect=RuntimeError("boom"),
        ):
            result = tool.run(paths, _noop_progress)

        assert len(result.log_lines) > 0
        all_text = " ".join(ll.text for ll in result.log_lines)
        assert "boom" in all_text


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class TestRegistry:
    def test_tool_is_registered_after_import(self) -> None:
        # Importing the package triggers register(MasterBudgetTool).
        import tools.master_budget  # noqa: F401  (side-effect: registers the tool)
        from toolkit.registry import _registered

        registered_ids = {cls.id for cls in _registered}
        assert "master-budget" in registered_ids

    def test_tool_appears_in_all_tools(self) -> None:
        from toolkit.registry import all_tools

        ids = [t.id for t in all_tools()]
        assert "master-budget" in ids
