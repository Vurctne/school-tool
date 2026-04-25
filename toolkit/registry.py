from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from toolkit.base_tool import BaseTool

_registered: list[type[BaseTool]] = []


def register(tool_cls: type[BaseTool]) -> None:
    if tool_cls not in _registered:
        _registered.append(tool_cls)


def all_tools() -> list[type[BaseTool]]:
    # Import every tool package so its __init__.py's register(...) call fires.
    import tools.hyia  # noqa: F401
    import tools.master_budget  # noqa: F401
    import tools.sub_program  # noqa: F401

    return sorted(_registered, key=lambda c: (c.group, c.order, c.label))
