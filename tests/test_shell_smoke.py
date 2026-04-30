"""Shell smoke test — CI-safe on Linux runners via xvfb; skips gracefully if no display."""

from __future__ import annotations

from typing import Any, cast

import pytest

from toolkit.base_tool import (
    BaseTool,
    InputSpec,
    LogLine,
    ProgressFn,
    RangeInput,
    TextInput,
    ToolResult,
)

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

    def preview_update(self, key: str, value: float | str) -> None:
        return None


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


def test_shell_with_range_input(tk_root: object) -> None:
    """A tool with a RangeInput renders without error; slider seeded with default."""
    import tkinter as tk
    from typing import cast

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _RangeInputTool:
        id = "range-smoke"
        group = "Budget"
        label = "Range smoke tool"
        short = "RS"
        order = 98
        inputs: list[InputSpec] = [
            RangeInput(
                key="threshold",
                label="Threshold (%)",
                min_value=0.0,
                max_value=300.0,
                default=101.0,
                step=1.0,
                live=True,
            )
        ]
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict[str, object], progress: ProgressFn) -> ToolResult:
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[tuple[str, object]]:
            return []

        def preview_update(self, key: str, value: float | str) -> None:
            return None

        def clear(self) -> None:
            return None

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _RangeInputTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Rail should show our tool.
    assert "range-smoke" in shell.rail_item_ids

    # Input cache seeded with default.
    assert shell._input_cache["range-smoke"].get("threshold") == 101.0


def test_inactive_tool_frames_not_placed(tk_root: object) -> None:
    """Inactive tool frames must NOT be in the geometry manager (place_forget fix).

    With multiple tools, all but the active frame should be place_forget()-ed so
    they do not receive <Configure> events on window resize (Fix 2 — Round 13).
    """
    import tkinter as tk
    from typing import cast

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _ToolA:
        id = "tool-a"
        group = "Budget"
        label = "Tool A"
        short = "TA"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run A"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict[str, object], progress: ProgressFn) -> ToolResult:
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[tuple[str, object]]:
            return []

        def clear(self) -> None:
            pass

    class _ToolB:
        id = "tool-b"
        group = "Budget"
        label = "Tool B"
        short = "TB"
        order = 2
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run B"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict[str, object], progress: ProgressFn) -> ToolResult:
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[tuple[str, object]]:
            return []

        def clear(self) -> None:
            pass

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(
        tk_root,
        fonts=fonts,
        tools=[cast("type[BaseTool]", _ToolA), cast("type[BaseTool]", _ToolB)],
    )
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Active tool is Tool A (first in list).
    active_id = shell.active_tool_id
    assert active_id == "tool-a"

    active_frame = shell._tool_frames["tool-a"]
    inactive_frame = shell._tool_frames["tool-b"]

    # The active frame must be placed (place_info returns a non-empty dict).
    assert active_frame.place_info(), "Active tool frame should be placed (place_info non-empty)"
    # The inactive frame must NOT be placed (place_forget was called).
    assert not inactive_frame.place_info(), (
        "Inactive tool frame should NOT be placed — it would receive <Configure> "
        "events on resize even when hidden (Fix 2 — Round 13)"
    )

    # Switching to Tool B should flip the placement.
    shell._activate_tool("tool-b")
    tk_root.update_idletasks()

    assert shell._tool_frames["tool-b"].place_info(), (
        "After activation, tool-b frame should be placed"
    )
    assert not shell._tool_frames["tool-a"].place_info(), (
        "After switching away, tool-a frame should be place_forget()-ed"
    )


def test_default_window_size_is_1440x900(tk_root: object) -> None:
    """Root window geometry should default to 1440x900 (Fix 2 — Round 14).

    The geometry string returned by root.geometry() has the form
    ``"WxH+X+Y"`` or just ``"WxH"`` before the window is shown.  We
    assert that the declared size prefix is exactly ``"1440x900"``.
    """
    import tkinter as tk

    assert isinstance(tk_root, tk.Tk)
    tk_root.geometry("1440x900")
    tk_root.update_idletasks()

    geo = tk_root.geometry()
    # geometry() returns "WxH+X+Y" — split on "+" to isolate the size part.
    size_part = geo.split("+")[0]
    assert size_part == "1440x900", (
        f"Expected default geometry '1440x900', got '{size_part}' (full: '{geo}')"
    )


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


# ---------------------------------------------------------------------------
# Round 15 — free-tier launch tests
# ---------------------------------------------------------------------------


def test_user_tab_hidden_when_show_user_tab_false(tk_root: object) -> None:
    """User tab must not appear in the rail when SHOW_USER_TAB is False.

    Tk-skip on Linux CI (no display). Patches app_metadata.SHOW_USER_TAB so
    the test is independent of the current flag value.
    """
    import tkinter as tk
    from typing import cast
    from unittest.mock import patch

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)

    with patch("app_metadata.SHOW_USER_TAB", False):
        shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
        shell.pack(fill="both", expand=True)
        tk_root.update_idletasks()

    # Walk all Label text values in the scroll_container (rail child index 1).
    scroll_container = shell._rail_frame.winfo_children()[1]
    rail_labels = [
        w.cget("text") for w in scroll_container.winfo_children() if isinstance(w, tk.Label)
    ]
    assert "User" not in rail_labels, (
        f"User tab should not appear in the rail when SHOW_USER_TAB is False; "
        f"found labels: {rail_labels}"
    )


def test_in_development_group_rendered_when_list_nonempty(tk_root: object) -> None:
    """Rail must contain an 'In development' header label when IN_DEVELOPMENT_TOOLS is non-empty.

    Tk-skip on Linux CI (no display).
    """
    import tkinter as tk
    from typing import cast

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Walk all Label widgets inside the rail frame and check for the header.
    rail_labels = [
        w.cget("text")
        for w in shell._rail_frame.winfo_children()[1].winfo_children()
        if isinstance(w, tk.Label)
    ]
    assert "In development" in rail_labels, (
        f"Expected 'In development' label in rail; found labels: {rail_labels}"
    )


def test_operating_statement_not_in_registry() -> None:
    """Operating Statement must not be registered (parked under In development for Round 15)."""
    from toolkit.registry import _registered, all_tools

    all_tools()  # trigger registration side-effects
    ids = [cls.id for cls in _registered]
    assert "operating" not in ids, (
        "OperatingStatementTool must not be registered — it is parked under "
        "'In development' for Round 15's free-tier launch."
    )


# ---------------------------------------------------------------------------
# Round 19 — draggable rail + Large.Accent.TButton style
# ---------------------------------------------------------------------------


def test_body_uses_paned_window(tk_root: object) -> None:
    """Round 19 — body now wraps rail + content in a tk.PanedWindow so the
    user can drag the rail width."""
    import tkinter as tk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # Body frame should contain a PanedWindow holding the rail + content.
    assert isinstance(shell._body_paned, tk.PanedWindow)
    # PanedWindow.panes() is untyped in tkinter stubs; cast through Any.
    panes_any = cast(Any, shell._body_paned).panes()
    assert len(panes_any) == 2, f"Expected 2 panes (rail + content), got: {panes_any}"

    # Rail's parent should be the PanedWindow, not the body frame directly.
    assert str(shell._rail_frame.winfo_parent()) == str(shell._body_paned)
    assert str(shell._content_outer.winfo_parent()) == str(shell._body_paned)


def test_rail_default_width_preserved(tk_root: object) -> None:
    """Round 19 — the rail still defaults to 220 px on first show."""
    import tkinter as tk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    # The rail Frame is still constructed with width=220 + pack_propagate(False).
    assert shell._rail_frame.cget("width") == 220


def test_large_accent_button_style_registered(tk_root: object) -> None:
    """Round 19 — 'Large.Accent.TButton' style is registered at shell init."""
    import tkinter as tk
    import tkinter.ttk as ttk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    style = ttk.Style()
    # ttk.Style.lookup returns the configured value or "" if not set.
    font_value = style.lookup("Large.Accent.TButton", "font")
    assert font_value, (
        "Expected 'Large.Accent.TButton' to have a configured font; "
        f"got empty/none. shell={shell!r}"
    )


def test_default_tool_uses_accent_tbutton_style(tk_root: object) -> None:
    """Round 19 — tools that don't declare primary_button_style still use
    the standard 'Accent.TButton' style (regression: backward compat)."""
    import tkinter as tk
    import tkinter.ttk as ttk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(tk_root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyTool)])
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()

    btn = shell._tool_primary_btns["dummy-tool"]
    assert isinstance(btn, ttk.Button)
    assert btn.cget("style") == "Accent.TButton"
