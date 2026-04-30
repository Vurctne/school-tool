"""Tests for the shell-level Clear button and BaseTool.clear() contract.

UI-dependent tests (those that need a live Tk root) are skipped on Linux CI
where tkinter is absent, matching the existing pattern in the test suite.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 1. BaseTool default clear() is a no-op
# ---------------------------------------------------------------------------


def test_base_tool_default_clear_is_noop() -> None:
    """A minimal BaseTool subclass must accept clear() and return None."""
    from typing import Any

    from toolkit.base_tool import FileInput, OutputSpec, ProgressFn, ToolResult

    class _MinimalTool:
        id = "minimal"
        group = "Test"
        label = "Minimal Tool"
        short = "MT"
        order = 0
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None
        inputs: list[Any] = [FileInput(key="f", label="File", filetypes=[("All files", "*.*")])]
        output = OutputSpec(key="out", label="Output", suffix=".xlsx")

        def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
            return ToolResult(status="success", banner_level="ok", banner_text="")

        def secondary_actions(self) -> list[Any]:
            return []

        def clear(self) -> None:
            return None

    tool = _MinimalTool()
    tool.clear()  # must not raise; return value is None (-> None)


# ---------------------------------------------------------------------------
# 2. SubProgramBudgetReportTool.clear() resets session state
# ---------------------------------------------------------------------------


def test_sub_program_clear_resets_session_state() -> None:
    """set _last_summary, _commentary_overrides, _last_output_path to non-None
    values; call clear(); verify all three are None afterwards."""
    from decimal import Decimal
    from pathlib import Path

    from tools.sub_program.frame import SubProgramBudgetReportTool
    from tools.sub_program.logic import ReportSummary

    tool = SubProgramBudgetReportTool()

    # Build a minimal ReportSummary so the type is satisfied
    summary = ReportSummary(
        lines=[],
        faculty_counts={},
        over_budget_lines=[],
        total_budget=Decimal("0"),
        total_ytd=Decimal("0"),
        output_path=Path("/tmp/output.xlsx"),
        faculty_budget={},
        faculty_ytd={},
        faculty_used_pct={},
    )

    tool._last_summary = summary
    tool._commentary_overrides = {"4001": "Some note"}
    tool._last_output_path = Path("/tmp/output.xlsx")

    assert tool._last_summary is not None
    assert tool._commentary_overrides is not None
    assert tool._last_output_path is not None

    tool.clear()

    assert tool._last_summary is None
    assert tool._commentary_overrides is None
    assert tool._last_output_path is None


# ---------------------------------------------------------------------------
# 3. MasterBudgetTool.clear() resets _last_output_path
# ---------------------------------------------------------------------------


def test_master_budget_clear_resets_last_output_path() -> None:
    """set _last_output_path to a non-None Path; call clear(); verify it is None."""
    from pathlib import Path

    from tools.master_budget.frame import MasterBudgetTool

    tool = MasterBudgetTool()
    tool._last_output_path = Path("/tmp/some_output.xlsm")

    assert tool._last_output_path is not None

    tool.clear()

    assert tool._last_output_path is None


# ---------------------------------------------------------------------------
# 4. HyiaTool.clear() uses the default no-op (no per-tool state)
# ---------------------------------------------------------------------------


def test_hyia_clear_is_noop() -> None:
    """HyiaTool has no per-tool state; clear() must return None without error."""
    from tools.hyia.frame import HyiaTool

    tool = HyiaTool()
    tool.clear()  # must not raise; return value is None (-> None)


# ---------------------------------------------------------------------------
# 5. Tk-dependent: Clear button present in action row (skipped on Linux CI)
# ---------------------------------------------------------------------------


def test_clear_button_in_action_row_tk() -> None:
    """The Clear button must appear in every tool's button row in the shell.

    Skipped when tkinter is absent (Linux CI).
    """
    try:
        import tkinter as tk
        import tkinter.ttk as ttk
    except ImportError:
        pytest.skip("Tk absent")

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tk display not available")

    try:
        from toolkit.fonts import detect_fonts
        from toolkit.registry import all_tools
        from toolkit.shell import TkShell

        fonts = detect_fonts(root)
        shell = TkShell(root, fonts=fonts, tools=all_tools())

        def _collect_button_texts(widget: tk.Misc, out: list[str]) -> None:
            """Recursively collect text labels from all ttk.Button widgets."""
            if isinstance(widget, ttk.Button):
                try:
                    out.append(str(widget.cget("text")))
                except Exception:
                    pass
            for child in widget.winfo_children():
                _collect_button_texts(child, out)

        # Check each tool frame contains a button labelled "Clear"
        for tool in shell._tools:
            tid = tool.id
            frame = shell._tool_frames.get(tid)
            assert frame is not None, f"No frame for tool {tid}"

            btn_texts: list[str] = []
            _collect_button_texts(frame, btn_texts)
            assert "Clear" in btn_texts, (
                f"Tool '{tool.label}' action row missing 'Clear' button. Found buttons: {btn_texts}"
            )
    finally:
        root.destroy()


# ---------------------------------------------------------------------------
# 6. Regression: Clear button must not raise "invalid command name" on the
#    SelectableList's inner Canvas/Frame after a result with a rail+table.
#    (Fix 1, Round 9 — stale Tk callback when rail destroyed before set_active)
# ---------------------------------------------------------------------------


def test_clear_tool_after_rail_result_no_tk_error() -> None:
    """render_result (with side_rail) + _clear_tool must not raise TclError.

    Regression guard for the 'invalid command name' bug where _clear_tool
    called rail.set_active(None) AFTER destroying the table_frame children
    that contained the SelectableList.  The fix is to call set_active(None)
    BEFORE destroying table children.

    Skipped when Tk is absent.
    """
    try:
        import tkinter as tk
    except ImportError:
        pytest.skip("Tk absent")

    try:
        root = tk.Tk()
        root.withdraw()
    except Exception:
        pytest.skip("Tk display not available")

    errors: list[str] = []

    def capture_exc(exc_type: type, exc_value: BaseException, exc_tb: object) -> None:
        errors.append(str(exc_value))

    try:
        from typing import cast

        from toolkit.base_tool import (
            BaseTool,
            InputSpec,
            ProgressFn,
            RailItem,
            TableSpec,
            ToolResult,
        )
        from toolkit.fonts import detect_fonts
        from toolkit.shell import TkShell

        # A minimal tool that produces a rail+table result.
        class _RailTool:
            id = "rail-tool"
            group = "Budget"
            label = "Rail Tool"
            short = "RT"
            order = 1
            inputs: list[InputSpec] = []
            output = None
            primary_button = "Run"
            pdf_template = None
            pdf_body = None
            requires_feature = None

            def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
                return ToolResult(status="success", banner_level="ok", banner_text="")

            def secondary_actions(self) -> list:  # type: ignore[type-arg]
                return []

            def clear(self) -> None:
                pass

        fonts = detect_fonts(root)
        shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _RailTool)])
        shell.pack(fill="both", expand=True)
        root.update_idletasks()

        # Install exception catcher so TclErrors in callbacks are surfaced.
        root.report_callback_exception = capture_exc  # noqa: Tk callback; root is Any when stubs absent

        # Render a result with a side rail (triggers the two-column grid layout).
        result = ToolResult(
            status="success",
            banner_level="ok",
            banner_text="Done.",
            side_rail=[
                RailItem(label="English", value="72 %", filter_key="English"),
                RailItem(label="Maths", value="45 %", filter_key="Maths"),
            ],
            table=TableSpec(
                columns=[{"key": "prog", "label": "Sub-program"}],
                rows=[
                    {"prog": "E01", "_faculty": "English"},
                    {"prog": "M01", "_faculty": "Maths"},
                ],
            ),
        )
        shell._render_result("rail-tool", result)
        root.update_idletasks()

        # Apply a filter so the rail has an active selection.
        shell._apply_filter("rail-tool", "English")
        root.update_idletasks()

        # Confirm the rail is live and set_active worked without error so far.
        assert not errors, f"Unexpected error before Clear: {errors}"

        # Now click Clear — must NOT raise "invalid command name".
        tool = shell._tool_map["rail-tool"]
        shell._clear_tool(tool)
        root.update_idletasks()

        assert not errors, (
            f"_clear_tool raised a Tk error: {errors}\n"
            "Root cause: set_active() was called after table children were destroyed. "
            "The fix (Round 9) reorders the steps: clear rail state first, then destroy."
        )

        # Filter state must be cleared.
        assert shell._tool_filter.get("rail-tool") is None
        assert shell._tool_rails.get("rail-tool") is None
        assert shell._tool_tables.get("rail-tool") is None

        # Chip must be hidden.
        chip = shell._tool_filter_chips.get("rail-tool")
        assert chip is not None
        assert not chip.winfo_ismapped(), "Filter chip should not be visible after Clear"

    finally:
        root.destroy()
