from __future__ import annotations

import pytest  # noqa: F401 — used for pytest.raises

from toolkit.base_tool import (
    BannerLevel,
    CurrencyInput,
    DateInput,
    FileInput,
    InputSpec,
    LogLine,
    NumberInput,
    OutputSpec,
    SecretInput,
    Status,
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
# ToolResult construction — minimum fields only
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
