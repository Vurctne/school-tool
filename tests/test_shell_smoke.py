"""Shell smoke test — CI-safe on Linux runners via xvfb; skips gracefully if no display."""

from __future__ import annotations

from typing import Any, cast

import pytest

from toolkit.base_tool import BaseTool, InputSpec, LogLine, ProgressFn, TextInput, ToolResult

# ---------------------------------------------------------------------------
# Dummy BaseTool subclass
# ---------------------------------------------------------------------------


class _DummyTool:
    """Minimal concrete BaseTool used solely for smoke-testing the shell."""

    id = "dummy-tool"
    group = "Budget"
    label = "Dummy tool"
    short = "DT"
    order = 99
    inputs: list[InputSpec] = [
        TextInput(key="note", label="Note", placeholder="Enter a note"),
    ]
    output = None
    primary_button = "Run dummy"
    pdf_template = None
    pdf_body = None

    def run(self, paths: dict[str, object], progress: ProgressFn) -> ToolResult:
        progress(50, "Halfway")
        progress(100, "Done")
        return ToolResult(
            status="success",
            banner_level="ok",
            banner_text="Dummy completed successfully.",
            log_lines=[LogLine("All good", tag="ok")],
        )

    def secondary_actions(self) -> list[tuple[str, object]]:
        return []


# ---------------------------------------------------------------------------
# Fixture: headless Tk root
# ---------------------------------------------------------------------------


@pytest.fixture()
def tk_root() -> Any:
    try:
        import tkinter as tk
    except ImportError as exc:
        pytest.skip(f"tkinter not installed: {exc}")
        return

    try:
        root = tk.Tk()
        root.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"No display available for Tk: {exc}")
        return

    yield root
    root.destroy()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_imports() -> None:
    """Ensure all shell/primitive modules import cleanly (skips on no tkinter)."""
    try:
        import tkinter  # noqa: F401
    except ImportError as exc:
        pytest.skip(f"tkinter not installed: {exc}")

    import toolkit.fonts  # noqa: F401
    import toolkit.logging_setup  # noqa: F401
    import toolkit.primitives  # noqa: F401
    import toolkit.shell  # noqa: F401


def test_shell_construction(tk_root: object) -> None:
    import tkinter as tk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Rail should have exactly one entry for our single dummy tool
    assert shell.rail_item_ids == ["dummy-tool"]

    # Active tool should be the dummy
    assert shell.active_tool_id == "dummy-tool"


def test_shell_title(tk_root: object) -> None:
    import tkinter as tk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Title must contain the tool label
    title = tk_root.title()
    assert "Dummy tool" in title, f"Expected 'Dummy tool' in title, got: {title!r}"


def test_font_detection(tk_root: object) -> None:
    import tkinter as tk

    from toolkit.fonts import FontMap, detect_fonts

    assert isinstance(tk_root, tk.Tk)
    fm = detect_fonts(tk_root)
    assert isinstance(fm, FontMap)
    assert fm.sans_family  # non-empty
    assert fm.mono_family  # non-empty
    assert fm.serif_family  # non-empty


def test_logging_setup() -> None:
    """configure_logging() should return a Path and not raise."""
    import logging

    # Reset root logger handlers to avoid interference from previous calls
    root_logger = logging.getLogger()
    handlers_before = list(root_logger.handlers)

    try:
        from toolkit.logging_setup import configure_logging

        log_path = configure_logging()
        assert log_path.suffix == ".log"
    finally:
        # Restore handlers to avoid polluting other tests
        for h in list(root_logger.handlers):
            if h not in handlers_before:
                root_logger.removeHandler(h)
