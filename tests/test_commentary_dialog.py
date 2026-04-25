"""Tests for CommentaryDialog primitive.

Skips cleanly when tkinter is not available (e.g. headless CI without Xvfb).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any, cast

import pytest

try:
    import tkinter as tk
except ImportError:
    pytest.skip("tkinter not available", allow_module_level=True)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def root() -> Generator[tk.Tk, None, None]:
    r: tk.Tk | None = None
    try:
        r = tk.Tk()
        r.withdraw()
    except tk.TclError as exc:
        pytest.skip(f"No display available: {exc}")
        return
    yield r
    if r is not None:
        try:
            r.destroy()
        except tk.TclError:
            pass


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------


def _all_widgets(parent: Any) -> list[Any]:
    result: list[Any] = [parent]
    for child in parent.winfo_children():
        result.extend(_all_widgets(child))
    return result


def _click_sp_label(top: Any, sp_id: str) -> None:
    """Find and click the label for the given sub-program id."""
    for widget in _all_widgets(top):
        if isinstance(widget, tk.Label) and widget.cget("text") == sp_id:
            widget.event_generate("<Button-1>")
            return


def _find_text_widget(top: Any) -> tk.Text | None:
    for widget in _all_widgets(top):
        if isinstance(widget, tk.Text):
            return widget
    return None


def _click_button(top: Any, label: str) -> None:
    for widget in _all_widgets(top):
        if isinstance(widget, tk.Button) and widget.cget("text") == label:
            widget.invoke()
            return


def _count_sp_labels(top: Any, sub_programs: list[str]) -> int:
    count = 0
    sp_set = set(sub_programs)
    for widget in _all_widgets(top):
        if isinstance(widget, tk.Label) and widget.cget("text") in sp_set:
            count += 1
    return count


def _open_and_drive(
    root: tk.Tk,
    sub_programs: list[str],
    initial: dict[str, str],
    action: str,
    select_sp: str | None = None,
    type_text: str | None = None,
) -> dict[str, str] | None:
    """Schedule post-show actions via root.after, then call CommentaryDialog.

    Parameters
    ----------
    action:
        "save"    — click Save button
        "cancel"  — click Cancel button
        "destroy" — destroy the Toplevel directly (simulates window-close)
    """
    from toolkit.primitives import CommentaryDialog

    def _drive() -> None:
        top: Any = None
        for widget in root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                top = widget
        if top is None:
            return

        if select_sp is not None:
            _click_sp_label(top, select_sp)
            root.update_idletasks()

        if type_text is not None:
            editor = _find_text_widget(top)
            if editor is not None:
                editor.insert("end", type_text)
                editor.event_generate("<<Modified>>")
                root.update_idletasks()

        if action == "save":
            _click_button(top, "Save")
        elif action == "cancel":
            _click_button(top, "Cancel")
        elif action == "destroy":
            top.destroy()

    root.after(50, _drive)
    return CommentaryDialog(cast("tk.Widget", root), sub_programs, initial)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_save_returns_dict_with_edited_entries(root: tk.Tk) -> None:
    """Select sp2, type 'second', Save → returned dict has sp1 and sp2 entries."""
    sub_programs = ["sp1", "sp2", "sp3"]
    initial = {"sp1": "first note"}

    ret = _open_and_drive(
        root,
        sub_programs,
        initial,
        action="save",
        select_sp="sp2",
        type_text="second",
    )

    assert ret is not None, "Expected dict, got None"
    assert ret.get("sp1") == "first note"
    assert "second" in ret.get("sp2", ""), (
        f"Expected 'second' in sp2 text, got {ret.get('sp2')!r}"
    )


def test_cancel_returns_none(root: tk.Tk) -> None:
    """Select sp1, type something, then Cancel → returns None."""
    sub_programs = ["sp1", "sp2", "sp3"]
    initial: dict[str, str] = {}

    ret = _open_and_drive(
        root,
        sub_programs,
        initial,
        action="cancel",
        select_sp="sp1",
        type_text="should be discarded",
    )

    assert ret is None, f"Expected None on cancel, got {ret!r}"


def test_window_destroy_returns_none(root: tk.Tk) -> None:
    """Closing the window via destroy() → returns None."""
    sub_programs = ["sp1", "sp2", "sp3"]
    initial: dict[str, str] = {}

    ret = _open_and_drive(
        root,
        sub_programs,
        initial,
        action="destroy",
    )

    assert ret is None, f"Expected None on window close, got {ret!r}"


def test_list_shows_all_items(root: tk.Tk) -> None:
    """The list pane renders a label for each of the 3 sub-programs."""
    from toolkit.primitives import CommentaryDialog

    sub_programs = ["alpha", "beta", "gamma"]
    initial: dict[str, str] = {}

    found_count: list[int] = []

    def _drive() -> None:
        for widget in root.winfo_children():
            if isinstance(widget, tk.Toplevel):
                found_count.append(_count_sp_labels(widget, sub_programs))
                _click_button(widget, "Cancel")
                return

    root.after(50, _drive)
    CommentaryDialog(cast("tk.Widget", root), sub_programs, initial)

    assert found_count, "Drive callback never ran"
    assert found_count[0] == 3, f"Expected 3 list items, found {found_count[0]}"
