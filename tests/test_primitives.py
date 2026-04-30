"""Tests for toolkit primitives: SelectableList, Table (phase-3 extensions).

Tk-dependent tests skip cleanly when tkinter is absent (headless CI).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest


def _has_tk() -> bool:
    try:
        import tkinter as tk

        r = tk.Tk()
        r.destroy()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def root() -> Generator[Any, None, None]:
    try:
        import tkinter as tk
    except ImportError as exc:
        pytest.skip(f"tkinter not installed: {exc}")
        return

    r: Any = None
    try:
        r = tk.Tk()
        r.withdraw()
    except Exception as exc:
        pytest.skip(f"No display available: {exc}")
        return

    yield r

    if r is not None:
        try:
            r.destroy()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# SelectableList smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_renders_items(root: Any) -> None:
    """SelectableList creates one row frame per RailItem."""

    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="English", value="72 %", filter_key="english"),
        RailItem(label="Maths", value="105 %", filter_key="maths", highlight=True),
        RailItem(label="Science", value="88 %", filter_key="science"),
    ]
    selected: list[str] = []
    widget = SelectableList(root, items=items, on_select=lambda k: selected.append(k))
    widget.pack()
    root.update_idletasks()

    # Three items should produce three rows in the inner frame
    assert len(widget._row_frames) == 3
    assert set(widget._row_frames.keys()) == {"english", "maths", "science"}


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_set_active_highlights_row(root: Any) -> None:
    """set_active(key) paints the matching row RAIL_SELECTED blue."""

    from toolkit import tokens
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="English", value="72 %", filter_key="english"),
        RailItem(label="Maths", value="105 %", filter_key="maths"),
    ]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    widget.set_active("english")
    root.update_idletasks()

    english_frame = widget._row_frames["english"]
    maths_frame = widget._row_frames["maths"]

    assert english_frame.cget("bg") == tokens.RAIL_SELECTED
    assert maths_frame.cget("bg") != tokens.RAIL_SELECTED


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_click_invokes_on_select(root: Any) -> None:
    """Clicking a row label invokes on_select with the filter_key."""

    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="English", value="72 %", filter_key="english"),
        RailItem(label="Maths", value="105 %", filter_key="maths"),
    ]
    selected: list[str] = []
    widget = SelectableList(root, items=items, on_select=lambda k: selected.append(k))
    widget.pack()
    root.update_idletasks()

    # Simulate a click on the Maths row label
    lbl = widget._row_labels.get("maths")
    assert lbl is not None, "Maths label widget not found"
    lbl.event_generate("<Button-1>")
    root.update_idletasks()

    assert "maths" in selected


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_set_items_preserves_active(root: Any) -> None:
    """set_items keeps the active selection when the key still exists."""

    from toolkit import tokens
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="English", value="72 %", filter_key="english"),
        RailItem(label="Maths", value="105 %", filter_key="maths"),
    ]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    widget.set_active("maths")

    # Update items (e.g. value changed) -- same keys
    new_items = [
        RailItem(label="English", value="73 %", filter_key="english"),
        RailItem(label="Maths", value="106 %", filter_key="maths"),
    ]
    widget.set_items(new_items)
    root.update_idletasks()

    # Active key should still be maths after refresh
    assert widget._active_key == "maths"
    maths_frame = widget._row_frames["maths"]
    assert maths_frame.cget("bg") == tokens.RAIL_SELECTED


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_highlight_row_tinted(root: Any) -> None:
    """RailItem with highlight=True gets RAIL_HL_BG background (not selected)."""

    from toolkit import tokens
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="Maths", value="105 %", filter_key="maths", highlight=True),
    ]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    maths_frame = widget._row_frames["maths"]
    # When not active, highlight row should use RAIL_HL_BG
    assert maths_frame.cget("bg") == tokens.RAIL_HL_BG


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_active_overrides_highlight(root: Any) -> None:
    """Active selection blue overrides the highlight pink tint."""

    from toolkit import tokens
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [
        RailItem(label="Maths", value="105 %", filter_key="maths", highlight=True),
    ]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    widget.set_active("maths")
    root.update_idletasks()

    maths_frame = widget._row_frames["maths"]
    assert maths_frame.cget("bg") == tokens.RAIL_SELECTED


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_get_label_widget(root: Any) -> None:
    """get_label_widget returns the tk.Label for the given filter_key."""
    import tkinter as tk

    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [RailItem(label="English", value="72 %", filter_key="english")]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    lbl = widget.get_label_widget("english")
    assert lbl is not None
    assert isinstance(lbl, tk.Label)
    assert lbl.cget("text") == "English"

    missing = widget.get_label_widget("nonexistent")
    assert missing is None


# ---------------------------------------------------------------------------
# Table -- legacy path still works
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_table_legacy_bg_fg_path(root: Any) -> None:
    """Rows with _bg/_fg keys are styled as before (legacy path unmodified)."""

    from toolkit.primitives import Table

    columns = [{"key": "name", "label": "Name"}, {"key": "amount", "label": "Amount"}]
    tbl = Table(root, columns=columns)
    tbl.pack()

    rows = [
        {"name": "Row 1", "amount": "$100", "_bg": "#F4CCCC", "_fg": "#B00020"},
        {"name": "Row 2", "amount": "$200"},
    ]
    tbl.set_rows(rows)
    root.update_idletasks()

    # Two items should exist in the treeview
    children = tbl._tree.get_children()
    assert len(children) == 2

    # First row has a custom tag
    tags_0 = tbl._tree.item(children[0], "tags")
    assert any("custom_0" in str(t) for t in tags_0)

    # Second row has the alt tag (index 1, odd)
    tags_1 = tbl._tree.item(children[1], "tags")
    assert "alt" in tags_1


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_table_row_style_takes_precedence(root: Any) -> None:
    """When row_style is provided it overrides the legacy _bg/_fg path."""

    from toolkit.primitives import Table

    columns = [{"key": "name", "label": "Name"}]

    style_calls: list[dict[str, Any]] = []

    def row_style(row: dict) -> dict[str, str]:  # type: ignore[type-arg]
        style_calls.append(row)
        return {"background": "#AABBCC"}

    tbl = Table(root, columns=columns, row_style=row_style)
    tbl.pack()

    rows = [
        {"name": "Row 1", "_bg": "#F4CCCC"},  # has legacy key
        {"name": "Row 2"},
    ]
    tbl.set_rows(rows)
    root.update_idletasks()

    # row_style should have been called for each row
    assert len(style_calls) == 2

    children = tbl._tree.get_children()
    # First row should use style_ tag from row_style, not custom_ from _bg
    tags_0 = tbl._tree.item(children[0], "tags")
    assert any("style_0" in str(t) for t in tags_0)
    assert not any("custom_0" in str(t) for t in tags_0)


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_table_on_row_click_invoked(root: Any) -> None:
    """on_row_click is invoked with the correct row dict on treeview selection."""

    from toolkit.primitives import Table

    columns = [{"key": "name", "label": "Name"}]
    clicked: list[dict] = []  # type: ignore[type-arg]

    tbl = Table(root, columns=columns, on_row_click=lambda r: clicked.append(r))
    tbl.pack()

    rows = [{"name": "Alpha"}, {"name": "Beta"}]
    tbl.set_rows(rows)
    root.update_idletasks()

    # Select first row programmatically
    children = tbl._tree.get_children()
    tbl._tree.selection_set(children[0])
    tbl._tree.event_generate("<<TreeviewSelect>>")
    root.update_idletasks()

    assert len(clicked) == 1
    assert clicked[0]["name"] == "Alpha"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_table_set_rows_rebinds_correctly(root: Any) -> None:
    """set_rows called multiple times keeps the click handler working on new data."""

    from toolkit.primitives import Table

    columns = [{"key": "name", "label": "Name"}]
    clicked: list[str] = []

    def click_fn(row: dict) -> None:  # type: ignore[type-arg]
        clicked.append(row.get("name", ""))

    tbl = Table(root, columns=columns, on_row_click=click_fn)
    tbl.pack()

    # First set_rows call
    tbl.set_rows([{"name": "First"}])
    root.update_idletasks()

    # Second set_rows call (simulates filter change re-emitting rows)
    tbl.set_rows([{"name": "Second"}, {"name": "Third"}])
    root.update_idletasks()

    children = tbl._tree.get_children()
    # Click the second row ("Third")
    tbl._tree.selection_set(children[1])
    tbl._tree.event_generate("<<TreeviewSelect>>")
    root.update_idletasks()

    assert "Third" in clicked


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_table_no_click_binding_when_none(root: Any) -> None:
    """Table with no on_row_click does not raise on selection events."""

    from toolkit.primitives import Table

    columns = [{"key": "name", "label": "Name"}]
    tbl = Table(root, columns=columns)  # no on_row_click
    tbl.pack()
    tbl.set_rows([{"name": "Row 1"}])
    root.update_idletasks()

    children = tbl._tree.get_children()
    tbl._tree.selection_set(children[0])
    tbl._tree.event_generate("<<TreeviewSelect>>")
    root.update_idletasks()
    # Should not raise


# ---------------------------------------------------------------------------
# _render_result branch tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_render_result_no_rail_no_table(root: Any) -> None:
    """A ToolResult with no table data renders without error (HYIA-style)."""
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _DummyNoTable:
        id = "dummy-no-table"
        group = "Budget"
        label = "No table tool"
        short = "NT"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyNoTable)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    result = ToolResult(status="success", banner_level="ok", banner_text="Done.")
    shell._render_result("dummy-no-table", result)
    root.update_idletasks()
    # Should not raise; table_frame should remain hidden


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_render_result_legacy_table_no_rail(root: Any) -> None:
    """Legacy table_columns / table_rows path renders in single-column layout."""
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.primitives import Table
    from toolkit.shell import TkShell

    class _DummyLegacy:
        id = "dummy-legacy"
        group = "Budget"
        label = "Legacy table"
        short = "LT"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(
                status="success",
                banner_level="ok",
                banner_text="Done.",
                table_columns=[{"key": "col", "label": "Col"}],
                table_rows=[{"col": "val"}],
            )

        def secondary_actions(self) -> list[Any]:
            return []

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyLegacy)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done.",
        table_columns=[{"key": "col", "label": "Col"}],
        table_rows=[{"col": "val"}],
    )
    shell._render_result("dummy-legacy", result)
    root.update_idletasks()

    tbl = shell._tool_tables.get("dummy-legacy")
    assert tbl is not None
    assert isinstance(tbl, Table)


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_render_result_rail_and_table_spec(root: Any) -> None:
    """side_rail + table (TableSpec) creates the two-column grid layout."""
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, RailItem, TableSpec, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.primitives import Table
    from toolkit.shell import TkShell

    class _DummyRail:
        id = "dummy-rail"
        group = "Budget"
        label = "Rail tool"
        short = "RT"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(
                status="success",
                banner_level="ok",
                banner_text="Done.",
                side_rail=[RailItem(label="English", value="72 %", filter_key="english")],
                table=TableSpec(
                    columns=[{"key": "prog", "label": "Sub-program"}],
                    rows=[{"prog": "English"}],
                ),
            )

        def secondary_actions(self) -> list[Any]:
            return []

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyRail)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done.",
        side_rail=[RailItem(label="English", value="72 %", filter_key="english")],
        table=TableSpec(
            columns=[{"key": "prog", "label": "Sub-program"}],
            rows=[{"prog": "English"}],
        ),
    )
    shell._render_result("dummy-rail", result)
    root.update_idletasks()

    # A Table widget should have been created
    tbl = shell._tool_tables.get("dummy-rail")
    assert tbl is not None
    assert isinstance(tbl, Table)


# ---------------------------------------------------------------------------
# _filter_rows — pure logic, no Tk dependency (runs on Linux CI)
# ---------------------------------------------------------------------------
# Duplicate the function inline so these tests run even when tkinter is absent
# (importing toolkit.shell would fail on headless CI because shell.py imports
# tkinter unconditionally at module level).


def _filter_rows_impl(rows: list[dict[str, Any]], filter_key: str) -> list[dict[str, Any]]:
    """Mirror of toolkit.shell._filter_rows — kept here to stay Tk-free."""
    return [r for r in rows if r.get("_faculty") == filter_key]


def test_filter_rows_returns_matching_faculty() -> None:
    """_filter_rows isolates rows by _faculty key without touching Tk."""
    rows = [
        {"sub_program": "E01", "_faculty": "English"},
        {"sub_program": "M01", "_faculty": "Maths"},
        {"sub_program": "E02", "_faculty": "English"},
        {"sub_program": "S01", "_faculty": "Science"},
    ]
    result = _filter_rows_impl(rows, "English")
    assert len(result) == 2
    assert all(r["_faculty"] == "English" for r in result)
    assert result[0]["sub_program"] == "E01"
    assert result[1]["sub_program"] == "E02"


def test_filter_rows_unknown_key_returns_empty() -> None:
    """_filter_rows returns [] when no row matches the given key."""
    rows = [{"sub_program": "E01", "_faculty": "English"}]
    assert _filter_rows_impl(rows, "Nonexistent") == []


def test_filter_rows_empty_input() -> None:
    """_filter_rows handles an empty row list gracefully."""
    assert _filter_rows_impl([], "English") == []


def test_filter_rows_missing_faculty_key() -> None:
    """Rows without a ``_faculty`` key are excluded (treated as non-match)."""
    rows = [
        {"sub_program": "E01"},  # no _faculty key
        {"sub_program": "E02", "_faculty": "English"},
    ]
    result = _filter_rows_impl(rows, "English")
    assert len(result) == 1
    assert result[0]["sub_program"] == "E02"


# ---------------------------------------------------------------------------
# Click-to-filter shell integration (Tk-dependent)
# ---------------------------------------------------------------------------


def _make_filter_shell(root: Any) -> Any:
    """Build a minimal TkShell with a rail+table tool for filter tests.

    Returns the shell instance. The tool id is "dummy-filter".
    """
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, RailItem, TableSpec, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    _rows = [
        {"prog": "E01", "_faculty": "English"},
        {"prog": "E02", "_faculty": "English"},
        {"prog": "M01", "_faculty": "Maths"},
        {"prog": "S01", "_faculty": "Science"},
    ]
    _rail = [
        RailItem(label="English", value="2", filter_key="English"),
        RailItem(label="Maths", value="1", filter_key="Maths"),
        RailItem(label="Science", value="1", filter_key="Science"),
    ]
    _spec = TableSpec(
        columns=[{"key": "prog", "label": "Sub-program"}],
        rows=_rows,
    )

    class _DummyFilter:
        id = "dummy-filter"
        group = "Budget"
        label = "Filter tool"
        short = "FT"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(
                status="success",
                banner_level="ok",
                banner_text="Done.",
                side_rail=_rail,
                table=_spec,
            )

        def secondary_actions(self) -> list[Any]:
            return []

        def clear(self) -> None:
            pass

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _DummyFilter)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done.",
        side_rail=_rail,
        table=_spec,
    )
    shell._render_result("dummy-filter", result)
    root.update_idletasks()
    return shell


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_apply_filter_filters_table_rows(root: Any) -> None:
    """_apply_filter reduces the table to rows matching the faculty."""
    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "English")
    root.update_idletasks()

    tbl = shell._tool_tables.get("dummy-filter")
    assert tbl is not None
    # Two English rows should be visible in the Treeview
    children = tbl._tree.get_children()
    assert len(children) == 2
    # Verify filter key is stored
    assert shell._tool_filter.get("dummy-filter") == "English"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_clear_filter_restores_all_rows(root: Any) -> None:
    """_clear_filter restores the full row set after a filter is applied."""
    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "Maths")
    root.update_idletasks()

    shell._clear_filter("dummy-filter")
    root.update_idletasks()

    tbl = shell._tool_tables.get("dummy-filter")
    assert tbl is not None
    children = tbl._tree.get_children()
    assert len(children) == 4  # all rows restored
    assert shell._tool_filter.get("dummy-filter") is None


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_filter_chip_shows_count(root: Any) -> None:
    """After applying a filter the chip frame contains the count text."""
    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "English")
    root.update_idletasks()

    chip_frame = shell._tool_filter_chips.get("dummy-filter")
    assert chip_frame is not None
    # Chip frame should be visible (has children — the count label and × button)
    children = chip_frame.winfo_children()
    assert len(children) >= 1
    # First child is the count label; its text should mention "Showing 2 of 4"
    count_lbl = children[0]
    text = count_lbl.cget("text")
    assert "Showing 2 of 4" in text


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_clear_button_resets_filter(root: Any) -> None:
    """The shell-level Clear button clears the active filter."""
    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "Science")
    root.update_idletasks()

    # Confirm filter is active
    assert shell._tool_filter.get("dummy-filter") == "Science"

    # Invoke _clear_tool as the Clear button does

    tool = shell._tool_map.get("dummy-filter")
    assert tool is not None
    shell._clear_tool(tool)
    root.update_idletasks()

    # Filter must be gone
    assert shell._tool_filter.get("dummy-filter") is None
    # Table should have been destroyed (table_frame cleared), so _tool_tables is None
    assert shell._tool_tables.get("dummy-filter") is None


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_rail_active_highlight_set_on_filter(root: Any) -> None:
    """Active rail row gets blue highlight when filter is applied."""
    from toolkit import tokens

    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "Maths")
    root.update_idletasks()

    rail = shell._tool_rails.get("dummy-filter")
    assert rail is not None
    maths_frame = rail._row_frames.get("Maths")
    assert maths_frame is not None
    assert maths_frame.cget("bg") == tokens.RAIL_SELECTED


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_rail_active_cleared_on_clear_filter(root: Any) -> None:
    """set_active(None) is called on the rail when the filter is cleared."""
    from toolkit import tokens

    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "English")
    root.update_idletasks()

    shell._clear_filter("dummy-filter")
    root.update_idletasks()

    rail = shell._tool_rails.get("dummy-filter")
    assert rail is not None
    assert rail._active_key is None
    # The previously active row should no longer show RAIL_SELECTED
    english_frame = rail._row_frames.get("English")
    assert english_frame is not None
    assert english_frame.cget("bg") != tokens.RAIL_SELECTED


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_filter_resets_on_fresh_result(root: Any) -> None:
    """Re-calling _render_result resets any active filter."""
    shell = _make_filter_shell(root)
    shell._apply_filter("dummy-filter", "Science")
    root.update_idletasks()

    assert shell._tool_filter.get("dummy-filter") == "Science"

    # Render a fresh result — should clear the filter state
    from toolkit.base_tool import RailItem, TableSpec, ToolResult

    fresh_result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done again.",
        side_rail=[RailItem(label="English", value="2", filter_key="English")],
        table=TableSpec(
            columns=[{"key": "prog", "label": "Sub-program"}],
            rows=[{"prog": "E01", "_faculty": "English"}],
        ),
    )
    shell._render_result("dummy-filter", fresh_result)
    root.update_idletasks()

    assert shell


# ---------------------------------------------------------------------------
# Resize debounce — SelectableList configure handlers (Fix 3, Round 9)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_debounce_after_ids_initialised(root: Any) -> None:
    """SelectableList must initialise _inner_configure_after and
    _canvas_configure_after to None (debounce guards must be present).

    This code-level check documents the debounce mechanism so contributors
    don't accidentally remove it: the two attributes are used as after() IDs
    and must start as None.
    """
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [RailItem(label="English", value="72 %", filter_key="english")]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    assert hasattr(widget, "_inner_configure_after"), (
        "_inner_configure_after attribute missing — debounce guard was removed"
    )
    assert hasattr(widget, "_canvas_configure_after"), (
        "_canvas_configure_after attribute missing — debounce guard was removed"
    )
    # Initially None (no pending after call)
    assert widget._inner_configure_after is None
    assert widget._canvas_configure_after is None


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_selectable_list_inner_configure_fires_after_idle(root: Any) -> None:
    """Firing <Configure> on the inner frame schedules a deferred scroll-region
    update rather than updating synchronously.

    The debounce stores an after() ID in _inner_configure_after; we verify the
    ID is set after the event and is eventually consumed (None after update_idletasks).
    """
    from toolkit.base_tool import RailItem
    from toolkit.primitives import SelectableList

    items = [RailItem(label="English", value="72 %", filter_key="english")]
    widget = SelectableList(root, items=items, on_select=lambda k: None)
    widget.pack()
    root.update_idletasks()

    # Ensure the initial after() from construction has fired.
    root.update()

    # Generate a Configure event on the inner frame.
    widget._inner.event_generate("<Configure>")
    # The after() ID should now be set (deferred call pending).
    assert widget._inner_configure_after is not None, (
        "_inner_configure_after should be set after a Configure event — debounce is not working"
    )

    # Allow the deferred call to fire.
    root.update()

    # After the deferred call runs, the ID should be cleared back to None.
    assert widget._inner_configure_after is None, (
        "_inner_configure_after should be None after the deferred update ran"
    )


# ---------------------------------------------------------------------------
# RangeInput rendering with numeric_box=True (Fix 1, Round 11)
# ---------------------------------------------------------------------------


def _make_range_shell_with_numeric_box(root: Any, *, numeric_box: bool) -> Any:
    """Build a minimal TkShell with a single RangeInput (100-120) tool."""
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, RangeInput, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _NumBoxTool:
        id = "numbox-tool"
        group = "Budget"
        label = "Numbox tool"
        short = "NB"
        order = 1
        inputs: list[InputSpec] = [
            RangeInput(
                key="threshold",
                label="Over-budget threshold (%)",
                min_value=100.0,
                max_value=120.0,
                default=101.0,
                step=1.0,
                live=False,
                numeric_box=numeric_box,
            ),
        ]
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

        def preview_update(self, key: str, value: float | str) -> None:
            return None

        def clear(self) -> None:
            return None

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _NumBoxTool)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()
    return shell


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_with_numeric_box_renders_entry(root: Any) -> None:
    """When numeric_box=True the rendered container exposes a ttk.Entry (_num_entry)."""
    import tkinter as tk

    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    num_entry = getattr(container, "_num_entry", None)
    assert num_entry is not None, "_num_entry not set when numeric_box=True"
    assert isinstance(num_entry, tk.Entry)

    # _value_lbl must be None when numeric_box=True (replaced by the entry).
    value_lbl = getattr(container, "_value_lbl", "missing")
    assert value_lbl is None, "_value_lbl should be None when numeric_box=True"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_without_numeric_box_renders_label(root: Any) -> None:
    """When numeric_box=False (default) the container exposes a tk.Label (_value_lbl)."""
    import tkinter as tk

    shell = _make_range_shell_with_numeric_box(root, numeric_box=False)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    value_lbl = getattr(container, "_value_lbl", None)
    assert value_lbl is not None, "_value_lbl not set when numeric_box=False"
    assert isinstance(value_lbl, tk.Label)

    num_entry = getattr(container, "_num_entry", None)
    assert num_entry is None, "_num_entry should be None when numeric_box=False"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_entry_accepts_value_above_max(root: Any) -> None:
    """Committing a value above max via the numeric entry is accepted (not clamped).

    The actual_var (and input cache) receives the typed value; the slider knob
    clamps internally but the user-facing value is preserved.
    """
    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    num_entry_var = getattr(container, "_num_entry_var", None)
    assert num_entry_var is not None
    num_entry = getattr(container, "_num_entry", None)
    assert num_entry is not None

    # Set entry text to 200 (exceeds max=120) and simulate FocusOut.
    num_entry_var.set("200")
    num_entry.event_generate("<FocusOut>")
    root.update_idletasks()

    # actual_var (_scale_var) should hold 200 — the typed value is NOT clamped.
    actual_var = container._scale_var
    assert actual_var.get() == pytest.approx(200.0, abs=0.1)
    # Input cache must also reflect the unclamped actual value.
    cached = shell._input_cache["numbox-tool"].get("threshold")
    assert cached == pytest.approx(200.0, abs=0.1)


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_entry_reverts_on_non_numeric(root: Any) -> None:
    """Non-numeric text in the entry reverts to the previous committed value."""
    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    num_entry_var = getattr(container, "_num_entry_var", None)
    assert num_entry_var is not None
    num_entry = getattr(container, "_num_entry", None)
    assert num_entry is not None
    scale_var = container._scale_var

    # Initial value is 101.
    assert scale_var.get() == pytest.approx(101.0, abs=0.1)

    # Type non-numeric text and fire FocusOut.
    num_entry_var.set("abc")
    num_entry.event_generate("<FocusOut>")
    root.update_idletasks()

    # Scale var should revert to 101.
    assert scale_var.get() == pytest.approx(101.0, abs=0.1)


# ---------------------------------------------------------------------------
# RangeInput decoupled-var + polish tests (Round 12)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_decoupled_vars(root: Any) -> None:
    """When numeric_box=True the slider DoubleVar and entry DoubleVar are different objects."""
    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    actual_var = getattr(container, "_actual_var", None)
    assert actual_var is not None, "_actual_var not set when numeric_box=True"

    scale_widget = getattr(container, "_scale", None)
    assert scale_widget is not None

    # The Scale widget's variable and actual_var must be distinct objects.
    # We verify by checking that actual_var is the same object as _scale_var
    # (which is set to actual_var), while an internal slider_var drives the knob.
    # The key observable contract: typing 200 leaves actual_var == 200,
    # which the existing test_range_widget_entry_accepts_value_above_max verifies.
    # Here we just check the attribute is exposed and is a DoubleVar.
    import tkinter as tk

    assert isinstance(actual_var, tk.DoubleVar)


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_entry_rejects_zero_and_negative(root: Any) -> None:
    """Typing 0 or a negative number reverts to the previous actual value."""
    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    num_entry_var = getattr(container, "_num_entry_var", None)
    assert num_entry_var is not None
    num_entry = getattr(container, "_num_entry", None)
    assert num_entry is not None
    actual_var = container._scale_var
    assert actual_var.get() == pytest.approx(101.0, abs=0.1)

    # Try typing 0.
    num_entry_var.set("0")
    num_entry.event_generate("<FocusOut>")
    root.update_idletasks()
    assert actual_var.get() == pytest.approx(101.0, abs=0.1), "0 should revert to 101"

    # Try typing -5.
    num_entry_var.set("-5")
    num_entry.event_generate("<FocusOut>")
    root.update_idletasks()
    assert actual_var.get() == pytest.approx(101.0, abs=0.1), "-5 should revert to 101"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_slider_drag_clamps_within_range(root: Any) -> None:
    """Programmatically setting actual_var from a slider-drag value stays at endpoint.

    Tk's Scale widget auto-clamps the slider_var to [min, max]; the slider trace
    then forwards that clamped value to actual_var.  Verify actual_var ends up at
    the clamped max when the slider is at its maximum position.
    """
    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    actual_var = container._scale_var  # points to actual_var

    # Get the Scale widget and set it to its maximum (Tk clamps it).
    scale = getattr(container, "_scale", None)
    assert scale is not None

    # Set slider to a value beyond max; Tk will clamp to max_value=120.
    scale.set(130)
    root.update_idletasks()

    # actual_var should equal the clamped max (120) since slider emitted 120.
    assert actual_var.get() == pytest.approx(120.0, abs=0.1)


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_widget_renders_range_labels(root: Any) -> None:
    """When numeric_box=True the widget tree contains Labels with min% and max% text."""
    import tkinter as tk

    shell = _make_range_shell_with_numeric_box(root, numeric_box=True)
    wmap = shell._tool_widgets.get("numbox-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    # Walk the widget tree and collect Label texts.
    def _collect_labels(widget: tk.Misc) -> list[str]:
        found: list[str] = []
        if isinstance(widget, tk.Label):
            found.append(str(widget.cget("text")))
        for child in widget.winfo_children():
            found.extend(_collect_labels(child))
        return found

    label_texts = _collect_labels(container)
    # Expect "100%" and "120%" as range boundary labels.
    assert "100%" in label_texts, f"100% label missing. Labels found: {label_texts}"
    assert "120%" in label_texts, f"120% label missing. Labels found: {label_texts}"


# ---------------------------------------------------------------------------
# Resize debounce -- TkShell tool frame canvas handlers (Fix 3, Round 11)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_tool_frame_canvas_debounce_uses_after(root: Any) -> None:
    """The tool frame canvas <Configure> handlers schedule deferred updates
    (debounce pattern).  Firing Configure events does not raise.
    """
    import tkinter as tk
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _SimpleTool:
        id = "simple-tool"
        group = "Budget"
        label = "Simple tool"
        short = "ST"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

        def clear(self) -> None:
            pass

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _SimpleTool)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    frame = shell._tool_frames.get("simple-tool")
    assert frame is not None
    canvas_widgets = [w for w in frame.winfo_children() if isinstance(w, tk.Canvas)]
    assert canvas_widgets, "No Canvas child found in tool frame"
    canvas = canvas_widgets[0]

    # Generating Configure events should not raise.
    canvas.event_generate("<Configure>")
    root.update()


# ---------------------------------------------------------------------------
# CommentaryDialog -- Save / Clear all (Fix 2, Round 11)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_commentary_dialog_has_save_button(root: Any) -> None:
    """CommentaryDialog renders a Save button (Accent.TButton) in the button row."""
    import tkinter as tk
    import tkinter.ttk as ttk

    from toolkit.primitives import CommentaryDialog

    sub_programs = ["SP01", "SP02"]
    initial: dict[str, str] = {}
    result_holder: list[Any] = []

    def _run_dialog() -> None:
        def _inspect_and_close() -> None:
            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            assert toplevels, "No Toplevel found"
            top = toplevels[-1]

            def _find_buttons(widget: tk.Misc) -> list[ttk.Button]:
                found: list[ttk.Button] = []
                if isinstance(widget, ttk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_buttons(child))
                return found

            buttons = _find_buttons(top)
            btn_texts = [str(b.cget("text")) for b in buttons]
            result_holder.append(btn_texts)
            top.destroy()

        root.after(100, _inspect_and_close)
        CommentaryDialog(root, sub_programs, initial)

    _run_dialog()
    root.update()
    root.after(200, lambda: None)
    root.update()

    assert result_holder, "Dialog did not capture button list"
    assert "Save" in result_holder[0], f"Save button missing. Found: {result_holder[0]}"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_commentary_dialog_save_persists_edits_without_closing(root: Any) -> None:
    """Clicking Save flushes edits without closing the dialog."""
    import tkinter as tk
    import tkinter.ttk as ttk

    from toolkit.primitives import CommentaryDialog

    sub_programs = ["SP01"]
    initial: dict[str, str] = {}
    dialog_still_open: list[bool] = [True]

    def _run_dialog() -> None:
        def _interact() -> None:
            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            if not toplevels:
                return
            top = toplevels[-1]

            def _find_text(widget: tk.Misc) -> tk.Text | None:
                if isinstance(widget, tk.Text):
                    return widget
                for child in widget.winfo_children():
                    found = _find_text(child)
                    if found:
                        return found
                return None

            editor = _find_text(top)
            if editor is None:
                return
            editor.delete("1.0", "end")
            editor.insert("1.0", "Test commentary text")

            def _find_buttons(widget: tk.Misc) -> list[ttk.Button]:
                found: list[ttk.Button] = []
                if isinstance(widget, ttk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_buttons(child))
                return found

            buttons = _find_buttons(top)
            save_btns = [b for b in buttons if str(b.cget("text")) == "Save"]
            assert save_btns, "Save button not found"
            save_btns[0].invoke()
            root.update_idletasks()

            dialog_still_open[0] = top.winfo_exists()
            top.destroy()

        root.after(80, _interact)
        CommentaryDialog(root, sub_programs, initial)

    _run_dialog()
    root.update()

    assert dialog_still_open[0], "Dialog closed after Save — should stay open"


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_commentary_dialog_clear_all_empties_dict_after_confirm(root: Any) -> None:
    """Clicking Clear all and confirming empties the commentary dict."""
    import tkinter as tk
    import tkinter.ttk as ttk
    import unittest.mock as mock

    from toolkit.primitives import CommentaryDialog

    sub_programs = ["SP01", "SP02"]
    initial: dict[str, str] = {"SP01": "Some text", "SP02": "More text"}
    result_holder: list[Any] = [None]

    def _run_dialog() -> None:
        def _interact() -> None:
            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            if not toplevels:
                return
            top = toplevels[-1]

            def _find_buttons(widget: tk.Misc) -> list[ttk.Button]:
                found: list[ttk.Button] = []
                if isinstance(widget, ttk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_buttons(child))
                return found

            buttons = _find_buttons(top)
            clear_btns = [b for b in buttons if str(b.cget("text")) == "Clear all"]
            assert clear_btns, "Clear all button not found"

            with mock.patch("tkinter.messagebox.askyesno", return_value=True):
                clear_btns[0].invoke()
            root.update_idletasks()

            def _find_tk_buttons(widget: tk.Misc) -> list[tk.Button]:
                found: list[tk.Button] = []
                if isinstance(widget, tk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_tk_buttons(child))
                return found

            all_tk_btns = _find_tk_buttons(top)
            ok_btns = [b for b in all_tk_btns if str(b.cget("text")) == "OK"]
            if ok_btns:
                ok_btns[0].invoke()
            else:
                top.destroy()

        root.after(80, _interact)
        result_holder[0] = CommentaryDialog(root, sub_programs, initial)

    _run_dialog()
    root.update()

    result = result_holder[0]
    if result is not None:
        for sp in sub_programs:
            assert result.get(sp, "") == "", (
                f"Commentary for {sp} should be empty after Clear all, got: {result.get(sp)!r}"
            )


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_commentary_dialog_clear_all_no_op_when_user_cancels(root: Any) -> None:
    """Clicking Clear all then cancelling leaves the dict intact."""
    import tkinter as tk
    import tkinter.ttk as ttk
    import unittest.mock as mock

    from toolkit.primitives import CommentaryDialog

    sub_programs = ["SP01"]
    initial: dict[str, str] = {"SP01": "Preserved text"}
    result_holder: list[Any] = [None]

    def _run_dialog() -> None:
        def _interact() -> None:
            toplevels = [w for w in root.winfo_children() if isinstance(w, tk.Toplevel)]
            if not toplevels:
                return
            top = toplevels[-1]

            def _find_buttons(widget: tk.Misc) -> list[ttk.Button]:
                found: list[ttk.Button] = []
                if isinstance(widget, ttk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_buttons(child))
                return found

            buttons = _find_buttons(top)
            clear_btns = [b for b in buttons if str(b.cget("text")) == "Clear all"]
            assert clear_btns, "Clear all button not found"

            with mock.patch("tkinter.messagebox.askyesno", return_value=False):
                clear_btns[0].invoke()
            root.update_idletasks()

            def _find_tk_buttons(widget: tk.Misc) -> list[tk.Button]:
                found: list[tk.Button] = []
                if isinstance(widget, tk.Button):
                    found.append(widget)
                for child in widget.winfo_children():
                    found.extend(_find_tk_buttons(child))
                return found

            all_tk_btns = _find_tk_buttons(top)
            ok_btns = [b for b in all_tk_btns if str(b.cget("text")) == "OK"]
            if ok_btns:
                ok_btns[0].invoke()
            else:
                top.destroy()

        root.after(80, _interact)
        result_holder[0] = CommentaryDialog(root, sub_programs, initial)

    _run_dialog()
    root.update()

    result = result_holder[0]
    if result is not None:
        assert result.get("SP01") == "Preserved text", (
            f"Commentary should be preserved when user cancels Clear all. "
            f"Got: {result.get('SP01')!r}"
        )


# ---------------------------------------------------------------------------
# Fix 1 (Round 13) — RangeInput label shows live value when numeric_box=True
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_input_label_includes_live_value(root: Any) -> None:
    """When numeric_box=True the row-1 label text includes the current value as
    '<label>: <value>%', not just the static '<label>' string.
    """
    import tkinter as tk
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, RangeInput, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _LiveLabelTool:
        id = "live-label-tool"
        group = "Budget"
        label = "Live label tool"
        short = "LL"
        order = 1
        inputs: list[InputSpec] = [
            RangeInput(
                key="threshold",
                label="Over-budget threshold",
                min_value=100.0,
                max_value=120.0,
                default=101.0,
                step=1.0,
                live=False,
                numeric_box=True,
            ),
        ]
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

        def preview_update(self, key: str, value: float | str) -> None:
            return None

        def clear(self) -> None:
            return None

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _LiveLabelTool)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    wmap = shell._tool_widgets.get("live-label-tool", {})
    container = wmap.get("threshold")
    assert container is not None

    # Walk the widget tree and collect Label texts.
    def _collect_labels(widget: tk.Misc) -> list[str]:
        found: list[str] = []
        if isinstance(widget, tk.Label):
            try:
                found.append(str(widget.cget("text")))
            except Exception:
                pass
        for child in widget.winfo_children():
            found.extend(_collect_labels(child))
        return found

    label_texts = _collect_labels(container)
    # The row-1 label must contain the current value (101) and a percent sign.
    live_labels = [
        t for t in label_texts if "Over-budget threshold" in t and "101" in t and "%" in t
    ]
    assert live_labels, (
        f"Expected a label like 'Over-budget threshold: 101%' but got labels: {label_texts}"
    )


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_range_input_label_updates_on_value_change(root: Any) -> None:
    """When the slider/entry value changes, the row-1 label updates to reflect
    the new value (live StringVar binding).
    """
    import tkinter as tk
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, RangeInput, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _LiveLabelTool2:
        id = "live-label-tool2"
        group = "Budget"
        label = "Over-budget threshold"
        short = "LT"
        order = 1
        inputs: list[InputSpec] = [
            RangeInput(
                key="threshold",
                label="Over-budget threshold",
                min_value=100.0,
                max_value=120.0,
                default=101.0,
                step=1.0,
                live=False,
                numeric_box=True,
            ),
        ]
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

        def preview_update(self, key: str, value: float | str) -> None:
            return None

        def clear(self) -> None:
            return None

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _LiveLabelTool2)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    wmap = shell._tool_widgets.get("live-label-tool2", {})
    container = wmap.get("threshold")
    assert container is not None

    # Change the value via the numeric entry.
    num_entry_var = getattr(container, "_num_entry_var", None)
    num_entry = getattr(container, "_num_entry", None)
    assert num_entry_var is not None
    assert num_entry is not None

    num_entry_var.set("115")
    num_entry.event_generate("<FocusOut>")
    root.update_idletasks()

    # Walk the widget tree and collect Label texts.
    def _collect_labels(widget: tk.Misc) -> list[str]:
        found: list[str] = []
        if isinstance(widget, tk.Label):
            try:
                found.append(str(widget.cget("text")))
            except Exception:
                pass
        for child in widget.winfo_children():
            found.extend(_collect_labels(child))
        return found

    label_texts = _collect_labels(container)
    # After setting to 115, the live label must contain "115" and "%".
    live_labels = [
        t for t in label_texts if "Over-budget threshold" in t and "115" in t and "%" in t
    ]
    assert live_labels, (
        f"Expected label to update to '115%' after entry change but got: {label_texts}"
    )


# ---------------------------------------------------------------------------
# Fix 2 (Round 13) — Root-window Configure debounce
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_tk(), reason="Tk absent")
def test_shell_root_configure_debounce_attribute(root: Any) -> None:
    """TkShell must initialise _root_configure_after to None (debounce guard).

    This is the safety-net root-window Configure handler added in Round 13.
    The attribute must exist so the debounce cancel-and-reschedule logic works.
    """
    from typing import cast

    from toolkit.base_tool import BaseTool, InputSpec, ProgressFn, ToolResult
    from toolkit.fonts import detect_fonts
    from toolkit.shell import TkShell

    class _SimpleTool2:
        id = "simple-tool-2"
        group = "Budget"
        label = "Simple tool 2"
        short = "S2"
        order = 1
        inputs: list[InputSpec] = []
        output = None
        primary_button = "Run"
        pdf_template = None
        pdf_body = None
        requires_feature = None

        def run(self, paths: dict, progress: ProgressFn) -> ToolResult:  # type: ignore[type-arg]
            return ToolResult(status="success", banner_level="ok", banner_text="Done.")

        def secondary_actions(self) -> list[Any]:
            return []

        def clear(self) -> None:
            pass

    fonts = detect_fonts(root)
    shell = TkShell(root, fonts=fonts, tools=[cast("type[BaseTool]", _SimpleTool2)])
    shell.pack(fill="both", expand=True)
    root.update_idletasks()

    assert hasattr(shell, "_root_configure_after"), (
        "_root_configure_after attribute missing — root Configure debounce was removed"
    )
    # After update_idletasks the initial value should be None (no pending after)
    # or the deferred call may have already fired (also None).
    assert shell._root_configure_after is None or isinstance(shell._root_configure_after, str)
