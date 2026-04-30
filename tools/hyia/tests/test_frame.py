from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

from toolkit.base_tool import (
    CurrencyInput,
    DateInput,
    InputSpec,
    SecretInput,
    ToolResult,
)
from tools.hyia.frame import HyiaTool


def test_hyia_tool_has_required_attrs() -> None:
    """HyiaTool conforms structurally to BaseTool (has all required attributes)."""
    tool = HyiaTool()
    assert hasattr(tool, "id")
    assert hasattr(tool, "group")
    assert hasattr(tool, "label")
    assert hasattr(tool, "short")
    assert hasattr(tool, "order")
    assert hasattr(tool, "inputs")
    assert hasattr(tool, "output")
    assert hasattr(tool, "primary_button")
    assert hasattr(tool, "pdf_template")
    assert hasattr(tool, "pdf_body")
    assert callable(tool.run)
    assert callable(tool.secondary_actions)


def test_hyia_tool_class_attrs() -> None:
    assert HyiaTool.id == "hyia"
    assert HyiaTool.group == "Banking"
    assert HyiaTool.label == "HYIA Transfer Code"
    assert HyiaTool.short == "HY"
    assert HyiaTool.order == 10
    assert HyiaTool.primary_button == "Generate code"
    assert HyiaTool.pdf_template is None
    assert HyiaTool.pdf_body is None
    assert HyiaTool.output is None


def test_inputs_list_has_three_items() -> None:
    assert len(HyiaTool.inputs) == 3


def test_inputs_correct_kinds() -> None:
    from typing import cast

    inputs = cast(list[InputSpec], HyiaTool.inputs)
    assert inputs[0].kind == "secret"
    assert inputs[1].kind == "currency"
    assert inputs[2].kind == "date"


def test_inputs_are_correct_types() -> None:
    assert isinstance(HyiaTool.inputs[0], SecretInput)
    assert isinstance(HyiaTool.inputs[1], CurrencyInput)
    assert isinstance(HyiaTool.inputs[2], DateInput)


def test_run_doe_worked_example() -> None:
    """run() with DoE worked example returns ToolResult with correct security code."""
    tool = HyiaTool()
    progress = MagicMock()

    paths: dict[str, object] = {
        "sin": "12345",
        "amount": "$20,000.00",
        "date": date(2007, 2, 16),
    }

    result = tool.run(paths, progress)

    assert isinstance(result, ToolResult)
    assert result.status == "success"

    # Check the metric tuple contains the correct security code
    assert len(result.metrics) == 1
    label, value, tone = result.metrics[0]
    assert label == "Security code"
    assert value == "2012370"
    assert tone == "ok"


def test_run_calls_progress() -> None:
    tool = HyiaTool()
    progress = MagicMock()

    paths: dict[str, object] = {
        "sin": "12345",
        "amount": "$20,000.00",
        "date": date(2007, 2, 16),
    }

    tool.run(paths, progress)
    progress.assert_called_once_with(100, "Calculating…")


def test_run_log_lines_show_placeholder_only() -> None:
    """Round 21 — log_lines no longer contain the formula directly.

    Anyone glancing at the screen should see only the security code, not
    the SIN-derived breakdown.  The formula is exposed on demand via the
    press-and-hold "Show formula" button.
    """
    tool = HyiaTool()
    progress = MagicMock()

    paths: dict[str, object] = {
        "sin": "12345",
        "amount": "$20,000.00",
        "date": date(2007, 2, 16),
    }

    result = tool.run(paths, progress)

    assert len(result.log_lines) == 1
    log = result.log_lines[0]
    # Formula is NOT in the log line directly any more.
    assert "12345" not in log.text
    assert "2000000" not in log.text
    assert "2012370" not in log.text
    # Placeholder mentions the press-and-hold button by name.
    assert "Show formula" in log.text
    assert log.tag == "muted"


def test_press_hold_formula_text_masks_sin() -> None:
    """Round 21 — press-and-hold reveal exposes formula text with SIN masked."""
    tool = HyiaTool()
    progress = MagicMock()

    paths: dict[str, object] = {
        "sin": "12345",
        "amount": "$20,000.00",
        "date": date(2007, 2, 16),
    }
    tool.run(paths, progress)

    actions = tool.press_hold_actions()
    assert len(actions) == 1
    label, get_text = actions[0]
    assert label == "Show formula"

    formula = get_text()
    # Same audit content as before — only the surface area moved.
    assert "12345" not in formula
    assert "*****" in formula
    assert "2000000" in formula
    assert "2012370" in formula


def test_press_hold_formula_six_digit_sin_masked() -> None:
    """Round 21 — six-digit SIN masked with six asterisks in revealed formula."""
    tool = HyiaTool()
    progress = MagicMock()

    paths: dict[str, object] = {
        "sin": "123456",
        "amount": "$100.00",
        "date": date(2026, 4, 24),
    }
    tool.run(paths, progress)

    formula = tool.press_hold_actions()[0][1]()
    assert "123456" not in formula
    assert "******" in formula


def test_press_hold_empty_before_run() -> None:
    """Round 21 — before any run(), the press-hold reveal returns empty."""
    tool = HyiaTool()
    formula = tool.press_hold_actions()[0][1]()
    assert formula == ""


def test_clear_resets_cached_formula() -> None:
    """Round 21 — Clear must wipe the cached formula so it can't leak."""
    tool = HyiaTool()
    tool.run(
        {"sin": "12345", "amount": "$1.00", "date": date(2026, 4, 24)},
        MagicMock(),
    )
    # Sanity — formula is populated after run.
    assert tool.press_hold_actions()[0][1]() != ""
    tool.clear()
    # After Clear, the reveal returns empty.
    assert tool.press_hold_actions()[0][1]() == ""


def test_secondary_actions_empty() -> None:
    tool = HyiaTool()
    assert tool.secondary_actions() == []
