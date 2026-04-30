from __future__ import annotations

from toolkit.registry import register
from tools.refined_pal_search.frame import RefinedPalSearchTool

# RefinedPalSearchTool conforms structurally to the BaseTool Protocol; mypy
# can't see the structural match for a non-Protocol class declaration so it
# rejects the type. Same pattern used in tools/hyia/__init__.py and the other
# concrete tool registrations.
register(RefinedPalSearchTool)  # type: ignore[arg-type]
