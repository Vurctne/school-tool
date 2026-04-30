from __future__ import annotations

import dataclasses

import pytest

from toolkit.base_tool import (
    BannerLevel,
    CurrencyInput,
    DateInput,
    FileInput,
    InputSpec,
    LogLine,
    NumberInput,
    OutputSpec,
    RailItem,
    RangeInput,
    SecretInput,
    Status,
    TableSpec,
    TextInput,
    ToolResult,
)

# ---------------------------------------------------------------------------
# InputSpec kind discriminator tests
# ---------------------------------------------------------------------------


def test_file_input_kind() -> None:
    spec = FileInput(key="expense_file", label="Expense XLSX")
    assert spec.kind == "file"
    assert spec.key == "expense_file"
    assert spec.filetypes == []


def test_text_input_kind() -> None:
    spec = TextInput(key="note", label="Note", placeholder="Enter text", max_length=100)
    assert spec.kind == "text"
    assert spec.max_length == 100


def test_number_input_kind() -> None:
    spec = NumberInput(key="count", label="Count", min_value=0.0, max_value=999.0, decimals=2)
    assert spec.kind == "number"
    assert spec.decimals == 2


def test_currency_input_kind() -> None:
    spec = CurrencyInput(key="amount", label="Amount (AUD)")
    assert spec.kind == "currency"


def test_date_input_kind() -> None:
    spec = DateInput(key="transfer_date", label="Transfer Date", default="today")
    assert spec.kind == "date"
    assert spec.default == "today"


def test_secret_input_kind_and_defaults() -> None:
    spec = SecretInput(key="sin", label="SIN", pattern=r"\d{4,6}", remember_key="hyia_sin")
    assert spec.kind == "secret"
    assert spec.pattern == r"\d{4,6}"
    assert spec.remember_key == "hyia_sin"


def test_secret_input_default_remember_key_is_none() -> None:
    spec = SecretInput(key="pin", label="PIN")
    assert spec.remember_key is None


# ---------------------------------------------------------------------------
# Frozen dataclass immutability
# ---------------------------------------------------------------------------


def test_file_input_is_frozen() -> None:
    spec = FileInput(key="f", label="File")
    with pytest.raises((AttributeError, TypeError)):
        spec.key = "other"  # type: ignore[misc]


def test_secret_input_is_frozen() -> None:
    spec = SecretInput(key="s", label="Secret")
    with pytest.raises((AttributeError, TypeError)):
        spec.label = "Changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# InputSpec union discrimination via match / isinstance
# ---------------------------------------------------------------------------


def test_input_spec_discrimination_match() -> None:
    specs: list[InputSpec] = [
        FileInput(key="a", label="A"),
        TextInput(key="b", label="B"),
        NumberInput(key="c", label="C"),
        CurrencyInput(key="d", label="D"),
        DateInput(key="e", label="E"),
        SecretInput(key="f", label="F"),
    ]
    kinds = [s.kind for s in specs]
    assert kinds == ["file", "text", "number", "currency", "date", "secret"]


def test_input_spec_isinstance() -> None:
    spec: InputSpec = SecretInput(key="sin", label="SIN")
    assert isinstance(spec, SecretInput)
    assert not isinstance(spec, FileInput)


# ---------------------------------------------------------------------------
# OutputSpec
# ---------------------------------------------------------------------------


def test_output_spec_fields() -> None:
    out = OutputSpec(key="output_file", label="Output workbook", suffix=".xlsm")
    assert out.suffix == ".xlsm"


# ---------------------------------------------------------------------------
# LogLine
# ---------------------------------------------------------------------------


def test_log_line_defaults() -> None:
    line = LogLine(text="All done")
    assert line.tag is None


def test_log_line_with_tag() -> None:
    line = LogLine(text="3 mismatches found", tag="warning")
    assert line.tag == "warning"


# ---------------------------------------------------------------------------
# ToolResult construction -- minimum fields only
# ---------------------------------------------------------------------------


def test_tool_result_minimum() -> None:
    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Completed successfully.",
    )
    assert result.status == "success"
    assert result.log_lines == []
    assert result.metrics == []
    assert result.table_columns is None
    assert result.table_rows is None
    assert result.output_path is None


def test_tool_result_with_log_lines() -> None:
    lines = [LogLine("Heading", "heading"), LogLine("All matched", "ok")]
    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done",
        log_lines=lines,
    )
    assert len(result.log_lines) == 2
    assert result.log_lines[0].tag == "heading"


def test_tool_result_error_state() -> None:
    result = ToolResult(
        status="error",
        banner_level="danger",
        banner_text="Unreadable file.",
    )
    assert result.status == "error"
    assert result.banner_level == "danger"


def test_tool_result_with_metrics() -> None:
    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done",
        metrics=[("Revenue", "$1,234", "ok"), ("Expenditure", "$999", None)],
    )
    assert result.metrics[0] == ("Revenue", "$1,234", "ok")
    assert result.metrics[1][2] is None


# ---------------------------------------------------------------------------
# Status and BannerLevel Literal typing (runtime value checks)
# ---------------------------------------------------------------------------


def test_status_values_are_strings() -> None:
    statuses: list[Status] = ["idle", "running", "success", "warning", "error"]
    assert all(isinstance(s, str) for s in statuses)


def test_banner_level_values_are_strings() -> None:
    levels: list[BannerLevel] = ["neutral", "ok", "warning", "danger", "info"]
    assert all(isinstance(lv, str) for lv in levels)


# ---------------------------------------------------------------------------
# RailItem and TableSpec (phase-3 additions)
# ---------------------------------------------------------------------------


def test_tool_result_defaults_side_rail_and_table_to_none() -> None:
    """ToolResult constructed without the new kwargs has side_rail=None, table=None."""
    result = ToolResult(
        status="success",
        banner_level="ok",
        banner_text="Done.",
    )
    assert result.side_rail is None
    assert result.table is None


def test_tool_result_existing_fields_unaffected() -> None:
    """All pre-phase-3 fields still work as before after the schema extension."""
    result = ToolResult(
        status="warning",
        banner_level="warning",
        banner_text="Some warnings.",
        log_lines=[LogLine("note", "muted")],
        metrics=[("Revenue", "$1,234", "ok")],
        table_columns=[{"key": "col", "label": "Col"}],
        table_rows=[{"col": "val"}],
    )
    assert result.status == "warning"
    assert result.table_columns is not None
    assert result.table_rows is not None
    assert result.side_rail is None
    assert result.table is None


def test_rail_item_is_frozen() -> None:
    """RailItem is a frozen dataclass -- mutation raises FrozenInstanceError."""
    item = RailItem(label="English", value="72 %", filter_key="english")
    assert item.label == "English"
    assert item.value == "72 %"
    assert item.filter_key == "english"
    assert item.highlight is False
    with pytest.raises(dataclasses.FrozenInstanceError):
        item.label = "Maths"  # type: ignore[misc]


def test_rail_item_highlight_default_false() -> None:
    item = RailItem(label="Maths", value="105 %", filter_key="maths")
    assert item.highlight is False


def test_rail_item_highlight_true() -> None:
    item = RailItem(label="Maths", value="105 %", filter_key="maths", highlight=True)
    assert item.highlight is True


def test_table_spec_is_frozen() -> None:
    """TableSpec is a frozen dataclass."""
    spec = TableSpec(
        columns=[{"key": "name", "label": "Name"}],
        rows=[{"name": "Row 1"}],
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.columns = []  # type: ignore[misc]


def test_table_spec_callbacks_are_optional() -> None:
    """TableSpec can be constructed with only columns and rows."""
    spec = TableSpec(columns=[], rows=[])
    assert spec.row_style is None
    assert spec.on_row_click is None


def test_table_spec_with_callbacks() -> None:
    """TableSpec stores callable fields correctly."""
    called: list[str] = []

    def style_fn(row: dict) -> dict[str, str]:  # type: ignore[type-arg]
        return {"background": "#F4CCCC"} if row.get("over") else {}

    def click_fn(row: dict) -> None:  # type: ignore[type-arg]
        called.append(row.get("name", ""))

    spec = TableSpec(
        columns=[{"key": "name", "label": "Name"}],
        rows=[{"name": "Row 1", "over": True}],
        row_style=style_fn,
        on_row_click=click_fn,
    )
    assert spec.row_style is style_fn
    assert spec.on_row_click is click_fn

    assert spec.row_style({"over": True}) == {"background": "#F4CCCC"}
    assert spec.row_style({"over": False}) == {}

    spec.on_row_click({"name": "test-row"})
    assert called == ["test-row"]


def test_tool_result_with_side_rail_and_table() -> None:
    """ToolResult populated with new fields stores them correctly."""
    items = [
        RailItem(label="English", value="72 %", filter_key="english"),
        RailItem(label="Maths", value="105 %", filter_key="maths", highlight=True),
    ]
    spec = TableSpec(
        columns=[{"key": "sub_program", "label": "Sub-program"}],
        rows=[{"sub_program": "English"}],
    )
    result = ToolResult(
        status="warning",
        banner_level="warning",
        banner_text="Over-budget rows found.",
        side_rail=items,
        table=spec,
    )
    assert result.side_rail is not None
    assert len(result.side_rail) == 2
    assert result.side_rail[1].highlight is True
    assert result.table is spec


# ---------------------------------------------------------------------------
# RangeInput (phase-4 additions)
# ---------------------------------------------------------------------------


def test_range_input_is_input_spec() -> None:
    """RangeInput is a member of the InputSpec union."""
    spec: InputSpec = RangeInput(
        key="threshold",
        label="Over-budget threshold (%)",
        min_value=0.0,
        max_value=300.0,
        default=101.0,
    )
    assert isinstance(spec, RangeInput)


def test_range_input_default_step_1() -> None:
    """RangeInput.step defaults to 1.0."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0)
    assert spec.step == 1.0


def test_range_input_live_default_true() -> None:
    """RangeInput.live defaults to True (enables preview_update callback)."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0)
    assert spec.live is True


def test_range_input_live_false() -> None:
    """RangeInput.live=False disables the live preview callback."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0, live=False)
    assert spec.live is False


def test_range_input_is_frozen() -> None:
    """RangeInput is a frozen dataclass — mutation raises FrozenInstanceError."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0)
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        spec.key = "other"  # type: ignore[misc]


def test_range_input_kind() -> None:
    """RangeInput has kind == 'range'."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0)
    assert spec.kind == "range"


def test_range_input_in_input_spec_isinstance() -> None:
    """isinstance checks against InputSpec union work for RangeInput."""
    spec: InputSpec = RangeInput(key="t", label="T", min_value=0.0, max_value=200.0, default=101.0)
    assert isinstance(spec, RangeInput)
    assert not isinstance(spec, FileInput)
    assert not isinstance(spec, NumberInput)


# ---------------------------------------------------------------------------
# RangeInput.numeric_box (Round 11 additions)
# ---------------------------------------------------------------------------


def test_range_input_numeric_box_default_false() -> None:
    """RangeInput.numeric_box defaults to False so existing call sites are unaffected."""
    spec = RangeInput(key="k", label="L", min_value=0.0, max_value=100.0, default=50.0)
    assert spec.numeric_box is False


def test_range_input_numeric_box_true_round_trip() -> None:
    """RangeInput can be constructed with numeric_box=True and the value survives."""
    spec = RangeInput(
        key="threshold",
        label="Over-budget threshold (%)",
        min_value=100.0,
        max_value=120.0,
        default=101.0,
        step=1.0,
        live=True,
        numeric_box=True,
    )
    assert spec.numeric_box is True
    # Verify other fields are not disturbed.
    assert spec.min_value == 100.0
    assert spec.max_value == 120.0
    assert spec.default == 101.0
    assert spec.step == 1.0
    assert spec.live is True
    # Frozen — mutation must raise.
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        spec.numeric_box = False  # type: ignore[misc]


# ------------------------------------------
