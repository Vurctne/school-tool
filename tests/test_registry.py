from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest

from toolkit.base_tool import InputSpec, OutputSpec, ProgressFn, ToolResult
from toolkit.registry import _registered, register

# ---------------------------------------------------------------------------
# Minimal stub that structurally satisfies BaseTool (Protocol)
# ---------------------------------------------------------------------------


class _StubTool:
    id: str = "stub"
    group: str = "Test"
    label: str = "Stub Tool"
    short: str = "ST"
    order: int = 99
    inputs: list[InputSpec] = []
    output: OutputSpec | None = None
    primary_button: str = "Run"
    pdf_template: str | None = None
    pdf_body: str | None = None
    requires_feature: str | None = None

    def run(self, paths: dict[str, Any], progress: ProgressFn) -> ToolResult:
        return ToolResult(status="success", banner_level="ok", banner_text="stub")

    def secondary_actions(self) -> list[tuple[str, Callable[..., None]]]:
        return []

    def clear(self) -> None:
        return None

    def preview_update(self, key: str, value: float | str) -> None:
        return None


class _AnotherStubTool(_StubTool):
    id: str = "another-stub"
    label: str = "Another Stub Tool"
    order: int = 100


# ---------------------------------------------------------------------------
# Helper: snapshot and restore _registered across tests to avoid pollution
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolate_registry() -> Any:
    """Snapshot and restore the global _registered list around each test."""
    original = list(_registered)
    yield
    _registered.clear()
    _registered.extend(original)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_registry_starts_empty_before_tool_imports() -> None:
    """_registered should not contain _StubTool before register() is called."""
    assert _StubTool not in _registered


def test_register_adds_tool() -> None:
    register(_StubTool)
    assert _StubTool in _registered


def test_register_is_idempotent() -> None:
    """Calling register() twice with the same class must not duplicate it."""
    register(_StubTool)
    register(_StubTool)
    count = _registered.count(_StubTool)
    assert count == 1


def test_register_multiple_distinct_tools() -> None:
    register(_StubTool)
    register(_AnotherStubTool)
    assert _StubTool in _registered
    assert _AnotherStubTool in _registered
    assert len([c for c in _registered if c in (_StubTool, _AnotherStubTool)]) == 2


def test_register_order_preserved() -> None:
    """Tools should appear in insertion order before sorting."""
    register(_AnotherStubTool)
    register(_StubTool)
    # Both are registered; insertion order respected (sorted happens in all_tools)
    idx_another = _registered.index(_AnotherStubTool)
    idx_stub = _registered.index(_StubTool)
    assert idx_another < idx_stub


def test_register_does_not_affect_other_tools_in_registry() -> None:
    """Registering a new tool must not remove previously registered tools."""
    register(_StubTool)
    before = list(_registered)
    register(_AnotherStubTool)
    assert _StubTool in _registered
    assert _AnotherStubTool in _registered
    assert len(_registered) == len(before) + 1
