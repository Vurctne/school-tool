from __future__ import annotations

# Operating Statement is implemented but parked under "In development" for
# Round 15's free-tier launch. The class import below stays so existing tests
# that reference OperatingStatementTool keep working — but the auto-register
# call is suppressed so the tool does NOT appear in the live tool rail.
#
# To re-activate the tool: uncomment the register() line AND remove the
# corresponding entry from IN_DEVELOPMENT_TOOLS in toolkit/registry.py.
from tools.operating.frame import OperatingStatementTool  # noqa: F401

# from toolkit.registry import register
# register(OperatingStatementTool)  # type: ignore[arg-type]
