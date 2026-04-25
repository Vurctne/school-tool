"""Licence gate tests for paid tools in the TkShell.

Tests verify that:
- active/grace states render the tool frame (not the unlock frame).
- none/expired/in-flight states render the unlock CTA.
- Free tools (HYIA) are never gated.
- The "Go to User tab" button in the unlock CTA activates the user tab.
"""

from __future__ import annotations

from typing import Any, cast
from unittest.mock import patch

import pytest

from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, TextInput, ToolResult

# ---------------------------------------------------------------------------
# Stub tools
# ---------------------------------------------------------------------------


class _FreeTool:
    """Minimal free tool — no requires_feature (None)."""

    id = "free-tool"
    group = "Banking"
    label = "Free Tool"
    short = "FT"
    order = 1
    inputs: list[InputSpec] = [TextInput(key="x", label="X")]
    output = None
    primary_button = "Run"
    pdf_template = None
    pdf_body = None
    requires_feature = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        return ToolResult(status="success", banner_level="ok", banner_text="ok")

    def secondary_actions(self) -> list[tuple[str, Any]]:
        return []


class _PaidTool:
    """Minimal paid tool — requires_feature = 'sub_program'."""

    id = "paid-tool"
    group = "Budget"
    label = "Paid Tool"
    short = "PT"
    order = 10
    inputs: list[InputSpec] = [TextInput(key="y", label="Y")]
    output = None
    primary_button = "Run"
    pdf_template = None
    pdf_body = None
    requires_feature = "sub_program"

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        return ToolResult(status="success", banner_level="ok", banner_text="ok")

    def secondary_actions(self) -> list[tuple[str, Any]]:
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
# Helper: build a shell with both stub tools
# ---------------------------------------------------------------------------


def _build_shell(tk_root: Any) -> Any:
    import tkinter as tk

    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    assert isinstance(tk_root, tk.Tk)
    fonts = detect_fonts(tk_root)
    shell = TkShell(
        tk_root,
        fonts=fonts,
        tools=[
            cast("type[BaseTool]", _FreeTool),
            cast("type[BaseTool]", _PaidTool),
        ],
    )
    shell.pack(fill="both", expand=True)
    tk_root.update_idletasks()
    return shell


def _make_licence_status(state: str) -> Any:
    from toolkit.licence import LicenceStatus

    return LicenceStatus(state=state)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_active_licence_shows_tool_frame(tk_root: Any) -> None:
    """With state='active', the paid tool frame is visible (not the unlock frame)."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("active")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    # The tool frame should be on top — unlock frame either absent or lowered
    assert shell._unlock_frame is None or not _frame_is_on_top(shell, "unlock")
    assert _frame_is_on_top(shell, "paid-tool")


def test_grace_licence_shows_tool_frame(tk_root: Any) -> None:
    """With state='grace', the paid tool frame is still shown (with a log warning)."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("grace")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    assert _frame_is_on_top(shell, "paid-tool")


def test_none_licence_shows_unlock_frame(tk_root: Any) -> None:
    """With state='none', the unlock CTA frame is shown instead of the tool."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("none")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    assert shell._unlock_frame is not None
    assert _frame_is_on_top(shell, "unlock")
    # Tool frame must not be on top
    assert not _frame_is_on_top(shell, "paid-tool")


def test_expired_licence_shows_unlock_frame(tk_root: Any) -> None:
    """With state='expired', the unlock CTA is shown."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("expired")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    assert shell._unlock_frame is not None
    assert _frame_is_on_top(shell, "unlock")


def test_invoice_issued_shows_unlock_frame(tk_root: Any) -> None:
    """With state='invoice_issued' (payment in-flight), the unlock CTA is shown."""
    with patch(
        "toolkit.licence.read_status",
        return_value=_make_licence_status("invoice_issued"),
    ):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    assert shell._unlock_frame is not None
    assert _frame_is_on_top(shell, "unlock")


def test_free_tool_never_gated(tk_root: Any) -> None:
    """A free tool (requires_feature=None) is always shown without a licence check."""
    with patch("toolkit.licence.read_status", side_effect=AssertionError("should not be called")):
        shell = _build_shell(tk_root)
        shell._activate_tool("free-tool")

    assert _frame_is_on_top(shell, "free-tool")


def test_go_to_user_tab_button(tk_root: Any) -> None:
    """'Go to User tab' in the unlock CTA activates the user frame."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("none")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")

    assert shell._unlock_frame is not None

    # Simulate clicking "Go to User tab"
    shell._activate_user_tab()
    tk_root.update_idletasks()

    assert shell._user_frame is not None
    # User frame should now be on top; tool frames and unlock frame should be lowered
    assert not _frame_is_on_top(shell, "paid-tool")
    assert not _frame_is_on_top(shell, "unlock")


def test_unlock_frame_reused_updates_title(tk_root: Any) -> None:
    """Re-activating the same paid tool reuses the unlock frame and updates the title var."""
    with patch("toolkit.licence.read_status", return_value=_make_licence_status("none")):
        shell = _build_shell(tk_root)
        shell._activate_tool("paid-tool")
        first_frame = shell._unlock_frame

        shell._activate_tool("paid-tool")
        second_frame = shell._unlock_frame

    # Same frame object — no re-creation
    assert first_frame is second_frame
    # Title var updated to the tool's label
    assert shell._unlock_title_var is not None
    assert shell._unlock_title_var.get() == "Paid Tool"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _frame_is_on_top(shell: Any, key: str) -> bool:
    """Return True if the named frame is the topmost in the stacking order."""
    import tkinter as tk

    content: tk.Frame = shell._content_outer

    # Gather all children placed in _content_outer
    children = content.place_slaves()
    if not children:
        return False

    # 'raise' / 'lower' in Tk is reflected by winfo_children() order —
    # the last child in winfo_children() is on top.
    stacked = list(content.winfo_children())
    if not stacked:
        return False

    top_widget = stacked[-1]

    if key == "unlock":
        return shell._unlock_frame is not None and top_widget is shell._unlock_frame
    else:
        frame = shell._tool_frames.get(key)
        return frame is not None and top_widget is frame
