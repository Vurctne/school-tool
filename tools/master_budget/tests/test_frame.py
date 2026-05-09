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
    mismatch_account_codes: list[str] | None = None,
    mismatch_subprogram_codes: list[str] | None = None,
    source_only_account_codes: list[str] | None = None,
    source_only_subprogram_codes: list[str] | None = None,
    matched_rows: int = 5,
    matched_cells: int = 20,
) -> ImportSummary:
    return ImportSummary(
        matched_rows=matched_rows,
        matched_cells=matched_cells,
        mismatch_account_codes=mismatch_account_codes or [],
        mismatch_subprogram_codes=mismatch_subprogram_codes or [],
        source_only_account_codes=source_only_account_codes or [],
        source_only_subprogram_codes=source_only_subprogram_codes or [],
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

    def test_inputs_declares_three_file_inputs(self) -> None:
        # Round 27 — third FileInput ``master_file_b`` enables Compare mode.
        # Keep all three as FileInput; the run() method dispatches by which
        # combination is filled.
        tool = MasterBudgetTool()
        assert len(tool.inputs) == 3
        for inp in tool.inputs:
            assert isinstance(inp, FileInput)

    def test_input_keys(self) -> None:
        tool = MasterBudgetTool()
        keys = [inp.key for inp in tool.inputs]
        assert "expense_file" in keys
        assert "master_file" in keys
        assert "master_file_b" in keys

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
        """Round 27 — secondary actions: 'Open output folder' (Autofill mode
        result) + 'Export comparison Excel' (Compare mode result).
        """
        tool = MasterBudgetTool()
        actions = tool.secondary_actions()
        assert len(actions) == 2
        labels = [label for label, _ in actions]
        assert labels[0] == "Open output folder"
        assert labels[1] == "Export comparison Excel"
        for _, cb in actions:
            assert callable(cb)

    def test_alt_run_buttons_exposes_compare(self) -> None:
        """Round 28 — Compare lives on its own primary-style button via
        alt_run_buttons(), independent of the Generate primary."""
        tool = MasterBudgetTool()
        alt = tool.alt_run_buttons()
        assert len(alt) == 1
        label, cb = alt[0]
        assert label == "Compare two budgets"
        assert callable(cb)

    def test_open_output_folder_handles_no_prior_run(self) -> None:
        """Clicking the button before any Generate run must not raise — it
        shows an info dialog (or silently no-ops in headless environments)."""
        tool = MasterBudgetTool()
        _, cb = tool.secondary_actions()[0]
        tool._last_output_path = None
        cb()  # must not raise

    def test_export_compare_handles_no_prior_compare(self) -> None:
        """Clicking 'Export comparison Excel' before any Compare run must not
        raise — it shows an info dialog (or silently no-ops in headless)."""
        tool = MasterBudgetTool()
        _, cb = tool.secondary_actions()[1]
        tool._last_compare_summary = None
        cb()  # must not raise

    def test_run_compare_missing_master_a_returns_friendly_error(self) -> None:
        """Round 39 — Round 28's run_compare entry-point was untested.
        With Master Budget A blank, return a friendly error result."""
        tool = MasterBudgetTool()
        result = tool.run_compare({"master_file_b": "/tmp/b.xlsm"}, lambda *_: None)
        assert result.status == "error"
        assert result.banner_level == "danger"
        # Friendly error mentions both files (the helpful "fill in" guidance).
        text_blob = (result.banner_text + " ".join(ll.text for ll in result.log_lines)).lower()
        assert "master budget" in text_blob

    def test_run_compare_missing_master_b_returns_friendly_error(self) -> None:
        """Same — Master Budget B blank."""
        tool = MasterBudgetTool()
        result = tool.run_compare({"master_file": "/tmp/a.xlsm"}, lambda *_: None)
        assert result.status == "error"
        assert result.banner_level == "danger"


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
        summary = _make_summary(mismatch_account_codes=["71000", "72000"])
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_banner_level_warning_when_mismatch_codes(self) -> None:
        summary = _make_summary(mismatch_account_codes=["71000"])
        result = _run_with_mock_summary(summary)
        assert result.banner_level == "warning"

    def test_banner_text_mentions_mismatch_count(self) -> None:
        summary = _make_summary(mismatch_account_codes=["71000", "72000", "73000"])
        result = _run_with_mock_summary(summary)
        assert "3" in result.banner_text

    def test_status_warning_when_source_only_codes(self) -> None:
        summary = _make_summary(source_only_account_codes=["80000"])
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_status_warning_when_both_code_lists_non_empty(self) -> None:
        summary = _make_summary(
            mismatch_account_codes=["71000"],
            source_only_account_codes=["80000"],
        )
        result = _run_with_mock_summary(summary)
        assert result.status == "warning"

    def test_mismatch_codes_appear_in_log(self) -> None:
        summary = _make_summary(mismatch_account_codes=["71000"])
        result = _run_with_mock_summary(summary)
        all_text = " ".join(ll.text for ll in result.log_lines)
        assert "71000" in all_text

    def test_source_only_codes_appear_in_log(self) -> None:
        summary = _make_summary(source_only_account_codes=["80000"])
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
        from toolkit.registry import all_tools

        registered_ids = [t.id for t in all_tools()]
        assert "master-budget" in registered_ids


# ---------------------------------------------------------------------------
# Bug regression guards (2026-04-25 fixes)
# ---------------------------------------------------------------------------


def test_mismatch_codes_log_tag_is_danger() -> None:
    """Bug 2 regression guard: mismatch code log lines use tag='danger', not 'warning'.

    The Excel cell fill is HL_MISMATCH (pink) and the user-facing instruction
    text says 'Pink / red'. Before the 2026-04-25 fix the log used tag='warning'
    (orange). A regression back to 'warning' would leave existing tests passing
    but recreate the visual mismatch reported by the user.
    """
    summary = _make_summary(mismatch_account_codes=["70008"])
    result = _run_with_mock_summary(summary)
    code_lines = [ll for ll in result.log_lines if ll.text.strip() == "70008"]
    assert code_lines, "expected one log line for code 70008"
    assert code_lines[0].tag == "danger", (
        "Bug 2 regression: mismatch code lines must use tag='danger' (red), "
        "not 'warning' (orange). Match Excel pink fill + Instructions 'Pink / red'."
    )


def test_subprogram_column_codes_appear_in_log() -> None:
    """Bug 3 regression guard: column-mismatch sub-program codes are surfaced in
    the IMPORT SUMMARY log, not just painted into the workbook.

    Before the 2026-04-25 fix the `ImportSummary` dataclass only carried account
    codes (rows). The two sub-program-code lists (columns) were painted in the
    output workbook but never reached the log. The user reported seeing pink
    columns in Excel with no log explanation. The fix added two new fields and
    two new log sections; this test pins both.
    """
    summary = _make_summary(
        mismatch_subprogram_codes=["6052", "6201"],
        source_only_subprogram_codes=["7350"],
    )
    result = _run_with_mock_summary(summary)
    log_text = " ".join(ll.text for ll in result.log_lines)

    # Column-mismatch section header + each code.
    assert "Mismatch columns (2)" in log_text, (
        "expected 'Mismatch columns (2)' header in log; got log:\n" + log_text
    )
    assert "6052" in log_text, "subprogram code 6052 missing from log"
    assert "6201" in log_text, "subprogram code 6201 missing from log"

    # Source-only column section header + the code.
    assert "Source-only columns (1)" in log_text, "expected 'Source-only columns (1)' header in log"
    assert "7350" in log_text, "subprogram code 7350 missing from log"

    # Both column-mismatch lines should also use tag='danger' (consistent with row mismatches).
    column_lines = [ll for ll in result.log_lines if ll.text.strip() in ("6052", "6201")]
    assert len(column_lines) == 2
    for ll in column_lines:
        assert ll.tag == "danger", (
            f"column mismatch code lines must use tag='danger', got {ll.tag!r}"
        )


def test_open_output_folder_secondary_action_name() -> None:
    """secondary_actions() must include 'Open output folder' as the first entry."""
    tool = MasterBudgetTool()
    actions = tool.secondary_actions()
    names = [name for name, _ in actions]
    assert "Open output folder" in names, (
        f"'Open output folder' not found in secondary actions: {names}"
    )


def test_open_output_folder_delegates_to_shared_helper() -> None:
    """Master Budget's _open_output_folder must delegate to toolkit.files.open_output_folder."""
    tool = MasterBudgetTool()
    p = Path(r"C:\Users\foo\OneDrive - DET Schools\file.xlsm")
    tool._last_output_path = p
    called_with: list[Path] = []
    with patch(
        "toolkit.files.open_output_folder", side_effect=lambda path: called_with.append(path)
    ):
        tool._open_output_folder()
    assert called_with == [p]
